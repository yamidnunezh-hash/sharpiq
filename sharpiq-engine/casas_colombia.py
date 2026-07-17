# casas_colombia.py — que casas COLOMBIANAS tenemos datos en cada API
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from config import ODDS_API_KEY, ODDSAPI_IO_KEY

# Casas con LICENCIA en Colombia (Coljuegos) - las legales/populares alla
CASAS_CO = ["betplay", "rushbet", "wplay", "codere", "zamba", "yajuego",
            "betsson", "rivalo", "sportium", "luckia", "bwin", "betano",
            "1xbet", "megapuestas", "stake", "bet365", "pinnacle", "aquijuego"]

print("=" * 60)
print("1) THE ODDS API (la que ya usa el motor)")
print("=" * 60)
r = requests.get("https://api.the-odds-api.com/v4/sports/soccer_mexico_ligamx/odds",
                 params={"apiKey": ODDS_API_KEY, "regions": "us,us2,uk,eu,au",
                         "markets": "h2h", "oddsFormat": "decimal"}, timeout=30)
casas_toa = set()
if r.status_code == 200:
    for p in r.json():
        for bm in p.get("bookmakers", []):
            casas_toa.add(bm.get("title", ""))
print(f"   Total casas (todas): {len(casas_toa)}")
print("   Casas COLOMBIANAS encontradas:")
enc = [c for c in casas_toa if any(k in c.lower() for k in CASAS_CO)]
for c in sorted(enc):
    print(f"      - {c}")
if not enc:
    print("      NINGUNA casa 100% colombiana (solo internacionales)")

print("\n" + "=" * 60)
print("2) ODDS-API.IO (la nueva, plan free = 2 casas)")
print("=" * 60)
r2 = requests.get("https://api.odds-api.io/v3/bookmakers",
                  params={"apiKey": ODDSAPI_IO_KEY}, timeout=30)
if r2.status_code == 200:
    data = r2.json()
    casas_io = [b.get("name", "") for b in data] if isinstance(data, list) else []
    activas = [b.get("name","") for b in data if b.get("active")] if isinstance(data, list) else []
    print(f"   Total casas en su catalogo: {len(casas_io)}")
    print("   Casas COLOMBIANAS / que operan en CO:")
    enc2 = [c for c in casas_io if any(k in c.lower() for k in CASAS_CO)]
    for c in sorted(set(enc2)):
        act = " (activa)" if c in activas else ""
        print(f"      - {c}{act}")
    if not enc2:
        print("      ninguna con esos nombres")
else:
    print(f"   error {r2.status_code}: {r2.text[:120]}")
