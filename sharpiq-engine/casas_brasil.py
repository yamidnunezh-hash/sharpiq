# casas_brasil.py — casas de BRASIL en odds-api.io (mercado regulado 2025)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from config import ODDSAPI_IO_KEY

# Marcas grandes en Brasil (licenciadas/populares)
CASAS_BR = ["betano", "bet365", "betfair", "betsson", "kto", "superbet",
            "esportes da sorte", "estrela bet", "estrelabet", "sportingbet",
            "betnacional", "bet nacional", "pixbet", "blaze", "stake",
            "novibet", "vaidebet", "br4bet", "1xbet", "betmgm", "pinnacle",
            "betboom", "betfast", "lottoland", "parimatch", "betway", "f12",
            "mcgames", "aposta ganha", "seguro bet", "brazino", "reals",
            "betpix", "hanz", "luva bet", "bet da sorte"]

r = requests.get("https://api.odds-api.io/v3/bookmakers",
                 params={"apiKey": ODDSAPI_IO_KEY}, timeout=30)
data = r.json()
casas = [b for b in data if isinstance(b, dict)]
print(f"Total casas en odds-api.io: {len(casas)}\n")

print("=" * 56)
print("CASAS QUE OPERAN EN BRASIL:")
print("=" * 56)
enc = []
for b in casas:
    nombre = b.get("name", "")
    n = nombre.lower()
    if any(k in n for k in CASAS_BR) or n.endswith(" br") or ".br" in n or "brazil" in n:
        enc.append((nombre, b.get("active", False)))

# Excluir versiones de OTROS paises (ES, MX, IT, FR, DE, UK, PE...)
otros_suf = ("es","mx","pe","it","fr","de","dk","pt","ca","bg","cz","uk","nj","au","se","nl","us","pl","be")
def es_brasil(n):
    nl = n.lower()
    if "br" in nl.replace("bet","") or ".br" in nl or "brazil" in nl:
        return True
    ult = nl.split()[-1] if nl.split() else ""
    return ult not in otros_suf

br = sorted(set(n for n,_ in enc if es_brasil(n)))
for nombre in br:
    activa = next((a for nm,a in enc if nm==nombre), False)
    print(f"   {'[activa]' if activa else '[  off ]'}  {nombre}")

print(f"\nTOTAL casas usables en Brasil: {len(br)}")
