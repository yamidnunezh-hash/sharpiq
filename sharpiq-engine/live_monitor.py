# -*- coding: utf-8 -*-
"""
SharpIQ — Monitor de Partidos en Vivo
Detecta momentos clave durante los partidos publicados y envía
alertas al canal VIP con análisis actualizado del modelo.

Ejecutar: python live_monitor.py
Corre cada 5 minutos mientras haya partidos activos.
Usa ~30-40 requests/día de api-football (dentro del límite gratuito).
"""
import os, sys, time, json, sqlite3, math
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from config import APIFOOTBALL_KEY, TELEGRAM_CHAT_ID
from motor import _apifb, LIGAS_APIFB

DB_PATH = os.path.join(BASE_DIR, "sharpiq.db")
DATOS_PATH = os.path.join(BASE_DIR, "..", "datos.js")

# ── TRIGGERS — momentos que disparan una alerta ───────────────────
# (minuto_min, minuto_max, condicion, mensaje_tipo)
TRIGGERS = [
    (44, 46, "0-0",       "ht_cero"),       # Medio tiempo 0-0
    (58, 62, "0-0",       "min60_cero"),    # Min 60 sin goles
    (58, 62, "any",       "min60_update"),  # Min 60 actualización general
    (73, 77, "0-0",       "min75_cero"),    # Min 75 sin goles — over urgente
    (73, 77, "any",       "min75_update"),  # Min 75 cualquier marcador
    (0,   3, "any",       "inicio"),        # Partido iniciado
]


# ── BASE DE DATOS DE ALERTAS YA ENVIADAS ─────────────────────────

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


# ── LEER PARTIDOS PUBLICADOS HOY ─────────────────────────────────

def partidos_publicados_hoy():
    """Lee PROXIMOS_EVENTOS de datos.js y devuelve lista de partidos."""
    try:
        import re
        with open(DATOS_PATH, encoding='utf-8') as f:
            texto = f.read()
        patron = r'partido\s*:\s*"([^"]+)"'
        return re.findall(patron, texto)
    except Exception:
        return []


# ── MODELO LIVE — probabilidades con tiempo restante ─────────────

def probabilidades_live(goles_local_esp, goles_visita_esp, minuto, gl_actual, gv_actual):
    """
    Recalcula probabilidades con el estado actual del partido.
    Ajusta los goles esperados restantes según minuto y marcador.
    """
    minutos_restantes = max(90 - minuto, 5)
    factor_tiempo = minutos_restantes / 90.0

    # Goles esperados restantes (ajuste por tiempo)
    lambda_l = goles_local_esp * factor_tiempo
    lambda_v = goles_visita_esp * factor_tiempo

    # Si hay goles ya, el ritmo tiende a bajar (equipos más cerrados)
    goles_totales = gl_actual + gv_actual
    if goles_totales >= 2:
        lambda_l *= 0.85
        lambda_v *= 0.85
    elif goles_totales == 0 and minuto >= 60:
        # Sin goles a los 60' → ligero ajuste al alza (partido abierto)
        lambda_l *= 1.10
        lambda_v *= 1.10

    lambda_total = lambda_l + lambda_v

    # P(al menos 1 gol más)
    p_mas_gol = 1 - math.exp(-lambda_total)

    # P(victoria final) con estado actual
    # Simplificado: si va ganando, probabilidad de mantener resultado
    if gl_actual > gv_actual:
        p_local_gana = 0.55 + (minuto / 90) * 0.30
        p_visita_gana = max(0.05, 0.25 - (minuto / 90) * 0.20)
    elif gv_actual > gl_actual:
        p_visita_gana = 0.55 + (minuto / 90) * 0.30
        p_local_gana = max(0.05, 0.25 - (minuto / 90) * 0.20)
    else:  # empate
        p_local_gana = 0.35
        p_visita_gana = 0.35

    p_empate = max(0.01, 1 - p_local_gana - p_visita_gana)

    return {
        "lambda_restante": round(lambda_total, 2),
        "p_mas_gol": round(p_mas_gol * 100, 1),
        "p_local":   round(p_local_gana * 100, 1),
        "p_empate":  round(p_empate * 100, 1),
        "p_visita":  round(p_visita_gana * 100, 1),
        "minutos_restantes": minutos_restantes,
    }


# ── CONSTRUIR MENSAJE DE ALERTA ───────────────────────────────────

