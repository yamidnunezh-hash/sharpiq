"""
SharpIQ — Motor de Predicciones
Modelo: Poisson + Dixon-Coles + Value Betting
"""
import requests
import json
import math
import os
import sys
import csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, date
from scipy.stats import poisson
from scipy.optimize import minimize
import numpy as np

try:
    from telegram_alertas import enviar_alerta_value_bet, enviar_resumen_dia
    TELEGRAM_OK = True
except Exception:
    TELEGRAM_OK = False

# Ruta siempre correcta sin importar desde donde se ejecute
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH       = os.path.join(BASE_DIR, "..", "predicciones.json")
MEJOR_PATH      = os.path.join(BASE_DIR, "..", "mejor_prediccion.json")
HISTORIAL_PATH  = os.path.join(BASE_DIR, "historial_cuotas.csv")

# Dixon-Coles: correlación negativa entre goles local/visita en marcadores bajos
RHO = -0.10

# ── CONFIGURACIÓN ──────────────────────────────────────────────
from config import FOOTBALL_DATA_KEY as API_KEY, ODDS_API_KEY
try:
    from config import APIFOOTBALL_KEY
except ImportError:
    APIFOOTBALL_KEY = None

API_URL       = "https://api.football-data.org/v4"
ODDS_API_URL  = "https://api.the-odds-api.com/v4"
APIFB_URL     = "https://v3.football.api-sports.io"

# ── TEAM IDs para api-football ──────────────────────────────────
TEAM_IDS = {
    # Premier League
    "Manchester City FC": 50,      "Manchester City": 50,
    "Arsenal FC": 42,              "Arsenal": 42,
    "Liverpool FC": 40,            "Liverpool": 40,
    "Chelsea FC": 49,              "Chelsea": 49,
    "Tottenham Hotspur FC": 47,    "Tottenham": 47,
    "Newcastle United FC": 34,     "Newcastle": 34,
    "Aston Villa FC": 66,          "Aston Villa": 66,
    "Manchester United FC": 33,    "Manchester United": 33,
    "Brighton & Hove Albion FC": 51,"Brighton": 51,
    "West Ham United FC": 48,      "West Ham": 48,
    "Fulham FC": 36,               "Fulham": 36,
    "Brentford FC": 55,            "Brentford": 55,
    "Crystal Palace FC": 52,       "Crystal Palace": 52,
    "Everton FC": 45,              "Everton": 45,
    "Nottingham Forest FC": 65,    "Nottingham Forest": 65,
    "AFC Bournemouth": 35,         "Bournemouth": 35,
    "Wolverhampton Wanderers FC": 39, "Wolves": 39,
    "Leicester City FC": 46,       "Leicester": 46,
    "Ipswich Town FC": 57,         "Ipswich": 57,
    "Sunderland AFC": 64,          "Sunderland": 64,
    # La Liga
    "Real Madrid CF": 541,         "Real Madrid": 541,
    "FC Barcelona": 529,           "Barcelona": 529,
    "Club Atletico de Madrid": 530,"Atletico Madrid": 530,
    "Athletic Club": 532,
    "Villarreal CF": 533,          "Villarreal": 533,
    "Real Sociedad de Futbol": 548,"Real Sociedad": 548,
    "Real Betis Balompie": 543,    "Real Betis": 543,
    "Sevilla FC": 536,             "Sevilla": 536,
    # Bundesliga
    "FC Bayern Munchen": 157,      "Bayern Munich": 157,
    "Borussia Dortmund": 165,      "Dortmund": 165,
    "Bayer 04 Leverkusen": 168,    "Leverkusen": 168,
    "RB Leipzig": 173,             "Leipzig": 173,
    "Eintracht Frankfurt": 169,    "Frankfurt": 169,
    "VfB Stuttgart": 172,          "Stuttgart": 172,
    # Serie A
    "FC Internazionale Milano": 505,"Inter Milan": 505,
    "Juventus FC": 496,            "Juventus": 496,
    "SSC Napoli": 492,             "Napoli": 492,
    "AC Milan": 489,               "Milan": 489,
    "AS Roma": 497,                "Roma": 497,
    "SS Lazio": 487,               "Lazio": 487,
    "Atalanta BC": 499,            "Atalanta": 499,
    # Ligue 1
    "Paris Saint-Germain FC": 85,  "PSG": 85,
    "Olympique de Marseille": 81,  "Marseille": 81,
    "AS Monaco FC": 91,            "Monaco": 91,
    "Lille OSC": 79,               "Lille": 79,
    "OGC Nice": 84,                "Nice": 84,
}

