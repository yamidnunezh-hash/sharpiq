# -*- coding: utf-8 -*-
"""
SharpIQ — CLV snapshot. Corre cada 1h. Por cada pick ABIERTO captura la cuota
actual (movimiento de linea) en odds_history; cuando un pick ya empezo, congela
la ultima captura como CIERRE y calcula CLV. Match SIEMPRE por evento_id+mercado.
"""
import os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db_clv
from psycopg2.extras import RealDictCursor


def _best_cuota(evento, mercado, home, away):
    """(cuota, casa) actual del mercado del pick dentro de un evento de The Odds API.
    Decodifica la key del value_bet -> (market, outcome). Soporta 1X2 / moneyline y
    Over/Under. Mercados exoticos (handicap, btts, dc) -> (None, None) por ahora."""
    m = (mercado or "").lower()
    tgt_mkt = tgt_name = tgt_point = None
    if m == "victoria_local" or mercado == home:
        tgt_mkt, tgt_name = "h2h", home
    elif m == "victoria_visita" or mercado == away:
        tgt_mkt, tgt_name = "h2h", away
    elif m in ("empate", "draw"):
        tgt_mkt, tgt_name = "h2h", "Draw"
    elif m.startswith("over") or m.startswith("under"):
        tgt_mkt = "totals"
        tgt_name = "Over" if m.startswith("over") else "Under"
        num = m.replace("over", "").replace("under", "").strip("_")
        if "_" in num:                       # US: "5_5" -> 5.5
            tgt_point = float(num.replace("_", "."))
        elif num.isdigit() and len(num) >= 2:  # futbol: "25" -> 2.5
            tgt_point = float(num[:-1] + "." + num[-1])
    if not tgt_mkt:
        return (None, None)
    best_pr, best_casa = 0, None
    for bm in evento.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            if mkt.get("key") != tgt_mkt:
                continue
            for o in mkt.get("outcomes", []):
                if o.get("name") != tgt_name:
                    continue
                if tgt_point is not None and o.get("point") != tgt_point:
                    continue
                pr = o.get("price", 0)
                if pr and pr > best_pr:
                    best_pr, best_casa = pr, bm.get("title", bm.get("key", ""))
    return (best_pr or None, best_casa)


def correr(fetch_odds=None, ahora=None):
    """fetch_odds(liga_code)->[eventos] (default motor.obtener_cuotas_liga).
    ahora: datetime UTC (default now). Ambos inyectables para pruebas."""
    if fetch_odds is None:
        from motor import obtener_cuotas_liga as fetch_odds
    if ahora is None:
        ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    conn = db_clv._conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1) CAPTURA — picks abiertos (evento futuro, sin cierre), agrupados por deporte
    cur.execute("""SELECT pick_uid, evento_id, partido, mercado, liga_code
                   FROM picks WHERE cuota_cierre IS NULL AND comienzo > %s""", (ahora,))
    por_liga = {}
    for p in cur.fetchall():
        por_liga.setdefault(p["liga_code"], []).append(p)

    n_snap = 0
    for liga_code, picks in por_liga.items():
        try:
            eventos = fetch_odds(liga_code) or []
        except Exception:
            eventos = []
        ev_by_id = {str(e.get("id")): e for e in eventos}
        for p in picks:
            ev = ev_by_id.get(str(p["evento_id"]))
            if not ev:
                continue   # evento no esta en el feed (ya empezo / no disponible)
            cuota, casa = _best_cuota(ev, p["mercado"], ev.get("home_team", ""), ev.get("away_team", ""))
            if cuota:
                db_clv.guardar_odds_history(p["pick_uid"], p["evento_id"], p["partido"],
                                            p["mercado"], casa or "", cuota)
                n_snap += 1

    # 2) CIERRE — picks que ya empezaron y sin cierre: ultima snapshot = cierre
    cur.execute("""SELECT pick_uid, cuota_apertura FROM picks
                   WHERE cuota_cierre IS NULL AND comienzo <= %s""", (ahora,))
    n_cierre = 0
    for p in cur.fetchall():
        cur.execute("""SELECT cuota FROM odds_history WHERE pick_uid=%s
                       ORDER BY ts DESC LIMIT 1""", (p["pick_uid"],))
        row = cur.fetchone()
        cierre = row["cuota"] if row else p["cuota_apertura"]  # sin snapshot -> apertura
        db_clv.actualizar_cierre(p["pick_uid"], cierre)
        n_cierre += 1

    conn.close()
    print(f"CLV snapshot: {n_snap} capturas, {n_cierre} cierres")
    return n_snap, n_cierre


if __name__ == "__main__":
    correr()