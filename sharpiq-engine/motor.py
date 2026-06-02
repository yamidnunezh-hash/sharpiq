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
import logging
import numpy as np

class _NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):  return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)):    return bool(obj)
        if isinstance(obj, np.ndarray):     return obj.tolist()
        return super().default(obj)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, date, timedelta, timezone
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


def _setup_logger():
    """Logger que escribe en logs/motor_YYYY-MM-DD.log y en consola simultáneamente."""
    from datetime import date as _d
    log_dir  = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"motor_{_d.today().isoformat()}.log")
    lg = logging.getLogger("sharpiq.motor")
    if not lg.handlers:  # evitar duplicar handlers si se reimporta el módulo
        lg.setLevel(logging.DEBUG)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        lg.addHandler(fh)
        lg.addHandler(ch)
        lg.propagate = False
    return lg

LOG = _setup_logger()


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
    "Macara": 1155,
    "UCV": 2840,
    "UCV FC": 2840,
    "CA Juventud": 2353,
    "Juventud": 2353,
    "1. FC Heidenheim": 180,
    "1. FC Köln": 192,
    "1899 Hoffenheim": 167,
    "2 de Mayo": 2140,
    "A. Italiano": 2329,
    "Aberdeen": 252,
    "AC Milan": 489,
    "ADO Den Haag": 198,
    "ADT": 10492,
    "AEK Athens FC": 575,
    "AEK Larnaca": 614,
    "AIK Stockholm": 377,
    "Ajax": 194,
    "Aktobe": 4563,
    "Al Khaleej Saihat": 2928,
    "Al Kholood": 10509,
    "Al Najma": 2992,
    "Al Okhdood": 2977,
    "Al Orubah": 2961,
    "Al Riyadh": 10511,
    "Al Shabab": 2940,
    "Al Taawon": 2936,
    "Al Wehda Club": 2937,
    "Al-Ahli Jeddah": 2929,
    "Al-Ettifaq": 2934,
    "Al-Fateh": 2931,
    "Al-Fayha": 2944,
    "Al-Hazm": 2945,
    "Al-Hilal Saudi FC": 2932,
    "Al-Ittihad FC": 2938,
    "Al-Nassr": 2939,
    "Al-Qadisiyah FC": 2933,
    "Al-Raed": 2935,
    "Alaves": 542,
    "Albirex Niigata": 311,
    "Aldosivi": 463,
    "Alianza Lima": 2553,
    "Alianza Valledupar": 1141,
    "Almere City FC": 419,
    "Alverca": 4724,
    "Always Ready": 3700,
    "Amazonas": 10862,
    "America de Cali": 1138,
    "America Mineiro": 125,
    "Anderlecht": 554,
    "Angers": 77,
    "Apoel Nicosia": 2247,
    "Ararat-Armenia": 3683,
    "Araz": 11238,
    "Arda Kardzhali": 1430,
    "Argentinos JRS": 458,
    "Aris": 3408,
    "Aris Thessalonikis": 1123,
    "Arouca": 240,
    "Arsenal": 42,
    "AS Roma": 497,
    "Asan Mugunghwa": 2753,
    "Aston Villa": 66,
    "Atalanta": 499,
    "Athletic Bilbao": 531,
    "Athletic Club": 13975,
    "Athletic Club (MG)": 13975,
    "Atlanta United FC": 1608,
    "Atlas": 2283,
    "Atletico Goianiense": 144,
    "Atletico Grau": 2564,
    "Atletico Madrid": 530,
    "Atletico Nacional": 1137,
    "Atletico Paranaense": 134,
    "Atletico San Luis": 2314,
    "Atletico Tucuman": 455,
    "Atletico-MG": 1062,
    "Atlètic Club d'Escaldes": 3345,
    "Aucas": 1156,
    "Auda": 4135,
    "Aurora": 3637,
    "Austin": 16489,
    "Austria Vienna": 601,
    "Auxerre": 108,
    "Avai": 145,
    "Avispa Fukuoka": 316,
    "AVS": 21595,
    "AZ Alkmaar": 201,
    "B36 Torshavn": 678,
    "Bahia": 118,
    "Bala Town": 352,
    "Ballkani": 12733,
    "Banfield": 449,
    "Banga": 3858,
    "Baník Ostrava": 3713,
    "Barcelona": 529,
    "Barcelona SC": 1152,
    "Barracas Central": 2432,
    "Bayer Leverkusen": 168,
    "Bayern": 157,
    "Bayern München": 157,
    "Başakşehir": 564,
    "Beitar Jerusalem": 657,
    "Belgrano Cordoba": 440,
    "Benfica": 211,
    "Beşiktaş": 549,
    "BFC Daugavpils": 4149,
    "Birkirkara": 2277,
    "Birmingham": 54,
    "BK Hacken": 367,
    "Blackburn": 67,
    "Blooming": 3701,
    "Boavista": 222,
    "Boca": 451,
    "Boca Juniors": 451,
    "Bodo/Glimt": 327,
    "Bologna": 500,
    "Bolívar": 3702,
    "Borac Banja Luka": 3364,
    "Borussia Dortmund": 165,
    "Borussia Mönchengladbach": 163,
    "Boston River": 2361,
    "Botafogo": 120,
    "Botafogo SP": 2618,
    "Botev Plovdiv": 634,
    "Bournemouth": 35,
    "Brann": 319,
    "Bravo": 4359,
    "Breidablik": 276,
    "Brentford": 55,
    "Brighton": 51,
    "Bristol City": 56,
    "Brondby": 407,
    "Brusque": 1211,
    "BSC Young Boys": 565,
    "Bucaramanga": 1131,
    "Bucheon FC 1995": 2745,
    "Buducnost Podgorica": 579,
    "Burnley": 44,
    "Caernarfon Town": 356,
    "Cagliari": 490,
    "Cambuur": 420,
    "Carabobo FC": 2810,
    "Caracas FC": 2808,
    "Cardiff": 43,
    "Casa Pia": 4716,
    "Ceara": 129,
    "Celje": 4360,
    "Celta Vigo": 538,
    "Celtic": 247,
    "Central Cordoba de Santiago": 1065,
    "Cercle Brugge": 741,
    "Cerezo Osaka": 291,
    "Cerro Largo": 2369,
    "Cerro Porteno": 1176,
    "Cesar Vallejo": 2541,
    "CF Montreal": 1614,
    "CF Pachuca": 2292,
    "CFR 1907 Cluj": 2246,
    "Chapecoense-sc": 132,
    "Charleroi": 736,
    "Charlotte": 18310,
    "Charlton": 1335,
    "Chelsea": 49,
    "Cherno More Varna": 851,
    "Chicago Fire": 1607,
    "Chico": 1132,
    "Chivas": 2278,
    "Cienciano": 2562,
    "Cliftonville FC": 2266,
    "Club America": 2287,
    "Club Brugge KV": 569,
    "Club Guarani": 1174,
    "Club Nacional": 2356,
    "Club Queretaro": 2290,
    "Club Tijuana": 2280,
    "Cobreloa": 2332,
    "Cobresal": 2331,
    "Colo Colo": 2315,
    "Colorado Rapids": 1610,
    "Columbus Crew": 1613,
    "Como": 895,
    "Consadole Sapporo": 279,
    "Coquimbo Unido": 2330,
    "Corinthians": 131,
    "Coritiba": 147,
    "Corvinul Hunedoara": 20034,
    "Coventry": 1346,
    "CRB": 146,
    "Cremonese": 520,
    "Criciuma": 140,
    "Crusaders FC": 697,
    "Cruz Azul": 2295,
    "Cruzeiro": 135,
    "Crystal Palace": 52,
    "CSKA 1948": 1426,
    "Cuiaba": 1193,
    "Cusco": 10013,
    "D. La Serena": 2341,
    "Daegu FC": 2747,
    "Daejeon Citizen": 2750,
    "Damac": 2956,
    "Danubio": 2352,
    "DC United": 1615,
    "De Graafschap": 199,
    "Defensa Y Justicia": 442,
    "Defensor Sporting": 2350,
    "Delfin SC": 1149,
    "Den Bosch": 421,
    "Deportes Copiapo": 2343,
    "Deportes Iquique": 2319,
    "Deportes Limache": 16730,
    "Deportes Tolima": 1142,
    "Deportivo Cali": 1127,
    "Deportivo Cuenca": 1154,
    "Deportivo Garcilaso": 20960,
    "Deportivo La Guaira": 2813,
    "Deportivo Pasto": 1126,
    "Deportivo Pereira": 1462,
    "Deportivo Riestra": 476,
    "Deportivo Tachira FC": 2807,
    "Derby": 69,
    "Derry City": 670,
    "Dečić": 3745,
    "Dila": 3499,
    "DIM": 1128,
    "Dinamo Batumi": 705,
    "Dinamo Brest": 386,
    "Dinamo Minsk": 394,
    "Dinamo Tbilisi": 2262,
    "Dinamo Tirana": 3326,
    "Dinamo Zagreb": 620,
    "Djurgardens IF": 364,
    "Dnipro-1": 3623,
    "Dordrecht": 409,
    "Drita": 14281,
    "Dunajska Streda": 2257,
    "Dundee Utd": 1386,
    "Dungannon Swifts": 5351,
    "Dynamo Kyiv": 572,
    "Egnatia Rrogozhinë": 3327,
    "Eintracht Frankfurt": 169,
    "El Nacional": 1150,
    "Elche": 797,
    "Empoli": 511,
    "Envigado": 1129,
    "Espanyol": 540,
    "Estoril": 230,
    "Estrela": 15130,
    "Estudiantes L.P.": 450,
    "Everton": 45,
    "Everton de Vina": 2325,
    "Excelsior": 196,
    "F91 Dudelange": 578,
    "Fagiano Okayama": 310,
    "Famalicao": 242,
    "Farense": 231,
    "FBC Melgar": 2554,
    "FC Anyang": 2748,
    "FC Astana": 562,
    "FC Augsburg": 170,
    "FC Basel 1893": 551,
    "FC Cincinnati": 2242,
    "FC Copenhagen": 400,
    "FC Dallas": 1597,
    "FC Differdange 03": 684,
    "FC Isloch Minsk R.": 391,
    "FC Juarez": 2298,
    "FC Levadia Tallinn": 2273,
    "FC Lugano": 606,
    "FC Midtjylland": 397,
    "FC Noah": 3684,
    "FC Porto": 212,
    "FC Santa Coloma": 591,
    "FC Seoul": 2766,
    "FC ST. Gallen": 1011,
    "FC St. Pauli": 186,
    "FC Tokyo": 292,
    "FC Urartu": 2276,
    "FC Vaduz": 660,
    "FC Volendam": 416,
    "FC Zurich": 783,
    "FCSB": 559,
    "Fehérvár FC": 610,
    "Fenerbahçe": 611,
    "Ferencvarosi TC": 651,
    "Ferroviária": 7826,
    "Feyenoord": 209,
    "Fiorentina": 502,
    "FK Crvena Zvezda": 598,
    "FK Košice": 10534,
    "FK Liepaja": 661,
    "FK Partizan": 573,
    "FK Rabotnicki": 663,
    "FK Sarajevo": 679,
    "FK Tobol Kostanay": 2259,
    "FK Zalgiris Vilnius": 586,
    "Flamengo": 127,
    "Flora Tallinn": 687,
    "Floriana": 4625,
    "Fluminense": 124,
    "Fortaleza": 154,
    "Fortaleza EC": 154,
    "Fortaleza FC": 1147,
    "Fortuna Sittard": 205,
    "Fredrikstad": 2149,
    "FSV Mainz 05": 164,
    "Fulham": 36,
    "Galatasaray": 645,
    "Gamba Osaka": 293,
    "Gangwon FC": 2746,
    "GAP Connah S Quay FC": 357,
    "Genk": 742,
    "Genoa": 495,
    "Gent": 631,
    "Getafe": 546,
    "GIL Vicente": 762,
    "Gimcheon Sangmu FC": 2768,
    "Gimnasia L.P.": 434,
    "Girona": 547,
    "GO Ahead Eagles": 410,
    "Godoy Cruz": 439,
    "Goias": 151,
    "Gremio": 130,
    "Groningen": 202,
    "Guadalajara Chivas": 2278,
    "Gualberto Villarroel SJ": 22266,
    "Guarani Campinas": 138,
    "Guimaraes": 224,
    "Gwangju FC": 2759,
    "Gyori ETO FC": 2402,
    "Hamburger SV": 175,
    "Hammarby FF": 363,
    "Hamrun Spartans": 4626,
    "Hapoel Beer Sheva": 563,
    "Haverfordwest County AFC": 2194,
    "HB Torshavn": 4133,
    "Heart Of Midlothian": 254,
    "Heerenveen": 210,
    "Hegelmann Litauen": 3861,
    "Hellas Verona": 504,
    "Heracles": 206,
    "Hibernian": 249,
    "Hibernians": 3884,
    "HJK Helsinki": 649,
    "HNK Hajduk Split": 608,
    "HNK Rijeka": 561,
    "Holstein Kiel": 191,
    "Houston Dynamo": 1600,
    "Huachipato": 2328,
    "Hull City": 64,
    "Huracan": 445,
    "IDV": 1153,
    "IF Elfsborg": 372,
    "Ilves": 1163,
    "Incheon United": 2763,
    "Independ. Rivadavia": 473,
    "Independiente": 453,
    "Independiente del Valle": 1153,
    "Independiente Medellin": 1128,
    "Instituto Cordoba": 478,
    "Inter": 505,
    "Inter Club d'Escaldes": 3342,
    "Inter Miami": 9568,
    "Internacional": 119,
    "Internacional de Bogota": 1134,
    "Ipswich": 57,
    "Ituano": 7779,
    "Jagiellonia": 336,
    "Jaguares": 1133,
    "Jeju United FC": 2761,
    "Jeonbuk Motors": 2762,
    "Jorge Wilstermann": 3705,
    "Jubilo Iwata": 280,
    "Junior": 1135,
    "Juventude": 152,
    "Juventus": 496,
    "KA Akureyri": 272,
    "Kairat Almaty": 664,
    "Kalju Nomme": 662,
    "Kashima": 290,
    "Kashiwa Reysol": 281,
    "Kauno Žalgiris": 3872,
    "Kawasaki Frontale": 294,
    "KI Klaksvik": 701,
    "Kilmarnock": 250,
    "Koper": 4374,
    "Kryvbas KR": 6489,
    "KuPS": 1165,
    "Kyoto Sanga": 302,
    "La Fiorita": 2249,
    "Lanus": 446,
    "Larne": 5354,
    "Las Palmas": 534,
    "Lask Linz": 1026,
    "Lausanne": 1014,
    "Lazio": 487,
    "LDU": 1158,
    "LDU de Quito": 1158,
    "LDU Quito": 1158,
    "Le Havre": 111,
    "Lecce": 867,
    "Lech Poznan": 347,
    "Leeds": 63,
    "Leganes": 537,
    "Legia Warszawa": 339,
    "Leicester": 46,
    "Lens": 116,
    "Leon": 2289,
    "Levante": 539,
    "Levski Sofia": 646,
    "Libertad Asuncion": 1179,
    "Lille": 79,
    "Lincoln Red Imps FC": 667,
    "Linfield": 583,
    "Liverpool": 40,
    "Liverpool Montevideo": 2358,
    "Llaneros": 1464,
    "Llapi": 14395,
    "Lorient": 97,
    "Los Angeles FC": 1616,
    "Los Angeles Galaxy": 1605,
    "Ludogorets": 566,
    "Luton": 1359,
    "Lyon": 80,
    "Maccabi Haifa": 4195,
    "Maccabi Petah Tikva": 4495,
    "Maccabi Tel Aviv": 604,
    "Machida Zelvia": 303,
    "Magpies": 16135,
    "Malisheva": 15576,
    "Mallorca": 798,
    "Malmo FF": 375,
    "Man City": 50,
    "Man United": 33,
    "Manchester City": 50,
    "Manchester United": 33,
    "Maribor": 552,
    "Marsaxlokk": 14507,
    "Marseille": 81,
    "Mazatlán": 14002,
    "Metropolitanos FC": 2825,
    "Metz": 112,
    "Middlesbrough": 70,
    "Millonarios": 1125,
    "Millwall": 58,
    "Milsami Orhei": 691,
    "Minnesota United FC": 1612,
    "Mirassol": 7848,
    "Mlada Boleslav": 640,
    "Molde": 329,
    "Monaco": 91,
    "Monagas SC": 2811,
    "Monterrey": 2282,
    "Montpellier": 82,
    "Monza": 1579,
    "Moreirense": 215,
    "Mornar": 3740,
    "Mushuc Runa SC": 1162,
    "NAC Breda": 203,
    "Nacional": 225,
    "Nacional Asuncion": 1175,
    "Nacional Potosí": 3706,
    "Nagoya Grampus": 288,
    "Nantes": 83,
    "Napoli": 492,
    "Nashville SC": 9569,
    "NEC Nijmegen": 413,
    "Necaxa": 2288,
    "Neman": 387,
    "NEOM": 10513,
    "New England Revolution": 1609,
    "New York City FC": 1604,
    "New York Red Bulls": 1602,
    "Newcastle": 34,
    "Newells Old Boys": 457,
    "Nice": 84,
    "NK Osijek": 616,
    "NK Varazdin": 1483,
    "Norwich": 71,
    "Nottingham Forest": 65,
    "Novi Pazar": 2643,
    "Novorizontino": 7834,
    "NSI Runavik": 682,
    "Nublense": 2337,
    "O'Higgins": 2320,
    "Oleksandria": 3619,
    "Olimpia": 1182,
    "Olimpija Ljubljana": 677,
    "Olympiakos Piraeus": 553,
    "Omonia Nicosia": 3402,
    "Once Caldas": 1136,
    "Operario-PR": 1223,
    "Ordabasy": 692,
    "Orense SC": 1992,
    "Orlando City SC": 1598,
    "Osasuna": 727,
    "Oviedo": 718,
    "Oxford United": 1338,
    "Pafos": 3403,
    "Paide": 3528,
    "Paks": 2390,
    "Palestino": 2318,
    "Palmeiras": 121,
    "Panathinaikos": 617,
    "Panevėžys": 3874,
    "PAOK": 619,
    "Paris FC": 114,
    "Paris Saint Germain": 85,
    "Parma": 523,
    "Partizani": 708,
    "Patriotas": 1140,
    "Paysandu": 149,
    "PEC Zwolle": 193,
    "Penarol": 2348,
    "Penybont": 2191,
    "Petrocub": 2271,
    "Philadelphia Union": 1599,
    "Pisa": 801,
    "Platense": 1064,
    "Plymouth": 1357,
    "Plzen": 567,
    "Pohang Steelers": 2764,
    "Polessya": 6496,
    "Ponte Preta": 139,
    "Portland Timbers": 1617,
    "Portsmouth": 1355,
    "Portuguesa FC": 2814,
    "Preston": 59,
    "Prishtina": 680,
    "Progres Niederkorn": 658,
    "PSG": 85,
    "PSV Eindhoven": 197,
    "Puebla": 2291,
    "Puerto Cabello": 2827,
    "Pumas": 2286,
    "Puskas Academy": 2391,
    "Pyunik Yerevan": 709,
    "Qarabag": 556,
    "QPR": 72,
    "Racing Club": 436,
    "Racing FC Union Luxembourg": 2030,
    "Racing Montevideo": 2359,
    "Radnicki 1923": 2644,
    "Raków Częstochowa": 3491,
    "Rangers": 257,
    "Rapid Vienna": 781,
    "Rayados": 2282,
    "Rayo Vallecano": 728,
    "Rayo Zuliano": 16847,
    "RB Bragantino": 794,
    "RB Leipzig": 173,
    "Real Betis": 543,
    "Real Madrid": 541,
    "Real Salt Lake": 1606,
    "Real Sociedad": 548,
    "Real Tomayapo": 15708,
    "Red Bull Salzburg": 571,
    "RED Star FC 93": 104,
    "Reims": 93,
    "Remo": 1198,
    "Rennes": 94,
    "Riga": 10124,
    "Rio Ave": 226,
    "River": 435,
    "River Plate": 435,
    "Rodez": 1301,
    "Rosario Central": 437,
    "Rosenborg": 331,
    "Ružomberok": 3549,
    "Rīgas FS": 4160,
    "Sabah FA": 13976,
    "Saburtalo": 3502,
    "Sagan Tosu": 295,
    "Saint Etienne": 1063,
    "Samsunspor": 3603,
    "San Antonio Bulo Bulo": 17760,
    "San Diego": 25484,
    "San Jose Earthquakes": 1596,
    "San Lorenzo": 460,
    "San Martin S.J.": 461,
    "Sanfrecce Hiroshima": 282,
    "Santa Clara": 227,
    "Santa Fe": 1139,
    "Santos": 128,
    "Santos Laguna": 2285,
    "Sao Paulo": 126,
    "Sarmiento Junin": 474,
    "Sassuolo": 488,
    "SC Braga": 217,
    "SC Freiburg": 160,
    "SC Paderborn 07": 185,
    "Seattle Sounders": 1595,
    "Seoul E-Land FC": 2749,
    "Servette FC": 2184,
    "Sevilla": 536,
    "Shakhtar Donetsk": 550,
    "Shamrock Rovers": 652,
    "Sheffield Utd": 62,
    "Sheffield Wednesday": 74,
    "Shelbourne": 3854,
    "Sheriff Tiraspol": 568,
    "Shimizu S-pulse": 283,
    "Shkendija": 609,
    "Shonan Bellmare": 284,
    "Sigma Olomouc": 2250,
    "Sileks": 4331,
    "Silkeborg": 2073,
    "SJK": 689,
    "Slask Wroclaw": 337,
    "Slavia Praha": 560,
    "Sliema Wanderers": 4628,
    "Slovan Bratislava": 656,
    "Southampton": 41,
    "Spaeri": 14864,
    "Sparta Praha": 628,
    "Sparta Rotterdam": 426,
    "Spartak Trnava": 1120,
    "Sport Huancayo": 2555,
    "Sport Recife": 123,
    "Sporting CP": 228,
    "Sporting Cristal": 2546,
    "Sporting Kansas City": 1611,
    "Sportivo Ameliano": 10487,
    "Sportivo Luqueno": 1183,
    "Sportivo Trinidense": 1187,
    "St Joseph S Fc": 698,
    "ST Mirren": 251,
    "St Patrick's Athl.": 3843,
    "St. Louis City": 20787,
    "Stade Brestois 29": 106,
    "Stjarnan": 275,
    "Stoke City": 75,
    "Strasbourg": 95,
    "Struga": 4346,
    "Sturm Graz": 637,
    "Sumqayıt": 5503,
    "Sunderland": 746,
    "Sutjeska": 673,
    "Suwon Bluewings": 2765,
    "Suwon City FC": 2756,
    "SV Elversberg": 1660,
    "Swansea": 76,
    "Talleres Cordoba": 456,
    "Tallinna Kalev": 3529,
    "Tecnico Universitario": 1151,
    "Telstar": 427,
    "The New Saints": 354,
    "The Strongest": 3711,
    "Tigre": 452,
    "Tigres UANL": 2279,
    "Tikveš": 4348,
    "Tirana": 694,
    "Tokyo Verdy": 306,
    "Toluca": 2281,
    "Tondela": 218,
    "Torino": 503,
    "Toronto FC": 1601,
    "Torpedo Kutaisi": 685,
    "Torpedo Zhodino": 385,
    "Torreense": 4799,
    "Tottenham": 47,
    "Toulouse": 96,
    "Trabzonspor": 998,
    "TransINVEST Vilnius": 18878,
    "Tre Fiori": 2260,
    "Tre Penne": 700,
    "Tromso": 325,
    "TSC Backa Topola": 2646,
    "Twente": 415,
    "U. Catolica": 2994,
    "U.N.A.M. - Pumas": 2286,
    "UCV": 2840,
    "Udinese": 494,
    "UE Santa Coloma": 703,
    "Ulsan Hyundai FC": 2767,
    "UNA Strassen": 2036,
    "Union Berlin": 182,
    "Union Espanola": 2321,
    "Union La Calera": 2326,
    "Union Magdalena": 1465,
    "Union Santa Fe": 441,
    "Union St. Gilloise": 1393,
    "Universidad Catolica": 1157,
    "Universidad de Chile": 2323,
    "Universitario": 2540,
    "Universitario de Vinto": 17762,
    "Universitatea Cluj": 2599,
    "Universitatea Craiova": 632,
    "Urawa": 287,
    "Utrecht": 207,
    "Valencia": 532,
    "Valladolid": 720,
    "Valur Reykjavik": 274,
    "Vancouver Whitecaps": 1603,
    "Vardar Skopje": 574,
    "Vasco": 133,
    "Vasco DA Gama": 133,
    "Velez Sarsfield": 438,
    "Velež": 3381,
    "Venezia": 517,
    "VfB Stuttgart": 172,
    "VfL Bochum": 176,
    "VfL Wolfsburg": 161,
    "Viking": 759,
    "Vikingur Gota": 580,
    "Vikingur Reykjavik": 278,
    "Vila Nova": 142,
    "Villarreal": 533,
    "Virtus": 5308,
    "Vissel Kobe": 289,
    "Vitoria": 136,
    "Vizela": 810,
    "Vllaznia Shkodër": 3339,
    "Vojvodina": 702,
    "Volta Redonda": 7814,
    "VPS": 650,
    "Waalwijk": 417,
    "Wanderers": 2360,
    "Watford": 38,
    "Werder Bremen": 162,
    "West Brom": 60,
    "West Ham": 48,
    "Willem II": 195,
    "Wisla Krakow": 338,
    "Wolfsberger AC": 1025,
    "Wolves": 39,
    "Wrexham": 1837,
    "Yokohama F. Marinos": 296,
    "Yokohama FC": 307,
    "Zeljeznicar Sarajevo": 654,
    "Zimbru": 4633,
    "Zira": 648,
    "Zrinjski": 588,
    "Águilas Doradas": 1144,
    "Šiauliai": 3870,
    "Žilina": 3554,
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
    "239": "soccer_argentina_primera_division",
    "262": "soccer_mexico_ligamx",
    "253": "soccer_usa_mls",
    "265": "soccer_chile_campeonato",
    # Liga BetPlay / Perú / Ecuador / Uruguay: no disponibles aún en The Odds API (404)
    # Se activarán cuando The Odds API los añada
    # "242": "soccer_colombia_primera_a",
    # "268": "soccer_peru_primera_division",
    # "240": "soccer_ecuador_liga_pro",
    # "341": "soccer_uruguay_primera_division",
    "1":   "soccer_fifa_world_cup",              # FIFA Mundial 2026 (junio-julio)
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
    "soccer_colombia_primera_a":               "Liga BetPlay",
    "soccer_peru_primera_division":            "Liga 1 Perú",
    "soccer_ecuador_liga_pro":                 "LigaPro Ecuador",
    "soccer_uruguay_primera_division":         "Torneo Apertura Uruguay",
    "soccer_fifa_world_cup":                   "FIFA Mundial 2026",
}