# Mapeo ligas football-data.org → the-odds-api.com
LIGAS_ODDS = {
    "PL":  "soccer_epl",
    "PD":  "soccer_spain_la_liga",
    "BL1": "soccer_germany_bundesliga",
    "SA":  "soccer_italy_serie_a",
    "FL1": "soccer_france_ligue_one",
    "CL":  "soccer_uefa_champs_league",
    "CLI": "soccer_conmebol_copa_libertadores",
    "CSA": "soccer_conmebol_copa_sudamericana",
    # api-sports IDs → the-odds-api
    "39":  "soccer_epl",
    "140": "soccer_spain_la_liga",
    "78":  "soccer_germany_bundesliga",
    "135": "soccer_italy_serie_a",
    "61":  "soccer_france_ligue_one",
    "2":   "soccer_uefa_champs_league",
    "3":   "soccer_uefa_europa_league",
    "13":  "soccer_conmebol_copa_libertadores",
    "11":  "soccer_conmebol_copa_sudamericana",
    "1":   "soccer_fifa_world_cup",
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
    "CLI": "Copa Libertadores",
    "CSA": "Copa Sudamericana",
    "WC":  "Mundial",
}

# Liga IDs de api-sports.io que el motor analiza
LIGAS_APIFB = {
    1:    "Mundial FIFA 2026",
    2:    "Champions League",
    3:    "Europa League",
    39:   "Premier League",
    61:   "Ligue 1",
    71:   "Brasileirao Serie A",
    78:   "Bundesliga",
    11:   "Copa Sudamericana",
    13:   "Copa Libertadores",
    128:  "Liga BetPlay",
    135:  "Serie A",
    140:  "La Liga",
    241:  "Copa Colombia",
    253:  "MLS",
    262:  "Liga MX",
}

# ── API-FOOTBALL: FORMA, H2H, LESIONES ─────────────────────────
_cache_apifb = {}

def _apifb(endpoint, params):
    if not APIFOOTBALL_KEY:
        return None
    cache_key = f"{endpoint}_{sorted(params.items())}"
    if cache_key in _cache_apifb:
        return _cache_apifb[cache_key]
    try:
        r = requests.get(
            f"{APIFB_URL}/{endpoint}",
            headers={"x-apisports-key": APIFOOTBALL_KEY},
            params=params, timeout=15
        )
        if r.status_code != 200:
            return None
        data = r.json()
        restantes = r.headers.get("x-ratelimit-requests-remaining", "?")
        print(f"    API-Football /{endpoint} | Restantes: {restantes}")
        _cache_apifb[cache_key] = data
        return data
    except Exception as e:
        print(f"    API-Football error: {e}")
        return None

def obtener_forma_reciente(equipo, n=5):
    """Últimos N partidos: devuelve forma, ataque y defensa recientes."""
    team_id = TEAM_IDS.get(equipo)
    if not team_id:
        return None
    data = _apifb("fixtures", {"team": team_id, "last": n, "status": "FT"})
    if not data or not data.get("response"):
        return None
    fixtures = data["response"]
    if not fixtures:
        return None
    puntos = goles_favor = goles_contra = 0
    for f in fixtures:
        es_local = f["teams"]["home"]["id"] == team_id
        sh = f["score"]["fulltime"]["home"] or 0
        sa = f["score"]["fulltime"]["away"] or 0
        gf, gc = (sh, sa) if es_local else (sa, sh)
        goles_favor += gf
        goles_contra += gc
        if gf > gc:    puntos += 3
        elif gf == gc: puntos += 1
    total = len(fixtures)
    forma = round(puntos / (total * 3), 3)
    print(f"    Forma {equipo[-12:]}: {puntos}/{total*3}pts | Gf:{round(goles_favor/total,2)} Gc:{round(goles_contra/total,2)}")
    return {
        "forma":            forma,
        "ataque_reciente":  round(goles_favor  / total, 3),
        "defensa_reciente": round(goles_contra / total, 3),
        "partidos":         total,
    }

def obtener_h2h(local, visitante):
    """Últimos 10 enfrentamientos directos."""
    id_l = TEAM_IDS.get(local)
    id_v = TEAM_IDS.get(visitante)
    if not id_l or not id_v:
        return None
    data = _apifb("fixtures/headtohead", {"h2h": f"{id_l}-{id_v}", "last": 10})
    if not data or not data.get("response"):
        return None
    fixtures = data["response"]
    if len(fixtures) < 3:
        return None
    vl = ve = vv = total_goles = 0
    for f in fixtures:
        es_local = f["teams"]["home"]["id"] == id_l
        sh = f["score"]["fulltime"]["home"] or 0
        sa = f["score"]["fulltime"]["away"] or 0
        gf, gc = (sh, sa) if es_local else (sa, sh)
        total_goles += sh + sa
        if gf > gc:    vl += 1
        elif gf == gc: ve += 1
        else:          vv += 1
    n = len(fixtures)
    print(f"    H2H {local[-10:]} vs {visitante[-10:]}: {vl}W-{ve}D-{vv}L | {round(total_goles/n,1)} goles/p")
    return {
        "victorias_local":   vl / n,
        "empates":           ve / n,
        "victorias_visita":  vv / n,
        "goles_por_partido": round(total_goles / n, 2),
        "partidos":          n,
    }

