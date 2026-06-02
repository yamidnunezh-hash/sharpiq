# -*- coding: utf-8 -*-
"""
SharpIQ — Alertas Telegram
Envia notificaciones cuando el motor detecta value bets
"""
import requests
import json
import os
import sys
import html as _html
sys.path.insert(0, os.path.dirname(__file__))


def _cfg(nombre, default=None):
    """Lee una config: variable de entorno PRIMERO, luego config.py, luego default.
    Permite cambiar los chat_id de los canales sin tocar código (env vars / Secrets)."""
    v = os.environ.get(nombre)
    if v:
        return v
    try:
        import config
        return getattr(config, nombre, default)
    except ImportError:
        return default


def esc(s):
    """Escapa & < > para que un nombre (equipo/liga/jugador) con esos caracteres
    no rompa el HTML de Telegram (que descarta el mensaje entero en silencio)."""
    return _html.escape(str(s if s is not None else ""), quote=False)


def _fmt_fecha(fecha_iso):
    """'2026-06-03' -> '03/06/26 · ' (para anteponer a la hora). '' si no hay fecha."""
    try:
        y, m, d = (fecha_iso or "").split("-")
        return f"{d}/{m}/{y[2:]} · "
    except Exception:
        return ""


TELEGRAM_TOKEN      = _cfg("TELEGRAM_TOKEN")
TELEGRAM_FREE_ID    = _cfg("TELEGRAM_FREE_ID")     # Canal SharpIQ (gratis)
TELEGRAM_YAMID_ID   = _cfg("TELEGRAM_YAMID_ID")    # DM privado Yamid (todo lo interno)
TELEGRAM_ALERTAS_ID = _cfg("TELEGRAM_ALERTAS_ID")  # Canal SharpIQ Alertas (avisos de servicio)
# El canal VIP (TELEGRAM_CHAT_ID) se lee on-demand en get_chat_id().

# Precio mostrado en el bot. TODO(Yamid): confirmar precio final (lo definimos aparte).
PRECIO_VIP = "$60.000 COP/mes"

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.py")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# GIFs enviados al canal FREE — puedes reemplazar las URLs por las que prefieras
GIFS_WIN = [
    "https://media.giphy.com/media/26u4lOMA8JKSnL9Uk/giphy.gif",
    "https://media.giphy.com/media/3o7TKMt1VVNkHV2PaE/giphy.gif",
    "https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif",
]
GIFS_MANANA = [
    "https://media.giphy.com/media/077i6AULCXc0FKTj9s/giphy.gif",
    "https://media.giphy.com/media/l0HlMZrXA0mL9OHLU/giphy.gif",
    "https://media.giphy.com/media/WoD6JZnwap6s8/giphy.gif",
]


def get_chat_id():
    """Canal VIP. env var TELEGRAM_CHAT_ID primero, luego config.py."""
    return _cfg("TELEGRAM_CHAT_ID")


