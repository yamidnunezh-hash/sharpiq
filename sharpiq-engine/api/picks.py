"""
SharpIQ — Endpoint de Picks
Free: 2 picks gratis por día (sin EV, solo vista previa)
VIP:  todos los picks con EV+ en tiempo real desde predicciones.json
"""
import os, sys, json
from datetime import date
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from .auth import usuario_activo, solo_vip
from .db   import db

router = APIRouter()

# Ruta al JSON generado por el motor
_BASE  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JSON  = os.path.join(_BASE, "..", "predicciones.json")


def _cargar_predicciones():
    try:
        with open(_JSON, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"predicciones": [], "fecha": str(date.today())}


def _filtrar_vip(pred: dict) -> dict:
    """Devuelve solo los campos necesarios para un pick VIP."""
    return pred


def _filtrar_free(pred: dict) -> dict:
    """Vista previa para usuarios free — oculta EV y cuotas exactas."""
    return {
        "local":      pred.get("local"),
        "visitante":  pred.get("visitante"),
        "liga":       pred.get("liga"),
        "hora":       pred.get("hora"),
        "fecha_evento": pred.get("fecha_evento"),
        "deporte_emoji": pred.get("deporte_emoji", "⚽"),
        "prediccion_principal": {
            "mercado": pred.get("prediccion_principal", {}).get("mercado", "—"),
            "prob":    "??",
            "ev":      None,
        },
        "bloqueado": True,
    }


@router.get("/hoy")
def picks_hoy(token=Depends(usuario_activo)):
    """Todos los picks del día según el plan del usuario."""
    plan    = token.get("plan", "free")
    data    = _cargar_predicciones()
    preds   = data.get("predicciones", [])
    fecha   = data.get("fecha", str(date.today()))

    if plan in ("vip", "admin"):
        # VIP: todos los picks con EV positivo vs Pinnacle
        picks_vip = []
        for p in preds:
            ev_max = max(
                (vb.get("ev_pinn", 0) or 0 for vb in p.get("value_bets", {}).values()),
                default=0
            )
            if ev_max >= 5:
                picks_vip.append(_filtrar_vip(p))
        return {"plan": plan, "fecha": fecha, "total": len(picks_vip), "picks": picks_vip}
    else:
        # Free: 2 picks como preview (sin EV, sin cuotas)
        preview = [_filtrar_free(p) for p in preds[:2]]
        total_vip = sum(
            1 for p in preds
            if max((vb.get("ev_pinn", 0) or 0 for vb in p.get("value_bets", {}).values()), default=0) >= 5
        )
        return {
            "plan":      "free",
            "fecha":     fecha,
            "total":     2,
            "total_vip": total_vip,
            "picks":     preview,
            "mensaje":   f"Hoy hay {total_vip} picks con EV+ para suscriptores VIP",
        }


@router.get("/historial")
def historial(token=Depends(usuario_activo), limite: int = Query(50, le=200)):
    """Historial de picks publicados con resultado."""
    plan = token.get("plan", "free")
    with db() as conn:
        cur = conn.cursor()
        if plan in ("vip", "admin"):
            cur.execute("""
                SELECT fecha, partido, liga, prediccion, cuota, emoji,
                       resultado, ev_pinn, publicado_en
                FROM picks_publicados
                ORDER BY publicado_en DESC LIMIT %s
            """, (limite,))
        else:
            # Free: solo los últimos 5 y sin EV
            cur.execute("""
                SELECT fecha, partido, liga, prediccion, cuota, emoji,
                       resultado, publicado_en
                FROM picks_publicados
                WHERE plan_requerido='free'
                ORDER BY publicado_en DESC LIMIT 5
            """)
        rows = cur.fetchall()
        return [dict(r) for r in rows]


@router.get("/stats")
def stats_publicas():
    """Estadísticas públicas: win rate, ROI, total picks. Sin auth requerida."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE resultado IN ('win','loss')) as resueltos,
                COUNT(*) FILTER (WHERE resultado='win') as wins,
                COUNT(*) FILTER (WHERE resultado='loss') as losses,
                ROUND(AVG(CASE WHEN resultado='win' AND cuota != '' AND cuota IS NOT NULL
                          THEN CAST(cuota AS NUMERIC) - 1 ELSE NULL END)::NUMERIC, 3) as roi_win,
                COUNT(*) as total_picks
            FROM picks_publicados
        """)
        row = cur.fetchone()
        wins     = int(row["wins"] or 0)
        losses   = int(row["losses"] or 0)
        resueltos = wins + losses
        win_rate = round(wins / resueltos * 100, 1) if resueltos else 0
        return {
            "total_picks":  int(row["total_picks"] or 0),
            "resueltos":    resueltos,
            "wins":         wins,
            "losses":       losses,
            "win_rate":     win_rate,
            "fecha_inicio": "2026-05-23",
        }


@router.post("/publicar")
def publicar_pick(body: dict, token=Depends(solo_vip)):
    """Admin publica un pick en el historial."""
    required = ["fecha", "partido", "prediccion"]
    for f in required:
        if not body.get(f):
            raise HTTPException(400, f"Campo requerido: {f}")
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO picks_publicados
            (fecha, partido, liga, prediccion, cuota, hora, emoji, plan_requerido, ev_pinn)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            body["fecha"], body["partido"],
            body.get("liga",""), body["prediccion"],
            body.get("cuota",""), body.get("hora",""),
            body.get("emoji","⚽"), body.get("plan","vip"),
            body.get("ev_pinn"),
        ))
        new_id = cur.fetchone()["id"]
    return {"ok": True, "id": new_id}


@router.patch("/resultado/{pick_id}")
def marcar_resultado(pick_id: int, body: dict, token=Depends(solo_vip)):
    resultado = body.get("resultado")
    if resultado not in ("win", "loss", "void"):
        raise HTTPException(400, "resultado debe ser: win, loss o void")
    with db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE picks_publicados SET resultado=%s WHERE id=%s RETURNING id",
                    (resultado, pick_id))
        if not cur.fetchone():
            raise HTTPException(404, "Pick no encontrado")
    return {"ok": True, "resultado": resultado}