def obtener_lesiones(equipo):
    """Jugadores con baja activa para el próximo partido del equipo."""
    team_id = TEAM_IDS.get(equipo)
    if not team_id:
        return []
    # Temporada actual: 2025 = temporada 2025/26
    temporada = date.today().year if date.today().month >= 7 else date.today().year - 1
    data = _apifb("injuries", {"team": team_id, "season": temporada})
    if not data or not data.get("response"):
        return []

    hoy = date.today()
    lesionados = []
    vistos = set()  # evitar duplicados por nombre

    for p in data["response"]:
        tipo   = p.get("player", {}).get("type", "")
        nombre = p.get("player", {}).get("name", "Unknown")
        razon  = p.get("player", {}).get("reason", "")

        # Filtrar solo lesiones de partidos futuros (no historial)
        fixture_fecha_str = p.get("fixture", {}).get("date", "")
        if fixture_fecha_str:
            try:
                fixture_fecha = datetime.fromisoformat(fixture_fecha_str[:10]).date()
                if fixture_fecha < hoy:
                    continue  # lesión pasada, ignorar
            except Exception:
                pass

        if tipo in ("Missing Fixture", "Questionable") and nombre not in vistos:
            vistos.add(nombre)
            lesionados.append({"nombre": nombre, "tipo": tipo, "razon": razon})

    if lesionados:
        print(f"    Lesiones {equipo[-12:]}: {len(lesionados)} activa(s) → {', '.join(l['nombre'] for l in lesionados[:3])}")
    return lesionados

# ── OBTENER PARTIDOS DEL DÍA ────────────────────────────────────
def obtener_partidos_hoy_apifb():
    """Una sola llamada trae todos los partidos del día de todas las ligas configuradas."""
    hoy = date.today().isoformat()
    data = _apifb("fixtures", {"date": hoy})
    if not data or not data.get("response"):
        return []
    partidos = []
    conteo = {}
    for f in data["response"]:
        lid = f["league"]["id"]
        if lid not in LIGAS_APIFB:
            continue
        nombre_liga = LIGAS_APIFB[lid]
        status = f["fixture"]["status"]["short"]
        if status not in ("NS", "TBD"):
            continue  # solo partidos no iniciados
        partidos.append({
            "id":         f["fixture"]["id"],
            "liga":       nombre_liga,
            "liga_code":  str(lid),
            "local":      f["teams"]["home"]["name"],
            "visitante":  f["teams"]["away"]["name"],
            "hora":       f["fixture"]["date"][11:16],
            "estado":     status,
        })
        conteo[nombre_liga] = conteo.get(nombre_liga, 0) + 1
    for liga, n in sorted(conteo.items()):
        print(f"  {liga}: {n} partidos")
    return partidos


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
    for codigo in ["PL", "PD", "BL1", "SA", "FL1", "CLI", "CSA"]:
        cargar_stats_liga(codigo)

def get_stats_equipo(nombre):
    if nombre in _cache_stats:
        return _cache_stats[nombre]
    if nombre in STATS_EQUIPOS:
        return STATS_EQUIPOS[nombre]
    return {"ataque": 1.35, "defensa": 1.35, "forma": 0.75}

def obtener_partidos_hoy():
    # Primero intentar api-sports.io (cubre todas las ligas del mundo)
    if APIFOOTBALL_KEY:
        partidos = obtener_partidos_hoy_apifb()
        if partidos:
            return partidos
        print("  api-sports sin resultados, usando football-data.org...")
    # Fallback: football-data.org (solo ligas europeas)
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

# ── DIXON-COLES CORRECTION ──────────────────────────────────────
def _dc_tau(i, j, mu_h, mu_a):
    """Factor de corrección Dixon-Coles para marcadores bajos (0-0, 1-0, 0-1, 1-1)."""
    if   i == 0 and j == 0: return 1 - mu_h * mu_a * RHO
    elif i == 1 and j == 0: return 1 + mu_a * RHO
    elif i == 0 and j == 1: return 1 + mu_h * RHO
    elif i == 1 and j == 1: return 1 - RHO
    return 1.0

