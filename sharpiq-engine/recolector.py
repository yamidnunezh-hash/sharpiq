# -*- coding: utf-8 -*-
"""
SharpIQ — Recolector Diario
Corre cada noche: guarda resultados + stats del día anterior en la DB local.
Con el tiempo construyes tu propia base de datos histórica sin pagar APIs.
"""
import os
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import APIFOOTBALL_KEY
from database import (inicializar, guardar_partido, guardar_estadisticas,
                      actualizar_promedios_equipo, resumen)
from motor import LIGAS_APIFB, _apifb

STAT_MAP = {
    "Shots on Goal":      "tiros_puerta",
    "Shots off Goal":     "tiros_fuera",
    "Total Shots":        "tiros_total",
    "Blocked Shots":      "tiros_bloqueados",
    "Corner Kicks":       "corners",
    "Yellow Cards":       "tarjetas_amarillas",
    "Red Cards":          "tarjetas_rojas",
    "Fouls":              "faltas",
    "Ball Possession":    "posesion",
    "Total passes":       "pases_totales",
    "Passes accurate":    "pases_precisos",
}


def recolectar_dia(fecha_iso):
    print(f"\n  Recolectando: {fecha_iso}")

    data = _apifb("fixtures", {"date": fecha_iso})
    if not data or not data.get("response"):
        print("  Sin datos para esta fecha")
        return 0

    fixtures = [f for f in data["response"]
                if f["league"]["id"] in LIGAS_APIFB
                and f["fixture"]["status"]["short"] == "FT"]

    print(f"  Partidos finalizados: {len(fixtures)}")
    guardados = 0

    for f in fixtures:
        fid       = f["fixture"]["id"]
        fecha     = f["fixture"]["date"][:10]
        liga_id   = f["league"]["id"]
        liga_nom  = LIGAS_APIFB[liga_id]
        local     = f["teams"]["home"]["name"]
        visitante = f["teams"]["away"]["name"]
        gl        = f["score"]["fulltime"]["home"] or 0
        gv        = f["score"]["fulltime"]["away"] or 0

        guardar_partido(fid, fecha, liga_id, liga_nom, local, visitante, gl, gv, "FT")

        # Obtener estadísticas del partido
        stats_data = _apifb("fixtures/statistics", {"fixture": fid})
        time.sleep(0.3)  # respetar rate limit

        if stats_data and stats_data.get("response"):
            for team_stats in stats_data["response"]:
                equipo   = team_stats["team"]["name"]
                es_local = 1 if equipo == local else 0
                stats    = {}
                for s in team_stats.get("statistics", []):
                    key = STAT_MAP.get(s["type"])
                    if key:
                        val = s["value"]
                        if isinstance(val, str) and "%" in val:
                            stats[key] = val  # posesion como string "55%"
                        else:
                            try:
                                stats[key] = int(val or 0)
                            except (ValueError, TypeError):
                                stats[key] = 0
                guardar_estadisticas(fid, equipo, es_local, stats)

        guardados += 1

    # Actualizar promedios de todos los equipos involucrados
    equipos_vistos = set()
    for f in fixtures:
        equipos_vistos.add((f["teams"]["home"]["name"], f["league"]["id"]))
        equipos_vistos.add((f["teams"]["away"]["name"], f["league"]["id"]))

    for equipo, liga_id in equipos_vistos:
        actualizar_promedios_equipo(equipo, liga_id)

    print(f"  Guardados: {guardados} partidos con stats")
    return guardados


def recolectar_ayer():
    ayer = (date.today() - timedelta(days=1)).isoformat()
    return recolectar_dia(ayer)


def recolectar_rango(dias_atras=7):
    """Recolecta los últimos N días — útil para poblar la DB inicial."""
    total = 0
    for i in range(dias_atras, 0, -1):
        fecha = (date.today() - timedelta(days=i)).isoformat()
        total += recolectar_dia(fecha)
        time.sleep(1)
    return total


if __name__ == "__main__":
    inicializar()

    if len(sys.argv) > 1:
        if sys.argv[1] == "ayer":
            recolectar_ayer()
        elif sys.argv[1] == "semana":
            print("  Recolectando últimos 7 días...")
            recolectar_rango(7)
        elif sys.argv[1] == "mes":
            print("  Recolectando últimos 30 días...")
            recolectar_rango(30)
        elif sys.argv[1].startswith("20"):
            recolectar_dia(sys.argv[1])
    else:
        recolectar_ayer()

    resumen()
