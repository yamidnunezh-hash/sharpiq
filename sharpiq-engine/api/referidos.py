"""
SharpIQ — Sistema de Referidos
Recompensa: 1 mes gratis de VIP por cada referido que active VIP.
Se aplica extendiendo fecha_fin del referidor (+30d). Si no tiene VIP activo,
queda pendiente y se aplica en su próxima activación.
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

        # Referidos totales — recompensa en MESES GRATIS (antes: $ comisión)
        cur.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN u.plan='vip' THEN 1 ELSE 0 END) as activos,
                   COALESCE(SUM(r.meses_gratis_ganados),0)   as meses_ganados,
                   COALESCE(SUM(r.meses_gratis_aplicados),0) as meses_aplicados
            FROM referidos r
            JOIN usuarios u ON u.id = r.referido_id
            WHERE r.referidor_id = %s
        """, (user_id,))
        stats = cur.fetchone()
        ganados   = int(stats["meses_ganados"] or 0)
        aplicados = int(stats["meses_aplicados"] or 0)

        # Lista últimos 20
        cur.execute("""
            SELECT u.nombre, u.email, u.plan,
                   r.meses_gratis_ganados, r.meses_gratis_aplicados, r.fecha
            FROM referidos r
            JOIN usuarios u ON u.id = r.referido_id
            WHERE r.referidor_id = %s
            ORDER BY r.fecha DESC LIMIT 20
        """, (user_id,))
        lista = cur.fetchall()

        return {
            "codigo_ref":       codigo,
            "link_referido":    f"https://sharpiq.co/registro.html?ref={codigo}",
            "total_referidos":  int(stats["total"] or 0),
            "referidos_vip":    int(stats["activos"] or 0),
            "meses_ganados":    ganados,
            "meses_aplicados":  aplicados,
            "meses_pendientes": ganados - aplicados,
            "recompensa":       "1 mes gratis por cada referido VIP",
            "lista":            [dict(r) for r in lista],
        }


@router.get("/ranking")
def ranking_referidos(token=Depends(usuario_activo)):
    """Top 10 referidores del mes."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.nombre, COUNT(r.id) as referidos,
                   COALESCE(SUM(r.meses_gratis_ganados),0) as meses_gratis
            FROM referidos r
            JOIN usuarios u ON u.id = r.referidor_id
            WHERE r.fecha >= NOW() - INTERVAL '30 days'
            GROUP BY u.nombre
            ORDER BY referidos DESC LIMIT 10
        """)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