# ── MODELO POISSON + DIXON-COLES ────────────────────────────────
def modelo_poisson(goles_local_esperados, goles_visita_esperados):
    """
    Distribución Poisson con corrección Dixon-Coles (ρ=-0.10).
    Ajusta marcadores bajos que Poisson puro subestima (0-0, 1-1).
    """
    max_goles = 8
    mu_h = goles_local_esperados
    mu_a = goles_visita_esperados

    # Matriz de probabilidades con corrección
    matriz = {}
    total = 0.0
    for i in range(max_goles):
        for j in range(max_goles):
            p = poisson.pmf(i, mu_h) * poisson.pmf(j, mu_a) * _dc_tau(i, j, mu_h, mu_a)
            p = max(p, 0.0)
            matriz[(i, j)] = p
            total += p

    # Normalizar
    if total > 0:
        matriz = {k: v / total for k, v in matriz.items()}

    victoria_local = empate = victoria_visita = 0.0
    over15 = over25 = over35 = over45 = 0.0
    btts = 0.0
    hdc_local = hdc_visita = 0.0  # handicap -1 local / +1 visita

    for (i, j), p in matriz.items():
        # 1X2
        if   i > j: victoria_local  += p
        elif i == j: empate         += p
        else:        victoria_visita += p
        # Totales
        total_g = i + j
        if total_g > 1.5: over15 += p
        if total_g > 2.5: over25 += p
        if total_g > 3.5: over35 += p
        if total_g > 4.5: over45 += p
        # BTTS
        if i > 0 and j > 0: btts += p
        # Handicap: local gana por 2+ / visita no pierde por 1
        if i - j >= 2: hdc_local  += p
        if j - i >= 0: hdc_visita += p  # visita +1 (gana o empata ajustado)

    double_1x = victoria_local + empate
    double_x2 = empate + victoria_visita
    double_12 = victoria_local + victoria_visita
    dnb_local  = victoria_local / double_12 if double_12 > 0 else 0
    dnb_visita = victoria_visita / double_12 if double_12 > 0 else 0

    return {
        "victoria_local":           round(victoria_local  * 100, 1),
        "empate":                   round(empate           * 100, 1),
        "victoria_visita":          round(victoria_visita  * 100, 1),
        "over15":                   round(over15           * 100, 1),
        "under15":                  round((1 - over15)     * 100, 1),
        "over25":                   round(over25           * 100, 1),
        "under25":                  round((1 - over25)     * 100, 1),
        "over35":                   round(over35           * 100, 1),
        "under35":                  round((1 - over35)     * 100, 1),
        "over45":                   round(over45           * 100, 1),
        "under45":                  round((1 - over45)     * 100, 1),
        "btts_si":                  round(btts             * 100, 1),
        "btts_no":                  round((1 - btts)       * 100, 1),
        "doble_1x":                 round(double_1x        * 100, 1),
        "doble_x2":                 round(double_x2        * 100, 1),
        "doble_12":                 round(double_12        * 100, 1),
        "dnb_local":                round(dnb_local        * 100, 1),
        "dnb_visita":               round(dnb_visita       * 100, 1),
        "hdc_local_menos1":         round(hdc_local        * 100, 1),
        "hdc_visita_mas1":          round(hdc_visita       * 100, 1),
        "goles_esperados_local":    round(mu_h, 2),
        "goles_esperados_visita":   round(mu_a, 2),
        "total_goles_esperados":    round(mu_h + mu_a, 2),
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
    # Copa Libertadores 2026
    "Boca Juniors":              {"ataque": 1.7, "defensa": 1.0, "forma": 0.78},
    "Fluminense":                {"ataque": 1.5, "defensa": 1.1, "forma": 0.72},
    "Cruzeiro":                  {"ataque": 1.6, "defensa": 1.0, "forma": 0.74},
    "Rosario Central":           {"ataque": 1.4, "defensa": 1.2, "forma": 0.68},
    "Santa Fe":                  {"ataque": 1.3, "defensa": 1.2, "forma": 0.65},
    "Coquimbo Unido":            {"ataque": 1.2, "defensa": 1.3, "forma": 0.62},
    "Tolima":                    {"ataque": 1.3, "defensa": 1.2, "forma": 0.64},
    "Always Ready":              {"ataque": 1.2, "defensa": 1.3, "forma": 0.60},
    "Mirassol":                  {"ataque": 1.4, "defensa": 1.1, "forma": 0.68},
    "Platense":                  {"ataque": 1.2, "defensa": 1.3, "forma": 0.62},
    "Bolivar":                   {"ataque": 1.6, "defensa": 1.0, "forma": 0.72},
    "Club Bolivar":              {"ataque": 1.6, "defensa": 1.0, "forma": 0.72},
    "Universidad Cesar Vallejo": {"ataque": 1.1, "defensa": 1.4, "forma": 0.58},
    "UCV":                       {"ataque": 1.1, "defensa": 1.4, "forma": 0.58},
    # Copa Sudamericana 2026
    "America de Cali":           {"ataque": 1.4, "defensa": 1.2, "forma": 0.66},
    "America":                   {"ataque": 1.4, "defensa": 1.2, "forma": 0.66},
    "Tigre":                     {"ataque": 1.3, "defensa": 1.2, "forma": 0.64},
    "Boston River":              {"ataque": 1.2, "defensa": 1.3, "forma": 0.60},
    "O'Higgins":                 {"ataque": 1.3, "defensa": 1.2, "forma": 0.63},
    "Sao Paulo":                 {"ataque": 1.6, "defensa": 1.0, "forma": 0.74},
    "São Paulo":                 {"ataque": 1.6, "defensa": 1.0, "forma": 0.74},
    "Millonarios":               {"ataque": 1.4, "defensa": 1.1, "forma": 0.68},
    "Cuenca":                    {"ataque": 1.1, "defensa": 1.4, "forma": 0.58},
    "Deportivo Cuenca":          {"ataque": 1.1, "defensa": 1.4, "forma": 0.58},
    "Recoleta":                  {"ataque": 1.1, "defensa": 1.4, "forma": 0.56},
    "Deportes Recoleta":         {"ataque": 1.1, "defensa": 1.4, "forma": 0.56},
    "Torque":                    {"ataque": 1.2, "defensa": 1.3, "forma": 0.60},
    "Deportivo Riestra":         {"ataque": 1.2, "defensa": 1.3, "forma": 0.62},
    "Dep. Riestra":              {"ataque": 1.2, "defensa": 1.3, "forma": 0.62},
    "Audax Italiano":            {"ataque": 1.3, "defensa": 1.2, "forma": 0.63},
    "Barracas Central":          {"ataque": 1.2, "defensa": 1.3, "forma": 0.61},
    "Barracas":                  {"ataque": 1.2, "defensa": 1.3, "forma": 0.61},
    "Racing Club":               {"ataque": 1.7, "defensa": 1.0, "forma": 0.76},
    "River Plate":               {"ataque": 1.9, "defensa": 0.9, "forma": 0.82},
    "Atletico Nacional":         {"ataque": 1.5, "defensa": 1.1, "forma": 0.70},
    "Junior":                    {"ataque": 1.3, "defensa": 1.2, "forma": 0.64},
    "Independiente":             {"ataque": 1.4, "defensa": 1.2, "forma": 0.66},
    "Estudiantes":               {"ataque": 1.5, "defensa": 1.1, "forma": 0.70},
    "Palestino":                 {"ataque": 1.2, "defensa": 1.3, "forma": 0.61},
    "LDU Quito":                 {"ataque": 1.5, "defensa": 1.1, "forma": 0.70},
    "Deportes Iquique":          {"ataque": 1.1, "defensa": 1.4, "forma": 0.57},
}