def construir_alerta(fixture, trigger, probs):
    local   = fixture["teams"]["home"]["name"]
    visita  = fixture["teams"]["away"]["name"]
    gl      = fixture["goals"]["home"] or 0
    gv      = fixture["goals"]["away"] or 0
    minuto  = fixture["fixture"]["status"]["elapsed"] or 0
    liga    = fixture["league"]["name"]

    marcador = f"{gl}-{gv}"
    p_gol    = probs["p_mas_gol"]
    mins     = probs["minutos_restantes"]

    if trigger == "inicio":
        return (
            f"🟢 <b>PARTIDO EN CURSO</b>\n\n"
            f"⚽ <b>{local} vs {visita}</b>\n"
            f"🏆 {liga} | Min {minuto}'\n"
            f"📊 Marcador: {marcador}\n\n"
            f"<i>Seguimiento activo — recibirás alertas en momentos clave</i>"
        )

    if trigger in ("ht_cero", "min60_cero", "min75_cero"):
        urgencia = "🚨 URGENTE" if trigger == "min75_cero" else "⚡ ALERTA LIVE"
        return (
            f"{urgencia} — <b>Sin goles | Min {minuto}'</b>\n\n"
            f"⚽ <b>{local} vs {visita}</b>\n"
            f"🏆 {liga} | {marcador}\n\n"
            f"📊 <b>Probabilidad de al menos 1 gol más: {p_gol}%</b>\n"
            f"⏱ {mins} minutos restantes\n\n"
            f"💡 <b>Mercado sugerido:</b> Over 0.5 goles restantes\n"
            f"🔍 Busca la cuota en tu casa de apuestas\n\n"
            f"<i>SharpIQ Live — La ventaja inteligente</i>"
        )

    if trigger in ("min60_update", "min75_update"):
        if gl > gv:
            lider, ventaja = local, f"{gl}-{gv}"
            p_mantiene = probs["p_local"]
            mercado_sug = f"Victoria {local}"
        elif gv > gl:
            lider, ventaja = visita, f"{gl}-{gv}"
            p_mantiene = probs["p_visita"]
            mercado_sug = f"Victoria {visita}"
        else:
            lider = None
            p_mantiene = probs["p_empate"]
            mercado_sug = "Empate"

        if lider:
            return (
                f"📡 <b>ACTUALIZACIÓN LIVE | Min {minuto}'</b>\n\n"
                f"⚽ <b>{local} vs {visita}</b>\n"
                f"🏆 {liga} | {marcador}\n\n"
                f"🏆 <b>{lider}</b> va ganando {ventaja}\n"
                f"📊 Probabilidad de mantener resultado: <b>{p_mantiene}%</b>\n"
                f"⏱ {mins} minutos restantes\n\n"
                f"💡 <b>Mercado sugerido:</b> {mercado_sug}\n"
                f"🔍 Busca la cuota en tu casa de apuestas\n\n"
                f"<i>SharpIQ Live — La ventaja inteligente</i>"
            )
        else:
            return (
                f"📡 <b>ACTUALIZACIÓN LIVE | Min {minuto}'</b>\n\n"
                f"⚽ <b>{local} vs {visita}</b>\n"
                f"🏆 {liga} | Empate {marcador}\n\n"
                f"📊 Prob. gol restante: <b>{p_gol}%</b> | "
                f"Prob. empate final: <b>{p_mantiene}%</b>\n"
                f"⏱ {mins} minutos restantes\n\n"
                f"<i>SharpIQ Live — La ventaja inteligente</i>"
            )

    return None


# ── ENVIAR ALERTA AL CANAL VIP ────────────────────────────────────

def enviar_alerta_live(texto):
    import requests
    from config import TELEGRAM_TOKEN
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "HTML"},
        timeout=10
    )


# ── LOOP PRINCIPAL ────────────────────────────────────────────────

def correr():
    inicializar_live_db()
    print(f"\n SharpIQ Live Monitor — {date.today().isoformat()}")

    partidos_hoy = partidos_publicados_hoy()
    if not partidos_hoy:
        print("  Sin partidos publicados hoy — monitor inactivo")
        return

    print(f"  Partidos monitoreando: {len(partidos_hoy)}")

    # IDs de ligas que seguimos
    liga_ids = ",".join(str(k) for k in LIGAS_APIFB.keys())

    ciclos_sin_partidos = 0

    while True:
        try:
            # Obtener fixtures en vivo
            data = _apifb("fixtures", {"live": liga_ids})
            fixtures_live = data.get("response", []) if data else []

            if not fixtures_live:
                ciclos_sin_partidos += 1
                print(f"  [{datetime.now().strftime('%H:%M')}] Sin partidos en vivo ({ciclos_sin_partidos})")
                # Salir si no hay partidos en 30 minutos
                if ciclos_sin_partidos >= 6:
                    print("  Sin actividad — monitor detenido")
                    break
                time.sleep(300)
                continue

            ciclos_sin_partidos = 0

            for fixture in fixtures_live:
                local  = fixture["teams"]["home"]["name"]
                visita = fixture["teams"]["away"]["name"]
                partido_str = f"{local} vs {visita}"

                # Solo monitorear partidos que publicamos
                es_publicado = any(
                    p.lower()[:15] in partido_str.lower() or
                    partido_str.lower()[:15] in p.lower()
                    for p in partidos_hoy
                )
                if not es_publicado:
                    continue

                fid    = fixture["fixture"]["id"]
                minuto = fixture["fixture"]["status"]["elapsed"] or 0
                gl     = fixture["goals"]["home"] or 0
                gv     = fixture["goals"]["away"] or 0
                marcador_cond = "0-0" if gl == 0 and gv == 0 else "any"

                print(f"  [{datetime.now().strftime('%H:%M')}] {partido_str} | {gl}-{gv} | Min {minuto}'")

                # Evaluar triggers
                for (min_min, min_max, cond, trigger) in TRIGGERS:
                    if not (min_min <= minuto <= min_max):
                        continue
                    if cond != "any" and cond != marcador_cond:
                        continue
                    if ya_enviado(fid, trigger):
                        continue

                    # Calcular probabilidades live
                    from motor import STATS_EQUIPOS, get_stats_equipo, calcular_goles_esperados
                    stats_l = get_stats_equipo(local)
                    stats_v = get_stats_equipo(visita)
                    gl_esp, gv_esp = calcular_goles_esperados(local, visita)
                    probs = probabilidades_live(gl_esp, gv_esp, minuto, gl, gv)

                    texto = construir_alerta(fixture, trigger, probs)
                    if texto:
                        enviar_alerta_live(texto)
                        marcar_enviado(fid, trigger)
                        print(f"  ✅ Alerta enviada: {trigger} | {partido_str}")

            time.sleep(300)  # Esperar 5 minutos

        except KeyboardInterrupt:
            print("\n  Monitor detenido manualmente")
            break
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    correr()
