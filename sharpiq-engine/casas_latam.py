# casas_latam.py — casas por pais LatAm en odds-api.io (para arbitraje)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests
from config import ODDSAPI_IO_KEY

r = requests.get("https://api.odds-api.io/v3/bookmakers",
                 params={"apiKey": ODDSAPI_IO_KEY}, timeout=30)
casas = [b.get("name","") for b in r.json() if isinstance(b, dict) and b.get("active")]

# Marcas que operan en cada pais LatAm (aprox; verificar licencia antes de vender)
PAISES = {
 "Mexico":    ["caliente","winpot","strendus","betano mx","codere","1xbet","betsson","bet365","betway","novibet","stake","betano","betfair"],
 "Peru":      ["betano pe","betsson","coolbet","1xbet","bet365","betano","doradobet","apuesta total","te apuesto","meridianbet","betfair","inkabet"],
 "Chile":     ["coolbet","betsson","betano","1xbet","bet365","betano","betway","latamwin","juegalo","betsafe","betfair"],
 "Argentina": ["betano","bplay","codere","1xbet","betsson","bet365","betwarrior","betfair","stake"],
 "Ecuador":   ["coolbet","betsson","1xbet","betano","bet365","betcris","betfair"],
}

print(f"Casas activas totales en odds-api.io: {len(casas)}\n")
print("="*54)
print("CASAS APOSTABLES POR PAIS LATAM (para arbitraje)")
print("="*54)
resumen = []
for pais, marcas in PAISES.items():
    enc = sorted({c for c in casas if any(m in c.lower() for m in marcas)
                  and not any(x in c.lower() for x in ["(es)"," es"," it"," fr"," de"," uk"," pt"," bg"," cz"," nj"," za"])})
    resumen.append((pais, len(enc)))
    print(f"\n{pais} -> {len(enc)} casas:")
    print("   " + ", ".join(enc))

print("\n" + "="*54)
print("RANKING (mas casas = mejor para arbitraje):")
for p, n in sorted(resumen, key=lambda x:-x[1]):
    viable = "ARBITRAJE OK" if n >= 8 else ("justo" if n >= 5 else "MUY POCAS")
    print(f"   {p:12} {n:2} casas  -> {viable}")
