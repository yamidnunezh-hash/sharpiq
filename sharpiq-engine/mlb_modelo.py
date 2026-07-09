"""
SharpIQ — Modelo de carreras MLB
═══════════════════════════════════════════════════════════════════════════════
FASE 2 del proyecto "MLB pulido". Convierte los datos crudos de mlb_datos.py en
PROBABILIDADES para los 3 mercados que ofrece el mercado:

    • Ganador (moneyline)
    • Run line (-1.5 / +1.5)
    • Over / Under de carreras totales

Cómo se estiman las carreras esperadas de un equipo:

    λ = media_liga × ataque_propio × defensa_rival × parque × localía

  ataque_propio  = carreras anotadas por juego / media de la liga
  defensa_rival  = ERA combinado del rival, ponderado 60% ABRIDOR + 40% equipo
                   (un abridor promedio hace ~5.3 de las 9 entradas; el resto
                   lo tira el bullpen, que se refleja en el ERA del equipo)
  parque         = factor de carreras del estadio local (Coors infla, T-Mobile hunde)
  localía        = +2% para el local

Distribución: BINOMIAL NEGATIVA, no Poisson pura. Las carreras en béisbol son
"sobredispersas" (grandes innings de 5-6 carreras) — la varianza real supera a
la media. Poisson subestima los partidos de mucha o poca carrera y por tanto
mete mal precio en los Over/Under. Con VAR_RATIO=1.25 la cola queda realista.

Este módulo es INDEPENDIENTE: no importa ni modifica motor.py.

    python mlb_modelo.py            # probabilidades de los partidos de hoy
    python mlb_modelo.py 2026-07-10

NO se publica NADA hasta que el backtest (Fase 4) demuestre que le gana al mercado.
"""
from __future__ import annotations

import sys
from datetime import date

from mlb_datos import BASE, _get, _stat, _f, partidos_de_hoy, datos_partido

MAX_CARRERAS = 25      # cola suficiente: P(>25 carreras) es despreciable
VAR_RATIO    = 1.25    # varianza / media (sobredispersión del béisbol)
PESO_ABRIDOR = 0.60    # el abridor cubre ~5.3 de 9 entradas
VENTAJA_LOCAL = 1.02

# Regresión a la media. El ratio crudo (ataque_equipo / media_liga) exagera:
# media temporada != habilidad real, y el ERA de un abridor es RUIDOSÍSIMO en
# 100 entradas. Sin esto el modelo escupe totales de 6.2 y 12.0 que el mercado
# nunca pone. Encogemos cada factor hacia 1.0:  f' = 1 + k(f - 1)
REG_ATAQUE  = 0.75     # la ofensiva de equipo se estabiliza rápido
REG_DEFENSA = 0.55     # ERA = mucho ruido, poca señal -> encoger más fuerte

# Factor de carreras del estadio (>1 infla, <1 hunde). Clave: equipo LOCAL.
PARQUES = {
    "Colorado Rockies": 1.33,   "Boston Red Sox": 1.09,   "Cincinnati Reds": 1.07,
    "Philadelphia Phillies": 1.04, "Texas Rangers": 1.04,  "Arizona Diamondbacks": 1.03,
    "New York Yankees": 1.02,   "Chicago Cubs": 1.02,     "Atlanta Braves": 1.01,
    "Washington Nationals": 1.01, "Toronto Blue Jays": 1.01,
    "Baltimore Orioles": 1.00,  "Chicago White Sox": 1.00, "Kansas City Royals": 1.00,
    "Pittsburgh Pirates": 0.99, "Milwaukee Brewers": 0.99, "Minnesota Twins": 0.99,
    "Cleveland Guardians": 0.98, "Detroit Tigers": 0.98,  "Los Angeles Angels": 0.98,
    "Houston Astros": 0.97,     "Athletics": 0.97,        "Los Angeles Dodgers": 0.97,
    "St. Louis Cardinals": 0.97, "New York Mets": 0.96,
    "San Diego Padres": 0.95,   "Miami Marlins": 0.95,    "Tampa Bay Rays": 0.95,
    "San Francisco Giants": 0.94, "Seattle Mariners": 0.93,
}

_liga: dict | None = None


