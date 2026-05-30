# -*- coding: utf-8 -*-
"""
SharpIQ — Backtest histórico riguroso (Big-5 europeas)
======================================================
Reproduce la metodología del motor (Poisson + Dixon-Coles, no-vig de la línea
de mercado, blend por liquidez, EV, tiers, Half-Kelly) sobre 3 temporadas
reales con cuotas reales de cierre, SIN look-ahead (las stats de cada equipo
solo usan partidos PREVIOS de la misma temporada).

Fuente de datos: Club Football Match Data 2000-2025 (mirror football-data.co.uk),
que incluye resultados reales + cuotas de mercado (promedio y mejor disponible).

Uso:  python backtest_historico.py
Salida: backtest_resultados.json  (picks validados)  + resumen por consola.
"""
import json, math, os, io, csv
from collections import defaultdict
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_URL = "https://raw.githubusercontent.com/xgabora/Club-Football-Match-Data-2000-2025/main/data/Matches.csv"
LIGAS = {"E0": "Premier League", "SP1": "La Liga", "I1": "Serie A",
         "D1": "Bundesliga", "F1": "Ligue 1"}
# Ventaja local por liga (misma calibración que el motor)
VENTAJA = {"E0": 1.28, "SP1": 1.30, "D1": 1.27, "I1": 1.26, "F1": 1.24}

RHO          = -0.10   # Dixon-Coles (idéntico al motor)
PESO_MERCADO = 0.78    # blend alta liquidez (top-5 europeas), igual que el motor
MIN_PREV     = 5       # partidos previos mínimos por equipo (evita ruido inicial)

# Umbrales de tiers (idénticos a clasificar_tiers del motor)
SEGURO   = dict(prob=62.0, cuota_max=2.10, ev=2.0)
PRINC    = dict(prob=45.0, cuota_min=1.55, cuota_max=3.00, ev=2.0)
ALTO     = dict(prob=30.0, cuota_min=1.75, cuota_max=5.5, ev=7.0)


# ── Poisson + Dixon-Coles ──────────────────────────────────────
def _pois(k, lam):
    return math.exp(-lam) * lam**k / math.factorial(k)

def _dc_tau(i, j, lh, la):
    if   i == 0 and j == 0: return 1 - lh * la * RHO
    elif i == 1 and j == 0: return 1 + la * RHO
    elif i == 0 and j == 1: return 1 + lh * RHO
    elif i == 1 and j == 1: return 1 - RHO
    return 1.0

def probs_modelo(lh, la, maxg=8):
    m = {}
    tot = 0.0
    for i in range(maxg):
        for j in range(maxg):
            p = max(_pois(i, lh) * _pois(j, la) * _dc_tau(i, j, lh, la), 0.0)
            m[(i, j)] = p; tot += p
    if tot <= 0:
        return None
    for k in m: m[k] /= tot
    pl = sum(p for (i, j), p in m.items() if i > j)
    pe = sum(p for (i, j), p in m.items() if i == j)
    pv = sum(p for (i, j), p in m.items() if i < j)
    over = sum(p for (i, j), p in m.items() if i + j > 2.5)
    return {"1": pl, "X": pe, "2": pv, "over25": over, "under25": 1 - over}

def no_vig(odds):
    """odds = lista de cuotas decimales del mismo mercado -> probs justas."""
    inv = [1.0 / o for o in odds if o and o > 1.0]
    if len(inv) != len(odds) or not inv:
        return None
    s = sum(inv)
    return [x / s for x in inv]


# ── Half-Kelly (idéntico al motor) ─────────────────────────────
def kelly(prob_pct, cuota, frac=0.5, mn=1.0, mx=5.0):
    p = prob_pct / 100.0
    b = cuota - 1.0
    if p <= 0 or b <= 0: return mn
    k = (b * p - (1 - p)) / b
    if k <= 0: return mn
    return round(min(max(k * frac * 100, mn), mx), 1)


