# -*- coding: utf-8 -*-
"""
SharpIQ — Arbitraje ESPANA (sobre odds-api.io, 26 casas espanolas)

Yamid viaja a Espana el 1-ago-26 para probar/pautar el arbitraje. Espana tiene
26 casas apostables en odds-api.io (vs 4 en Colombia) -> el arbitraje SI tiene
chance alla. Incluye Betfair Exchange (cuotas sin margen = mas arbs).

OJO PLAN: el free tier de odds-api.io da 2 casas. Para usar las 26 hace falta
el plan Growth (£179, 10 casas) o Pro (£229, 15). Este modulo pide TODAS las
casas; la API devuelve solo las del plan. Con 2 casas: casi 0 arbs (normal).
Con 10-15: ahi empiezan a salir. Correr arb_logger_es un dia para el numero real.

Estructura odds-api.io (distinta a The Odds API):
  bookmakers: { "Casa": [ {name:"ML", odds:[{home,draw,away}]},
                          {name:"Totals", odds:[{hdp,over,under}]},
                          {name:"Both Teams To Score", odds:[{yes,no}]} ] }
"""
import os
import requests
from casas_por_pais import CASAS_ES_ODDSAPIIO, CASAS_BR_ODDSAPIIO

API  = "https://api.odds-api.io/v3"

# Casas segun el pais objetivo del arbitraje.
CASAS_POR_PAIS = {
    "ES": CASAS_ES_ODDSAPIIO,   # 24 casas espanolas
    "BR": CASAS_BR_ODDSAPIIO,   # 27 casas brasilenas (el mejor mercado)
}

# Ligas que le interesan a cada mercado (substring del league.name).
LIGAS_POR_PAIS = {
    "ES": ("spain -", "la liga", "premier", "serie a", "bundesliga",
           "ligue 1", "champions", "europa"),
    "BR": ("brazil -", "brasileiro", "copa do brasil", "libertadores",
           "sudamericana", "paulista", "carioca"),
}

# Ligas espanolas/europeas + verano (para tener partidos siempre) — compat
LIGAS_ES = [
    "spain-la-liga", "spain-la-liga-2", "spain-copa-del-rey",
    "england-premier-league", "italy-serie-a", "germany-bundesliga",
    "france-ligue-1", "uefa-champions-league",
    # verano (por si las de arriba estan de pretemporada):
    "usa-mls", "brazil-serie-a", "mexico-liga-mx",
]

MAX_CUOTA_SANA  = 15.0
MAX_PROFIT_SANO = 6.0
MIN_PROFIT      = 0.1


def _key():
    from config import ODDSAPI_IO_KEY
    return ODDSAPI_IO_KEY


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def eventos_es(sport="football", pais="ES"):
    """Partidos sin jugar de las ligas del pais objetivo."""
    try:
        r = requests.get(f"{API}/events", params={"apiKey": _key(), "sport": sport}, timeout=30)
        if r.status_code != 200:
            return []
        objetivo = LIGAS_POR_PAIS.get(pais, LIGAS_POR_PAIS["ES"])
        return [e for e in r.json()
                if any(k in (e.get("league", {}) or {}).get("name", "").lower() for k in objetivo)
                and e.get("status") != "settled"]
    except Exception:
        return []


def odds_evento(event_id, pais="ES", casas=None):
    """Cuotas del evento para las casas del pais (por defecto las del pais dado)."""
    lista = ",".join(casas or CASAS_POR_PAIS.get(pais, CASAS_ES_ODDSAPIIO))[:400]
    try:
        r = requests.get(f"{API}/odds",
                         params={"apiKey": _key(), "eventId": event_id, "bookmakers": lista},
                         timeout=30)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


def _mejores(bookmakers, extraer):
    """Dado {casa:[mercados]}, devuelve {lado: (mejor_cuota, casa)} usando extraer()."""
    best = {}
    for casa, mercados in (bookmakers or {}).items():
        for m in mercados:
            for lado, cuota in extraer(m):
                c = _f(cuota)
                if c <= 1.01 or c > MAX_CUOTA_SANA:
                    continue
                if lado not in best or c > best[lado][0]:
                    best[lado] = (c, casa)
    return best


def _arb(best, lados_necesarios):
    """Si las mejores cuotas de esos lados dan arbitraje, devuelve el detalle."""
    if not all(l in best for l in lados_necesarios):
        return None
    casas = {best[l][1] for l in lados_necesarios}
    if len(casas) < 2:                       # deben ser casas distintas
        return None
    suma = sum(1 / best[l][0] for l in lados_necesarios)
    if suma >= 1.0:
        return None
    profit = round((1 / suma - 1) * 100, 2)
    if not (MIN_PROFIT <= profit <= MAX_PROFIT_SANO):
        return None
    return {
        "profit_pct": profit,
        "lados": [{"lado": l, "cuota": best[l][0], "casa": best[l][1],
                   "stake": round((1 / best[l][0]) / suma * 100, 2)} for l in lados_necesarios],
    }


def detectar(evento_odds):
    """Todos los arbitrajes de un evento (ML 3 vias + Totals/BTTS 2 vias)."""
    bk = evento_odds.get("bookmakers", {}) or {}
    out = []
    ev = f"{evento_odds.get('home','?')} vs {evento_odds.get('away','?')}"

    # ML (3 vias)
    bestml = _mejores(bk, lambda m: (
        [("home", m["odds"][0].get("home")), ("draw", m["odds"][0].get("draw")),
         ("away", m["odds"][0].get("away"))] if m.get("name") == "ML" and m.get("odds") else []))
    a = _arb(bestml, ["home", "draw", "away"])
    if a: out.append({**a, "partido": ev, "mercado": "1X2"})

    # Totals (2 vias por linea)
    for linea in (0.5, 1.5, 2.5, 3.5, 4.5):
        def _tot(m, _linea=linea):
            pares = []
            if m.get("name") != "Totals":
                return pares
            for o in m.get("odds", []):
                if abs(_f(o.get("hdp")) - _linea) < 0.01:
                    pares.append(("over", o.get("over")))
                    pares.append(("under", o.get("under")))
            return pares
        bestt = _mejores(bk, _tot)
        a = _arb(bestt, ["over", "under"])
        if a: out.append({**a, "partido": ev, "mercado": f"Total {linea}"})

    # BTTS (2 vias)
    bestb = _mejores(bk, lambda m: (
        [("si", m["odds"][0].get("yes")), ("no", m["odds"][0].get("no"))]
        if "both teams" in (m.get("name","").lower()) and m.get("odds") else []))
    a = _arb(bestb, ["si", "no"])
    if a: out.append({**a, "partido": ev, "mercado": "Ambos Anotan"})

    return out


def escanear(max_eventos=40, pais="ES"):
    """Escaneo completo del pais. Devuelve (lista de arbitrajes, nro de eventos)."""
    evs = eventos_es(pais=pais)
    arbs = []
    for e in evs[:max_eventos]:
        d = odds_evento(e["id"], pais=pais)
        if d:
            for a in detectar(d):
                a["pais"] = pais
                arbs.append(a)
    arbs.sort(key=lambda x: -x["profit_pct"])
    return arbs, len(evs)