# Mapeo sport_key (The Odds API) → liga_code (API-Football) para el modelo Poisson
_SPORT_KEY_TO_LIGA_CODE = {
    "soccer_epl":                        "39",
    "soccer_spain_la_liga":              "140",
    "soccer_germany_bundesliga":         "78",
    "soccer_italy_serie_a":              "135",
    "soccer_france_ligue_one":           "61",
    "soccer_efl_champ":                  "40",
    "soccer_england_league1":            "41",
    "soccer_italy_serie_b":              "136",
    "soccer_spain_segunda_division":     "141",
    "soccer_germany_bundesliga2":        "79",
    "soccer_belgium_first_div":          "144",
    "soccer_austria_bundesliga":         "218",
    "soccer_uefa_champs_league":         "2",
    "soccer_uefa_europa_league":         "3",
    "soccer_conmebol_copa_libertadores": "13",
    "soccer_conmebol_copa_sudamericana": "11",
    "soccer_brazil_campeonato":          "71",
    "soccer_brazil_serie_b":             "72",
    "soccer_argentina_primera_division": "239",
    "soccer_mexico_ligamx":              "262",
    "soccer_chile_campeonato":           "265",
    "soccer_norway_eliteserien":         "103",
    "soccer_sweden_allsvenskan":         "113",
    "soccer_sweden_superettan":          "114",
    "soccer_japan_j_league":             "98",
    "soccer_china_superleague":          "169",
    "soccer_finland_veikkausliiga":      "244",
    "soccer_league_of_ireland":          "357",
}

