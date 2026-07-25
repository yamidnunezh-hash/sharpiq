# -*- coding: utf-8 -*-
"""
SharpIQ — RADAR DE VALOR (todos los deportes en temporada) 🦈
═══════════════════════════════════════════════════════════════════════════════
POR QUE EXISTE (23-jul-2026):
El motor PREDICTOR (motor.py) adivina resultados y sale sobre-confiado con los
favoritos -> publica "Under 2.5" aburridos. Este RADAR no adivina NADA: solo
compara lo que paga cada casa contra el precio JUSTO de Pinnacle (la casa más
eficiente del mundo, sin su margen). Donde una casa va atrasada = valor REAL,
matemático, sin predecir nada.

    valor (EV) = cuota_de_la_casa × prob_justa_de_pinnacle − 1

DIFERENCIA CLAVE con live_valor.py:
  · live_valor solo mira 12 ligas de FÚTBOL, 2h antes, 2 mercados -> en verano
    (Europa dormida) se ve vacío.
  · radar_valor mira TODOS los deportes activos del plan (fútbol de todo el
    mundo + MLB + WNBA + tenis + lo que esté en temporada), TODO el día, y
    varios mercados (ganador, goles/totales, hándicap). Así hay volumen todos
    los días: cuando el fútbol duerme, cazamos en el béisbol/tenis.

  · Además cruza cada jugada contra BETPLAY/BETANO (odds_latam.py) para confirmar
    que el cliente colombiano LA PUEDE TOMAR y con qué EV real.

MÉTODO SEGURO (nada de valor fantasma):
  · Solo comparamos líneas IDÉNTICAS (mismo punto) contra Pinnacle -> sin
    traducciones de Poisson que puedan inflar el valor.
  · Reglas duras del motor: prob≥30%, cuota 1.30–5.5, edge ≤15% (más de eso es
    data mala, no oportunidad).

    python radar_valor.py            # escanea y muestra (no escribe web)
    python radar_valor.py --json     # además escribe radar_valor_feed.json
    python radar_valor.py --betplay  # además cruza contra Betplay (más créditos)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import requests

from config import ODDS_API_KEY

BASE = "https://api.the-odds-api.com/v4"
FEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "radar_valor_feed.json")

SHARP = "pinnacle"                 # el termómetro de la verdad
REGIONS = "eu,uk"                  # eu trae Pinnacle + blandas; uk suma bet365/willhill
MERCADOS = "h2h,totals,spreads"    # ganador · goles/totales · hándicap (fallback)

# Mercados POR DEPORTE — solo los que Pinnacle SÍ cotiza (medibles).
# Las líneas "alternate_*" multiplican jugadas: no solo el O/U principal,
# también Más/Menos 1.5, 2.5, 3.5… y hándicaps alternativos, cada uno medido.
def _mercados_de(dep_key: str) -> str:
    if dep_key.startswith("soccer"):
        return "h2h,totals,spreads,alternate_totals,alternate_spreads"
    if dep_key.startswith("baseball"):
        return "h2h,totals,spreads,alternate_totals"
    if dep_key.startswith("basketball"):
        return "h2h,totals,spreads,alternate_totals,alternate_spreads"
    return MERCADOS

def _norm_mkey(k: str) -> str:
    """Trata las líneas alternativas como el mismo mercado que la principal,
    para que la cuota justa de Pinnacle case con la de la casa por PUNTO."""
    if k in ("totals", "alternate_totals"):   return "totals"
    if k in ("spreads", "alternate_spreads"): return "spreads"
    return k

# ── CASAS: nombre bonito + ¿opera en Colombia? (que el cliente SÍ pueda tomar) ──
# El valor solo sirve si el cliente puede apostarlo. Marcamos cuáles operan en
# Colombia; por defecto la web muestra SOLO esas (matar la "cuota fantasma").
CASAS = {
    "onexbet":       ("1xBet",        True),
    "betsson":       ("Betsson",      True),
    "betway":        ("Betway",       True),
    "betano":        ("Betano",       True),
    "betfair_ex_eu": ("Betfair",      True),
    "betfair":       ("Betfair",      True),
    "bwin":          ("Bwin",         True),
    "codere":        ("Codere",       True),
    "wplay":         ("Wplay",        True),
    "rushbet":       ("Rushbet",      True),
    "stake":         ("Stake",        True),
    # No disponibles/confiables en CO -> se ven solo con --todas (referencia)
    "unibet":        ("Unibet",       False),
    "unibet_eu":     ("Unibet",       False),
    "unibet_nl":     ("Unibet",       False),
    "bet365":        ("bet365",       False),
    "williamhill":   ("William Hill", False),
    "coolbet":       ("Coolbet",      False),
    "marathonbet":   ("Marathonbet",  False),
    "leovegas":      ("LeoVegas",     False),
    "livescorebet":  ("LiveScore",    False),
    "nordicbet":     ("NordicBet",    False),
    "betclic":       ("Betclic",      False),
    "tipico":        ("Tipico",       False),
    "matchbook":     ("Matchbook",    False),
    "betfair_ex_uk": ("Betfair",      False),
}


def casa_info(key: str):
    """(nombre_bonito, opera_en_colombia). Desconocida -> nombre crudo, no CO."""
    return CASAS.get(key, (key.replace("_", " ").title(), False))


# Emoji por deporte (para la tarjeta web)
_EMOJI_DEP = {"soccer": "⚽", "baseball": "⚾", "basketball": "🏀",
              "tennis": "🎾", "americanfootball": "🏈", "icehockey": "🏒",
              "cricket": "🏏", "mma": "🥊", "boxing": "🥊", "rugby": "🏉",
              "aussierules": "🏉", "lacrosse": "🥍"}


def _emoji(dep_key: str) -> str:
    for k, e in _EMOJI_DEP.items():
        if dep_key.startswith(k):
            return e
    return "🎯"

# ── Reglas duras (las mismas que sostienen el motor) ──────────────────────────
EV_MIN       = 0.03               # 3% mínimo de valor para publicar
EDGE_MAXIMO  = 0.15              # >15% sobre Pinnacle = data mala, no oportunidad
PROB_MINIMA  = 0.30              # nada por debajo del 30% de probabilidad
CUOTA_MAXIMA = 5.5              # nada de loterías
CUOTA_MINIMA = 1.30              # por debajo el margen se lo come todo

VENTANA_HORAS    = 15            # partidos desde ahora hasta 15h adelante (+ en vivo)
CREDITOS_MINIMOS = 5000          # freno de mano: no dejar sin créditos al motor

# Deportes que NUNCA nos interesan (o donde el modelo LatAm no aplica)
EXCLUIR_KEYS = ("_winner", "outrights")


def _get(url, params):
    try:
        r = requests.get(url, params=params, timeout=20)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def creditos_restantes():
    try:
        r = requests.get(f"{BASE}/sports", params={"apiKey": ODDS_API_KEY}, timeout=10)
        return int(r.headers.get("x-requests-remaining", 0))
    except Exception:
        return None


def deportes_activos() -> list:
    """TODOS los deportes con partidos (no futuros/outrights) activos AHORA."""
    d = _get(f"{BASE}/sports", {"apiKey": ODDS_API_KEY}) or []
    out = []
    for s in d:
        if not s.get("active"):
            continue
        if s.get("has_outrights"):
            continue                       # futuros (campeón de liga) — no es esto
        k = s.get("key", "")
        if any(x in k for x in EXCLUIR_KEYS):
            continue
        out.append(s)
    return out


def eventos_en_ventana(dep_key: str) -> list:
    """Eventos de este deporte desde ahora hasta VENTANA_HORAS (o en vivo)."""
    ev = _get(f"{BASE}/sports/{dep_key}/events", {"apiKey": ODDS_API_KEY}) or []
    ahora = datetime.now(timezone.utc)
    out = []
    for e in ev:
        try:
            ini = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
        except Exception:
            continue
        mins = (ahora - ini).total_seconds() / 60
        if -VENTANA_HORAS * 60 < mins < 200:      # pre (hasta 15h) o en vivo
            e["_estado"] = "VIVO" if mins > 0 else "PRE"
            e["_min"] = int(abs(mins))
            out.append(e)
    return out


def _sin_margen(cuotas: dict) -> dict:
    """Quita el margen -> probabilidades que suman 1 (precio justo de Pinnacle)."""
    inv = {k: 1.0 / v for k, v in cuotas.items() if v and v > 1}
    total = sum(inv.values())
    return {k: v / total for k, v in inv.items()} if total else {}


def _grupos_pinnacle(markets: list) -> dict:
    """Devig de Pinnacle por mercado, agrupando bien cada línea.

    · h2h      -> un solo grupo (1 / X / 2).
    · totals   -> un grupo por PUNTO (Over/Under de esa línea).
    · spreads  -> un grupo por |punto| (los dos equipos de ese hándicap).
    Devuelve {mercado_key: {clave_outcome: prob_justa}}.
    """
    justo = {}
    for m in markets:
        key = _norm_mkey(m.get("key"))
        outs = m.get("outcomes", [])
        if key == "h2h":
            cu = {o["name"]: o["price"] for o in outs if o.get("price")}
            for k, p in _sin_margen(cu).items():
                justo[f"h2h|{k}"] = p
        elif key in ("totals", "spreads"):
            # agrupar por punto (totals) o |punto| (spreads)
            grupos = {}
            for o in outs:
                pt = o.get("point")
                if pt is None or not o.get("price"):
                    continue
                g = round(abs(float(pt)), 2) if key == "spreads" else round(float(pt), 2)
                grupos.setdefault(g, {})[f'{o["name"]}|{o["point"]}'] = o["price"]
            for cu in grupos.values():
                if len(cu) < 2:            # sin la pareja no se puede quitar margen
                    continue
                for k, p in _sin_margen(cu).items():
                    justo[f"{key}|{k}"] = p
    return justo


def _nombre_legible(mkey: str, outcome: str, punto) -> str:
    """Texto bonito para la web."""
    if mkey == "h2h":
        return {"Draw": "Empate"}.get(outcome, outcome)      # gana <equipo> / Empate
    if mkey == "totals":
        t = "Más de" if outcome == "Over" else "Menos de"
        return f"{t} {punto}"
    if mkey == "spreads":
        signo = f"+{punto}" if float(punto) > 0 else f"{punto}"
        return f"{outcome} ({signo})"
    return outcome


def valor_del_evento(dep_key: str, dep_titulo: str, ev: dict) -> list:
    """Compara TODAS las casas contra Pinnacle en este evento. Devuelve jugadas."""
    d = _get(f"{BASE}/sports/{dep_key}/events/{ev['id']}/odds", {
        "apiKey": ODDS_API_KEY, "regions": REGIONS,
        "markets": _mercados_de(dep_key), "oddsFormat": "decimal",
    })
    if not d:
        return []

    justo = {}
    for bm in d.get("bookmakers", []):
        if bm["key"] == SHARP:
            justo = _grupos_pinnacle(bm.get("markets", []))
            break
    if not justo:
        return []                          # sin Pinnacle no hay verdad -> no opinamos

    hall = []
    for bm in d.get("bookmakers", []):
        if bm["key"] == SHARP:
            continue
        for m in bm.get("markets", []):
            mkey = _norm_mkey(m.get("key"))
            for o in m.get("outcomes", []):
                cuota = o.get("price")
                pt = o.get("point")
                if mkey == "h2h":
                    clave = f"h2h|{o['name']}"
                else:
                    clave = f"{mkey}|{o['name']}|{pt}"
                p = justo.get(clave)
                if not p or not cuota:
                    continue
                if p < PROB_MINIMA or not (CUOTA_MINIMA <= cuota <= CUOTA_MAXIMA):
                    continue
                ev_pct = p * cuota - 1
                justa = 1 / p
                if ev_pct >= EV_MIN and (cuota / justa - 1) <= EDGE_MAXIMO:
                    hall.append({
                        "deporte": dep_titulo,
                        "deporte_key": dep_key,
                        "estado": ev["_estado"],
                        "min": ev["_min"],
                        "evento_id": ev["id"],
                        "partido": f"{ev['away_team']} @ {ev['home_team']}",
                        "local": ev["home_team"],
                        "visitante": ev["away_team"],
                        "mercado": mkey,
                        "outcome": o["name"],
                        "punto": pt,
                        "jugada": _nombre_legible(mkey, o["name"], pt),
                        "casa": bm["key"],
                        "cuota": round(cuota, 2),
                        "cuota_justa": round(justa, 2),
                        "prob": round(p * 100, 1),
                        "ev": round(ev_pct * 100, 1),
                    })
    return hall


def _mejor_por_jugada(hall: list) -> list:
    """Si varias casas pagan la misma jugada, deja SOLO la de mejor cuota."""
    mejor = {}
    for h in hall:
        clave = (h["evento_id"], h["mercado"], h["outcome"], h["punto"])
        if clave not in mejor or h["cuota"] > mejor[clave]["cuota"]:
            mejor[clave] = h
    return list(mejor.values())


def escanear(con_betplay: bool = False) -> list:
    q = creditos_restantes()
    if q is not None and q < CREDITOS_MINIMOS:
        print(f"⛔ Quedan {q} créditos (< {CREDITOS_MINIMOS}). No se escanea: el motor tiene prioridad.")
        return []
    if q is not None:
        print(f"   Créditos disponibles: {q}")

    deportes = deportes_activos()
    print(f"   Deportes activos en el plan: {len(deportes)}")

    todo = []
    escaneados = 0
    for s in deportes:
        evs = eventos_en_ventana(s["key"])
        if not evs:
            continue
        print(f"   · {s['title']:38s} {len(evs)} partido(s) en ventana")
        for ev in evs:
            try:
                todo += valor_del_evento(s["key"], s["title"], ev)
            except Exception as e:
                # un partido con datos raros NO puede tumbar el escaneo completo
                print(f"       (evento {ev.get('id','?')} saltado: {e})")
            escaneados += 1

    todo = _mejor_por_jugada(todo)
    todo.sort(key=lambda h: (h["estado"] != "VIVO", -h["ev"]))
    print(f"   Partidos escaneados: {escaneados}  ·  Jugadas de valor: {len(todo)}")

    if con_betplay and todo:
        _cruzar_betplay(todo)
    return todo


# ── Cruce contra BETPLAY/BETANO (lo que el cliente colombiano SÍ toma) ─────────
_MAP_MERCADO = {   # (mercado, outcome) del radar -> clave de odds_latam
    ("totals", "Over", 1.5): "over15", ("totals", "Under", 1.5): "under15",
    ("totals", "Over", 2.5): "over25", ("totals", "Under", 2.5): "under25",
    ("totals", "Over", 3.5): "over35", ("totals", "Under", 3.5): "under35",
}


def _clave_latam(h: dict, local: str, visitante: str) -> str | None:
    if h["mercado"] == "h2h":
        if h["outcome"] == "Draw":
            return "X"
        if h["outcome"] == local:
            return "1"
        if h["outcome"] == visitante:
            return "2"
        return None
    if h["mercado"] == "totals" and h["punto"] is not None:
        return _MAP_MERCADO.get(("totals", h["outcome"], round(float(h["punto"]), 1)))
    return None


def _cruzar_betplay(hall: list) -> None:
    """Para las jugadas de fútbol, mira qué paga Betplay y calcula el EV tomable."""
    try:
        import odds_latam as ol
    except Exception as e:
        print(f"   (no se pudo cargar odds_latam: {e})")
        return
    for h in hall:
        if not h["deporte_key"].startswith("soccer"):
            continue
        clave = _clave_latam(h, h["local"], h["visitante"])
        if not clave:
            continue
        try:
            r = ol.comparar(h["local"], h["visitante"], clave, h["prob"])
        except Exception:
            r = None
        if r and r.get("cuota_casa"):
            h["betplay_cuota"] = r["cuota_casa"]
            h["betplay_ev"] = r["valor_pct"]
            h["betplay_toma"] = bool(r.get("hay_valor"))


def escribir_feed(hall: list) -> None:
    data = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "total": len(hall),
        "jugadas": hall,
    }
    with open(FEED, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   Feed escrito: {os.path.basename(FEED)} ({len(hall)} jugadas)")


# ── FEED PARA LA WEB (radar_feed.js -> window.RADAR_VALOR) ─────────────────────
FEED_WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "radar_feed.js")


def _jugada_web(h: dict) -> str:
    """Texto claro para el cliente."""
    if h["mercado"] == "h2h":
        if h["outcome"] == "Draw":
            return "Empate"
        return f"Gana {h['outcome']}"
    if h["mercado"] == "totals":
        t = "Más de" if h["outcome"] == "Over" else "Menos de"
        return f"{t} {h['punto']} goles" if h["deporte_key"].startswith("soccer") else f"{t} {h['punto']}"
    if h["mercado"] == "spreads":
        signo = f"+{h['punto']}" if float(h["punto"]) > 0 else f"{h['punto']}"
        return f"{h['outcome']} ({signo})"
    return h.get("jugada", h["outcome"])


def feed_web(hall: list, solo_co: bool = True) -> list:
    """Normaliza a lo que muestra la web: casa bonita, jugada clara, solo CO."""
    out = []
    for h in hall:
        nombre, opera_co = casa_info(h["casa"])
        if solo_co and not opera_co:
            continue
        out.append({
            "deporte": h["deporte"],
            "emoji": _emoji(h["deporte_key"]),
            "estado": h["estado"],
            "partido": f"{h['local']} vs {h['visitante']}",
            "jugada": _jugada_web(h),
            "casa": nombre,
            "cuota": h["cuota"],
            "cuota_justa": h["cuota_justa"],
            "valor": h["ev"],
            "prob": h["prob"],
            "betplay_cuota": h.get("betplay_cuota"),
            "betplay_valor": h.get("betplay_ev"),
        })
    return out


def escribir_feed_web(hall: list, solo_co: bool = True) -> None:
    jugadas = feed_web(hall, solo_co)
    data = {"generado": datetime.now(timezone.utc).isoformat(),
            "total": len(jugadas), "jugadas": jugadas}
    js = "// Generado por radar_valor.py — NO editar a mano.\n"
    js += "window.RADAR_VALOR = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n"
    with open(FEED_WEB, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"   Feed WEB escrito: {os.path.basename(FEED_WEB)} "
          f"({len(jugadas)} jugadas tomables en CO)")


if __name__ == "__main__":
    con_bp = "--betplay" in sys.argv
    print("🦈 SharpIQ — RADAR DE VALOR (todos los deportes)")
    print("   Compara cada casa contra Pinnacle sin margen. No adivina: mide.")
    print("═" * 70)
    hall = escanear(con_betplay=con_bp)

    # 1) EL PRODUCTO PRIMERO: escribir los feeds antes de cualquier print bonito.
    #    Así una línea de consola con un campo raro NUNCA deja el radar sin publicar.
    if "--json" in sys.argv:
        escribir_feed(hall)
    if "--web" in sys.argv:
        solo_co = "--todas" not in sys.argv
        escribir_feed_web(hall, solo_co=solo_co)

    # 2) Impresión SOLO cosmética (resumen en consola). Blindada: si algo falla
    #    aquí, el feed ya quedó escrito y el job de CI termina en verde.
    try:
        print()
        if not hall:
            print("Sin valor en la ventana actual. (Respuesta honesta: hoy está flojo.)")
        else:
            print(f"{len(hall)} JUGADA(S) DE VALOR REAL:\n")
            for h in hall[:30]:
                ic = "🔴 VIVO" if h["estado"] == "VIVO" else "🟡 PRE"
                bp = ""
                if h.get("betplay_cuota"):
                    bp = f"  | Betplay {h['betplay_cuota']} (EV {h['betplay_ev']:+}%)"
                print(f"  {ic} {h['deporte'][:22]:22s} {h['partido'][:32]:32s}")
                print(f"       {h['jugada']:20s} @{h['cuota']:<5} {h['casa']:10s} "
                      f"Pinnacle {h['cuota_justa']} → EV +{h['ev']}%{bp}")
    except Exception as e:
        print(f"(resumen de consola omitido: {e})")
