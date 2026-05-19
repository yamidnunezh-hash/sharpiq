"""
SharpIQ — Motor de Predicciones
Modelo: Poisson + Dixon-Coles + Value Betting
"""
import requests
import json
import math
import os
from datetime import datetime, date
from scipy.stats import poisson
from scipy.optimize import minimize
import numpy as np

# Ruta siempre correcta sin importar desde donde se ejecute
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, "..", "predicciones.json")

# ── CONFIGURACIÓN ──────────────────────────────────────────────
from config import FOOTBALL_DATA_KEY as API_KEY, ODDS_API_KEY
API_URL = "https://api.football-data.org/v4"
ODDS_API_URL = "https://api.the-odds-api.com/v4"

# Mapeo ligas football-data.org → the-odds-api.com
LIGAS_ODDS = {
    "PL":  "soccer_epl",
    "PD":  "soccer_spain_la_liga",
    "BL1": "soccer_germany_bundesliga",
    "SA":  "soccer_italy_serie_a",
    "FL1": "soccer_france_ligue_one",
    "CL":  "soccer_uefa_champs_league",
}

# Casas de apuestas preferidas (europeas, disponibles en Colombia)
BOOKMAKERS = ["bet365", "betway", "unibet", "williamhill", "marathonbet"]

LIGAS = {
    "PL":  "Premier League",
    "PD":  "La Liga",
    "BL1": "Bundesliga",
    "SA":  "Serie A",
    "FL1": "Ligue 1",
    "CL":  "Champions League",
    "WC":  "Mundial",
}

# ── OBTENER PARTIDOS DEL DÍA ────────────────────────────────────
def obtener_partidos_liga(codigo_liga, fecha):
    headers = {"X-Auth-Token": API_KEY}
    url = f"{API_URL}/competitions/{codigo_liga}/matches?dateFrom={fecha}&dateTo={fecha}&status=SCHEDULED"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        partidos = []
        for m in data.get("matches", []):
            partidos.append({
                "id": m["id"],
                "liga": m["competition"]["name"],
                "liga_code": m["competition"]["code"],
                "local": m["homeTeam"]["name"],
                "visitante": m["awayTeam"]["name"],
                "hora": m["utcDate"][11:16],
                "estado": m["status"],
            })
        return partidos
    except Exception:
        return []

# ── STATS REALES DESDE STANDINGS ───────────────────────────────
_cache_stats = {}

def cargar_stats_liga(codigo_liga):
    if codigo_liga in _cache_stats:
        return
    headers = {"X-Auth-Token": API_KEY}
    try:
        r = requests.get(f"{API_URL}/competitions/{codigo_liga}/standings",
                         headers=headers, timeout=15)
        if r.status_code != 200:
            return
        data = r.json()
        tabla = data.get("standings", [{}])[0].get("table", [])
        for eq in tabla:
            if eq.get("playedGames", 0) == 0:
                continue
            nombre = eq["team"]["name"]
            pj = eq["playedGames"]
            ataque = round(eq["goalsFor"] / pj, 3)
            defensa = round(eq["goalsAgainst"] / pj, 3)
            pts_pct = eq["points"] / (pj * 3)
            forma = round(0.5 + pts_pct * 0.5, 3)  # escala 0.5-1.0
            _cache_stats[nombre] = {"ataque": ataque, "defensa": defensa, "forma": forma}
        print(f"  Stats reales cargadas: {codigo_liga} ({len(tabla)} equipos)")
    except Exception:
        pass

def cargar_todas_las_stats():
    for codigo in ["PL", "PD", "BL1", "SA", "FL1"]:
        cargar_stats_liga(codigo)

def get_stats_equipo(nombre):
    if nombre in _cache_stats:
        return _cache_stats[nombre]
    if nombre in STATS_EQUIPOS:
        return STATS_EQUIPOS[nombre]
    return {"ataque": 1.35, "defensa": 1.35, "forma": 0.75}

def obtener_partidos_hoy():
    hoy = date.today().isoformat()
    todos = []
    for codigo in LIGAS.keys():
        partidos = obtener_partidos_liga(codigo, hoy)
        todos.extend(partidos)
        if partidos:
            print(f"  {LIGAS[codigo]}: {len(partidos)} partidos")
    if not todos:
        print("  Sin partidos hoy, usando datos demo")
        return partidos_demo()
    return todos

def obtener_partidos_fecha(fecha_iso):
    todos = []
    for codigo in LIGAS.keys():
        partidos = obtener_partidos_liga(codigo, fecha_iso)
        todos.extend(partidos)
    return todos