PROMEDIO_LIGA = {"ataque": 1.35, "defensa": 1.35}

def calcular_goles_esperados(local, visitante):
    stats_l = dict(get_stats_equipo(local))
    stats_v = dict(get_stats_equipo(visitante))

    # ── Enriquecer con forma reciente (API-Football) ────────────
    if APIFOOTBALL_KEY:
        forma_l = obtener_forma_reciente(local)
        forma_v = obtener_forma_reciente(visitante)
        # Blend: 40% temporada + 60% últimos 5 partidos
        if forma_l:
            stats_l["ataque"]  = round(stats_l["ataque"]  * 0.4 + forma_l["ataque_reciente"]  * 0.6, 3)
            stats_l["defensa"] = round(stats_l["defensa"] * 0.4 + forma_l["defensa_reciente"] * 0.6, 3)
            stats_l["forma"]   = round(stats_l["forma"]   * 0.4 + forma_l["forma"]            * 0.6, 3)
        if forma_v:
            stats_v["ataque"]  = round(stats_v["ataque"]  * 0.4 + forma_v["ataque_reciente"]  * 0.6, 3)
            stats_v["defensa"] = round(stats_v["defensa"] * 0.4 + forma_v["defensa_reciente"] * 0.6, 3)
            stats_v["forma"]   = round(stats_v["forma"]   * 0.4 + forma_v["forma"]            * 0.6, 3)

    ventaja_local = 1.25

    goles_local  = (stats_l["ataque"]  / PROMEDIO_LIGA["ataque"])  * \
                   (stats_v["defensa"] / PROMEDIO_LIGA["defensa"]) * \
                   PROMEDIO_LIGA["ataque"] * ventaja_local * stats_l["forma"]

    goles_visita = (stats_v["ataque"]  / PROMEDIO_LIGA["ataque"])  * \
                   (stats_l["defensa"] / PROMEDIO_LIGA["defensa"]) * \
                   PROMEDIO_LIGA["ataque"] * stats_v["forma"]

    # ── Ajuste H2H (30% de corrección) ─────────────────────────
    if APIFOOTBALL_KEY:
        h2h = obtener_h2h(local, visitante)
        if h2h:
            total_modelo = goles_local + goles_visita
            if total_modelo > 0:
                factor = h2h["goles_por_partido"] / total_modelo
                factor = max(0.80, min(factor, 1.20))  # limitar ±20%
                goles_local  *= 1 + (factor - 1) * 0.3
                goles_visita *= 1 + (factor - 1) * 0.3

    # ── Ajuste por lesiones (-0.12 por baja ofensiva) ──────────
    if APIFOOTBALL_KEY:
        bajas_l = obtener_lesiones(local)
        bajas_v = obtener_lesiones(visitante)
        # Reducir ataque por número de bajas (máx -20%)
        penalidad_l = min(len(bajas_l) * 0.05, 0.20)
        penalidad_v = min(len(bajas_v) * 0.05, 0.20)
        goles_local  *= (1 - penalidad_l)
        goles_visita *= (1 - penalidad_v)

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
            "regions": "eu,uk",
            "markets": "h2h,totals,btts,double_chance,draw_no_bet",
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
    mejor = {
        "1": None,       "1_casa": None,
        "X": None,       "X_casa": None,
        "2": None,       "2_casa": None,
        "over15": None,  "over15_casa": None,
        "under15": None, "under15_casa": None,
        "over25": None,  "over25_casa": None,
        "under25": None, "under25_casa": None,
        "over35": None,  "over35_casa": None,
        "under35": None, "under35_casa": None,
        "btts_si": None, "btts_si_casa": None,
        "btts_no": None, "btts_no_casa": None,
        "doble_1x": None, "doble_1x_casa": None,
        "doble_x2": None, "doble_x2_casa": None,
        "doble_12": None, "doble_12_casa": None,
        "dnb_local": None,  "dnb_local_casa": None,
        "dnb_visita": None, "dnb_visita_casa": None,
    }
    home = partido.get("home_team", "")
    away = partido.get("away_team", "")

    for bm in partido.get("bookmakers", []):
        bm_name = bm.get("title", "")
        for market in bm.get("markets", []):
            key = market.get("key")
            outcomes = market.get("outcomes", [])

            if key == "h2h":
                prices = {o["name"]: o["price"] for o in outcomes}
                c1 = prices.get(home)
                c2 = prices.get(away)
                draw_keys = [k for k in prices if k not in [home, away]]
                cx = prices.get(draw_keys[0]) if draw_keys else None
                if c1 and (mejor["1"] is None or c1 > mejor["1"]):
                    mejor["1"] = round(c1, 2);  mejor["1_casa"] = bm_name
                if cx and (mejor["X"] is None or cx > mejor["X"]):
                    mejor["X"] = round(cx, 2);  mejor["X_casa"] = bm_name
                if c2 and (mejor["2"] is None or c2 > mejor["2"]):
                    mejor["2"] = round(c2, 2);  mejor["2_casa"] = bm_name

            elif key == "totals":
                for o in outcomes:
                    pt = o.get("point", 0)
                    nm = o.get("name")
                    pr = o["price"]
                    for lim, over_k, under_k in [(1.5,"over15","under15"),(2.5,"over25","under25"),(3.5,"over35","under35")]:
                        if abs(pt - lim) < 0.01:
                            if nm == "Over" and (mejor[over_k] is None or pr > mejor[over_k]):
                                mejor[over_k] = round(pr, 2); mejor[over_k+"_casa"] = bm_name
                            elif nm == "Under" and (mejor[under_k] is None or pr > mejor[under_k]):
                                mejor[under_k] = round(pr, 2); mejor[under_k+"_casa"] = bm_name

            elif key == "btts":
                for o in outcomes:
                    if o.get("name") in ("Yes", "Sí"):
                        if mejor["btts_si"] is None or o["price"] > mejor["btts_si"]:
                            mejor["btts_si"] = round(o["price"], 2); mejor["btts_si_casa"] = bm_name
                    elif o.get("name") == "No":
                        if mejor["btts_no"] is None or o["price"] > mejor["btts_no"]:
                            mejor["btts_no"] = round(o["price"], 2); mejor["btts_no_casa"] = bm_name

            elif key == "double_chance":
                dc_map = {"1X": "doble_1x", "X2": "doble_x2", "12": "doble_12"}
                for o in outcomes:
                    k2 = dc_map.get(o.get("name",""))
                    if k2 and (mejor[k2] is None or o["price"] > mejor[k2]):
                        mejor[k2] = round(o["price"], 2); mejor[k2+"_casa"] = bm_name

            elif key == "draw_no_bet":
                for o in outcomes:
                    if o["name"] == home and (mejor["dnb_local"] is None or o["price"] > mejor["dnb_local"]):
                        mejor["dnb_local"] = round(o["price"], 2); mejor["dnb_local_casa"] = bm_name
                    elif o["name"] == away and (mejor["dnb_visita"] is None or o["price"] > mejor["dnb_visita"]):
                        mejor["dnb_visita"] = round(o["price"], 2); mejor["dnb_visita_casa"] = bm_name

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

    # Value bets 1X2
    value_local  = calcular_value_bet(probs["victoria_local"],  cuotas.get("1", 2.0))
    value_empate = calcular_value_bet(probs["empate"],          cuotas.get("X", 3.2))
    value_visita = calcular_value_bet(probs["victoria_visita"], cuotas.get("2", 3.5))

    # Value bets — todos los mercados con cuota real de la API
    mercados_extra = [
        ("over15",    "over15"),
        ("under15",   "under15"),
        ("over25",    "over25"),
        ("under25",   "under25"),
        ("over35",    "over35"),
        ("under35",   "under35"),
        ("btts_si",   "btts_si"),
        ("btts_no",   "btts_no"),
        ("doble_1x",  "doble_1x"),
        ("doble_x2",  "doble_x2"),
        ("doble_12",  "doble_12"),
        ("dnb_local", "dnb_local"),
        ("dnb_visita","dnb_visita"),
    ]

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

    value_bets = {
        "victoria_local":  value_local,
        "empate":          value_empate,
        "victoria_visita": value_visita,
    }
    for mercado_key, prob_key in mercados_extra:
        if cuotas.get(mercado_key):
            vb = calcular_value_bet(probs[prob_key], cuotas[mercado_key])
            if vb: value_bets[mercado_key] = vb

    return {
        "local":      local,
        "visitante":  visitante,
        "probabilidades": probs,
        "cuotas":     cuotas,
        "value_bets": value_bets,
        "kelly":      kelly_local,
        "prediccion_principal": prediccion_principal,
        "confianza":  round(max_prob, 1),
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

# ── SELECCIONAR MEJOR PREDICCIÓN DEL DÍA ───────────────────────
def seleccionar_mejor_prediccion(reporte):
    mejor = None
    mejor_ev = -999

    for pred in reporte["predicciones"]:
        for mercado, vb in pred["value_bets"].items():
            if not vb["tiene_valor"]:
                continue
            prioridad = 2 if vb["clasificacion"] == "ALTO VALOR" else 1
            score = prioridad * 1000 + vb["ev_porcentaje"]
            if score > mejor_ev:
                mejor_ev = score
                utc_hora = pred.get("hora", "00:00")
                h, m2 = (int(x) for x in utc_hora.split(":"))
                cot_h = ((h - 5) + 24) % 24
                hora_cot = f"{str(cot_h).zfill(2)}:{str(m2).zfill(2)} COT"
                nombres = {
                    "victoria_local":  "Victoria Local (1)",
                    "empate":          "Empate (X)",
                    "victoria_visita": "Victoria Visitante (2)",
                    "over25":          "Over 2.5",
                    "under25":         "Under 2.5",
                    "btts_si":         "Ambos Marcan — Sí",
                    "btts_no":         "Ambos Marcan — No",
                }
                cuota_key_map = {
                    "victoria_local":  "1",
                    "empate":          "X",
                    "victoria_visita": "2",
                    "over25":          "over25",
                    "under25":         "under25",
                    "btts_si":         "btts_si",
                    "btts_no":         "btts_no",
                }
                cuota_key = cuota_key_map.get(mercado, "1")
                mejor = {
                    "partido": f"{pred['local']} vs {pred['visitante']}",
                    "liga": pred.get("liga", ""),
                    "local": pred["local"],
                    "visitante": pred["visitante"],
                    "prediccion": nombres.get(mercado, mercado),
                    "mercado_key": mercado,
                    "cuota": str(pred["cuotas"].get(cuota_key, "")),
                    "casa": pred["cuotas"].get(cuota_key + "_casa", ""),
                    "hora_utc": utc_hora,
                    "hora_cot": hora_cot,
                    "ev": vb["ev_porcentaje"],
                    "clasificacion": vb["clasificacion"],
                    "confianza": pred["confianza"],
                    "pred_completa": pred,
                }

    # Si no hay value bets, tomar la de mayor confianza
    if not mejor and reporte["predicciones"]:
        pred = reporte["predicciones"][0]
        utc_hora = pred.get("hora", "00:00")
        h, m2 = (int(x) for x in utc_hora.split(":"))
        cot_h = ((h - 5) + 24) % 24
        hora_cot = f"{str(cot_h).zfill(2)}:{str(m2).zfill(2)} COT"
        mejor = {
            "partido": f"{pred['local']} vs {pred['visitante']}",
            "liga": pred.get("liga", ""),
            "local": pred["local"],
            "visitante": pred["visitante"],
            "prediccion": pred["prediccion_principal"]["mercado"],
            "mercado_key": None,
            "cuota": str(pred["cuotas"].get("1", "")),
            "hora_utc": utc_hora,
            "hora_cot": hora_cot,
            "ev": None,
            "clasificacion": None,
            "confianza": pred["confianza"],
            "pred_completa": pred,
        }

    return mejor


# ── HISTORIAL DE CUOTAS (base para CLV futuro) ──────────────────
def guardar_historial_cuotas(reporte):
    """
    Guarda cuotas de apertura en CSV cada vez que corre el motor.
    Acumula datos para calcular Closing Line Value con el tiempo.
    """
    campos = [
        "fecha_consulta", "partido", "liga", "hora_partido",
        "cuota_1", "casa_1", "cuota_X", "casa_X", "cuota_2", "casa_2",
        "cuota_over25", "casa_over25", "cuota_under25", "casa_under25",
    ]
    ahora = datetime.now().isoformat(timespec="seconds")
    filas = []
    for pred in reporte["predicciones"]:
        if not pred.get("cuotas_reales"):
            continue  # solo cuotas reales de la API, no estimadas
        c = pred.get("cuotas", {})
        filas.append({
            "fecha_consulta":  ahora,
            "partido":         f"{pred['local']} vs {pred['visitante']}",
            "liga":            pred.get("liga", ""),
            "hora_partido":    pred.get("hora", ""),
            "cuota_1":         c.get("1", ""),    "casa_1":     c.get("1_casa", ""),
            "cuota_X":         c.get("X", ""),    "casa_X":     c.get("X_casa", ""),
            "cuota_2":         c.get("2", ""),    "casa_2":     c.get("2_casa", ""),
            "cuota_over25":    c.get("over25", ""),  "casa_over25":  c.get("over25_casa", ""),
            "cuota_under25":   c.get("under25", ""), "casa_under25": c.get("under25_casa", ""),
        })
    if not filas:
        return
    existe = os.path.isfile(HISTORIAL_PATH)
    with open(HISTORIAL_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        if not existe:
            writer.writeheader()
        writer.writerows(filas)
    print(f"  Historial cuotas: {len(filas)} partidos → historial_cuotas.csv")


# ── GUARDAR JSON PARA EL PANEL ──────────────────────────────────
def guardar_predicciones():
    reporte = reporte_del_dia()
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)
    print(f"✅ Predicciones guardadas: {reporte['total_partidos']} partidos")
    print(f"📅 Fecha: {reporte['fecha']}")

    guardar_historial_cuotas(reporte)

    mejor = seleccionar_mejor_prediccion(reporte)
    if mejor:
        with open(MEJOR_PATH, "w", encoding="utf-8") as f:
            json.dump(mejor, f, ensure_ascii=False, indent=2)
        print(f"⭐ Mejor prediccion: {mejor['partido']} — {mejor['prediccion']}")

    if TELEGRAM_OK:
        print("\n📲 Enviando alertas Telegram...")
        alto_valor_enviados = 0
        for pred in reporte["predicciones"]:
            for mercado, vb in pred["value_bets"].items():
                if vb["clasificacion"] == "ALTO VALOR":
                    ok = enviar_alerta_value_bet(pred, mercado, vb)
                    if ok:
                        alto_valor_enviados += 1
        if alto_valor_enviados:
            print(f"  🔥 {alto_valor_enviados} alertas ALTO VALOR enviadas")
        enviar_resumen_dia(reporte)
        print("  📋 Resumen del día enviado")

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

        # Mostrar value bets con casa de apuestas
        cuota_key_map = {
            "victoria_local": "1", "empate": "X", "victoria_visita": "2",
            "over25": "over25", "under25": "under25",
            "btts_si": "btts_si", "btts_no": "btts_no",
        }
        for mercado, vb in pred["value_bets"].items():
            if vb["tiene_valor"]:
                ck = cuota_key_map.get(mercado, "1")
                cuota = pred["cuotas"].get(ck, "")
                casa  = pred["cuotas"].get(ck + "_casa", "")
                casa_str = f" [{casa}]" if casa else ""
                print(f"   💰 VALUE BET: {mercado} @ {cuota}{casa_str} → EV: +{vb['ev_porcentaje']}% [{vb['clasificacion']}]")
