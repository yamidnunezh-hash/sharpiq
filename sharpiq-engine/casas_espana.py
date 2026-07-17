# casas_espana.py — casas de ESPANA en odds-api.io (266 casas)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from config import ODDSAPI_IO_KEY

# Marcas con licencia DGOJ en Espana (o que operan .es)
CASAS_ES = ["betfair", "william hill", "888", "bwin", "codere", "sportium",
            "luckia", "marca apuestas", "retabet", "winamax", "betway",
            "leovegas", "betsson", "kirolbet", "paf", "versus", "paston",
            "marathon", "bet365", "pokerstars", "interwetten", "zebet",
            "circus", "yaass", "goldenpark", "aupabet", "tonybet", "casumo",
            "coolbet", "unibet", "betano", "1xbet", "dafabet", "vbet"]

r = requests.get("https://api.odds-api.io/v3/bookmakers",
                 params={"apiKey": ODDSAPI_IO_KEY}, timeout=30)
data = r.json()
casas = [b for b in data if isinstance(b, dict)]
print(f"Total casas en odds-api.io: {len(casas)}\n")

print("=" * 56)
print("CASAS QUE OPERAN EN ESPANA (o versiones .es/ES):")
print("=" * 56)
enc = []
for b in casas:
    nombre = b.get("name", "")
    n = nombre.lower()
    # match por marca espanola O sufijo ES/es
    if any(k in n for k in CASAS_ES) or n.endswith(" es") or "(es)" in n or " es " in n:
        enc.append((nombre, b.get("active", False)))

# quitar las claramente de otro pais (BR, MX, IT, FR, DE, UK...)
otros = ["br", "mx", "pe", "it", "fr", "de", "dk", "pt", "ca", "bg", "cz",
         "uk", "nj", "au", "se", "nl", "us"]
def es_espanola(nombre):
    n = nombre.lower()
    # si termina en un sufijo de OTRO pais, fuera (salvo que diga es)
    ult = n.split()[-1] if n.split() else ""
    if ult in otros and ult != "es":
        return False
    return True

es_list = sorted(set(n for n, _ in enc if es_espanola(n)))
for nombre in es_list:
    activa = next((a for nm, a in enc if nm == nombre), False)
    print(f"   {'[activa]' if activa else '[  off ]'}  {nombre}")

print(f"\nTOTAL casas usables en Espana: {len(es_list)}")
print("\n(Con estas se puede intentar ARBITRAJE de verdad en Espana)")
