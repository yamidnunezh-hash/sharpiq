# -*- coding: utf-8 -*-
"""
SharpIQ — Auto Publicar
Toma la mejor predicción del día y la publica en datos.js + push + Telegram.
Solo publica si tiene cuota REAL de la API (no estimada) y EV >= 15%.
"""
import os, sys, re, json, subprocess
from datetime import date

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
DATOS_PATH = os.path.join(BASE_DIR, "..", "datos.js")
JSON_PATH  = os.path.join(BASE_DIR, "..", "predicciones.json")


def _leer_predicciones():
    if not os.path.exists(JSON_PATH):
        return None
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _ya_publicado(partido):
    """Verifica si el partido ya está en PROXIMOS_EVENTOS de datos.js."""
    try:
        with open(DATOS_PATH, encoding="utf-8") as f:
            contenido = f.read()
        return partido.lower()[:20] in contenido.lower()
    except Exception:
        return False


def _hora_cot(hora_utc):
    try:
        h, m = hora_utc.split(":")
        cot = (int(h) - 5 + 24) % 24
        return f"{str(cot).zfill(2)}:{m} COT"
    except Exception:
        return hora_utc


def _agregar_a_datos_js(partido, liga, mercado, cuota, hora, ev):
    with open(DATOS_PATH, encoding="utf-8") as f:
        texto = f.read()

    nueva_entrada = f"""  {{
    fecha:      "{date.today().strftime('%d/%m/%y')}",
    partido:    "{partido}",
    liga:       "{liga}",
    prediccion: "{mercado} — EV +{ev}%",
    cuota:      "{cuota}",
    hora:       "{hora}",
    status:     "vip"
  }},"""

    texto_nuevo = re.sub(
        r'(const\s+PROXIMOS_EVENTOS\s*=\s*\[)',
        r'\1\n' + nueva_entrada,
        texto
    )
    with open(DATOS_PATH, "w", encoding="utf-8") as f:
        f.write(texto_nuevo)


def _hora_cot_de_pred(pred):
    h, m = pred.get("hora", "00:00").split(":")
    cot = (int(h) - 5 + 24) % 24
    return f"{str(cot).zfill(2)}:{m} COT"


def correr():
    print("\n SharpIQ — Auto Publicar")

    reporte = _leer_predicciones()
    if not reporte:
        print("  Sin predicciones.json — corre motor.py primero")
        return

    # Saludo matutino al canal free con lista de partidos del día
    try:
        from telegram_alertas import enviar_saludo_manana_free
        partidos_hoy = [
            {
                "local":    p["local"],
                "visitante": p["visitante"],
                "liga":     p.get("liga", ""),
                "hora":     _hora_cot_de_pred(p),
            }
            for p in reporte.get("predicciones", [])
        ]
        enviar_saludo_manana_free(partidos_hoy)
        print("  Saludo matutino enviado al canal free ✓")
    except Exception as e:
        print(f"  Saludo free error: {e}")

    # Buscar mejor predicción con cuota real y EV >= 15%
    candidatos = []
    for pred in reporte.get("predicciones", []):
        if not pred.get("cuotas_reales"):
            continue  # Solo cuotas reales — nunca estimadas
        for mercado, vb in pred.get("value_bets", {}).items():
            if not vb or not vb.get("tiene_valor"):
                continue
            if vb.get("ev_porcentaje", 0) < 15:
                continue
            candidatos.append((pred, mercado, vb))

    if not candidatos:
        print("  Sin value bets con cuota real y EV >= 15% hoy")
        try:
            from telegram_alertas import enviar_aviso_yamid
            enviar_aviso_yamid(
                f"📋 <b>SharpIQ — Motor {date.today().isoformat()}</b>\n\n"
                f"Sin predicciones con cuota real hoy.\n"
                f"Verifica manualmente en localhost:8080/predicciones.html"
            )
        except Exception:
            pass
        return

    # Ordenar por EV descendente, priorizar ALTO VALOR
    candidatos.sort(key=lambda x: (
        x[2].get("clasificacion") == "ALTO VALOR",
        x[2].get("ev_porcentaje", 0)
    ), reverse=True)

    pred, mercado, vb = candidatos[0]
    partido  = f"{pred['local']} vs {pred['visitante']}"
    liga     = pred.get("liga", "")
    hora_utc = pred.get("hora", "00:00")
    hora_cot = _hora_cot(hora_utc)
    ev       = vb["ev_porcentaje"]

    nombres = {
        "victoria_local":  "Victoria Local (1)",
        "empate":          "Empate (X)",
        "victoria_visita": "Victoria Visitante (2)",
        "over25":          "Over 2.5 Goles",
        "under25":         "Under 2.5 Goles",
        "over15":          "Over 1.5 Goles",
        "under15":         "Under 1.5 Goles",
        "over35":          "Over 3.5 Goles",
        "btts_si":         "Ambos Marcan",
    }
    cuota_map = {
        "victoria_local":"1","empate":"X","victoria_visita":"2",
        "over25":"over25","under25":"under25","over15":"over15",
        "under15":"under15","over35":"over35","btts_si":"btts_si",
    }
    nombre_mercado = nombres.get(mercado, mercado)
    cuota = str(pred["cuotas"].get(cuota_map.get(mercado, "1"), "?"))

    if _ya_publicado(partido):
        print(f"  Ya publicado: {partido}")
        return

    print(f"  Publicando: {partido} | {nombre_mercado} @ {cuota} | EV +{ev}%")

    # Actualizar datos.js
    _agregar_a_datos_js(partido, liga, nombre_mercado, cuota, hora_cot, ev)

    # Git push
    repo_dir = os.path.join(BASE_DIR, "..")
    try:
        subprocess.run(["git", "add", "datos.js"], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m",
            f"auto: publicar {partido} — {nombre_mercado} EV+{ev}%"],
            cwd=repo_dir, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, check=True)
        print("  GitHub actualizado ✓")
    except subprocess.CalledProcessError as e:
        print(f"  Git error: {e}")

    # Telegram: tres destinos
    try:
        from telegram_alertas import enviar_autopublicacion, enviar_mensaje, enviar_canal_free
        from config import TELEGRAM_CHAT_ID

        # 1. Aviso privado a Yamid
        enviar_autopublicacion(partido, liga, nombre_mercado, cuota, hora_cot, ev)

        # 2. Canal VIP — predicción completa
        enviar_mensaje(
            f"🔥 <b>SharpIQ — Nueva Predicción VIP</b>\n\n"
            f"⚽ <b>{partido}</b>\n"
            f"🏆 {liga} | {hora_cot}\n"
            f"📊 <b>Mercado:</b> {nombre_mercado}\n"
            f"💵 <b>Cuota:</b> {cuota}\n"
            f"⚡ <b>EV:</b> +{ev}%\n\n"
            f"<i>SharpIQ — La ventaja inteligente</i>",
            chat_id=TELEGRAM_CHAT_ID
        )

        # 3. Canal free — teaser sin mercado ni cuota
        enviar_canal_free(partido, liga, hora_cot)

        print("  Telegram enviado (VIP + Free + Yamid) ✓")
    except Exception as e:
        print(f"  Telegram error: {e}")

    # Push notification a suscriptores web
    try:
        from push_notifications import enviar_push_prediccion
        enviados = enviar_push_prediccion(partido, nombre_mercado, cuota, ev)
        if enviados:
            print(f"  Push enviado a {enviados} suscriptores ✓")
    except Exception as e:
        print(f"  Push error: {e}")

    return {"partido": partido, "mercado": nombre_mercado, "cuota": cuota, "ev": ev}


if __name__ == "__main__":
    correr()