# ── Medias de la liga (denominador de todos los ratios) ───────────────────────
def medias_liga() -> dict:
    """Carreras por juego y ERA promedio de las 30 franquicias (una sola vez)."""
    global _liga
    if _liga:
        return _liga

    equipos = _get(f"{BASE}/teams?sportId=1&activeStatus=Y")["teams"]
    carreras, juegos, eras = 0, 0, []
    for eq in equipos:
        hit = _stat(_get(f"{BASE}/teams/{eq['id']}/stats"
                         f"?stats=season&group=hitting&season={date.today().year}"))
        pit = _stat(_get(f"{BASE}/teams/{eq['id']}/stats"
                         f"?stats=season&group=pitching&season={date.today().year}"))
        g = int(hit.get("gamesPlayed") or 0)
        if not g:
            continue
        carreras += int(hit.get("runs") or 0)
        juegos   += g
        eras.append(_f(pit.get("era"), 4.30))

    _liga = {
        "carreras_por_juego": round(carreras / max(juegos, 1), 3),
        "era": round(sum(eras) / max(len(eras), 1), 3),
        "equipos": len(eras),
    }
    return _liga


# ── Carreras esperadas ────────────────────────────────────────────────────────
def _era_defensiva(pitcher: dict, equipo: dict, era_liga: float) -> float:
    """ERA combinado del rival: 60% abridor + 40% equipo (bullpen incluido).

    Un abridor sin entradas suficientes (novato, regreso de lesión) no es fiable:
    en ese caso se cae al ERA del equipo en vez de inventar un número.
    """
    era_eq = equipo.get("era_equipo") or era_liga
    entradas = pitcher.get("entradas", 0)
    era_ab   = pitcher.get("era")
    if not era_ab or entradas < 20:        # muestra insuficiente -> no confiar
        return era_eq
    return PESO_ABRIDOR * era_ab + (1 - PESO_ABRIDOR) * era_eq


def _regresar(factor: float, k: float) -> float:
    """Encoge un factor hacia 1.0. k=1 lo deja crudo, k=0 lo anula."""
    return 1.0 + k * (factor - 1.0)


def carreras_esperadas(datos: dict) -> tuple[float, float]:
    """(λ_visita, λ_local) — carreras esperadas de cada lado."""
    liga = medias_liga()
    cpj_liga, era_liga = liga["carreras_por_juego"], liga["era"]
    parque = PARQUES.get(datos["local"]["nombre"], 1.00)

    lams = {}
    for lado, rival in (("visita", "local"), ("local", "visita")):
        ataque = _regresar(
            (datos[lado]["equipo"]["ca_por_juego"] or cpj_liga) / cpj_liga,
            REG_ATAQUE)
        defensa = _regresar(
            _era_defensiva(datos[rival]["pitcher"],
                           datos[rival]["equipo"], era_liga) / era_liga,
            REG_DEFENSA)
        lam = cpj_liga * ataque * defensa * parque
        if lado == "local":
            lam *= VENTAJA_LOCAL
        lams[lado] = round(max(lam, 0.5), 3)     # piso: nadie espera <0.5 carreras

    return lams["visita"], lams["local"]


# ── Distribución de carreras (binomial negativa) ──────────────────────────────
def distribucion(lam: float) -> list[float]:
    """P(equipo anote exactamente k carreras), k = 0..MAX_CARRERAS.

    Binomial negativa parametrizada por media y varianza = media × VAR_RATIO.
    r = lam/(VAR_RATIO-1), p = 1/VAR_RATIO. Recurrencia:
        P(0)   = p^r
        P(k)   = P(k-1) × (r+k-1)/k × (1-p)
    """
    r = lam / (VAR_RATIO - 1)
    p = 1.0 / VAR_RATIO
    probs = [p ** r]
    for k in range(1, MAX_CARRERAS + 1):
        probs.append(probs[-1] * (r + k - 1) / k * (1 - p))
    total = sum(probs)
    return [x / total for x in probs]           # normaliza la cola truncada


