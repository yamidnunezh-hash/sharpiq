# -*- coding: utf-8 -*-
"""
SharpIQ — Push Notifications
Envía notificaciones push web a suscriptores usando VAPID/Web Push.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
SUBS_PATH = os.path.join(BASE_DIR, "push_subs.json")


def _cargar_subs():
    if not os.path.exists(SUBS_PATH):
        return []
    with open(SUBS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _guardar_subs(subs):
    with open(SUBS_PATH, "w", encoding="utf-8") as f:
        json.dump(subs, f, ensure_ascii=False, indent=2)


def guardar_suscripcion(sub_json):
    """Guarda una nueva suscripción push (llamado desde servidor.py)."""
    subs = _cargar_subs()
    endpoint = sub_json.get("endpoint", "")
    # Evitar duplicados
    if not any(s.get("endpoint") == endpoint for s in subs):
        subs.append(sub_json)
        _guardar_subs(subs)
        print(f"  Push sub guardada: {endpoint[:50]}...")
        return True
    return False


def enviar_push(titulo, cuerpo, url="/", icono="/assets/icon-192.png"):
    """Envía notificación push a todos los suscriptores activos."""
    from pywebpush import webpush, WebPushException
    from config import VAPID_PUBLIC_KEY, VAPID_PRIVATE_PEM, VAPID_CLAIMS

    subs = _cargar_subs()
    if not subs:
        print("  Sin suscriptores push")
        return 0

    payload = json.dumps({
        "title": titulo,
        "body":  cuerpo,
        "icon":  icono,
        "url":   url,
    })

    enviados = 0
    fallidas = []
    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_PEM,
                vapid_claims=VAPID_CLAIMS,
            )
            enviados += 1
        except WebPushException as e:
            status = e.response.status_code if e.response else 0
            if status in (404, 410):  # suscripción expirada
                fallidas.append(sub.get("endpoint"))
            else:
                print(f"  Push error ({status}): {e}")

    # Limpiar subs expiradas
    if fallidas:
        subs = [s for s in subs if s.get("endpoint") not in fallidas]
        _guardar_subs(subs)
        print(f"  {len(fallidas)} subs expiradas eliminadas")

    print(f"  Push enviado: {enviados}/{len(subs)+len(fallidas)} suscriptores")
    return enviados


def enviar_push_prediccion(partido, mercado, cuota, ev):
    """Shortcut para notificar nueva predicción VIP."""
    return enviar_push(
        titulo=f"⚽ SharpIQ — Nueva predicción",
        cuerpo=f"{partido} · {mercado} @ {cuota} · EV +{ev}%",
        url="/",
    )


if __name__ == "__main__":
    # Test: muestra cuántos suscriptores hay
    subs = _cargar_subs()
    print(f"Suscriptores push activos: {len(subs)}")
