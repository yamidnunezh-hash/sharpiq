"""
SharpIQ — Pagos MercadoPago
Suscripción recurrente VIP: $15 USD/mes
"""
import os, sys, json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, Request, Depends
import requests as http

from .auth import usuario_activo
from .db   import db

router = APIRouter()

try:
    from config import MP_ACCESS_TOKEN, MP_PUBLIC_KEY
except ImportError:
    MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "")
    MP_PUBLIC_KEY   = os.environ.get("MP_PUBLIC_KEY", "")

MP_BASE = "https://api.mercadopago.com"

PLANES = {
    "vip": {
        "nombre":      "SharpIQ VIP",
        "precio":      62000.00,   # ~$15 USD en COP
        "moneda":      "COP",
        "descripcion": "Acceso completo a picks EV+ diarios con análisis Sharp",
        "frecuencia":  1,
        "tipo_freq":   "months",
    }
}


def _mp_headers():
    return {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type":  "application/json",
    }


def _crear_plan_mp(plan_key: str) -> str:
    """Crea o recupera el plan de suscripción en MercadoPago. Devuelve plan_id."""
    plan = PLANES[plan_key]
    payload = {
        "auto_recurring": {
            "frequency":       plan["frecuencia"],
            "frequency_type":  plan["tipo_freq"],
            "transaction_amount": plan["precio"],
            "currency_id":     plan["moneda"],
        },
        "back_url":   "https://sharpiq.co/bienvenido.html",
        "reason":     plan["nombre"],
        "status":     "active",
    }
    r = http.post(f"{MP_BASE}/preapproval_plan", headers=_mp_headers(), json=payload, timeout=15)
    if r.status_code not in (200, 201):
        raise HTTPException(500, f"MercadoPago error al crear plan: {r.text}")
    return r.json()["id"]


@router.get("/planes")
def listar_planes():
    return [{"key": k, **{f: v for f, v in v.items()}} for k, v in PLANES.items()]


@router.post("/suscribir/{plan_key}")
def suscribir(plan_key: str, token=Depends(usuario_activo)):
    if plan_key not in PLANES:
        raise HTTPException(400, "Plan no válido")
    plan = PLANES[plan_key]
    user_id = int(token["sub"])

    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT email, nombre FROM usuarios WHERE id=%s", (user_id,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(404, "Usuario no encontrado")

    # Crear preferencia de pago (checkout)
    payload = {
        "reason":         plan["nombre"],
        "payer_email":    user["email"],
        "auto_recurring": {
            "frequency":          plan["frecuencia"],
            "frequency_type":     plan["tipo_freq"],
            "transaction_amount": plan["precio"],
            "currency_id":        plan["moneda"],
        },
        "back_url":    f"https://sharpiq.co/bienvenido.html?plan={plan_key}&uid={user_id}",
        "status":      "pending",
        "external_reference": str(user_id),
    }
    r = http.post(f"{MP_BASE}/preapproval", headers=_mp_headers(), json=payload, timeout=15)
    if r.status_code not in (200, 201):
        raise HTTPException(500, f"MercadoPago error: {r.text}")

    data = r.json()
    return {
        "ok":           True,
        "checkout_url": data.get("init_point") or data.get("sandbox_init_point"),
        "sub_id":       data.get("id"),
    }


@router.post("/webhook")
async def webhook(request: Request):
    """Recibe notificaciones de pago de MercadoPago."""
    try:
        body = await request.json()
    except Exception:
        return {"ok": False}

    topic = body.get("type") or request.query_params.get("topic", "")
    resource_id = (body.get("data", {}).get("id") or
                   request.query_params.get("id", ""))

    if topic in ("subscription_preapproval", "preapproval") and resource_id:
        r = http.get(f"{MP_BASE}/preapproval/{resource_id}",
                     headers=_mp_headers(), timeout=10)
        if r.status_code == 200:
            sub = r.json()
            estado    = sub.get("status")
            user_ref  = sub.get("external_reference")
            email     = sub.get("payer_email", "")
            sub_id    = sub.get("id")

            if user_ref and estado == "authorized":
                _activar_vip(int(user_ref), sub_id, email)
            elif user_ref and estado in ("cancelled", "paused"):
                _desactivar_vip(int(user_ref))

    elif topic == "payment" and resource_id:
        r = http.get(f"{MP_BASE}/v1/payments/{resource_id}",
                     headers=_mp_headers(), timeout=10)
        if r.status_code == 200:
            pago = r.json()
            if pago.get("status") == "approved":
                user_ref = pago.get("external_reference")
                if user_ref:
                    _registrar_pago(int(user_ref), pago)

    return {"ok": True}


def _activar_vip(user_id: int, sub_id: str, email: str):
    with db() as conn:
        cur = conn.cursor()
        fecha_fin = datetime.utcnow() + timedelta(days=32)
        cur.execute("""
            INSERT INTO suscripciones (usuario_id, plan, precio_usd, fecha_fin,
                                       mp_subscription_id, mp_payer_email, estado)
            VALUES (%s,'vip',62000.00,%s,%s,%s,'active')
            ON CONFLICT (usuario_id, estado) DO UPDATE
            SET fecha_fin=%s, mp_subscription_id=%s, mp_payer_email=%s
        """, (user_id, fecha_fin, sub_id, email, fecha_fin, sub_id, email))
        cur.execute("UPDATE usuarios SET plan='vip' WHERE id=%s", (user_id,))
        # Registrar comisión para quien lo refirió (20%)
        cur.execute("SELECT referidor_id FROM referidos WHERE referido_id=%s", (user_id,))
        ref = cur.fetchone()
        if ref:
            comision = round(15.00 * 0.20, 2)
            cur.execute("""
                UPDATE referidos SET comision_usd=comision_usd+%s
                WHERE referido_id=%s
            """, (comision, user_id))


def _desactivar_vip(user_id: int):
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE suscripciones SET estado='cancelled'
            WHERE usuario_id=%s AND estado='active'
        """, (user_id,))
        cur.execute("UPDATE usuarios SET plan='free' WHERE id=%s", (user_id,))


def _registrar_pago(user_id: int, pago: dict):
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pagos (usuario_id, monto, moneda, mp_payment_id, mp_status, concepto)
            VALUES (%s,%s,%s,%s,%s,'VIP SharpIQ')
            ON CONFLICT DO NOTHING
        """, (user_id, pago.get("transaction_amount", 0),
              pago.get("currency_id", "USD"),
              str(pago.get("id")), pago.get("status")))


@router.get("/mi-suscripcion")
def mi_suscripcion(token=Depends(usuario_activo)):
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT plan, precio_usd, fecha_inicio, fecha_fin, estado, mp_payer_email
            FROM suscripciones WHERE usuario_id=%s AND estado='active'
            ORDER BY fecha_inicio DESC LIMIT 1
        """, (int(token["sub"]),))
        row = cur.fetchone()
        if not row:
            return {"plan": "free", "activo": False}
        return {"plan": row["plan"], "activo": True,
                "fecha_fin": str(row["fecha_fin"]),
                "precio": float(row["precio_usd"] or 0)}
