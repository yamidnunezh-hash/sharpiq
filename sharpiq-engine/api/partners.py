"""
SharpIQ — Motor de Partners (afiliados / unilevel legal, estilo bróker)
Zona del socio: inscribirse, ver comisiones, referidos, árbol genealógico, wallet y payouts.
El DEVENGO de comisiones (crear la comisión al pagar un cliente) vive en pagos.py.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime

from .auth import usuario_activo, solo_admin
from .db import db

router = APIRouter()

# % por nivel — SOLO para mostrar en el dashboard (el cálculo real está en pagos.COM_NIVELES).
NIVELES_PCT = {1: 35, 2: 10, 3: 5}

# Rangos por # de clientes VIP directos activos (gamificación, sin implicación de pago).
RANGOS = [
    (0,   "Bronce",    "🥉", "Bienvenido — empieza a construir tu red"),
    (5,   "Plata",     "🥈", "Bono de reconocimiento por tu crecimiento"),
    (10,  "Oro",       "🥇", "Prioridad en soporte y material de venta"),
    (25,  "Zafiro",    "💠", "Acceso a concursos y bonos de liderazgo"),
    (50,  "Esmeralda", "💚", "Bono estratégico del equipo"),
    (100, "Diamante",  "💎", "Élite SharpIQ — beneficios máximos"),
]


def _rango(activos):
    idx = 0
    for i, (minv, *_ ) in enumerate(RANGOS):
        if activos >= minv:
            idx = i
    minv, nombre, emoji, beneficio = RANGOS[idx]
    if idx + 1 < len(RANGOS):
        nextmin, nextname, _, _ = RANGOS[idx + 1]
        span = nextmin - minv
        progreso = int(min(100, (activos - minv) * 100 / span)) if span else 100
        return {"nombre": nombre, "emoji": emoji, "beneficio": beneficio, "activos": activos,
                "siguiente": nextname, "faltan": max(0, nextmin - activos), "progreso": progreso}
    return {"nombre": nombre, "emoji": emoji, "beneficio": beneficio, "activos": activos,
            "siguiente": None, "faltan": 0, "progreso": 100}


def _partner_row(cur, user_id):
    cur.execute("""SELECT id, es_partner, pct_comision, crypto_red, crypto_address,
                          min_payout_usd, activo, fecha_alta
                   FROM partners WHERE usuario_id=%s""", (user_id,))
    return cur.fetchone()


def _enlace(codigo):
    return f"https://sharpiq.co/registro.html?ref={codigo or ''}"


@router.get("/estado")
def estado(token=Depends(usuario_activo)):
    """¿El usuario es Partner? Devuelve su ficha (o es_partner:false) + su código/enlace."""
    uid = int(token["sub"])
    with db() as conn:
        cur = conn.cursor()
        p = _partner_row(cur, uid)
        cur.execute("SELECT codigo_ref FROM usuarios WHERE id=%s", (uid,))
        codigo = (cur.fetchone() or {}).get("codigo_ref") or ""
    if not p:
        return {"es_partner": False, "codigo_ref": codigo, "enlace": _enlace(codigo)}
    return {"es_partner": bool(p.get("es_partner")) and bool(p.get("activo")),
            "codigo_ref": codigo, "enlace": _enlace(codigo),
            "wallet": {"red": p.get("crypto_red"), "address": p.get("crypto_address")},
            "min_payout_usd": float(p.get("min_payout_usd") or 20)}


@router.post("/inscribir")
def inscribir(token=Depends(usuario_activo)):
    """Auto-inscripción como Partner: GRATIS, cualquiera que quiera. Idempotente."""
    uid = int(token["sub"])
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""INSERT INTO partners (usuario_id, es_partner, activo)
                       VALUES (%s, TRUE, TRUE)
                       ON CONFLICT (usuario_id) DO UPDATE SET es_partner=TRUE, activo=TRUE""",
                    (uid,))
        cur.execute("SELECT codigo_ref FROM usuarios WHERE id=%s", (uid,))
        codigo = (cur.fetchone() or {}).get("codigo_ref") or ""
    return {"ok": True, "es_partner": True, "codigo_ref": codigo, "enlace": _enlace(codigo)}


