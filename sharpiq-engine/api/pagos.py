"""
SharpIQ — Pagos MercadoPago
Suscripción VIP: $20 USD/mes (~80.000 COP)
"""
import os, sys, json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, Request, Depends
import requests as http

from .auth import usuario_activo, solo_admin
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
        "precio":      80000,   # COP que cobra MercadoPago (~$20 USD, precio pre-lanzamiento)
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


@router.post("/checkout-publico")
def checkout_publico():
    """Checkout sin autenticación — directo desde landing page."""
    plan = PLANES["vip"]
    payload = {
        "items": [{
            "title":       plan["nombre"],
            "description": plan["descripcion"],
            "quantity":    1,
            "unit_price":  plan["precio"],
            "currency_id": plan["moneda"],
        }],
        "back_urls": {
            "success": "https://sharpiq.co/bienvenido.html?plan=vip",
            "failure": "https://sharpiq.co/cuenta.html?error=pago",
            "pending": "https://sharpiq.co/cuenta.html?pending=1",
        },
        "auto_return":      "approved",
        "notification_url": "https://api.sharpiq.co/pagos/webhook",
    }
    r = http.post(f"{MP_BASE}/checkout/preferences", headers=_mp_headers(), json=payload, timeout=15)
    if r.status_code not in (200, 201):
        raise HTTPException(500, f"MercadoPago error: {r.text}")
    data = r.json()
    return {
        "ok":           True,
        "checkout_url": data.get("init_point") or data.get("sandbox_init_point"),
    }


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

    # Admin bypass: el JWT tiene email pero no hay fila en DB con id=1
    if not user:
        if not token.get("email"):
            raise HTTPException(404, "Usuario no encontrado")
        user = {"email": token["email"], "nombre": token.get("plan", "usuario").title()}

    # Checkout Pro — pago único mensual (evita restricciones de preapproval cross-country)
    payload = {
        "items": [
            {
                "title":       plan["nombre"],
                "description": plan["descripcion"],
                "quantity":    1,
                "unit_price":  plan["precio"],
                "currency_id": plan["moneda"],
            }
        ],
        "payer": {"email": user["email"]},
        "back_urls": {
            "success": f"https://sharpiq.co/bienvenido.html?plan={plan_key}&uid={user_id}",
            "failure": f"https://sharpiq.co/cuenta.html?error=pago",
            "pending": f"https://sharpiq.co/cuenta.html?pending=1",
        },
        "auto_return":        "approved",
        "external_reference": str(user_id),
        "notification_url":   "https://api.sharpiq.co/pagos/webhook",
    }
    r = http.post(f"{MP_BASE}/checkout/preferences", headers=_mp_headers(), json=payload, timeout=15)
    if r.status_code not in (200, 201):
        raise HTTPException(500, f"MercadoPago error: {r.text}")

    data = r.json()
    return {
        "ok":           True,
        "checkout_url": data.get("init_point") or data.get("sandbox_init_point"),
        "sub_id":       data.get("id"),
    }