def guardar_chat_id(chat_id):
    """Guarda el chat_id en config.py"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        contenido = f.read()
    nuevo = contenido.replace(
        'TELEGRAM_CHAT_ID  = ""',
        f'TELEGRAM_CHAT_ID  = "{chat_id}"'
    ).replace(
        f'TELEGRAM_CHAT_ID  = "{chat_id}"',  # evitar doble reemplazo
        f'TELEGRAM_CHAT_ID  = "{chat_id}"'
    )
    # Reemplazo mas robusto
    import re
    nuevo = re.sub(r'TELEGRAM_CHAT_ID\s*=\s*"[^"]*"',
                   f'TELEGRAM_CHAT_ID  = "{chat_id}"', contenido)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(nuevo)
    print(f"  Chat ID guardado: {chat_id}")


def obtener_mi_chat_id():
    """Obtiene el chat_id del ultimo mensaje enviado al bot"""
    r = requests.get(f"{TELEGRAM_API}/getUpdates", timeout=10)
    data = r.json()
    updates = data.get("result", [])
    if not updates:
        return None
    ultimo = updates[-1]
    msg = ultimo.get("message") or ultimo.get("channel_post")
    if msg:
        return str(msg["chat"]["id"])
    return None


def enviar_mensaje(texto, chat_id=None):
    if not chat_id:
        chat_id = get_chat_id()
    if not chat_id:
        print("  Sin chat_id — ejecuta: py telegram_alertas.py setup")
        return False
    r = requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML"
    }, timeout=10)
    return r.status_code == 200


def _enviar_gif(chat_id, gif_url, caption=""):
    """Base: envia un GIF a cualquier chat_id. Falla silenciosamente."""
    if not chat_id:
        return False
    try:
        payload = {"chat_id": chat_id, "animation": gif_url}
        if caption:
            payload["caption"] = caption
            payload["parse_mode"] = "HTML"
        r = requests.post(f"{TELEGRAM_API}/sendAnimation", json=payload, timeout=15)
        return r.status_code == 200
    except Exception:
        return False


def enviar_gif_free(gif_url, caption=""):
    """Envia un GIF al canal free."""
    return _enviar_gif(TELEGRAM_FREE_ID, gif_url, caption)


def enviar_gif_vip(gif_url, caption=""):
    """Envia un GIF al canal VIP."""
    return _enviar_gif(get_chat_id(), gif_url, caption)


def enviar_alerta_value_bet(pred, mercado, vb):
    emoji = "🔥" if vb["clasificacion"] == "ALTO VALOR" else "💰"

    nombres_mercado = {
        "victoria_local":  "Victoria Local (1)",
        "empate":          "Empate (X)",
        "victoria_visita": "Victoria Visitante (2)",
        "over15":          "Over 1.5 Goles",
        "under15":         "Under 1.5 Goles",
        "over25":          "Over 2.5 Goles",
        "under25":         "Under 2.5 Goles",
        "over35":          "Over 3.5 Goles",
        "under35":         "Under 3.5 Goles",
        "btts_si":         "Ambos Marcan — Sí",
        "btts_no":         "Ambos Marcan — No",
        "doble_1x":        "Doble Oportunidad 1X",
        "doble_x2":        "Doble Oportunidad X2",
        "doble_12":        "Doble Oportunidad 12",
        "dnb_local":       "Draw No Bet — Local",
        "dnb_visita":      "Draw No Bet — Visitante",
    }
    cuota_key_map = {
        "victoria_local":  "1",
        "empate":          "X",
        "victoria_visita": "2",
        "over15":          "over15",
        "under15":         "under15",
        "over25":          "over25",
        "under25":         "under25",
        "over35":          "over35",
        "under35":         "under35",
        "btts_si":         "btts_si",
        "btts_no":         "btts_no",
        "doble_1x":        "doble_1x",
        "doble_x2":        "doble_x2",
        "doble_12":        "doble_12",
        "dnb_local":       "dnb_local",
        "dnb_visita":      "dnb_visita",
    }
    prob_key_map = {
        "victoria_local":  "victoria_local",
        "empate":          "empate",
        "victoria_visita": "victoria_visita",
        "over25":          "over25",
        "under25":         "under25",
        "btts_si":         "btts_si",
        "btts_no":         "btts_no",
    }

    # cuota: prefiere el valor ya calculado en vb, si no busca en pred["cuotas"]
    ck    = cuota_key_map.get(mercado, mercado)
    cuota = vb.get("cuota") or pred["cuotas"].get(ck) or pred["cuotas"].get(mercado, "?")
    # casa: viene en vb para deportes americanos, en cuotas para fútbol
    casa  = vb.get("casa") or pred["cuotas"].get(ck + "_casa", "") or pred["cuotas"].get(mercado + "_casa", "")
    # prob: pinn_prob para deportes americanos, prob_modelo para fútbol
    prob  = vb.get("pinn_prob") or vb.get("prob_modelo") or pred["probabilidades"].get(prob_key_map.get(mercado, mercado), 0)

    h, m2 = pred.get("hora", "00:00").split(":")
    hora_cot = f"{str((int(h)-5+24)%24).zfill(2)}:{m2} COT"

    casa_linea = f"\n🏠 <b>Casa recomendada:</b> {esc(casa)}" if casa else ""

    deporte = pred.get("deporte", "").upper()
    sport_emoji = pred.get("deporte_emoji") or {"NBA":"🏀","NHL":"🏒","MLB":"⚾","NFL":"🏈"}.get(deporte, "⚽")

    texto = f"""{emoji} <b>SharpIQ — {vb['clasificacion']}</b>

{sport_emoji} <b>{esc(pred['local'])} vs {esc(pred['visitante'])}</b>
🏆 {esc(pred.get('liga', ''))} | {_fmt_fecha(pred.get('fecha_evento',''))}{hora_cot}

📊 <b>Mercado:</b> {nombres_mercado.get(mercado, mercado)}
📈 <b>Probabilidad modelo:</b> {prob}%
💵 <b>Cuota:</b> {cuota}{casa_linea}
✅ <b>Valor esperado:</b> +{vb['ev_porcentaje']}%

