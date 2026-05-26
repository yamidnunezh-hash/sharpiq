# -*- coding: utf-8 -*-
"""
SharpIQ — Monitor de Partidos en Vivo (one-shot)
Corre una vez, detecta momentos clave y calcula EV real antes de alertar.
Solo envía cuando hay valor matemático confirmado.
GitHub Actions lo ejecuta cada 5 minutos.
"""
import os, sys, math, sqlite3, json
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from config import APIFOOTBALL_KEY, TELEGRAM_CHAT_ID
from motor import _apifb, LIGAS_APIFB

DB_PATH         = os.path.join(BASE_DIR, "sharpiq.db")
DATOS_PATH      = os.path.join(BASE_DIR, "..", "datos.js")
PREDICCIONES_PATH = os.path.join(BASE_DIR, "..", "predicciones.json")

# ── UMBRAL MÍNIMO DE PROBABILIDAD POR TRIGGER ────────────────────────
# Si el modelo no llega a este % de probabilidad, no hay valor — no se envía
PROB_MIN = {
    "inicio":        0,    # Siempre notificar inicio
    "ht_cero":      55,    # P(gol 2ª mitad) > 55%
    "ht_update":    70,    # P(mantener resultado) > 70%
    "min60_cero":   63,    # P(al menos 1 gol) > 63%
    "min60_update": 74,    # P(mantener) > 74%
    "min75_cero":   70,    # P(gol) > 70% — más exigente por tiempo
    "min75_update": 82,    # P(mantener) > 82%
    "dominancia":   62,    # P(equipo dominante marca) > 62%
}

# ── TRIGGERS ─────────────────────────────────────────────────────────
TRIGGERS = [
    (0,   3,  "any",        "inicio"),
    (44,  46, "0-0",        "ht_cero"),
    (44,  46, "any",        "ht_update"),
    (58,  62, "0-0",        "min60_cero"),
    (58,  62, "any",        "min60_update"),
    (73,  77, "0-0",        "min75_cero"),
    (73,  77, "any",        "min75_update"),
    (20,  45, "dominancia", "dominancia"),
]


# ── ANTI-SPAM EN BASE DE DATOS ───────────────────────────────────────

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


# ── CUOTAS PRE-PARTIDO DESDE predicciones.json ──────────────────────

def cuotas_prepartido(local, visita):
    """Busca las cuotas pre-partido del motor para el partido."""
    try:
        with open(PREDICCIONES_PATH, encoding='utf-8') as f:
            data = json.load(f)
        for p in data.get("predicciones", []):
            loc = p.get("local", "").lower()
            vis = p.get("visitante", "").lower()
            if (local.lower()[:8] in loc or loc[:8] in local.lower()) and \
               (visita.lower()[:8] in vis or vis[:8] in visita.lower()):
                return p.get("value_bets", {}), p
    except Exception:
        pass
    return {}, {}


# ── CALCULAR EV LIVE ─────────────────────────────────────────────────

def calcular_ev_live(prob_modelo, cuota_mercado):
    """EV = (prob × cuota) - 1. Retorna como porcentaje."""
    return round((prob_modelo / 100) * cuota_mercado - 1, 3) * 100

def cuota_justa(prob):
    """Convierte probabilidad % a cuota justa (sin margen)."""
    if prob <= 0:
        return 99.0
    return round(100 / prob, 2)

def hay_valor(prob, trigger, cuota_ref=None):
    """
    Retorna (tiene_valor, prob_relevante, cuota_justa, ev_estimado).
    Si cuota_ref viene de predicciones.json, calcula EV real.
    Si no, solo verifica que prob >= umbral.
    """
    umbral = PROB_MIN.get(trigger, 60)
    cj     = cuota_justa(prob)

    if prob < umbral:
        return False, prob, cj, 0

    if cuota_ref and cuota_ref > 1.01:
        ev = calcular_ev_live(prob, cuota_ref)
        # Valor solo si EV > 8%
        return ev >= 8, prob, cj, ev

    # Sin cuota de referencia: valor si prob >= umbral
    ev_est = round((prob / 100) * (cj * 1.05) - 1, 3) * 100  # estimado con 5% margen
    return True, prob, cj, ev_est


# ── ESTADÍSTICAS EN VIVO (remates a puerta) ──────────────────────────