def _firma_mp_valida(request, data_id):
    """Verifica la firma x-signature de MercadoPago. SEGURO POR DEFECTO:
    - Sin MP_WEBHOOK_SECRET configurado → NO verifica (no bloquea ningún pago).
    - Con secret pero sin MP_WEBHOOK_ENFORCE=1 → solo LOGUEA si no cuadra (no bloquea).
    - Solo bloquea con secret + MP_WEBHOOK_ENFORCE=1.
    Así nunca se tumba un pago real por una verificación mal configurada."""
    import os, hashlib, hmac
    secret = os.environ.get("MP_WEBHOOK_SECRET", "")
    try:
        from config import MP_WEBHOOK_SECRET as _s
        secret = secret or (_s or "")
    except Exception:
        pass
    if not secret:
        return True
    try:
        sig    = request.headers.get("x-signature", "")
        req_id = request.headers.get("x-request-id", "")
        partes = dict(p.strip().split("=", 1) for p in sig.split(",") if "=" in p)
        ts, v1 = partes.get("ts", ""), partes.get("v1", "")
        manifest = f"id:{str(data_id).lower()};request-id:{req_id};ts:{ts};"
        calc = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        ok = bool(ts and v1) and hmac.compare_digest(calc, v1)
    except Exception:
        ok = False
    if not ok:
        print(f"[MP webhook] firma NO valida (data_id={data_id})")
        if os.environ.get("MP_WEBHOOK_ENFORCE") == "1":
            return False
    return True


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

    # Verificación de firma (defensa en profundidad; segura por defecto — ver helper)
    if not _firma_mp_valida(request, resource_id):
        return {"ok": False, "error": "firma_invalida"}

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
        # Base: extiende desde la fecha_fin vigente si aún no vence; si no, desde ahora.
        cur.execute("""SELECT fecha_fin FROM suscripciones
                       WHERE usuario_id=%s AND estado='active'""", (user_id,))
        row  = cur.fetchone()
        base = datetime.utcnow()
        if row and row.get("fecha_fin") and row["fecha_fin"] > base:
            base = row["fecha_fin"]
        fecha_fin = base + timedelta(days=30)  # 1 mes pagado
        cur.execute("""
            INSERT INTO suscripciones (usuario_id, plan, precio_usd, fecha_fin,
                                       mp_subscription_id, mp_payer_email, estado)
            VALUES (%s,'vip',20,%s,%s,%s,'active')
            ON CONFLICT (usuario_id, estado) DO UPDATE
            SET fecha_fin=%s, mp_subscription_id=%s, mp_payer_email=%s
        """, (user_id, fecha_fin, sub_id, email, fecha_fin, sub_id, email))
        cur.execute("UPDATE usuarios SET plan='vip' WHERE id=%s", (user_id,))
        # El premio al referidor ahora es COMISIÓN en efectivo (motor de Partners,
        # ver _devengar_comisiones). El viejo "1 mes gratis" quedó ELIMINADO.


def _desactivar_vip(user_id: int):
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE suscripciones SET estado='cancelled'
            WHERE usuario_id=%s AND estado='active'
        """, (user_id,))
        cur.execute("UPDATE usuarios SET plan='free' WHERE id=%s", (user_id,))


# ── Comisiones del motor de Partners (unilevel legal) ────────────────────────
# % por nivel sobre el precio VIP. Configurable por env. Empezamos con 30 / 7 / 5.
COM_NIVELES = [
    (1, float(os.environ.get("COM_N1", "35"))),
    (2, float(os.environ.get("COM_N2", "10"))),
    (3, float(os.environ.get("COM_N3", "5"))),
]
# INTERRUPTOR LEGAL: por defecto SOLO el nivel 1 (comisión directa = inequívocamente legal).
# Cuando el abogado dé el OK, se pone COM_MULTINIVEL=1 en Railway y se encienden N2 y N3.
COM_MULTINIVEL = os.environ.get("COM_MULTINIVEL", "0") == "1"


def _devengar_comisiones(cliente_id: int, pago_id):
    """Al pagar un cliente, sube su cadena de referidos y crea una comisión para cada
    referidor que sea PARTNER activo. Nivel 1 SIEMPRE; niveles 2-3 solo si COM_MULTINIVEL
    (tras visto bueno legal). Base = precio VIP en USD (igual pague en COP o cripto).
    Idempotente por UNIQUE(pago_id, partner_id). Nunca rompe el pago (try/except)."""
    if not pago_id:
        return
    base    = PRECIO_VIP_USD
    periodo = datetime.utcnow().strftime("%Y-%m")
    niveles = COM_NIVELES if COM_MULTINIVEL else COM_NIVELES[:1]
    try:
        with db() as conn:
            cur = conn.cursor()
            actual = cliente_id
            for nivel, pct in niveles:
                cur.execute("SELECT referido_por FROM usuarios WHERE id=%s", (actual,))
                row = cur.fetchone()
                ref_id = row.get("referido_por") if row else None
                if not ref_id:
                    break                      # se acabó la cadena de referidos
                cur.execute("""SELECT id FROM partners
                               WHERE usuario_id=%s AND es_partner=TRUE AND activo=TRUE""",
                            (ref_id,))
                prow = cur.fetchone()
                if prow:
                    monto = round(base * pct / 100.0, 2)
                    cur.execute("""
                        INSERT INTO comisiones (partner_id, cliente_id, pago_id, nivel, pct,
                                                periodo, monto_usd, estado)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,'pendiente')
                        ON CONFLICT (pago_id, partner_id) DO NOTHING
                    """, (prow["id"], cliente_id, pago_id, nivel, pct, periodo, monto))
                actual = ref_id                # sube un nivel en el árbol
    except Exception as e:
        print("[comisiones] error devengando:", e)


def _registrar_pago(user_id: int, pago: dict):
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pagos (usuario_id, monto, moneda, mp_payment_id, mp_status, concepto)
            VALUES (%s,%s,%s,%s,%s,'VIP SharpIQ')
            ON CONFLICT (mp_payment_id) DO NOTHING
            RETURNING id
        """, (user_id, pago.get("transaction_amount", 0),
              pago.get("currency_id", "COP"),
              str(pago.get("id")), pago.get("status")))
        r = cur.fetchone()
        pago_id = r["id"] if r else None

    # ── Flujo REAL (Checkout Pro, pago único): activar VIP + recompensa referido +
    #    DEVENGAR comisiones de Partners. Solo si el pago es NUEVO (pago_id) → idempotente.
    if pago_id and pago.get("status") == "approved":
        email = (pago.get("payer") or {}).get("email", "")
        _activar_vip(user_id, str(pago.get("id")), email)
        _devengar_comisiones(user_id, pago_id)


