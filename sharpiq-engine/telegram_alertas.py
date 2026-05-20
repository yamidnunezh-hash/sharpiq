# -*- coding: utf-8 -*-
"""
SharpIQ — Alertas Telegram
Envia notificaciones cuando el motor detecta value bets
"""
import requests
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from config import TELEGRAM_TOKEN
try:
    from config import TELEGRAM_YAMID_ID
except ImportError:
    TELEGRAM_YAMID_ID = None
try:
    from config import TELEGRAM_FREE_ID
except ImportError:
    TELEGRAM_FREE_ID = None

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
    """Lee el chat_id guardado en config.py"""
    from config import TELEGRAM_CHAT_ID
    return TELEGRAM_CHAT_ID


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


def enviar_gif_free(gif_url, caption=""):
    """Envia un GIF al canal free. Falla silenciosamente si Telegram no puede descargarlo."""
    if not TELEGRAM_FREE_ID:
        return False
    try:
        payload = {"chat_id": TELEGRAM_FREE_ID, "animation": gif_url}
        if caption:
            payload["caption"] = caption
            payload["parse_mode"] = "HTML"
        r = requests.post(f"{TELEGRAM_API}/sendAnimation", json=payload, timeout=15)
        return r.status_code == 200
    except Exception:
        return False


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

    ck    = cuota_key_map.get(mercado, "1")
    cuota = pred["cuotas"].get(ck, "?")
    casa  = pred["cuotas"].get(ck + "_casa", "")
    prob  = pred["probabilidades"].get(prob_key_map.get(mercado, "victoria_local"), 0)

    h, m2 = pred.get("hora", "00:00").split(":")
    hora_cot = f"{str((int(h)-5+24)%24).zfill(2)}:{m2} COT"

    casa_linea = f"\n🏠 <b>Casa recomendada:</b> {casa}" if casa else ""

    texto = f"""{emoji} <b>SharpIQ — {vb['clasificacion']}</b>

⚽ <b>{pred['local']} vs {pred['visitante']}</b>
🏆 {pred.get('liga', '')} | {hora_cot}

📊 <b>Mercado:</b> {nombres_mercado.get(mercado, mercado)}
📈 <b>Probabilidad modelo:</b> {prob}%
💵 <b>Cuota:</b> {cuota}{casa_linea}
✅ <b>Valor esperado:</b> +{vb['ev_porcentaje']}%

<i>SharpIQ Engine — La ventaja inteligente</i>"""

    return enviar_mensaje(texto)


def enviar_resumen_dia(reporte):
    total = reporte["total_partidos"]
    preds = reporte["predicciones"]
    value_bets = sum(1 for p in preds for v in p["value_bets"].values() if v["tiene_valor"])
    alto_valor = sum(1 for p in preds for v in p["value_bets"].values() if v["clasificacion"] == "ALTO VALOR")

    texto = f"""📋 <b>SharpIQ — Resumen del dia</b>
📅 {reporte['fecha']}

⚽ Partidos analizados: {total}
💰 Value Bets detectados: {value_bets}
🔥 Alto Valor: {alto_valor}

"""
    nombres = {
        "victoria_local":"Local (1)","empate":"Empate (X)","victoria_visita":"Visitante (2)",
        "over25":"Over 2.5","under25":"Under 2.5","btts_si":"BTTS Sí","btts_no":"BTTS No",
    }
    cuota_map = {
        "victoria_local":"1","empate":"X","victoria_visita":"2",
        "over25":"over25","under25":"under25","btts_si":"btts_si","btts_no":"btts_no",
    }
    for pred in preds:
        tiene_vb = any(v["tiene_valor"] for v in pred["value_bets"].values() if v)
        if tiene_vb:
            texto += f"• {pred['local']} vs {pred['visitante']}\n"
            for m, vb in pred["value_bets"].items():
                if vb and vb["tiene_valor"]:
                    ck   = cuota_map.get(m, "1")
                    cuota = pred["cuotas"].get(ck, "")
                    casa  = pred["cuotas"].get(ck + "_casa", "")
                    casa_str = f" [{casa}]" if casa else ""
                    texto += f"  → {nombres.get(m,m)} @ {cuota}{casa_str}: EV +{vb['ev_porcentaje']}%\n"

    texto += "\n<i>sharpiq.co — La ventaja inteligente</i>"
    # Resumen va solo a Yamid, no al canal VIP
    return enviar_mensaje(texto, chat_id=TELEGRAM_YAMID_ID)