def clasificar(prob, cuota, ev):
    """Devuelve el tier o None. prob en %, ev en %."""
    if prob >= SEGURO["prob"] and cuota <= SEGURO["cuota_max"] and ev >= SEGURO["ev"]:
        return "SEGURO"
    if prob >= PRINC["prob"] and PRINC["cuota_min"] <= cuota <= PRINC["cuota_max"] and ev >= PRINC["ev"]:
        return "PRINCIPAL"
    if ev >= ALTO["ev"] and ALTO["cuota_min"] <= cuota <= ALTO["cuota_max"] and prob >= ALTO["prob"]:
        return "ALTO VALOR"
    return None


def season_of(d):
    y, m = int(d[:4]), int(d[5:7])
    return y if m >= 7 else y - 1


def cargar_datos():
    cache = os.path.join(BASE, "_bt_data.json")
    if os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    import requests
    r = requests.get(DATA_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=180)
    rows = list(csv.DictReader(io.StringIO(r.content.decode("latin-1"))))
    sub = [x for x in rows if x["Division"] in LIGAS
           and "2022-07-01" <= x["MatchDate"] <= "2025-07-01"
           and x.get("OddHome") and x.get("MaxHome") and x.get("Over25") and x.get("MaxOver25")]
    json.dump(sub, open(cache, "w", encoding="utf-8"))
    return sub


def f(x):
    try: return float(x)
    except (ValueError, TypeError): return None


def correr():
    data = cargar_datos()
    # Ordenar cronológicamente dentro de cada (liga, temporada)
    data.sort(key=lambda x: (x["Division"], x["MatchDate"]))
    # Stats rodantes por (liga, temporada, equipo)
    stats = defaultdict(lambda: {"gf": 0.0, "gc": 0.0, "n": 0})
    liga_avg = defaultdict(lambda: {"goles": 0.0, "n": 0})  # (liga,season) -> avg goles/equipo/partido

    picks = []
    for x in data:
        liga, fecha = x["Division"], x["MatchDate"]
        season = season_of(fecha)
        h, a = x["HomeTeam"], x["AwayTeam"]
        gh, ga = f(x["FTHome"]), f(x["FTAway"])
        if gh is None or ga is None:
            continue
        kh, ka = (liga, season, h), (liga, season, a)
        lk = (liga, season)

        sh, sa = stats[kh], stats[ka]
        avg = (liga_avg[lk]["goles"] / liga_avg[lk]["n"]) if liga_avg[lk]["n"] >= 40 else 1.40

        # Solo evaluar si ambos equipos tienen historial suficiente esta temporada
        if sh["n"] >= MIN_PREV and sa["n"] >= MIN_PREV and avg > 0:
            atk_h, def_h = sh["gf"] / sh["n"], sh["gc"] / sh["n"]
            atk_a, def_a = sa["gf"] / sa["n"], sa["gc"] / sa["n"]
            vent = VENTAJA.get(liga, 1.27)
            lh = (atk_h / avg) * (def_a / avg) * avg * vent
            la = (atk_a / avg) * (def_h / avg) * avg
            lh, la = max(0.15, min(lh, 5.0)), max(0.15, min(la, 5.0))
            pm = probs_modelo(lh, la)
            if pm:
                # No-vig de la línea de mercado (promedio) -> prob justa de mercado
                nv_1x2 = no_vig([f(x["OddHome"]), f(x["OddDraw"]), f(x["OddAway"])])
                nv_ou  = no_vig([f(x["Over25"]), f(x["Under25"])])
                mercados = []
                if nv_1x2:
                    mercados += [("1", nv_1x2[0], f(x["MaxHome"]), "Victoria Local"),
                                 ("X", nv_1x2[1], f(x["MaxDraw"]), "Empate"),
                                 ("2", nv_1x2[2], f(x["MaxAway"]), "Victoria Visitante")]
                if nv_ou:
                    mercados += [("over25", nv_ou[0], f(x["MaxOver25"]), "Over 2.5"),
                                 ("under25", nv_ou[1], f(x["MaxUnder25"]), "Under 2.5")]
                # Mejor pick del partido por EV (uno por partido, evita correlación)
                mejor = None
                for mk, p_mkt, cuota, nombre in mercados:
                    if not cuota or cuota <= 1.0:
                        continue
                    blend = PESO_MERCADO * p_mkt + (1 - PESO_MERCADO) * pm[mk]
                    ev = (blend * cuota - 1) * 100
                    prob_pct = blend * 100
                    tier = clasificar(prob_pct, cuota, ev)
                    if tier and (mejor is None or ev > mejor["ev"]):
                        mejor = {"mercado": mk, "nombre": nombre, "prob": round(prob_pct, 1),
                                 "cuota": round(cuota, 2), "ev": round(ev, 1), "tier": tier}
                if mejor:
                    # Resolver resultado real
                    tot = gh + ga
                    res_map = {"1": gh > ga, "2": ga > gh, "X": gh == ga,
                               "over25": tot > 2.5, "under25": tot < 2.5}
                    gano = res_map[mejor["mercado"]]
                    stake = kelly(mejor["prob"], mejor["cuota"])
                    profit_u = (mejor["cuota"] - 1) if gano else -1.0          # flat 1u
                    profit_k = stake * (mejor["cuota"] - 1) if gano else -stake  # half-kelly %
                    picks.append({**mejor, "liga": LIGAS[liga], "div": liga, "fecha": fecha,
                                  "partido": f"{h} vs {a}", "marcador": f"{int(gh)}-{int(ga)}",
                                  "resultado": "win" if gano else "loss",
                                  "stake_pct": stake, "profit_u": round(profit_u, 3),
                                  "profit_k": round(profit_k, 3)})

        # Actualizar stats DESPUÉS de evaluar (no look-ahead)
        sh["gf"] += gh; sh["gc"] += ga; sh["n"] += 1
        sa["gf"] += ga; sa["gc"] += gh; sa["n"] += 1
        liga_avg[lk]["goles"] += gh + ga; liga_avg[lk]["n"] += 2

    return picks


