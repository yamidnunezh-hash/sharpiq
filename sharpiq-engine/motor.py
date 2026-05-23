"""
SharpIQ — Motor de Predicciones
Modelo: Poisson + Dixon-Coles + Value Betting
"""
import re
import requests
import json
import math
import os
import sys
import csv
import numpy as np

class _NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):  return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)):    return bool(obj)
        if isinstance(obj, np.ndarray):     return obj.tolist()
        return super().default(obj)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, date, timedelta
from scipy.stats import poisson
from scipy.optimize import minimize
import numpy as np

try:
    from telegram_alertas import enviar_alerta_value_bet, enviar_resumen_dia
    TELEGRAM_OK = True
except Exception:
    TELEGRAM_OK = False

try:
    from stats_mercados import analizar_mercados_ext
    MERCADOS_EXT_OK = True
except Exception:
    MERCADOS_EXT_OK = False

try:
    from xg_integracion import ajustar_con_xg
    XG_OK = True
except Exception:
    XG_OK = False

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
    # ── Brasileirao Serie A ──────────────────────────────────────
    "Flamengo": 127,               "CR Flamengo": 127,            "Flamengo RJ": 127,
    "Palmeiras": 121,              "SE Palmeiras": 121,           "Palmeiras SP": 121,
    "Atletico Mineiro": 1062,      "Atlético Mineiro": 1062,      "Atletico MG": 1062,
    "Fluminense": 124,             "Fluminense FC": 124,
    "Internacional": 119,          "SC Internacional": 119,       "Internacional RS": 119,
    "Corinthians": 131,            "SC Corinthians": 131,
    "Sao Paulo": 126,              "São Paulo": 126,              "Sao Paulo FC": 126,
    "Santos": 123,                 "Santos FC": 123,
    "Botafogo": 116,               "Botafogo FR": 116,            "Botafogo RJ": 116,
    "Vasco": 117,                  "Vasco da Gama": 117,          "CR Vasco da Gama": 117,
    "Gremio": 120,                 "Grêmio": 120,                 "Gremio Porto Alegre": 120,
    "Athletico Paranaense": 108,   "Athletico PR": 108,           "CA Paranaense": 108,
    "Cruzeiro": 140,               "Cruzeiro EC": 140,
    "Bahia": 118,                  "EC Bahia": 118,
    "Bragantino": 113,             "Red Bull Bragantino": 113,    "RB Bragantino": 113,
    "Fortaleza": 2020,             "Fortaleza EC": 2020,
    "Atletico Goianiense": 2021,   "Atletico GO": 2021,
    "Cuiaba": 2025,                "Cuiabá": 2025,
    "Ceara": 130,                  "Ceará SC": 130,
    "Sport Recife": 133,           "Sport Club": 133,
    # ── Argentina Primera División ───────────────────────────────
    "River Plate": 547,            "Club River Plate": 547,       "River": 547,
    "Boca Juniors": 405,           "Club Atletico Boca Juniors": 405, "Boca": 405,
    "Racing Club": 442,            "Racing Avellaneda": 442,
    "Independiente": 436,          "CA Independiente": 436,       "Independiente Avellaneda": 436,
    "San Lorenzo": 448,            "San Lorenzo de Almagro": 448,
    "Estudiantes": 432,            "Estudiantes LP": 432,         "Estudiantes de La Plata": 432,
    "Lanus": 440,                  "CA Lanus": 440,
    "Talleres": 1108,              "Talleres Cordoba": 1108,      "CA Talleres": 1108,
    "Atletico Tucuman": 425,       "CA Atletico Tucuman": 425,
    "Huracan": 435,                "CA Huracan": 435,
    "Banfield": 427,               "CA Banfield": 427,
    "Velez Sarsfield": 451,        "CA Velez Sarsfield": 451,     "Velez": 451,
    "Rosario Central": 444,        "CA Rosario Central": 444,
    "Newells Old Boys": 441,       "Newell's Old Boys": 441,      "Newells": 441,
    "Gimnasia La Plata": 433,      "Gimnasia LP": 433,
    "Argentinos Juniors": 424,     "Argentinos": 424,
    "Defensa y Justicia": 430,     "Defensa Justicia": 430,
    "Tigre": 450,                  "CA Tigre": 450,
    # ── Liga MX ──────────────────────────────────────────────────
    "Club America": 2283,          "America": 2283,               "CF America": 2283,
    "Guadalajara": 2282,           "Chivas": 2282,                "CD Guadalajara": 2282,
    "Cruz Azul": 2284,             "Cruz Azul FC": 2284,
    "Tigres UANL": 2285,           "Tigres": 2285,
    "Monterrey": 2286,             "CF Monterrey": 2286,          "Rayados": 2286,
    "Toluca": 2287,                "Deportivo Toluca": 2287,
    "Santos Laguna": 2289,         "Santos Laguna FC": 2289,
    "Atlas": 2281,                 "Atlas FC": 2281,
    "Pumas UNAM": 2292,            "Pumas": 2292,                 "UNAM": 2292,
    "Leon": 2288,                  "Club Leon": 2288,
    "Pachuca": 2290,               "CF Pachuca": 2290,            "Tuzos": 2290,
    "Necaxa": 2291,                "Club Necaxa": 2291,
    "FC Juarez": 2293,             "Juarez": 2293,
    "Queretaro": 2295,             "Queretaro FC": 2295,
    # ── Colombia Liga BetPlay ─────────────────────────────────────
    "Atletico Nacional": 1155,     "Atletico Nacional Medellin": 1155,
    "Millonarios": 1157,           "Millonarios FC": 1157,        "Millonarios Bogota": 1157,
    "Junior": 1158,                "Junior FC": 1158,             "Atletico Junior": 1158,
    "America de Cali": 1154,       "America Cali": 1154,
    "Deportivo Cali": 1156,        "Cali": 1156,
    "Santa Fe": 1165,              "Independiente Santa Fe": 1165,
    "Independiente Medellin": 1159,"DIM": 1159,
    "Deportes Tolima": 1161,       "Tolima": 1161,
    "Once Caldas": 1163,
    "La Equidad": 1160,
    "Envigado": 1162,
    "Deportivo Pasto": 1164,       "Pasto": 1164,
    # ── Copa Libertadores — otros países ─────────────────────────
    "LDU Quito": 735,              "LDU": 735,                    "Liga de Quito": 735,
    "Independiente del Valle": 744,"IDV": 744,                    "Ind del Valle": 744,
    "Barcelona SC": 1322,          "Barcelona Guayaquil": 1322,   "Barcelona Ecuador": 1322,
    "Emelec": 731,                 "CS Emelec": 731,
    "Olimpia": 498,                "Club Olimpia": 498,
    "Libertad": 497,               "Club Libertad": 497,
    "Cerro Porteno": 495,          "Cerro Porteño": 495,
    "Nacional Montevideo": 499,    "Club Nacional": 499,          "Nacional Uruguay": 499,
    "Penharol": 500,               "Peñarol": 500,                "Club Atletico Penharol": 500,
    "Danubio": 501,
    # ── Chile Primera División ───────────────────────────────────
    "Colo Colo": 2355,             "Colo-Colo": 2355,
    "Universidad de Chile": 2356,  "U de Chile": 2356,            "La U": 2356,
    "Universidad Catolica": 2357,  "UC": 2357,                    "Cruzados": 2357,
    "Huachipato": 2358,            "CD Huachipato": 2358,
    "Palestino": 2360,             "CD Palestino": 2360,
    "Cobresal": 2359,
    "Audax Italiano": 2361,        "Audax": 2361,
}

# Mapeo ligas football-data.org / api-sports → the-odds-api.com
LIGAS_ODDS = {
    # football-data.org codes
    "PL":  "soccer_epl",
    "PD":  "soccer_spain_la_liga",
    "BL1": "soccer_germany_bundesliga",
    "SA":  "soccer_italy_serie_a",
    "FL1": "soccer_france_ligue_one",
    "CL":  "soccer_uefa_champs_league",
    "CLI": "soccer_conmebol_copa_libertadores",
    "CSA": "soccer_conmebol_copa_sudamericana",
    # api-sports IDs — UEFA / Europa
    "2":   "soccer_uefa_champs_league",
    "3":   "soccer_uefa_europa_league",
    "848": "soccer_uefa_europa_conference_league",
    "1":   "soccer_fifa_world_cup",
    # api-sports IDs — Grandes ligas europeas
    "39":  "soccer_epl",
    "40":  "soccer_efl_champ",
    "41":  "soccer_england_league1",
    "42":  "soccer_england_league2",
    "78":  "soccer_germany_bundesliga",
    "79":  "soccer_germany_bundesliga2",
    "135": "soccer_italy_serie_a",
    "136": "soccer_italy_serie_b",
    "140": "soccer_spain_la_liga",
    "141": "soccer_spain_segunda_division",
    "61":  "soccer_france_ligue_one",
    "218": "soccer_austria_bundesliga",
    "144": "soccer_belgium_first_div",
    # api-sports IDs — LATAM / Americas
    "13":  "soccer_conmebol_copa_libertadores",
    "11":  "soccer_conmebol_copa_sudamericana",
    "71":  "soccer_brazil_campeonato",
    "72":  "soccer_brazil_serie_b",
    # "128": "soccer_colombia_primera_a",  # 404 en The Odds API — liga no disponible
    "239": "soccer_argentina_primera_division",
    "262": "soccer_mexico_ligamx",
    "253": "soccer_usa_mls",
    "265": "soccer_chile_campeonato",
    # api-sports IDs — Asia / Pacífico / Europa norte
    "98":  "soccer_japan_j_league",
    "169": "soccer_china_superleague",
    "103": "soccer_norway_eliteserien",
    "113": "soccer_sweden_allsvenskan",
    "114": "soccer_sweden_superettan",
    "106": "soccer_poland_ekstraklasa",
    "244": "soccer_finland_veikkausliiga",
    "357": "soccer_league_of_ireland",
}

# Nombre legible por sport_key (para logs y predicciones)
_SPORT_NOMBRE = {
    "soccer_epl":                              "Premier League",
    "soccer_spain_la_liga":                    "La Liga",
    "soccer_germany_bundesliga":               "Bundesliga",
    "soccer_italy_serie_a":                    "Serie A",
    "soccer_france_ligue_one":                 "Ligue 1",
    "soccer_uefa_champs_league":               "Champions League",
    "soccer_conmebol_copa_libertadores":       "Copa Libertadores",
    "soccer_conmebol_copa_sudamericana":       "Copa Sudamericana",
    "soccer_uefa_europa_league":               "Europa League",
    "soccer_uefa_europa_conference_league":    "Conference League",
    "soccer_fifa_world_cup":                   "FIFA World Cup",
    "soccer_efl_champ":                        "EFL Championship",
    "soccer_england_league1":                  "League One",
    "soccer_england_league2":                  "League Two",
    "soccer_germany_bundesliga2":              "2. Bundesliga",
    "soccer_italy_serie_b":                    "Serie B",
    "soccer_spain_segunda_division":           "Segunda División",
    "soccer_austria_bundesliga":               "Austria Bundesliga",
    "soccer_belgium_first_div":                "Belgian First Div",
    "soccer_brazil_campeonato":                "Brasileirao",
    "soccer_brazil_serie_b":                   "Brasileirao B",
    "soccer_argentina_primera_division":       "Liga Profesional",
    "soccer_mexico_ligamx":                    "Liga MX",
    "soccer_usa_mls":                          "MLS",
    "soccer_chile_campeonato":                 "Campeonato Chileno",
    "soccer_japan_j_league":                   "J-League",
    "soccer_china_superleague":                "Super Liga China",
    "soccer_norway_eliteserien":               "Eliteserien",
    "soccer_sweden_allsvenskan":               "Allsvenskan",
    "soccer_sweden_superettan":                "Superettan",
    "soccer_poland_ekstraklasa":               "Ekstraklasa",
    "soccer_finland_veikkausliiga":            "Veikkausliiga",
    "soccer_league_of_ireland":                "League of Ireland",
}