@router.get("/dashboard")
def dashboard(token=Depends(usuario_activo)):
    """Resumen del Partner: KPIs, referidos directos y comisiones recientes."""
    uid = int(token["sub"])
    periodo = datetime.utcnow().strftime("%Y-%m")
    with db() as conn:
        cur = conn.cursor()
        p = _partner_row(cur, uid)
        if not p:
            raise HTTPException(404, "Aún no eres Partner")
        pid = p["id"]
        cur.execute("""SELECT
                COALESCE(SUM(monto_usd),0)                                      AS total,
                COALESCE(SUM(monto_usd) FILTER (WHERE periodo=%s),0)            AS mes,
                COALESCE(SUM(monto_usd) FILTER (WHERE estado='pendiente'),0)    AS pendiente
            FROM comisiones WHERE partner_id=%s""", (periodo, pid))
        k = cur.fetchone() or {}
        cur.execute("SELECT COUNT(*) AS n FROM usuarios WHERE referido_por=%s AND plan='vip'", (uid,))
        activos = int((cur.fetchone() or {}).get("n") or 0)
        # Directos con lo que CADA UNO le ha generado en comisión al partner.
        cur.execute("""
            SELECT u.id, u.nombre, u.email, u.plan, u.fecha_registro,
                   COALESCE((SELECT SUM(monto_usd) FROM comisiones
                             WHERE partner_id=%s AND cliente_id=u.id),0) AS generado
            FROM usuarios u WHERE u.referido_por=%s
            ORDER BY (u.plan='vip') DESC, u.fecha_registro DESC LIMIT 100""", (pid, uid))
        refs = cur.fetchall()
        # Serie mensual de comisiones (para el gráfico) — últimos 6 periodos.
        cur.execute("""SELECT periodo, COALESCE(SUM(monto_usd),0) AS monto
                       FROM comisiones WHERE partner_id=%s
                       GROUP BY periodo ORDER BY periodo DESC LIMIT 6""", (pid,))
        mensual = list(reversed(cur.fetchall()))
        cur.execute("""SELECT nivel, pct, monto_usd, periodo, estado, fecha
                       FROM comisiones WHERE partner_id=%s ORDER BY id DESC LIMIT 60""", (pid,))
        coms = cur.fetchall()
        cur.execute("SELECT codigo_ref FROM usuarios WHERE id=%s", (uid,))
        codigo = (cur.fetchone() or {}).get("codigo_ref") or ""
    return {
        "kpis": {
            "clientes_activos": activos,
            "comision_mes":     float(k.get("mes") or 0),
            "total_ganado":     float(k.get("total") or 0),
            "por_cobrar":       float(k.get("pendiente") or 0),
        },
        "rango": _rango(activos),
        "mensual": [{"periodo": m["periodo"] or "", "monto": float(m["monto"] or 0)} for m in mensual],
        "codigo_ref": codigo, "enlace": _enlace(codigo),
        "wallet": {"red": p.get("crypto_red"), "address": p.get("crypto_address")},
        "min_payout_usd": float(p.get("min_payout_usd") or 20),
        "referidos": [{"nombre": r["nombre"], "email": r["email"], "plan": r["plan"],
                       "fecha": str(r["fecha_registro"])[:10],
                       "activo": r["plan"] == "vip", "generado": float(r["generado"] or 0)} for r in refs],
        "comisiones": [{"nivel": c["nivel"], "pct": float(c["pct"] or 0),
                        "monto": float(c["monto_usd"] or 0), "periodo": c["periodo"],
                        "estado": c["estado"], "fecha": str(c["fecha"])[:10]} for c in coms],
    }


