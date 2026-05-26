# -*- coding: utf-8 -*-
"""
SharpIQ — Monitor de Partidos en Vivo (one-shot)
Corre una vez, detecta momentos clave en partidos publicados y envía
alertas al canal VIP. GitHub Actions lo ejecuta cada 5 minutos.
"""
import os, sys, math, sqlite3
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from config import APIFOOTBALL_KEY, TELEGRAM_CHAT_ID
from motor import _apifb, LIGAS_APIFB

DB_PATH    = os.path.join(BASE_DIR, "sharpiq.db")
DATOS_PATH = os.path.join(BASE_DIR, "..", "datos.js")

# ── TRIGGERS ─────────────────────────────────────────────────────────
# (min_min, min_max, condicion, trigger_id)
TRIGGERS = [
    (0,   3,  "any",        "inicio"),        # Partido inicia
    (44,  46, "0-0",        "ht_cero"),       # HT sin goles
    (44,  46, "any",        "ht_update"),     # HT actualización
    (58,  62, "0-0",        "min60_cero"),    # Min 60 sin goles
    (58,  62, "any",        "min60_update"),  # Min 60 actualización
    (73,  77, "0-0",        "min75_cero"),    # Min 75 sin goles — over urgente
    (73,  77, "any",        "min75_update"),  # Min 75 actualización
    (20,  45, "dominancia", "dominancia"),    # Equipo domina pero no marca
]


# ── BASE DE DATOS ANTI-SPAM ──────────────────────────────────────────

def _db():
    return sqlite3.connect(DB_PATH)