# Deportes adicionales cubiertos por The Odds API (no requieren API-Football)
# El motor los analiza directo con EV vs Pinnacle.
# Claves de tenis: tournament-specific (solo la activa devolverá datos — las inactivas retornan vacío y se ignoran)
SPORTS_ODDS_ONLY = {
    # ── Basketball ───────────────────────────────────────────────
    "basketball_nba":               "NBA",
    "basketball_euroleague":        "Euroleague",
    "basketball_nba_preseason":     "NBA Preseason",
    # ── Baseball ─────────────────────────────────────────────────
    "baseball_mlb":                 "MLB",
    # ── Hockey sobre hielo ────────────────────────────────────────
    "icehockey_nhl":                "NHL",
    # ── Fútbol americano ─────────────────────────────────────────
    "americanfootball_nfl":         "NFL",
    "americanfootball_ncaaf":       "NCAA Football",
    "americanfootball_ufl":         "UFL",
    # ── Tenis ATP — Grand Slams + Masters 1000 ───────────────────
    "tennis_atp_french_open":       "ATP Roland Garros",     # mayo-junio
    "tennis_atp_wimbledon":         "ATP Wimbledon",          # junio-julio
    "tennis_atp_us_open":           "ATP US Open",            # agosto-septiembre
    "tennis_atp_madrid_open":       "ATP Madrid Open",
    # NOTA: tennis_atp_australian_open y tennis_atp_rome_open NO son keys válidas
    # en The Odds API (devuelven 404 "Unknown sport"). Si se reactivan, verificar
    # el key correcto en https://the-odds-api.com/sports antes de añadirlas.
    # ── Tenis WTA — Grand Slams + Premier ────────────────────────
    "tennis_wta_french_open":       "WTA Roland Garros",
    "tennis_wta_wimbledon":         "WTA Wimbledon",
    "tennis_wta_us_open":           "WTA US Open",
    # ── MMA / Boxeo ───────────────────────────────────────────────
    "mma_mixed_martial_arts":       "UFC / MMA",
    "boxing_boxing":                "Boxeo",
    # ── Rugby ─────────────────────────────────────────────────────
    "rugbyleague_nrl":              "NRL Rugby League",
    "rugbyunion_super_rugby":       "Super Rugby",
    # ── Cricket ──────────────────────────────────────────────────
    "cricket_ipl":                  "IPL Cricket",
    "cricket_big_bash":             "Big Bash Cricket",
    # golf_pga_tour / darts_betway_premier_league → HTTP 404 en The Odds API
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

def obtener_forma_reciente(equipo, n=5, liga_id=None):
    """Últimos N partidos: devuelve forma, ataque y defensa recientes.
    Si liga_id se especifica, filtra solo partidos de esa competición."""
    team_id = TEAM_IDS.get(equipo)
    if not team_id:
        return None
    params = {"team": team_id, "last": n, "status": "FT"}
    if liga_id:
        params["league"] = liga_id
        params["season"] = date.today().year if date.today().month >= 6 else date.today().year - 1
    data = _apifb("fixtures", params)
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

# ── CONVERSIÓN UTC → COT (fuente única de verdad) ───────────────
def _commence_a_cot(commence_iso):
    """The Odds API entrega commence_time en UTC ("2026-05-30T21:55:00Z").
    Devuelve un datetime NAIVE en hora de Colombia (COT = UTC-5), ajustando la
    FECHA correctamente al cruzar medianoche. None si no se puede parsear.

    Es la fuente única para hora_cot y fecha_evento: evita el bug histórico de
    convertir solo la hora con (hh-5)%24 sin mover el día."""
    try:
        dt_utc = datetime.strptime((commence_iso or "")[:16], "%Y-%m-%dT%H:%M")
        return dt_utc - timedelta(hours=5)
    except Exception:
        return None


# ── OBTENER PARTIDOS DEL DÍA ────────────────────────────────────
def obtener_partidos_hoy_apifb():
    """Una sola llamada trae todos los partidos del día de todas las ligas configuradas."""
    hoy = date.today().isoformat()
    data = _apifb("fixtures", {"date": hoy})
    if not data or not data.get("response"):
        return []
    partidos = []
    conteo = {}
    # Solo aceptar fixtures dentro de las próximas 48h (cubre finales/partidos 2 días adelante)
    limite_utc = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=48)
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
    # Sin datos reales (ni tabla, ni DB local). NO inventar stats en silencio:
    # se devuelven defaults marcados con _sin_datos para que el pick derivado
    # quede etiquetado NO CONFIABLE y no se publique. Ver _factor_altitud / clasificar_tiers.
    print(f"  ⚠ Sin stats reales para '{nombre}' — picks de este equipo quedan NO CONFIABLES")
    return {"ataque": 1.35, "defensa": 1.35, "forma": 0.75, "_sin_datos": True}

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
    "Junior Barranquilla":       {"ataque": 1.3, "defensa": 1.2, "forma": 0.64},
    "Club Junior":               {"ataque": 1.3, "defensa": 1.2, "forma": 0.64},
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
    # Serie A Betano 2026
    "Coritiba":                  {"ataque": 1.5, "defensa": 1.2, "forma": 0.70},
    "Coritiba FC":               {"ataque": 1.5, "defensa": 1.2, "forma": 0.70},
    # Brasileirao Serie B 2026
    "Botafogo SP":               {"ataque": 1.1, "defensa": 1.5, "forma": 0.48},
    "Botafogo Sao Paulo":        {"ataque": 1.1, "defensa": 1.5, "forma": 0.48},
    "Athletic Club Mineiro":     {"ataque": 1.3, "defensa": 1.3, "forma": 0.62},
    "Athletic Club":             {"ataque": 1.3, "defensa": 1.3, "forma": 0.62},
    "Vila Nova":                 {"ataque": 1.3, "defensa": 1.2, "forma": 0.65},
    "Vila Nova FC":              {"ataque": 1.3, "defensa": 1.2, "forma": 0.65},
    "CRB":                       {"ataque": 1.2, "defensa": 1.3, "forma": 0.60},
    "Sport Recife":              {"ataque": 1.4, "defensa": 1.2, "forma": 0.66},
    "Sport Club do Recife":      {"ataque": 1.4, "defensa": 1.2, "forma": 0.66},
    "Ceara":                     {"ataque": 1.4, "defensa": 1.2, "forma": 0.66},
    "Ceara SC":                  {"ataque": 1.4, "defensa": 1.2, "forma": 0.66},
    "Mirassol":                  {"ataque": 1.4, "defensa": 1.2, "forma": 0.68},
    "Mirassol FC":               {"ataque": 1.4, "defensa": 1.2, "forma": 0.68},
    "Goias":                     {"ataque": 1.3, "defensa": 1.3, "forma": 0.63},
    "Goias EC":                  {"ataque": 1.3, "defensa": 1.3, "forma": 0.63},
    "Paysandu":                  {"ataque": 1.2, "defensa": 1.3, "forma": 0.60},
    "Paysandu SC":               {"ataque": 1.2, "defensa": 1.3, "forma": 0.60},
    "Ituano":                    {"ataque": 1.1, "defensa": 1.4, "forma": 0.55},
    "Guarani":                   {"ataque": 1.1, "defensa": 1.4, "forma": 0.53},
    "Guarani FC":                {"ataque": 1.1, "defensa": 1.4, "forma": 0.53},
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

