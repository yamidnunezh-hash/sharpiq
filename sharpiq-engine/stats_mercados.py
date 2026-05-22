# -*- coding: utf-8 -*-
"""
SharpIQ — Mercados Extendidos
Corners, Tarjetas, Handicap Asiático
Caché SQLite: cada equipo se consulta una vez y se renueva cada 7 días.
Costo adicional de API: ~10-15 requests/día (vs 200+ sin caché).
"""
import os, sqlite3, math
from datetime import datetime, date
from scipy.stats import poisson

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "sharpiq.db")

PROMEDIO_CORNERS_LIGA  = 10.5   # corners totales promedio por partido
PROMEDIO_TARJETAS_LIGA = 3.8    # tarjetas totales promedio por partido


# ── CACHÉ PERSISTENTE EN SQLITE ────────────────────────────────────

def _db():
    return sqlite3.connect(DB_PATH)

def inicializar():
    with _db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS stats_ext_cache (
            equipo           TEXT PRIMARY KEY,
            season           INTEGER,
            corners_favor    REAL,
            corners_contra   REAL,
            tarjetas_favor   REAL,
            tarjetas_contra  REAL,
            disparos_favor   REAL,
            disparos_contra  REAL,
            actualizado      TEXT
        )""")

def _get_cache(equipo):
    with _db() as c:
        row = c.execute(
            "SELECT corners_favor, corners_contra, tarjetas_favor, tarjetas_contra, "
            "disparos_favor, disparos_contra, actualizado FROM stats_ext_cache WHERE equipo=?",
            (equipo,)
        ).fetchone()
    if not row:
        return None
    dias = (datetime.now() - datetime.fromisoformat(row[6])).days
    if dias > 7:
        return None
    return {
        "corners_favor":   row[0], "corners_contra":  row[1],
        "tarjetas_favor":  row[2], "tarjetas_contra": row[3],
        "disparos_favor":  row[4], "disparos_contra": row[5],
    }

def _guardar_cache(equipo, stats):
    season = date.today().year if date.today().month >= 7 else date.today().year - 1
    with _db() as c:
        c.execute("""INSERT OR REPLACE INTO stats_ext_cache
            (equipo, season, corners_favor, corners_contra, tarjetas_favor,
             tarjetas_contra, disparos_favor, disparos_contra, actualizado)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (equipo, season,
             stats["corners_favor"],   stats["corners_contra"],
             stats["tarjetas_favor"],  stats["tarjetas_contra"],
             stats["disparos_favor"],  stats["disparos_contra"],
             datetime.now().isoformat()))


# ── OBTENER STATS DESDE API (1 request por equipo, cacheado 7 días) ──

def obtener_stats_ext(equipo, liga_id):
    """
    Devuelve stats de corners/tarjetas/disparos para un equipo.
    Primero busca en SQLite; solo llama a la API si no hay datos frescos.
    """
    cached = _get_cache(equipo)
    if cached:
        return cached

    try:
        from motor import _apifb, TEAM_IDS, _match_equipos

        # Búsqueda exacta primero, luego fuzzy para nombres que no coinciden exacto
        team_id = TEAM_IDS.get(equipo)
        if not team_id:
            for nombre, tid in TEAM_IDS.items():
                if _match_equipos(equipo, nombre):
                    team_id = tid
                    break
        if not team_id:
            return None

        # Aceptar tanto códigos numéricos (api-sports) como strings (football-data)
        _liga_map = {
            "PL": 39, "PD": 140, "BL1": 78, "SA": 135, "FL1": 61,
            "CL": 2,  "CLI": 13, "CSA": 11,
        }
        try:
            liga_int = int(liga_id)
        except (ValueError, TypeError):
            liga_int = _liga_map.get(str(liga_id))
            if not liga_int:
                return None

        season = date.today().year if date.today().month >= 7 else date.today().year - 1
        data = _apifb("teams/statistics", {
            "team": team_id, "season": season, "league": liga_int
        })
        if not data or not data.get("response"):
            return None

        r    = data["response"]
        pj   = r.get("fixtures", {}).get("played", {}).get("total", 1) or 1

        # ── Corners ──────────────────────────────────────────────
        c_for  = r.get("corners", {}).get("for",     {}).get("total", {})
        c_agt  = r.get("corners", {}).get("against", {}).get("total", {})
        cf = sum(v for v in c_for.values()  if isinstance(v, (int, float))) / pj
        ca = sum(v for v in c_agt.values()  if isinstance(v, (int, float))) / pj

        # ── Tarjetas ─────────────────────────────────────────────
        cards  = r.get("cards", {})
        yf = sum((v.get("total") or 0) for v in cards.get("yellow", {}).values())
        rf = sum((v.get("total") or 0) for v in cards.get("red",    {}).values())
        tf = (yf + rf * 2) / pj   # peso: amarilla=1 pt, roja=2 pts

        # ── Disparos ─────────────────────────────────────────────
        shots  = r.get("shots", {})
        disp_f = (shots.get("total", {}).get("total") or 0) / pj
        disp_c = (shots.get("on",    {}).get("total") or 0) / pj

        stats = {
            "corners_favor":   round(cf,    2),
            "corners_contra":  round(ca,    2),
            "tarjetas_favor":  round(tf,    2),
            "tarjetas_contra": round(tf,    2),   # simétrico como proxy
            "disparos_favor":  round(disp_f, 2),
            "disparos_contra": round(disp_c, 2),
        }
        _guardar_cache(equipo, stats)
        print(f"    Stats ext {equipo[-14:]}: corners {cf:.1f}/{ca:.1f} | tarjetas {tf:.1f}")
        return stats

    except Exception as e:
        print(f"    Stats ext {equipo}: error {e}")
        return None