# ══════════════════════════════════════════════════════════════════════════
#  PAGOS CRIPTO (NOWPayments) — EN PARALELO a MercadoPago, SIN tocarlo.
#  El cliente paga en la cripto/red que quiera (auto-conversión a tu wallet).
#  El pago finalizado engancha en el MISMO _activar_vip() (no duplica lógica).
#  Idempotencia: reusa mp_payment_id con prefijo 'nowp_' (índice UNIQUE ya existe).
# ══════════════════════════════════════════════════════════════════════════
try:
    from config import NOWPAYMENTS_API_KEY, NOWPAYMENTS_IPN_SECRET
except ImportError:
    NOWPAYMENTS_API_KEY    = os.environ.get("NOWPAYMENTS_API_KEY", "")
    NOWPAYMENTS_IPN_SECRET = os.environ.get("NOWPAYMENTS_IPN_SECRET", "")
# Login de la cuenta NOWPayments: necesario SOLO para LISTAR pagos (ese endpoint exige un
# JWT de POST /v1/auth; la API key sola no basta). Con esto reconciliamos sin webhook.
NOWPAYMENTS_EMAIL    = os.environ.get("NOWPAYMENTS_EMAIL", "")
NOWPAYMENTS_PASSWORD = os.environ.get("NOWPAYMENTS_PASSWORD", "")

NP_BASE = "https://api.nowpayments.io/v1"
_NP_JWT = {"token": "", "exp": 0.0}
PRECIO_VIP_USD = float(os.environ.get("PRECIO_VIP_USD", "20"))  # $20 pre-lanzamiento; ajustable en Railway


@router.post("/cripto/checkout")
def cripto_checkout(token=Depends(usuario_activo)):
    """Crea un cobro cripto (invoice NOWPayments) para el VIP y devuelve la URL de pago.
    order_id = user_id -> amarra el pago al usuario, igual que external_reference en MP."""
    if not NOWPAYMENTS_API_KEY:
        raise HTTPException(503, "Pagos cripto no configurados todavía")
    user_id = int(token["sub"])
    payload = {
        "price_amount":     PRECIO_VIP_USD,
        "price_currency":   "usd",
        "order_id":         str(user_id),
        "order_description": "SharpIQ VIP — 1 mes",
        "ipn_callback_url": "https://api.sharpiq.co/pagos/cripto/webhook",
        "success_url":      "https://sharpiq.co/bienvenido.html?plan=vip",
        "cancel_url":       "https://sharpiq.co/cuenta.html?error=pago",
    }
    r = http.post(f"{NP_BASE}/invoice", json=payload, timeout=20,
                  headers={"x-api-key": NOWPAYMENTS_API_KEY, "Content-Type": "application/json"})
    if r.status_code not in (200, 201):
        raise HTTPException(502, f"NOWPayments error: {r.text[:200]}")
    return {"url": r.json().get("invoice_url")}


