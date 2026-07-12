"""
SharpIQ — DETECTOR DE VALOR (PRE-PARTIDO + EN VIVO) 🦈
═══════════════════════════════════════════════════════════════════════════════
Los clientes piden picks EN VIVO ("dame algo para apostar ahora, al minuto 60").
Esto lo detecta — SIN pagar nada extra: el plan actual de The Odds API YA devuelve
cuotas in-play (verificado 11-jul-2026 con Argentina-Suiza en curso, min 53).

CÓMO ENCUENTRA EL VALOR
    Pinnacle es la casa más eficiente del mundo. Su precio (sin margen) es la
    mejor estimación pública de la probabilidad real. Las casas "blandas"
    (Betsson, Unibet, LeoVegas...) tardan en ajustar — sobre todo EN VIVO.

        valor (EV) = cuota_de_la_blanda × prob_real_de_pinnacle − 1

    Ejemplo real detectado: Betsson pagaba 2.48 el Over 2.5 que Pinnacle
    valoraba en 2.12 -> Betsson iba atrasada -> +16% de EV.

    Es la misma idea que Yamid vio a mano (Betsson 3.4 vs Rushbet 5.5), pero
    mejor: en vez de comparar dos casas cualquiera, comparamos contra la VERDAD
    (Pinnacle). Así sirve para CUALQUIER casa donde el cliente apueste
    (Rushbet, Wplay, Codere... aunque no estén en la API).

⚠️ MODO PAPEL POR DEFECTO — NO PUBLICA NADA.
   Registra en live_valor_log.jsonl y mide LO CRÍTICO: ¿la cuota SOBREVIVE el
   tiempo que tarda el VIP en leer el Telegram y apostar? Si se evapora en
   segundos, mandaríamos a la gente a una cuota que ya no existe: eso destruye
   la confianza más rápido que perder. El 64.2% del motor NO se toca hasta que
   2 semanas de registro demuestren que el valor es real Y alcanzable.

    python live_valor.py                 # escanea PRE + VIVO, modo papel
    python live_valor.py --ver           # solo muestra, no registra
    python live_valor.py --alertar       # ADEMÁS avisa a Yamid por Telegram (privado)
    python live_valor.py --revisar       # ¿sobrevivieron las cuotas registradas?
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import requests

from config import ODDS_API_KEY

BASE = "https://api.the-odds-api.com/v4"
LOG  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_valor_log.jsonl")

DEPORTES = [
    "soccer_fifa_world_cup", "soccer_epl", "soccer_spain_la_liga",
    "soccer_italy_serie_a", "soccer_germany_bundesliga", "soccer_france_ligue_one",
    "soccer_uefa_champs_league", "soccer_conmebol_copa_libertadores",
    "soccer_conmebol_copa_sudamericana", "soccer_brazil_campeonato",
    "soccer_colombia_primera_a", "soccer_argentina_primera_division",
]
SHARP   = "pinnacle"          # el termómetro de la verdad
BLANDAS = "betsson,unibet,bet365,williamhill,betway,leovegas,livescorebet,marathonbet,coolbet"
MERCADOS = "h2h,totals"

# El margen EN VIVO es más alto -> exigimos más EV que en pre-partido.
EV_MIN_VIVO = 0.05
EV_MIN_PRE  = 0.03
EDGE_MAXIMO = 0.15            # >15% sobre Pinnacle = error de datos, no oportunidad
VENTANA_PRE = 6 * 60          # pre-partido: hasta 6 h antes

# MISMAS REGLAS DURAS DEL MOTOR (las que sostienen el 64.2%). Un longshot con
# "+EV" es veneno: al 4% de probabilidad el VIP pierde 22 seguidas antes de
# acertar una — se va del canal antes del acierto. Matemática ≠ producto.
PROB_MINIMA  = 0.30           # nada por debajo del 30% de probabilidad
CUOTA_MAXIMA = 5.5            # nada de cuotas de lotería
CUOTA_MINIMA = 1.30           # por debajo, el margen se come todo


def _get(url, params):
    try:
        r = requests.get(url, params=params, timeout=15)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def _sin_margen(cuotas: dict) -> dict:
    """Quita el margen de la casa -> probabilidades que suman 1 (precio justo)."""
    inv = {k: 1.0 / v for k, v in cuotas.items() if v and v > 1}
    total = sum(inv.values())
    return {k: v / total for k, v in inv.items()} if total else {}


# ── TRADUCTOR DE LÍNEAS (la pieza clave del sistema) ─────────────────────────
# EN VIVO Pinnacle mueve su línea a cada rato (2.5 -> 2.25 -> 2.0) mientras las
# casas blandas se quedan quietas en 2.5. Si solo comparáramos líneas IDÉNTICAS,
# el detector quedaría CIEGO justo cuando más valor hay.
#
# Solución: de la línea de Pinnacle deducimos cuántos goles espera el mercado
# (lambda de Poisson) y con eso calculamos el precio justo de CUALQUIER otra
# línea. Así podemos comparar Betsson Over 2.5 contra Pinnacle Over 2.0.

def _poisson_cola(lam: float, k: float) -> float | None:
    """Probabilidad de GANAR un Over de línea k, con Poisson(lam).

    ⚠️ El tipo de línea cambia la matemática — confundirlo genera VALOR FALSO:
      · Línea .5 (2.5): gana con 3+ goles. Sin empate. -> P(X >= 3)
      · Línea ENTERA (2.0): gana con 3+, pero con EXACTAMENTE 2 hay PUSH (te
        devuelven la plata). El precio justo NO es P(X>=3) sino P(X>=3)
        condicionada a que no haya push.
      · Línea .25/.75 (asiática partida): media apuesta en cada línea vecina.
        Es enredada -> devolvemos None (no opinamos) antes que opinar mal.
    """
    import math
    n = int(math.floor(k))
    frac = k - n

    def pmf(i):
        return math.exp(-lam) * lam ** i / math.factorial(i)

    p_mayor = max(0.0, 1.0 - sum(pmf(i) for i in range(0, n + 1)))   # P(X >= n+1)

    if abs(frac - 0.5) < 1e-9:            # línea .5 -> limpia, sin push
        return min(1.0, p_mayor)
    if frac < 1e-9:                        # línea entera -> hay PUSH en X == n
        p_push  = pmf(n)
        p_menor = max(0.0, 1.0 - p_mayor - p_push)
        den = p_mayor + p_menor
        return (p_mayor / den) if den > 1e-9 else None
    return None                            # .25 / .75 -> no opinamos


def _lambda_desde_linea(linea: float, p_over: float) -> float | None:
    """Deduce los goles esperados (lambda) que hacen que P(Over linea) = p_over.

    Búsqueda binaria (forma robusta de invertir la Poisson).
    """
    if not (0.02 < p_over < 0.98):
        return None
    if _poisson_cola(1.0, linea) is None:   # línea que no sabemos tratar
        return None
    lo, hi = 0.05, 12.0
    for _ in range(60):
        mid = (lo + hi) / 2
        p = _poisson_cola(mid, linea)
        if p is None:
            return None
        if p < p_over:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _probs_totales_pinnacle(mercados: list) -> dict:
    """De las líneas de totales de Pinnacle -> lambda del mercado -> permite
    valorar CUALQUIER línea. Devuelve {'_lambda': x, 'Over|2.5': p, ...}."""
    lams = []
    for m in mercados:
        if m.get("key") != "totals":
            continue
        por_linea = {}
        for o in m.get("outcomes", []):
            pt = o.get("point")
            if pt is None:
                continue
            por_linea.setdefault(pt, {})[o["name"]] = o["price"]
        for pt, cu in por_linea.items():
            if "Over" not in cu or "Under" not in cu:
                continue
            p = _sin_margen(cu).get("Over")
            lam = _lambda_desde_linea(float(pt), p) if p else None
            if lam:
                lams.append(lam)
    if not lams:
        return {}
    lam = sum(lams) / len(lams)          # promedio de todas las líneas de Pinnacle
    return {"_lambda": lam}


def eventos(deporte: str) -> list:
    """Devuelve eventos EN VIVO y PRE-PARTIDO (marcados con `_estado`)."""
    ev = _get(f"{BASE}/sports/{deporte}/events", {"apiKey": ODDS_API_KEY}) or []
    ahora = datetime.now(timezone.utc)
    out = []
    for e in ev:
        try:
            ini = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
        except Exception:
            continue
        mins = (ahora - ini).total_seconds() / 60      # >0 = ya empezó
        if 0 < mins < 115:
            e["_estado"], e["_minuto"] = "VIVO", int(mins)
            out.append(e)
        elif -VENTANA_PRE < mins <= 0:
            e["_estado"], e["_minuto"] = "PRE", int(-mins)   # min. para que empiece
            out.append(e)
    return out


def valor_del_partido(deporte: str, ev: dict) -> list:
    """Compara cada casa blanda contra Pinnacle. Devuelve jugadas con valor."""
    d = _get(f"{BASE}/sports/{deporte}/events/{ev['id']}/odds", {
        "apiKey": ODDS_API_KEY, "bookmakers": f"{SHARP},{BLANDAS}",
        "markets": MERCADOS, "oddsFormat": "decimal",
    })
    if not d:
        return []

    justo, mk_pinn = {}, []
    for bm in d.get("bookmakers", []):
        if bm["key"] != SHARP:
            continue
        mk_pinn = bm.get("markets", [])
        for m in mk_pinn:
            cuotas = {}
            for o in m.get("outcomes", []):
                k = o["name"] + (f"|{o['point']}" if o.get("point") is not None else "")
                cuotas[k] = o["price"]
            justo[m["key"]] = _sin_margen(cuotas)
    if not justo:
        return []      # sin Pinnacle no hay verdad -> no opinamos

    # Goles esperados según Pinnacle -> permite valorar líneas que Pinnacle
    # NO ofrece ahora mismo (en vivo mueve su línea constantemente).
    lam = _probs_totales_pinnacle(mk_pinn).get("_lambda")

    ev_min = EV_MIN_VIVO if ev["_estado"] == "VIVO" else EV_MIN_PRE
    hallazgos = []
    for bm in d.get("bookmakers", []):
        if bm["key"] == SHARP:
            continue
        for m in bm.get("markets", []):
            probs = justo.get(m["key"], {})
            for o in m.get("outcomes", []):
                k = o["name"] + (f"|{o['point']}" if o.get("point") is not None else "")
                cuota = o.get("price")
                p = probs.get(k)
                traducida = False
                # Pinnacle NO tiene esta línea -> la deducimos de su lambda.
                if p is None and m["key"] == "totals" and lam and o.get("point") is not None:
                    pov = _poisson_cola(lam, float(o["point"]))
                    if pov is None:        # línea .25/.75 -> no opinamos
                        continue
                    p = pov if o["name"] == "Over" else 1.0 - pov
                    traducida = True
                if not p or not cuota:
                    continue
                # REGLAS DURAS (las del motor): nada de loterías ni cuotas muertas.
                if p < PROB_MINIMA or not (CUOTA_MINIMA <= cuota <= CUOTA_MAXIMA):
                    continue
                ev_pct = p * cuota - 1
                justa  = 1 / p
                if ev_pct >= ev_min and (cuota / justa - 1) <= EDGE_MAXIMO:
                    hallazgos.append({
                        "linea_traducida": traducida,
                        "estado":  ev["_estado"],
                        "partido": f"{ev['away_team']} @ {ev['home_team']}",
                        "minuto":  ev["_minuto"],
                        "deporte": deporte,
                        "evento_id": ev["id"],
                        "casa":    bm["key"],
                        "mercado": m["key"],
                        "jugada":  k.replace("|", " "),
                        "cuota":   cuota,
                        "cuota_justa": round(justa, 2),
                        "prob_real": round(p * 100, 1),
                        "ev":      round(ev_pct * 100, 1),
                    })
    return hallazgos


def escanear(registrar: bool = True) -> list:
    todos = []
    for dep in DEPORTES:
        for ev in eventos(dep):
            todos += valor_del_partido(dep, ev)
    todos.sort(key=lambda h: (h["estado"] != "VIVO", -h["ev"]))
    if registrar and todos:
        ts = datetime.now(timezone.utc).isoformat()
        with open(LOG, "a", encoding="utf-8") as f:
            for h in todos:
                f.write(json.dumps({**h, "ts": ts}, ensure_ascii=False) + "\n")
    return todos


# ── LO CRÍTICO: ¿la cuota sobrevive el tiempo de reacción del VIP? ────────────
def revisar_supervivencia(minutos_atras: int = 30) -> None:
    """Re-consulta las cuotas registradas y mide si SIGUEN VIVAS.

    Si una cuota detectada se evapora antes de que el VIP alcance a apostar, esa
    alerta NO sirve — publicarla sería mandar a la gente a un precio inexistente.
    Este es el dato que decide si el producto EN VIVO es viable o no.
    """
    if not os.path.exists(LOG):
        print("Aún no hay registro. Corre el escáner primero.")
        return
    ahora = datetime.now(timezone.utc)
    filas = []
    with open(LOG, encoding="utf-8") as f:
        for ln in f:
            try:
                h = json.loads(ln)
                # Registros viejos (primera versión) no traen deporte/evento_id -> saltar
                if not h.get("deporte") or not h.get("evento_id"):
                    continue
                dt = datetime.fromisoformat(h["ts"])
                edad = (ahora - dt).total_seconds() / 60
                if 1 <= edad <= minutos_atras:
                    h["_edad"] = edad
                    filas.append(h)
            except Exception:
                continue
    if not filas:
        print(f"Sin detecciones de los últimos {minutos_atras} min para revisar.")
        return

    print(f"SUPERVIVENCIA DE LA CUOTA — {len(filas)} detección(es)\n")
    vivas = muertas = 0
    for h in filas[-15:]:
        d = _get(f"{BASE}/sports/{h['deporte']}/events/{h['evento_id']}/odds", {
            "apiKey": ODDS_API_KEY, "bookmakers": h["casa"],
            "markets": h["mercado"], "oddsFormat": "decimal"})
        ahora_cuota = None
        for bm in (d or {}).get("bookmakers", []):
            for m in bm.get("markets", []):
                for o in m.get("outcomes", []):
                    k = o["name"] + (f" {o['point']}" if o.get("point") is not None else "")
                    if k == h["jugada"]:
                        ahora_cuota = o["price"]
        if ahora_cuota is None:
            estado = "✖ ya no existe"
            muertas += 1
        elif ahora_cuota >= h["cuota"] * 0.98:      # aguanta (o mejoró)
            estado = f"✔ SIGUE VIVA ({ahora_cuota})"
            vivas += 1
        else:
            estado = f"✖ bajó a {ahora_cuota}"
            muertas += 1
        print(f"  [{h['_edad']:.0f} min] {h['partido'][:28]:<28} {h['jugada']:<16} "
              f"@{h['cuota']:<5} en {h['casa']:<10} -> {estado}")
    tot = vivas + muertas
    print(f"\n  SOBREVIVEN: {vivas}/{tot} ({vivas/tot*100:.0f}%)" if tot else "")
    print("\n  >>> Si sobreviven <50%, las alertas EN VIVO NO son viables tal cual:")
    print("      el VIP no alcanzaría a apostar. Habría que filtrar solo las duraderas.")


def alertar_yamid(hallazgos: list) -> None:
    """Avisa a Yamid por Telegram PRIVADO (NO al canal VIP — sigue en pruebas)."""
    if not hallazgos:
        return
    try:
        from config import TELEGRAM_TOKEN, TELEGRAM_YAMID_ID
    except Exception:
        print("(sin config de Telegram — no se envía alerta)")
        return
    L = ["🧪 <b>SharpIQ — Detector de valor (MODO PRUEBA)</b>",
         "<i>Solo para ti. NO se envió a los VIP.</i>", ""]
    for h in hallazgos[:6]:
        icono = "🔴 EN VIVO" if h["estado"] == "VIVO" else "🟡 PRE"
        det = f"min {h['minuto']}" if h["estado"] == "VIVO" else f"en {h['minuto']} min"
        L.append(f"{icono} · {h['partido']} ({det})")
        L.append(f"   <b>{h['jugada']}</b> @ <b>{h['cuota']}</b> en {h['casa']}")
        L.append(f"   Pinnacle la valora en {h['cuota_justa']} → EV <b>+{h['ev']}%</b>")
        L.append("")
    L.append("⚠️ Hipótesis sin validar. Verifica que la cuota siga viva antes de nada.")
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": TELEGRAM_YAMID_ID, "text": "\n".join(L),
                            "parse_mode": "HTML"}, timeout=10)
        print("\n📲 Alerta enviada a tu Telegram privado (NO al canal VIP).")
    except Exception as e:
        print(f"(no se pudo enviar Telegram: {e})")


if __name__ == "__main__":
    if "--revisar" in sys.argv:
        revisar_supervivencia()
        sys.exit(0)

    registrar = "--ver" not in sys.argv
    print("🦈 SharpIQ — Detector de VALOR  ·  PRE-PARTIDO + EN VIVO")
    print("   MODO PAPEL: registra y avisa solo a Yamid. NO publica a los VIP.")
    print("═" * 70)

    hallazgos = escanear(registrar)
    if not hallazgos:
        print("\nSin valor ahora mismo. Eso es una respuesta válida 🦈")
    else:
        vivo = [h for h in hallazgos if h["estado"] == "VIVO"]
        pre  = [h for h in hallazgos if h["estado"] == "PRE"]
        print(f"\n{len(hallazgos)} jugada(s) con valor  "
              f"({len(vivo)} en vivo · {len(pre)} pre-partido)\n")
        for h in hallazgos[:12]:
            icono = "🔴 EN VIVO" if h["estado"] == "VIVO" else "🟡 PRE"
            det   = f"min ~{h['minuto']}" if h["estado"] == "VIVO" else f"empieza en {h['minuto']} min"
            print(f"  {icono}  {h['partido']}  ({det})")
            print(f"     {h['jugada']:<18} @ {h['cuota']:<6} en {h['casa']}")
            print(f"     Pinnacle: {h['cuota_justa']} (prob {h['prob_real']}%)  →  EV +{h['ev']}%")
            print()
        if "--alertar" in sys.argv:
            alertar_yamid(hallazgos)

    if registrar and hallazgos:
        print(f"Registrado en {os.path.basename(LOG)} — modo papel, NO se publicó.")
    print("\n⚠️  Antes de lanzarlo a los VIP hay que comprobar que la CUOTA SOBREVIVE")
    print("    el tiempo que tardan en leer y apostar:  python live_valor.py --revisar")
