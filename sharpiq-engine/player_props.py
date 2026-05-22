# -*- coding: utf-8 -*-
"""
SharpIQ — Player Props
Probabilidades de goleador anytime para los partidos del dia.
Datos: api-football /players/topscorers (cache 24h)
Mercado: P(jugador marca) = 1 - e^(-lambda_jugador)
"""
import os, sqlite3, math, json
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "sharpiq.db")


# ── CACHE SQLITE ────────────────────────────────────────────────────

def _db():
    return sqlite3.connect(DB_PATH)

def inicializar():
    with _db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS topscorers_cache (
            liga_id     INTEGER,
            season      INTEGER,
            data_json   TEXT,
            actualizado TEXT,
            PRIMARY KEY (liga_id, season)
        )""")

def _get_cache(liga_id, season):
    with _db() as c:
        row = c.execute(
            "SELECT data_json, actualizado FROM topscorers_cache WHERE liga_id=? AND season=?",
            (str(liga_id), season)
        ).fetchone()
    if not row:
        return None
    horas = (datetime.now() - datetime.fromisoformat(row[1])).total_seconds() / 3600
    if horas > 24:
        return None
    return json.loads(row[0])

def _guardar_cache(liga_id, season, data):
    with _db() as c:
        c.execute("""INSERT OR REPLACE INTO topscorers_cache
                     (liga_id, season, data_json, actualizado)
                     VALUES (?,?,?,?)""",
                  (int(liga_id), season, json.dumps(data), datetime.now().isoformat()))


# ── OBTENER TOP SCORERS ─────────────────────────────────────────────

def obtener_topscorers(liga_id):
    """
    Devuelve lista de top scorers con su equipo y goles por partido.
    Cache de 24 horas — solo 1 llamada por liga por dia.
    """
    inicializar()
    season = date.today().year if date.today().month >= 7 else date.today().year - 1

    cached = _get_cache(liga_id, season)
    if cached is not None:
        return cached

    try:
        from motor import _apifb
    except Exception:
        return []

    data = _apifb("players/topscorers", {"league": int(liga_id), "season": season})
    if not data or not data.get("response"):
        return []

    goleadores = []
    for entry in data["response"][:20]:
        p     = entry.get("player", {})
        stats = entry.get("statistics", [{}])[0]
        goals = stats.get("goals", {}).get("total") or 0
        pj    = stats.get("games", {}).get("appearences") or 1
        team  = stats.get("team", {}).get("name", "")
        goleadores.append({
            "nombre":            p.get("name", ""),
            "id":                p.get("id"),
            "equipo":            team,
            "goles":             int(goals),
            "partidos":          int(pj),
            "goles_por_partido": round(goals / pj, 3),
        })

    _guardar_cache(liga_id, season, goleadores)
    print(f"    Player props: {len(goleadores)} goleadores cargados (liga {liga_id})")
    return goleadores


# ── CALCULAR PROBABILIDADES DE GOLEADOR ────────────────────────────

def calcular_props_partido(local, visitante, liga_id, lambda_local, lambda_visita):
    """
    Devuelve lista de jugadores con P(anytime scorer) para este partido.
    Solo incluye jugadores de los dos equipos en juego.
    """
    topscorers = obtener_topscorers(liga_id)
    if not topscorers:
        return []

    try:
        from motor import _match_equipos
    except Exception:
        return []

    props = []
    for gol in topscorers:
        equipo    = gol["equipo"]
        es_local  = _match_equipos(equipo, local)
        es_visita = _match_equipos(equipo, visitante)
        if not es_local and not es_visita:
            continue

        team_lambda = lambda_local if es_local else lambda_visita

        # Fraccion del equipo que aporta este jugador (10% min, 70% max)
        fraccion  = min(max(gol["goles_por_partido"] / max(team_lambda, 0.5), 0.10), 0.70)
        lambda_p  = round(team_lambda * fraccion, 3)

        prob_scorer = round((1 - math.exp(-lambda_p)) * 100, 1)
        cuota_ref   = round(100 / prob_scorer * 0.92, 2) if prob_scorer > 0 else None

        props.append({
            "nombre":      gol["nombre"],
            "equipo":      equipo,
            "es_local":    es_local,
            "goles_pp":    gol["goles_por_partido"],
            "lambda":      lambda_p,
            "prob_scorer": prob_scorer,
            "cuota_ref":   cuota_ref,
        })

    props.sort(key=lambda x: x["prob_scorer"], reverse=True)
    return props[:6]


# ── ANALIZAR TODOS LOS PARTIDOS DEL DIA ────────────────────────────

def analizar_player_props(predicciones):
    """
    Punto de entrada desde guardar_predicciones().
    Devuelve dict {partido_str: [props]} para los partidos con datos.
    """
    resultados = {}
    for pred in predicciones:
        liga_id   = pred.get("liga_code", "")
        local     = pred.get("local", "")
        visitante = pred.get("visitante", "")
        if not liga_id or not local or not visitante:
            continue

        lam_l = pred.get("probabilidades", {}).get("goles_esperados_local",  1.3)
        lam_v = pred.get("probabilidades", {}).get("goles_esperados_visita", 1.1)

        props = calcular_props_partido(local, visitante, liga_id, lam_l, lam_v)
        if props:
            resultados[f"{local} vs {visitante}"] = props

    return resultados


# ── CONSTRUIR MENSAJE TELEGRAM ──────────────────────────────────────

def construir_mensaje_props(props_dia):
    """
    Construye mensaje Telegram con los mejores player props del dia.
    Solo muestra jugadores con P(scorer) >= 40%.
    """
    if not props_dia:
        return None

    lineas = ["🎯 <b>SharpIQ — Goleadores del Dia</b>\n"]
    encontrados = 0

    for partido, props in props_dia.items():
        candidatos = [p for p in props if p["prob_scorer"] >= 40]
        if not candidatos:
            continue
        lineas.append(f"\n⚽ <b>{partido}</b>")
        for p in candidatos[:3]:
            cuota_str = f" @ <b>{p['cuota_ref']}</b>" if p["cuota_ref"] else ""
            lineas.append(
                f"  👤 {p['nombre']} ({p['equipo']})\n"
                f"  📊 P(marca): <b>{p['prob_scorer']}%</b>{cuota_str}\n"
                f"  📈 Goles/partido: {p['goles_pp']}"
            )
            encontrados += 1

    if not encontrados:
        return None

    lineas.append("\n<i>SharpIQ — La ventaja inteligente</i>")
    return "\n".join(lineas)