# ── DATOS DEMO (cuando no hay API key) ─────────────────────────
def partidos_demo():
    return [
        {"id": 1, "liga": "Premier League", "liga_code": "PL",
         "local": "Manchester City", "visitante": "Arsenal",
         "hora": "20:45", "estado": "SCHEDULED"},
        {"id": 2, "liga": "La Liga", "liga_code": "PD",
         "local": "Real Madrid", "visitante": "Barcelona",
         "hora": "21:00", "estado": "SCHEDULED"},
        {"id": 3, "liga": "Champions League", "liga_code": "CL",
         "local": "Bayern Munich", "visitante": "PSG",
         "hora": "21:00", "estado": "SCHEDULED"},
        {"id": 4, "liga": "Serie A", "liga_code": "SA",
         "local": "Inter Milan", "visitante": "Juventus",
         "hora": "20:45", "estado": "SCHEDULED"},
    ]

# ── MODELO POISSON ──────────────────────────────────────────────
def modelo_poisson(goles_local_esperados, goles_visita_esperados):
    """
    Calcula probabilidades de resultado usando distribución Poisson.
    Retorna: {victoria_local, empate, victoria_visita, over25, under25, btts}
    """
    max_goles = 8

    prob_local = [poisson.pmf(i, goles_local_esperados) for i in range(max_goles)]
    prob_visita = [poisson.pmf(i, goles_visita_esperados) for i in range(max_goles)]

    victoria_local = 0
    empate = 0
    victoria_visita = 0
    over25 = 0
    btts = 0

    for i in range(max_goles):
        for j in range(max_goles):
            p = prob_local[i] * prob_visita[j]
            if i > j:
                victoria_local += p
            elif i == j:
                empate += p
            else:
                victoria_visita += p
            if (i + j) > 2.5:
                over25 += p
            if i > 0 and j > 0:
                btts += p

    return {
        "victoria_local": round(victoria_local * 100, 1),
        "empate": round(empate * 100, 1),
        "victoria_visita": round(victoria_visita * 100, 1),
        "over25": round(over25 * 100, 1),
        "under25": round((1 - over25) * 100, 1),
        "btts_si": round(btts * 100, 1),
        "btts_no": round((1 - btts) * 100, 1),
        "goles_esperados_local": round(goles_local_esperados, 2),
        "goles_esperados_visita": round(goles_visita_esperados, 2),
        "total_goles_esperados": round(goles_local_esperados + goles_visita_esperados, 2),
    }