def obtener_stats_live(fixture_id):
    data = _apifb("fixtures/statistics", {"fixture": fixture_id})
    if not data:
        return 0, 0
    shots_h = shots_a = 0
    teams = data.get("response", [])
    for i, team_stats in enumerate(teams):
        for stat in team_stats.get("statistics", []):
            if stat.get("type") == "Shots on Goal":
                val = int(stat.get("value") or 0)
                if i == 0:
                    shots_h = val
                else:
                    shots_a = val
    return shots_h, shots_a


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

    p_mas_gol = (1 - math.exp(-(lambda_l + lambda_v))) * 100

    if gl_actual > gv_actual:
        p_local  = min(95, 55 + (minuto / 90) * 30)
        p_visita = max(5,  25 - (minuto / 90) * 20)
    elif gv_actual > gl_actual:
        p_visita = min(95, 55 + (minuto / 90) * 30)
        p_local  = max(5,  25 - (minuto / 90) * 20)
    else:
        p_local = p_visita = 35.0

    return {
        "p_mas_gol": round(p_mas_gol, 1),
        "p_local":   round(p_local, 1),
        "p_empate":  round(max(1, 100 - p_local - p_visita), 1),
        "p_visita":  round(p_visita, 1),
        "mins_rest": minutos_rest,
    }


# ── CONSTRUIR MENSAJE CON EV REAL ────────────────────────────────────

def _ev_tag(ev):
    if ev >= 15:
        return f"🔥 EV +{ev:.1f}% — VALOR ALTO"
    if ev >= 8:
        return f"✅ EV +{ev:.1f}% — Valor confirmado"
    return f"⚠️ EV {ev:.1f}%"