def _verificar_ipn(raw_body: bytes, firma: str) -> bool:
    """Verifica la firma HMAC-SHA512 del IPN (recipe NOWPayments: JSON con claves
    ordenadas y sin espacios). Endpoint de dinero: firma OBLIGATORIA."""
    if not NOWPAYMENTS_IPN_SECRET or not firma:
        return False
    import hmac, hashlib
    try:
        datos    = json.loads(raw_body)
        ordenado = json.dumps(datos, sort_keys=True, separators=(",", ":"))
        digest   = hmac.new(NOWPAYMENTS_IPN_SECRET.encode(), ordenado.encode(),
                            hashlib.sha512).hexdigest()
        return hmac.compare_digest(digest, firma)
    except Exception:
        return False


def _np_confirmar_pago(payment_id: str) -> dict:
    """Doble chequeo: re-consulta el estado real del pago en NOWPayments (no confiar
    solo en el body reenviado)."""
    try:
        r = http.get(f"{NP_BASE}/payment/{payment_id}", timeout=15,
                     headers={"x-api-key": NOWPAYMENTS_API_KEY})
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def _registrar_pago_cripto(user_id: int, np: dict):
    """Registra/actualiza el pago cripto y activa el VIP la PRIMERA vez que queda 'finished'.
    Robusto ante VARIOS IPN del mismo pago: NOWPayments manda un aviso por cada cambio de
    estado (waiting -> confirming -> finished). Antes, si llegaba primero un aviso no-finished
    se creaba la fila y el aviso 'finished' posterior caía en ON CONFLICT -> NUNCA activaba.
    Ahora activamos exactamente UNA vez, al llegar a 'finished', aunque la fila ya existiera."""
    pay_id = "nowp_" + str(np.get("payment_id") or np.get("id") or "")
    estado = str(np.get("payment_status") or "")
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, mp_status FROM pagos WHERE mp_payment_id=%s", (pay_id,))
        prev = cur.fetchone()
        ya_finished = bool(prev and str(prev.get("mp_status")) == "finished")
        if prev is None:
            cur.execute("""
                INSERT INTO pagos (usuario_id, monto, moneda, mp_payment_id, mp_status, concepto)
                VALUES (%s,%s,%s,%s,%s,'VIP SharpIQ (cripto)')
                ON CONFLICT (mp_payment_id) DO NOTHING
            """, (user_id, np.get("price_amount") or PRECIO_VIP_USD,
                  (np.get("price_currency") or "usd").upper(), pay_id, estado))
            cur.execute("SELECT id FROM pagos WHERE mp_payment_id=%s", (pay_id,))
            prev = cur.fetchone()
        else:
            cur.execute("UPDATE pagos SET mp_status=%s WHERE mp_payment_id=%s", (estado, pay_id))
        pago_id = prev["id"] if prev else None
    # Activa el VIP + devenga comisiones al llegar a 'finished'. ya_finished evita el
    # doble-activado si NOWPayments reenvía el aviso de 'finished'.
    if estado == "finished" and not ya_finished:
        _activar_vip(user_id, pay_id, "")
        _devengar_comisiones(user_id, pago_id)


@router.post("/cripto/webhook")
async def cripto_webhook(request: Request):
    """IPN de NOWPayments: verifica firma -> re-confirma estado -> activa VIP.
    Paralelo total al webhook de MercadoPago; no comparte tabla ni idempotencia."""
    raw   = await request.body()
    firma = request.headers.get("x-nowpayments-sig", "")
    if not _verificar_ipn(raw, firma):
        raise HTTPException(401, "Firma IPN inválida")
    try:
        data = json.loads(raw)
    except Exception:
        raise HTTPException(400, "Body inválido")
    user_ref   = data.get("order_id")
    payment_id = data.get("payment_id") or data.get("id")
    if not user_ref or not payment_id:
        return {"ok": True}
    real = _np_confirmar_pago(str(payment_id)) or {}
    _registrar_pago_cripto(int(user_ref), {**data, **real})
    return {"ok": True}


