# -*- coding: utf-8 -*-
"""
SharpIQ — Bot Handler
Captura el email y chat_id del usuario cuando inicia el bot.
Lo guarda en SQLite + lo registra para que el webhook de MP active el acceso VIP.
"""
import os, sys, time, json, sqlite3, requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
try:
    from config import (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_YAMID_ID,
                        MP_ACCESS_TOKEN, CF_ACCOUNT_ID, CF_API_TOKEN, CF_KV_NAMESPACE)
except ImportError:
    TELEGRAM_TOKEN    = os.environ.get('TELEGRAM_TOKEN', '')
    TELEGRAM_CHAT_ID  = os.environ.get('TELEGRAM_CHAT_ID', '')
    TELEGRAM_YAMID_ID = os.environ.get('TELEGRAM_YAMID_ID', '')
    MP_ACCESS_TOKEN   = os.environ.get('MP_ACCESS_TOKEN', '')
    CF_ACCOUNT_ID     = os.environ.get('CF_ACCOUNT_ID', '')
    CF_API_TOKEN      = os.environ.get('CF_API_TOKEN', '')
    CF_KV_NAMESPACE   = os.environ.get('CF_KV_NAMESPACE', '')

DB_PATH  = os.path.join(BASE_DIR, "sharpiq.db")
API_URL  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
MP_PLAN = "79abf20272b64347b16a901055c89d8c"

def mp_link(chat_id):
    """Link de MP con external_reference = chat_id para auto-activar sin pedir email."""
    return (f"https://www.mercadopago.com.co/subscriptions/checkout"
            f"?preapproval_plan_id={MP_PLAN}&external_reference={chat_id}")

# ── DB ────────────────────────────────────────────────────────────

def _db():
    return sqlite3.connect(DB_PATH)

