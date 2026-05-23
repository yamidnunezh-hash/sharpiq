"""
SharpIQ — Panel de membresía del usuario
"""
from fastapi import APIRouter, Depends
from .auth import usuario_activo
from .db   import db

router = APIRouter()


@router.get("/dashboard")
def dashboard(token=Depends(usuario_activo)):
    user_id = int(token["sub"])
    with db() as conn:
        cur = conn.cursor()

        # Perfil
        cur.execute("""
            SELECT u.id, u.email, u.nombre, u.plan, u.codigo_ref, u.fecha_registro,
                   s.fecha_fin, s.precio_usd
            FROM usuarios u
            LEFT JOIN suscripciones s ON s.usuario_id=u.id AND s.estado='active'
            WHERE u.id=%s
        """, (user_id,))
        perfil = dict(cur.fetchone() or {})
        # El plan del JWT siempre tiene prioridad (admin bypass)
        if token.get("plan") in ("admin", "vip"):
            perfil["plan"] = token["plan"]

        # Pagos
        cur.execute("""
            SELECT monto, moneda, mp_status, concepto, fecha
            FROM pagos WHERE usuario_id=%s ORDER BY fecha DESC LIMIT 10
        """, (user_id,))
        pagos = [dict(r) for r in cur.fetchall()]

        # Referidos resumen
        cur.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN u2.plan='vip' THEN 1 ELSE 0 END) as activos,
                   SUM(r.comision_usd) as comision
            FROM referidos r
            JOIN usuarios u2 ON u2.id=r.referido_id
            WHERE r.referidor_id=%s
        """, (user_id,))
        ref_stats = dict(cur.fetchone() or {})

    return {
        "perfil":    perfil,
        "pagos":     pagos,
        "referidos": {
            "total":   int(ref_stats.get("total") or 0),
            "activos": int(ref_stats.get("activos") or 0),
            "comision":float(ref_stats.get("comision") or 0),
        },
        "link_ref": f"https://sharpiq.co/registro.html?ref={perfil.get('codigo_ref','')}",
    }