@router.get("/arbol")
def arbol(token=Depends(usuario_activo)):
    """Árbol genealógico (3 niveles) para la visualización D3. Una sola consulta recursiva."""
    uid = int(token["sub"])
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT nombre FROM usuarios WHERE id=%s", (uid,))
        yo = (cur.fetchone() or {}).get("nombre") or "Tú"
        cur.execute("""
            WITH RECURSIVE arbol AS (
                SELECT id, nombre, plan, referido_por, 1 AS nivel
                FROM usuarios WHERE referido_por=%s
                UNION ALL
                SELECT u.id, u.nombre, u.plan, u.referido_por, a.nivel+1
                FROM usuarios u JOIN arbol a ON u.referido_por = a.id
                WHERE a.nivel < 3
            )
            SELECT id, nombre, plan, referido_por, nivel FROM arbol
        """, (uid,))
        filas = cur.fetchall()
    nodos = {uid: {"id": uid, "nombre": yo, "plan": "-", "nivel": 0, "hijos": []}}
    for f in filas:
        nodos[f["id"]] = {"id": f["id"], "nombre": f["nombre"], "plan": f["plan"],
                          "nivel": f["nivel"], "hijos": []}
    for f in filas:
        padre = nodos.get(f["referido_por"])
        if padre:
            padre["hijos"].append(nodos[f["id"]])
    return nodos[uid]


@router.post("/wallet")
def wallet(body: dict, token=Depends(usuario_activo)):
    """Guarda/actualiza la wallet cripto de cobro del Partner."""
    uid = int(token["sub"])
    red  = (body.get("red") or "").strip().upper()
    addr = (body.get("address") or "").strip()
    if not red or not addr:
        raise HTTPException(400, "Falta la red o la dirección de la wallet")
    with db() as conn:
        cur = conn.cursor()
        p = _partner_row(cur, uid)
        if not p:
            raise HTTPException(404, "Aún no eres Partner")
        cur.execute("UPDATE partners SET crypto_red=%s, crypto_address=%s WHERE usuario_id=%s",
                    (red, addr, uid))
    return {"ok": True, "red": red, "address": addr}


@router.post("/solicitar-payout")
def solicitar_payout(token=Depends(usuario_activo)):
    """El Partner solicita el pago de sus comisiones PENDIENTES. Si supera el mínimo, crea
    el lote del periodo (estado 'pendiente'); el admin lo aprueba y paga en cripto (Fase 4)."""
    uid = int(token["sub"])
    periodo = datetime.utcnow().strftime("%Y-%m")
    with db() as conn:
        cur = conn.cursor()
        p = _partner_row(cur, uid)
        if not p:
            raise HTTPException(404, "Aún no eres Partner")
        if not p.get("crypto_address"):
            raise HTTPException(400, "Primero configura tu wallet de cobro")
        pid    = p["id"]
        minimo = float(p.get("min_payout_usd") or 20)
        cur.execute("""SELECT COALESCE(SUM(monto_usd),0) AS pend FROM comisiones
                       WHERE partner_id=%s AND estado='pendiente'""", (pid,))
        pend = float((cur.fetchone() or {}).get("pend") or 0)
        if pend < minimo:
            return {"ok": False, "monto": pend, "minimo": minimo,
                    "motivo": f"Necesitas al menos ${minimo:.0f} para retirar. Llevas ${pend:.2f}."}
        cur.execute("""INSERT INTO payouts (partner_id, periodo, monto_total_usd, crypto_red,
                                            crypto_address, estado)
                       VALUES (%s,%s,%s,%s,%s,'pendiente')
                       ON CONFLICT (partner_id, periodo) DO UPDATE
                       SET monto_total_usd=EXCLUDED.monto_total_usd""",
                    (pid, periodo, pend, p.get("crypto_red"), p.get("crypto_address")))
    return {"ok": True, "monto": pend, "estado": "solicitado",
            "mensaje": "Solicitud enviada. Se paga tras la aprobación del equipo."}


