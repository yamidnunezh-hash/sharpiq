#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reporte de efectividad de SharpIQ.  Uso:  python reporte_efectividad.py

Lee datos.js (PREDICCIONES_HISTORIAL + PROXIMOS_EVENTOS ya resueltos) y desglosa
win% y yield (unidades) por mercado, deporte, liga y tier. Muestra la CALIBRACION
(la probabilidad que dio el modelo vs cuanto gano de verdad) en cuanto haya datos
del campo 'prob' (se empieza a guardar desde 2026-06-06).

SOLO LECTURA: no modifica datos.js ni nada. Seguro de correr cuando sea.
"""
import os
import re
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(BASE, "..", "datos.js")


def cargar():
    txt = open(DATOS, encoding="utf-8").read()

    def arr(nombre):
        m = re.search(nombre + r"\s*=\s*\[(.*?)\n\];", txt, re.S)
        out = []
        if m:
            for o in re.findall(r"\{[^{}]*\}", m.group(1)):
                out.append({k: v for k, v in re.findall(r'(\w+):\s*"([^"]*)"', o)})
        return out

    return arr("PREDICCIONES_HISTORIAL"), arr("PROXIMOS_EVENTOS")


def pend(r):
    return (not r) or r in ("pending", "pendiente")


def mercado(pred):
    p = (pred or "").lower()
    if "under" in p:
        return "Under (goles)"
    if "over" in p:
        return "Over (goles)"
    if "btts" in p or "ambos" in p:
        return "BTTS"
    if "gana" in p or "victoria" in p:
        return "Gana (1X2/ganador)"
    if "handicap" in p or "ndicap" in p:
        return "Handicap"
    if "doble" in p:
        return "Doble oportunidad"
    return "Otro"


def deporte(liga):
    l = (liga or "").lower()
    if any(k in l for k in ["mlb", "kbo", "npb", "baseball"]):
        return "Beisbol"
    if any(k in l for k in ["nba", "wnba", "euroleague", "euroliga", "basket"]):
        return "Basket"
    if "nhl" in l or "hockey" in l:
        return "NHL"
    if any(k in l for k in ["nfl", "ncaa", "cfl", "ufl", "americ"]):
        return "Futbol americano"
    if any(k in l for k in ["atp", "wta", "tenis", "roland", "wimbledon", " open"]):
        return "Tenis"
    if "balonmano" in l or "handball" in l:
        return "Balonmano"
    return "Futbol"


def unidades(p):
    try:
        c = float(p.get("cuota", "0"))
    except (ValueError, TypeError):
        c = 0
    if p.get("resultado") == "win":
        return c - 1
    if p.get("resultado") == "loss":
        return -1
    return 0


def tabla(titulo, picks, keyfn, minimo=1):
    g = defaultdict(lambda: [0, 0, 0.0])
    for p in picks:
        k = keyfn(p)
        g[k][0] += 1
        if p.get("resultado") == "win":
            g[k][1] += 1
        g[k][2] += unidades(p)
    print("\n=== %s ===" % titulo)
    print("  %-26s %6s %6s %10s" % ("categoria", "picks", "win%", "yield/u"))
    for k, (n, w, u) in sorted(g.items(), key=lambda x: -x[1][2]):
        if n < minimo:
            continue
        marca = " <-- gana" if u / n > 0.05 else (" <-- pierde" if u / n < -0.05 else "")
        print("  %-26s %6d %5d%% %+9.2fu%s" % (k, n, round(w / n * 100), u / n, marca))


def calibracion(picks):
    print("\n=== CALIBRACION (lo que dijo el modelo vs lo que gano de verdad) ===")
    conp = [p for p in picks if p.get("prob")]
    if not conp:
        print("  (aun sin datos del campo 'prob' — se llena con los picks nuevos,")
        print("   sobre todo con el Mundial. Vuelve a correr este reporte mas adelante.)")
        return
    buck = defaultdict(lambda: [0, 0])
    for p in conp:
        try:
            pr = float(p["prob"])
        except (ValueError, TypeError):
            continue
        b = (">=70%" if pr >= 70 else "60-70%" if pr >= 60 else
             "50-60%" if pr >= 50 else "40-50%" if pr >= 40 else "<40%")
        buck[b][0] += 1
        if p.get("resultado") == "win":
            buck[b][1] += 1
    print("  %-12s %6s %16s" % ("modelo dijo", "picks", "gano de verdad"))
    for b in [">=70%", "60-70%", "50-60%", "40-50%", "<40%"]:
        if b in buck:
            n, w = buck[b]
            print("  %-12s %6d %15d%%" % (b, n, round(w / n * 100)))
    print("  (idealmente cada fila gana ~lo que dijo. Si '60-70%' gana 45%, el modelo")
    print("   esta INFLADO en esa franja y conviene bajarlo.)")


def main():
    hist, prox = cargar()
    todos = hist + [p for p in prox if not pend(p.get("resultado"))]
    res = [p for p in todos if p.get("resultado") in ("win", "loss")]
    print("=" * 52)
    print("  SHARPIQ - REPORTE DE EFECTIVIDAD")
    print("=" * 52)
    if not res:
        print("  Sin picks resueltos aun.")
        return
    w = sum(1 for p in res if p["resultado"] == "win")
    u = sum(unidades(p) for p in res)
    pend_n = sum(1 for p in prox if pend(p.get("resultado")))
    print("  Resueltos: %d   |   %dW / %dL   |   %d%% aciertos" %
          (len(res), w, len(res) - w, round(w / len(res) * 100)))
    print("  Yield total: %+.2f u   (%+.3f u por pick)" % (u, u / len(res)))
    print("  Pendientes ahora: %d" % pend_n)
    print("  NOTA: muestra chica = senales, no veredictos. Se vuelve fiable hacia 100+ picks.")
    tabla("POR MERCADO", res, lambda p: mercado(p.get("prediccion", "")))
    tabla("POR DEPORTE", res, lambda p: deporte(p.get("liga", "")))
    tabla("POR LIGA (min 2 picks)", res, lambda p: (p.get("liga", "?") or "?")[:24], minimo=2)
    tabla("POR TIER", res, lambda p: p.get("tier", "(sin tier)"))
    calibracion(res)
    print()


if __name__ == "__main__":
    main()