# ── ESTADÍSTICAS DE EQUIPOS ────────────────────────────────────
# ataque: goles/partido promedio | defensa: goles recibidos/partido | forma: 0-1
STATS_EQUIPOS = {
    # Premier League 2025/26
    "Manchester City FC":        {"ataque": 2.1, "defensa": 0.9, "forma": 0.78},
    "Arsenal FC":                {"ataque": 1.9, "defensa": 0.8, "forma": 0.80},
    "Liverpool FC":              {"ataque": 2.2, "defensa": 0.7, "forma": 0.88},
    "Chelsea FC":                {"ataque": 1.8, "defensa": 1.0, "forma": 0.76},
    "Tottenham Hotspur FC":      {"ataque": 1.7, "defensa": 1.1, "forma": 0.72},
    "Newcastle United FC":       {"ataque": 1.6, "defensa": 1.0, "forma": 0.74},
    "Aston Villa FC":            {"ataque": 1.7, "defensa": 1.1, "forma": 0.73},
    "Brighton & Hove Albion FC": {"ataque": 1.5, "defensa": 1.2, "forma": 0.70},
    "Manchester United FC":      {"ataque": 1.4, "defensa": 1.3, "forma": 0.65},
    "West Ham United FC":        {"ataque": 1.4, "defensa": 1.3, "forma": 0.64},
    "Fulham FC":                 {"ataque": 1.3, "defensa": 1.2, "forma": 0.67},
    "Brentford FC":              {"ataque": 1.3, "defensa": 1.3, "forma": 0.65},
    "Wolverhampton Wanderers FC":{"ataque": 1.2, "defensa": 1.4, "forma": 0.60},
    "Crystal Palace FC":         {"ataque": 1.2, "defensa": 1.3, "forma": 0.62},
    "Everton FC":                {"ataque": 1.1, "defensa": 1.4, "forma": 0.58},
    "Nottingham Forest FC":      {"ataque": 1.4, "defensa": 1.1, "forma": 0.70},
    "AFC Bournemouth":           {"ataque": 1.5, "defensa": 1.2, "forma": 0.68},
    "Sunderland AFC":            {"ataque": 1.2, "defensa": 1.3, "forma": 0.63},
    "Ipswich Town FC":           {"ataque": 1.0, "defensa": 1.5, "forma": 0.55},
    "Leicester City FC":         {"ataque": 1.1, "defensa": 1.5, "forma": 0.52},
    # La Liga 2025/26
    "Real Madrid CF":            {"ataque": 2.0, "defensa": 0.7, "forma": 0.88},
    "FC Barcelona":              {"ataque": 2.2, "defensa": 0.8, "forma": 0.85},
    "Club Atletico de Madrid":   {"ataque": 1.7, "defensa": 0.7, "forma": 0.82},
    "Athletic Club":             {"ataque": 1.5, "defensa": 1.0, "forma": 0.72},
    "Villarreal CF":             {"ataque": 1.4, "defensa": 1.1, "forma": 0.70},
    "Real Sociedad de Futbol":   {"ataque": 1.4, "defensa": 1.1, "forma": 0.70},
    "Real Betis Balompie":       {"ataque": 1.3, "defensa": 1.2, "forma": 0.68},
    "Sevilla FC":                {"ataque": 1.3, "defensa": 1.2, "forma": 0.66},
    # Bundesliga 2025/26
    "FC Bayern Munchen":         {"ataque": 2.3, "defensa": 0.9, "forma": 0.82},
    "Borussia Dortmund":         {"ataque": 1.9, "defensa": 1.1, "forma": 0.76},
    "Bayer 04 Leverkusen":       {"ataque": 2.0, "defensa": 0.8, "forma": 0.84},
    "RB Leipzig":                {"ataque": 1.8, "defensa": 0.9, "forma": 0.78},
    "Eintracht Frankfurt":       {"ataque": 1.5, "defensa": 1.1, "forma": 0.72},
    "VfB Stuttgart":             {"ataque": 1.6, "defensa": 1.0, "forma": 0.74},
    # Serie A 2025/26
    "FC Internazionale Milano":  {"ataque": 1.8, "defensa": 0.8, "forma": 0.83},
    "Juventus FC":               {"ataque": 1.5, "defensa": 0.9, "forma": 0.72},
    "SSC Napoli":                {"ataque": 1.8, "defensa": 0.9, "forma": 0.80},
    "AC Milan":                  {"ataque": 1.7, "defensa": 1.0, "forma": 0.76},
    "AS Roma":                   {"ataque": 1.5, "defensa": 1.1, "forma": 0.70},
    "SS Lazio":                  {"ataque": 1.5, "defensa": 1.1, "forma": 0.70},
    "Atalanta BC":               {"ataque": 2.0, "defensa": 0.9, "forma": 0.82},
    # Ligue 1 2025/26
    "Paris Saint-Germain FC":    {"ataque": 2.2, "defensa": 0.8, "forma": 0.86},
    "Olympique de Marseille":    {"ataque": 1.6, "defensa": 1.1, "forma": 0.74},
    "AS Monaco FC":              {"ataque": 1.7, "defensa": 1.0, "forma": 0.76},
    "Lille OSC":                 {"ataque": 1.5, "defensa": 1.0, "forma": 0.74},
    "OGC Nice":                  {"ataque": 1.4, "defensa": 1.1, "forma": 0.70},
    # Champions League (nombres cortos como referencia)
    "Manchester City":           {"ataque": 2.1, "defensa": 0.9, "forma": 0.78},
    "Arsenal":                   {"ataque": 1.9, "defensa": 0.8, "forma": 0.80},
    "Real Madrid":               {"ataque": 2.0, "defensa": 0.7, "forma": 0.88},
    "Barcelona":                 {"ataque": 2.2, "defensa": 0.8, "forma": 0.85},
    "Bayern Munich":             {"ataque": 2.3, "defensa": 0.9, "forma": 0.82},
    "PSG":                       {"ataque": 2.2, "defensa": 0.8, "forma": 0.86},
    "Inter Milan":               {"ataque": 1.8, "defensa": 0.8, "forma": 0.83},
    "Juventus":                  {"ataque": 1.5, "defensa": 0.9, "forma": 0.72},
}

PROMEDIO_LIGA = {"ataque": 1.35, "defensa": 1.35}

def calcular_goles_esperados(local, visitante):
    stats_l = get_stats_equipo(local)
    stats_v = get_stats_equipo(visitante)

    ventaja_local = 1.25  # factor ventaja de local

    goles_local = (stats_l["ataque"] / PROMEDIO_LIGA["ataque"]) * \
                  (stats_v["defensa"] / PROMEDIO_LIGA["defensa"]) * \
                  PROMEDIO_LIGA["ataque"] * ventaja_local * stats_l["forma"]

    goles_visita = (stats_v["ataque"] / PROMEDIO_LIGA["ataque"]) * \
                   (stats_l["defensa"] / PROMEDIO_LIGA["defensa"]) * \
                   PROMEDIO_LIGA["ataque"] * stats_v["forma"]

    return goles_local, goles_visita

