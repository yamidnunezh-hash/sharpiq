# -*- coding: utf-8 -*-
"""
SharpIQ — AUDITOR DE RESULTADOS
Re-verifica TODOS los picks resueltos (win/loss) de datos.js contra el marcador
REAL (The Odds API /scores), y reporta los MAL calificados.

Nace del bug que cazo Yamid (21-jul-26): Toluca-Pumas "Over 2.5" marcado FALLO
a las 7pm cuando el partido era a las 9pm (aun no jugaba). El resolvedor agarro
un marcador equivocado. Este auditor pilla ese y cualquier otro.

MODO SEGURO: por defecto SOLO REPORTA (no toca nada). Con --corregir aplica.
Solo re-califica mercados de GOLES/resultado (usan el marcador). Tarjetas/corners
/props NO se tocan (necesitan otro dato). Si no encuentra el partido -> lo deja.
"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests
from config import ODDS_API_KEY
from auto_resultados import evaluar

DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "datos.js")

# Ligas/deportes a auditar (donde The Odds API da marcadores)
SPORTS = ["soccer_fifa_world_cup", "soccer_mexico_ligamx", "soccer_usa_mls",
          "soccer_brazil_campeonato", "soccer_brazil_serie_b",
          "soccer_argentina_primera_division", "soccer_conmebol_copa_sudamericana",
          "soccer_conmebol_copa_libertadores", "soccer_sweden_allsvenskan",
          "soccer_norway_eliteserien", "soccer_epl", "soccer_spain_la_liga",
          "soccer_italy_serie_a", "basketball_wnba", "basketball_nba", "baseball_mlb"]


def _norm(s):
    s = (s or "").lower()
    for a, b in (("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")):
        s = s.replace(a, b)
    for x in ("fc ","cf ","club "," fc"," cf"," sc"," ec"," de caliente","deportivo ",
              " u21"," u20"," (f)"," afc"," cd "):
        s = s.replace(x, " ")
    return " ".join(s.split())


def _match(a, b):
    na, nb = _norm(a), _norm(b)
    if not na or not nb: return False
    if na == nb or na in nb or nb in na: return True
    pa, pb = set(na.split()), set(nb.split())
    return any(len(w) >= 4 for w in (pa & pb))


# 1) Bajar TODOS los marcadores reales (una vez por deporte)
print("Descargando marcadores reales...")
juegos = []
for sp in SPORTS:
    try:
        r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sp}/scores",
                         params={"apiKey": ODDS_API_KEY, "daysFrom": 3}, timeout=25)
        if r.status_code != 200: continue
        for g in r.json():
            if not g.get("completed") or not g.get("scores"): continue
            # BUGFIX: los "scores" de The Odds API a veces traen el nombre con
            # ligeras diferencias -> emparejar cada score al equipo por similitud,
            # no por igualdad exacta (antes gh/ga salian None y NADA se auditaba).
            gh = ga = None
            for s in g["scores"]:
                sn = _norm(s.get("name", ""))
                try: val = int(s.get("score"))
                except (TypeError, ValueError): continue
                if _match(g["home_team"], s.get("name", "")): gh = val
                elif _match(g["away_team"], s.get("name", "")): ga = val
            # Fallback: si quedo alguno sin asignar, usa el ORDEN (0=home,1=away)
            if (gh is None or ga is None) and len(g["scores"]) == 2:
                try:
                    gh = int(g["scores"][0]["score"]) if gh is None else gh
                    ga = int(g["scores"][1]["score"]) if ga is None else ga
                except (TypeError, ValueError, KeyError):
                    pass
            juegos.append({"home": g["home_team"], "away": g["away_team"], "gh": gh, "ga": ga})
    except Exception as e:
        print(f"   {sp}: error {e}")
con_marcador = sum(1 for j in juegos if j["gh"] is not None and j["ga"] is not None)
print(f"Marcadores reales (completados): {len(juegos)}  |  con score valido: {con_marcador}\n")

# 2) Leer picks resueltos de datos.js
txt = open(DATOS, encoding="utf-8").read()
bloques = re.findall(r'\{[^{}]*\}', txt)
def gf(b, k):
    m = re.search(k + r'\s*:\s*["\']([^"\']*)', b); return m.group(1) if m else ''

resueltos = []
for b in bloques:
    res = gf(b, "resultado").lower()
    if res in ("win", "loss"):
        resueltos.append({"partido": gf(b,"partido"), "pred": gf(b,"prediccion"),
                          "cuota": gf(b,"cuota"), "res": res, "fecha": gf(b,"fecha"),
                          "liga": gf(b,"liga")})

print(f"Picks resueltos en la web: {len(resueltos)}")
print("=" * 70)

# 3) Auditar
malos, sin_datos, ok = [], 0, 0
for p in resueltos:
    predl = p["pred"].lower()
    # Solo mercados que dependen del marcador de goles
    if any(x in predl for x in ("tarjeta","corner","card","remate","disparo","falta","props")):
        continue
    partes = p["partido"].split(" vs ")
    if len(partes) != 2: continue
    loc, vis = partes
    juego = next((j for j in juegos if _match(loc, j["home"]) and _match(vis, j["away"])
                  and j["gh"] is not None and j["ga"] is not None), None)
    if not juego:
        sin_datos += 1
        continue
    correcto = evaluar(p["pred"], juego["gh"], juego["ga"], loc, vis)
    if correcto is None:
        continue
    if correcto != p["res"]:
        malos.append((p, juego, correcto))
    else:
        ok += 1

print(f"\n✅ Bien calificados: {ok}")
print(f"❓ Sin marcador para verificar: {sin_datos}")
print(f"❌ MAL CALIFICADOS: {len(malos)}")
print("=" * 70)
for p, j, correcto in malos:
    print(f"\n  {p['partido']}  ({j['gh']}-{j['ga']})")
    print(f"     {p['pred']} @ {p['cuota']}")
    print(f"     web dice: {p['res'].upper()}  ->  REAL es: {correcto.upper()}  ❌ CORREGIR")

if not malos:
    print("\n🎉 Todos los picks verificables están BIEN calificados.")
    raise SystemExit

if "--corregir" not in sys.argv:
    print(f"\n⚠️ {len(malos)} mal calificados. Corre con  --corregir  para arreglarlos.")
    raise SystemExit

# ── CORREGIR: en datos.js Y en el bloque inline de index.html ──────────────
print("\nCorrigiendo en datos.js e index.html...")
INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "index.html")
n_fix = 0

def _corrige_texto(texto):
    global n_fix
    def _fix(mo):
        global n_fix
        b = mo.group(0)
        part = gf(b, "partido"); pred = gf(b, "prediccion"); res = gf(b, "resultado").lower()
        if res not in ("win", "loss"):
            return b
        for p, j, correcto in malos:
            if p["partido"] == part and p["pred"] == pred and res == p["res"]:
                n_fix += 1
                return re.sub(r'(resultado\s*:\s*["\'])[^"\']*(["\'])',
                              r'\g<1>' + correcto + r'\g<2>', b)
        return b
    return re.sub(r'\{[^{}]*\}', _fix, texto)

for ruta in (DATOS, INDEX):
    if not os.path.exists(ruta):
        continue
    t = open(ruta, encoding="utf-8").read()
    t2 = _corrige_texto(t)
    if t2 != t:
        open(ruta, "w", encoding="utf-8").write(t2)
        print(f"   ✅ actualizado: {os.path.basename(ruta)}")

print(f"\n✅ {n_fix} correcciones aplicadas. Revisa y haz git push.")