# ── DEFAULTS POR LIGA (fallback si no hay datos de API) ───────────

DEFAULTS_LIGA = {
    "2":   {"cf": 5.4, "ca": 5.1, "tf": 2.0},   # Champions
    "3":   {"cf": 5.3, "ca": 5.2, "tf": 2.1},   # Europa League
    "39":  {"cf": 5.6, "ca": 5.4, "tf": 1.9},   # Premier
    "140": {"cf": 5.0, "ca": 5.0, "tf": 2.3},   # La Liga
    "78":  {"cf": 5.5, "ca": 5.0, "tf": 2.0},   # Bundesliga
    "135": {"cf": 5.1, "ca": 5.2, "tf": 2.5},   # Serie A
    "61":  {"cf": 5.2, "ca": 5.3, "tf": 2.2},   # Ligue 1
    "13":  {"cf": 4.8, "ca": 5.0, "tf": 2.6},   # Libertadores
    "128": {"cf": 4.5, "ca": 4.8, "tf": 2.8},   # BetPlay Colombia
}
_DEFAULT = {"cf": 5.2, "ca": 5.3, "tf": 2.2}

def _defaults(liga_id):
    d = DEFAULTS_LIGA.get(str(liga_id), _DEFAULT)
    return {
        "corners_favor":   d["cf"], "corners_contra":  d["ca"],
        "tarjetas_favor":  d["tf"], "tarjetas_contra": d["tf"],
        "disparos_favor":  12.0,    "disparos_contra": 4.5,
    }


# ── CÁLCULO DE LAMBDAS ────────────────────────────────────────────

def calcular_corners_esperados(local, visitante, liga_id):
    sl = obtener_stats_ext(local,    liga_id) or _defaults(liga_id)
    sv = obtener_stats_ext(visitante, liga_id) or _defaults(liga_id)

    avg = PROMEDIO_CORNERS_LIGA / 2   # 5.25 por equipo

    cl = (sl["corners_favor"] / avg) * (sv["corners_contra"] / avg) * avg * 1.06
    cv = (sv["corners_favor"] / avg) * (sl["corners_contra"] / avg) * avg

    return round(cl, 2), round(cv, 2)

def calcular_tarjetas_esperadas(local, visitante, liga_id):
    sl = obtener_stats_ext(local,    liga_id) or _defaults(liga_id)
    sv = obtener_stats_ext(visitante, liga_id) or _defaults(liga_id)

    avg = PROMEDIO_TARJETAS_LIGA / 2

    tl = (sl["tarjetas_favor"] / avg) * avg * 1.08   # local recibe más tarjetas
    tv = (sv["tarjetas_favor"] / avg) * avg

    return round(tl, 2), round(tv, 2)


# ── MODELOS POISSON ───────────────────────────────────────────────

def modelo_corners(lambda_local, lambda_visita):
    lam = lambda_local + lambda_visita
    out = {"corners_esperados": round(lam, 1)}
    for lim in [8.5, 9.5, 10.5, 11.5, 12.5]:
        k   = int(lim + 0.5)
        ov  = round((1 - sum(poisson.pmf(i, lam) for i in range(k))) * 100, 1)
        tag = str(k)
        out[f"corners_over{tag}"]  = ov
        out[f"corners_under{tag}"] = round(100 - ov, 1)
    return out

def modelo_tarjetas(lambda_local, lambda_visita):
    lam = lambda_local + lambda_visita
    out = {"tarjetas_esperadas": round(lam, 1)}
    for lim in [2.5, 3.5, 4.5, 5.5]:
        k   = int(lim + 0.5)
        ov  = round((1 - sum(poisson.pmf(i, lam) for i in range(k))) * 100, 1)
        tag = str(k)
        out[f"tarjetas_over{tag}"]  = ov
        out[f"tarjetas_under{tag}"] = round(100 - ov, 1)
    return out

