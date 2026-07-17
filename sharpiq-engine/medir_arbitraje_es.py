# medir_arbitraje_es.py — ¿CUANTOS arbitrajes reales hay para un cliente en ESPANA?
# Escanea las ligas con mas casas (top Europa) y cuenta arbs con casas apostables en ES.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from datetime import datetime, timezone
from config import ODDS_API_KEY
from arbitraje import escanear_pais, detectar_arbitraje_partido
from casas_por_pais import casas_de, NOMBRE_PAIS

BASE = "https://api.the-odds-api.com/v4"

# LIGAS ACTIVAS EN JULIO (las europeas top estan de pretemporada).
# En agosto, cuando Yamid este en Espana, arrancan La Liga/Premier/etc -> mas arbs.
LIGAS = [
    # En temporada AHORA (verano):
    "soccer_usa_mls", "soccer_brazil_campeonato", "soccer_brazil_serie_b",
    "soccer_mexico_ligamx", "soccer_argentina_primera_division",
    "soccer_sweden_allsvenskan", "soccer_norway_eliteserien",
    "soccer_finland_veikkausliiga", "soccer_japan_j_league",
    "soccer_korea_kleague1", "soccer_conmebol_copa_libertadores",
    "soccer_conmebol_copa_sudamericana", "soccer_uefa_europa_conference_league",
    # Por si ya hay amistosos/clasificatorios con cuotas:
    "soccer_spain_la_liga", "soccer_epl",
]

PAIS = "ES"
permitidas = set(casas_de(PAIS))
print(f"=== MEDICION ARBITRAJE {NOMBRE_PAIS.get(PAIS, PAIS)} ===")
print(f"Casas apostables en {PAIS}: {len(permitidas)}")
print(f"Hora UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}\n")

todos, casas_vistas = [], set()
for liga in LIGAS:
    try:
        r = requests.get(f"{BASE}/sports/{liga}/odds",
                         params={"apiKey": ODDS_API_KEY, "regions": "eu,uk",
                                 "markets": "h2h,totals,spreads", "oddsFormat": "decimal"},
                         timeout=30)
        if r.status_code != 200:
            print(f"  {liga:34} -> {r.status_code}")
            continue
        data = r.json()
        if not isinstance(data, list):
            continue
        # cuantas de MIS casas ES aparecen en esta liga
        for p in data:
            for bm in p.get("bookmakers", []):
                if bm["title"] in permitidas:
                    casas_vistas.add(bm["title"])
        print(f"  {liga:34} -> {len(data)} partidos")
        todos.extend(data)
    except Exception as e:
        print(f"  {liga:34} -> EXC {str(e)[:30]}")

print(f"\nTotal partidos: {len(todos)}")
print(f"Casas ES presentes ahora: {sorted(casas_vistas)}")
print(f"Creditos The Odds API restantes: {r.headers.get('x-requests-remaining')}")

# ── ARBITRAJES 2 VIAS (totals/spreads) para ESPANA ────────────────────
arbs2 = escanear_pais(todos, PAIS, mercados=("totals", "spreads"))

# ── ARBITRAJES 1X2 (3 vias) filtrando a casas ES ──────────────────────
arbs1x2 = []
for p in todos:
    a = detectar_arbitraje_partido(p)
    if not a:
        continue
    casas = {a["1"]["casa"], a["X"]["casa"], a["2"]["casa"]}
    if casas <= permitidas and 0 < a["profit_pct"] <= 5:   # todas apostables + sano
        arbs1x2.append(a)

print("\n" + "=" * 66)
print(f"ARBITRAJES REALES PARA ESPANA (solo casas apostables ahi):")
print("=" * 66)
print(f"  2 vias (totals/spreads): {len(arbs2)}")
print(f"  1X2 (resultado):         {len(arbs1x2)}")
print(f"  TOTAL en esta foto:      {len(arbs2) + len(arbs1x2)}")

for a in arbs2[:5]:
    casas = " + ".join(L["casa"] for L in a["lados"])
    print(f"\n  +{a['profit_pct']}%  {a['local']} vs {a['visitante']} [{a['mercado']} {a['linea']}]")
    for L in a["lados"]:
        print(f"     {L['nombre']:20} @{L['cuota']:5} [{L['casa']:16}] stake {L['stake']}u")
for a in arbs1x2[:3]:
    print(f"\n  +{a['profit_pct']}%  {a['local']} vs {a['visitante']} (1X2)")
    print(f"     1 @{a['1']['cuota']} [{a['1']['casa']}] · X @{a['X']['cuota']} [{a['X']['casa']}] · 2 @{a['2']['cuota']} [{a['2']['casa']}]")

print("\n" + "=" * 66)
print("NOTA: esto es UNA foto. Los arbs nacen y mueren todo el dia.")
print("Para el numero real hay que escanear cada X min durante 24h.")
