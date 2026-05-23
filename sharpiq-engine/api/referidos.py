"""
SharpIQ — Sistema de Referidos
Comisión: 20% del primer mes de cada referido que pague VIP
"""
from fastapi import APIRouter, Depends, HTTPException
from .auth import usuario_activo
from .db   import db

router = APIRouter()


@router.get("/mis-referidos")
def mis_referidos(token=Depends(usuario_activo)):
    user_id = int(token["sub"])
    with db() as conn:
        cur = conn.cursor()
        # Código propio
        cur.execute("SELECT codigo_ref FROM usuarios WHERE id=%s", (user_id,))
        row = cur.fetchone()
        codigo = row["codigo_ref"] if row else ""

        # Referidos totales
        cur.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN u.plan='vip' THEN 1 ELSE 0 END) as activos,
                   SUM(r.comision_usd) as comision_total,
                   SUM(CASE WHEN r.pagado THEN r.comision_usd ELSE 0 END) as cobrado
            FROM referidos r
            JOIN usuarios u ON u.id = r.referido_id
            WHERE r.referidor_id = %s
        """, (user_id,))
        stats = cur.fetchone()

        # Lista últimos 20
        cur.execute("""
            SELECT u.nombre, u.email, u.plan, r.comision_usd, r.pagado, r.fecha
            FROM referidos r
            JOIN usuarios u ON u.id = r.referido_id
            WHERE r.referidor_id = %s
            ORDER BY r.fecha DESC LIMIT 20
        """, (user_id,))
        lista = cur.fetchall()

        return {
            "codigo_ref":      codigo,
            "link_referido":   f"https://sharpiq.co/registro.html?ref={codigo}",
            "total_referidos": int(stats["total"] or 0),
            "referidos_vip":   int(stats["activos"] or 0),
            "comision_total":  float(stats["comision_total"] or 0),
            "comision_cobrada":float(stats["cobrado"] or 0),
            "comision_pendiente": float((stats["comision_total"] or 0) - (stats["cobrado"] or 0)),
            "porcentaje":      20,
            "lista":           [dict(r) for r in lista],
        }


@router.get("/ranking")
def ranking_referidos(token=Depends(usuario_activo)):
    """Top 10 referidores del mes."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.nombre, COUNT(r.id) as referidos, SUM(r.comision_usd) as comision
            FROM referidos r
            JOIN usuarios u ON u.id = r.referidor_id
            WHERE r.fecha >= NOW() - INTERVAL '30 days'
            GROUP BY u.nombre
            ORDER BY referidos DESC LIMIT 10
        """)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
