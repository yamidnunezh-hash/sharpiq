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
PROMEDIO_SHOTS_LIGA    = 4.2    # disparos al arco por equipo por partido
CONVERSION_RATE        = 0.28   # fracción de disparos al arco que terminan en gol

DEFAULTS_SHOTS_LIGA = {
    "39":  4.8,   # Premier League
    "140": 4.6,   # La Liga
    "78":  5.0,   # Bundesliga
    "135": 4.3,   # Serie A
    "61":  4.4,   # Ligue 1
    "2":   4.5,   # Champions League
    "13":  3.8,   # Copa Libertadores
    "11":  3.7,   # Copa Sudamericana
    "71":  4.0,   # Brasileirao
    "128": 3.6,   # Liga BetPlay
}


# ── CACHÉ PERSISTENTE EN SQLITE ────────────────────────────────────

def _db():
    return sqlite3.connect(DB_PATH)

def inicializar():
    with _db() as c:
        # Migración: el esquema viejo nombraba 'disparos_contra' a los disparos
        # A PUERTA del propio equipo (nombre engañoso: no eran disparos en contra).
        # Si existe el esquema viejo, se descarta — es un caché regenerable (TTL 7d).
        cols = [r[1] for r in c.execute("PRAGMA table_info(stats_ext_cache)").fetchall()]
        if cols and "disparos_contra" in cols:
            c.execute("DROP TABLE stats_ext_cache")
        c.execute("""CREATE TABLE IF NOT EXISTS stats_ext_cache (
            equipo           TEXT PRIMARY KEY,
            season           INTEGER,
            corners_favor    REAL,
            corners_contra   REAL,
            tarjetas_favor   REAL,
            tarjetas_contra  REAL,
            disparos_totales REAL,
            disparos_puerta  REAL,
            actualizado      TEXT
        )""")
        # Tabla separada para datos reales de disparos/paradas por partido
        c.execute("""CREATE TABLE IF NOT EXISTS stats_tiros_cache (
            equipo          TEXT PRIMARY KEY,
            shots_on_target REAL,
            saves           REAL,
            partidos        INTEGER,
            actualizado     TEXT
        )""")

def _get_cache(equipo):
    with _db() as c:
        row = c.execute(
            "SELECT corners_favor, corners_contra, tarjetas_favor, tarjetas_contra, "
            "disparos_totales, disparos_puerta, actualizado FROM stats_ext_cache WHERE equipo=?",
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
        "disparos_totales": row[4], "disparos_puerta": row[5],
    }

def _get_tiros_cache(equipo):
    with _db() as c:
        row = c.execute(
            "SELECT shots_on_target, saves, partidos, actualizado FROM stats_tiros_cache WHERE equipo=?",
            (equipo,)
        ).fetchone()
    if not row:
        return None
    dias = (datetime.now() - datetime.fromisoformat(row[3])).days
    if dias > 3:   # datos frescos cada 3 días
        return None
    return {"shots_on_target": row[0], "saves": row[1], "partidos": row[2]}

def _guardar_tiros_cache(equipo, stats):
    with _db() as c:
        c.execute("""INSERT OR REPLACE INTO stats_tiros_cache
            (equipo, shots_on_target, saves, partidos, actualizado)
            VALUES (?,?,?,?,?)""",
            (equipo, stats["shots_on_target"], stats["saves"],
             stats["partidos"], datetime.now().isoformat()))

