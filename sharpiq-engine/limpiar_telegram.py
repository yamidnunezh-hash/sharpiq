"""
SharpIQ — Limpieza de canales Telegram
Borra todos los mensajes del bot en los 3 canales y envía mensaje de inicio limpio.
Ejecutar una sola vez: python limpiar_telegram.py
"""
import requests
import time
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_FREE_ID, TELEGRAM_YAMID_ID

BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

CANALES = [
    (TELEGRAM_CHAT_ID,  "VIP"),
    (TELEGRAM_FREE_ID,  "Público"),
    (TELEGRAM_YAMID_ID, "Yamid (alertas)"),
]

INICIO_VIP = (
    "🔷 *SharpIQ VIP — Nueva Era*\n\n"
    "Historial reiniciado. A partir de ahora cada pick queda registrado con EV real.\n\n"
    "📊 Win rate · ROI · Curva de bankroll — todo verificable desde cero.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "_La ventaja inteligente_"
)

INICIO_FREE = (
    "⚡ *SharpIQ — Nueva Era*\n\n"
    "Canal reiniciado. Picks gratuitos de alta precisión con IA.\n\n"
    "Para acceso VIP con todos los picks → @sharpiq\\_vip\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "_La ventaja inteligente_"
)

INICIO_YAMID = (
    "🔧 *SharpIQ Motor — Reiniciado*\n\n"
    "Estadísticas en cero. Motor listo para nuevo ciclo.\n"
    "Próximo barrido automático a las 9:00 AM COT."
)


def get_updates(offset=None):
    params = {"timeout": 5, "allowed_updates": ["channel_post"]}
    if offset:
        params["offset"] = offset
    r = requests.get(f"{BASE}/getUpdates", params=params, timeout=10)
    return r.json().get("result", [])


def delete_message(chat_id, msg_id):
    r = requests.post(f"{BASE}/deleteMessage", json={"chat_id": chat_id, "message_id": msg_id}, timeout=5)
    return r.json().get("ok", False)


def send_message(chat_id, text):
    r = requests.post(f"{BASE}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_notification": False
    }, timeout=10)
    return r.json()


def limpiar_canal(chat_id, nombre):
    print(f"\n[{nombre}] Obteniendo mensajes del bot...")
    eliminados = 0
    # Intenta borrar IDs en rango amplio (mensajes recientes)
    # El bot solo puede borrar sus propios mensajes en canales donde es admin
    for msg_id in range(1, 500):
        ok = delete_message(chat_id, msg_id)
        if ok:
            eliminados += 1
            time.sleep(0.05)
    print(f"[{nombre}] Eliminados: {eliminados} mensajes")


def main():
    print("=" * 50)
    print("SharpIQ — Limpieza de canales Telegram")
    print("=" * 50)

    # Intenta limpiar (solo borra mensajes del bot)
    for chat_id, nombre in CANALES:
        limpiar_canal(chat_id, nombre)

    time.sleep(1)

    # Envía mensaje de inicio limpio
    print("\nEnviando mensajes de nueva era...")
    r1 = send_message(TELEGRAM_CHAT_ID, INICIO_VIP)
    print(f"[VIP] {'OK' if r1.get('ok') else 'ERROR: ' + str(r1)}")

    r2 = send_message(TELEGRAM_FREE_ID, INICIO_FREE)
    print(f"[Público] {'OK' if r2.get('ok') else 'ERROR: ' + str(r2)}")

    r3 = send_message(TELEGRAM_YAMID_ID, INICIO_YAMID)
    print(f"[Yamid] {'OK' if r3.get('ok') else 'ERROR: ' + str(r3)}")

    print("\n[LISTO] Canales limpios y mensajes de inicio enviados.")
    print("\nNOTA: Telegram no permite borrar mensajes antiguos vía API.")
    print("Si quieres eliminar mensajes anteriores del historial visual,")
    print("ve a cada canal en Telegram → mantén presionado un mensaje →")
    print("'Seleccionar' → selecciona todos → 'Eliminar'.")


if __name__ == "__main__":
    main()
