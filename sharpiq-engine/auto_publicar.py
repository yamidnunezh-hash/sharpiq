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

    ev_tag = f" — EV +{ev}%" if ev > 0 else ""
    nueva_entrada = f"""  {{
    fecha:      "{date.today().strftime('%d/%m/%y')}",
    partido:    "{partido}",
    liga:       "{liga}",
    prediccion: "{mercado}{ev_tag}",
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
    print("\n SharpIQ — Auto Publicar (3 tiers)")

    reporte = _leer_predicciones()
    if not reporte:
        print("  Sin predicciones.json — corre motor.py primero")
        return

    # Saludo matutino al canal free con lista de partidos del día
    try:
        from telegram_alertas import enviar_saludo_manana_free
        partidos_hoy = [
            {
                "local":     p["local"],
                "visitante": p["visitante"],
                "liga":      p.get("liga", ""),
                "hora":      _hora_cot_de_pred(p),
            }
            for p in reporte.get("predicciones", [])
        ]
        enviar_saludo_manana_free(partidos_hoy)
        print("  Saludo matutino enviado al canal free")
    except Exception as e:
        print(f"  Saludo free error: {e}")

    # ── Clasificar picks en 3 tiers ─────────────────────────────
    try:
        from motor import clasificar_tiers
        tiers = clasificar_tiers(reporte)
    except Exception as e:
        print(f"  Error clasificar_tiers: {e}")
        tiers = {"seguro": None, "principal": None, "alto_valor": None}

    # Filtrar ya-publicados
    for k in ("seguro", "principal", "alto_valor"):
        t = tiers.get(k)
        if t and _ya_publicado(t["pred"]["local"]):
            print(f"  Tier {k} ya publicado: {t['pred']['local']}")
            tiers[k] = None

    tiene_alguno = any(tiers.get(k) for k in ("seguro", "principal", "alto_valor"))
    if not tiene_alguno:
        try:
            from telegram_alertas import enviar_aviso_yamid
            enviar_aviso_yamid(
                f"⚠️ SharpIQ {date.today().isoformat()} — "
                f"Sin condiciones para los 3 tiers hoy (todos ya publicados o sin cuotas DNB/Over1.5)."
            )
        except Exception:
            pass
        print("  Sin picks nuevos hoy")
        return

    # ── GIF + Mensaje VIP con los 3 tiers en un solo mensaje ────
    try:
        from telegram_alertas import enviar_gif_vip, enviar_tiers_vip, GIFS_MANANA
        import random
        enviar_gif_vip(random.choice(GIFS_MANANA))
        enviar_tiers_vip(tiers["seguro"], tiers["principal"], tiers["alto_valor"])
        print("  Tiers VIP enviados")
    except Exception as e:
        print(f"  Telegram tiers error: {e}")

    # ── Aviso privado a Yamid ────────────────────────────────────
    try:
        from telegram_alertas import enviar_aviso_yamid
        lineas = []
        for k, emoji in [("seguro", "🛡️"), ("principal", "⭐"), ("alto_valor", "🔥")]:
            t = tiers.get(k)
            if t:
                lineas.append(
                    f"{emoji} {t['pred']['local']} vs {t['pred']['visitante']} "
                    f"— {t['mercado_nombre']} @{t['cuota']}"
                )
        enviar_aviso_yamid(
            f"🤖 <b>SharpIQ — 3 Tiers publicados</b>\n\n"
            + "\n".join(lineas)
            + "\n\n✅ Canal VIP + sharpiq.co actualizados"
        )
    except Exception as e:
        print(f"  Yamid aviso error: {e}")

    # ── Actualizar datos.js con los 3 tiers ──────────────────────
    _CK_MAP = {
        "victoria_local":"1","empate":"X","victoria_visita":"2",
        "over15":"over15","under15":"under15","over25":"over25","under25":"under25",
        "over35":"over35","under35":"under35","btts_si":"btts_si","btts_no":"btts_no",
        "doble_12":"doble_12","dnb_local":"dnb_local","dnb_visita":"dnb_visita",
    }
    for k in ("seguro", "principal", "alto_valor"):
        t = tiers.get(k)
        if not t:
            continue
        pred     = t["pred"]
        partido  = f"{pred['local']} vs {pred['visitante']}"
        liga     = pred.get("liga", "")
        hora_cot = _hora_cot(pred.get("hora", "00:00"))
        ev_val   = round(t.get("ev_pinn", t.get("ev", 0)) or 0)
        _agregar_a_datos_js(partido, liga, t["mercado_nombre"], str(t["cuota"]), hora_cot, ev_val)
        print(f"  datos.js: {partido} | {t['mercado_nombre']} @{t['cuota']}")

    # ── Git push ─────────────────────────────────────────────────
    repo_dir = os.path.join(BASE_DIR, "..")
    try:
        picks_str = " | ".join(
            tiers[k]["mercado_nombre"]
            for k in ("seguro", "principal", "alto_valor") if tiers.get(k)
        )
        subprocess.run(["git", "add", "datos.js"], cwd=repo_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"auto: picks {date.today().isoformat()} — {picks_str}"],
            cwd=repo_dir, check=True
        )
        subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, check=True)
        print("  GitHub actualizado")
    except subprocess.CalledProcessError as e:
        print(f"  Git error: {e}")

    # ── Canal free: teaser partido + aviso de picks VIP ──────────
    try:
        from telegram_alertas import enviar_canal_free, enviar_mensaje
        from config import TELEGRAM_FREE_ID
        teaser = tiers.get("alto_valor") or tiers.get("seguro") or tiers.get("principal")
        if teaser:
            p = teaser["pred"]
            enviar_canal_free(
                f"{p['local']} vs {p['visitante']}",
                p.get("liga", ""),
                _hora_cot(p.get("hora", "00:00"))
            )
        total_picks = sum(1 for k in ("seguro", "principal", "alto_valor") if tiers.get(k))
        if total_picks > 1:
            partidos_str = "\n".join(
                f"⚽ {tiers[k]['pred']['local']} vs {tiers[k]['pred']['visitante']}"
                for k in ("seguro", "principal", "alto_valor") if tiers.get(k)
            )
            enviar_mensaje(
                f"📋 <b>Hoy hay {total_picks} picks en el canal VIP</b>\n\n"
                f"{partidos_str}\n\n"
                f"🔒 Mercados y cuotas exactas solo para suscriptores\n"
                f"👉 <a href=\"https://t.me/sharpiq_alertas_bot\">Activar acceso VIP</a>\n\n"
                f"<i>SharpIQ — La ventaja inteligente</i>",
                chat_id=TELEGRAM_FREE_ID
            )
        print("  Canal free enviado")
    except Exception as e:
        print(f"  Free canal error: {e}")

    # ── Para el mejor pick: CLV snapshot + narrativa + mercados ext
    mejor_tier = tiers.get("alto_valor") or tiers.get("principal") or tiers.get("seguro")

    if mejor_tier:
        try:
            from database import inicializar, guardar_snapshot
            inicializar()
            pred = mejor_tier["pred"]
            fixture_id = pred.get("id")
            if fixture_id:
                guardar_snapshot(
                    fixture_id, pred["local"], pred["visitante"],
                    date.today().isoformat(), "apertura",
                    pred.get("cuotas", {})
                )
                print("  CLV snapshot apertura guardado")
        except Exception as e:
            print(f"  CLV snapshot error: {e}")

        try:
            from telegram_alertas import enviar_narrativa
            pred    = mejor_tier["pred"]
            mk      = mejor_tier["mercado"]
            vb_data = pred.get("value_bets", {}).get(mk, {})
            enviar_narrativa(pred, mk, vb_data)
            print("  Narrativa enviada (Free + VIP)")
        except Exception as e:
            print(f"  Narrativa error: {e}")

        try:
            from telegram_alertas import enviar_mercados_ext_vip
            enviar_mercados_ext_vip(mejor_tier["pred"])
            print("  Mercados extendidos enviados (VIP)")
        except Exception as e:
            print(f"  Mercados ext error: {e}")

        try:
            from push_notifications import enviar_push_prediccion
            pred     = mejor_tier["pred"]
            partido  = f"{pred['local']} vs {pred['visitante']}"
            ev_push  = round(mejor_tier.get("ev_pinn", 0) or 0)
            enviados = enviar_push_prediccion(
                partido, mejor_tier["mercado_nombre"], str(mejor_tier["cuota"]), ev_push
            )
            if enviados:
                print(f"  Push enviado a {enviados} suscriptores")
        except Exception as e:
            print(f"  Push error: {e}")

    # ── Monitor en vivo ──────────────────────────────────────────
    try:
        monitor_path = os.path.join(BASE_DIR, "live_monitor.py")
        subprocess.Popen(
            [sys.executable, monitor_path],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        print("  Monitor en vivo iniciado")
    except Exception as e:
        print(f"  Monitor en vivo error: {e}")

    return tiers


if __name__ == "__main__":
    correr()