def construir_alerta(fixture, trigger, probs, shots_h=0, shots_a=0, ev=0, cj=0, prob=0):
    local  = fixture["teams"]["home"]["name"]
    visita = fixture["teams"]["away"]["name"]
    gl     = fixture["goals"]["home"] or 0
    gv     = fixture["goals"]["away"] or 0
    minuto = fixture["fixture"]["status"]["elapsed"] or 0
    liga   = fixture["league"]["name"]
    marc   = f"{gl}-{gv}"
    mins   = probs["mins_rest"]

    ev_linea  = _ev_tag(ev)
    cj_linea  = f"💰 Cuota justa SharpIQ: <b>{cj}</b> — apuesta solo si encuentras cuota MAYOR"
    stake     = "📌 <i>Stake máximo en vivo: 2% del bankroll</i>"
    shots_txt = f"🎯 Remates a puerta: {local} {shots_h} — {visita} {shots_a}\n" if (shots_h or shots_a) else ""

    if trigger == "inicio":
        return (
            f"🟢 <b>EN CURSO | Min {minuto}'</b>\n\n"
            f"⚽ <b>{local} vs {visita}</b>\n"
            f"🏆 {liga} | {marc}\n\n"
            f"<i>SharpIQ monitoreando — alertas solo cuando haya valor real</i>"
        )

    if trigger == "dominancia":
        dom, dom_s = (local, shots_h) if shots_h >= 4 else (visita, shots_a)
        return (
            f"🎯 <b>DOMINANCIA SIN GOL | Min {minuto}'</b>\n\n"
            f"⚽ <b>{local} vs {visita}</b>\n"
            f"🏆 {liga} | {marc}\n\n"
            f"📊 <b>{dom}</b>: {dom_s} remates a puerta sin convertir\n"
            f"🔮 Prob. de anotar: <b>{prob}%</b>\n"
            f"{ev_linea}\n"
            f"{cj_linea}\n\n"
            f"{stake}\n"
            f"<i>SharpIQ Live — La ventaja inteligente</i>"
        )

    if trigger in ("ht_cero", "min60_cero", "min75_cero"):
        urgencia = "🚨 URGENTE" if trigger == "min75_cero" else "⚡ ALERTA LIVE"
        return (
            f"{urgencia} — <b>Sin goles | Min {minuto}'</b>\n\n"
            f"⚽ <b>{local} vs {visita}</b>\n"
            f"🏆 {liga} | {marc}\n\n"
            f"{shots_txt}"
            f"🔮 Prob. al menos 1 gol: <b>{prob}%</b>\n"
            f"{ev_linea}\n"
            f"{cj_linea}\n\n"
            f"💡 Mercado: <b>Over 0.5 goles restantes</b>\n"
            f"⏱ {mins} minutos restantes\n\n"
            f"{stake}\n"
            f"<i>SharpIQ Live — La ventaja inteligente</i>"
        )

    if trigger in ("ht_update", "min60_update", "min75_update"):
        if gl > gv:
            lider = local;  p_m = probs["p_local"];  sug = f"Victoria {local}"
        elif gv > gl:
            lider = visita; p_m = probs["p_visita"]; sug = f"Victoria {visita}"
        else:
            lider = None;   p_m = probs["p_empate"]; sug = "Empate"

        return (
            f"📡 <b>LIVE | Min {minuto}'</b>\n\n"
            f"⚽ <b>{local} vs {visita}</b>\n"
            f"🏆 {liga} | {marc}\n\n"
            f"{shots_txt}"
            f"🔮 {('Prob. mantener ' + lider + ': ') if lider else 'Prob. empate final: '}"
            f"<b>{p_m}%</b>\n"
            f"{ev_linea}\n"
            f"{cj_linea}\n\n"
            f"💡 Mercado: <b>{sug}</b>\n"
            f"⏱ {mins} min restantes\n\n"
            f"{stake}\n"
            f"<i>SharpIQ Live — La ventaja inteligente</i>"
        )

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
    print(f"\n SharpIQ Live Monitor — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    partidos_hoy = partidos_publicados_hoy()
    if not partidos_hoy:
        print("  Sin partidos publicados — skip")
        return

    liga_ids = ",".join(str(k) for k in LIGAS_APIFB.keys())
    data     = _apifb("fixtures", {"live": liga_ids})
    fixtures = data.get("response", []) if data else []

    if not fixtures:
        print("  Sin partidos en vivo")
        return

    alertas = 0
    for fixture in fixtures:
        local   = fixture["teams"]["home"]["name"]
        visita  = fixture["teams"]["away"]["name"]
        fid     = fixture["fixture"]["id"]
        minuto  = fixture["fixture"]["status"]["elapsed"] or 0
        gl      = fixture["goals"]["home"] or 0
        gv      = fixture["goals"]["away"] or 0
        marc_c  = "0-0" if gl == 0 and gv == 0 else "any"

        # Solo partidos publicados por SharpIQ
        partido_str = f"{local} vs {visita}"
        if not any(p.lower()[:15] in partido_str.lower() or
                   partido_str.lower()[:15] in p.lower()
                   for p in partidos_hoy):
            continue

        print(f"  {partido_str} | {gl}-{gv} | Min {minuto}'")

        # Remates en vivo
        shots_h = shots_a = 0
        if minuto >= 15:
            shots_h, shots_a = obtener_stats_live(fid)

        # Cuotas pre-partido del motor
        vbets, pred_data = cuotas_prepartido(local, visita)

        # Condición dominancia
        dom = marc_c == "0-0" and minuto >= 20 and (shots_h >= 4 or shots_a >= 4)

        from motor import calcular_goles_esperados
        gl_esp, gv_esp = calcular_goles_esperados(local, visita)
        probs = probabilidades_live(gl_esp, gv_esp, minuto, gl, gv)

        for (min_min, min_max, cond, trigger) in TRIGGERS:
            if not (min_min <= minuto <= min_max):
                continue
            if cond == "dominancia" and not dom:
                continue
            if cond not in ("any", "dominancia") and cond != marc_c:
                continue
            if ya_enviado(fid, trigger):
                continue

            # ── Seleccionar probabilidad relevante para el trigger ──
            if trigger in ("ht_update", "min60_update", "min75_update"):
                if gl > gv:
                    prob_rel = probs["p_local"]
                    cuota_ref = float(vbets.get("victoria_local", {}).get("cuota", 0) or 0)
                elif gv > gl:
                    prob_rel = probs["p_visita"]
                    cuota_ref = float(vbets.get("victoria_visita", {}).get("cuota", 0) or 0)
                else:
                    prob_rel = probs["p_empate"]
                    cuota_ref = float(vbets.get("empate", {}).get("cuota", 0) or 0)
            elif trigger == "dominancia":
                prob_rel  = probs["p_mas_gol"]
                cuota_ref = float(vbets.get("over15", {}).get("cuota", 0) or 0)
            else:
                prob_rel  = probs["p_mas_gol"]
                cuota_ref = float(vbets.get("over15", {}).get("cuota", 0) or 0)

            # ── Verificar valor real ──────────────────────────────
            tiene_valor, prob, cj, ev = hay_valor(prob_rel, trigger, cuota_ref)

            if not tiene_valor:
                print(f"  ⛔ Sin valor: {trigger} | prob={prob}% umbral={PROB_MIN.get(trigger,60)}% ev={ev:.1f}%")
                continue

            texto = construir_alerta(fixture, trigger, probs, shots_h, shots_a, ev, cj, prob)
            if texto:
                enviar_alerta_live(texto)
                marcar_enviado(fid, trigger)
                print(f"  ✅ Alerta enviada: {trigger} | {partido_str} | prob={prob}% ev={ev:.1f}%")
                alertas += 1

    print(f"  Total alertas enviadas: {alertas}")


if __name__ == "__main__":
    correr()