<i>SharpIQ Engine — La ventaja inteligente</i>"""

    return enviar_mensaje(texto)


def enviar_resumen_dia(reporte):
    """
    Resumen privado para Yamid: solo muestra los 3 picks clasificados del día
    (no todos los value bets crudos que incluían longshots @13-34).
    """
    from datetime import date as _d
    total = reporte["total_partidos"]

    # Clasificar tiers para mostrar solo los picks reales del día
    try:
        from motor import clasificar_tiers
        tiers = clasificar_tiers(reporte)
    except Exception:
        tiers = {}

    _TIER_EMOJI = {"seguro": "🛡️ SEGURO", "principal": "⭐ PRINCIPAL", "alto_valor": "🔥 ALTO VALOR"}
    _SP_EMOJI   = {"NHL":"🏒","NBA":"🏀","MLB":"⚾","ATP":"🎾","WTA":"🎾","Boxeo":"🥊","UFC":"🥋"}

    picks_lines = []
    for k in ("seguro", "principal", "alto_valor"):
        t = tiers.get(k)
        if not t:
            continue
        p      = t["pred"]
        liga   = p.get("liga", "")
        emoji  = next((v for kw, v in _SP_EMOJI.items() if kw in liga.upper()), "⚽")
        hora_u = p.get("hora", "00:00")
        hh     = (int(hora_u[:2]) - 5 + 24) % 24
        hora_c = f"{hh:02d}:{hora_u[3:5]} COT"
        picks_lines.append(
            f"{_TIER_EMOJI[k]}\n"
            f"{emoji} {esc(p['local'])} vs {esc(p['visitante'])}\n"
            f"🏆 {esc(liga)} | {_fmt_fecha(p.get('fecha_evento',''))}{hora_c}\n"
            f"📊 {t['mercado_nombre']} @{t['cuota']} — "
            + (f"EV +{t['ev_pinn']}%" if t.get('ev_pinn') is not None else "sin EV")
            + f" | Prob {t['prob']}% | Kelly {t['kelly_pct']}%"
        )

    sep = "\n" + "─" * 28 + "\n"
    cuerpo = sep.join(picks_lines) if picks_lines else "Sin picks calificados hoy (EV insuficiente)"

    texto = (
        f"🤖 <b>SharpIQ — Resumen Motor</b>\n"
        f"📅 {reporte['fecha']} | {total} partidos analizados\n"
        f"{'─' * 28}\n\n"
        f"{cuerpo}\n\n"
        f"<i>sharpiq.co — La ventaja inteligente</i>"
    )
    return enviar_mensaje(texto, chat_id=TELEGRAM_YAMID_ID)


def enviar_aviso_yamid(texto):
    """Mensaje privado a Yamid (DM) — TODO lo interno: errores, debug, CLV, steam,
    confirmaciones de auto-publicado, nuevo referido. NUNCA va al canal Alertas."""
    return enviar_mensaje(texto, chat_id=TELEGRAM_YAMID_ID)


def enviar_alerta_servicio(texto):
    """Canal público 'SharpIQ Alertas' — SOLO avisos de servicio que el suscriptor
    debe ver: 'sin picks hoy', 'picks publicados', estado del servicio. Nada interno.
    Si no hay TELEGRAM_ALERTAS_ID configurado, no envía (no rompe el flujo)."""
    if not TELEGRAM_ALERTAS_ID:
        return False
    return enviar_mensaje(texto, chat_id=TELEGRAM_ALERTAS_ID)


def _sport_emoji(liga: str) -> str:
    liga_up = liga.upper()
    if any(x in liga_up for x in ("NHL", "HOCKEY")):       return "🏒"
    if any(x in liga_up for x in ("NBA", "BASKET")):       return "🏀"
    if any(x in liga_up for x in ("MLB", "BASEBALL")):     return "⚾"
    if any(x in liga_up for x in ("NFL", "UFL")):          return "🏈"
    if any(x in liga_up for x in ("TENIS", "ATP", "WTA")): return "🎾"
    return "⚽"


def enviar_canal_free(partido, liga, hora, pick_free=None, prob_free=None):
    """Publica en el canal público: un pick real de baja complejidad + teaser VIP."""
    sp = _sport_emoji(liga)
    if pick_free:
        texto = (
            f"{sp} <b>{esc(partido)}</b>\n"
            f"📅 {esc(liga)} | {esc(hora)}\n\n"
            f"📊 <b>Pick FREE:</b> <b>{esc(pick_free)}</b>\n"
            f"📈 Probabilidad estimada: {prob_free}%\n\n"
            f"💡 <i>Cuota exacta + 2 picks VIP adicionales con EV vs Pinnacle</i>\n"
            f"🔒 Acceso VIP → https://sharpiq.co\n\n"
            f"<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
        )
    else:
        texto = (
            f"{sp} <b>{esc(partido)}</b>\n"
            f"📅 {esc(liga)} | {esc(hora)}\n\n"
            f"🔎 El motor detectó valor en este partido.\n"
            f"📊 Predicción completa + cuota EV+ → solo en canal VIP\n\n"
            f"🔒 Únete → https://sharpiq.co\n\n"
            f"<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
        )
    return enviar_mensaje(texto, chat_id=TELEGRAM_FREE_ID)


def enviar_autopublicacion(partido, liga, mercado, cuota, hora, ev):
    """Avisa a Yamid cuando el motor auto-publicó una predicción."""
    texto = (
        f"🤖 <b>SharpIQ — Auto-publicado</b>\n\n"
        f"⚽ <b>{partido}</b>\n"
        f"🏆 {liga} | {hora}\n"
        f"📊 <b>Mercado:</b> {mercado}\n"
        f"💵 <b>Cuota:</b> {cuota}\n"
        f"⚡ <b>EV:</b> +{ev}%\n\n"
        f"✅ Publicado en sharpiq.co y enviado al canal VIP\n"
        f"<i>Revisa cuando puedas — puedes corregir desde el panel</i>"
    )
    return enviar_aviso_yamid(texto)


def notificar_referido(codigo_ref, telegram_usuario="desconocido"):
    """Avisa a Yamid cuando alguien registra un referido vía /referido CODIGO."""
    texto = (
        f"🎁 <b>SharpIQ — Nuevo Referido</b>\n\n"
        f"👤 <b>Nuevo suscriptor:</b> @{esc(telegram_usuario)}\n"
        f"🔗 <b>Código referidor:</b> <code>{esc(codigo_ref)}</code>\n\n"
        f"✅ Recompensa: <b>1 mes gratis</b> para el referidor con código {esc(codigo_ref)}\n"
        f"<i>Se aplica automáticamente al confirmarse el pago VIP del referido.</i>"
    )
    return enviar_aviso_yamid(texto)


def procesar_updates_bot():
    """
    Procesa mensajes nuevos al bot. Maneja /referido CODIGO y /start.
    Llama desde un cron o manualmente para procesar la cola.
    """
    try:
        r = requests.get(f"{TELEGRAM_API}/getUpdates", timeout=10)
        if r.status_code != 200:
            return
        updates = r.json().get("result", [])
    except Exception as e:
        print(f"procesar_updates_bot getUpdates error: {e}")
        return

    for upd in updates:
        uid = upd["update_id"]
        try:
            msg = upd.get("message", {})
            texto = msg.get("text", "").strip()
            usuario = msg.get("from", {}).get("username", "desconocido")
            chat_id_usuario = str(msg.get("chat", {}).get("id", ""))

            if texto.startswith("/start"):
                enviar_mensaje(
                    "👋 <b>Bienvenido a SharpIQ</b>\n\n"
                    "Predicciones deportivas con inteligencia artificial y EV vs Pinnacle. 🧠⚽🏀\n\n"
                    f"🔒 <b>Acceso VIP — {PRECIO_VIP}</b>\n"
                    "✅ 3 picks diarios con análisis completo\n"
                    "✅ Corners, tarjetas, handicap asiático\n"
                    "✅ EV vs Pinnacle en tiempo real\n\n"
                    "👇 <b>Suscríbete aquí (pago automático, acceso al instante):</b>\n"
                    "https://sharpiq.co\n\n"
                    "Tu acceso VIP se activa solo al confirmarse el pago. 🚀",
                    chat_id=chat_id_usuario
                )

            elif texto.startswith("/referido"):
                partes = texto.split()
                if len(partes) >= 2:
                    codigo = partes[1].strip().upper()
                    notificar_referido(codigo, usuario)
                    enviar_mensaje(
                        f"✅ Referido registrado correctamente.\n"
                        f"Código: <code>{esc(codigo)}</code>\n\n"
                        f"Tu referidor recibirá <b>1 mes gratis</b> de VIP al confirmarse tu pago. "
                        f"¡Gracias por hacer crecer la comunidad SharpIQ! 🔥",
                        chat_id=chat_id_usuario
                    )
                else:
                    enviar_mensaje(
                        "Uso: <code>/referido CODIGO</code>\nEjemplo: /referido ABC123",
                        chat_id=chat_id_usuario
                    )
        except Exception as e:
            print(f"procesar_updates_bot handle {uid}: {e}")
        finally:
            # Marca ESTE update como leído de inmediato → si algo falla, no se
            # reprocesa /start ni /referido en la siguiente corrida (idempotente).
            try:
                requests.get(f"{TELEGRAM_API}/getUpdates",
                             params={"offset": uid + 1, "timeout": 0}, timeout=10)
            except Exception:
                pass


def enviar_saludo_manana_free(partidos_hoy):
    """
    Saludo matutino al canal free — estilo dinámico CampeonesColombia.
    partidos_hoy: lista de dicts con claves 'local', 'visitante', 'liga', 'hora', 'fecha'
    """
    from datetime import date
    import random

    # Filtrar solo partidos de HOY
    hoy_iso = date.today().isoformat()
    partidos_hoy = [p for p in partidos_hoy if p.get("fecha", hoy_iso) == hoy_iso]

    dias = {0:"Lunes",1:"Martes",2:"Miércoles",3:"Jueves",4:"Viernes",5:"Sábado",6:"Domingo"}
    meses = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
             7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}
    hoy = date.today()
    dia_nombre = dias[hoy.weekday()]
    mes_nombre = meses[hoy.month]

    saludos = [
        "¡Buenos días comunidad! ☀️",
        "¡Arriba la comunidad SharpIQ! 🔥",
        "¡Feliz día a todos! Aquí empieza la jornada ⚡",
        "¡Buenos días! El fútbol no para y nosotros tampoco 💪",
    ]
    saludo = random.choice(saludos)

    texto = (
        f"{saludo}\n\n"
        f"📅 <b>{dia_nombre} {hoy.day} de {mes_nombre}</b>\n\n"
        f"⚽ <b>Partidos de hoy:</b>\n"
    )

    if partidos_hoy:
        # GIF de análisis SOLO si hay partidos (evita GIF en días vacíos)
        enviar_gif_free(random.choice(GIFS_MANANA))
        for p in partidos_hoy[:6]:  # máximo 6 partidos
            texto += f"• {esc(p['local'])} vs {esc(p['visitante'])} — {esc(p.get('hora',''))}\n"
            if p.get('liga'):
                texto += f"  🏆 {esc(p['liga'])}\n"
    else:
        texto += "• Jornada tranquila hoy — analizando opciones\n"

    texto += (
        f"\n🔒 <b>Las predicciones VIP ya están listas</b>\n"
        f"¿Quieres las cuotas y mercados exactos?\n"
        f"👉 Únete al canal VIP → https://sharpiq.co\n\n"
        f"<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
    )
    return enviar_mensaje(texto, chat_id=TELEGRAM_FREE_ID)


def enviar_resultado_free(partido, resultado_texto, emoji_resultado):
    """
    Publica el resultado de una predicción en el canal free.
    resultado_texto: 'WIN ✅' o 'LOSS ❌'
    emoji_resultado: '✅' o '❌'
    """
    import random
    wins = [
        "¡La IA no falla! 🤖🔥",
        "¡Eso es análisis de datos! 📊💪",
        "¡SharpIQ suma otro acierto! ⚡",
    ]
    losses = [
        "El fútbol siempre sorprende. Seguimos analizando 📊",
        "No todas entran, pero el EV positivo es clave a largo plazo 💡",
        "Pérdida asumida — el modelo aprende 🤖",
    ]
    es_win = emoji_resultado == "✅"
    comentario = random.choice(wins if es_win else losses)

    # GIF celebratorio solo en WIN
    if es_win:
        enviar_gif_free(random.choice(GIFS_WIN))

    texto = (
        f"{emoji_resultado} <b>Resultado — {esc(partido)}</b>\n\n"
        f"<b>{resultado_texto}</b>\n\n"
        f"{comentario}\n\n"
        f"🔒 Ver predicciones de mañana → https://sharpiq.co\n"
        f"<i>SharpIQ — La ventaja inteligente</i>"
    )
    return enviar_mensaje(texto, chat_id=TELEGRAM_FREE_ID)


def _construir_narrativa(pred, mercado, vb, canal):
    """
    Genera texto de análisis narrativo a partir de los datos de la predicción.
    canal: 'free' (incluye CTA a VIP) | 'vip' (más detallado, sin CTA)
    """
    local     = esc(pred["local"])
    visitante = esc(pred["visitante"])
    probs     = pred.get("probabilidades", {})
    cuotas    = pred.get("cuotas", {})
    forma_l   = pred.get("forma_local")  or {}
    forma_v   = pred.get("forma_visita") or {}
    h2h       = pred.get("h2h")          or {}

    ev        = vb.get("ev_porcentaje", 0)
    prob_raw  = 0.0
    cuota_api = 0.0
    cuota_justa_str = ""

    # Mapeo mercado → clave de probabilidad y cuota
    prob_map = {
        "victoria_local":  ("victoria_local",  "1"),
        "empate":          ("empate",           "X"),
        "victoria_visita": ("victoria_visita",  "2"),
        "over25":          ("over25",           "over25"),
        "under25":         ("under25",          "under25"),
        "over15":          ("over15",           "over15"),
        "under15":         ("under15",          "under15"),
        "over35":          ("over35",           "over35"),
        "btts_si":         ("btts_si",          "btts_si"),
        "btts_no":         ("btts_no",          "btts_no"),
    }
    mercado_nombres = {
        "victoria_local":  "Victoria Local",
        "empate":          "Empate",
        "victoria_visita": "Victoria Visitante",
        "over25":          "Over 2.5 Goles",
        "under25":         "Under 2.5 Goles",
        "over15":          "Over 1.5 Goles",
        "under15":         "Under 1.5 Goles",
        "over35":          "Over 3.5 Goles",
        "btts_si":         "Ambos Marcan — Sí",
        "btts_no":         "Ambos Marcan — No",
    }

    prob_key, cuota_key = prob_map.get(mercado, ("victoria_local", "1"))
    prob_raw  = probs.get(prob_key, 0)
    cuota_api = cuotas.get(cuota_key, 0)
    nombre_mercado = mercado_nombres.get(mercado, mercado)

    if prob_raw and prob_raw > 0:
        cuota_justa = round(100 / prob_raw, 2)
        cuota_justa_str = str(cuota_justa)

    goles_esp  = probs.get("total_goles_esperados", 0)
    goles_l    = probs.get("goles_esperados_local", 0)
    goles_v    = probs.get("goles_esperados_visita", 0)

    # ── Bloque de forma ──
    linea_forma = ""
    if forma_l.get("ataque_reciente") and forma_v.get("ataque_reciente"):
        atq_l = forma_l["ataque_reciente"]
        def_l = forma_l.get("defensa_reciente", 0)
        atq_v = forma_v["ataque_reciente"]
        def_v = forma_v.get("defensa_reciente", 0)
        linea_forma = (
            f"📋 <b>Forma reciente (últimos 5 partidos):</b>\n"
            f"• {local}: {atq_l} goles/p anotados, {def_l} recibidos\n"
            f"• {visitante}: {atq_v} goles/p anotados, {def_v} recibidos\n"
        )

    # ── Bloque H2H ──
    linea_h2h = ""
    if h2h.get("partidos"):
        n = h2h["partidos"]
        gpp = h2h.get("goles_por_partido", 0)
        vl  = round(h2h.get("victorias_local", 0)  * n)
        ve  = round(h2h.get("empates", 0)           * n)
        vv  = round(h2h.get("victorias_visita", 0)  * n)
        linea_h2h = (
            f"🔁 <b>Últimos {n} enfrentamientos:</b> "
            f"{vl}V {ve}E {vv}D — {gpp} goles/partido en promedio\n"
        )

    # ── Bloque de goles esperados ──
    linea_goles = (
        f"⚽ <b>Goles esperados:</b> {local} {goles_l} — {goles_v} {visitante} "
        f"(total ~{goles_esp})\n"
    ) if goles_esp else ""

    # ── Bloque EV — solo si EV es positivo ──
    tiene_valor = ev > 0 and cuota_api and cuota_justa_str and float(cuota_api) > float(cuota_justa_str)
    if tiene_valor:
        linea_ev = (
            f"📈 <b>El valor matemático:</b>\n"
            f"• Probabilidad del modelo: <b>{prob_raw}%</b> para {nombre_mercado}\n"
            f"• Cuota justa: <b>{cuota_justa_str}</b> — la casa ofrece <b>{cuota_api}</b>\n"
            f"• Ventaja a tu favor: <b>EV +{ev}%</b>\n"
        )
        pie_vip  = "<i>EV positivo confirmado — apuesta con criterio matemático.</i>"
        pie_free = (
            f"📊 Probabilidad SharpIQ: <b>{prob_raw}%</b> | Cuota justa: <b>{cuota_justa_str}</b>\n"
            f"La casa paga <b>{cuota_api}</b> — ventaja del <b>+{ev}%</b> a tu favor.\n\n"
            f"🔒 <b>¿Quieres la predicción completa?</b> 👉 https://sharpiq.co\n\n"
            f"<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
        )
        intro_free = "El modelo detecta que la casa <b>subestima</b> la probabilidad real de este resultado.\n\n"
    else:
        linea_ev = (
            f"📊 <b>Análisis del modelo:</b>\n"
            f"• Probabilidad estimada: <b>{prob_raw}%</b> para {nombre_mercado}\n"
            f"• Cuota disponible: <b>{cuota_api}</b>\n"
            f"⚠️ <i>Sin ventaja matemática detectada — partido para observar, no apostar.</i>\n"
        )
        pie_vip  = "<i>Este análisis es informativo. Hoy no hay apuesta con valor matemático confirmado.</i>"
        pie_free = (
            f"🔍 Partido interesante para seguir hoy.\n\n"
            f"🔒 Predicciones con valor confirmado → https://sharpiq.co\n\n"
            f"<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
        )
        intro_free = ""

    # ── Árbitro y sede neutral ────────────────────────────────────
    linea_contexto = ""
    arbitro = esc(pred.get("arbitro", ""))
    if arbitro:
        linea_contexto += f"👮 <b>Árbitro:</b> {arbitro}\n"
    if pred.get("sede_neutral"):
        linea_contexto += f"🏟️ <b>Sede neutral</b> — sin ventaja de local\n"
    if linea_contexto:
        linea_contexto = "\n" + linea_contexto

    if canal == "vip":
        texto = (
            f"🔬 <b>Análisis completo — SharpIQ Engine</b>\n\n"
            f"{linea_goles}"
            f"{linea_forma}"
            f"{linea_h2h}\n"
            f"{linea_ev}\n"
            f"{linea_contexto}"
            f"{pie_vip}"
        )
    else:  # free
        texto = (
            f"🔍 <b>{'¿Por qué esta predicción?' if tiene_valor else 'Partido del día'}</b>\n\n"
            f"{linea_goles}"
            f"{linea_h2h}\n"
            f"{intro_free}"
            f"{pie_free}"
        )

    return texto.strip()


def enviar_narrativa(pred, mercado, vb):
    """Envía el análisis narrativo al canal free y al canal VIP."""
    try:
        texto_free = _construir_narrativa(pred, mercado, vb, canal="free")
        texto_vip  = _construir_narrativa(pred, mercado, vb, canal="vip")
        enviar_mensaje(texto_free, chat_id=TELEGRAM_FREE_ID)
        enviar_mensaje(texto_vip,  chat_id=get_chat_id())
    except Exception as e:
        print(f"  Narrativa error: {e}")


def enviar_mercados_ext_vip(pred):
    """
    Envía al canal VIP el análisis de corners, tarjetas y handicap asiático.
    Se llama después del mensaje principal de la predicción.
    """
    ext = pred.get("mercados_ext", {})
    if not ext:
        return False

    local     = esc(pred["local"])
    visitante = esc(pred["visitante"])
    corners   = ext.get("corners",  {})
    tarjetas  = ext.get("tarjetas", {})
    handicap  = ext.get("handicap", {})

    # No enviar si los datos son todos cero (equipo sin stats en API-Football)
    c_esp = corners.get("corners_esperados", 0)
    t_esp = tarjetas.get("tarjetas_esperadas", 0)
    if (not c_esp or float(c_esp) == 0.0) and (not t_esp or float(t_esp) == 0.0):
        return False

    # ── Corners ──────────────────────────────────────────────────
    c_esp = corners.get("corners_esperados", "?")
    lineas_c = [f"• Esperados: <b>{c_esp}</b> totales en el partido"]
    for k, label in [("10", "Over/Under 9.5"), ("11", "Over/Under 10.5"), ("12", "Over/Under 11.5")]:
        ov = corners.get(f"corners_over{k}")
        un = corners.get(f"corners_under{k}")
        if ov is not None:
            cj_ov = round(100 / ov, 2) if ov > 0 else "—"
            cj_un = round(100 / un, 2) if un and un > 0 else "—"
            lim = int(k) - 0.5
            lineas_c.append(
                f"• O/U {lim}: Over {ov}% (justa {cj_ov}) | Under {un}% (justa {cj_un})"
            )

    # ── Tarjetas ─────────────────────────────────────────────────
    t_esp = tarjetas.get("tarjetas_esperadas", "?")
    lineas_t = [f"• Esperadas: <b>{t_esp}</b> tarjetas en el partido"]
    for k, label in [("3", "2.5"), ("4", "3.5"), ("5", "4.5")]:
        ov = tarjetas.get(f"tarjetas_over{k}")
        un = tarjetas.get(f"tarjetas_under{k}")
        if ov is not None:
            cj_ov = round(100 / ov, 2) if ov > 0 else "—"
            cj_un = round(100 / un, 2) if un and un > 0 else "—"
            lim = int(k) - 0.5
            lineas_t.append(
                f"• O/U {lim}: Over {ov}% (justa {cj_ov}) | Under {un}% (justa {cj_un})"
            )

    # ── Handicap Asiático ─────────────────────────────────────────
    lineas_ah = []
    ah_map = [
        ("ah_local_menos05",  f"{local} -0.5"),
        ("ah_visita_mas05",   f"{visitante} +0.5"),
        ("ah_local_menos1",   f"{local} -1"),
        ("ah_visita_mas1",    f"{visitante} +1"),
        ("ah_local_menos15",  f"{local} -1.5"),
        ("ah_visita_mas15",   f"{visitante} +1.5"),
    ]
    for key, nombre in ah_map:
        prob = handicap.get(key)
        if prob is not None:
            cj = round(100 / prob, 2) if prob > 0 else "—"
            lineas_ah.append(f"• {nombre}: {prob}% → cuota justa <b>{cj}</b>")

    texto = (
        f"📊 <b>Análisis Extendido — SharpIQ</b>\n\n"
        f"⚽ <b>{local} vs {visitante}</b>\n\n"
        f"🚩 <b>CORNERS</b>\n"
        + "\n".join(lineas_c) + "\n\n"
        f"🟨 <b>TARJETAS</b>\n"
        + "\n".join(lineas_t) + "\n\n"
        f"🔢 <b>HANDICAP ASIÁTICO</b>\n"
        + "\n".join(lineas_ah) + "\n\n"
        f"💡 <i>Si encuentras una cuota mayor a la justa → tienes ventaja matemática</i>\n\n"
        f"<i>SharpIQ — La ventaja inteligente</i>"
    )
    return enviar_mensaje(texto, chat_id=get_chat_id())


def _justificacion_pick(p, tier, mercado):
    """Lectura cualitativa del pick: contexto (final/altitud) + mercado + forma."""
    liga = (p.get("liga") or "")
    fl = p.get("forma_local") or {}
    fv = p.get("forma_visita") or {}
    bits = []
    if "final" in liga.lower() or p.get("sede_neutral"):
        bits.append("final a partido unico, suele ser cerrada y tactica")
    nombre = ((p.get("local") or "") + " " + (p.get("visitante") or "")).lower()
    for ciudad, alt in (("la paz","3600m"),("bolivar","3600m"),("cusco","3400m"),("cienciano","3400m"),("quito","2800m"),("bogota","2600m")):
        if ciudad in nombre:
            bits.append("factor altitud (" + alt + ") reduce ritmo y goles")
            break
    m = mercado
    if "under" in m:
        dl = fl.get("defensa_reciente"); dv = fv.get("defensa_reciente")
        if isinstance(dl,(int,float)) and isinstance(dv,(int,float)) and (dl+dv)/2 <= 1.1:
            bits.append("ambas defensas vienen firmes")
        bits.append("el modelo proyecta pocos goles")
    elif "over" in m:
        bits.append("se esperan goles por el poder ofensivo / defensas fragiles")
    elif "ambos" in m or "btts" in m:
        bits.append("ambos equipos generan y conceden con regularidad")
    elif any(k in m for k in ("gana","victoria","no bet","dnb","ndicap","handicap","doble")):
        bits.append("favorito con diferencia de nivel y mejor forma reciente")
    if not bits:
        return ""
    s = "; ".join(bits)
    return s[0].upper() + s[1:] + "."


def _analisis_experto(tier):
    """Bloque de analisis nivel analista: probabilidades, valor, forma, H2H y lectura."""
    try:
        p = tier.get("pred", {}) or {}
        probs = p.get("probabilidades", {}) or {}
        local = (p.get("local") or "").strip()
        visit = (p.get("visitante") or "").strip()
        mercado = (tier.get("mercado_nombre") or "").lower()
        cuota = tier.get("cuota", "")
        _ev_raw = tier.get("ev_pinn", tier.get("ev", None))   # None = pick sin ancla de mercado
        ev = round(_ev_raw or 0)
        kelly = tier.get("kelly_pct")
        L = esc(((local.split(" ")[0] if local else "Local"))[:11])
        V = esc(((visit.split(" ")[0] if visit else "Visita"))[:11])
        out = []
        vl = probs.get("victoria_local"); vv = probs.get("victoria_visita"); em = probs.get("empate")
        if vl is not None and vv is not None and em is not None:
            out.append("\U0001f4ca <b>Prob 1X2:</b> " + L + " " + format(vl, ".0f") + "% \u00b7 X " + format(em, ".0f") + "% \u00b7 " + V + " " + format(vv, ".0f") + "%")
        tot = []
        if probs.get("over25") is not None: tot.append("O2.5 " + str(round(probs["over25"])) + "%")
        if probs.get("under25") is not None: tot.append("U2.5 " + str(round(probs["under25"])) + "%")
        if probs.get("btts_si") is not None: tot.append("BTTS " + str(round(probs["btts_si"])) + "%")
        if tot:
            out.append("\U0001f4c8 <b>Goles:</b> " + " \u00b7 ".join(tot))
        if _ev_raw is None:
            linea = "\U0001f48e <b>Valor:</b> @" + str(cuota) + " \u00b7 sin EV (sin l\u00ednea de mercado)"
        else:
            ev_txt = ("+" + str(ev) + "%") if ev >= 0 else (str(ev) + "%")
            linea = "\U0001f48e <b>Valor:</b> @" + str(cuota) + " \u00b7 EV " + ev_txt
        if kelly: linea += " \u00b7 Kelly " + str(kelly) + "%"
        out.append(linea)
        def _f(f):
            if not isinstance(f, dict): return None
            af = f.get("ataque_reciente"); de = f.get("defensa_reciente"); fr = f.get("forma")
            if af is None or de is None: return None
            pts = (" \u00b7 " + str(round(fr*15)) + "/15") if isinstance(fr,(int,float)) else ""
            return format(af, ".1f") + " GF / " + format(de, ".1f") + " GC" + pts
        f1 = _f(p.get("forma_local")); f2 = _f(p.get("forma_visita"))
        if f1 or f2:
            parts = []
            if f1: parts.append(L + " " + f1)
            if f2: parts.append(V + " " + f2)
            out.append("\U0001f504 <b>Forma (ult.5):</b> " + " | ".join(parts))
        h = p.get("h2h")
        if isinstance(h, dict) and h.get("partidos"):
            n = h["partidos"]
            vlh = round(h.get("victorias_local", 0) * n)
            emh = round(h.get("empates", 0) * n)
            vvh = round(h.get("victorias_visita", 0) * n)
            gpp = h.get("goles_por_partido")
            gtxt = (" \u00b7 " + format(gpp, ".1f") + " goles/p") if isinstance(gpp,(int,float)) else ""
            out.append("\u2694\ufe0f <b>H2H (" + str(n) + "):</b> " + str(vlh) + "-" + str(emh) + "-" + str(vvh) + gtxt)
        just = _justificacion_pick(p, tier, mercado)
        if just:
            out.append("\U0001f9e0 <b>Lectura:</b> " + just)
        return "\n".join(out)
    except Exception:
        return "<i>Prob modelo: " + str(round(tier.get("prob", 0))) + "%</i>"


def enviar_tiers_vip(seguro, principal, alto_valor):
    """
    Mensaje único al canal VIP con los 3 picks del día en formato de tiers.
    Formato: 🛡️ SEGURO / ⭐ PICK PRINCIPAL / 🔥 ALTO VALOR
    """
    def _hcot(pred):
        h, m = pred.get("hora", "00:00").split(":")
        return f"{str((int(h)-5+24)%24).zfill(2)}:{m} COT"

    def _bloque(tier, emoji, label):
        if not tier:
            return None
        p  = tier["pred"]
        es_prop = p.get("es_player_prop", False)

        if es_prop:
            # Player prop: mostrar jugador + partido de contexto
            jugador  = esc(p.get("prop_jugador", p["local"]))
            partido  = esc(p.get("partido", p["visitante"]))
            ev_extra = ""
            if label == "ALTO VALOR":
                ev = round(tier.get("ev_pinn", tier.get("ev", 0)) or 0)
                ev_extra = f" — EV +{ev}%"
            prob_label = "Prob modelo"
            if label == "ALTO VALOR":
                stake_line = "⚠️ <i>Solo si tienes confianza — Stake: 2% del bankroll</i>"
            else:
                stake_line = "💰 <i>Stake recomendado: 3% del bankroll</i>"
            return (
                f"{emoji} <b>{label}</b>\n"
                f"🏀 <b>{jugador}</b>\n"
                f"📌 {partido}\n"
                f"🏆 {esc(p.get('liga',''))} | {_fmt_fecha(p.get('fecha_evento',''))}{_hcot(p)}\n"
                f"\U0001f3af <b>{tier['mercado_nombre']}</b> @{tier['cuota']}{ev_extra}\n"
                f"{_analisis_experto(tier)}\n"
                f"{stake_line}"
            )
        else:
            # Partido normal (fútbol u otro deporte de equipo)
            ev_extra = ""
            if label == "ALTO VALOR":
                ev = round(tier.get("ev_pinn", tier.get("ev", 0)) or 0)
                ev_extra = f" — EV +{ev}%"
            prob_label = "Prob DNB" if "dnb" in tier.get("mercado", "") else "Prob modelo"
            sp_emoji = _sport_emoji(p.get("liga", "") or p.get("deporte", ""))
            if label == "ALTO VALOR":
                stake_line = "⚠️ <i>Solo si tienes confianza — Stake: 2% del bankroll</i>"
            else:
                stake_line = "💰 <i>Stake recomendado: 3% del bankroll</i>"
            return (
                f"{emoji} <b>{label}</b>\n"
                f"{sp_emoji} <b>{esc(p['local'])} vs {esc(p['visitante'])}</b>\n"
                f"🏆 {esc(p.get('liga',''))} | {_fmt_fecha(p.get('fecha_evento',''))}{_hcot(p)}\n"
                f"\U0001f3af <b>{tier['mercado_nombre']}</b> @{tier['cuota']}{ev_extra}\n"
                f"{_analisis_experto(tier)}\n"
                f"{stake_line}"
            )

    bloques = [b for b in [
        _bloque(seguro,      "🛡️", "SEGURO"),
        _bloque(principal,   "⭐", "PICK PRINCIPAL"),
        _bloque(alto_valor,  "🔥", "ALTO VALOR"),
    ] if b]

    if not bloques:
        return False

    sep = "\n" + "─" * 30 + "\n\n"
    texto = (
        f"📊 <b>SharpIQ — Picks del Día</b>\n"
        f"{'─' * 30}\n\n"
        + sep.join(bloques)
        + "\n\n📌 <i>Regla: nunca más del 8% del bankroll en un día</i>"
        + "\n<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
    )
    return enviar_mensaje(texto, chat_id=get_chat_id())


def enviar_resultado_vip(partido, resultado_texto, emoji_resultado):
    """
    Publica el resultado de una predicción en el canal VIP con GIF celebratorio en WIN.
    """
    import random
    es_win = emoji_resultado == "✅"

    if es_win:
        enviar_gif_vip(random.choice(GIFS_WIN))

    wins_vip = [
        "¡Predicción acertada! 🤖🔥 Así se trabaja con datos.",
        "¡EV positivo convertido en ganancia! 📊💪",
        "¡Otro acierto SharpIQ! ⚡ La ventaja inteligente.",
    ]
    losses_vip = [
        "Resultado adverso — el modelo sigue aprendiendo 📊",
        "No todas entran. El largo plazo nos da la razón 💡",
        "Pérdida registrada. Bankroll y disciplina son clave 🤖",
    ]
    comentario = random.choice(wins_vip if es_win else losses_vip)

    texto = (
        f"{emoji_resultado} <b>Resultado VIP — {esc(partido)}</b>\n\n"
        f"<b>{resultado_texto}</b>\n\n"
        f"{comentario}\n\n"
        f"<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
    )
    return enviar_mensaje(texto, chat_id=get_chat_id())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        print("\nSetup SharpIQ Alertas Telegram")
        print("="*40)
        print("1. Abre Telegram")
        print("2. Busca @sharpiq_alertas_bot")
        print("3. Envia /start")
        input("4. Presiona Enter cuando hayas enviado /start...")

        chat_id = obtener_mi_chat_id()
        if chat_id:
            guardar_chat_id(chat_id)
            enviar_mensaje(f"SharpIQ Alertas activado!\nRecibiras notificaciones de value bets aqui.", chat_id)
            print(f"\nListo! Alertas configuradas para chat: {chat_id}")
        else:
            print("No se encontro mensaje. Asegurate de enviar /start al bot primero.")
    else:
        print("Uso: py telegram_alertas.py setup")