# Factores de corrección por liga basados en datos reales API-Football
# Metodología: se calcula el output promedio del modelo para equipos típicos de cada liga
# y se ajusta para que coincida con el promedio real de goles de la competición.
# NO es real_avg/1.35 — es real_avg_por_partido / modelo_promedio_por_partido.
#
# Datos reales (últimos 20 partidos por liga, API-Football):
#   Copa Libertadores:  1.90g/partido | Over2.5=35% | Under2.5=65%
#   Copa Sudamericana:  2.15g/partido | Over2.5=35% | Under2.5=65%
#   Brasileirao A:      3.25g/partido | Over2.5=70%  <-- modelo subestima mucho
#   Argentina Primera:  2.15g/partido | Over2.5=50%
#   Premier League:     2.80g/partido | Over2.5=55%
ESCALA_GOLES_LIGA = {
    # CONMEBOL copas: modelo sin escala da ~1.90-2.0g de promedio → alineado ✓
    # Solo se aplica corrección LEVE para partidos extremos
    "13":   0.95,   # Copa Libertadores:  real 1.90g → ajuste -5%
    "CLI":  0.95,
    "11":   1.05,   # Copa Sudamericana:  real 2.15g → ajuste +5%
    "CSA":  1.05,
    # Brasileirao: modelo sin escala da ~2.70g pero real es 3.25g → +20%
    "71":   1.20,
    "72":   1.05,
    # Otras LATAM
    "239":  0.95,   # Argentina Primera:  similar a Copa Lib
    "128":  1.00,   # Liga BetPlay Colombia
    "262":  1.00,   # Liga MX
    "265":  0.95,   # Chile Primera
    "253":  1.00,   # MLS
    # Europa — ya calibrado con PROMEDIO=1.35
    "39":  1.05, "PL":  1.05,   # Premier League ligeramente más goles
    "78":  1.10, "BL1": 1.10,   # Bundesliga alta anotación
    "135": 0.95, "SA":  0.95,
    "140": 0.95, "PD":  0.95,
    "61":  0.95, "FL1": 0.95,
    "2":   1.00, "CL":  1.00,
    "3":   1.00,
    "103": 1.10, "113": 1.10,
}

# Liga IDs CONMEBOL para filtrar forma por competición específica
_LIGAS_CONMEBOL_IDS = {"13", "11", "CLI", "CSA"}
_LIGA_CODE_TO_APIFB_ID = {
    "13": 13, "CLI": 13,
    "11": 11, "CSA": 11,
    "71": 71, "72": 72,
    "128": 128, "239": 239, "262": 262, "265": 265,
}

# Confiabilidad de la última estimación por par (local, visitante): la pone
# calcular_goles_esperados y la lee predecir_partido para etiquetar el pick.
_CONF_CACHE = {}

# ── ALTITUD (CONMEBOL) ──────────────────────────────────────────
# El estadio LOCAL en altura reduce los goles, sobre todo del visitante de
# tierra baja, que no se aclimata en 24-48h de viaje. Bandas calibradas con
# los efectos documentados sobre el total de goles (ver CLAUDE.md):
#   La Paz 3600m -25% · Cusco 3400m -20% · Quito 2850m -12% ·
#   Bogotá 2640m -8% · Medellín 1500m -2%.
# Se carga la mayor parte de la reducción sobre el visitante (el local vive ahí).
_ALTITUD_EQUIPOS = {
    # La Paz / El Alto / Potosí (~3600-4000m)
    "bolivar": 3600, "the strongest": 3600, "always ready": 4000,
    "nacional potosi": 3900,
    # Cusco (~3400m)
    "cienciano": 3400, "cusco": 3400,
    # Quito y valle de los Chillos (~2500-3200m)
    "ldu": 2850, "liga de quito": 2850, "liga deportiva universitaria": 2850,
    "el nacional": 2850, "aucas": 2850, "universidad catolica del ecuador": 2850,
    "deportivo quito": 2850, "mushuc runa": 3200,
    "independiente del valle": 2500,
    # Bogotá / Pasto (~2600-2900m)
    "millonarios": 2640, "santa fe": 2640, "la equidad": 2640, "bogota": 2640,
    "tigres fc": 2640, "deportivo pasto": 2900,
    # Tunja / Manizales (~2150-2820m)
    "patriotas": 2820, "boyaca chico": 2560, "once caldas": 2150,
    # Medellín (~1500m) — efecto leve
    "atletico nacional": 1500, "independiente medellin": 1500,
}

def _altitud_m(nombre):
    """Altitud del estadio del equipo (0 si no es equipo de altura conocido)."""
    n = nombre.lower()
    for a, b in (("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ü","u"),("ñ","n")):
        n = n.replace(a, b)
    for frag, metros in _ALTITUD_EQUIPOS.items():
        if frag in n:
            return metros
    return 0

def _factor_altitud(local, visitante, sede_neutral=False):
    """
    Factores multiplicativos (factor_local, factor_visita) por la altura del
    estadio LOCAL. El visitante de tierra baja recibe la mayor penalización;
    si el visitante también es de altura, se considera aclimatado y se suaviza.
    """
    if sede_neutral:
        return 1.0, 1.0
    alt = _altitud_m(local)
    if alt < 1200:
        return 1.0, 1.0
    if   alt >= 3500: fl, fv = 0.90, 0.62   # La Paz/Potosí  ≈ -25% total
    elif alt >= 3200: fl, fv = 0.92, 0.70   # Cusco          ≈ -20%
    elif alt >= 2750: fl, fv = 0.95, 0.80   # Quito/Pasto    ≈ -12%
    elif alt >= 2300: fl, fv = 0.97, 0.86   # Bogotá         ≈ -8%
    else:             fl, fv = 0.99, 0.96   # 1200-2300m     ≈ -2%
    # Visitante también de altura (≤800m de diferencia) → aclimatado, sufre menos
    alt_v = _altitud_m(visitante)
    if alt_v >= 2000 and (alt - alt_v) <= 800:
        fv = round(1 - (1 - fv) * 0.30, 3)
    return fl, fv