# ── CUOTAS REALES (The Odds API) ────────────────────────────────
_cache_cuotas = {}  # cache para no gastar créditos

def obtener_cuotas_liga(sport_key):
    if sport_key in _cache_cuotas:
        return _cache_cuotas[sport_key]
    try:
        url = f"{ODDS_API_URL}/sports/{sport_key}/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal",
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        _cache_cuotas[sport_key] = data
        restantes = r.headers.get("x-requests-remaining", "?")
        print(f"  Odds API: {len(data)} partidos | Creditos restantes: {restantes}")
        return data
    except Exception as e:
        print(f"  Error Odds API: {e}")
        return []

def buscar_cuotas_partido(local, visitante, sport_key):
    partidos = obtener_cuotas_liga(sport_key)
    local_norm = local.lower().replace(" fc", "").replace(" cf", "").strip()
    visita_norm = visitante.lower().replace(" fc", "").replace(" cf", "").strip()

    for p in partidos:
        h = p.get("home_team", "").lower().replace(" fc", "").replace(" cf", "").strip()
        a = p.get("away_team", "").lower().replace(" fc", "").replace(" cf", "").strip()
        if (local_norm in h or h in local_norm) and (visita_norm in a or a in visita_norm):
            return extraer_mejor_cuota(p)
    return None

def extraer_mejor_cuota(partido):
    mejor = {"1": None, "X": None, "2": None, "casa": None}
    home = partido.get("home_team", "")
    away = partido.get("away_team", "")

    for bm in partido.get("bookmakers", []):
        for market in bm.get("markets", []):
            if market.get("key") != "h2h":
                continue
            outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
            c1 = outcomes.get(home)
            c2 = outcomes.get(away)
            draw_keys = [k for k in outcomes if k not in [home, away]]
            cx = outcomes.get(draw_keys[0]) if draw_keys else None

            if c1 and (mejor["1"] is None or c1 > mejor["1"]):
                mejor["1"] = round(c1, 2)
                mejor["casa"] = bm.get("title", "")
            if cx and (mejor["X"] is None or cx > mejor["X"]):
                mejor["X"] = round(cx, 2)
            if c2 and (mejor["2"] is None or c2 > mejor["2"]):
                mejor["2"] = round(c2, 2)
    return mejor if mejor["1"] else None

# ── VALUE BETTING ───────────────────────────────────────────────
def calcular_value_bet(prob_modelo, cuota_casa):
    """
    Value = (Probabilidad_modelo * Cuota) - 1
    Si Value > 0 → apuesta con valor positivo
    """
    prob_decimal = prob_modelo / 100
    value = (prob_decimal * cuota_casa) - 1
    ev_porcentaje = round(value * 100, 1)
    tiene_valor = bool(value > 0.05)  # mínimo 5% de valor
    return {
        "value": float(round(value, 3)),
        "ev_porcentaje": float(ev_porcentaje),
        "tiene_valor": tiene_valor,
        "clasificacion": "ALTO VALOR" if value > 0.15 else "VALOR" if value > 0.05 else "SIN VALOR"
    }

# ── KELLY CRITERION ─────────────────────────────────────────────
def kelly_criterion(prob_modelo, cuota_casa, bankroll=1000, fraccion=0.25):
    """
    Calcula el stake óptimo según Kelly.
    fraccion=0.25 → Kelly fraccionado (más seguro)
    """
    p = prob_modelo / 100
    q = 1 - p
    b = cuota_casa - 1

    kelly = (b * p - q) / b
    kelly_fraccional = kelly * fraccion

    if kelly_fraccional <= 0:
        return {"stake_porcentaje": 0, "stake_dinero": 0, "recomendacion": "NO APOSTAR"}

    stake_porcentaje = round(kelly_fraccional * 100, 1)
    stake_dinero = round(bankroll * kelly_fraccional, 2)

    return {
        "stake_porcentaje": stake_porcentaje,
        "stake_dinero": stake_dinero,
        "recomendacion": f"Apostar {stake_porcentaje}% del bankroll"
    }