def _guardar_cache(equipo, stats):
    season = date.today().year if date.today().month >= 7 else date.today().year - 1
    with _db() as c:
        c.execute("""INSERT OR REPLACE INTO stats_ext_cache
            (equipo, season, corners_favor, corners_contra, tarjetas_favor,
             tarjetas_contra, disparos_totales, disparos_puerta, actualizado)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (equipo, season,
             stats["corners_favor"],   stats["corners_contra"],
             stats["tarjetas_favor"],  stats["tarjetas_contra"],
             stats["disparos_totales"], stats["disparos_puerta"],
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

        # /teams/statistics NO incluye corners en muchos planes → cf/ca quedan en 0.
        # Sin este fallback, calcular_corners_esperados da λ≈0 y el modelo predice
        # Under al 100%. Usar el promedio de la liga cuando no hay dato real.
        if cf <= 0 or ca <= 0:
            d = DEFAULTS_LIGA.get(str(liga_int), _DEFAULT)
            if cf <= 0:
                cf = d["cf"]
            if ca <= 0:
                ca = d["ca"]

        # ── Tarjetas ─────────────────────────────────────────────
        cards  = r.get("cards", {})
        yf = sum((v.get("total") or 0) for v in cards.get("yellow", {}).values())
        rf = sum((v.get("total") or 0) for v in cards.get("red",    {}).values())
        tf = (yf + rf * 2) / pj   # peso: amarilla=1 pt, roja=2 pts

        # ── Disparos (ambos son del PROPIO equipo, no en contra) ──
        shots     = r.get("shots", {})
        disp_tot  = (shots.get("total", {}).get("total") or 0) / pj   # disparos totales
        disp_pta  = (shots.get("on",    {}).get("total") or 0) / pj   # disparos a puerta (SOT)

        stats = {
            "corners_favor":   round(cf,    2),
            "corners_contra":  round(ca,    2),
            "tarjetas_favor":  round(tf,    2),
            "tarjetas_contra": round(tf,    2),   # simétrico como proxy
            "disparos_totales": round(disp_tot, 2),
            "disparos_puerta":  round(disp_pta, 2),
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
        "disparos_totales": 12.0,   "disparos_puerta": 4.5,
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

def obtener_stats_tiros_reales(equipo, liga_id=None, n=5):
    """
    Shots on target y saves reales de los últimos N partidos terminados.

    Plan gratuito api-sports.io: usa season=2024 (soportado) + filtra los N
    más recientes del lado Python. El parámetro 'last' requiere plan de pago.

    Costo API: 1 req /fixtures (toda la temporada) + N req /fixtures/statistics.
    Caché SQLite 3 días → en la práctica muy pocos equipos nuevos por día.

    Campos reales de la API:
      - "Shots on Goal"    → disparos que van entre los tres palos (= shots on target)
      - "Goalkeeper Saves" → paradas del portero en ese partido
    """
    inicializar()
    cached = _get_tiros_cache(equipo)
    if cached:
        return cached

    try:
        from motor import _apifb, TEAM_IDS, _match_equipos
    except Exception:
        return None

    # Resolver team_id
    team_id = TEAM_IDS.get(equipo)
    if not team_id:
        for nombre, tid in TEAM_IDS.items():
            if _match_equipos(equipo, nombre):
                team_id = tid
                break
    if not team_id:
        return None

    # Resolver liga_id numérico para la query (usar 2024 = último season accesible
    # en plan gratuito; si tienen plan de pago se puede cambiar a 2025)
    _liga_map = {
        "PL": 39, "PD": 140, "BL1": 78, "SA": 135, "FL1": 61,
        "CL": 2,  "CLI": 13, "CSA": 11, "39": 39, "140": 140,
        "78": 78, "135": 135, "61": 61, "13": 13, "11": 11,
        "71": 71, "128": 128, "253": 253,
    }
    liga_int = None
    if liga_id:
        try:
            liga_int = int(liga_id)
        except (ValueError, TypeError):
            liga_int = _liga_map.get(str(liga_id))

    # Temporada: preferir la más reciente accesible
    season = date.today().year if date.today().month >= 7 else date.today().year - 1
    # Plan free solo soporta hasta 2024; si falla, bajamos un año
    params_fix = {"team": team_id, "season": season, "status": "FT"}
    if liga_int:
        params_fix["league"] = liga_int

    data = _apifb("fixtures", params_fix)
    # Si falla por restricción de season, intentar con 2024
    if not data or not data.get("response"):
        params_fix["season"] = season - 1
        data = _apifb("fixtures", params_fix)
    if not data or not data.get("response"):
        return None

    # Ordenar por fecha descendente y tomar los N más recientes
    fixtures = sorted(
        data["response"],
        key=lambda f: f["fixture"].get("date", ""),
        reverse=True
    )[:n]

    total_shots = 0
    total_saves = 0
    conteo = 0

    for f in fixtures:
        fixture_id = f["fixture"]["id"]
        stats_data = _apifb("fixtures/statistics", {"fixture": fixture_id})
        if not stats_data or not stats_data.get("response"):
            continue

        for team_stats in stats_data["response"]:
            if team_stats.get("team", {}).get("id") != team_id:
                continue
            shots_ot = 0
            saves    = 0
            for stat in team_stats.get("statistics", []):
                tipo  = stat.get("type", "")
                valor = stat.get("value")
                # La API usa "Shots on Goal" (= disparos entre los tres palos)
                if tipo in ("Shots on Goal", "Shots on Target"):
                    try:
                        shots_ot = int(valor) if valor is not None else 0
                    except (ValueError, TypeError):
                        shots_ot = 0
                elif tipo == "Goalkeeper Saves":
                    try:
                        saves = int(valor) if valor is not None else 0
                    except (ValueError, TypeError):
                        saves = 0
            total_shots += shots_ot
            total_saves += saves
            conteo += 1
            break

    if conteo == 0:
        return None

    result = {
        "shots_on_target": round(total_shots / conteo, 2),
        "saves":           round(total_saves / conteo, 2),
        "partidos":        conteo,
    }
    _guardar_tiros_cache(equipo, result)
    print(f"    Tiros reales {equipo[-16:]}: SoT={result['shots_on_target']}/p "
          f"| Saves={result['saves']}/p ({conteo}p)")
    return result


def calcular_disparos_visitante_esperados(local, visitante, liga_id):
    """
    λ de disparos al arco del equipo visitante.
    Prioridad: datos reales últimos 5 partidos → promedio de temporada → default de liga.
    Factor visitante: ×0.85 (el equipo genera menos oportunidades fuera de casa).
    """
    avg = DEFAULTS_SHOTS_LIGA.get(str(liga_id), PROMEDIO_SHOTS_LIGA)

    # Datos reales (últimos 5 partidos)
    stats_vis = obtener_stats_tiros_reales(visitante, liga_id=liga_id)
    if stats_vis and stats_vis["partidos"] >= 3:
        lambda_shots = round(stats_vis["shots_on_target"] * 0.85, 2)
        print(f"    Disparos vis REAL ({visitante[-14:]}): "
              f"{stats_vis['shots_on_target']:.1f}/p → λ={lambda_shots}")
        return lambda_shots

    # Fallback: promedio de temporada ya en cache
    sv = obtener_stats_ext(visitante, liga_id) or _defaults(liga_id)
    shots_vis = sv.get("disparos_puerta") or avg
    if shots_vis < 0.5:
        shots_vis = avg
    return round(shots_vis * 0.85, 2)


def calcular_paradas_esperadas(lambda_shots_vis, goles_visita_esperados, local=None):
    """
    λ de paradas del portero local.
    Prioridad: saves reales del portero local (últimos 5 partidos) →
               estimado = disparos al arco visitante − goles esperados visitante.
    """
    if local:
        stats_local = obtener_stats_tiros_reales(local, liga_id=None)
        if stats_local and stats_local["partidos"] >= 3:
            lambda_paradas = round(max(stats_local["saves"], 0.5), 2)
            print(f"    Paradas GK REAL ({local[-14:]}): {lambda_paradas:.2f}/p")
            return lambda_paradas

    # Fallback: estimado
    paradas = lambda_shots_vis - goles_visita_esperados
    return round(max(paradas, 0.5), 2)


def modelo_disparos_al_arco(lambda_shots):
    """Distribución Poisson para remates al arco del equipo visitante."""
    out = {"disparos_esperados": round(lambda_shots, 1)}
    for k in [2, 3, 4, 5]:
        ov = round((1 - sum(poisson.pmf(i, lambda_shots) for i in range(k))) * 100, 1)
        out[f"disp_vis_over{k}"]  = ov
        out[f"disp_vis_under{k}"] = round(100 - ov, 1)
    return out


def modelo_paradas_portero(lambda_paradas):
    """Distribución Poisson para paradas del portero local."""
    out = {"paradas_esperadas": round(lambda_paradas, 1)}
    for k in [2, 3, 4]:
        ov = round((1 - sum(poisson.pmf(i, lambda_paradas) for i in range(k))) * 100, 1)
        out[f"paradas_local_over{k}"]  = ov
        out[f"paradas_local_under{k}"] = round(100 - ov, 1)
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

def calcular_ev_mercados_ext(probs_corners, probs_tarjetas, probs_ah,
                             probs_disparos=None, probs_paradas=None, cuotas_ext=None):
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

    # Remates al arco del visitante (Over/Under 2.5 – 5.5)
    if probs_disparos:
        for k in [2, 3, 4, 5]:
            for sufijo in ("over", "under"):
                pk = f"disp_vis_{sufijo}{k}"
                prob = probs_disparos.get(pk)
                if prob and prob > 0:
                    c = cuotas_ext.get(pk, round(100 / prob * 0.95, 2))
                    mercados[pk] = _ev(prob, c)

    # Paradas del portero local (Over/Under 2.5 – 4.5)
    if probs_paradas:
        for k in [2, 3, 4]:
            for sufijo in ("over", "under"):
                pk = f"paradas_local_{sufijo}{k}"
                prob = probs_paradas.get(pk)
                if prob and prob > 0:
                    c = cuotas_ext.get(pk, round(100 / prob * 0.95, 2))
                    mercados[pk] = _ev(prob, c)

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

    lambda_disp_vis = calcular_disparos_visitante_esperados(local, visitante, liga_id)
    goles_visita    = probs_poisson.get("goles_esperados_visita", 1.1)
    lambda_paradas  = calcular_paradas_esperadas(lambda_disp_vis, goles_visita, local=local)

    probs_c    = modelo_corners(cl, cv)
    probs_t    = modelo_tarjetas(tl, tv)
    probs_ah   = modelo_handicap_asiatico(probs_poisson)
    probs_disp = modelo_disparos_al_arco(lambda_disp_vis)
    probs_par  = modelo_paradas_portero(lambda_paradas)

    print(f"    Disparos vis: λ={lambda_disp_vis} | Paradas GK: λ={lambda_paradas}")

    ev_ext = calcular_ev_mercados_ext(probs_c, probs_t, probs_ah, probs_disp, probs_par)

    return {
        "corners":   probs_c,
        "tarjetas":  probs_t,
        "handicap":  probs_ah,
        "disparos":  probs_disp,
        "paradas":   probs_par,
        "ev_ext":    ev_ext,
    }
