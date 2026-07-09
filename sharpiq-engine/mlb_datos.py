"""
SharpIQ — MLB Stats API (statsapi.mlb.com)
═══════════════════════════════════════════════════════════════════════════════
FASE 1 del proyecto "MLB pulido": traer los datos crudos que alimentarán el
modelo de carreras (lanzador abridor + ofensiva/defensiva de equipo).

La API oficial de MLB es GRATIS y NO requiere API key.

Este módulo es INDEPENDIENTE: no importa ni modifica motor.py. Se puede correr
solo para inspeccionar los datos:

    python mlb_datos.py            # partidos de hoy con los inputs del modelo
    python mlb_datos.py 2026-07-10

Siguiente fase (modelo): con estos números se estiman las carreras esperadas de
cada equipo -> Poisson -> probabilidades de ganador / run line / over-under.
NO se publica nada hasta que un backtest demuestre que le gana al mercado.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import date

BASE = "https://statsapi.mlb.com/api/v1"
TEMPORADA = date.today().year
_cache: dict[str, dict] = {}


def _get(url: str, intentos: int = 4) -> dict:
    """GET con caché en memoria y reintentos.

    Un corte de red de dos segundos no puede tumbar un backtest de 30 minutos:
    reintenta con espera creciente (1s, 2s, 4s) antes de rendirse.
    """
    if url in _cache:
        return _cache[url]
    req = urllib.request.Request(url, headers={"User-Agent": "SharpIQ/1.0"})
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.load(r)
            _cache[url] = data
            return data
        except Exception:
            if intento == intentos - 1:
                raise
            time.sleep(2 ** intento)
    raise RuntimeError("inalcanzable")


def _stat(bloque: dict) -> dict:
    """Extrae el dict de stats de la respuesta (o {} si viene vacío)."""
    try:
        return bloque["stats"][0]["splits"][0]["stat"]
    except (KeyError, IndexError):
        return {}


def _f(v, por_defecto=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return por_defecto


# ── Lanzadores ────────────────────────────────────────────────────────────────
def stats_lanzador(player_id: int) -> dict:
    """ERA, WHIP y entradas lanzadas del abridor en la temporada."""
    if not player_id:
        return {}
    d = _get(f"{BASE}/people/{player_id}/stats"
             f"?stats=season&group=pitching&season={TEMPORADA}")
    s = _stat(d)
    if not s:
        return {}
    return {
        "era":      _f(s.get("era"), 4.50),          # carreras limpias / 9 entradas
        "whip":     _f(s.get("whip"), 1.30),         # corredores permitidos / entrada
        "entradas": _f(s.get("inningsPitched"), 0),
        "ponches":  int(s.get("strikeOuts") or 0),
        "bb":       int(s.get("baseOnBalls") or 0),
    }


# ── Equipos ───────────────────────────────────────────────────────────────────
def stats_equipo(team_id: int) -> dict:
    """Ofensiva (carreras anotadas) y defensiva (carreras permitidas) por partido."""
    hit = _stat(_get(f"{BASE}/teams/{team_id}/stats"
                     f"?stats=season&group=hitting&season={TEMPORADA}"))
    pit = _stat(_get(f"{BASE}/teams/{team_id}/stats"
                     f"?stats=season&group=pitching&season={TEMPORADA}"))
    jugados = int(hit.get("gamesPlayed") or 0) or 1
    return {
        "juegos":            jugados,
        "carreras_anotadas": int(hit.get("runs") or 0),
        "carreras_permitidas": int(pit.get("runs") or 0),
        # normalizadas POR PARTIDO -> son los insumos del modelo Poisson
        "ca_por_juego": round(int(hit.get("runs") or 0) / jugados, 3),
        "cp_por_juego": round(int(pit.get("runs") or 0) / jugados, 3),
        "ops":          _f(hit.get("ops"), 0.700),
        "era_equipo":   _f(pit.get("era"), 4.30),
    }


# ── Partidos ──────────────────────────────────────────────────────────────────
def partidos_de_hoy(fecha: str | None = None) -> list[dict]:
    """Partidos MLB de una fecha (YYYY-MM-DD) con el abridor probable de cada lado."""
    fecha = fecha or date.today().isoformat()
    d = _get(f"{BASE}/schedule?sportId=1&date={fecha}"
             f"&hydrate=probablePitcher(note),team")
    juegos = []
    for dia in d.get("dates", []):
        for g in dia.get("games", []):
            local, visita = g["teams"]["home"], g["teams"]["away"]
            juegos.append({
                "game_id":  g.get("gamePk"),
                "estado":   g.get("status", {}).get("detailedState", ""),
                "hora_utc": g.get("gameDate", ""),
                "local":    {"id": local["team"]["id"], "nombre": local["team"]["name"],
                             "lanzador_id": (local.get("probablePitcher") or {}).get("id"),
                             "lanzador":    (local.get("probablePitcher") or {}).get("fullName", "—")},
                "visita":   {"id": visita["team"]["id"], "nombre": visita["team"]["name"],
                             "lanzador_id": (visita.get("probablePitcher") or {}).get("id"),
                             "lanzador":    (visita.get("probablePitcher") or {}).get("fullName", "—")},
            })
    return juegos


def datos_partido(juego: dict) -> dict:
    """Junta TODO lo que el modelo necesitará de un partido."""
    out = {"game_id": juego["game_id"], "estado": juego["estado"],
           "partido": f'{juego["visita"]["nombre"]} @ {juego["local"]["nombre"]}'}
    for lado in ("local", "visita"):
        eq = juego[lado]
        out[lado] = {
            "nombre":   eq["nombre"],
            "lanzador": eq["lanzador"],
            "pitcher":  stats_lanzador(eq["lanzador_id"]),
            "equipo":   stats_equipo(eq["id"]),
        }
    return out


if __name__ == "__main__":
    fecha = sys.argv[1] if len(sys.argv) > 1 else None
    juegos = partidos_de_hoy(fecha)
    print(f"MLB — {len(juegos)} partido(s) para {fecha or date.today().isoformat()}\n")
    for j in juegos[:5]:                       # muestra los primeros 5
        d = datos_partido(j)
        print(f"  {d['partido']}   [{d['estado']}]")
        for lado, etiqueta in (("visita", "VIS"), ("local", "LOC")):
            x, p, e = d[lado], d[lado]["pitcher"], d[lado]["equipo"]
            print(f"    {etiqueta} {x['nombre']:24s} | abridor: {x['lanzador']:20s} "
                  f"ERA {p.get('era','—'):<5} WHIP {p.get('whip','—'):<5}")
            print(f"        anota {e['ca_por_juego']:.2f} c/juego · permite "
                  f"{e['cp_por_juego']:.2f} c/juego · ERA equipo {e['era_equipo']}")
        print()
    print("Fase 1 OK: datos crudos listos para el modelo de carreras (Fase 2).")