# ── ADMIN: pagar comisiones a los Partners ───────────────────────────────────

@router.get("/admin/payouts")
def admin_payouts(token=Depends(solo_admin)):
    """Lista los payouts SOLICITADOS (pendientes) para que el admin los pague."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT po.id, po.periodo, po.monto_total_usd, po.crypto_red, po.crypto_address,
                   po.creado, u.nombre, u.email
            FROM payouts po
            JOIN partners pa ON pa.id = po.partner_id
            JOIN usuarios  u ON u.id  = pa.usuario_id
            WHERE po.estado='pendiente'
            ORDER BY po.creado ASC""")
        rows = cur.fetchall()
    return {"payouts": [{"id": r["id"], "nombre": r["nombre"], "email": r["email"],
                         "monto": float(r["monto_total_usd"] or 0), "periodo": r["periodo"],
                         "red": r["crypto_red"], "address": r["crypto_address"],
                         "creado": str(r["creado"])[:16]} for r in rows]}


@router.post("/admin/payout/pagar")
def admin_payout_pagar(body: dict, token=Depends(solo_admin)):
    """Marca un payout como PAGADO (con el txid on-chain) y pasa a 'pagada' las comisiones
    pendientes de ese partner. El envío de la cripto lo hace el admin por fuera (NOWPayments
    Mass Payouts o su wallet) y aquí solo registra el resultado."""
    pid  = body.get("payout_id")
    txid = (body.get("txid") or "").strip()
    if not pid:
        raise HTTPException(400, "Falta payout_id")
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT partner_id, estado FROM payouts WHERE id=%s", (pid,))
        po = cur.fetchone()
        if not po:
            raise HTTPException(404, "Ese payout no existe")
        if po["estado"] == "completado":
            return {"ok": True, "ya_pagado": True}
        cur.execute("UPDATE payouts SET estado='completado', txid=%s WHERE id=%s", (txid, pid))
        cur.execute("""UPDATE comisiones SET estado='pagada'
                       WHERE partner_id=%s AND estado='pendiente'""", (po["partner_id"],))
    return {"ok": True}


@router.post("/admin/anclar")
def admin_anclar(body: dict, token=Depends(solo_admin)):
    """Ancla un usuario EXISTENTE bajo un sponsor en el árbol (setea referido_por). Sirve para
    meter en la red a gente que ya se había registrado sin enlace. Evita ciclos."""
    email  = (body.get("email") or "").lower().strip()
    codigo = (body.get("sponsor_codigo") or "").upper().strip()
    if not email or not codigo:
        raise HTTPException(400, "Falta el email o el código del sponsor")
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
        u = cur.fetchone()
        if not u:
            raise HTTPException(404, "No hay cuenta con ese email")
        cur.execute("SELECT id, nombre FROM usuarios WHERE codigo_ref=%s", (codigo,))
        s = cur.fetchone()
        if not s:
            raise HTTPException(404, "No existe un usuario con ese código de sponsor")
        uid, sid = u["id"], s["id"]
        if uid == sid:
            raise HTTPException(400, "Un usuario no puede ser su propio sponsor")
        # Anti-ciclo: subiendo desde el sponsor no debemos toparnos con el usuario.
        actual, hops = sid, 0
        while actual and hops < 30:
            cur.execute("SELECT referido_por FROM usuarios WHERE id=%s", (actual,))
            r = cur.fetchone()
            actual = r.get("referido_por") if r else None
            if actual == uid:
                raise HTTPException(400, "No se puede: crearía un ciclo en el árbol")
            hops += 1
        cur.execute("UPDATE usuarios SET referido_por=%s WHERE id=%s", (sid, uid))
    return {"ok": True, "email": email, "sponsor": s["nombre"], "sponsor_codigo": codigo}
