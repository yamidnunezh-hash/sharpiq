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
from config import (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_YAMID_ID,
                    MP_ACCESS_TOKEN, CF_ACCOUNT_ID, CF_API_TOKEN, CF_KV_NAMESPACE)

DB_PATH  = os.path.join(BASE_DIR, "sharpiq.db")
API_URL  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
MP_PLAN  = "79abf20272b64347b16a901055c89d8c"
MP_LINK  = f"https://www.mercadopago.com.co/subscriptions/checkout?preapproval_plan_id={MP_PLAN}"

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

def crear_link_vip():
    """Genera un link de invitación único de un solo uso para el canal VIP."""
    r = requests.post(f"{API_URL}/createChatInviteLink", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "member_limit": 1,
        "name": f"VIP-{int(time.time())}"
    }, timeout=10).json()
    if r.get("ok"):
        return r["result"]["invite_link"]
    return None

def notificar_yamid(mensaje):
    requests.post(f"{API_URL}/sendMessage", json={
        "chat_id": TELEGRAM_YAMID_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }, timeout=10)


# ── ESTADOS DE CONVERSACIÓN ───────────────────────────────────────

_esperando_email = {}   # chat_id → True


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

def activar_por_email(email_pagador):
    """Llama esto cuando MP confirma un pago. Envía acceso VIP al usuario."""
    row = buscar_por_email(email_pagador)
    if not row:
        notificar_yamid(f"⚠️ Pago recibido de {email_pagador} pero no hay usuario registrado con ese email.")
        return False

    chat_id, username = row
    link = crear_link_vip()
    if not link:
        notificar_yamid(f"❌ No se pudo generar link VIP para @{username} ({email_pagador})")
        return False

    activar_vip(chat_id)
    enviar(chat_id,
        f"🎉 <b>¡Pago confirmado! Acceso VIP activado.</b>\n\n"
        f"Únete al canal SharpIQ VIP con este link exclusivo:\n{link}\n\n"
        f"<i>SharpIQ — La ventaja inteligente</i>"
    )
    notificar_yamid(f"💰 NUEVO VIP activado automáticamente\n👤 @{username} | {email_pagador}")
    return True


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
                    handle_start(chat_id, username, first_name)
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
