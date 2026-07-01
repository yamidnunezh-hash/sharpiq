# -*- coding: utf-8 -*-
"""
SharpIQ — Validación del motor 🦈
¿El motor de verdad tiene VENTAJA? Este script no inventa nada: lee los picks
históricos YA resueltos (PREDICCIONES_HISTORIAL en datos.js) y mide:

  1. CALIBRACIÓN — cuando el motor dice 65%, ¿acierta ~65%? (lo más importante)
  2. RENDIMIENTO (ROI) — apostando 1 unidad plana a cada pick, ¿se gana o se pierde?
  3. Por RANGO DE CUOTA — ¿dónde está el valor real?

Uso:  python validar_motor.py            (reporte por consola)
      python validar_motor.py --json     (además guarda validacion_motor.json)
"""
import os, re, sys, json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATOS    = os.path.join(BASE_DIR, "..", "datos.js")


def _cargar_historial():
    """Lee PREDICCIONES_HISTORIAL de datos.js (sintaxis JS, claves sin comillas)."""
    try:
        t = open(DATOS, encoding="utf-8", errors="replace").read()
    except Exception as e:
        print(f"No pude leer datos.js: {e}")
        return []
    m = re.search(r"PREDICCIONES_HISTORIAL\s*=\s*\[(.*?)\];", t, re.DOTALL)
    if not m:
        return []
    picks = []
    for bloque in re.findall(r"\{[^{}]*\}", m.group(1)):
        def campo(k):
            g = re.search(rf'{k}\s*:\s*"([^"]*)"', bloque)
            return g.group(1).strip() if g else ""
        res = campo("resultado").lower()
        try:
            prob = float(campo("prob"))
        except ValueError:
            prob = None
        try:
            cuota = float(campo("cuota"))
        except ValueError:
            cuota = None
        picks.append({
            "fecha": campo("fecha"), "partido": campo("partido"),
            "liga": campo("liga"), "prediccion": campo("prediccion"),
            "prob": prob, "cuota": cuota, "resultado": res,
        })
    return picks


def _resueltos(picks):
    """Solo picks con resultado definido (win/loss/push) y datos completos."""
    return [p for p in picks
            if p["resultado"] in ("win", "loss", "push")
            and p["prob"] is not None and p["cuota"] is not None]


def _pct(x, n):
    return round(100 * x / n, 1) if n else 0.0


def calibracion(picks):
    """Agrupa por rango de probabilidad y compara prob predicha vs aciertos reales."""
    bandas = [(0, 40), (40, 50), (50, 60), (60, 70), (70, 80), (80, 101)]
    filas = []
    for lo, hi in bandas:
        grupo = [p for p in picks if lo <= p["prob"] < hi and p["resultado"] != "push"]
        wins = sum(1 for p in grupo if p["resultado"] == "win")
        n = len(grupo)
        if not n:
            continue
        prob_media  = sum(p["prob"] for p in grupo) / n
        acierto_real = _pct(wins, n)
        filas.append({
            "banda": f"{lo}-{hi if hi <= 100 else 100}%",
            "n": n, "prob_predicha": round(prob_media, 1),
            "acierto_real": acierto_real, "diff": round(acierto_real - prob_media, 1),
        })
    return filas


def rendimiento(picks):
    """ROI apostando 1 unidad plana a cada pick resuelto (win/loss)."""
    jugables = [p for p in picks if p["resultado"] in ("win", "loss")]
    n = len(jugables)
    wins   = sum(1 for p in jugables if p["resultado"] == "win")
    losses = n - wins
    profit = sum((p["cuota"] - 1) if p["resultado"] == "win" else -1 for p in jugables)
    cuota_media = sum(p["cuota"] for p in jugables) / n if n else 0
    return {
        "n": n, "wins": wins, "losses": losses,
        "win_rate": _pct(wins, n),
        "roi": round(100 * profit / n, 2) if n else 0.0,
        "profit_unidades": round(profit, 2),
        "cuota_media": round(cuota_media, 2),
    }


def por_rango_cuota(picks):
    rangos = [("Favoritos (<1.50)", 0, 1.50), ("1.50-2.00", 1.50, 2.00),
              ("2.00-3.00", 2.00, 3.00), ("Underdogs (>3.00)", 3.00, 99)]
    out = []
    for nombre, lo, hi in rangos:
        grupo = [p for p in picks if lo <= p["cuota"] < hi and p["resultado"] in ("win", "loss")]
        r = rendimiento(grupo)
        if r["n"]:
            out.append({"rango": nombre, **r})
    return out


def _linea():
    print("─" * 60)


def main(guardar_json=False):
    picks = _cargar_historial()
    res = _resueltos(picks)
    print("\n🦈  VALIDACIÓN DEL MOTOR SharpIQ")
    _linea()
    print(f"Picks en historial: {len(picks)}  |  resueltos y medibles: {len(res)}")
    if len(res) < 20:
        print("⚠️  Muestra pequeña: los números son indicativos, no concluyentes aún.")

    # 1) CALIBRACIÓN
    print("\n📊  CALIBRACIÓN — ¿la probabilidad del motor es honesta?")
    _linea()
    cal = calibracion(res)
    print(f"{'Banda':<10}{'Picks':>6}{'Dice':>8}{'Acierta':>9}{'Dif':>7}")
    for f in cal:
        señal = "✅" if abs(f["diff"]) <= 7 else ("⚠️" if f["diff"] < 0 else "🎯")
        print(f"{f['banda']:<10}{f['n']:>6}{f['prob_predicha']:>7}%{f['acierto_real']:>8}%"
              f"{f['diff']:>+6}  {señal}")
    print("  Lectura: 'Dice' = prob promedio del motor · 'Acierta' = % real de aciertos.")
    print("  ✅ bien calibrado (±7) · ⚠️ sobreconfía (promete de más) · 🎯 conservador.")

    # 2) RENDIMIENTO
    print("\n💰  RENDIMIENTO — 1 unidad plana por pick")
    _linea()
    r = rendimiento(res)
    signo = "GANANCIA ✅" if r["roi"] > 0 else "PÉRDIDA ❌"
    print(f"Récord: {r['wins']}W - {r['losses']}L  ({r['win_rate']}% aciertos)")
    print(f"Cuota media: {r['cuota_media']}  |  Break-even: "
          f"{round(100/r['cuota_media'],1) if r['cuota_media'] else 0}% necesario")
    print(f"ROI: {r['roi']:+}%  ({r['profit_unidades']:+} unidades)  →  {signo}")

    # 3) POR RANGO DE CUOTA
    print("\n🎯  POR RANGO DE CUOTA — ¿dónde está el valor?")
    _linea()
    print(f"{'Rango':<20}{'Picks':>6}{'Aciertos':>10}{'ROI':>9}")
    for f in por_rango_cuota(res):
        print(f"{f['rango']:<20}{f['n']:>6}{f['win_rate']:>9}%{f['roi']:>+8}%")

    print()
    if guardar_json:
        salida = {"total": len(picks), "medibles": len(res),
                  "calibracion": cal, "rendimiento": r,
                  "por_cuota": por_rango_cuota(res)}
        ruta = os.path.join(BASE_DIR, "..", "validacion_motor.json")
        json.dump(salida, open(ruta, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"Guardado: {ruta}\n")


if __name__ == "__main__":
    main(guardar_json="--json" in sys.argv)