# ── PREDICCIÓN COMPLETA ─────────────────────────────────────────
def predecir_partido(local, visitante, cuotas=None):
    goles_local, goles_visita = calcular_goles_esperados(local, visitante)
    probs = modelo_poisson(goles_local, goles_visita)

    # Cuotas por defecto si no se pasan
    if not cuotas:
        cuotas = {
            "1": round(1 / (probs["victoria_local"] / 100) * 0.9, 2),
            "X": round(1 / (probs["empate"] / 100) * 0.9, 2),
            "2": round(1 / (probs["victoria_visita"] / 100) * 0.9, 2),
        }

    # Value bets
    value_local = calcular_value_bet(probs["victoria_local"], cuotas.get("1", 2.0))
    value_empate = calcular_value_bet(probs["empate"], cuotas.get("X", 3.2))
    value_visita = calcular_value_bet(probs["victoria_visita"], cuotas.get("2", 3.5))

    # Kelly
    kelly_local = kelly_criterion(probs["victoria_local"], cuotas.get("1", 2.0))

    # Predicción principal
    max_prob = max(probs["victoria_local"], probs["empate"], probs["victoria_visita"])
    if max_prob == probs["victoria_local"]:
        prediccion_principal = {"mercado": "Victoria Local (1)", "prob": probs["victoria_local"]}
    elif max_prob == probs["empate"]:
        prediccion_principal = {"mercado": "Empate (X)", "prob": probs["empate"]}
    else:
        prediccion_principal = {"mercado": "Victoria Visitante (2)", "prob": probs["victoria_visita"]}

    return {
        "local": local,
        "visitante": visitante,
        "probabilidades": probs,
        "cuotas": cuotas,
        "value_bets": {
            "victoria_local": value_local,
            "empate": value_empate,
            "victoria_visita": value_visita,
        },
        "kelly": kelly_local,
        "prediccion_principal": prediccion_principal,
        "confianza": round(max_prob, 1),
    }

# ── GENERAR REPORTE DEL DÍA ─────────────────────────────────────
def reporte_del_dia():
    partidos = obtener_partidos_hoy()
    predicciones = []

    # Cargar stats reales de las ligas
    print("\nCargando stats reales de equipos...")
    cargar_todas_las_stats()

    # Precargar cuotas por liga (una sola llamada por liga = ahorra creditos)
    print("\nObteniendo cuotas reales...")
    cuotas_por_liga = {}
    for codigo, sport_key in LIGAS_ODDS.items():
        cuotas_por_liga[codigo] = obtener_cuotas_liga(sport_key)

    for p in partidos:
        # Buscar cuotas reales para este partido
        sport_key = LIGAS_ODDS.get(p["liga_code"])
        cuotas_reales = None
        if sport_key:
            cuotas_reales = buscar_cuotas_partido(p["local"], p["visitante"], sport_key)

        pred = predecir_partido(p["local"], p["visitante"], cuotas=cuotas_reales)
        pred["liga"] = p["liga"]
        pred["hora"] = p["hora"]
        pred["id"] = p["id"]
        pred["cuotas_reales"] = bool(cuotas_reales)
        predicciones.append(pred)

    # Ordenar: primero value bets, luego por confianza
    predicciones.sort(key=lambda x: (
        any(v["tiene_valor"] for v in x["value_bets"].values()),
        x["confianza"]
    ), reverse=True)

    return {
        "fecha": date.today().isoformat(),
        "total_partidos": len(predicciones),
        "predicciones": predicciones,
        "generado": datetime.now().strftime("%H:%M:%S")
    }

# ── GUARDAR JSON PARA EL PANEL ──────────────────────────────────
def guardar_predicciones():
    reporte = reporte_del_dia()
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)
    print(f"✅ Predicciones guardadas: {reporte['total_partidos']} partidos")
    print(f"📅 Fecha: {reporte['fecha']}")
    return reporte

if __name__ == "__main__":
    print("🔮 SharpIQ — Motor de Predicciones")
    print("=" * 50)
    reporte = guardar_predicciones()

    print("\n📊 PREDICCIONES DEL DÍA:")
    for pred in reporte["predicciones"]:
        print(f"\n⚽ {pred['liga']} | {pred['hora']}")
        print(f"   {pred['local']} vs {pred['visitante']}")
        print(f"   1: {pred['probabilidades']['victoria_local']}% | X: {pred['probabilidades']['empate']}% | 2: {pred['probabilidades']['victoria_visita']}%")
        print(f"   Over 2.5: {pred['probabilidades']['over25']}% | BTTS: {pred['probabilidades']['btts_si']}%")
        print(f"   → {pred['prediccion_principal']['mercado']} ({pred['confianza']}% confianza)")

        # Mostrar value bets
        for mercado, vb in pred["value_bets"].items():
            if vb["tiene_valor"]:
                print(f"   💰 VALUE BET: {mercado} → EV: +{vb['ev_porcentaje']}% [{vb['clasificacion']}]")
