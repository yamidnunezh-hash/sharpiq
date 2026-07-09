"""
SharpIQ — MLB: valor esperado contra el mercado
═══════════════════════════════════════════════════════════════════════════════
FASE 3 del proyecto "MLB pulido". Enfrenta las probabilidades de mlb_modelo.py
contra las cuotas REALES de The Odds API.

Dos números por cada apuesta:

  EDGE  = prob_modelo − prob_pinnacle_sin_margen
          ¿Sabemos algo que Pinnacle no sabe? Pinnacle es la casa más eficiente
          del mundo: su precio (quitándole el margen) es la mejor estimación
          pública de la probabilidad real. Un edge grande casi siempre significa
          que NOSOTROS estamos equivocados, no ellos.

  EV    = prob_modelo × mejor_cuota_disponible − 1
          Lo que ganamos por peso apostado, a largo plazo, si el modelo acierta.

Un pick solo tiene sentido si EV y EDGE son positivos A LA VEZ. Si el EV sale
positivo pero el edge contra Pinnacle es negativo, lo único que encontramos fue
una casa despistada... o un error nuestro.

    python mlb_ev.py            # partidos de hoy
    python mlb_ev.py 2026-07-10

⚠️ ESTE MÓDULO NO PUBLICA NADA. Solo imprime. El motor no lo llama.
   Sin el backtest de la Fase 4, estos "picks" son una hipótesis, no una apuesta.
"""
from __future__ import annotations

import sys
from datetime import date

import requests

from config import ODDS_API_KEY
from mlb_datos import partidos_de_hoy
from mlb_modelo import analizar, cuota_justa

ODDS_URL   = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
BOOKMAKERS = "pinnacle,draftkings,fanduel,betmgm,bet365"
EV_MINIMO   = 0.03    # 3% — por debajo, el ruido se come la ventaja
EDGE_MINIMO = 0.02    # 2% — hay que saber algo real, no solo pillar mal precio

# COMPUERTA DE VALOR (misma idea que el motor de fútbol). Pinnacle no se
# equivoca por 10 puntos porcentuales. Un edge enorme NO es una mina de oro:
# es la firma de un dato malo o de un partido que no entendemos (abridor
# suplente, bullpen quemado, lluvia, viento). Tirar esos picks a la basura
# es lo que separa un modelo rentable de uno que se desangra.
EDGE_MAXIMO = 0.08    # >8% de desacuerdo con Pinnacle = sospechoso, descartar
EV_MAXIMO   = 0.20    # >20% de EV en MLB no existe. Si aparece, es un bug.


# ── Cuotas ────────────────────────────────────────────────────────────────────
def cuotas_mlb() -> list[dict]:
    r = requests.get(ODDS_URL, timeout=15, params={
        "apiKey": ODDS_API_KEY, "bookmakers": BOOKMAKERS,
        "markets": "h2h,spreads,totals", "oddsFormat": "decimal",
    })
    if r.status_code != 200:
        print(f"  Odds API: HTTP {r.status_code} — {r.text[:140]}")
        return []
    print(f"  Odds API: {len(r.json())} partidos MLB | "
          f"créditos restantes: {r.headers.get('x-requests-remaining','?')}")
    return r.json()


def _norm(s: str) -> str:
    return s.lower().replace(".", "").strip()


def emparejar(partido_modelo: dict, eventos: list[dict]) -> dict | None:
    """Encuentra el evento de The Odds API que corresponde al partido de MLB API."""
    loc, vis = _norm(partido_modelo["local"]), _norm(partido_modelo["visita"])
    for ev in eventos:
        h, a = _norm(ev.get("home_team", "")), _norm(ev.get("away_team", ""))
        if (h == loc and a == vis):
            return ev
        # "Athletics" vs "Oakland Athletics": comparar por apodo (última palabra)
        if h.split()[-1:] == loc.split()[-1:] and a.split()[-1:] == vis.split()[-1:]:
            return ev
    return None


def _mercado(ev: dict, key: str, casa: str | None = None) -> list[dict]:
    """Outcomes de un mercado. Si se pide una casa, solo la de esa casa."""
    salida = []
    for bm in ev.get("bookmakers", []):
        if casa and bm["key"] != casa:
            continue
        for mk in bm.get("markets", []):
            if mk["key"] == key:
                for o in mk.get("outcomes", []):
                    salida.append({**o, "casa": bm["key"]})
    return salida


def _sin_margen(cuota_a: float, cuota_b: float) -> tuple[float, float]:
    """Quita el margen de la casa: dos probabilidades que suman exactamente 1."""
    pa, pb = 1 / cuota_a, 1 / cuota_b
    total = pa + pb
    return pa / total, pb / total


def _mejor(outcomes: list[dict], nombre: str, punto: float | None = None):
    """Mejor cuota disponible (la más alta) para un resultado concreto."""
    cands = [o for o in outcomes
             if _norm(o["name"]) == _norm(nombre)
             and (punto is None or abs(o.get("point", 0) - punto) < 0.01)]
    return max(cands, key=lambda o: o["price"]) if cands else None


def _pinn_par(ev: dict, key: str, n1: str, n2: str,
              p1: float | None = None, p2: float | None = None):
    """Probabilidades sin margen de Pinnacle para un par de resultados opuestos."""
    outs = _mercado(ev, key, casa="pinnacle")
    o1, o2 = _mejor(outs, n1, p1), _mejor(outs, n2, p2)
    if not o1 or not o2:
        return None, None
    return _sin_margen(o1["price"], o2["price"])