# Deportes adicionales cubiertos por The Odds API (no requieren API-Football)
# El motor los analiza directo con EV vs Pinnacle
SPORTS_ODDS_ONLY = {
    "basketball_nba":           "NBA",
    "basketball_euroleague":    "Euroleague",
    "baseball_mlb":             "MLB",
    "icehockey_nhl":            "NHL",
    "tennis_atp_french_open":   "ATP Roland Garros",
    "tennis_wta_french_open":   "WTA Roland Garros",
    "americanfootball_nfl":     "NFL",
    "americanfootball_ufl":     "UFL",
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
    # UEFA / FIFA
    1:    "Mundial FIFA 2026",
    2:    "Champions League",
    3:    "Europa League",
    848:  "Conference League",
    # Grandes ligas europeas
    39:   "Premier League",
    40:   "Championship",
    41:   "League One",
    42:   "League Two",
    78:   "Bundesliga",
    79:   "Bundesliga 2",
    135:  "Serie A",
    136:  "Serie B",
    140:  "La Liga",
    141:  "La Liga 2",
    61:   "Ligue 1",
    218:  "Austrian Bundesliga",
    144:  "Belgian Pro League",
    # LATAM / Americas
    13:   "Copa Libertadores",
    11:   "Copa Sudamericana",
    71:   "Brasileirao Serie A",
    72:   "Brasileirao Serie B",
    128:  "Liga BetPlay",
    239:  "Primera División Argentina",
    253:  "MLS",
    262:  "Liga MX",
    265:  "Primera División Chile",
    # Asia / Europa norte
    98:   "J1 League",
    169:  "Chinese Super League",
    103:  "Eliteserien",
    113:  "Allsvenskan",
    114:  "Superettan",
    106:  "Ekstraklasa",
    244:  "Veikkausliiga",
    357:  "League of Ireland",
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
    # Solo aceptar fixtures dentro de las próximas 36h (filtra Mundial TBD y Copa Lib futura)
    limite_utc = datetime.utcnow() + timedelta(hours=36)
    for f in data["response"]:
        lid = f["league"]["id"]
        if lid not in LIGAS_APIFB:
            continue
        nombre_liga = LIGAS_APIFB[lid]
        status = f["fixture"]["status"]["short"]
        if status not in ("NS", "TBD"):
            continue  # solo partidos no iniciados
        # Verificar que el fixture esté dentro de las próximas 36h
        fixture_date_str = (f["fixture"].get("date") or "")[:16]
        if fixture_date_str:
            try:
                fixture_dt = datetime.strptime(fixture_date_str, "%Y-%m-%dT%H:%M")
                if fixture_dt > limite_utc:
                    continue  # partido demasiado lejos (Mundial, Copa Lib futura, etc.)
            except Exception:
                pass
        # Sede neutral: finales, semifinales o Mundial (todas en sede neutral)
        round_name   = f["league"].get("round", "").lower()
        sede_neutral = (
            lid == 1  # Mundial FIFA — todos en sede neutral
            or any(kw in round_name for kw in ("final", "semi-final", "3rd place", "third place"))
        )
        arbitro = f["fixture"].get("referee") or ""

        partidos.append({
            "id":           f["fixture"]["id"],
            "liga":         nombre_liga,
            "liga_code":    str(lid),
            "local":        f["teams"]["home"]["name"],
            "visitante":    f["teams"]["away"]["name"],
            "hora":         f["fixture"]["date"][11:16],
            "estado":       status,
            "sede_neutral": sede_neutral,
            "arbitro":      arbitro,
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
    for codigo in ["PL", "PD", "BL1", "SA", "FL1", "CLI"]:
        cargar_stats_liga(codigo)

def get_stats_equipo(nombre):
    if nombre in _cache_stats:
        return _cache_stats[nombre]
    if nombre in STATS_EQUIPOS:
        return STATS_EQUIPOS[nombre]
    # Fallback: consultar la base de datos local (recolector.py la llena cada noche)
    try:
        from database import get_promedios
        row = get_promedios(nombre)
        if row and row.get("partidos_jugados", 0) >= 5:
            return {
                "ataque":  row["goles_favor_avg"],
                "defensa": row["goles_contra_avg"],
                "forma":   row["forma_reciente"],
            }
    except Exception:
        pass
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
    # ── Brasileirao Serie A 2025 ─────────────────────────────────
    "Flamengo":                  {"ataque": 1.9, "defensa": 1.0, "forma": 0.80},
    "CR Flamengo":               {"ataque": 1.9, "defensa": 1.0, "forma": 0.80},
    "Palmeiras":                 {"ataque": 1.8, "defensa": 0.8, "forma": 0.82},
    "SE Palmeiras":              {"ataque": 1.8, "defensa": 0.8, "forma": 0.82},
    "Atletico Mineiro":          {"ataque": 1.7, "defensa": 1.0, "forma": 0.78},
    "Atlético Mineiro":          {"ataque": 1.7, "defensa": 1.0, "forma": 0.78},
    "Atletico MG":               {"ataque": 1.7, "defensa": 1.0, "forma": 0.78},
    "Botafogo":                  {"ataque": 1.7, "defensa": 1.0, "forma": 0.79},
    "Botafogo FR":               {"ataque": 1.7, "defensa": 1.0, "forma": 0.79},
    "Internacional":             {"ataque": 1.6, "defensa": 1.1, "forma": 0.73},
    "SC Internacional":          {"ataque": 1.6, "defensa": 1.1, "forma": 0.73},
    "Corinthians":               {"ataque": 1.5, "defensa": 1.2, "forma": 0.68},
    "SC Corinthians":            {"ataque": 1.5, "defensa": 1.2, "forma": 0.68},
    "Santos":                    {"ataque": 1.4, "defensa": 1.3, "forma": 0.64},
    "Santos FC":                 {"ataque": 1.4, "defensa": 1.3, "forma": 0.64},
    "Vasco":                     {"ataque": 1.4, "defensa": 1.3, "forma": 0.65},
    "Vasco da Gama":             {"ataque": 1.4, "defensa": 1.3, "forma": 0.65},
    "Gremio":                    {"ataque": 1.5, "defensa": 1.2, "forma": 0.69},
    "Grêmio":                    {"ataque": 1.5, "defensa": 1.2, "forma": 0.69},
    "Athletico Paranaense":      {"ataque": 1.5, "defensa": 1.1, "forma": 0.72},
    "Athletico PR":              {"ataque": 1.5, "defensa": 1.1, "forma": 0.72},
    "CA Paranaense":             {"ataque": 1.5, "defensa": 1.1, "forma": 0.72},
    "Bahia":                     {"ataque": 1.5, "defensa": 1.2, "forma": 0.68},
    "EC Bahia":                  {"ataque": 1.5, "defensa": 1.2, "forma": 0.68},
    "Bragantino":                {"ataque": 1.6, "defensa": 1.1, "forma": 0.72},
    "Red Bull Bragantino":       {"ataque": 1.6, "defensa": 1.1, "forma": 0.72},
    "RB Bragantino":             {"ataque": 1.6, "defensa": 1.1, "forma": 0.72},
    "Fortaleza":                 {"ataque": 1.6, "defensa": 1.1, "forma": 0.72},
    "Fortaleza EC":              {"ataque": 1.6, "defensa": 1.1, "forma": 0.72},
    "Fluminense FC":             {"ataque": 1.5, "defensa": 1.1, "forma": 0.72},
    # ── Liga MX 2025/26 ──────────────────────────────────────────
    "Club America":              {"ataque": 1.9, "defensa": 0.9, "forma": 0.82},
    "America":                   {"ataque": 1.9, "defensa": 0.9, "forma": 0.82},
    "Tigres UANL":               {"ataque": 1.8, "defensa": 0.9, "forma": 0.80},
    "Tigres":                    {"ataque": 1.8, "defensa": 0.9, "forma": 0.80},
    "Monterrey":                 {"ataque": 1.7, "defensa": 0.9, "forma": 0.78},
    "CF Monterrey":              {"ataque": 1.7, "defensa": 0.9, "forma": 0.78},
    "Cruz Azul":                 {"ataque": 1.7, "defensa": 1.0, "forma": 0.78},
    "Guadalajara":               {"ataque": 1.6, "defensa": 1.0, "forma": 0.75},
    "Chivas":                    {"ataque": 1.6, "defensa": 1.0, "forma": 0.75},
    "Pachuca":                   {"ataque": 1.5, "defensa": 1.1, "forma": 0.72},
    "CF Pachuca":                {"ataque": 1.5, "defensa": 1.1, "forma": 0.72},
    "Pumas UNAM":                {"ataque": 1.5, "defensa": 1.1, "forma": 0.70},
    "Pumas":                     {"ataque": 1.5, "defensa": 1.1, "forma": 0.70},
    "Leon":                      {"ataque": 1.5, "defensa": 1.1, "forma": 0.70},
    "Club Leon":                 {"ataque": 1.5, "defensa": 1.1, "forma": 0.70},
    "Toluca":                    {"ataque": 1.5, "defensa": 1.1, "forma": 0.72},
    "Deportivo Toluca":          {"ataque": 1.5, "defensa": 1.1, "forma": 0.72},
    "Santos Laguna":             {"ataque": 1.4, "defensa": 1.2, "forma": 0.68},
    "Atlas":                     {"ataque": 1.4, "defensa": 1.2, "forma": 0.68},
    "Atlas FC":                  {"ataque": 1.4, "defensa": 1.2, "forma": 0.68},
    "Queretaro":                 {"ataque": 1.3, "defensa": 1.3, "forma": 0.62},
    "Necaxa":                    {"ataque": 1.3, "defensa": 1.3, "forma": 0.61},
    "FC Juarez":                 {"ataque": 1.2, "defensa": 1.4, "forma": 0.58},
    # ── Argentina completa ────────────────────────────────────────
    "Boca Juniors":              {"ataque": 1.7, "defensa": 1.0, "forma": 0.78},
    "Club Atletico Boca Juniors":{"ataque": 1.7, "defensa": 1.0, "forma": 0.78},
    "San Lorenzo":               {"ataque": 1.4, "defensa": 1.2, "forma": 0.66},
    "San Lorenzo de Almagro":    {"ataque": 1.4, "defensa": 1.2, "forma": 0.66},
    "Talleres":                  {"ataque": 1.6, "defensa": 1.0, "forma": 0.73},
    "Talleres Cordoba":          {"ataque": 1.6, "defensa": 1.0, "forma": 0.73},
    "Velez Sarsfield":           {"ataque": 1.4, "defensa": 1.2, "forma": 0.67},
    "Velez":                     {"ataque": 1.4, "defensa": 1.2, "forma": 0.67},
    "Lanus":                     {"ataque": 1.4, "defensa": 1.2, "forma": 0.66},
    "Atletico Tucuman":          {"ataque": 1.3, "defensa": 1.2, "forma": 0.64},
    "Huracan":                   {"ataque": 1.3, "defensa": 1.3, "forma": 0.63},
    "Banfield":                  {"ataque": 1.3, "defensa": 1.3, "forma": 0.62},
    "Newells Old Boys":          {"ataque": 1.4, "defensa": 1.2, "forma": 0.65},
    "Newell's Old Boys":         {"ataque": 1.4, "defensa": 1.2, "forma": 0.65},
    "Gimnasia La Plata":         {"ataque": 1.2, "defensa": 1.4, "forma": 0.60},
    "Argentinos Juniors":        {"ataque": 1.4, "defensa": 1.2, "forma": 0.65},
    "Defensa y Justicia":        {"ataque": 1.4, "defensa": 1.2, "forma": 0.65},
    # ── Colombia Liga BetPlay ─────────────────────────────────────
    "Deportivo Cali":            {"ataque": 1.4, "defensa": 1.2, "forma": 0.65},
    "Independiente Medellin":    {"ataque": 1.4, "defensa": 1.2, "forma": 0.66},
    "DIM":                       {"ataque": 1.4, "defensa": 1.2, "forma": 0.66},
    "La Equidad":                {"ataque": 1.2, "defensa": 1.3, "forma": 0.61},
    "Envigado":                  {"ataque": 1.1, "defensa": 1.4, "forma": 0.58},
    "Deportivo Pasto":           {"ataque": 1.1, "defensa": 1.4, "forma": 0.57},
    "Once Caldas":               {"ataque": 1.2, "defensa": 1.3, "forma": 0.62},
    # ── Chile Primera División ───────────────────────────────────
    "Colo Colo":                 {"ataque": 1.7, "defensa": 1.0, "forma": 0.77},
    "Colo-Colo":                 {"ataque": 1.7, "defensa": 1.0, "forma": 0.77},
    "Universidad de Chile":      {"ataque": 1.5, "defensa": 1.1, "forma": 0.70},
    "U de Chile":                {"ataque": 1.5, "defensa": 1.1, "forma": 0.70},
    "Universidad Catolica":      {"ataque": 1.6, "defensa": 1.0, "forma": 0.73},
    "Cruzados":                  {"ataque": 1.6, "defensa": 1.0, "forma": 0.73},
    "Cobresal":                  {"ataque": 1.2, "defensa": 1.3, "forma": 0.60},
    "Huachipato":                {"ataque": 1.3, "defensa": 1.2, "forma": 0.64},
    # ── Copa Libertadores — Uruguay, Paraguay, Ecuador ────────────
    "Nacional Montevideo":       {"ataque": 1.4, "defensa": 1.1, "forma": 0.72},
    "Club Nacional":             {"ataque": 1.4, "defensa": 1.1, "forma": 0.72},
    "Penharol":                  {"ataque": 1.5, "defensa": 1.0, "forma": 0.75},
    "Peñarol":                   {"ataque": 1.5, "defensa": 1.0, "forma": 0.75},
    "Olimpia":                   {"ataque": 1.3, "defensa": 1.2, "forma": 0.66},
    "Libertad":                  {"ataque": 1.3, "defensa": 1.2, "forma": 0.64},
    "Cerro Porteno":             {"ataque": 1.3, "defensa": 1.2, "forma": 0.64},
    "Cerro Porteño":             {"ataque": 1.3, "defensa": 1.2, "forma": 0.64},
    "Independiente del Valle":   {"ataque": 1.5, "defensa": 1.0, "forma": 0.74},
    "IDV":                       {"ataque": 1.5, "defensa": 1.0, "forma": 0.74},
    "Barcelona SC":              {"ataque": 1.4, "defensa": 1.1, "forma": 0.70},
    "Barcelona Guayaquil":       {"ataque": 1.4, "defensa": 1.1, "forma": 0.70},
    "Emelec":                    {"ataque": 1.3, "defensa": 1.2, "forma": 0.64},
}

PROMEDIO_LIGA = {"ataque": 1.35, "defensa": 1.35}

def calcular_goles_esperados(local, visitante, liga_code="", sede_neutral=False):
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

    # Ventaja local calibrada por liga (basada en datos históricos 2020-2025)
    VENTAJA_LOCAL_LIGA = {
        "PL":  1.28,   # Premier League
        "PD":  1.30,   # La Liga
        "BL1": 1.27,   # Bundesliga
        "SA":  1.26,   # Serie A
        "FL1": 1.24,   # Ligue 1
        "CL":  1.18,   # Champions League (neutral en muchos casos)
        "CLI": 1.20,   # Copa Libertadores
        "CSA": 1.19,   # Copa Sudamericana
        "71":  1.22,   # Brasileirao
        "128": 1.24,   # Liga BetPlay Colombia
        "262": 1.23,   # Liga MX
        "239": 1.22,   # Argentina Primera
        "265": 1.21,   # Chile Primera
        "253": 1.20,   # MLS
    }
    ventaja_local = VENTAJA_LOCAL_LIGA.get(liga_code, 1.25)
    if sede_neutral:
        ventaja_local = 1.0  # final o sede neutral: sin ventaja de cancha

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

    # ── Ajuste xG (shots on target proxy, caché de stats_mercados) ─
    if APIFOOTBALL_KEY and XG_OK and liga_code:
        try:
            goles_local, goles_visita = ajustar_con_xg(
                local, visitante, liga_code, goles_local, goles_visita)
        except Exception:
            pass

    return goles_local, goles_visita

# ── CUOTAS REALES (The Odds API) ────────────────────────────────
_cache_cuotas     = {}  # cache para no gastar créditos
_cache_cuotas_ext = {}  # cache para mercados extendidos de fútbol

_SPORTS_US = {
    "basketball_nba", "basketball_wnba", "baseball_mlb", "icehockey_nhl",
    "americanfootball_nfl", "americanfootball_ufl", "americanfootball_ncaaf",
    "lacrosse_pll", "lacrosse_ncaa",
}

def obtener_cuotas_liga(sport_key):
    if sport_key in _cache_cuotas:
        return _cache_cuotas[sport_key]
    try:
        url = f"{ODDS_API_URL}/sports/{sport_key}/odds"
        # Deportes americanos: incluir región us para más casas
        if sport_key in _SPORTS_US:
            regions   = "eu,uk,us"
            bookmakers = "pinnacle,draftkings,fanduel,bet365,betmgm,unibet"
            markets    = "h2h,spreads,totals"
        else:
            regions   = "eu,uk"
            bookmakers = "pinnacle,bet365,betfair,unibet,williamhill,bwin"
            markets    = "h2h,totals,btts,double_chance,draw_no_bet"
        params = {
            "apiKey":      ODDS_API_KEY,
            "regions":     regions,
            "markets":     markets,
            "oddsFormat":  "decimal",
            "bookmakers":  bookmakers,
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

def _fetch_odds_ext(sport_key):
    """
    Obtiene cuotas completas para un deporte de fútbol.
    Mercados: 1X2, Over/Under (todas las líneas), BTTS, DC, DNB, Handicap, Team Totals.
    Caché separada de obtener_cuotas_liga para no mezclar respuestas.
    """
    if sport_key in _cache_cuotas_ext:
        return _cache_cuotas_ext[sport_key]
    try:
        url = f"{ODDS_API_URL}/sports/{sport_key}/odds"
        params = {
            "apiKey":      ODDS_API_KEY,
            "regions":     "eu,uk",
            "markets":     "h2h,totals",
            "oddsFormat":  "decimal",
            "bookmakers":  "pinnacle,bet365,betfair,unibet,williamhill,bwin",
        }
        r = requests.get(url, params=params, timeout=20)
        if r.status_code != 200:
            print(f"  Odds ext {sport_key}: HTTP {r.status_code}")
            return []
        data = r.json()
        _cache_cuotas_ext[sport_key] = data
        restantes = r.headers.get("x-requests-remaining", "?")
        print(f"  Odds ext {sport_key}: {len(data)} eventos | Créditos: {restantes}")
        return data
    except Exception as e:
        print(f"  Odds ext {sport_key} error: {e}")
        return []


_STOPWORDS_EQUIPO = {
    # Sufijos genéricos
    'club', 'fc', 'cf', 'sc', 'ac', 'as', 'sk', 'sd', 'cd', 'ca', 'cs', 'cdp',
    'rc', 'ra', 'fk', 'nk', 'pk', 'bv', 'sv', 'nr', 'gd', 'if',
    # Artículos / preposiciones
    'de', 'del', 'los', 'las', 'el', 'la', 'the', 'y', 'e', 'do', 'da', 'dos',
    # Palabras comunes en nombres de equipos
    'united', 'city', 'sport', 'sporting', 'atletico', 'real', 'deportivo',
    'sociedad', 'association', 'junior', 'seniors',
    # Códigos de estado Brasil
    'rj', 'sp', 'mg', 'pr', 'rs', 'ba', 'pe', 'sc', 'go', 'ce',
    # Prefijos LATAM
    'ldu', 'csd', 'bsc', 'uanl', 'lfc',
}

def _norm_equipo(nombre):
    n = nombre.lower()
    n = re.sub(r'\b\w{2,3}\b$', '', n)        # quita sufijos de 2-3 chars al final (SP, RJ, FC…)
    n = re.sub(r'[áàä]','a', re.sub(r'[éèë]','e', re.sub(r'[íìï]','i',
        re.sub(r'[óòö]','o', re.sub(r'[úùü]','u', n)))))
    n = re.sub(r'[^a-z0-9 ]', ' ', n)
    palabras = [p for p in n.split() if p not in _STOPWORDS_EQUIPO and len(p) > 2]
    return set(palabras)

def _match_equipos(a, b):
    sa, sb = _norm_equipo(a), _norm_equipo(b)
    if not sa or not sb:
        return False
    interseccion = sa & sb
    if not interseccion:
        return False
    # Si hay al menos una palabra larga (≥5 chars) en común → match directo
    if any(len(w) >= 5 for w in interseccion):
        return True
    # Umbral proporcional: 50% de las palabras del set más pequeño
    return len(interseccion) / min(len(sa), len(sb)) >= 0.5


def buscar_cuotas_partido(local, visitante, sport_key):
    partidos = obtener_cuotas_liga(sport_key)
    for p in partidos:
        h = p.get("home_team", "")
        a = p.get("away_team", "")
        if _match_equipos(local, h) and _match_equipos(visitante, a):
            return extraer_mejor_cuota(p)
    # Sin match — loguear candidatos para diagnóstico
    if partidos:
        candidatos = [f"{p['home_team']} vs {p['away_team']}" for p in partidos[:6]]
        print(f"  No match '{local}' vs '{visitante}' en {sport_key}. API tiene: {candidatos}")
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
        # Pinnacle como benchmark de probabilidad real
        "pinnacle_1": None, "pinnacle_X": None, "pinnacle_2": None,
        "pinnacle_over25": None, "pinnacle_under25": None,
        "pinnacle_over15": None, "pinnacle_under15": None,
        "pinnacle_over35": None, "pinnacle_under35": None,
    }
    home = partido.get("home_team", "")
    away = partido.get("away_team", "")

    for bm in partido.get("bookmakers", []):
        bm_name  = bm.get("title", "")
        bm_key   = bm.get("key", "")
        es_pinn  = bm_key == "pinnacle"
        for market in bm.get("markets", []):
            key = market.get("key")
            outcomes = market.get("outcomes", [])

            if key == "h2h":
                prices = {o["name"]: o["price"] for o in outcomes}
                c1 = prices.get(home)
                c2 = prices.get(away)
                draw_keys = [k for k in prices if k not in [home, away]]
                cx = prices.get(draw_keys[0]) if draw_keys else None
                if es_pinn:
                    if c1: mejor["pinnacle_1"] = round(c1, 2)
                    if cx: mejor["pinnacle_X"] = round(cx, 2)
                    if c2: mejor["pinnacle_2"] = round(c2, 2)
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
                            if es_pinn:
                                if nm == "Over":    mejor[f"pinnacle_{over_k}"]  = round(pr, 2)
                                elif nm == "Under": mejor[f"pinnacle_{under_k}"] = round(pr, 2)

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
    tiene_valor = bool(value > 0.15)  # mínimo 15% EV — solo ALTO VALOR
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

# ── VALIDACIÓN DE CUOTAS ────────────────────────────────────────
def _validar_cuotas(cuotas, probs):
    """
    Elimina cuotas de la API que son implausibles dado lo que predice el modelo.
    Regla: si cuota_api > 3x la cuota_justa (1/prob), es error de datos → descartada.
    Retorna (cuotas_limpias, advertencias)
    """
    if not cuotas:
        return cuotas, []

    mapa = {
        "1":       probs.get("victoria_local", 0) / 100,
        "X":       probs.get("empate", 0) / 100,
        "2":       probs.get("victoria_visita", 0) / 100,
        "over25":  probs.get("over25", 0) / 100,
        "under25": probs.get("under25", 0) / 100,
        "over15":  probs.get("over15", 0) / 100,
        "under15": probs.get("under15", 0) / 100,
        "over35":  probs.get("over35", 0) / 100,
        "under35": probs.get("under35", 0) / 100,
        "btts_si": probs.get("btts_si", 0) / 100,
        "btts_no": probs.get("btts_no", 0) / 100,
    }

    limpias = dict(cuotas)
    advertencias = []
    for clave, prob in mapa.items():
        val = limpias.get(clave)
        if not val or prob <= 0:
            continue
        try:
            cuota_api  = float(val)
            cuota_justa = 1.0 / prob
        except (ValueError, ZeroDivisionError):
            continue
        if cuota_api > cuota_justa * 3.0:
            advertencias.append(
                f"{clave}: {cuota_api} (esperada ~{cuota_justa:.2f}, prob {prob*100:.0f}%) — DESCARTADA"
            )
            del limpias[clave]
            # También borrar _casa si existe
            limpias.pop(clave + "_casa", None)

    return limpias, advertencias


# ── PREDICCIÓN COMPLETA ─────────────────────────────────────────
def predecir_partido(local, visitante, cuotas=None, liga_code="", sede_neutral=False):
    goles_local, goles_visita = calcular_goles_esperados(local, visitante, liga_code, sede_neutral)
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

    # Value bets — todos los mercados con cuota
    value_bets = {
        "victoria_local":  value_local,
        "empate":          value_empate,
        "victoria_visita": value_visita,
    }
    for mercado_key, prob_key in mercados_extra:
        if cuotas.get(mercado_key):
            vb = calcular_value_bet(probs[prob_key], cuotas[mercado_key])
            if vb: value_bets[mercado_key] = vb

    # EV vs Pinnacle — desviar cuotas Pinnacle para obtener probabilidad real
    if cuotas:
        pinn1 = cuotas.get("pinnacle_1")
        pinnX = cuotas.get("pinnacle_X")
        pinn2 = cuotas.get("pinnacle_2")
        pinn_probs = {}
        if pinn1 and pinnX and pinn2:
            s3 = 1/pinn1 + 1/pinnX + 1/pinn2
            pinn_probs["victoria_local"]  = (1/pinn1) / s3
            pinn_probs["empate"]          = (1/pinnX) / s3
            pinn_probs["victoria_visita"] = (1/pinn2) / s3
        for lim_str in ["15", "25", "35"]:
            po = cuotas.get(f"pinnacle_over{lim_str}")
            pu = cuotas.get(f"pinnacle_under{lim_str}")
            if po and pu:
                s2 = 1/po + 1/pu
                pinn_probs[f"over{lim_str}"]  = (1/po) / s2
                pinn_probs[f"under{lim_str}"] = (1/pu) / s2
        _pinn_ck = {
            "victoria_local": "1", "empate": "X", "victoria_visita": "2",
            "over15": "over15", "under15": "under15",
            "over25": "over25", "under25": "under25",
            "over35": "over35", "under35": "under35",
        }
        for mk, vb in value_bets.items():
            pp = pinn_probs.get(mk)
            q  = cuotas.get(_pinn_ck.get(mk, mk))
            if pp and q:
                ev_p = round((pp * float(q) - 1) * 100, 1)
                vb["ev_pinn"]          = ev_p
                vb["tiene_valor_pinn"] = ev_p > 0
            else:
                vb["ev_pinn"]          = None
                vb["tiene_valor_pinn"] = None

    # Mercados extendidos: corners, tarjetas, handicap asiático
    mercados_ext = {}
    if MERCADOS_EXT_OK and liga_code:
        try:
            mercados_ext = analizar_mercados_ext(local, visitante, liga_code, probs)
        except Exception:
            pass

    # ── PREDICCIÓN PRINCIPAL — mejor EV entre TODOS los mercados ──
    _NOMBRES = {
        "victoria_local":    ("Victoria Local (1)",        probs["victoria_local"]),
        "empate":            ("Empate (X)",                 probs["empate"]),
        "victoria_visita":   ("Victoria Visitante (2)",     probs["victoria_visita"]),
        "over25":            ("Over 2.5 Goles",             probs.get("over25", 0)),
        "under25":           ("Under 2.5 Goles",            probs.get("under25", 0)),
        "over15":            ("Over 1.5 Goles",             probs.get("over15", 0)),
        "under15":           ("Under 1.5 Goles",            probs.get("under15", 0)),
        "over35":            ("Over 3.5 Goles",             probs.get("over35", 0)),
        "under35":           ("Under 3.5 Goles",            probs.get("under35", 0)),
        "btts_si":           ("Ambos Marcan — Sí",          probs.get("btts_si", 0)),
        "btts_no":           ("Ambos Marcan — No",          probs.get("btts_no", 0)),
        "doble_1x":          ("Doble Oportunidad 1X",       probs.get("doble_1x", 0)),
        "doble_x2":          ("Doble Oportunidad X2",       probs.get("doble_x2", 0)),
        "doble_12":          ("Doble Oportunidad 12",       probs.get("doble_12", 0)),
        "dnb_local":         ("DNB Local",                  probs.get("dnb_local", 0)),
        "dnb_visita":        ("DNB Visitante",              probs.get("dnb_visita", 0)),
    }
    _NOMBRES_EXT = {
        "corners_over9":     "Corners Over 9.5",
        "corners_under9":    "Corners Under 9.5",
        "corners_over10":    "Corners Over 10.5",
        "corners_under10":   "Corners Under 10.5",
        "corners_over11":    "Corners Over 11.5",
        "corners_under11":   "Corners Under 11.5",
        "corners_over12":    "Corners Over 12.5",
        "corners_under12":   "Corners Under 12.5",
        "tarjetas_over3":    "Tarjetas Over 3.5",
        "tarjetas_under3":   "Tarjetas Under 3.5",
        "tarjetas_over4":    "Tarjetas Over 4.5",
        "tarjetas_under4":   "Tarjetas Under 4.5",
        "tarjetas_over5":    "Tarjetas Over 5.5",
        "tarjetas_under5":   "Tarjetas Under 5.5",
        "ah_local_menos05":  "Handicap Local -0.5",
        "ah_visita_mas05":   "Handicap Visitante +0.5",
        "ah_local_menos1":   "Handicap Local -1",
        "ah_visita_mas1":    "Handicap Visitante +1",
        "ah_local_menos15":  "Handicap Local -1.5",
        "ah_visita_mas15":   "Handicap Visitante +1.5",
    }

    mejor_ev   = -9999
    mejor_pred = None

    # Escanear value_bets (1X2 + goles + doble chance + DNB)
    for mk, vb in value_bets.items():
        if not vb or mk not in _NOMBRES:
            continue
        ev = vb.get("ev_porcentaje", -9999)
        if ev > mejor_ev:
            mejor_ev = ev
            nombre, prob = _NOMBRES[mk]
            mejor_pred = {"mercado": nombre, "prob": round(prob, 1), "ev": round(ev, 1)}

    # Escanear mercados extendidos (corners, tarjetas, handicap)
    for mk, datos in (mercados_ext.get("ev_ext") or {}).items():
        if mk not in _NOMBRES_EXT:
            continue
        ev = datos.get("ev_porcentaje", -9999)
        if ev > mejor_ev:
            mejor_ev = ev
            mejor_pred = {
                "mercado": _NOMBRES_EXT[mk],
                "prob":    round(datos.get("prob_modelo", 0), 1),
                "ev":      round(ev, 1),
            }

    # Fallback: si no hay datos suficientes, usar mayor probabilidad 1X2
    if mejor_pred is None:
        max_p = max(probs["victoria_local"], probs["empate"], probs["victoria_visita"])
        if max_p == probs["victoria_local"]:
            mejor_pred = {"mercado": "Victoria Local (1)",    "prob": round(probs["victoria_local"], 1),  "ev": None}
        elif max_p == probs["empate"]:
            mejor_pred = {"mercado": "Empate (X)",             "prob": round(probs["empate"], 1),          "ev": None}
        else:
            mejor_pred = {"mercado": "Victoria Visitante (2)", "prob": round(probs["victoria_visita"], 1), "ev": None}

    prediccion_principal = mejor_pred

    return {
        "local":      local,
        "visitante":  visitante,
        "probabilidades": probs,
        "cuotas":     cuotas,
        "value_bets": value_bets,
        "kelly":      kelly_local,
        "prediccion_principal": prediccion_principal,
        "confianza":  prediccion_principal["prob"],
        "mercados_ext": mercados_ext,
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

    # Determinar tipo de snapshot según la hora
    hora_actual = datetime.now().hour
    snapshot_tipo = "apertura" if hora_actual < 13 else "tarde"
    print(f"\n  Snapshot de cuotas: {snapshot_tipo} ({hora_actual}h)")

    try:
        from database import inicializar as db_init, guardar_snapshot, get_movimiento
        db_init()
        db_ok = True
    except Exception:
        db_ok = False

    for p in partidos:
        # Buscar cuotas reales para este partido
        sport_key = LIGAS_ODDS.get(p["liga_code"])
        cuotas_reales = None
        if sport_key:
            cuotas_reales = buscar_cuotas_partido(p["local"], p["visitante"], sport_key)
            if cuotas_reales:
                print(f"  Cuotas OK: {p['local']} vs {p['visitante']} ({sport_key})")
            else:
                print(f"  Sin cuotas: {p['local']} vs {p['visitante']} ({sport_key}) — usando fallback")

        # Guardar snapshot para tracking de movimiento
        if db_ok and cuotas_reales and p.get("id"):
            try:
                guardar_snapshot(p["id"], p["local"], p["visitante"],
                                 date.today().isoformat(), snapshot_tipo, cuotas_reales)
            except Exception:
                pass

        # Validar cuotas contra probabilidades del modelo antes de usarlas
        avisos_cuota = []
        if cuotas_reales:
            probs_prev = modelo_poisson(*calcular_goles_esperados(p["local"], p["visitante"]))
            cuotas_reales, avisos_cuota = _validar_cuotas(cuotas_reales, probs_prev)
            for av in avisos_cuota:
                print(f"  ⚠ Cuota sospechosa {p['local']} vs {p['visitante']}: {av}")

        sede_neutral = p.get("sede_neutral", False)
        if sede_neutral:
            print(f"  Sede neutral detectada: {p['local']} vs {p['visitante']} ({p['liga']})")

        pred = predecir_partido(
            p["local"], p["visitante"],
            cuotas=cuotas_reales,
            liga_code=p.get("liga_code", ""),
            sede_neutral=sede_neutral,
        )
        pred["liga"]         = p["liga"]
        pred["hora"]         = p["hora"]
        pred["id"]           = p["id"]
        pred["sede_neutral"] = sede_neutral
        pred["arbitro"]      = p.get("arbitro", "")
        pred["cuotas_reales"] = bool(cuotas_reales)
        pred["cuotas_avisos"] = avisos_cuota

        # Datos de contexto para narrativa — usa el caché de api-football, 0 llamadas extra
        pred["forma_local"]  = obtener_forma_reciente(p["local"])
        pred["forma_visita"] = obtener_forma_reciente(p["visitante"])
        pred["h2h"]          = obtener_h2h(p["local"], p["visitante"])

        # Leer movimiento de línea si existe snapshot anterior
        pred["movimiento"] = None
        if db_ok and p.get("id"):
            try:
                pred["movimiento"] = get_movimiento(p["id"])
            except Exception:
                pass

        predicciones.append(pred)

    # Prioridad por competición — partidos grandes siempre primero
    PRIORIDAD_LIGA = {
        "2": 100, "CL": 100,        # Champions League
        "3": 90,  "EL": 90,         # Europa League
        "848": 85,                   # Conference League
        "1": 95,                     # Mundial FIFA
        "39": 70, "PL": 70,         # Premier League
        "140": 68, "PD": 68,        # La Liga
        "78": 65, "BL1": 65,        # Bundesliga
        "135": 63, "SA": 63,        # Serie A
        "61": 60, "FL1": 60,        # Ligue 1
        "13": 55, "CLI": 55,        # Copa Libertadores
        "11": 50, "CSA": 50,        # Copa Sudamericana
    }

    def _score_pred(p):
        liga_prio = PRIORIDAD_LIGA.get(str(p.get("liga_code", "")), 30)
        tiene_valor = any(v.get("tiene_valor") for v in p["value_bets"].values())
        mejor_ev = max((v.get("ev_porcentaje", 0) for v in p["value_bets"].values()), default=0)
        return (liga_prio * 0.4) + (mejor_ev * 0.4) + (p["confianza"] * 0.2) + (50 if tiene_valor else 0)

    predicciones.sort(key=_score_pred, reverse=True)

    # Scan arbitraje — aviso inmediato a Yamid si hay oportunidad garantizada
    try:
        from arbitraje import correr_scan
        correr_scan(cuotas_por_liga)
    except Exception as e:
        print(f"  Arbitraje scan error: {e}")

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
            ev_pinn = vb.get("ev_pinn")
            if ev_pinn is not None and ev_pinn <= 0:
                continue  # Pinnacle no confirma el valor
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


# ── PLAYER PROPS (NBA / NHL / MLB) ──────────────────────────────
# Mercados de props por deporte — The Odds API market keys
_PROP_MARKETS = {
    "basketball_nba": ["player_points", "player_rebounds", "player_assists"],
    "icehockey_nhl":  ["player_points", "player_shots_on_target"],
    "baseball_mlb":   ["batter_hits",   "pitcher_strikeouts"],
}
_PROP_NOMBRES = {
    "player_points":          "Puntos",
    "player_rebounds":        "Rebotes",
    "player_assists":         "Asistencias",
    "player_shots_on_target": "Tiros al Arco",
    "batter_hits":            "Hits",
    "pitcher_strikeouts":     "Strikeouts",
}


def analizar_player_props_sharp(sport_key, nombre_liga):
    """
    Obtiene player props (puntos/rebotes/asistencias) de The Odds API,
    devigea líneas de Pinnacle y calcula EV vs mejor casa disponible.
    Retorna predicciones en el mismo formato estándar del motor.
    """
    mercados = _PROP_MARKETS.get(sport_key, [])
    if not mercados:
        return []

    cache_key = f"props_{sport_key}"
    if cache_key in _cache_cuotas:
        eventos = _cache_cuotas[cache_key]
    else:
        try:
            url = f"{ODDS_API_URL}/sports/{sport_key}/odds"
            params = {
                "apiKey":     ODDS_API_KEY,
                "regions":    "us,eu",
                "markets":    ",".join(mercados),
                "oddsFormat": "decimal",
                "bookmakers": "pinnacle,draftkings,fanduel,bet365,betmgm,unibet",
            }
            r = requests.get(url, params=params, timeout=20)
            if r.status_code != 200:
                print(f"  Player props {sport_key}: HTTP {r.status_code}")
                return []
            eventos = r.json()
            _cache_cuotas[cache_key] = eventos
            restantes = r.headers.get("x-requests-remaining", "?")
            print(f"  Player props {nombre_liga}: {len(eventos)} eventos | Créditos: {restantes}")
        except Exception as e:
            print(f"  Player props {sport_key} error: {e}")
            return []

    predicciones = []

    for ev in eventos:
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        hora_raw = ev.get("commence_time", "")
        try:
            hh = int(hora_raw[11:13])
            mm = int(hora_raw[14:16])
            hora_cot = f"{str((hh-5+24)%24).zfill(2)}:{str(mm).zfill(2)}"
        except Exception:
            hora_cot = "00:00"

        # Recopilar líneas de Pinnacle y mejor cuota disponible por jugador+tipo+dirección
        pinn_lines = {}   # {(jugador, tipo, dir): (linea, precio)}
        best_odds  = {}   # {(jugador, tipo, dir): (precio, casa)}

        for bm in ev.get("bookmakers", []):
            bm_key  = bm.get("key", "")
            bm_name = bm.get("title", "")
            es_pinn = bm_key == "pinnacle"

            for mkt in bm.get("markets", []):
                tipo = mkt.get("key", "")
                if tipo not in mercados:
                    continue
                for o in mkt.get("outcomes", []):
                    jugador   = o.get("description", "")
                    direction = o.get("name", "").lower()   # "over" / "under"
                    precio    = o.get("price", 0)
                    linea     = o.get("point", 0)
                    if not jugador or not precio or direction not in ("over", "under"):
                        continue
                    k = (jugador, tipo, direction)
                    if es_pinn:
                        pinn_lines[k] = (linea, precio)
                    else:
                        if k not in best_odds or precio > best_odds[k][0]:
                            best_odds[k] = (precio, bm_name)

        # Construir predicción por jugador+tipo usando Pinnacle como referencia
        procesados = set()
        for (jugador, tipo, _), (linea, _) in pinn_lines.items():
            par = (jugador, tipo)
            if par in procesados:
                continue
            procesados.add(par)

            pinn_over  = pinn_lines.get((jugador, tipo, "over"))
            pinn_under = pinn_lines.get((jugador, tipo, "under"))
            if not pinn_over or not pinn_under:
                continue

            _, p_over_precio  = pinn_over
            _, p_under_precio = pinn_under
            overround = 1/p_over_precio + 1/p_under_precio
            prob_over  = round((1/p_over_precio)  / overround * 100, 1)
            prob_under = round((1/p_under_precio) / overround * 100, 1)

            tipo_n = _PROP_NOMBRES.get(tipo, tipo)
            vbs = {}
            cuotas_entry = {
                "pinnacle_over":  round(p_over_precio,  2),
                "pinnacle_under": round(p_under_precio, 2),
            }

            for direction, prob_val in (("over", prob_over), ("under", prob_under)):
                best = best_odds.get((jugador, tipo, direction))
                if not best:
                    continue
                best_precio, best_casa = best
                ev_pct = round((prob_val/100 * best_precio - 1) * 100, 1)
                cuotas_entry[direction] = round(best_precio, 2)
                cuotas_entry[f"{direction}_casa"] = best_casa
                vbs[direction] = {
                    "value":            round(prob_val/100 * best_precio - 1, 3),
                    "ev_porcentaje":    ev_pct,
                    "ev_pinn":          ev_pct,
                    "tiene_valor":      ev_pct >= 5,
                    "tiene_valor_pinn": ev_pct >= 5,
                    "clasificacion":    "ALTO VALOR" if ev_pct >= 10 else "VALOR" if ev_pct >= 5 else "SIN VALOR",
                    "cuota":            round(best_precio, 2),
                    "casa":             best_casa,
                    "pinn_prob":        prob_val,
                }

            if not vbs:
                continue

            mejor_dir = max(vbs, key=lambda d: vbs[d]["ev_pinn"])
            mejor_vb  = vbs[mejor_dir]
            mercado_nombre = f"{'Over' if mejor_dir == 'over' else 'Under'} {linea} {tipo_n}"

            predicciones.append({
                "local":      jugador,
                "visitante":  f"{home} vs {away}",
                "liga":       f"{nombre_liga} — Props",
                "liga_code":  sport_key,
                "hora":       hora_cot,
                "partido":    f"{home} vs {away}",
                "es_player_prop": True,
                "prop_tipo":  tipo,
                "prop_linea": linea,
                "prop_jugador": jugador,
                "cuotas":     cuotas_entry,
                "probabilidades": {"over": prob_over, "under": prob_under},
                "confianza":  max(prob_over, prob_under),
                "value_bets": vbs,
                "prediccion_principal": {
                    "mercado": mercado_nombre,
                    "prob":    mejor_vb["pinn_prob"],
                    "ev":      mejor_vb["ev_pinn"],
                },
                "cuotas_reales": True,
                "cuotas_avisos": [],
                "forma_local": [], "forma_visita": [], "h2h": {}, "movimiento": None,
                "mercados_ext": {},
            })

    print(f"  Player props {nombre_liga}: {len(predicciones)} jugadores analizados")
    return predicciones


# ── ANÁLISIS MULTIDEPORTE (NBA / NHL / MLB / Tennis / NFL) ───────
def analizar_deporte_sharp(sport_key, nombre_liga):
    """
    Analiza cualquier deporte desde The Odds API usando Pinnacle como línea sharp.
    Retorna lista de predicciones en el mismo formato que reporte_del_dia().
    """
    eventos = obtener_cuotas_liga(sport_key)
    if not eventos:
        return []

    predicciones = []
    for ev in eventos:
        home     = ev.get("home_team", "")
        away     = ev.get("away_team", "")
        hora_raw = ev.get("commence_time", "")
        hora     = hora_raw[:16].replace("T", " ")

        # ── Filtro temporal: solo próximas 48 horas ─────────────────
        try:
            dt = datetime.strptime(hora_raw[:16], "%Y-%m-%dT%H:%M")
            ahora_utc = datetime.utcnow()
            if ahora_utc >= dt:
                continue  # partido ya empezó
            if dt > ahora_utc + timedelta(hours=48):
                continue  # partido demasiado lejos (NFL septiembre, etc.)
        except Exception:
            pass

        # ── Recopilar cuotas Pinnacle y mejores por mercado ──────────
        pinn_h2h     = {}
        pinn_totals  = {}   # {("Over"|"Under", punto): precio}
        pinn_spreads = {}   # {(equipo, punto): precio}
        best_h2h     = {}   # {equipo: (precio, casa)}
        best_totals  = {}   # {("Over"|"Under", punto): (precio, casa)}
        best_spreads = {}   # {(equipo, punto): (precio, casa)}

        for bm in ev.get("bookmakers", []):
            bm_key  = bm.get("key", "")
            bm_name = bm.get("title", "")
            es_pinn = bm_key == "pinnacle"
            for mkt in bm.get("markets", []):
                mk = mkt.get("key", "")
                if mk == "h2h":
                    for o in mkt.get("outcomes", []):
                        nm, pr = o["name"], o.get("price", 0)
                        if not pr: continue
                        if es_pinn:
                            pinn_h2h[nm] = pr
                        elif nm not in best_h2h or pr > best_h2h[nm][0]:
                            best_h2h[nm] = (pr, bm_name)
                elif mk == "totals":
                    for o in mkt.get("outcomes", []):
                        nm  = o.get("name", "")   # "Over" / "Under"
                        pt  = o.get("point", 0)
                        pr  = o.get("price", 0)
                        if not pr or nm not in ("Over", "Under"): continue
                        k = (nm, pt)
                        if es_pinn:
                            pinn_totals[k] = pr
                        elif k not in best_totals or pr > best_totals[k][0]:
                            best_totals[k] = (pr, bm_name)
                elif mk == "spreads":
                    for o in mkt.get("outcomes", []):
                        nm  = o.get("name", "")
                        pt  = o.get("point", 0)
                        pr  = o.get("price", 0)
                        if not pr or not nm: continue
                        k = (nm, pt)
                        if es_pinn:
                            pinn_spreads[k] = pr
                        elif k not in best_spreads or pr > best_spreads[k][0]:
                            best_spreads[k] = (pr, bm_name)

        if len(pinn_h2h) < 2:
            continue  # sin Pinnacle moneyline no hay base de EV

        # ── Devigear h2h → probabilidades reales ─────────────────────
        overround  = sum(1/p for p in pinn_h2h.values() if p)
        pinn_probs = {k: (1/v)/overround for k, v in pinn_h2h.items() if v}

        # ── Calcular EV ───────────────────────────────────────────────
        value_bets = {}
        mejor_ev, mejor_outcome = -999, None

        def _vb_us(mk_key, mk_nombre, prob, cuota, casa):
            nonlocal mejor_ev, mejor_outcome
            if not cuota: return
            ev_pct = round((prob * cuota - 1) * 100, 1)
            value_bets[mk_key] = {
                "value": round(prob*cuota-1, 3), "ev_porcentaje": ev_pct,
                "ev_pinn": ev_pct, "tiene_valor": ev_pct >= 5,
                "tiene_valor_pinn": ev_pct >= 5,
                "clasificacion": "ALTO VALOR" if ev_pct >= 10 else "VALOR" if ev_pct >= 5 else "SIN VALOR",
                "cuota": cuota, "casa": casa,
                "pinn_prob": round(prob*100, 1), "mercado_nombre": mk_nombre,
            }
            if ev_pct > mejor_ev:
                mejor_ev, mejor_outcome = ev_pct, mk_key

        # Moneyline
        for outcome, prob in pinn_probs.items():
            best = best_h2h.get(outcome)
            if best:
                _vb_us(outcome, outcome, prob, best[0], best[1])

        # Totals (Over/Under — todas las líneas de Pinnacle)
        lineas_tot = set(pt for (_, pt) in pinn_totals)
        for pt in lineas_tot:
            p_ov = pinn_totals.get(("Over",  pt))
            p_un = pinn_totals.get(("Under", pt))
            if not p_ov or not p_un: continue
            s = 1/p_ov + 1/p_un
            for direction, prob in [("Over", (1/p_ov)/s), ("Under", (1/p_un)/s)]:
                best = best_totals.get((direction, pt))
                if not best: continue
                pt_str = str(pt).replace(".", "_")
                mk_key = f"{'over' if direction=='Over' else 'under'}_{pt_str}"
                mk_nombre = f"{direction} {pt}"
                _vb_us(mk_key, mk_nombre, prob, best[0], best[1])

        # Spreads (Handicap)
        spread_pts = set(abs(pt) for (_, pt) in pinn_spreads)
        for pt_abs in spread_pts:
            # Buscar el par local/visita para este punto
            par = {nm: (pt, pr) for (nm, pt), pr in pinn_spreads.items() if abs(pt) == pt_abs}
            if len(par) < 2: continue
            for nm, (pt, pr_pinn) in par.items():
                nm2 = [n for n in par if n != nm][0]
                pr2 = par[nm2][1]
                s   = 1/pr_pinn + 1/pr2
                prob = (1/pr_pinn) / s
                best = best_spreads.get((nm, pt))
                if not best: continue
                signo = "+" if pt >= 0 else ""
                mk_key    = f"spread_{nm.replace(' ','_').lower()}_{str(pt).replace('.','_').replace('-','m')}"
                mk_nombre = f"{nm} ({signo}{pt})"
                _vb_us(mk_key, mk_nombre, prob, best[0], best[1])

        if not value_bets or mejor_outcome is None:
            continue

        # ── Hora UTC + fecha COT (aritmética simple, sin strptime) ────
        hora_utc_hm = hora_raw[11:16] if len(hora_raw) >= 16 else "00:00"
        utc_h = int(hora_raw[11:13]) if len(hora_raw) >= 13 else 12
        utc_d = hora_raw[:10] if len(hora_raw) >= 10 else date.today().isoformat()
        if utc_h < 5:  # medianoche UTC → día anterior en COT
            fecha_evento = (date.fromisoformat(utc_d) - timedelta(days=1)).isoformat()
        else:
            fecha_evento = utc_d

        deporte = SPORTS_ODDS_ONLY.get(sport_key, nombre_liga)
        _SPORT_EMOJI = {"NBA":"🏀","MLB":"⚾","NHL":"🏒","NFL":"🏈"}
        sport_emoji  = _SPORT_EMOJI.get(deporte, "🏆")

        mk_nombre_principal = value_bets[mejor_outcome].get("mercado_nombre", mejor_outcome)
        predicciones.append({
            "local":        home,
            "visitante":    away,
            "liga":         nombre_liga,
            "liga_code":    sport_key,
            "deporte":      deporte,
            "deporte_emoji": sport_emoji,
            "hora":         hora_utc_hm,
            "fecha_evento": fecha_evento,
            "cuotas":       {**{o: best_h2h.get(o,(None,None))[0] for o in pinn_probs},
                             **{vb["mercado_nombre"]: vb["cuota"] for vb in value_bets.values()}},
            "probabilidades": {o: round(p*100,1) for o, p in pinn_probs.items()},
            "confianza":    round(max(pinn_probs.values())*100, 1),
            "value_bets":   value_bets,
            "prediccion_principal": {
                "mercado": mk_nombre_principal,
                "prob":    value_bets[mejor_outcome]["pinn_prob"],
                "ev":      mejor_ev,
            },
            "cuotas_reales": True,
            "cuotas_avisos": [],
            "forma_local": [], "forma_visita": [], "h2h": {}, "movimiento": None,
        })

    print(f"  {nombre_liga}: {len(predicciones)} eventos con Pinnacle")
    return predicciones


# ── ANÁLISIS DE FÚTBOL DIRECTO DESDE THE ODDS API ───────────────
def analizar_futbol_sharp(sport_key, nombre_liga):
    """
    Analiza fútbol usando The Odds API con Pinnacle como único benchmark.
    Mercados: 1X2, Over/Under (0.5‑5.5), BTTS, Doble Oportunidad,
              Draw No Bet, Handicap Asiático, Goles por equipo.
    Si un evento no tiene línea Pinnacle h2h → se descarta.
    Sin fallback. Sin Poisson. Sin api-sports.
    """
    _NOMBRES_MK = {
        "victoria_local":  "Victoria Local",
        "empate":          "Empate",
        "victoria_visita": "Victoria Visitante",
        "over05":  "Over 0.5 Goles",  "under05":  "Under 0.5 Goles",
        "over15":  "Over 1.5 Goles",  "under15":  "Under 1.5 Goles",
        "over25":  "Over 2.5 Goles",  "under25":  "Under 2.5 Goles",
        "over35":  "Over 3.5 Goles",  "under35":  "Under 3.5 Goles",
        "over45":  "Over 4.5 Goles",  "under45":  "Under 4.5 Goles",
        "over55":  "Over 5.5 Goles",  "under55":  "Under 5.5 Goles",
        "btts_si": "Ambos Marcan",    "btts_no":  "Ambos No Marcan",
        "doble_1x": "Doble Oportunidad 1X",
        "doble_x2": "Doble Oportunidad X2",
        "doble_12": "Doble Oportunidad 12",
        "dnb_local":   "Draw No Bet Local",
        "dnb_visita":  "Draw No Bet Visitante",
        "ah_l_m0_5":  "Handicap Local -0.5",   "ah_v_p0_5":  "Handicap Visitante +0.5",
        "ah_l_m1_0":  "Handicap Local -1",      "ah_v_p1_0":  "Handicap Visitante +1",
        "ah_l_m1_5":  "Handicap Local -1.5",    "ah_v_p1_5":  "Handicap Visitante +1.5",
        "ah_l_m2_0":  "Handicap Local -2",      "ah_v_p2_0":  "Handicap Visitante +2",
    }
    _GOAL_SUFFIX = {0.5:"05", 1.5:"15", 2.5:"25", 3.5:"35", 4.5:"45", 5.5:"55"}

    eventos = _fetch_odds_ext(sport_key)
    if not eventos:
        return []

    predicciones = []

    for ev in eventos:
        home     = ev.get("home_team", "")
        away     = ev.get("away_team", "")
        hora_raw = ev.get("commence_time", "")
        ev_id    = ev.get("id", "")

        # Descartar partidos ya empezados
        try:
            dt = datetime.strptime(hora_raw[:16], "%Y-%m-%dT%H:%M")
            if datetime.utcnow() >= dt:
                continue
        except Exception:
            pass

        # Hora UTC + fecha COT
        try:
            hh = int(hora_raw[11:13]);  mm = int(hora_raw[14:16])
            hora_utc = f"{hh:02d}:{mm:02d}"
            hora_cot = f"{(hh-5+24)%24:02d}:{mm:02d}"
            _dt_cot  = datetime.strptime(hora_raw[:16], "%Y-%m-%dT%H:%M") - timedelta(hours=5)
            fecha_evento = _dt_cot.strftime("%Y-%m-%d")
        except Exception:
            hora_utc = hora_cot = "00:00"
            fecha_evento = date.today().isoformat()

        # ── Recopilar líneas de Pinnacle y mejores cuotas ────────
        pinn_h2h   = {}   # {team_name: price}
        pinn_goals = {}   # {(point_float, "over"|"under"): price}
        pinn_btts  = {}   # {"yes"|"no": price}
        pinn_ah    = {}   # {(team_name, point_float): price}
        best       = {}   # {mk_key: (price, bookmaker_name)}

        for bm in ev.get("bookmakers", []):
            bm_key  = bm.get("key",   "")
            bm_name = bm.get("title", "")
            es_pinn = bm_key == "pinnacle"

            for mkt in bm.get("markets", []):
                mkey     = mkt.get("key", "")
                outcomes = mkt.get("outcomes", [])

                if mkey == "h2h":
                    for o in outcomes:
                        nm, pr = o["name"], o["price"]
                        if es_pinn:
                            pinn_h2h[nm] = pr
                        k = f"h2h_{nm}"
                        if k not in best or pr > best[k][0]:
                            best[k] = (pr, bm_name)

                elif mkey in ("totals", "alternate_totals"):
                    for o in outcomes:
                        pt = float(o.get("point", 0))
                        nm = o.get("name", "").lower()
                        pr = o["price"]
                        if es_pinn:
                            pinn_goals[(pt, nm)] = pr
                        k = f"goals_{nm}_{str(pt).replace('.','_')}"
                        if k not in best or pr > best[k][0]:
                            best[k] = (pr, bm_name)

                elif mkey == "team_totals":
                    for o in outcomes:
                        team = o.get("description", "")
                        pt   = float(o.get("point", 0))
                        nm   = o.get("name", "").lower()
                        pr   = o["price"]
                        t_k  = "local" if _match_equipos(team, home) else "visita"
                        k    = f"team_{t_k}_{nm}_{str(pt).replace('.','_')}"
                        if k not in best or pr > best[k][0]:
                            best[k] = (pr, bm_name)

                elif mkey == "btts":
                    for o in outcomes:
                        nm = o.get("name", "").lower()  # "yes" / "no"
                        pr = o["price"]
                        if es_pinn:
                            pinn_btts[nm] = pr
                        if nm not in best or pr > best[nm][0]:
                            best[nm] = (pr, bm_name)

                elif mkey == "double_chance":
                    _dc = {"1X": "doble_1x", "X2": "doble_x2", "12": "doble_12"}
                    for o in outcomes:
                        k2 = _dc.get(o.get("name", ""))
                        if k2:
                            pr = o["price"]
                            if k2 not in best or pr > best[k2][0]:
                                best[k2] = (pr, bm_name)

                elif mkey == "draw_no_bet":
                    for o in outcomes:
                        pr  = o["price"]
                        nm  = o.get("name", "")
                        k2  = "dnb_local" if nm == home else "dnb_visita" if nm == away else None
                        if k2 and (k2 not in best or pr > best[k2][0]):
                            best[k2] = (pr, bm_name)

                elif mkey in ("spreads", "alternate_spreads"):
                    for o in outcomes:
                        pt  = float(o.get("point", 0))
                        nm  = o.get("name", "")
                        pr  = o["price"]
                        if es_pinn:
                            pinn_ah[(nm, pt)] = pr
                        t_k = "l" if nm == home else "v"
                        d_k = "m" if pt < 0 else "p"
                        k   = f"ah_{t_k}_{d_k}{str(abs(pt)).replace('.','_')}"
                        if k not in best or pr > best[k][0]:
                            best[k] = (pr, bm_name)

        # Pinnacle h2h obligatorio
        if len(pinn_h2h) < 2:
            continue

        # ── Devigear Pinnacle h2h ────────────────────────────────
        or_h2h = sum(1/p for p in pinn_h2h.values() if p)
        p_h2h  = {nm: (1/pr)/or_h2h for nm, pr in pinn_h2h.items() if pr}

        cuotas     = {}
        value_bets = {}
        probs_out  = {}

        def _vb(mk, prob, best_key, ck, pinn_raw=None):
            if best_key not in best:
                return
            bp, bc = best[best_key]
            ev_pct = round((prob * bp - 1) * 100, 1)
            cuotas[ck]              = bp
            cuotas[f"{ck}_casa"]    = bc
            if pinn_raw:
                cuotas[f"pinnacle_{ck}"] = pinn_raw
            probs_out[mk] = round(prob * 100, 1)
            value_bets[mk] = {
                "value":             round(prob * bp - 1, 3),
                "ev_porcentaje":     ev_pct,
                "ev_pinn":           ev_pct,
                "tiene_valor":       ev_pct >= 5,
                "tiene_valor_pinn":  ev_pct >= 5,
                "clasificacion":     "ALTO VALOR" if ev_pct >= 10 else "VALOR" if ev_pct >= 5 else "SIN VALOR",
                "cuota":             bp,
                "casa":              bc,
                "pinn_prob":         round(prob * 100, 1),
            }

        # 1X2
        for nm, prob in p_h2h.items():
            if nm == home:
                _vb("victoria_local",  prob, f"h2h_{nm}", "1", pinn_h2h[nm])
            elif nm == away:
                _vb("victoria_visita", prob, f"h2h_{nm}", "2", pinn_h2h[nm])
            else:
                _vb("empate",          prob, f"h2h_{nm}", "X", pinn_h2h[nm])

        # Over/Under — devigear por línea
        pts_g = {}
        for (pt, nm), pr in pinn_goals.items():
            pts_g.setdefault(pt, {})[nm] = pr

        for pt, sides in pts_g.items():
            if "over" not in sides or "under" not in sides:
                continue
            s2   = 1/sides["over"] + 1/sides["under"]
            p_ov = (1/sides["over"])  / s2
            p_un = (1/sides["under"]) / s2
            sfx  = _GOAL_SUFFIX.get(pt, str(pt).replace(".", ""))
            pt_k = str(pt).replace(".", "_")
            _vb(f"over{sfx}",  p_ov, f"goals_over_{pt_k}",  f"over{sfx}",  sides["over"])
            _vb(f"under{sfx}", p_un, f"goals_under_{pt_k}", f"under{sfx}", sides["under"])

        # BTTS
        if "yes" in pinn_btts and "no" in pinn_btts:
            s2 = 1/pinn_btts["yes"] + 1/pinn_btts["no"]
            _vb("btts_si", (1/pinn_btts["yes"])/s2, "yes", "btts_si", pinn_btts["yes"])
            _vb("btts_no", (1/pinn_btts["no"])/s2,  "no",  "btts_no", pinn_btts["no"])

        # Doble Oportunidad — derivada de probs Pinnacle h2h
        p_l = probs_out.get("victoria_local",  0) / 100
        p_e = probs_out.get("empate",          0) / 100
        p_v = probs_out.get("victoria_visita", 0) / 100
        for mk2, prob2, k2 in [
            ("doble_1x", p_l + p_e, "doble_1x"),
            ("doble_x2", p_e + p_v, "doble_x2"),
            ("doble_12", p_l + p_v, "doble_12"),
        ]:
            if k2 in best and prob2 > 0:
                bp2, bc2 = best[k2]
                ev2 = round((prob2 * bp2 - 1) * 100, 1)
                cuotas[k2] = bp2;  cuotas[f"{k2}_casa"] = bc2
                probs_out[mk2] = round(prob2 * 100, 1)
                value_bets[mk2] = {
                    "value": round(prob2 * bp2 - 1, 3),
                    "ev_porcentaje": ev2, "ev_pinn": ev2,
                    "tiene_valor": ev2 >= 5, "tiene_valor_pinn": ev2 >= 5,
                    "clasificacion": "ALTO VALOR" if ev2 >= 10 else "VALOR" if ev2 >= 5 else "SIN VALOR",
                    "cuota": bp2, "casa": bc2, "pinn_prob": round(prob2 * 100, 1),
                }

        # Draw No Bet — derivada de probs Pinnacle h2h
        p_12 = p_l + p_v
        if p_12 > 0:
            _vb("dnb_local",  p_l / p_12, "dnb_local",  "dnb_local")
            _vb("dnb_visita", p_v / p_12, "dnb_visita", "dnb_visita")

        # Handicap Asiático — devigear por par (local, visita) en misma línea
        pts_ah = {}
        for (nm, pt), pr in pinn_ah.items():
            pt_abs = abs(pt)
            pts_ah.setdefault(pt_abs, {})[nm] = (pr, pt)

        for pt_abs, sides in pts_ah.items():
            names = list(sides.keys())
            if len(names) < 2:
                continue
            local_nm  = home if home in names else names[0]
            visita_nm = away if away in names else names[1]
            pr_l, _   = sides[local_nm]
            pr_v, _   = sides[visita_nm]
            s2   = 1/pr_l + 1/pr_v
            p_lh = (1/pr_l) / s2
            p_vh = (1/pr_v) / s2
            pt_k = str(pt_abs).replace(".", "_")
            _vb(f"ah_l_m{pt_k}", p_lh, f"ah_l_m{pt_k}", f"ah_l_m{pt_k}", pr_l)
            _vb(f"ah_v_p{pt_k}", p_vh, f"ah_v_p{pt_k}", f"ah_v_p{pt_k}", pr_v)

        # Goles por equipo (team_totals) — informativo, sin Pinnacle obligatorio
        for bk, (bp, bc) in best.items():
            if bk.startswith("team_"):
                cuotas[bk] = bp;  cuotas[f"{bk}_casa"] = bc

        if not value_bets:
            continue

        mejor_mk  = max(value_bets, key=lambda k: value_bets[k].get("ev_pinn") or -999)
        mejor_vb  = value_bets[mejor_mk]

        predicciones.append({
            "local":        home,
            "visitante":    away,
            "liga":         nombre_liga,
            "liga_code":    sport_key,
            "id":           ev_id,
            "hora":         hora_utc,
            "fecha_evento": fecha_evento,
            "cuotas":     cuotas,
            "probabilidades": probs_out,
            "confianza":  max(probs_out.values()) if probs_out else 0,
            "value_bets": value_bets,
            "prediccion_principal": {
                "mercado": _NOMBRES_MK.get(mejor_mk, mejor_mk),
                "prob":    mejor_vb["pinn_prob"],
                "ev":      mejor_vb["ev_pinn"],
            },
            "cuotas_reales":  True,
            "cuotas_avisos":  [],
            "sede_neutral":   False,
            "arbitro":        "",
            "forma_local":    None,
            "forma_visita":   None,
            "h2h":            None,
            "movimiento":     None,
            "mercados_ext":   {},
        })

    print(f"  {nombre_liga}: {len(predicciones)} partidos con Pinnacle")
    return predicciones


# ── GUARDAR JSON PARA EL PANEL ──────────────────────────────────
def guardar_predicciones():
    try:
        from db_clv import guardar_pick as _db_pick, inicializar as _db_init
        _db_init()
        _db_ok = True
    except Exception as _e:
        print(f"  DB CLV: {_e}")
        _db_ok = False

    # ── Fútbol: todo desde The Odds API con Pinnacle ─────────────
    print("\nAnalizando fútbol (The Odds API / Pinnacle)...")
    predicciones_futbol = []
    sport_keys_vistos   = set()
    for liga_code, sport_key in LIGAS_ODDS.items():
        if sport_key in sport_keys_vistos:
            continue
        sport_keys_vistos.add(sport_key)
        nombre_liga = _SPORT_NOMBRE.get(sport_key, sport_key)
        try:
            preds = analizar_futbol_sharp(sport_key, nombre_liga)
            predicciones_futbol.extend(preds)
        except Exception as _ex:
            print(f"  {sport_key} futbol error: {_ex}")

    reporte = {
        "fecha":           date.today().isoformat(),
        "total_partidos":  len(predicciones_futbol),
        "predicciones":    predicciones_futbol,
        "generado":        datetime.now().strftime("%H:%M:%S"),
    }
    print(f"  Fútbol: {len(predicciones_futbol)} partidos con Pinnacle")

    # ── Deportes adicionales (NBA, NHL, MLB, Tennis…) ─────────────
    print("\nAnalizando deportes adicionales...")
    for sport_key, nombre in SPORTS_ODDS_ONLY.items():
        try:
            preds_extra = analizar_deporte_sharp(sport_key, nombre)
            reporte["predicciones"].extend(preds_extra)
            reporte["total_partidos"] += len(preds_extra)
        except Exception as _ex:
            print(f"  {nombre} error: {_ex}")

    # ── Player props (NBA / NHL / MLB) ────────────────────────────
    print("\nAnalizando player props...")
    for sport_key in _PROP_MARKETS:
        nombre = SPORTS_ODDS_ONLY.get(sport_key, sport_key)
        try:
            props = analizar_player_props_sharp(sport_key, nombre)
            reporte["predicciones"].extend(props)
            reporte["total_partidos"] += len(props)
        except Exception as _ex:
            print(f"  {nombre} props error: {_ex}")

    # Filtrar predicciones: solo hoy y mañana (máximo 36h desde ahora)
    limite = datetime.utcnow() + timedelta(hours=36)
    hoy_str = date.today().isoformat()
    antes = len(reporte["predicciones"])
    reporte["predicciones"] = [
        p for p in reporte["predicciones"]
        if (p.get("fecha_evento") or hoy_str) <= (limite.date().isoformat())
    ]
    reporte["total_partidos"] = len(reporte["predicciones"])
    descartados = antes - reporte["total_partidos"]
    if descartados:
        print(f"  Filtro 36h: {descartados} predicciones futuras eliminadas (Copa Lib, Mundial, etc.)")

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2, cls=_NpEncoder)
    print(f"[OK] Predicciones guardadas: {reporte['total_partidos']} partidos")
    print(f"[OK] Fecha: {reporte['fecha']}")

    guardar_historial_cuotas(reporte)

    mejor = seleccionar_mejor_prediccion(reporte)
    if mejor:
        with open(MEJOR_PATH, "w", encoding="utf-8") as f:
            json.dump(mejor, f, ensure_ascii=False, indent=2, cls=_NpEncoder)
        print(f"[OK] Mejor prediccion: {mejor['partido']} -- {mejor['prediccion']}")

    if TELEGRAM_OK:
        # Control de duplicados: si ya se enviaron alertas hoy, no reenviar
        _sentinel = os.path.join(BASE_DIR, "logs", f"alertas_{reporte['fecha']}.sent")
        _ya_enviado = os.path.exists(_sentinel)

        print("\n[OK] Enviando alertas Telegram...")
        alto_valor_enviados = 0
        _mk2ck = {
            "victoria_local":"1","empate":"X","victoria_visita":"2",
            "over15":"over15","under15":"under15",
            "over25":"over25","under25":"under25",
            "over35":"over35","under35":"under35",
            "btts_si":"btts_si","btts_no":"btts_no",
        }

        if _ya_enviado:
            print("  Alertas de hoy ya enviadas — skip")
        else:
            # Por partido: solo enviar el mercado con mayor EV (no ambos equipos)
            for pred in reporte["predicciones"]:
                mejor_mk, mejor_vb, mejor_ev = None, None, -999
                for mercado, vb in pred["value_bets"].items():
                    if vb["clasificacion"] == "ALTO VALOR":
                        ev_pinn = vb.get("ev_pinn", vb.get("ev_porcentaje", 0)) or 0
                        if ev_pinn > mejor_ev:
                            mejor_ev = ev_pinn
                            mejor_mk, mejor_vb = mercado, vb

                if mejor_mk is None:
                    continue
                if mejor_ev <= 0:
                    continue

                ok = enviar_alerta_value_bet(pred, mejor_mk, mejor_vb)
                if ok:
                    alto_valor_enviados += 1
                    if _db_ok:
                        _ck = _mk2ck.get(mejor_mk, mejor_mk)
                        try:
                            _db_pick(
                                fecha=reporte["fecha"],
                                partido=f"{pred['local']} vs {pred['visitante']}",
                                liga=pred.get("liga", ""),
                                mercado=mejor_mk,
                                prob_modelo=pred["probabilidades"].get(mejor_mk, 50),
                                cuota_apertura=float(pred["cuotas"].get(_ck) or 0),
                                cuota_pinnacle=pred["cuotas"].get(f"pinnacle_{_ck}"),
                            )
                        except Exception:
                            pass

            if alto_valor_enviados:
                print(f"  🔥 {alto_valor_enviados} alertas ALTO VALOR enviadas")
                # Marcar como enviado para no duplicar
                open(_sentinel, "w").close()

        enviar_resumen_dia(reporte)
        print("  📋 Resumen del día enviado")

    # Actualizar web con predicciones del día
    print("\n🌐 Actualizando web...")
    _actualizar_datos_js(reporte)

    # Alertas de steam — solo en pasada de tarde (snapshot_tipo == "tarde")
    hora_actual = datetime.now().hour
    if hora_actual >= 13:
        _alertar_steam(reporte)

    # Player props — goleadores del dia al canal VIP
    try:
        from player_props import analizar_player_props, construir_mensaje_props
        from telegram_alertas import enviar_mensaje
        from config import TELEGRAM_CHAT_ID
        props_dia = analizar_player_props(reporte["predicciones"])
        msg_props = construir_mensaje_props(props_dia)
        if msg_props:
            enviar_mensaje(msg_props, chat_id=TELEGRAM_CHAT_ID)
            print("  Goleadores del dia enviados (VIP)")
    except Exception as e:
        print(f"  Player props error: {e}")

    return reporte


def _actualizar_datos_js(reporte):
    """Sube predicciones.json a GitHub. datos.js lo maneja solo auto_publicar.py."""
    import subprocess
    repo_dir = os.path.join(BASE_DIR, "..")
    try:
        subprocess.run(["git", "add", "-f", "predicciones.json", "mejor_prediccion.json"],
                       cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"auto: predicciones {date.today().isoformat()}"],
                       cwd=repo_dir, check=True, capture_output=True)
        # Pull antes de push para evitar rechazo por commits remotos más nuevos
        subprocess.run(["git", "pull", "origin", "main", "--no-rebase"],
                       cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", "main"],
                       cwd=repo_dir, check=True, capture_output=True)
        print("  GitHub actualizado (predicciones.json) ✓")
    except subprocess.CalledProcessError as e:
        print(f"  Git error: {e}")


def _alertar_steam(reporte):
    """Detecta steam moves y RLM, avisa a Yamid por Telegram."""
    try:
        from database import get_movimiento
        from telegram_alertas import enviar_aviso_yamid
    except Exception:
        return

    alertas = []
    nombres_mercado = {
        "1": "Victoria Local", "X": "Empate", "2": "Victoria Visitante",
        "over25": "Over 2.5", "under25": "Under 2.5",
        "over15": "Over 1.5", "under15": "Under 1.5", "btts_si": "Ambos Marcan",
    }
    for pred in reporte.get("predicciones", []):
        fid = pred.get("id")
        if not fid:
            continue
        try:
            mov = get_movimiento(fid)
        except Exception:
            continue
        if not mov:
            continue

        partido = f"{pred['local']} vs {pred['visitante']}"
        lineas = []
        for mk, info in mov.items():
            if not isinstance(info, dict):
                continue
            cambio = info.get("cambio_pct", 0)
            if abs(cambio) < 8:
                continue
            tipo = info.get("tipo", "")
            emoji = "⚡ STEAM" if tipo == "steam" else ("🔄 RLM" if tipo == "rlm" else "📉")
            nombre = nombres_mercado.get(mk, mk)
            ap = info.get("apertura", "?")
            ta = info.get("tarde", "?")
            lineas.append(f"  {emoji} {nombre}: {ap} → {ta} ({cambio:+.1f}%)")

        if lineas:
            alertas.append(f"⚽ <b>{partido}</b>\n" + "\n".join(lineas))

    if not alertas:
        print("  Sin steam moves significativos")
        return

    texto = (
        f"⚡ <b>SharpIQ — Movimiento de Línea</b>\n"
        f"🕐 Pasada de tarde — {date.today().isoformat()}\n\n"
        + "\n\n".join(alertas) +
        "\n\n<i>Cuotas que cayeron ≥8% = dinero profesional entrando</i>"
    )
    ok = enviar_aviso_yamid(texto)
    print(f"  Steam alert: {'OK' if ok else 'FALLO'} ({len(alertas)} partido/s)")

def clasificar_tiers(reporte):
    """
    Selecciona los 3 picks del día según jerarquía de tiers.
    SEGURO:     Over 1.5 goles, prob >= 68%, cuota >= 1.28
    PRINCIPAL:  Draw No Bet local o visitante, prob >= 58%, cuota >= 1.55
    ALTO VALOR: EV vs Pinnacle >= 8%, cuota >= 1.90
    Nunca repite partido entre tiers.
    """
    SEGURO_MIN_PROB  = 68.0
    SEGURO_MIN_CUOTA = 1.28
    PRINC_MIN_PROB   = 58.0
    PRINC_MIN_CUOTA  = 1.55
    AV_MIN_EV        = 8.0
    AV_MIN_CUOTA     = 1.90

    _CK = {
        "victoria_local":"1","empate":"X","victoria_visita":"2",
        "over05":"over05","under05":"under05",
        "over15":"over15","under15":"under15",
        "over25":"over25","under25":"under25",
        "over35":"over35","under35":"under35",
        "over45":"over45","under45":"under45",
        "over55":"over55","under55":"under55",
        "btts_si":"btts_si","btts_no":"btts_no",
        "doble_1x":"doble_1x","doble_x2":"doble_x2","doble_12":"doble_12",
        "dnb_local":"dnb_local","dnb_visita":"dnb_visita",
        "ah_l_m0_5":"ah_l_m0_5","ah_v_p0_5":"ah_v_p0_5",
        "ah_l_m1_0":"ah_l_m1_0","ah_v_p1_0":"ah_v_p1_0",
        "ah_l_m1_5":"ah_l_m1_5","ah_v_p1_5":"ah_v_p1_5",
        "ah_l_m2_0":"ah_l_m2_0","ah_v_p2_0":"ah_v_p2_0",
    }
    _NOMBRES = {
        "victoria_local":  "Victoria Local",
        "empate":          "Empate",
        "victoria_visita": "Victoria Visitante",
        "over05":  "Over 0.5 Goles",  "under05":  "Under 0.5 Goles",
        "over15":  "Over 1.5 Goles",  "under15":  "Under 1.5 Goles",
        "over25":  "Over 2.5 Goles",  "under25":  "Under 2.5 Goles",
        "over35":  "Over 3.5 Goles",  "under35":  "Under 3.5 Goles",
        "over45":  "Over 4.5 Goles",  "under45":  "Under 4.5 Goles",
        "over55":  "Over 5.5 Goles",  "under55":  "Under 5.5 Goles",
        "btts_si": "Ambos Marcan",    "btts_no":  "Ambos No Marcan",
        "doble_1x":"Doble Oportunidad 1X",
        "doble_x2":"Doble Oportunidad X2",
        "doble_12":"Doble Oportunidad 12",
        "dnb_local":  "Draw No Bet Local",
        "dnb_visita": "Draw No Bet Visitante",
        "ah_l_m0_5":  "Handicap Local -0.5",   "ah_v_p0_5":  "Handicap Visitante +0.5",
        "ah_l_m1_0":  "Handicap Local -1",      "ah_v_p1_0":  "Handicap Visitante +1",
        "ah_l_m1_5":  "Handicap Local -1.5",    "ah_v_p1_5":  "Handicap Visitante +1.5",
        "ah_l_m2_0":  "Handicap Local -2",      "ah_v_p2_0":  "Handicap Visitante +2",
    }

    seguro_pool = []
    principal_pool = []
    alto_pool = []

    for pred in reporte.get("predicciones", []):
        probs      = pred.get("probabilidades", {})
        cuotas     = pred.get("cuotas", {})
        vbs        = pred.get("value_bets", {})
        liga_code  = str(pred.get("liga_code", ""))
        es_futbol  = liga_code not in SPORTS_ODDS_ONLY

        # Descartar fútbol sin cuotas reales de Pinnacle — predicciones con
        # λ fallback son esencialmente aleatorias y no deben publicarse
        if es_futbol and not pred.get("cuotas_reales"):
            continue

        if es_futbol:
            # ── SEGURO: Over 1.5 goles ───────────────────────────
            prob_o15  = probs.get("over15", 0)
            cuota_o15 = cuotas.get("over15")
            if prob_o15 >= SEGURO_MIN_PROB and cuota_o15 and float(cuota_o15) >= SEGURO_MIN_CUOTA:
                seguro_pool.append({
                    "pred":           pred,
                    "mercado":        "over15",
                    "mercado_nombre": "Over 1.5 Goles",
                    "prob":           prob_o15,
                    "cuota":          float(cuota_o15),
                    "score":          prob_o15 + float(cuota_o15) * 5,
                })

            # ── PICK PRINCIPAL: Draw No Bet ──────────────────────
            for dnb_k in ("dnb_local", "dnb_visita"):
                prob_dnb  = probs.get(dnb_k, 0)
                cuota_dnb = cuotas.get(dnb_k)
                if prob_dnb >= PRINC_MIN_PROB and cuota_dnb and float(cuota_dnb) >= PRINC_MIN_CUOTA:
                    principal_pool.append({
                        "pred":           pred,
                        "mercado":        dnb_k,
                        "mercado_nombre": _NOMBRES[dnb_k],
                        "prob":           prob_dnb,
                        "cuota":          float(cuota_dnb),
                        "score":          prob_dnb + float(cuota_dnb) * 10,
                    })

        elif pred.get("es_player_prop"):
            # ── Player props: Over con alta probabilidad ──────────
            for direction in ("over", "under"):
                prob_val  = probs.get(direction, 0)
                cuota_val = cuotas.get(direction)
                if not cuota_val:
                    continue
                mercado_nombre = pred["prediccion_principal"]["mercado"]
                if prob_val >= SEGURO_MIN_PROB and float(cuota_val) >= SEGURO_MIN_CUOTA:
                    seguro_pool.append({
                        "pred":           pred,
                        "mercado":        direction,
                        "mercado_nombre": mercado_nombre,
                        "prob":           prob_val,
                        "cuota":          float(cuota_val),
                        "score":          prob_val + float(cuota_val) * 5,
                    })
                if prob_val >= PRINC_MIN_PROB and float(cuota_val) >= PRINC_MIN_CUOTA:
                    principal_pool.append({
                        "pred":           pred,
                        "mercado":        direction,
                        "mercado_nombre": mercado_nombre,
                        "prob":           prob_val,
                        "cuota":          float(cuota_val),
                        "score":          prob_val + float(cuota_val) * 10,
                    })

        else:
            # ── SEGURO otros deportes: favorito moneyline ≥ 68% ──
            for team, prob_val in probs.items():
                cuota_val = cuotas.get(team)
                if not cuota_val:
                    continue
                if prob_val >= SEGURO_MIN_PROB and float(cuota_val) >= SEGURO_MIN_CUOTA:
                    seguro_pool.append({
                        "pred":           pred,
                        "mercado":        team,
                        "mercado_nombre": f"Gana {team}",
                        "prob":           prob_val,
                        "cuota":          float(cuota_val),
                        "score":          prob_val + float(cuota_val) * 5,
                    })

            # ── PRINCIPAL otros deportes: moneyline ≥ 58% ────────
            for team, prob_val in probs.items():
                cuota_val = cuotas.get(team)
                if not cuota_val:
                    continue
                if prob_val >= PRINC_MIN_PROB and float(cuota_val) >= PRINC_MIN_CUOTA:
                    principal_pool.append({
                        "pred":           pred,
                        "mercado":        team,
                        "mercado_nombre": f"Gana {team}",
                        "prob":           prob_val,
                        "cuota":          float(cuota_val),
                        "score":          prob_val + float(cuota_val) * 10,
                    })

        # ── ALTO VALOR: EV vs Pinnacle >= 8% (todos los deportes)
        for mk, vb in vbs.items():
            if not vb:
                continue
            ev_p = vb.get("ev_pinn")
            if ev_p is None or ev_p < AV_MIN_EV:
                continue
            ck = _CK.get(mk, mk)          # fallback: clave = nombre del equipo
            cuota_v = cuotas.get(ck)
            if not cuota_v or float(cuota_v) < AV_MIN_CUOTA:
                continue
            nombre_mk = _NOMBRES.get(mk) or (f"Gana {mk}" if not es_futbol else mk)
            alto_pool.append({
                "pred":           pred,
                "mercado":        mk,
                "mercado_nombre": nombre_mk,
                "prob":           probs.get(mk, vb.get("pinn_prob", 0)),
                "cuota":          float(cuota_v),
                "ev_pinn":        ev_p,
                "score":          ev_p,
            })

    seguro_pool.sort(key=lambda x: x["score"], reverse=True)
    principal_pool.sort(key=lambda x: x["score"], reverse=True)
    alto_pool.sort(key=lambda x: x["score"], reverse=True)

    usados = set()

    def _pick(pool):
        for c in pool:
            k = f"{c['pred']['local']} vs {c['pred']['visitante']}"
            if k not in usados:
                usados.add(k)
                return c
        return None

    # Orden: ALTO VALOR primero para no "desperdiciar" el mejor partido
    alto_valor = _pick(alto_pool)
    principal  = _pick(principal_pool)
    seguro     = _pick(seguro_pool)

    return {"seguro": seguro, "principal": principal, "alto_valor": alto_valor}


if __name__ == "__main__":
    print("🔮 SharpIQ — Motor de Predicciones")
    print("=" * 50)
    reporte = guardar_predicciones()

    _SE2 = {"NBA":"🏀","MLB":"⚾","NHL":"🏒","NFL":"🏈"}
    print("\n📊 PREDICCIONES DEL DÍA:")
    for pred in reporte["predicciones"]:
        probs  = pred['probabilidades']
        deporte = pred.get("deporte","").upper()
        emoji  = pred.get("deporte_emoji") or _SE2.get(deporte, "⚽")
        # Hora UTC → COT para mostrar en terminal
        try:
            hh_u = int(pred['hora'][:2])
            mm_u = pred['hora'][3:5]
            hora_cot_str = f"{(hh_u-5+24)%24:02d}:{mm_u} COT"
        except Exception:
            hora_cot_str = pred['hora']
        fecha_ev = pred.get('fecha_evento', '')
        print(f"\n{emoji} {pred['liga']} | {hora_cot_str}  {fecha_ev}")
        print(f"   {pred['local']} vs {pred['visitante']}")
        pred_p = pred['prediccion_principal']
        ev_val = pred_p.get('ev')
        ev_str = f"EV {'+' if (ev_val or 0)>=0 else ''}{ev_val}%" if ev_val is not None else "sin EV"
        print(f"   → {pred_p['mercado']} ({pred_p['prob']}% prob, {ev_str})")
        for mk, vb in pred["value_bets"].items():
            if vb.get("ev_pinn", 0) > 0:
                nombre = vb.get("mercado_nombre", mk)
                cuota  = vb.get("cuota", "")
                casa   = f" [{vb.get('casa','')}]" if vb.get("casa") else ""
                print(f"   💰 {nombre} @ {cuota}{casa} → EV: +{vb['ev_pinn']}% [{vb['clasificacion']}]")