def calcular_goles_esperados(local, visitante, liga_code="", sede_neutral=False):
    stats_l = dict(get_stats_equipo(local))
    stats_v = dict(get_stats_equipo(visitante))
    # Marca de "sin datos reales": base default sin tabla ni DB local.
    sin_datos_l = stats_l.pop("_sin_datos", False)
    sin_datos_v = stats_v.pop("_sin_datos", False)

    forma_l = forma_v = None
    # ── Enriquecer con forma reciente (API-Football) ────────────
    # Para Copa Lib/Suda y ligas LATAM: filtra por la competición específica
    # para usar estadísticas del equipo EN ESA copa, no en su liga doméstica.
    if APIFOOTBALL_KEY:
        liga_apifb_id = _LIGA_CODE_TO_APIFB_ID.get(liga_code)
        forma_l = obtener_forma_reciente(local,  liga_id=liga_apifb_id)
        forma_v = obtener_forma_reciente(visitante, liga_id=liga_apifb_id)
        if not forma_l:  # fallback a todos los partidos si no hay suficientes en esa copa
            forma_l = obtener_forma_reciente(local)
        if not forma_v:
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
        "71":  1.22,   # Brasileirao Serie A
        "72":  1.20,   # Brasileirao Serie B
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

    # ── Ajuste por ALTITUD (estadio local en altura, CONMEBOL) ─────
    # Reduce los goles según la altura del estadio local; pega más al
    # visitante de tierra baja. No aplica si la sede es neutral (final).
    fa_l, fa_v = _factor_altitud(local, visitante, sede_neutral)
    if fa_l != 1.0 or fa_v != 1.0:
        goles_local  = round(goles_local  * fa_l, 3)
        goles_visita = round(goles_visita * fa_v, 3)
        print(f"    Altitud {_altitud_m(local)}m {local[-14:]}: "
              f"x{fa_l:.2f} local / x{fa_v:.2f} visita → {goles_local:.2f}g / {goles_visita:.2f}g")

    # ── Escala por liga: corrige con promedios reales de la competición ─
    # Evita que el modelo use stats domésticas sin ajustar para torneos
    # donde el promedio de goles es muy diferente (Copa Lib: 1.90g, Brasileirao: 3.25g)
    escala = ESCALA_GOLES_LIGA.get(liga_code, 1.0)
    if escala != 1.0:
        goles_local  = round(goles_local  * escala, 3)
        goles_visita = round(goles_visita * escala, 3)
        print(f"    Escala liga {liga_code}: x{escala:.3f} → {goles_local:.2f}g / {goles_visita:.2f}g")

    # ── Confiabilidad: un equipo es NO CONFIABLE si su base fue default
    #    (sin tabla ni DB) Y la forma reciente de la API tampoco lo enriqueció.
    #    En ese caso el pick descansa sobre stats inventadas → no se publica.
    no_confiable = (sin_datos_l and not forma_l) or (sin_datos_v and not forma_v)
    if no_confiable:
        faltan = [t for t, sd, fm in
                  ((local, sin_datos_l, forma_l), (visitante, sin_datos_v, forma_v))
                  if sd and not fm]
        print(f"    ⚠ NO CONFIABLE {local[-12:]} vs {visitante[-12:]}: "
              f"sin datos reales para {', '.join(faltan)}")
    _CONF_CACHE[(local, visitante)] = not no_confiable

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
        _SPORTS_SOCCER = {"soccer_epl","soccer_spain_la_liga","soccer_germany_bundesliga",
                          "soccer_italy_serie_a","soccer_france_ligue_one","soccer_usa_mls",
                          "soccer_conmebol_copa_libertadores","soccer_conmebol_copa_sudamericana",
                          "soccer_brazil_campeonato","soccer_brazil_serie_b",
                          "soccer_argentina_primera_division","soccer_mexico_ligamx",
                          "soccer_colombia_primera_a","soccer_peru_primera_division",
                          "soccer_ecuador_liga_pro","soccer_uruguay_primera_division",
                          "soccer_chile_campeonato","soccer_fifa_world_cup"}
        if sport_key in _SPORTS_US:
            bookmakers = "pinnacle,draftkings,fanduel,bet365,betmgm,unibet"
            markets    = "h2h,spreads,totals"
        elif sport_key in _SPORTS_SOCCER:
            bookmakers = "pinnacle,bet365,betfair,unibet,williamhill,bwin"
            markets    = "h2h,totals,btts,double_chance,draw_no_bet"
        else:
            # Tenis y otros: solo h2h
            bookmakers = "pinnacle,bet365,betfair,unibet,williamhill,bwin"
            markets    = "h2h,totals"
        # bookmakers y regions son mutuamente exclusivos en The Odds API v4
        params = {
            "apiKey":      ODDS_API_KEY,
            "bookmakers":  bookmakers,
            "markets":     markets,
            "oddsFormat":  "decimal",
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 422 and markets != "h2h,totals":
            # LATAM/CONMEBOL leagues don't support btts/double_chance/draw_no_bet — retry with basic markets
            print(f"  Odds API {sport_key}: 422 en mercados extendidos, reintentando con h2h,totals")
            params["markets"] = "h2h,totals"
            r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            print(f"  Odds API {sport_key}: HTTP {r.status_code} — {r.text[:120]}")
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
        # IMPORTANTE: el endpoint a nivel de LIGA solo soporta los mercados
        # "featured": h2h, spreads, totals. Los mercados btts/double_chance/
        # draw_no_bet/alternate_totals SOLO existen en el endpoint por-evento
        # (/events/{id}/odds) → pedirlos aquí devuelve 422 SIEMPRE y desperdicia
        # 2 peticiones por liga. spreads = hándicap asiático para fútbol.
        # TODO: para btts/dc/dnb/alt_totals usar el endpoint por-evento (más créditos).
        _ext_markets = "h2h,totals,spreads"
        params = {
            "apiKey":      ODDS_API_KEY,
            "bookmakers":  "pinnacle,bet365,betfair,unibet,williamhill,bwin",
            "markets":     _ext_markets,
            "oddsFormat":  "decimal",
        }
        r = requests.get(url, params=params, timeout=20)
        # Fallback: alguna liga sin spreads → usar solo básicos
        if r.status_code == 422:
            print(f"  Odds ext {sport_key}: spreads no disponible, usando h2h,totals")
            params["markets"] = "h2h,totals"
            r = requests.get(url, params=params, timeout=20)
        if r.status_code != 200:
            print(f"  Odds ext {sport_key}: HTTP {r.status_code} — {r.text[:120]}")
            return []
        data = r.json()
        _cache_cuotas_ext[sport_key] = data
        restantes = r.headers.get("x-requests-remaining", "?")
        print(f"  Odds ext {sport_key}: {len(data)} eventos | Creditos: {restantes}")
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
        "pinnacle_btts_si": None, "pinnacle_btts_no": None,
        "pinnacle_doble_1x": None, "pinnacle_doble_x2": None, "pinnacle_doble_12": None,
        "pinnacle_dnb_local": None, "pinnacle_dnb_visita": None,
        "pinnacle_spread_local": None, "pinnacle_spread_visita": None,
        "spread_local": None, "spread_local_linea": None, "spread_local_casa": None,
        "spread_visita": None, "spread_visita_linea": None, "spread_visita_casa": None,
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
                        if es_pinn:
                            mejor["pinnacle_btts_si"] = round(o["price"], 2)
                        if mejor["btts_si"] is None or o["price"] > mejor["btts_si"]:
                            mejor["btts_si"] = round(o["price"], 2); mejor["btts_si_casa"] = bm_name
                    elif o.get("name") == "No":
                        if es_pinn:
                            mejor["pinnacle_btts_no"] = round(o["price"], 2)
                        if mejor["btts_no"] is None or o["price"] > mejor["btts_no"]:
                            mejor["btts_no"] = round(o["price"], 2); mejor["btts_no_casa"] = bm_name

            elif key == "double_chance":
                dc_map = {"1X": "doble_1x", "X2": "doble_x2", "12": "doble_12"}
                pinn_dc_map = {"1X": "pinnacle_doble_1x", "X2": "pinnacle_doble_x2", "12": "pinnacle_doble_12"}
                for o in outcomes:
                    k2 = dc_map.get(o.get("name",""))
                    if k2:
                        if es_pinn:
                            mejor[pinn_dc_map[o["name"]]] = round(o["price"], 2)
                        if mejor[k2] is None or o["price"] > mejor[k2]:
                            mejor[k2] = round(o["price"], 2); mejor[k2+"_casa"] = bm_name

            elif key == "draw_no_bet":
                for o in outcomes:
                    if o["name"] == home:
                        if es_pinn:
                            mejor["pinnacle_dnb_local"] = round(o["price"], 2)
                        if mejor["dnb_local"] is None or o["price"] > mejor["dnb_local"]:
                            mejor["dnb_local"] = round(o["price"], 2); mejor["dnb_local_casa"] = bm_name
                    elif o["name"] == away:
                        if es_pinn:
                            mejor["pinnacle_dnb_visita"] = round(o["price"], 2)
                        if mejor["dnb_visita"] is None or o["price"] > mejor["dnb_visita"]:
                            mejor["dnb_visita"] = round(o["price"], 2); mejor["dnb_visita_casa"] = bm_name

            elif key == "spreads":
                for o in outcomes:
                    pt   = o.get("point", 0)
                    pr   = round(o["price"], 2)
                    side = "local" if o["name"] == home else "visita" if o["name"] == away else None
                    if not side:
                        continue
                    if es_pinn:
                        mejor[f"pinnacle_spread_{side}"] = pr
                    k_price = f"spread_{side}"
                    if mejor[k_price] is None or pr > mejor[k_price]:
                        mejor[k_price] = pr
                        mejor[f"spread_{side}_linea"] = pt
                        mejor[f"spread_{side}_casa"]  = bm_name

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
            pl = (1/pinn1) / s3
            px = (1/pinnX) / s3
            pv = (1/pinn2) / s3
            pinn_probs["victoria_local"]  = pl
            pinn_probs["empate"]          = px
            pinn_probs["victoria_visita"] = pv
            # Derivar Double Chance y DNB de Pinnacle 1x2
            pinn_probs["doble_1x"]   = pl + px
            pinn_probs["doble_x2"]   = px + pv
            pinn_probs["doble_12"]   = pl + pv
            if (pl + pv) > 0:
                pinn_probs["dnb_local"]  = pl / (pl + pv)
                pinn_probs["dnb_visita"] = pv / (pl + pv)
        # Totals: Over/Under a múltiples líneas
        for lim_str in ["15", "25", "35"]:
            po = cuotas.get(f"pinnacle_over{lim_str}")
            pu = cuotas.get(f"pinnacle_under{lim_str}")
            if po and pu:
                s2 = 1/po + 1/pu
                pinn_probs[f"over{lim_str}"]  = (1/po) / s2
                pinn_probs[f"under{lim_str}"] = (1/pu) / s2
        # BTTS directo de Pinnacle si está disponible
        pb_si = cuotas.get("pinnacle_btts_si")
        pb_no = cuotas.get("pinnacle_btts_no")
        if pb_si and pb_no:
            s2 = 1/pb_si + 1/pb_no
            pinn_probs["btts_si"] = (1/pb_si) / s2
            pinn_probs["btts_no"] = (1/pb_no) / s2
        # Double Chance directo de Pinnacle si está disponible
        for dc in ("doble_1x", "doble_x2", "doble_12"):
            pdc = cuotas.get(f"pinnacle_{dc}")
            if pdc and dc not in pinn_probs:
                pinn_probs[dc] = 1 / pdc  # aprox sin vig para DC
        # DNB directo de Pinnacle si está disponible
        for dnb in ("dnb_local", "dnb_visita"):
            pdnb = cuotas.get(f"pinnacle_{dnb}")
            if pdnb and dnb not in pinn_probs:
                pinn_probs[dnb] = 1 / pdnb
        _pinn_ck = {
            "victoria_local": "1", "empate": "X", "victoria_visita": "2",
            "over15": "over15", "under15": "under15",
            "over25": "over25", "under25": "under25",
            "over35": "over35", "under35": "under35",
            "btts_si": "btts_si", "btts_no": "btts_no",
            "doble_1x": "doble_1x", "doble_x2": "doble_x2", "doble_12": "doble_12",
            "dnb_local": "dnb_local", "dnb_visita": "dnb_visita",
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
        "corners_over9":          "Corners Over 9.5",
        "corners_under9":         "Corners Under 9.5",
        "corners_over10":         "Corners Over 10.5",
        "corners_under10":        "Corners Under 10.5",
        "corners_over11":         "Corners Over 11.5",
        "corners_under11":        "Corners Under 11.5",
        "corners_over12":         "Corners Over 12.5",
        "corners_under12":        "Corners Under 12.5",
        "tarjetas_over3":         "Tarjetas Over 3.5",
        "tarjetas_under3":        "Tarjetas Under 3.5",
        "tarjetas_over4":         "Tarjetas Over 4.5",
        "tarjetas_under4":        "Tarjetas Under 4.5",
        "tarjetas_over5":         "Tarjetas Over 5.5",
        "tarjetas_under5":        "Tarjetas Under 5.5",
        "ah_local_menos05":       "Handicap Local -0.5",
        "ah_visita_mas05":        "Handicap Visitante +0.5",
        "ah_local_menos1":        "Handicap Local -1",
        "ah_visita_mas1":         "Handicap Visitante +1",
        "ah_local_menos15":       "Handicap Local -1.5",
        "ah_visita_mas15":        "Handicap Visitante +1.5",
        # Remates al arco del visitante
        "disp_vis_over2":         "Remates Visitante Over 2.5",
        "disp_vis_under2":        "Remates Visitante Under 2.5",
        "disp_vis_over3":         "Remates Visitante Over 3.5",
        "disp_vis_under3":        "Remates Visitante Under 3.5",
        "disp_vis_over4":         "Remates Visitante Over 4.5",
        "disp_vis_under4":        "Remates Visitante Under 4.5",
        "disp_vis_over5":         "Remates Visitante Over 5.5",
        "disp_vis_under5":        "Remates Visitante Under 5.5",
        # Paradas del portero local
        "paradas_local_over2":    "Paradas Portero Local Over 2.5",
        "paradas_local_under2":   "Paradas Portero Local Under 2.5",
        "paradas_local_over3":    "Paradas Portero Local Over 3.5",
        "paradas_local_under3":   "Paradas Portero Local Under 3.5",
        "paradas_local_over4":    "Paradas Portero Local Over 4.5",
        "paradas_local_under4":   "Paradas Portero Local Under 4.5",
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
        # NO CONFIABLE si la estimación se apoyó en stats default (API sin datos).
        "confiable":  _CONF_CACHE.get((local, visitante), True),
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
        if pred.get("confiable") is False:
            continue  # stats default (API sin datos) → no es el mejor pick del día
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

    # Si no hay value bets, tomar la de mayor confianza (que sea CONFIABLE)
    _confiables = [p for p in reporte["predicciones"] if p.get("confiable") is not False]
    if not mejor and _confiables:
        pred = _confiables[0]
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
# ── Player props — requiere The Odds API Pro ($19/mes, activa 2026-06-08) ──
# Actualmente retorna HTTP 422 con el plan básico.
# Al contratar Pro, estos mercados se activarán automáticamente.
_PROP_MARKETS = {
    "basketball_nba": [
        "player_points",           # Puntos totales
        "player_rebounds",         # Rebotes
        "player_assists",          # Asistencias
        "player_threes",           # Triples anotados
        "player_points_rebounds_assists",  # Combo PRA
        "player_first_basket",     # Primer anotador
    ],
    "icehockey_nhl":  [
        "player_points",
        "player_shots_on_target",
        "player_goals",
    ],
    "baseball_mlb":   [
        "batter_hits",
        "batter_home_runs",
        "pitcher_strikeouts",
        "pitcher_outs",
    ],
}
_PROP_NOMBRES = {
    "player_points":                   "Puntos",
    "player_rebounds":                 "Rebotes",
    "player_assists":                  "Asistencias",
    "player_threes":                   "Triples",
    "player_points_rebounds_assists":  "PRA Combo",
    "player_first_basket":             "Primer Anotador",
    "player_shots_on_target":          "Tiros al Arco",
    "player_goals":                    "Goles",
    "batter_hits":                     "Hits",
    "batter_home_runs":                "Home Runs",
    "pitcher_strikeouts":              "Strikeouts",
    "pitcher_outs":                    "Outs Lanzados",
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
        # Guardar hora en UTC (convención única; el display resta 5 al mostrar)
        # + fecha_evento ya en COT desde el helper, para que nunca se desfase el día.
        hora_utc = hora_raw[11:16] if len(hora_raw) >= 16 else "00:00"
        _dt_cot  = _commence_a_cot(hora_raw)
        fecha_ev = _dt_cot.strftime("%Y-%m-%d") if _dt_cot else date.today().isoformat()

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
                "hora":       hora_utc,
                "fecha_evento": fecha_ev,
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
            ahora_utc = datetime.now(timezone.utc).replace(tzinfo=None)
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

        sharp_fb_h2h_us = {}
        _SHARP_FB_US    = {"bet365", "betfair_ex", "betfair", "betfair_ex_uk"}

        for bm in ev.get("bookmakers", []):
            bm_key  = bm.get("key", "")
            bm_name = bm.get("title", "")
            es_pinn = bm_key == "pinnacle"
            es_fb   = bm_key in _SHARP_FB_US
            for mkt in bm.get("markets", []):
                mk = mkt.get("key", "")
                if mk == "h2h":
                    for o in mkt.get("outcomes", []):
                        nm, pr = o["name"], o.get("price", 0)
                        if not pr: continue
                        if es_pinn:
                            pinn_h2h[nm] = pr
                        if es_fb and nm not in sharp_fb_h2h_us:
                            sharp_fb_h2h_us[nm] = pr
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

        # Benchmark: Pinnacle preferido; fallback a bet365/betfair
        if len(pinn_h2h) < 2:
            if len(sharp_fb_h2h_us) < 2:
                continue
            pinn_h2h = sharp_fb_h2h_us

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
            # REGLA 3 (techo de cordura, igual que en futbol/analizar_futbol_sharp): un edge
            # real vs la linea sharp (Pinnacle) rara vez supera +10%. Si lo supera, la cuota
            # es sospechosa (stale/error) -> NO se publica. Cierra el hueco del "Vegas EV +24%".
            if ev_pct > 10.0:
                print(f"    [EV>10%] descartado (US/tenis): {mk_nombre} +{ev_pct}% (sharp {round(prob*100)}% @ {cuota})")
                return
            value_bets[mk_key] = {
                "value": round(prob*cuota-1, 3), "ev_porcentaje": ev_pct,
                "ev_pinn": ev_pct, "tiene_valor": ev_pct >= 5,
                "tiene_valor_pinn": ev_pct >= 5,
                "clasificacion": "ALTO VALOR" if ev_pct >= 7 else "VALOR" if ev_pct >= 5 else "SIN VALOR",
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

        # ── Hora UTC + fecha COT (vía helper, robusto al cruzar medianoche) ──
        hora_utc_hm  = hora_raw[11:16] if len(hora_raw) >= 16 else "00:00"
        _dt_cot      = _commence_a_cot(hora_raw)
        fecha_evento = _dt_cot.strftime("%Y-%m-%d") if _dt_cot else date.today().isoformat()

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

        # Descartar partidos ya empezados o demasiado lejanos (>48h).
        # El corte va ANTES del análisis para no gastar llamadas a API-Football
        # en partidos (Mundial, finales futuras) que luego se descartan igual.
        try:
            dt = datetime.strptime(hora_raw[:16], "%Y-%m-%dT%H:%M")
            ahora_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            if ahora_utc >= dt:
                continue
            if dt > ahora_utc + timedelta(hours=48):
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
        # Fallback sharp: bet365/betfair cuando Pinnacle no tiene línea
        sharp_fb_h2h   = {}
        sharp_fb_goals = {}
        _SHARP_FB = {"bet365", "betfair_ex", "betfair", "betfair_ex_uk"}

        for bm in ev.get("bookmakers", []):
            bm_key  = bm.get("key",   "")
            bm_name = bm.get("title", "")
            es_pinn = bm_key == "pinnacle"
            es_fb   = bm_key in _SHARP_FB

            for mkt in bm.get("markets", []):
                mkey     = mkt.get("key", "")
                outcomes = mkt.get("outcomes", [])

                if mkey == "h2h":
                    for o in outcomes:
                        nm, pr = o["name"], o["price"]
                        if es_pinn:
                            pinn_h2h[nm] = pr
                        if es_fb and nm not in sharp_fb_h2h:
                            sharp_fb_h2h[nm] = pr
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
                        if es_fb and (pt, nm) not in sharp_fb_goals:
                            sharp_fb_goals[(pt, nm)] = pr
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

        # Benchmark: Pinnacle preferido; fallback a bet365/betfair
        sin_pinnacle = False
        if len(pinn_h2h) < 2:
            if len(sharp_fb_h2h) < 2:
                continue  # sin ningún benchmark sharp → descartar
            pinn_h2h   = sharp_fb_h2h
            pinn_goals = sharp_fb_goals
            sin_pinnacle = True
            print(f"  Fallback bet365/betfair: {home} vs {away}")

        # ── Devigear benchmark h2h ───────────────────────────────
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

        # ── Modelo Poisson: segunda opinión para Over/Under y BTTS ──────
        # Pinnacle es muy eficiente en 1X2 → no tocamos esos mercados.
        # Para totales y BTTS el modelo propio puede detectar valor donde
        # el mercado está menos afinado (altitud CONMEBOL, equipos poco líquidos).
        # Solo actualiza si el EV blend es MAYOR al EV Pinnacle puro.
        try:
            liga_c = _SPORT_KEY_TO_LIGA_CODE.get(sport_key, "")
            if liga_c and APIFOOTBALL_KEY:
                gl, gv = calcular_goles_esperados(home, away, liga_c)
                mp = modelo_poisson(gl, gv)
                _MODEL_MK = [
                    ("over15",  mp["over15"] /100, "goals_over_1_5",  "over15"),
                    ("under15", mp["under15"]/100, "goals_under_1_5", "under15"),
                    ("over25",  mp["over25"] /100, "goals_over_2_5",  "over25"),
                    ("under25", mp["under25"]/100, "goals_under_2_5", "under25"),
                    ("over35",  mp["over35"] /100, "goals_over_3_5",  "over35"),
                    ("under35", mp["under35"]/100, "goals_under_3_5", "under35"),
                    ("btts_si", mp["btts_si"]/100, "yes",             "btts_si"),
                    ("btts_no", mp["btts_no"]/100, "no",              "btts_no"),
                ]
                for mk_m, model_p, bk_m, ck_m in _MODEL_MK:
                    if bk_m not in best:
                        continue
                    bp_m, bc_m = best[bk_m]
                    # Blend ponderado por LIQUIDEZ del mercado: en partidos muy liquidos
                    # (Champions, top-5 europeas, Mundial) Pinnacle es casi insuperable, asi
                    # que el modelo pesa poco (evita que el blend se despegue del precio justo).
                    # En ligas poco liquidas el modelo aporta mas senal donde el mercado es blando.
                    _sk = sport_key or ""
                    if any(h in _sk for h in ("uefa_champs_league","uefa_europa_league","uefa_europa_conference","epl","spain_la_liga","germany_bundesliga","italy_serie_a","france_ligue_one","fifa_world_cup")):
                        _peso_pinn = 0.78
                    elif any(mq in _sk for mq in ("brazil_campeonato","argentina_primera","conmebol_copa_libertadores","conmebol_copa_sudamericana","usa_mls","mexico_ligamx","efl_champ","netherlands_eredivisie","portugal_primeira")):
                        _peso_pinn = 0.55
                    else:
                        _peso_pinn = 0.38
                    _EV_TOPE = 10.0  # techo de cordura: con Pinnacle, un edge real rara vez pasa de +10%
                    pinn_p_raw = probs_out.get(mk_m, 0) / 100

                    if pinn_p_raw <= 0:
                        # ── REGLA 2: sin línea de Pinnacle = sin ancla de mercado.
                        #    Se publica el pick SIN EV (prob del modelo, ev_pinn=None) en vez
                        #    de inventar un EV con el modelo puro sin validar contra el mercado.
                        value_bets[mk_m] = {
                            "value":            None,
                            "ev_porcentaje":    None,
                            "ev_pinn":          None,
                            "tiene_valor":      False,
                            "tiene_valor_pinn": False,
                            "clasificacion":    "SIN EV",
                            "cuota":            bp_m,
                            "casa":             bc_m,
                            "pinn_prob":        round(model_p * 100, 1),
                            "sin_mercado":      True,
                        }
                        probs_out[mk_m] = round(model_p * 100, 1)
                        continue

                    # ── REGLA 1: SIEMPRE usar el blend mezclado con el mercado (ya no el
                    #    máximo vs el Pinnacle puro, que sesgaba hacia el EV más inflado).
                    blend_p  = round(pinn_p_raw * _peso_pinn + model_p * (1 - _peso_pinn), 4)
                    ev_blend = round((blend_p * bp_m - 1) * 100, 1)

                    # ── REGLA 3: techo de cordura. Si tras el blend el EV sigue > +10%, el
                    #    modelo contradice al mercado de forma sospechosa → NO se publica.
                    if ev_blend > _EV_TOPE:
                        value_bets.pop(mk_m, None)
                        print(f"    ⚠ EV sospechoso descartado: {home[-12:]} vs {away[-12:]} "
                              f"{mk_m} +{ev_blend}% (modelo {round(model_p*100)}% vs mercado {round(pinn_p_raw*100)}%)")
                        continue

                    value_bets[mk_m] = {
                        "value":             round(blend_p * bp_m - 1, 3),
                        "ev_porcentaje":     ev_blend,
                        "ev_pinn":           ev_blend,
                        "tiene_valor":       ev_blend >= 5,
                        "tiene_valor_pinn":  ev_blend >= 5,
                        "clasificacion":     "ALTO VALOR" if ev_blend >= 7 else "VALOR" if ev_blend >= 5 else "SIN VALOR",
                        "cuota":             bp_m,
                        "casa":              bc_m,
                        "pinn_prob":         round(blend_p * 100, 1),
                    }
                    probs_out[mk_m] = round(blend_p * 100, 1)
        except Exception:
            pass  # falla silenciosamente — no rompe el pipeline Pinnacle

        if not value_bets:
            continue

        mejor_mk  = max(value_bets, key=lambda k: value_bets[k].get("ev_pinn") or -999)
        mejor_vb  = value_bets[mejor_mk]

        # Mercados extendidos: corners, tarjetas, remates (API-Football)
        mercados_ext = {}
        if MERCADOS_EXT_OK and APIFOOTBALL_KEY:
            try:
                mercados_ext = analizar_mercados_ext(home, away, sport_key, probs_out)
                # Agregar EV de mercados ext a value_bets para que clasificar_tiers los vea
                for mk_ext, ev_data in (mercados_ext.get("ev_ext") or {}).items():
                    if ev_data.get("tiene_valor"):
                        value_bets[mk_ext] = {
                            "ev_porcentaje":    ev_data["ev_porcentaje"],
                            "ev_pinn":          ev_data["ev_porcentaje"],
                            "tiene_valor":      True,
                            "tiene_valor_pinn": True,
                            "clasificacion":    ev_data["clasificacion"],
                            "cuota":            ev_data["cuota_ref"],
                            "casa":             "API-Football model",
                            "pinn_prob":        ev_data["prob_modelo"],
                            "mercado_nombre":   mk_ext.replace("_", " ").title(),
                        }
            except Exception as _e:
                print(f"  Mercados ext {home}: {_e}")

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
            # NO CONFIABLE solo si el modelo de fútbol corrió sobre stats default;
            # en no-fútbol (sin entrada en _CONF_CACHE) queda confiable por defecto.
            "confiable":      _CONF_CACHE.get((home, away), True),
            "sin_pinnacle":   sin_pinnacle,
            "cuotas_avisos":  [],
            "sede_neutral":   False,
            "arbitro":        "",
            "forma_local":    obtener_forma_reciente(home)  if APIFOOTBALL_KEY else None,
            "forma_visita":   obtener_forma_reciente(away)  if APIFOOTBALL_KEY else None,
            "h2h":            obtener_h2h(home, away)       if APIFOOTBALL_KEY else None,
            "movimiento":     None,
            "mercados_ext":   mercados_ext,
        })

    print(f"  {nombre_liga}: {len(predicciones)} partidos con Pinnacle")
    return predicciones


# ── GUARDAR JSON PARA EL PANEL ──────────────────────────────────
def guardar_predicciones():
    LOG.info("=== SharpIQ Motor START ===")

    # ── Fútbol: todo desde The Odds API con Pinnacle ─────────────
    LOG.info("Analizando fútbol (The Odds API / Pinnacle)...")
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
            LOG.error(f"{sport_key} futbol error: {_ex}")

    reporte = {
        "fecha":           date.today().isoformat(),
        "total_partidos":  len(predicciones_futbol),
        "predicciones":    predicciones_futbol,
        "generado":        datetime.now().strftime("%H:%M:%S"),
    }
    LOG.info(f"Fútbol: {len(predicciones_futbol)} partidos con Pinnacle")

    # ── Deportes adicionales (NBA, NHL, MLB, Tennis…) ─────────────
    LOG.info("Analizando deportes adicionales...")
    for sport_key, nombre in SPORTS_ODDS_ONLY.items():
        try:
            preds_extra = analizar_deporte_sharp(sport_key, nombre)
            reporte["predicciones"].extend(preds_extra)
            reporte["total_partidos"] += len(preds_extra)
        except Exception as _ex:
            LOG.error(f"{nombre} error: {_ex}")

    # ── Player props (NBA / NHL / MLB) ────────────────────────────
    LOG.info("Analizando player props...")
    for sport_key in _PROP_MARKETS:
        nombre = SPORTS_ODDS_ONLY.get(sport_key, sport_key)
        try:
            props = analizar_player_props_sharp(sport_key, nombre)
            reporte["predicciones"].extend(props)
            reporte["total_partidos"] += len(props)
        except Exception as _ex:
            LOG.error(f"{nombre} props error: {_ex}")

    # Filtrar predicciones: máximo 48h desde ahora (cubre finales 2 días adelante)
    limite = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=48)
    hoy_str = date.today().isoformat()
    antes = len(reporte["predicciones"])
    reporte["predicciones"] = [
        p for p in reporte["predicciones"]
        if (p.get("fecha_evento") or hoy_str) <= (limite.date().isoformat())
    ]
    reporte["total_partidos"] = len(reporte["predicciones"])
    descartados = antes - reporte["total_partidos"]
    if descartados:
        LOG.info(f"Filtro 48h: {descartados} predicciones futuras eliminadas")

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2, cls=_NpEncoder)
    LOG.info(f"Predicciones guardadas: {reporte['total_partidos']} partidos — {reporte['fecha']}")

    guardar_historial_cuotas(reporte)

    mejor = seleccionar_mejor_prediccion(reporte)
    if mejor:
        with open(MEJOR_PATH, "w", encoding="utf-8") as f:
            json.dump(mejor, f, ensure_ascii=False, indent=2, cls=_NpEncoder)
        LOG.info(f"Mejor prediccion: {mejor['partido']} -- {mejor['prediccion']}")

    # Telegram: solo resumen privado a Yamid (sin picks crudos al canal VIP)
    # Los picks del canal VIP los gestiona exclusivamente auto_publicar.py → clasificar_tiers()
    if TELEGRAM_OK:
        try:
            enviar_resumen_dia(reporte)
        except Exception as _te:
            LOG.warning(f"Resumen Telegram: {_te}")

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


