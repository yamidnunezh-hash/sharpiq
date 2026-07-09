"""
SharpIQ — Backtest del modelo MLB
═══════════════════════════════════════════════════════════════════════════════
FASE 4. El portero. Responde UNA pregunta:

    ¿Este modelo habría GANADO plata apostando contra el mercado real?

Reglas para que el resultado no sea una mentira:

  1. SIN MIRAR EL FUTURO (data leakage). Para un partido del 20 de junio,
     las estadísticas de equipos y lanzadores se piden con `byDateRange` hasta
     el 19 de junio. Si usáramos las de hoy, el modelo "sabría" cómo terminó la
     temporada y el backtest daría un número precioso y falso.

  2. CUOTAS REALES DE ESE DÍA, no las de hoy. Snapshot histórico de The Odds API
     tomado antes de los partidos.

  3. LAS MISMAS COMPUERTAS que en producción (EV/edge mínimo y máximo).

  4. STAKE PLANO de 1 unidad. Sin Kelly, sin martingala, sin maquillaje.

Métrica que manda: el YIELD (unidades ganadas / unidades apostadas).
En apuestas deportivas, +2% a +5% de yield sostenido ya es un negocio muy bueno.
Un yield del +20% en una muestra chica es ruido, no talento.

    python mlb_backtest.py                          # último mes
    python mlb_backtest.py 2026-06-01 2026-07-07

⚠️ Si el yield sale NEGATIVO, MLB no se publica. Ese es el trato.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date, timedelta

import requests

from config import ODDS_API_KEY
from mlb_datos import BASE, _get, _f
from mlb_modelo import carreras_esperadas, mercados
from mlb_ev import (EV_MINIMO, EDGE_MINIMO, EDGE_MAXIMO, EV_MAXIMO,
                    _norm, _mercado, _sin_margen, _mejor, _pinn_par)

INICIO_TEMPORADA = "2026-03-01"
HIST_URL = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/odds"
BOOKMAKERS = "pinnacle,draftkings,fanduel,betmgm,bet365"

_cache_equipos: dict[str, tuple[dict, dict]] = {}
_cache_pitcher: dict[tuple, dict] = {}


# ── Estadísticas "como se veían" en una fecha ─────────────────────────────────
def stats_equipos_a_fecha(hasta: str) -> tuple[dict, dict]:
    """(stats por team_id, medias de liga) usando SOLO datos hasta `hasta`."""
    if hasta in _cache_equipos:
        return _cache_equipos[hasta]

    q = (f"stats=byDateRange&season=2026&sportIds=1"
         f"&startDate={INICIO_TEMPORADA}&endDate={hasta}")
    hit = _get(f"{BASE}/teams/stats?{q}&group=hitting")["stats"][0]["splits"]
    pit = _get(f"{BASE}/teams/stats?{q}&group=pitching")["stats"][0]["splits"]

    equipos: dict[int, dict] = {}
    for s in hit:
        st, tid = s["stat"], s["team"]["id"]
        g = int(st.get("gamesPlayed") or 0) or 1
        equipos[tid] = {"juegos": g,
                        "ca_por_juego": int(st.get("runs") or 0) / g,
                        "ops": _f(st.get("ops"), 0.700)}
    for s in pit:
        st, tid = s["stat"], s["team"]["id"]
        if tid not in equipos:
            continue
        g = equipos[tid]["juegos"]
        equipos[tid]["cp_por_juego"] = int(st.get("runs") or 0) / g
        equipos[tid]["era_equipo"]   = _f(st.get("era"), 4.30)

    validos = [e for e in equipos.values() if "era_equipo" in e]
    liga = {
        "carreras_por_juego": sum(e["ca_por_juego"] for e in validos) / len(validos),
        "era": sum(e["era_equipo"] for e in validos) / len(validos),
        "equipos": len(validos),
    }
    _cache_equipos[hasta] = (equipos, liga)
    return equipos, liga


def stats_pitcher_a_fecha(pid: int, hasta: str) -> dict:
    if not pid:
        return {}
    clave = (pid, hasta)
    if clave in _cache_pitcher:
        return _cache_pitcher[clave]
    try:
        d = _get(f"{BASE}/people/{pid}/stats?stats=byDateRange&group=pitching"
                 f"&season=2026&startDate={INICIO_TEMPORADA}&endDate={hasta}")
        st = d["stats"][0]["splits"][0]["stat"]
        out = {"era": _f(st.get("era"), 0), "whip": _f(st.get("whip"), 0),
               "entradas": _f(st.get("inningsPitched"), 0)}
    except Exception:
        out = {}
    _cache_pitcher[clave] = out
    return out


# ── Partidos ya jugados, con resultado ────────────────────────────────────────
def juegos_finalizados(fecha: str) -> list[dict]:
    d = _get(f"{BASE}/schedule?sportId=1&date={fecha}&hydrate=probablePitcher,team")
    out = []
    for dia in d.get("dates", []):
        for g in dia.get("games", []):
            if g.get("status", {}).get("detailedState") != "Final":
                continue
            loc, vis = g["teams"]["home"], g["teams"]["away"]
            if loc.get("score") is None or vis.get("score") is None:
                continue
            out.append({
                "local":  {"id": loc["team"]["id"], "nombre": loc["team"]["name"],
                           "pid": (loc.get("probablePitcher") or {}).get("id"),
                           "carreras": loc["score"]},
                "visita": {"id": vis["team"]["id"], "nombre": vis["team"]["name"],
                           "pid": (vis.get("probablePitcher") or {}).get("id"),
                           "carreras": vis["score"]},
            })
    return out


def cuotas_historicas(fecha: str) -> list[dict]:
    """Snapshot de cuotas del mediodía (antes de que empiece casi cualquier juego)."""
    r = requests.get(HIST_URL, timeout=25, params={
        "apiKey": ODDS_API_KEY, "bookmakers": BOOKMAKERS,
        "markets": "h2h,spreads,totals", "oddsFormat": "decimal",
        "date": f"{fecha}T16:00:00Z",
    })
    if r.status_code != 200:
        return []
    return r.json().get("data", [])


# ── Un partido: del dato crudo a las apuestas resueltas ───────────────────────
def apuestas_del_partido(j: dict, ev_evento: dict, hasta: str) -> list[dict]:
    equipos, liga = stats_equipos_a_fecha(hasta)
    if j["local"]["id"] not in equipos or j["visita"]["id"] not in equipos:
        return []

    datos = {}
    for lado in ("local", "visita"):
        datos[lado] = {
            "nombre":  j[lado]["nombre"],
            "equipo":  equipos[j[lado]["id"]],
            "pitcher": stats_pitcher_a_fecha(j[lado]["pid"], hasta),
        }

    lam_v, lam_l = carreras_esperadas(datos, liga=liga)

    outs_tot = _mercado(ev_evento, "totals", casa="pinnacle")
    if not outs_tot:
        return []
    linea = outs_tot[0]["point"]
    m = mercados(lam_v, lam_l, linea)

    local, visita = j["local"]["nombre"], j["visita"]["nombre"]
    cl, cv = j["local"]["carreras"], j["visita"]["carreras"]
    total_real, margen_local = cl + cv, cl - cv

    # (nombre, prob_modelo, prob_pinnacle, mejor_outcome, resultado_real, mercado)
    pp_loc, pp_vis = _pinn_par(ev_evento, "h2h", local, visita)
    h2h = _mercado(ev_evento, "h2h")

    pp_l15, pp_v15  = _pinn_par(ev_evento, "spreads", local, visita, -1.5, 1.5)
    pp_v15b, pp_l15b = _pinn_par(ev_evento, "spreads", visita, local, -1.5, 1.5)
    spr = _mercado(ev_evento, "spreads")

    pp_ov, pp_un = _pinn_par(ev_evento, "totals", "Over", "Under", linea, linea)
    tot = _mercado(ev_evento, "totals")

    def res_total(over: bool):
        if total_real == linea:
            return "push"
        gano = total_real > linea if over else total_real < linea
        return "win" if gano else "loss"

    cands = [
        (f"Gana {local}",  m["gana_local"],  pp_loc, _mejor(h2h, local),
         "win" if margen_local > 0 else "loss", "ganador"),
        (f"Gana {visita}", m["gana_visita"], pp_vis, _mejor(h2h, visita),
         "win" if margen_local < 0 else "loss", "ganador"),

        (f"{local} -1.5",  m["run_line_local_-1.5"], pp_l15,
         _mejor(spr, local, -1.5),
         "win" if margen_local >= 2 else "loss", "run_line"),
        (f"{visita} +1.5", 1 - m["run_line_local_-1.5"], pp_v15,
         _mejor(spr, visita, 1.5),
         "win" if margen_local < 2 else "loss", "run_line"),
        (f"{visita} -1.5", m["run_line_visita_-1.5"], pp_v15b,
         _mejor(spr, visita, -1.5),
         "win" if -margen_local >= 2 else "loss", "run_line"),
        (f"{local} +1.5",  1 - m["run_line_visita_-1.5"], pp_l15b,
         _mejor(spr, local, 1.5),
         "win" if -margen_local < 2 else "loss", "run_line"),

        (f"Más de {linea}",  m["over"],  pp_ov, _mejor(tot, "Over", linea),
         res_total(True), "total"),
        (f"Menos de {linea}", m["under"], pp_un, _mejor(tot, "Under", linea),
         res_total(False), "total"),
    ]

    filas = []
    for nombre, pm, pp, out, resultado, mkt in cands:
        if not out or pp is None:
            continue
        cuota = out["price"]
        filas.append({
            "partido": f"{visita} @ {local}", "apuesta": nombre, "mercado": mkt,
            "cuota": cuota, "prob_modelo": pm, "prob_pinnacle": pp,
            "edge": pm - pp, "ev": pm * cuota - 1, "resultado": resultado,
        })
    return filas


def _resumen(picks: list[dict], titulo: str):
    if not picks:
        print(f"  {titulo}: sin apuestas")
        return
    n = len(picks)
    ganadas = sum(1 for p in picks if p["resultado"] == "win")
    empates = sum(1 for p in picks if p["resultado"] == "push")
    perdidas = n - ganadas - empates
    arriesgado = n - empates
    unidades = sum((p["cuota"] - 1) if p["resultado"] == "win"
                   else 0 if p["resultado"] == "push" else -1 for p in picks)
    yield_ = unidades / arriesgado * 100 if arriesgado else 0
    acierto = ganadas / arriesgado * 100 if arriesgado else 0
    cuota_media = sum(p["cuota"] for p in picks) / n
    print(f"  {titulo}")
    print(f"    {n} picks | {ganadas}W {perdidas}L {empates}P | acierto {acierto:.1f}% "
          f"| cuota media {cuota_media:.2f}")
    print(f"    unidades {unidades:+.2f} | YIELD {yield_:+.2f}%")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        d0, d1 = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2])
    else:
        d1 = date.today() - timedelta(days=2)
        d0 = d1 - timedelta(days=30)

    print(f"\nBACKTEST MLB · {d0} → {d1}")
    print("Stats point-in-time (sin mirar el futuro) · cuotas históricas reales\n")

    todas, dias, sin_odds = [], 0, 0
    bias_tot, bias_loc, nb = 0.0, 0.0, 0

    d = d0
    while d <= d1:
        f = d.isoformat()
        hasta = (d - timedelta(days=1)).isoformat()   # ← la clave: día ANTERIOR
        juegos = juegos_finalizados(f)
        eventos = cuotas_historicas(f) if juegos else []
        if juegos and not eventos:
            sin_odds += 1
        for j in juegos:
            ev_evento = None
            for e in eventos:
                h, a = _norm(e.get("home_team", "")), _norm(e.get("away_team", ""))
                if (h == _norm(j["local"]["nombre"]) and a == _norm(j["visita"]["nombre"])) \
                   or (h.split()[-1:] == _norm(j["local"]["nombre"]).split()[-1:]
                       and a.split()[-1:] == _norm(j["visita"]["nombre"]).split()[-1:]):
                    ev_evento = e
                    break
            if not ev_evento:
                continue
            filas = apuestas_del_partido(j, ev_evento, hasta)
            todas += filas
            for fl in filas:
                if fl["apuesta"].startswith("Gana ") and fl["apuesta"][5:] == j["local"]["nombre"]:
                    bias_loc += fl["edge"]; nb += 1
        dias += 1
        print(f"  {f}: {len(juegos)} juegos, {len(todas)} apuestas evaluadas", flush=True)
        d += timedelta(days=1)

    print(f"\n{'='*70}")
    print(f"MUESTRA: {dias} días · {len(todas)} apuestas candidatas evaluadas")
    if sin_odds:
        print(f"({sin_odds} día(s) sin snapshot de cuotas)")
    if nb:
        print(f"Sesgo local fuera de muestra: {bias_loc/nb:+.2%}  [ideal ~0]")
    print(f"{'='*70}\n")

    # 1) Control: apostar TODO lo que el modelo cree que tiene valor (sin compuerta)
    crudas = [p for p in todas if p["ev"] >= EV_MINIMO and p["edge"] >= EDGE_MINIMO]
    _resumen(crudas, "SIN COMPUERTA (todo lo que el modelo llama 'valor')")
    print()

    # 2) Producción: con la compuerta de valor
    filtradas = [p for p in crudas
                 if p["edge"] <= EDGE_MAXIMO and p["ev"] <= EV_MAXIMO]
    _resumen(filtradas, "CON COMPUERTA DE VALOR (lo que publicaríamos)")
    print()

    # 3) Desglose por mercado — ¿dónde está (o no está) la ventaja?
    por_mkt = defaultdict(list)
    for p in filtradas:
        por_mkt[p["mercado"]].append(p)
    print("  Por mercado:")
    for mkt, ps in sorted(por_mkt.items()):
        _resumen(ps, f"  → {mkt}")
    print()

    # 4) Control negativo: apostar TODO sin filtrar. Debe dar ~-4.5% (el margen).
    _resumen(todas, "CONTROL — apostar todo a ciegas (debe perder ~el margen)")

    print(f"\n{'='*70}")
    print("VEREDICTO: si el yield CON COMPUERTA no es claramente positivo,")
    print("MLB NO se publica. Un modelo que no le gana al mercado cuesta plata.")
    print(f"{'='*70}")