# ── Evaluación ────────────────────────────────────────────────────────────────
def _evaluar(nombre, prob_modelo, prob_pinn, mejor_out):
    """Arma la fila de una apuesta candidata."""
    if not mejor_out or prob_pinn is None:
        return None
    cuota = mejor_out["price"]
    return {
        "apuesta": nombre,
        "cuota": cuota,
        "casa": mejor_out["casa"],
        "prob_modelo": prob_modelo,
        "prob_pinnacle": prob_pinn,
        "cuota_justa": cuota_justa(prob_modelo),
        "edge": prob_modelo - prob_pinn,
        "ev": prob_modelo * cuota - 1,
    }


def analizar_con_mercado(juego: dict, ev_evento: dict) -> list[dict]:
    """Todas las apuestas candidatas de un partido, con su EV y su edge."""
    # La línea de totales la manda Pinnacle: modelamos SU línea, no una inventada.
    outs_tot = _mercado(ev_evento, "totals", casa="pinnacle")
    linea = outs_tot[0]["point"] if outs_tot else 8.5

    m = analizar(juego, linea_total=linea)
    local, visita = m["local"], m["visita"]
    filas = []

    # 1) Ganador (moneyline)
    pp_loc, pp_vis = _pinn_par(ev_evento, "h2h", local, visita)
    h2h = _mercado(ev_evento, "h2h")
    filas += [
        _evaluar(f"Gana {local}",  m["gana_local"],  pp_loc, _mejor(h2h, local)),
        _evaluar(f"Gana {visita}", m["gana_visita"], pp_vis, _mejor(h2h, visita)),
    ]

    # 2) Run line -1.5 / +1.5
    pp_l15, pp_v15 = _pinn_par(ev_evento, "spreads", local, visita, -1.5, 1.5)
    spreads = _mercado(ev_evento, "spreads")
    filas += [
        _evaluar(f"{local} -1.5 (gana por 2+)", m["run_line_local_-1.5"],
                 pp_l15, _mejor(spreads, local, -1.5)),
        # +1.5 = el complemento: gana o pierde por 1
        _evaluar(f"{visita} +1.5 (no pierde por 2+)", 1 - m["run_line_local_-1.5"],
                 pp_v15, _mejor(spreads, visita, 1.5)),
    ]
    pp_v15b, pp_l15b = _pinn_par(ev_evento, "spreads", visita, local, -1.5, 1.5)
    filas += [
        _evaluar(f"{visita} -1.5 (gana por 2+)", m["run_line_visita_-1.5"],
                 pp_v15b, _mejor(spreads, visita, -1.5)),
        _evaluar(f"{local} +1.5 (no pierde por 2+)", 1 - m["run_line_visita_-1.5"],
                 pp_l15b, _mejor(spreads, local, 1.5)),
    ]

    # 3) Más / Menos de carreras
    pp_ov, pp_un = _pinn_par(ev_evento, "totals", "Over", "Under", linea, linea)
    tot = _mercado(ev_evento, "totals")
    filas += [
        _evaluar(f"Más de {linea} carreras",  m["over"],  pp_ov,
                 _mejor(tot, "Over", linea)),
        _evaluar(f"Menos de {linea} carreras", m["under"], pp_un,
                 _mejor(tot, "Under", linea)),
    ]

    for f in filas:
        if f:
            f["partido"] = m["partido"]
    return [f for f in filas if f]


if __name__ == "__main__":
    fecha   = sys.argv[1] if len(sys.argv) > 1 else None
    eventos = cuotas_mlb()
    juegos  = partidos_de_hoy(fecha)

    print(f"\nMLB — modelo vs mercado · {fecha or date.today().isoformat()}\n")

    todas, sin_cuotas = [], 0
    for j in juegos:
        m_prev = {"local": j["local"]["nombre"], "visita": j["visita"]["nombre"]}
        ev_evento = emparejar(m_prev, eventos)
        if not ev_evento:
            sin_cuotas += 1
            continue
        todas += analizar_con_mercado(j, ev_evento)

    if sin_cuotas:
        print(f"  ({sin_cuotas} partido(s) sin cuotas — probablemente ya empezaron)\n")

    # ¿Qué tan lejos está el modelo de Pinnacle? Este es el número que importa.
    edges = [abs(f["edge"]) for f in todas]
    if edges:
        print(f"  Desvío medio contra Pinnacle: {sum(edges)/len(edges):.1%}")
        print(f"  (si supera ~4%, el modelo está mal calibrado, no genial)\n")

    crudas = [f for f in todas
              if f["ev"] >= EV_MINIMO and f["edge"] >= EDGE_MINIMO]
    picks  = [f for f in crudas
              if f["edge"] <= EDGE_MAXIMO and f["ev"] <= EV_MAXIMO]
    picks.sort(key=lambda f: f["ev"], reverse=True)

    descartadas = len(crudas) - len(picks)
    if descartadas:
        print(f"  {descartadas} candidata(s) DESCARTADAS por la compuerta "
              f"(edge >{EDGE_MAXIMO:.0%} o EV >{EV_MAXIMO:.0%}): "
              f"desacuerdo así de grande con Pinnacle = error nuestro.\n")

    if not picks:
        print("  Sin apuestas de valor hoy. Eso es una respuesta válida.\n")
    else:
        print(f"  {len(picks)} candidata(s) — EV ≥ {EV_MINIMO:.0%} y edge ≥ {EDGE_MINIMO:.0%}:\n")
        for f in picks:
            print(f"  {f['partido']}")
            print(f"    {f['apuesta']}  @ {f['cuota']} ({f['casa']})")
            print(f"    modelo {f['prob_modelo']:.1%} · pinnacle {f['prob_pinnacle']:.1%} "
                  f"· edge {f['edge']:+.1%} · EV {f['ev']:+.1%}")
            print()

    print("⚠️  NADA de esto se publica. Falta la Fase 4: el backtest.")
    print("    Un EV positivo hoy no prueba ventaja; solo prueba desacuerdo.")