_STEAM_UMBRAL = 5.0   # % de caída de cuota para considerar steam

# Caché en memoria: fixture_id → dict de steam por mercado
# Se llena en _alertar_steam y se consume en clasificar_tiers
_steam_cache: dict = {}


def _alertar_steam(reporte):
    """
    Detecta steam moves (cuota cae ≥5% vs apertura) y guarda en _steam_cache
    para que clasificar_tiers pueda usarlo como bonus de convicción.
    """
    global _steam_cache
    _steam_cache = {}

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
    # Mapa movimientos_cuotas columna → clave value_bets
    _col_to_mk = {
        "1": "victoria_local", "2": "victoria_visita", "X": "empate",
        "over25": "over25", "under25": "under25",
        "over15": "over15", "under15": "under15",
        "btts_si": "btts_si",
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
        steam_por_partido = {}
        lineas = []

        for mk, info in (mov.get("mercados") or {}).items():
            if not isinstance(info, dict):
                continue
            cambio = info.get("cambio_pct", 0)
            if abs(cambio) < _STEAM_UMBRAL:
                continue

            tipo   = "steam" if cambio <= -_STEAM_UMBRAL else "rlm"
            emoji  = "⚡ STEAM" if tipo == "steam" else "🔄 RLM"
            nombre = nombres_mercado.get(mk, mk)
            ap, ta = info.get("apertura", "?"), info.get("actual", "?")
            lineas.append(f"  {emoji} {nombre}: {ap} → {ta} ({cambio:+.1f}%)")

            # Cachear: steam = cuota bajó (mercado comprado) → señal de valor
            mk_vb = _col_to_mk.get(mk, mk)
            steam_por_partido[mk_vb] = {
                "tipo":    tipo,
                "cambio":  cambio,
                "apertura": ap,
                "actual":   ta,
            }

        if steam_por_partido:
            _steam_cache[fid] = steam_por_partido

        if lineas:
            alertas.append(f"⚽ <b>{partido}</b>\n" + "\n".join(lineas))

    if not alertas:
        LOG.info("Steam moves: ninguno significativo (umbral ≥5%)")
        return

    texto = (
        f"⚡ <b>SharpIQ — Movimiento de Línea</b>\n"
        f"🕐 Pasada de tarde — {date.today().isoformat()}\n\n"
        + "\n\n".join(alertas) +
        "\n\n<i>Cuotas que caen ≥5% = dinero profesional entrando (steam)</i>"
    )
    try:
        ok = enviar_aviso_yamid(texto)
        LOG.info(f"Steam alert: {'OK' if ok else 'FALLO'} ({len(alertas)} partido/s)")
    except Exception as _e:
        LOG.error(f"Steam telegram: {_e}")

def kelly_stake(prob_pct, cuota, fraccion=0.5, min_pct=1.0, max_pct=5.0):
    """
    Half-Kelly Criterion: fracción óptima del bankroll.
    prob_pct : probabilidad en porcentaje (0-100)
    cuota    : cuota decimal (ej. 2.10)
    fraccion : 0.5 = half-Kelly (recomendado para reducir varianza)
    Devuelve el stake recomendado en porcentaje del bankroll, acotado entre min_pct y max_pct.
    """
    p = prob_pct / 100.0
    if p <= 0 or cuota <= 1.0:
        return min_pct
    b = cuota - 1.0
    kelly_full = (b * p - (1 - p)) / b
    if kelly_full <= 0:
        return min_pct
    stake = kelly_full * fraccion * 100   # en porcentaje
    return round(min(max(stake, min_pct), max_pct), 1)


def clasificar_tiers(reporte):
    """
    Selecciona los 3 picks del día evaluando TODOS los mercados disponibles.
    Los tiers se asignan por perfil de riesgo (prob + EV + cuota), no por tipo de mercado.

    SEGURO:     prob >= 62%, EV >= 2% vs Pinnacle, cuota <= 2.10
    PRINCIPAL:  prob >= 45%, EV >= 2% vs Pinnacle, cuota 1.55-3.00
    ALTO VALOR: EV >= 7% vs Pinnacle, cuota 1.75-5.5, prob >= 30%

    Mercados elegibles: 1X2, Over/Under 0.5-5.5, BTTS, DC, DNB,
                        Hándicap Asiático, cualquier mercado con línea Pinnacle.
    Nunca repite el mismo partido entre tiers.
    """
    SEGURO_MIN_PROB  = 62.0
    SEGURO_MAX_CUOTA = 2.10
    SEGURO_MIN_EV    = 2.0     # Mínimo 2% de edge real vs Pinnacle

    PRINC_MIN_PROB   = 45.0
    PRINC_MIN_CUOTA  = 1.55
    PRINC_MAX_CUOTA  = 3.00
    PRINC_MIN_EV     = 2.0

    AV_MIN_EV        = 7.0
    AV_MIN_CUOTA     = 1.75
    AV_MAX_CUOTA     = 5.5     # Política: nunca publicar cuota > 5.5
    AV_MIN_PROB      = 30.0    # Política: nunca publicar prob < 30%

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
        "btts_si": "Ambos Marcan — Sí", "btts_no": "Ambos No Marcan",
        "doble_1x": "Doble Oportunidad 1X",
        "doble_x2": "Doble Oportunidad X2",
        "doble_12": "Doble Oportunidad 12",
        "dnb_local":  "Draw No Bet Local",
        "dnb_visita": "Draw No Bet Visitante",
        "ah_l_m0_5":  "Hándicap Asiático Local -0.5",
        "ah_v_p0_5":  "Hándicap Asiático Visitante +0.5",
        "ah_l_m1_0":  "Hándicap Asiático Local -1",
        "ah_v_p1_0":  "Hándicap Asiático Visitante +1",
        "ah_l_m1_5":  "Hándicap Asiático Local -1.5",
        "ah_v_p1_5":  "Hándicap Asiático Visitante +1.5",
        "ah_l_m2_0":  "Hándicap Asiático Local -2",
        "ah_v_p2_0":  "Hándicap Asiático Visitante +2",
    }

    seguro_pool    = []
    principal_pool = []
    alto_pool      = []

    for pred in reporte.get("predicciones", []):
        # Stats default (API sin datos del equipo) → pick NO CONFIABLE, no publicar
        if pred.get("confiable") is False:
            continue
        probs     = pred.get("probabilidades", {})
        vbs       = pred.get("value_bets", {})
        liga_code = str(pred.get("liga_code", ""))
        es_futbol = liga_code not in SPORTS_ODDS_ONLY

        # Fútbol sin cuotas reales de Pinnacle = fallback estadístico → no publicar
        if es_futbol and not pred.get("cuotas_reales"):
            continue

        if es_futbol:
            # ── Evaluar TODOS los mercados con línea Pinnacle ────────
            for mk, vb in vbs.items():
                if not vb:
                    continue
                ev_p = vb.get("ev_pinn")
                # ev_p None = pick SIN ancla de mercado (regla 2). Puede ser SEGURO/PRINCIPAL
                # por PROBABILIDAD, pero NUNCA ALTO VALOR (ese tier exige EV real verificado).
                sin_ev = ev_p is None

                # La probabilidad y cuota vienen del value_bet (ya devigada)
                prob    = float(vb.get("pinn_prob") or probs.get(mk) or 0)
                cuota_f = float(vb.get("cuota") or 0)
                if not prob or cuota_f < 1.05:
                    continue

                nombre = _NOMBRES.get(mk) or vb.get("mercado_nombre") or mk

                # Steam bonus: si el mercado se movió a favor del pick +5%
                fid_steam  = pred.get("id")
                steam_info = (_steam_cache.get(fid_steam) or {}).get(mk, {})
                steam_ok   = steam_info.get("tipo") == "steam"  # cuota bajó → valor confirmado
                steam_bonus = abs(steam_info.get("cambio", 0)) if steam_ok else 0

                c = {
                    "pred":           pred,
                    "mercado":        mk,
                    "mercado_nombre": nombre,
                    "prob":           prob,
                    "cuota":          cuota_f,
                    "ev_pinn":        ev_p,
                    "ev":             ev_p,
                    "kelly_pct":      kelly_stake(prob, cuota_f),
                    "steam":          steam_ok,
                    "steam_bonus":    steam_bonus,
                }

                _ev = ev_p or 0  # para los scores cuando ev_p es None (pick sin EV)

                # SEGURO: alta probabilidad. Con mercado exige EV≥2; sin mercado, solo prob+cuota.
                if (prob >= SEGURO_MIN_PROB
                        and cuota_f <= SEGURO_MAX_CUOTA
                        and (sin_ev or ev_p >= SEGURO_MIN_EV)):
                    seguro_pool.append({**c, "score": prob * (1 + _ev / 200) + steam_bonus})

                # PRINCIPAL: balance EV × probabilidad (sin mercado, califica por prob).
                if (prob >= PRINC_MIN_PROB
                        and PRINC_MIN_CUOTA <= cuota_f <= PRINC_MAX_CUOTA
                        and (sin_ev or ev_p >= PRINC_MIN_EV)):
                    principal_pool.append({**c, "score": _ev * (prob / 100) + steam_bonus})

                # ALTO VALOR: SOLO con EV real (jamás sin ancla de mercado).
                if (not sin_ev
                        and ev_p >= AV_MIN_EV
                        and AV_MIN_CUOTA <= cuota_f <= AV_MAX_CUOTA
                        and prob >= AV_MIN_PROB):
                    alto_pool.append({**c, "score": ev_p + steam_bonus * 2})

        elif pred.get("es_player_prop"):
            # ── Player props ─────────────────────────────────────────
            for direction in ("over", "under"):
                vb_val = vbs.get(direction, {})
                if not vb_val:
                    continue
                prob_val  = float(vb_val.get("pinn_prob") or probs.get(direction) or 0)
                cuota_val = float(vb_val.get("cuota") or 0)
                ev_v      = vb_val.get("ev_pinn", 0) or 0
                if not cuota_val or not prob_val:
                    continue
                mercado_nombre = pred["prediccion_principal"]["mercado"]
                c = {
                    "pred":           pred,
                    "mercado":        direction,
                    "mercado_nombre": mercado_nombre,
                    "prob":           prob_val,
                    "cuota":          cuota_val,
                    "ev_pinn":        ev_v,
                    "ev":             ev_v,
                    "kelly_pct":      kelly_stake(prob_val, cuota_val),
                }
                if prob_val >= SEGURO_MIN_PROB and cuota_val <= SEGURO_MAX_CUOTA and ev_v >= SEGURO_MIN_EV:
                    seguro_pool.append({**c, "score": prob_val})
                if prob_val >= PRINC_MIN_PROB and PRINC_MIN_CUOTA <= cuota_val <= PRINC_MAX_CUOTA and ev_v >= PRINC_MIN_EV:
                    principal_pool.append({**c, "score": prob_val * cuota_val})

        else:
            # ── Otros deportes (NBA / MLB / NHL / Tennis…) ───────────
            for mk, vb in vbs.items():
                if not vb:
                    continue
                ev_p     = vb.get("ev_pinn") or vb.get("ev_porcentaje", 0) or 0
                prob_val  = float(vb.get("pinn_prob") or probs.get(mk) or 0)
                cuota_val = float(vb.get("cuota") or 0)
                if not prob_val or cuota_val < 1.05:
                    continue
                # Si el key es nombre de equipo (moneyline) → "Gana X"
                mk_nombre = vb.get("mercado_nombre") or mk
                if mk in (pred.get("local", ""), pred.get("visitante", "")):
                    mk_nombre = f"Gana {mk}"
                c = {
                    "pred":           pred,
                    "mercado":        mk,
                    "mercado_nombre": mk_nombre,
                    "prob":           prob_val,
                    "cuota":          cuota_val,
                    "ev_pinn":        ev_p,
                    "ev":             ev_p,
                    "kelly_pct":      kelly_stake(prob_val, cuota_val),
                }
                if prob_val >= SEGURO_MIN_PROB and cuota_val <= SEGURO_MAX_CUOTA and ev_p >= SEGURO_MIN_EV:
                    seguro_pool.append({**c, "score": prob_val * (1 + ev_p / 200)})
                if prob_val >= PRINC_MIN_PROB and PRINC_MIN_CUOTA <= cuota_val <= PRINC_MAX_CUOTA and ev_p >= PRINC_MIN_EV:
                    principal_pool.append({**c, "score": ev_p * (prob_val / 100)})
                if ev_p >= AV_MIN_EV and AV_MIN_CUOTA <= cuota_val <= AV_MAX_CUOTA and prob_val >= AV_MIN_PROB:
                    alto_pool.append({**c, "score": ev_p})

    seguro_pool.sort(key=lambda x: x["score"], reverse=True)
    principal_pool.sort(key=lambda x: x["score"], reverse=True)
    alto_pool.sort(key=lambda x: x["score"], reverse=True)

    usados_partidos  = set()
    usados_ligas     = set()
    usados_mercados  = []   # lista para contar tipos de mercado

    def _mercado_tipo(mk):
        if mk in ("under25", "under15", "under35", "over25", "over15", "over35"):
            return "totals"
        if mk in ("victoria_local", "victoria_visita", "empate"):
            return "1x2"
        if mk.startswith("ah_"):
            return "handicap"
        if mk.startswith("corners_"):
            return "corners"
        if mk.startswith("tarjetas_"):
            return "tarjetas"
        return "otro"

    def _pick(pool, permitir_mismo_tipo=False):
        for c in pool:
            k     = f"{c['pred']['local']} vs {c['pred']['visitante']}"
            liga  = c['pred'].get('liga_code', '')
            tipo  = _mercado_tipo(c['mercado'])
            # No repetir partido
            if k in usados_partidos:
                continue
            # No repetir liga (máximo 1 pick por competición)
            if liga in usados_ligas:
                continue
            # Máximo 1 pick de tipo "totals" entre los 3 picks del día
            if not permitir_mismo_tipo and tipo == "totals" and usados_mercados.count("totals") >= 1:
                continue
            usados_partidos.add(k)
            usados_ligas.add(liga)
            usados_mercados.append(tipo)
            return c
        # Si el filtro de diversidad deja el tier vacío, relajar restricción de tipo
        if not permitir_mismo_tipo:
            return _pick(pool, permitir_mismo_tipo=True)
        return None

    # Orden: ALTO VALOR primero para reservar el partido con mayor EV
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