def enviar_aviso_yamid(texto):
    """Mensaje privado a Yamid — alertas del motor, auto-publicaciones, errores."""
    return enviar_mensaje(texto, chat_id=TELEGRAM_YAMID_ID)


def enviar_canal_free(partido, liga, hora):
    """Publica un teaser en el canal público — mercado oculto para generar curiosidad."""
    texto = (
        f"⚽ <b>{partido}</b>\n"
        f"🏆 {liga} | {hora}\n\n"
        f"📊 <b>Predicción:</b> 🔒 Solo VIP\n"
        f"💵 <b>Cuota:</b> 🔒 Solo VIP\n\n"
        f"🔥 <b>¿Quieres la predicción completa?</b>\n"
        f"Únete al canal VIP → @SharpIQVIP\n\n"
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
        f"👤 <b>Nuevo suscriptor:</b> @{telegram_usuario}\n"
        f"🔗 <b>Código referidor:</b> <code>{codigo_ref}</code>\n\n"
        f"✅ Acción: dar <b>7 días extra</b> al suscriptor con código {codigo_ref}\n"
        f"<i>Verifica el pago en MercadoPago antes de aplicar el beneficio</i>"
    )
    return enviar_aviso_yamid(texto)


def procesar_updates_bot():
    """
    Procesa mensajes nuevos al bot. Maneja /referido CODIGO.
    Llama desde un cron o manualmente para procesar la cola.
    """
    r = requests.get(f"{TELEGRAM_API}/getUpdates", timeout=10)
    if r.status_code != 200:
        return
    updates = r.json().get("result", [])
    ultimo_id = None

    for upd in updates:
        ultimo_id = upd["update_id"]
        msg = upd.get("message", {})
        texto = msg.get("text", "")
        usuario = msg.get("from", {}).get("username", "desconocido")
        chat_id_usuario = str(msg.get("chat", {}).get("id", ""))

        if texto.startswith("/referido"):
            partes = texto.split()
            if len(partes) >= 2:
                codigo = partes[1].strip().upper()
                notificar_referido(codigo, usuario)
                # Confirmar al usuario que registró
                enviar_mensaje(
                    f"✅ Referido registrado correctamente.\n"
                    f"Código: <code>{codigo}</code>\n\n"
                    f"Tu amigo recibirá 7 días extra en su suscripción. "
                    f"¡Gracias por hacer crecer la comunidad SharpIQ! 🔥",
                    chat_id=chat_id_usuario
                )
            else:
                enviar_mensaje(
                    "Uso: <code>/referido CODIGO</code>\nEjemplo: /referido ABC123",
                    chat_id=chat_id_usuario
                )

    # Marcar updates como leídos
    if ultimo_id is not None:
        requests.get(f"{TELEGRAM_API}/getUpdates",
                     params={"offset": ultimo_id + 1}, timeout=10)


def enviar_saludo_manana_free(partidos_hoy):
    """
    Saludo matutino al canal free — estilo dinámico CampeonesColombia.
    partidos_hoy: lista de dicts con claves 'local', 'visitante', 'liga', 'hora'
    """
    from datetime import date
    import random

    # GIF de análisis antes del texto
    enviar_gif_free(random.choice(GIFS_MANANA))

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
        for p in partidos_hoy[:6]:  # máximo 6 partidos
            texto += f"• {p['local']} vs {p['visitante']} — {p.get('hora','')}\n"
            if p.get('liga'):
                texto += f"  🏆 {p['liga']}\n"
    else:
        texto += "• Jornada tranquila hoy — analizando opciones\n"

    texto += (
        f"\n🔒 <b>Las predicciones VIP ya están listas</b>\n"
        f"¿Quieres las cuotas y mercados exactos?\n"
        f"👉 Únete al canal VIP → @SharpIQVIP\n\n"
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
        f"{emoji_resultado} <b>Resultado — {partido}</b>\n\n"
        f"<b>{resultado_texto}</b>\n\n"
        f"{comentario}\n\n"
        f"🔒 Ver predicciones de mañana → @SharpIQVIP\n"
        f"<i>SharpIQ — La ventaja inteligente</i>"
    )
    return enviar_mensaje(texto, chat_id=TELEGRAM_FREE_ID)


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
