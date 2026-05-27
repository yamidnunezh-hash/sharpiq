# -*- coding: utf-8 -*-
"""
SharpIQ — Stats Partido
Uso: python stats_partido.py "Equipo Local" "Equipo Visitante"

Muestra forma reciente, goles, H2H y lesiones antes de cualquier análisis.
Llama directamente a API-Football (api-sports.io).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from motor import _apifb, TEAM_IDS, obtener_h2h, obtener_lesiones, APIFOOTBALL_KEY


def forma_detallada(equipo, n=5):
    """Últimos N partidos finalizados con resultado individual + stats."""
    team_id = TEAM_IDS.get(equipo)
    if not team_id:
        return None

    data = _apifb("fixtures", {"team": team_id, "last": n, "status": "FT"})
    if not data or not data.get("response"):
        return None

    fixtures = data["response"]
    resultados = []
    gf_total = gc_total = 0
    home_gf = home_gc = home_n = 0
    away_gf = away_gc = away_n = 0

    for f in fixtures:
        es_local = f["teams"]["home"]["id"] == team_id
        sh = f["score"]["fulltime"]["home"] or 0
        sa = f["score"]["fulltime"]["away"] or 0
        gf = sh if es_local else sa
        gc = sa if es_local else sh

        if gf > gc:    res = "W"
        elif gf == gc: res = "D"
        else:          res = "L"

        rival     = f["teams"]["away"]["name"] if es_local else f["teams"]["home"]["name"]
        local_str = f["teams"]["home"]["name"]
        visit_str = f["teams"]["away"]["name"]
        liga      = f["league"]["name"]
        fecha     = f["fixture"]["date"][:10]

        resultados.append({
            "res": res, "gf": gf, "gc": gc,
            "local_str": local_str[:16], "visit_str": visit_str[:16],
            "marcador": f"{sh}-{sa}",
            "es_local": es_local, "rival": rival,
            "liga": liga[:22], "fecha": fecha,
        })

        gf_total += gf; gc_total += gc
        if es_local:
            home_gf += gf; home_gc += gc; home_n += 1
        else:
            away_gf += gf; away_gc += gc; away_n += 1

    total = len(resultados)
    if total == 0:
        return None

    return {
        "equipo":           equipo,
        "resultados":       resultados,
        "forma_str":        "-".join(r["res"] for r in resultados),
        "wins":             sum(1 for r in resultados if r["res"] == "W"),
        "draws":            sum(1 for r in resultados if r["res"] == "D"),
        "losses":           sum(1 for r in resultados if r["res"] == "L"),
        "gf_avg":           round(gf_total / total, 2),
        "gc_avg":           round(gc_total / total, 2),
        "home_gf_avg":      round(home_gf / home_n, 2) if home_n else 0,
        "home_gc_avg":      round(home_gc / home_n, 2) if home_n else 0,
        "away_gf_avg":      round(away_gf / away_n, 2) if away_n else 0,
        "away_gc_avg":      round(away_gc / away_n, 2) if away_n else 0,
        "home_n": home_n, "away_n": away_n,
    }


def imprimir_stats(local_nombre, visitante_nombre):
    if not APIFOOTBALL_KEY:
        print("\n  ⚠️  APIFOOTBALL_KEY no configurada en config.py\n")
        return

    sep = "━" * 58
    print(f"\n{sep}")
    print(f"  📡 SHARPIQ STATS — {local_nombre}  vs  {visitante_nombre}")
    print(sep)

    for equipo, es_local in [(local_nombre, True), (visitante_nombre, False)]:
        rol     = "LOCAL" if es_local else "VISITANTE"
        stats   = forma_detallada(equipo, n=5)

        print(f"\n  {'🏠' if es_local else '✈️ '} {equipo.upper()} [{rol}]")
        print(f"  {'─' * 52}")

        if not stats:
            print(f"  ⚠️  Sin datos disponibles (verifica el nombre en TEAM_IDS)")
        else:
            # Últimos 5 partidos
            for r in stats["resultados"]:
                icono = "✅" if r["res"] == "W" else ("➖" if r["res"] == "D" else "❌")
                cond  = "🏠" if r["es_local"] else "✈️ "
                print(f"    {icono} {cond} {r['local_str']:16} {r['marcador']:5} {r['visit_str']:16}  {r['liga']}")

            print(f"  {'─' * 52}")
            w, d, l = stats["wins"], stats["draws"], stats["losses"]
            pct = round(w / (w + d + l) * 100) if (w + d + l) else 0
            print(f"  Forma:            {stats['forma_str']}  →  {w}V {d}E {l}D  ({pct}% victorias)")
            print(f"  Ataque/Defensa:   GF {stats['gf_avg']} por partido  |  GC {stats['gc_avg']} por partido")

            if es_local and stats["home_n"]:
                print(f"  Como LOCAL  ({stats['home_n']}p):  GF {stats['home_gf_avg']}  |  GC {stats['home_gc_avg']}")
            elif not es_local and stats["away_n"]:
                print(f"  Como VISITA ({stats['away_n']}p):  GF {stats['away_gf_avg']}  |  GC {stats['away_gc_avg']}")

        # Lesionados/suspendidos
        bajas = obtener_lesiones(equipo)
        if bajas:
            nombres = ", ".join(b.get("nombre", "?") for b in bajas[:4])
            print(f"  Bajas:            {nombres}")
        else:
            print(f"  Bajas:            Sin bajas confirmadas")

    # ── H2H ──
    print(f"\n  🔁 H2H DIRECTO — Últimos 10 encuentros")
    print(f"  {'─' * 52}")
    h2h = obtener_h2h(local_nombre, visitante_nombre)
    if h2h:
        vl  = round(h2h["victorias_local"]  * 100)
        ve  = round(h2h["empates"]          * 100)
        vv  = round(h2h["victorias_visita"] * 100)
        gxp = h2h["goles_por_partido"]
        n   = h2h["partidos"]
        print(f"  {local_nombre[:20]:20}  {vl}% victorias")
        print(f"  Empates:              {ve}%")
        print(f"  {visitante_nombre[:20]:20}  {vv}% victorias")
        print(f"  Goles promedio H2H:   {gxp} por partido  ({n} partidos)")

        # Señal Under/Over basada en H2H
        if gxp < 2.0:
            print(f"  📉 Señal H2H:         Historial MUY BAJO en goles → apoya Under")
        elif gxp < 2.5:
            print(f"  📉 Señal H2H:         Historial BAJO en goles → apoya Under 2.5")
        elif gxp < 3.0:
            print(f"  📊 Señal H2H:         Historial MEDIO → mercado equilibrado")
        else:
            print(f"  📈 Señal H2H:         Historial ALTO en goles → apoya Over 2.5")
    else:
        print(f"  Sin H2H suficiente registrado (< 3 partidos)")

    print(f"\n{sep}\n")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        local     = " ".join(sys.argv[1].split())
        visitante = " ".join(sys.argv[2].split())
        imprimir_stats(local, visitante)
    elif len(sys.argv) == 2:
        print("Uso: python stats_partido.py \"Local\" \"Visitante\"")
    else:
        # Demo con el partido de hoy
        imprimir_stats("Peñarol", "Independiente Santa Fe")