def inicializar_live_db():
    with _db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS live_alertas (
            fixture_id  INTEGER,
            trigger     TEXT,
            enviado     TEXT,
            PRIMARY KEY (fixture_id, trigger)
        )""")

def ya_enviado(fixture_id, trigger):
    with _db() as c:
        r = c.execute("SELECT 1 FROM live_alertas WHERE fixture_id=? AND trigger=?",
                      (fixture_id, trigger)).fetchone()
    return bool(r)

def marcar_enviado(fixture_id, trigger):
    with _db() as c:
        c.execute("INSERT OR IGNORE INTO live_alertas (fixture_id, trigger, enviado) VALUES (?,?,?)",
                  (fixture_id, trigger, datetime.now().isoformat()))


# ── LEER PARTIDOS PUBLICADOS ─────────────────────────────────────────

def partidos_publicados_hoy():
    try:
        import re
        with open(DATOS_PATH, encoding='utf-8') as f:
            texto = f.read()
        return re.findall(r'partido\s*:\s*"([^"]+)"', texto)
    except Exception:
        return []


# ── ESTADÍSTICAS EN VIVO (remates a puerta) ──────────────────────────

def obtener_stats_live(fixture_id):
    """Fetches live shots on target for both teams."""
    data = _apifb("fixtures/statistics", {"fixture": fixture_id})
    if not data:
        return None, None
    shots_home = shots_away = 0
    teams = data.get("response", [])
    for team_stats in teams:
        is_home = team_stats.get("team", {}).get("id") == teams[0].get("team", {}).get("id") if teams else False
        for stat in team_stats.get("statistics", []):
            if stat.get("type") == "Shots on Goal":
                val = stat.get("value") or 0
                if not shots_home:
                    shots_home = int(val)
                else:
                    shots_away = int(val)
    return shots_home, shots_away


# ── MODELO PROBABILIDADES LIVE ───────────────────────────────────────

def probabilidades_live(gl_esp, gv_esp, minuto, gl_actual, gv_actual):
    minutos_rest = max(90 - minuto, 5)
    factor       = minutos_rest / 90.0
    lambda_l     = gl_esp * factor
    lambda_v     = gv_esp * factor

    goles_tot = gl_actual + gv_actual
    if goles_tot >= 2:
        lambda_l *= 0.85; lambda_v *= 0.85
    elif goles_tot == 0 and minuto >= 60:
        lambda_l *= 1.10; lambda_v *= 1.10

    p_mas_gol = 1 - math.exp(-(lambda_l + lambda_v))

    if gl_actual > gv_actual:
        p_local = 0.55 + (minuto / 90) * 0.30
        p_visita = max(0.05, 0.25 - (minuto / 90) * 0.20)
    elif gv_actual > gl_actual:
        p_visita = 0.55 + (minuto / 90) * 0.30
        p_local  = max(0.05, 0.25 - (minuto / 90) * 0.20)
    else:
        p_local = p_visita = 0.35

    return {
        "p_mas_gol": round(p_mas_gol * 100, 1),
        "p_local":   round(p_local * 100, 1),
        "p_empate":  round(max(0.01, 1 - p_local - p_visita) * 100, 1),
        "p_visita":  round(p_visita * 100, 1),
        "mins_rest": minutos_rest,
    }


# ── CONSTRUIR MENSAJES ───────────────────────────────────────────────

def construir_alerta(fixture, trigger, probs, shots_home=0, shots_away=0):
    local  = fixture["teams"]["home"]["name"]
    visita = fixture["teams"]["away"]["name"]
    gl     = fixture["goals"]["home"] or 0
    gv     = fixture["goals"]["away"] or 0
    minuto = fixture["fixture"]["status"]["elapsed"] or 0
    liga   = fixture["league"]["name"]
    marc   = f"{gl}-{gv}"
    mins   = probs["mins_rest"]
    p_gol  = probs["p_mas_gol"]

    stake = "💰 <i>Si apuestas: máx 2% del bankroll en vivo</i>"

    if trigger == "inicio":
        return (
            f"🟢 <b>EN CURSO</b> | Min {minuto}'\n\n"
            f"⚽ <b>{local} vs {visita}</b>\n"
            f"🏆 {liga} | {marc}\n\n"
            f"<i>SharpIQ monitoreando — recibirás alertas en momentos clave</i>"
        )

    if trigger == "dominancia":
        if shots_home >= 4 and gl == 0:
            dom_equipo, dom_remates = local, shots_home
        elif shots_away >= 4 and gv == 0:
            dom_equipo, dom_remates = visita, shots_away
        else:
            return None
        return (
            f"🎯 <b>DOMINANCIA SIN GOL | Min {minuto}'</b>\n\n"
            f"⚽ <b>{local} vs {visita}</b>\n"
            f"🏆 {liga} | {marc}\n\n"
            f"📊 <b>{dom_equipo}: {dom_remates} remates a puerta</b> — sin convertir\n"
            f"🔮 Prob. de anotar: <b>{p_gol}%</b>\n\n"
            f"💡 <b>Oportunidad:</b> {dom_equipo} siguiente gol / Over 0.5\n"
            f"🔍 Busca la cuota — el valor suele estar alto aquí\n\n"
            f"{stake}\n"
            f"<i>SharpIQ Live — La ventaja inteligente</i>"
        )

    if trigger in ("ht_cero", "min60_cero", "min75_cero"):
        urgencia = "🚨 URGENTE" if trigger == "min75_cero" else "⚡ ALERTA LIVE"
        shots_txt = ""
        if shots_home or shots_away:
            shots_txt = f"🎯 Remates a puerta: {local} {shots_home} — {visita} {shots_away}\n"
        return (
            f"{urgencia} — <b>Sin goles | Min {minuto}'</b>\n\n"
            f"⚽ <b>{local} vs {visita}</b>\n"
            f"🏆 {liga} | {marc}\n\n"
            f"{shots_txt}"
            f"📊 <b>Prob. al menos 1 gol más: {p_gol}%</b>\n"
            f"⏱ {mins} minutos restantes\n\n"
            f"💡 <b>Mercado:</b> Over 0.5 goles restantes\n"
            f"🔍 Busca la cuota en tu casa de apuestas\n\n"
            f"{stake}\n"
            f"<i>SharpIQ Live — La ventaja inteligente</i>"
        )

    if trigger in ("ht_update", "min60_update", "min75_update"):
        if gl > gv:
            lider = local; p_m = probs["p_local"]; sug = f"Victoria {local}"
        elif gv > gl:
            lider = visita; p_m = probs["p_visita"]; sug = f"Victoria {visita}"
        else:
            lider = None; p_m = probs["p_empate"]; sug = "Empate"

        shots_txt = ""
        if shots_home or shots_away:
            shots_txt = f"🎯 Remates: {local} {shots_home} — {visita} {shots_away}\n"

        header = f"📡 <b>LIVE | Min {minuto}'</b>\n\n"
        body   = (
            f"⚽ <b>{local} vs {visita}</b>\n"
            f"🏆 {liga} | {marc}\n\n"
            f"{shots_txt}"
            f"📊 {('Líder ' + lider + ' — prob. mantener: ') if lider else 'Prob. empate final: '}"
            f"<b>{p_m}%</b>\n"
            f"⏱ {mins} min restantes\n\n"
            f"💡 <b>Mercado:</b> {sug}\n\n"
            f"{stake}\n"
            f"<i>SharpIQ Live — La ventaja inteligente</i>"
        )
        return header + body

    return None


# ── ENVIAR AL CANAL VIP ──────────────────────────────────────────────

def enviar_alerta_live(texto):
    import requests
    from config import TELEGRAM_TOKEN
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "HTML"},
        timeout=10
    )


# ── ONE-SHOT PRINCIPAL ───────────────────────────────────────────────

def correr():
    inicializar_live_db()
    hora = datetime.now().strftime('%H:%M')
    print(f"\n SharpIQ Live Monitor — {date.today().isoformat()} {hora}")

    partidos_hoy = partidos_publicados_hoy()
    if not partidos_hoy:
        print("  Sin partidos publicados — skip")
        return

    liga_ids = ",".join(str(k) for k in LIGAS_APIFB.keys())
    data     = _apifb("fixtures", {"live": liga_ids})
    fixtures = data.get("response", []) if data else []

    if not fixtures:
        print("  Sin partidos en vivo ahora")
        return

    alertas = 0
    for fixture in fixtures:
        local   = fixture["teams"]["home"]["name"]
        visita  = fixture["teams"]["away"]["name"]
        fid     = fixture["fixture"]["id"]
        minuto  = fixture["fixture"]["status"]["elapsed"] or 0
        gl      = fixture["goals"]["home"] or 0
        gv      = fixture["goals"]["away"] or 0

        # Solo monitorear partidos publicados
        partido_str = f"{local} vs {visita}"
        if not any(p.lower()[:15] in partido_str.lower() or
                   partido_str.lower()[:15] in p.lower()
                   for p in partidos_hoy):
            continue

        print(f"  {partido_str} | {gl}-{gv} | Min {minuto}'")

        marc_cond = "0-0" if gl == 0 and gv == 0 else "any"

        # Remates en vivo (1 request por partido, solo si vale la pena)
        shots_h = shots_a = 0
        if minuto >= 15:
            shots_h, shots_a = obtener_stats_live(fid)
            if shots_h is None:
                shots_h = shots_a = 0

        # Condición dominancia
        dom_cond = "dominancia" if (
            marc_cond == "0-0" and minuto >= 20 and
            (shots_h >= 4 or shots_a >= 4)
        ) else None

        from motor import calcular_goles_esperados
        gl_esp, gv_esp = calcular_goles_esperados(local, visita)
        probs = probabilidades_live(gl_esp, gv_esp, minuto, gl, gv)

        for (min_min, min_max, cond, trigger) in TRIGGERS:
            if not (min_min <= minuto <= min_max):
                continue
            if cond == "dominancia" and dom_cond != "dominancia":
                continue
            if cond not in ("any", "dominancia") and cond != marc_cond:
                continue
            if ya_enviado(fid, trigger):
                continue

            texto = construir_alerta(fixture, trigger, probs, shots_h, shots_a)
            if texto:
                enviar_alerta_live(texto)
                marcar_enviado(fid, trigger)
                print(f"  ✅ Alerta: {trigger} | {partido_str}")
                alertas += 1

    print(f"  Total alertas enviadas: {alertas}")


if __name__ == "__main__":
    correr()