def _np_token():
    """JWT de NOWPayments (POST /v1/auth con email+password). Cacheado ~4 min.
    El endpoint de LISTAR pagos lo exige (la API key sola da 401)."""
    import time
    now = time.time()
    if _NP_JWT["token"] and _NP_JWT["exp"] > now:
        return _NP_JWT["token"]
    if not (NOWPAYMENTS_EMAIL and NOWPAYMENTS_PASSWORD):
        return ""
    try:
        r = http.post(f"{NP_BASE}/auth", timeout=15,
                      json={"email": NOWPAYMENTS_EMAIL, "password": NOWPAYMENTS_PASSWORD})
        if r.status_code == 200:
            tk = (r.json() or {}).get("token", "")
            _NP_JWT["token"] = tk
            _NP_JWT["exp"]   = now + 240
            return tk
    except Exception:
        pass
    return ""


def _np_listar_pagos(limit=500):
    """Lista los pagos recientes de la cuenta NOWPayments (JWT + API key) para RECONCILIAR
    por order_id sin depender del webhook. Devuelve lista (posiblemente vacía)."""
    tk = _np_token()
    if not tk:
        return []
    try:
        r = http.get(f"{NP_BASE}/payment/?limit={limit}&page=0&sortBy=created_at&orderBy=desc",
                     headers={"Authorization": f"Bearer {tk}", "x-api-key": NOWPAYMENTS_API_KEY},
                     timeout=25)
        if r.status_code == 200:
            d = r.json()
            return (d.get("data") if isinstance(d, dict) else d) or []
    except Exception:
        pass
    return []


def _reconciliar_cripto(user_id: int) -> bool:
    """Le pregunta a NOWPayments por los pagos de este usuario (order_id = user_id) y activa
    el VIP por cada uno 'finished' (idempotente). Devuelve True si encontró alguno finished."""
    encontro = False
    for p in _np_listar_pagos():
        if str(p.get("order_id")) == str(user_id) and str(p.get("payment_status")) == "finished":
            _registrar_pago_cripto(user_id, p)
            encontro = True
    return encontro


def _plan_actual(user_id: int) -> str:
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT plan FROM usuarios WHERE id=%s", (user_id,))
        row = cur.fetchone() or {}
    return (row.get("plan") or "free")


@router.post("/cripto/verificar")
def cripto_verificar(token=Depends(usuario_activo)):
    """Reconciliación SIN webhook: le PREGUNTA a NOWPayments por los pagos de este usuario
    y, si alguno está 'finished', activa el VIP (idempotente). Lo llama el frontend al volver
    del pago y el botón 'Ya pagué'. A prueba de webhooks perdidos: solo usa la API key."""
    if not NOWPAYMENTS_API_KEY:
        raise HTTPException(503, "Pagos cripto no configurados")
    user_id = int(token["sub"])
    activado = _reconciliar_cripto(user_id)
    return {"ok": True, "activado": activado, "plan": _plan_actual(user_id)}


@router.post("/admin/reconciliar-cripto")
def admin_reconciliar_cripto(body: dict, token=Depends(solo_admin)):
    """El admin reconcilia el pago cripto de un cliente por email (herramienta de soporte).
    Busca los pagos 'finished' del cliente en NOWPayments y activa su VIP."""
    if not NOWPAYMENTS_API_KEY:
        raise HTTPException(503, "Pagos cripto no configurados")
    email = (body.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(400, "Falta el email del cliente")
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "No hay cuenta con ese email")
    activado = _reconciliar_cripto(row["id"])
    return {"ok": True, "email": email, "user_id": row["id"],
            "encontro_pago": activado, "plan": _plan_actual(row["id"])}


@router.post("/admin/activar-vip")
def activar_vip_manual(body: dict, token=Depends(solo_admin)):
    """Activa el VIP manualmente por email — para pagos por Nequi/transferencia
    o pagos web que quedaron sin amarrar. El cliente debe tener cuenta creada
    en sharpiq.co. Idempotente (extiende la fecha si ya tenía VIP)."""
    email = (body.get("email") or "").lower().strip()
    meses = max(1, int(body.get("meses") or 1))
    if not email:
        raise HTTPException(400, "Falta el email del cliente")
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, plan FROM usuarios WHERE email=%s", (email,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "No hay cuenta con ese email. Pídele al cliente "
                                 "que cree su cuenta gratis en sharpiq.co primero.")
    for _ in range(meses):
        _activar_vip(row["id"], f"manual-{email}", email)
    return {"ok": True, "email": email, "nombre": row["nombre"],
            "user_id": row["id"], "plan": "vip", "meses": meses}


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