def modelo_handicap_asiatico(probs_poisson):
    """
    Calcula handicap asiático para líneas -0.5, -1, -1.5, -2 del local.
    Usa la matriz de probabilidades del modelo Poisson ya calculado.
    """
    vl  = probs_poisson["victoria_local"]   / 100
    emp = probs_poisson["empate"]           / 100
    vv  = probs_poisson["victoria_visita"]  / 100

    # AH -0.5 local: gana si gana el partido (empate = pierde)
    ah_local_05  = round(vl * 100, 1)
    # AH +0.5 visita: gana si no pierde
    ah_visita_05 = round((emp + vv) * 100, 1)

    # AH -1 local: usar hdc_local_menos1 ya calculado
    ah_local_1   = probs_poisson.get("hdc_local_menos1", round(vl * 0.65 * 100, 1))
    ah_visita_1  = round(100 - ah_local_1, 1)

    # AH -1.5 local (estimado por Poisson)
    # P(local gana por 2+) ≈ hdc_local_menos1 * 0.7
    ah_local_15  = round(ah_local_1 * 0.70, 1)
    ah_visita_15 = round(100 - ah_local_15, 1)

    return {
        "ah_local_menos05":   ah_local_05,
        "ah_visita_mas05":    ah_visita_05,
        "ah_local_menos1":    ah_local_1,
        "ah_visita_mas1":     ah_visita_1,
        "ah_local_menos15":   ah_local_15,
        "ah_visita_mas15":    ah_visita_15,
    }


# ── EV PARA NUEVOS MERCADOS ───────────────────────────────────────

def calcular_ev_mercados_ext(probs_corners, probs_tarjetas, probs_ah, cuotas_ext=None):
    """
    Calcula EV para corners/tarjetas/handicap.
    cuotas_ext: dict con cuotas reales de casa de apuestas (opcional).
    Si no hay cuota real, genera cuota justa para referencia.
    """
    mercados = {}

    # Para cada mercado: (prob_modelo, cuota_real_o_justa)
    def _ev(prob, cuota):
        v = (prob / 100 * cuota) - 1
        return {
            "prob_modelo":    round(prob, 1),
            "cuota_justa":    round(100 / prob, 2) if prob > 0 else None,
            "cuota_ref":      round(cuota, 2),
            "ev_porcentaje":  round(v * 100, 1),
            "tiene_valor":    v > 0.05,
            "clasificacion":  "ALTO VALOR" if v > 0.15 else "VALOR" if v > 0.05 else "SIN VALOR",
        }

    cuotas_ext = cuotas_ext or {}

    # Corners Over/Under 9.5 y 10.5 (los más líquidos)
    for tag, k in [("9",  9), ("10", 10), ("11", 11)]:
        pk_ov = f"corners_over{k}"
        pk_un = f"corners_under{k}"
        if pk_ov in probs_corners:
            prob_ov = probs_corners[pk_ov]
            prob_un = probs_corners[pk_un]
            c_ov = cuotas_ext.get(pk_ov, round(100 / prob_ov * 0.95, 2) if prob_ov > 0 else None)
            c_un = cuotas_ext.get(pk_un, round(100 / prob_un * 0.95, 2) if prob_un > 0 else None)
            if c_ov: mercados[pk_ov] = _ev(prob_ov, c_ov)
            if c_un: mercados[pk_un] = _ev(prob_un, c_un)

    # Tarjetas Over/Under 3.5 y 4.5
    for tag, k in [("3", 3), ("4", 4), ("5", 5)]:
        pk_ov = f"tarjetas_over{k}"
        pk_un = f"tarjetas_under{k}"
        if pk_ov in probs_tarjetas:
            prob_ov = probs_tarjetas[pk_ov]
            prob_un = probs_tarjetas[pk_un]
            c_ov = cuotas_ext.get(pk_ov, round(100 / prob_ov * 0.95, 2) if prob_ov > 0 else None)
            c_un = cuotas_ext.get(pk_un, round(100 / prob_un * 0.95, 2) if prob_un > 0 else None)
            if c_ov: mercados[pk_ov] = _ev(prob_ov, c_ov)
            if c_un: mercados[pk_un] = _ev(prob_un, c_un)

    # Handicap Asiático
    for mk, prob in probs_ah.items():
        c = cuotas_ext.get(mk, round(100 / prob * 0.95, 2) if prob > 0 else None)
        if c: mercados[mk] = _ev(prob, c)

    return mercados


# ── FUNCIÓN PRINCIPAL — analizar partido completo ─────────────────

def analizar_mercados_ext(local, visitante, liga_id, probs_poisson):
    """
    Punto de entrada desde motor.py.
    Devuelve dict con probabilidades y EV de todos los mercados extendidos.
    """
    inicializar()

    cl, cv = calcular_corners_esperados(local, visitante, liga_id)
    tl, tv = calcular_tarjetas_esperadas(local, visitante, liga_id)

    probs_c  = modelo_corners(cl, cv)
    probs_t  = modelo_tarjetas(tl, tv)
    probs_ah = modelo_handicap_asiatico(probs_poisson)

    ev_ext = calcular_ev_mercados_ext(probs_c, probs_t, probs_ah)

    return {
        "corners":  probs_c,
        "tarjetas": probs_t,
        "handicap": probs_ah,
        "ev_ext":   ev_ext,
    }