def resumen(picks):
    n = len(picks)
    w = sum(1 for p in picks if p["resultado"] == "win")
    stake_flat = n * 1.0
    pl_flat = sum(p["profit_u"] for p in picks)
    stake_k = sum(p["stake_pct"] for p in picks)
    pl_k = sum(p["profit_k"] for p in picks)
    print("\n" + "=" * 62)
    print(f"  BACKTEST SHARPIQ — Big-5 europeas, 3 temporadas (2022-2025)")
    print("=" * 62)
    print(f"  Picks validados : {n}")
    print(f"  Aciertos (W/L)  : {w}W / {n-w}L  ({w/n*100:.1f}% win rate)")
    print(f"  Cuota promedio  : {sum(p['cuota'] for p in picks)/n:.2f}")
    print(f"  --- Stake plano (1u/pick) ---")
    print(f"  Apostado: {stake_flat:.0f}u | Neto: {pl_flat:+.1f}u | ROI: {pl_flat/stake_flat*100:+.1f}%")
    print(f"  --- Half-Kelly (% bankroll) ---")
    print(f"  Apostado: {stake_k:.1f}u | Neto: {pl_k:+.1f}u | ROI: {pl_k/stake_k*100:+.1f}%")
    for dim, key in [("LIGA", "liga"), ("TIER", "tier"), ("MERCADO", "nombre")]:
        print(f"  --- por {dim} ---")
        agg = defaultdict(lambda: [0, 0, 0.0])
        for p in picks:
            a = agg[p[key]]; a[0] += 1; a[1] += p["resultado"] == "win"; a[2] += p["profit_u"]
        for k, (cnt, wins, pl) in sorted(agg.items(), key=lambda kv: -kv[1][2]):
            print(f"    {k:18s} {cnt:4d} picks | {wins/cnt*100:4.1f}% WR | ROI {pl/cnt*100:+5.1f}%")
    print("=" * 62)


if __name__ == "__main__":
    picks = correr()
    json.dump(picks, open(os.path.join(BASE, "backtest_resultados.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"Guardados {len(picks)} picks en backtest_resultados.json")
    resumen(picks)
