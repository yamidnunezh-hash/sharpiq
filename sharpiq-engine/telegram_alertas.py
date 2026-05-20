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

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.py")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


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