# ── Mercados ──────────────────────────────────────────────────────────────────
def mercados(lam_v: float, lam_l: float, linea_total: float = 8.5) -> dict:
    """Probabilidades de ganador, run line y over/under."""
    pv, pl = distribucion(lam_v), distribucion(lam_l)

    gana_v = gana_l = empate = 0.0
    rl_v15 = rl_l15 = 0.0        # cubre el -1.5 (gana por 2+)
    over = under = push = 0.0

    for v, prob_v in enumerate(pv):
        for l, prob_l in enumerate(pl):
            j = prob_v * prob_l
            if   v > l: gana_v += j
            elif l > v: gana_l += j
            else:       empate += j

            if v - l >= 2: rl_v15 += j
            if l - v >= 2: rl_l15 += j

            t = v + l
            if   t > linea_total: over  += j
            elif t < linea_total: under += j
            else:                 push  += j

    # En MLB no hay empates: el 9-9 se decide en entradas extra. Repartimos ese
    # bloque proporcional a la fuerza de cada equipo (aprox. razonable).
    if empate > 0:
        peso_v = lam_v / (lam_v + lam_l)
        gana_v += empate * peso_v
        gana_l += empate * (1 - peso_v)

    # Un empate al final del 9º se rompe en extras: en la práctica el ganador
    # casi nunca saca 2+ carreras, así que el empate NO alimenta la run line.
    return {
        "lam_visita": lam_v, "lam_local": lam_l,
        "total_esperado": round(lam_v + lam_l, 2),
        "gana_visita": round(gana_v, 4),
        "gana_local":  round(gana_l, 4),
        "run_line_visita_-1.5": round(rl_v15, 4),
        "run_line_local_-1.5":  round(rl_l15, 4),
        "linea": linea_total,
        "over":  round(over, 4),
        "under": round(under, 4),
        "push":  round(push, 4),
    }


def cuota_justa(prob: float) -> float:
    """Cuota decimal sin margen de casa. Es el precio que 'deberia' tener."""
    return round(1 / prob, 2) if prob > 0 else 0.0


def analizar(juego: dict, linea_total: float = 8.5) -> dict:
    d = datos_partido(juego)
    lam_v, lam_l = carreras_esperadas(d)
    m = mercados(lam_v, lam_l, linea_total)
    m["partido"] = d["partido"]
    m["game_id"] = d["game_id"]
    m["visita"]  = d["visita"]["nombre"]
    m["local"]   = d["local"]["nombre"]
    m["abridor_visita"] = d["visita"]["lanzador"]
    m["abridor_local"]  = d["local"]["lanzador"]
    m["parque"] = PARQUES.get(d["local"]["nombre"], 1.00)
    return m


if __name__ == "__main__":
    fecha  = sys.argv[1] if len(sys.argv) > 1 else None
    liga   = medias_liga()
    juegos = partidos_de_hoy(fecha)

    print(f"\nMLB — modelo de carreras · {fecha or date.today().isoformat()}")
    print(f"Media liga: {liga['carreras_por_juego']} carreras/juego · "
          f"ERA {liga['era']} · {liga['equipos']} equipos\n")

    for j in juegos:
        m = analizar(j)
        print(f"  {m['partido']}   (parque ×{m['parque']})")
        print(f"    Abridores: {m['abridor_visita']} vs {m['abridor_local']}")
        print(f"    Carreras esperadas: {m['visita']} {m['lam_visita']} — "
              f"{m['lam_local']} {m['local']}   (total {m['total_esperado']})")
        print(f"    Ganador : {m['visita']} {m['gana_visita']:.1%} "
              f"(cuota justa {cuota_justa(m['gana_visita'])})  |  "
              f"{m['local']} {m['gana_local']:.1%} "
              f"(cuota justa {cuota_justa(m['gana_local'])})")
        print(f"    Run line: {m['visita']} -1.5 {m['run_line_visita_-1.5']:.1%}  |  "
              f"{m['local']} -1.5 {m['run_line_local_-1.5']:.1%}")
        print(f"    Total {m['linea']}: Más de {m['over']:.1%} "
              f"(cuota justa {cuota_justa(m['over'])})  |  "
              f"Menos de {m['under']:.1%} "
              f"(cuota justa {cuota_justa(m['under'])})  |  empate línea {m['push']:.1%}")
        print()

    print("Fase 2 OK: el modelo ya da probabilidades. Falta compararlas contra")
    print("las cuotas reales (Fase 3) y BACKTESTEAR antes de publicar (Fase 4).")
