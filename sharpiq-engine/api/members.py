"""
SharpIQ — Panel de membresía del usuario
"""
from fastapi import APIRouter, Depends
from .auth import usuario_activo, solo_admin
from .db   import db

router = APIRouter()


@router.get("/admin/clientes")
def listar_clientes(token=Depends(solo_admin)):
    """Lista de TODOS los usuarios registrados con su plan — solo admin."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.email, u.nombre, u.plan, u.fecha_registro, s.fecha_fin
            FROM usuarios u
            LEFT JOIN suscripciones s ON s.usuario_id=u.id AND s.estado='active'
            ORDER BY u.fecha_registro DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
    clientes = [{
        "email":          r["email"],
        "nombre":         r["nombre"],
        "plan":           r.get("plan") or "free",
        "fecha_registro": str(r.get("fecha_registro") or "")[:10],
        "vence":          str(r.get("fecha_fin") or "")[:10],
    } for r in rows]
    return {
        "total": len(clientes),
        "vip":   sum(1 for c in clientes if c["plan"] == "vip"),
        "free":  sum(1 for c in clientes if c["plan"] == "free"),
        "clientes": clientes,
    }


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
                   COALESCE(SUM(r.meses_gratis_ganados),0) as meses_gratis
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
            "meses_gratis":int(ref_stats.get("meses_gratis") or 0),
        },
        "link_ref": f"https://sharpiq.co/registro.html?ref={perfil.get('codigo_ref','')}",
    }