def inicializar_bot_db():
    with _db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS vip_pendientes (
            chat_id     INTEGER PRIMARY KEY,
            username    TEXT,
            email       TEXT,
            estado      TEXT DEFAULT 'pendiente',
            creado      TEXT,
            activado    TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS trials (
            chat_id     INTEGER PRIMARY KEY,
            username    TEXT,
            inicio      TEXT,
            fin         TEXT,
            usado       INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS referidos (
            codigo          TEXT PRIMARY KEY,
            referidor_id    INTEGER,
            referidor_user  TEXT,
            referido_id     INTEGER,
            referido_user   TEXT,
            recompensa      INTEGER DEFAULT 0,
            creado          TEXT
        )""")

def guardar_pendiente(chat_id, username, email):
    with _db() as c:
        c.execute("""INSERT OR REPLACE INTO vip_pendientes
                     (chat_id, username, email, estado, creado)
                     VALUES (?, ?, ?, 'pendiente', ?)""",
                  (chat_id, username, email, datetime.now().isoformat()))
    # Escribir en Cloudflare KV para que el Worker pueda accederlo
    _kv_put(f"email:{email.lower().strip()}", str(chat_id))

def _kv_put(key, value):
    if not CF_ACCOUNT_ID or not CF_API_TOKEN or not CF_KV_NAMESPACE:
        return
    try:
        requests.put(
            f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE}/values/{key}",
            headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
            data=value,
            timeout=5
        )
    except Exception:
        pass

def activar_vip(chat_id):
    with _db() as c:
        c.execute("UPDATE vip_pendientes SET estado='activo', activado=? WHERE chat_id=?",
                  (datetime.now().isoformat(), chat_id))

def buscar_por_email(email):
    with _db() as c:
        row = c.execute("SELECT chat_id, username FROM vip_pendientes WHERE email=? AND estado='pendiente'",
                        (email.lower().strip(),)).fetchone()
    return row

def listar_vip():
    with _db() as c:
        return c.execute("SELECT chat_id, username, email, estado, creado FROM vip_pendientes ORDER BY creado DESC").fetchall()


# ── TELEGRAM ─────────────────────────────────────────────────────

def enviar(chat_id, texto, reply_markup=None):
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{API_URL}/sendMessage", json=payload, timeout=10)

def crear_link_vip(expire_days=None, nombre="VIP"):
    """Genera un link de invitación único de un solo uso para el canal VIP.
    expire_days: si se indica, el link expira en N días (para trials)."""
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "member_limit": 1,
        "name": f"{nombre}-{int(time.time())}"
    }
    if expire_days:
        payload["expire_date"] = int(time.time()) + expire_days * 86400
    r = requests.post(f"{API_URL}/createChatInviteLink", json=payload, timeout=10).json()
    if r.get("ok"):
        return r["result"]["invite_link"]
    return None

def codigo_referido(chat_id):
    """Genera código de referido único basado en chat_id."""
    return f"SIQ{str(chat_id)[-5:]}"

def notificar_yamid(mensaje):
    requests.post(f"{API_URL}/sendMessage", json={
        "chat_id": TELEGRAM_YAMID_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }, timeout=10)


# ── ESTADOS DE CONVERSACIÓN ───────────────────────────────────────

_esperando_email  = {}   # chat_id → True
_esperando_metodo = {}   # chat_id → método elegido ('mp' | 'paypal')


# ── HANDLERS ─────────────────────────────────────────────────────

def handle_start(chat_id, username, first_name):
    _esperando_email[chat_id] = True
    enviar(chat_id,
        f"👋 Hola <b>{first_name}</b>, bienvenido a <b>SharpIQ VIP</b>.\n\n"
        f"Para activar tu membresía automáticamente después del pago, "
        f"necesito tu email de Mercado Pago.\n\n"
        f"✉️ <b>¿Cuál es tu email?</b>"
    )

def handle_email(chat_id, username, email):
    if "@" not in email or "." not in email:
        enviar(chat_id, "⚠️ Ese no parece un email válido. Escríbelo de nuevo:")
        return

    guardar_pendiente(chat_id, username, email.lower().strip())
    _esperando_email.pop(chat_id, None)

    enviar(chat_id,
        f"✅ <b>Email registrado:</b> {email}\n\n"
        f"Ahora completa tu suscripción en Mercado Pago. "
        f"Usa el mismo email <b>{email}</b> al pagar.\n\n"
        f"Cuando confirmes el pago, tu acceso al canal VIP se activará automáticamente.\n\n"
        f"👇 <a href=\"{MP_LINK}\">Ir a pagar — $10 USD/mes</a>",
        reply_markup={"inline_keyboard": [[
            {"text": "💳 Suscribirme ahora", "url": MP_LINK}
        ]]}
    )
    notificar_yamid(f"🔔 Nuevo interesado VIP\n👤 @{username} | chat_id: {chat_id}\n✉️ {email}")

def handle_activar(chat_id, username):
    """Comando manual /activar para casos donde el webhook no llega."""
    link = crear_link_vip()
    if link:
        activar_vip(chat_id)
        enviar(chat_id,
            f"🎉 <b>¡Acceso VIP activado!</b>\n\n"
            f"Únete al canal con este link exclusivo (un solo uso):\n{link}\n\n"
            f"<i>SharpIQ — La ventaja inteligente</i>"
        )
        notificar_yamid(f"✅ VIP activado manualmente\n👤 @{username} | chat_id: {chat_id}")
    else:
        enviar(chat_id, "⚠️ Error generando el link. Contacta a @yamidnunezh")

def handle_prueba(chat_id, username):
    """7 días gratis — un solo uso por usuario."""
    with _db() as c:
        usado = c.execute("SELECT usado FROM trials WHERE chat_id=?", (chat_id,)).fetchone()
    if usado and usado[0]:
        enviar(chat_id,
            "⚠️ Ya usaste tu prueba gratuita de 7 días.\n\n"
            f"Para continuar con acceso VIP:\n"
            f"👇 <a href=\"{MP_LINK}\">Suscribirme — $10 USD/mes</a>",
            reply_markup={"inline_keyboard": [[{"text": "💳 Suscribirme ahora", "url": MP_LINK}]]}
        )
        return

    link = crear_link_vip(expire_days=7, nombre="TRIAL")
    if not link:
        enviar(chat_id, "⚠️ Error activando la prueba. Contacta a @yamidnunezh")
        return

    from datetime import timedelta
    inicio = datetime.now()
    fin    = inicio + timedelta(days=7)
    with _db() as c:
        c.execute("""INSERT OR REPLACE INTO trials (chat_id, username, inicio, fin, usado)
                     VALUES (?,?,?,?,1)""",
                  (chat_id, username, inicio.isoformat(), fin.isoformat()))

    enviar(chat_id,
        f"🎁 <b>¡7 días GRATIS en SharpIQ VIP!</b>\n\n"
        f"Accede al canal con este link exclusivo:\n{link}\n\n"
        f"⏰ Válido hasta: <b>{fin.strftime('%d/%m/%Y')}</b>\n\n"
        f"Tendrás acceso a:\n"
        f"✅ Picks diarios con EV\n"
        f"✅ Corners, tarjetas, handicap\n"
        f"✅ Alertas en vivo durante partidos\n\n"
        f"<i>SharpIQ — La ventaja inteligente</i>"
    )
    notificar_yamid(f"🎁 Trial activado\n👤 @{username} | chat_id: {chat_id}\nFin: {fin.strftime('%d/%m/%Y')}")

def handle_micodigo(chat_id, username):
    """Muestra el código de referido personal y link para compartir."""
    codigo = codigo_referido(chat_id)
    link_ref = f"https://t.me/sharpiq_alertas_bot?start=ref_{codigo}"
    enviar(chat_id,
        f"🔗 <b>Tu código de referido</b>\n\n"
        f"Código: <code>{codigo}</code>\n\n"
        f"Comparte este link con tus amigos:\n{link_ref}\n\n"
        f"🎁 <b>¿Cómo funciona?</b>\n"
        f"Cuando un amigo se suscriba usando tu link, recibes <b>1 mes gratis</b>.\n\n"
        f"<i>SharpIQ — La ventaja inteligente</i>"
    )

def handle_start(chat_id, username, first_name, ref_codigo=None):
    # Registrar referido si viene con código
    if ref_codigo:
        with _db() as c:
            ya = c.execute("SELECT 1 FROM referidos WHERE referido_id=?", (chat_id,)).fetchone()
            if not ya and ref_codigo != codigo_referido(chat_id):
                referidor_id = None
                for row in _listar_todos():
                    if codigo_referido(row[0]) == ref_codigo:
                        referidor_id = row[0]
                        break
                if referidor_id:
                    with _db() as c2:
                        c2.execute("""INSERT OR REPLACE INTO referidos
                                      (codigo, referidor_id, referidor_user, referido_id, referido_user, creado)
                                      VALUES (?,?,?,?,?,?)""",
                                   (ref_codigo, referidor_id, ref_codigo, chat_id, username, datetime.now().isoformat()))
                    notificar_yamid(f"🔗 Nuevo referido\nReferidor ID: {referidor_id}\nNuevo usuario: @{username}")

    link = mp_link(chat_id)
    # Guardar chat_id en DB esperando confirmación de pago
    guardar_pendiente(chat_id, username, f"pending_{chat_id}@mp")

    enviar(chat_id,
        f"👋 Hola <b>{first_name}</b>, bienvenido a <b>SharpIQ VIP</b>.\n\n"
        f"📊 Picks diarios con IA · Corners · Tarjetas · Alertas en vivo\n"
        f"✅ Acceso inmediato al canal VIP tras el pago\n"
        f"💰 <b>$10 USD/mes</b> — cancela cuando quieras\n\n"
        f"👇 Toca el botón para activar tu membresía:",
        reply_markup={"inline_keyboard": [
            [{"text": "💳 Suscribirme ahora — $10 USD/mes", "url": link}],
            [{"text": "🎁 Probar 7 días GRATIS",            "callback_data": "pago_prueba"}]
        ]}
    )

def _listar_todos():
    with _db() as c:
        return c.execute("SELECT chat_id FROM vip_pendientes").fetchall()

def handle_status(chat_id):
    """Solo para Yamid — ver lista de pendientes."""
    if str(chat_id) != str(TELEGRAM_YAMID_ID):
        return
    rows = listar_vip()
    if not rows:
        enviar(chat_id, "No hay usuarios registrados aún.")
        return
    lineas = ["<b>Usuarios VIP:</b>\n"]
    for r in rows[:20]:
        lineas.append(f"@{r[1]} | {r[2]} | {r[3]}")
    enviar(chat_id, "\n".join(lineas))


# ── ACTIVACIÓN POR EMAIL (llamada desde webhook) ──────────────────

def activar_por_referencia(external_reference):
    """
    Activa VIP usando external_reference = chat_id (sin necesitar email).
    Llama esto desde el webhook de MP cuando confirma el pago.
    """
    try:
        chat_id = int(external_reference)
    except (ValueError, TypeError):
        # Fallback: intentar por email (compatibilidad con flujo antiguo)
        return activar_por_email(external_reference)

    with _db() as c:
        row = c.execute("SELECT username FROM vip_pendientes WHERE chat_id=?",
                        (chat_id,)).fetchone()
    username = row[0] if row else "usuario"

    link = crear_link_vip()
    if not link:
        notificar_yamid(f"❌ No se pudo generar link VIP para chat_id {chat_id}")
        return False

    activar_vip(chat_id)
    enviar(chat_id,
        f"🎉 <b>¡Pago confirmado! Acceso VIP activado.</b>\n\n"
        f"Únete al canal SharpIQ VIP con este link exclusivo:\n{link}\n\n"
        f"✅ Acceso a todos los picks diarios\n"
        f"✅ Alertas en vivo durante partidos\n\n"
        f"<i>SharpIQ — La ventaja inteligente</i>"
    )
    notificar_yamid(f"💰 NUEVO VIP activado\n👤 @{username} | chat_id: {chat_id}")
    return True

def activar_por_email(email_pagador):
    """Fallback: activa por email (flujo antiguo o casos especiales)."""
    row = buscar_por_email(email_pagador)
    if not row:
        notificar_yamid(f"⚠️ Pago de {email_pagador} sin usuario registrado.")
        return False
    chat_id, username = row
    return activar_por_referencia(str(chat_id))


# ── POLLING LOOP ──────────────────────────────────────────────────

def correr():
    inicializar_bot_db()
    print("SharpIQ Bot Handler iniciado — @sharpiq_alertas_bot")
    offset = 0

    while True:
        try:
            r = requests.get(f"{API_URL}/getUpdates",
                             params={"offset": offset, "timeout": 30},
                             timeout=35).json()

            for update in r.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                if not msg:
                    continue

                chat_id   = msg["chat"]["id"]
                username  = msg["chat"].get("username", "sin_username")
                first_name = msg["chat"].get("first_name", "")
                text      = msg.get("text", "").strip()

                if text.startswith("/start"):
                    partes = text.split()
                    ref = None
                    if len(partes) > 1 and partes[1].startswith("ref_"):
                        ref = partes[1][4:]
                    handle_start(chat_id, username, first_name, ref_codigo=ref)
                elif text.startswith("/prueba"):
                    handle_prueba(chat_id, username)
                elif text.startswith("/micodigo"):
                    handle_micodigo(chat_id, username)
                elif text.startswith("/activar"):
                    handle_activar(chat_id, username)
                elif text.startswith("/status"):
                    handle_status(chat_id)
                elif chat_id in _esperando_email:
                    handle_email(chat_id, username, text)

        except KeyboardInterrupt:
            print("Bot detenido.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    correr()
