# arb_logger.py — MEDIDOR CONTINUO de arbitraje (el numero REAL, no una foto)
#
# Una sola consulta subcuenta: los arbs nacen y mueren en segundos. Este script
# escanea cada X minutos y ACUMULA todos los arbs que aparecen, sin repetir.
# Corre esto un dia entero (o durante tu viaje a Espana) y sabras cuantos arbs
# REALES hay para un cliente en ese pais.
#
# Uso:   python arb_logger.py ES 10      (pais ES, cada 10 min)
#        python arb_logger.py CO 15      (Colombia, cada 15 min)
# Detener: Ctrl+C. Log en arb_log_<PAIS>.txt
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from datetime import datetime, timezone
from config import ODDS_API_KEY
from arbitraje import escanear_pais, detectar_arbitraje_partido
from casas_por_pais import casas_de, NOMBRE_PAIS

BASE = "https://api.the-odds-api.com/v4"
PAIS = (sys.argv[1] if len(sys.argv) > 1 else "ES").upper()
CADA_MIN = int(sys.argv[2]) if len(sys.argv) > 2 else 10
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"arb_log_{PAIS}.txt")

# Ligas en temporada ahora (verano). En agosto agrega La Liga/Premier/etc.
LIGAS = ["soccer_usa_mls", "soccer_brazil_campeonato", "soccer_brazil_serie_b",
         "soccer_mexico_ligamx", "soccer_argentina_primera_division",
         "soccer_sweden_allsvenskan", "soccer_norway_eliteserien",
         "soccer_conmebol_copa_libertadores", "soccer_conmebol_copa_sudamericana",
         "soccer_spain_la_liga", "soccer_epl", "soccer_italy_serie_a"]

permitidas = set(casas_de(PAIS))
vistos = set()      # firmas de arbs ya contados (para no duplicar)
total = 0

def log(msg):
    print(msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

log(f"\n=== INICIO medidor {NOMBRE_PAIS.get(PAIS,PAIS)} · cada {CADA_MIN} min · {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC ===")
log(f"Casas apostables en {PAIS}: {len(permitidas)}")

try:
    ronda = 0
    while True:
        ronda += 1
        todos = []
        for liga in LIGAS:
            try:
                r = requests.get(f"{BASE}/sports/{liga}/odds",
                                 params={"apiKey": ODDS_API_KEY, "regions": "eu,uk",
                                         "markets": "h2h,totals,spreads", "oddsFormat": "decimal"},
                                 timeout=30)
                if r.status_code == 200 and isinstance(r.json(), list):
                    todos.extend(r.json())
            except Exception:
                pass

        # 2 vias + 1X2, solo casas apostables en el pais
        encontrados = escanear_pais(todos, PAIS, mercados=("totals", "spreads"))
        for p in todos:
            a = detectar_arbitraje_partido(p)
            if a and {a["1"]["casa"], a["X"]["casa"], a["2"]["casa"]} <= permitidas and 0 < a["profit_pct"] <= 5:
                encontrados.append({"local": a["local"], "visitante": a["visitante"],
                                    "mercado": "1X2", "profit_pct": a["profit_pct"],
                                    "lados": [{"casa": c} for c in (a["1"]["casa"], a["2"]["casa"])]})

        nuevos = 0
        creds = r.headers.get("x-requests-remaining", "?")
        for a in encontrados:
            firma = f"{a['local']}|{a['visitante']}|{a['mercado']}"
            if firma in vistos:
                continue
            vistos.add(firma); total += 1; nuevos += 1
            casas = " + ".join(L["casa"] for L in a["lados"])
            log(f"  [{datetime.now(timezone.utc):%H:%M}] ARB #{total}: +{a['profit_pct']}%  "
                f"{a['local']} vs {a['visitante']} [{a['mercado']}]  ({casas})")

        log(f"Ronda {ronda}: {len(todos)} partidos | {nuevos} arbs nuevos | ACUMULADO: {total} | creditos: {creds}")
        time.sleep(CADA_MIN * 60)
except KeyboardInterrupt:
    log(f"\n=== FIN · {ronda} rondas · {total} arbitrajes UNICOS acumulados ===")
    log(f"Promedio: {round(total/max(ronda,1),2)} arbs nuevos por escaneo")
