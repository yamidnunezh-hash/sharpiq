# -*- coding: utf-8 -*-
"""
SharpIQ — Auto Publicar
Toma la mejor predicción del día y la publica en datos.js + push + Telegram.
Solo publica si tiene cuota REAL de la API (no estimada) y EV >= 15%.
"""
import os, sys, re, json, subprocess, logging
from datetime import date

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
DATOS_PATH  = os.path.join(BASE_DIR, "..", "datos.js")
INDEX_PATH  = os.path.join(BASE_DIR, "..", "index.html")
JSON_PATH   = os.path.join(BASE_DIR, "..", "predicciones.json")

# Marcadores para el bloque de datos inline en index.html
_DATA_START = "<!-- SHARPIQ_DATA_START -->"
_DATA_END   = "<!-- SHARPIQ_DATA_END -->"


def _get_log():
    """Reutiliza el logger del motor si ya fue inicializado, o crea uno propio."""
    lg = logging.getLogger("sharpiq.motor")
    if not lg.handlers:
        log_dir  = os.path.join(BASE_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"motor_{date.today().isoformat()}.log")
        lg.setLevel(logging.DEBUG)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        fh  = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        ch  = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        lg.addHandler(fh)
        lg.addHandler(ch)
        lg.propagate = False
    return lg

LOG = _get_log()


def registrar_tiers_clv(tiers):
    """Registra los 3 tiers (seguro/principal/alto_valor) en la tabla picks del CLV.
    Guarda el EV REAL del motor (ev_pinn, NO recalcula prob*cuota). pick_uid =
    evento_id:mercado (dedup + match en Fase 2 sin depender de nombres fragiles)."""
    try:
        from db_clv import guardar_pick, inicializar
        inicializar()  # idempotente
    except Exception as e:
        LOG.debug(f"CLV init: {e}")
        return
    for _tname in ("seguro", "principal", "alto_valor"):
        _tier = (tiers or {}).get(_tname)
        if not _tier:
            continue
        try:
            _p   = _tier["pred"]
            _mk  = _tier.get("mercado", "")
            _eid = str(_p.get("id", "") or "")
            _partido = f"{_p['local']} vs {_p['visitante']}"
            _uid = f"{_eid}:{_mk}" if _eid else f"{_p.get('fecha_evento','')}|{_partido}|{_mk}"
            _casa = ((_p.get("value_bets", {}) or {}).get(_mk, {}) or {}).get("casa", "")
            guardar_pick(
                pick_uid       = _uid,
                evento_id      = _eid,
                fecha_evento   = _p.get("fecha_evento") or date.today().isoformat(),
                comienzo       = _p.get("comienzo"),
                partido        = _partido,
                liga           = _p.get("liga", ""),
                liga_code      = str(_p.get("liga_code", "")),
                mercado        = _mk,
                tier           = _tname,
                casa           = _casa,
                prob_modelo    = float(_tier.get("prob", 0) or 0),
                cuota_apertura = float(_tier.get("cuota", 0) or 0),
                ev_apertura    = _tier.get("ev_pinn", _tier.get("ev")),
            )
            LOG.info(f"CLV registrado [{_tname}] {_mk} @ {_tier.get('cuota')} EV {_tier.get('ev_pinn')}")
        except Exception as e:
            LOG.debug(f"CLV guardar_pick [{_tname}]: {e}")


def _leer_predicciones():
    if not os.path.exists(JSON_PATH):
        return None
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _ya_publicado(local, visitante=""):
    """Verifica si el partido (local vs visitante) ya está en PROXIMOS_EVENTOS."""
    try:
        with open(DATOS_PATH, encoding="utf-8") as f:
            contenido = f.read().lower()
        # Verificar partido completo "local vs visitante" para evitar falsos positivos
        # cuando un equipo aparece como visitante en un pick anterior
        partido_str = f"{local} vs {visitante}".lower() if visitante else local.lower()
        # Buscar el string completo (mínimo 25 chars para evitar matches parciales)
        return partido_str[:30] in contenido
    except Exception:
        return False


def _hora_cot(hora_utc):
    try:
        h, m = hora_utc.split(":")
        cot = (int(h) - 5 + 24) % 24
        return f"{str(cot).zfill(2)}:{m} COT"
    except Exception:
        return hora_utc


def _agregar_a_datos_js(partido, liga, mercado, cuota, hora, ev, fecha_evento=None, tier="principal", stake_pct=3):
    if fecha_evento:
        try:
            from datetime import date as _date
            d = _date.fromisoformat(fecha_evento)
            fecha_str = d.strftime('%d/%m/%y')
        except Exception:
            fecha_str = date.today().strftime('%d/%m/%y')
    else:
        fecha_str = date.today().strftime('%d/%m/%y')

    ev_tag = f" — EV +{ev}%" if ev > 0 else ""
    nueva_entrada = f"""  {{
    fecha:      "{fecha_str}",
    partido:    "{partido}",
    liga:       "{liga}",
    prediccion: "{mercado}{ev_tag}",
    cuota:      "{cuota}",
    hora:       "{hora}",
    status:     "vip",
    tier:       "{tier}",
    stake_pct:  "{stake_pct}"
  }},"""

    patron = r'(const\s+PROXIMOS_EVENTOS\s*=\s*\[)'

    # Actualizar datos.js (backup)
    with open(DATOS_PATH, encoding="utf-8") as f:
        texto = f.read()
    texto_nuevo = re.sub(patron, r'\1\n' + nueva_entrada, texto)
    with open(DATOS_PATH, "w", encoding="utf-8") as f:
        f.write(texto_nuevo)

    # Actualizar TAMBIÉN el bloque inline de index.html (fuente real)
    try:
        with open(INDEX_PATH, encoding="utf-8") as f:
            html = f.read()
        # Reemplazar el bloque de datos inline completo con la versión actualizada de datos.js
        nuevo_bloque = (
            f"{_DATA_START}\n"
            f"<script id=\"sharpiq-data\">\n"
            f"{texto_nuevo.strip()}\n"
            f"</script>\n"
            f"{_DATA_END}"
        )
        html = re.sub(
            rf"{re.escape(_DATA_START)}.*?{re.escape(_DATA_END)}",
            nuevo_bloque,
            html,
            flags=re.DOTALL
        )
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as ex:
        LOG.warning(f"No se pudo actualizar inline data en index.html: {ex}")


def _hora_cot_de_pred(pred):
    h, m = pred.get("hora", "00:00").split(":")
    cot = (int(h) - 5 + 24) % 24
    return f"{str(cot).zfill(2)}:{m} COT"


def correr():
    LOG.info("=== SharpIQ Auto Publicar START (3 tiers) ===")

    # Ventana horaria en COT: solo picks con hora de inicio <= HASTA_HORA_COT
    HASTA_HORA_COT = int(os.environ.get("HASTA_HORA_COT", "23"))

    # Siempre correr el motor primero para tener predicciones frescas
    LOG.info("Corriendo motor...")
    try:
        from motor import guardar_predicciones
        guardar_predicciones()
    except Exception as e:
        LOG.error(f"Motor error: {e} — intentando con predicciones.json existente")

    reporte = _leer_predicciones()
    if not reporte:
        LOG.error("Sin predicciones.json — motor no pudo generar datos")
        return

    # Saludo matutino al canal free — solo una vez por día
    import os as _os
    BASE_DIR_AP = _os.path.dirname(_os.path.abspath(__file__))
    _saludo_sent = _os.path.join(BASE_DIR_AP, "logs", f"saludo_{date.today().isoformat()}.sent")
    if not _os.path.exists(_saludo_sent):
        try:
            from telegram_alertas import enviar_saludo_manana_free
            partidos_hoy = [
                {
                    "local":     p["local"],
                    "visitante": p["visitante"],
                    "liga":      p.get("liga", ""),
                    "hora":      _hora_cot_de_pred(p),
                    "fecha":     p.get("fecha_evento", date.today().isoformat()),
                }
                for p in reporte.get("predicciones", [])
            ]
            enviar_saludo_manana_free(partidos_hoy)
            open(_saludo_sent, "w").close()
            LOG.info("Saludo matutino enviado al canal free")
        except Exception as e:
            LOG.error(f"Saludo free error: {e}")
    else:
        LOG.info("Saludo de hoy ya enviado — skip")

    # ── Clasificar picks en 3 tiers ─────────────────────────────
    try:
        from motor import clasificar_tiers
        tiers = clasificar_tiers(reporte)
    except Exception as e:
        LOG.error(f"Error clasificar_tiers: {e}")
        tiers = {"seguro": None, "principal": None, "alto_valor": None}

    # Filtrar ya-publicados y partidos ya comenzados
    from datetime import datetime, timezone
    ahora_cot = datetime.now(timezone.utc).replace(tzinfo=None)
    ahora_cot = ahora_cot.replace(
        hour=(datetime.now(timezone.utc).replace(tzinfo=None).hour - 5) % 24,
        minute=datetime.now(timezone.utc).replace(tzinfo=None).minute
    )
    for k in ("seguro", "principal", "alto_valor"):
        t = tiers.get(k)
        if not t:
            continue
        if _ya_publicado(t["pred"]["local"], t["pred"].get("visitante", "")):
            LOG.info(f"Tier {k} ya publicado: {t['pred']['local']} vs {t['pred'].get('visitante','')}")
            tiers[k] = None
            continue
        # Descartar si el partido ya empezó o si está fuera de la ventana horaria
        try:
            hora_str = t["pred"].get("hora", "")
            if hora_str:
                h, m  = hora_str.split(":")
                cot_h = (int(h) - 5 + 24) % 24
                # Comparar en COT: hora actual COT vs hora del partido COT
                ahora_cot_h = (datetime.now(timezone.utc).replace(tzinfo=None).hour - 5) % 24
                ahora_cot_m = datetime.now(timezone.utc).replace(tzinfo=None).minute
                ahora_cot_mins  = ahora_cot_h * 60 + ahora_cot_m
                partido_cot_mins = cot_h * 60 + int(m)
                # Solo descartar si el partido es HOY en COT y ya pasó la hora
                fecha_ev = t["pred"].get("fecha_evento", date.today().isoformat())
                if fecha_ev == date.today().isoformat() and ahora_cot_mins >= partido_cot_mins:
                    LOG.warning(f"Tier {k} descartado — {t['pred']['local']} ya empezó ({cot_h:02d}:{m} COT)")
                    tiers[k] = None
                elif cot_h > HASTA_HORA_COT and fecha_ev == date.today().isoformat():
                    LOG.warning(f"Tier {k} fuera de ventana — {t['pred']['local']} a las {cot_h:02d}:{m} COT (ventana hasta {HASTA_HORA_COT:02d}:00)")
                    tiers[k] = None
        except Exception:
            pass

    tiene_alguno = any(tiers.get(k) for k in ("seguro", "principal", "alto_valor"))
    if not tiene_alguno:
        # Solo avisar a Yamid UNA vez al día, no en cada turno
        _sin_picks_sent = os.path.join(BASE_DIR_AP, "logs", f"sin_picks_{date.today().isoformat()}.sent")
        if not os.path.exists(_sin_picks_sent):
            try:
                from telegram_alertas import enviar_alerta_servicio, enviar_mensaje, get_chat_id
                _msg_sin = (
                    f"📭 <b>SharpIQ — Sin picks hoy</b>\n\n"
                    f"El motor no encontró valor suficiente para publicar hoy. "
                    f"Preferimos no apostar antes que forzar una jugada sin ventaja.\n\n"
                    f"<i>Mañana seguimos. La disciplina es parte del sistema.</i>"
                )
                # Aviso de SERVICIO → canal Alertas
                enviar_alerta_servicio(_msg_sin)
                # También al VIP, para que el suscriptor vea que el sistema funciona (no caído)
                try:
                    enviar_mensaje(_msg_sin, chat_id=get_chat_id())
                except Exception:
                    pass
                open(_sin_picks_sent, "w").close()
            except Exception:
                pass
        LOG.info("Sin picks nuevos hoy — fin")
        return

    # ── GIF + Mensaje VIP con los 3 tiers en un solo mensaje ────
    try:
        from telegram_alertas import enviar_gif_vip, enviar_tiers_vip, GIFS_MANANA, _gif_rotado
        enviar_gif_vip(_gif_rotado(GIFS_MANANA))
        enviar_tiers_vip(tiers["seguro"], tiers["principal"], tiers["alto_valor"])
        LOG.info("Tiers VIP enviados a Telegram")
        # Aviso de SERVICIO al canal Alertas (sin revelar los picks, eso es perk VIP)
        try:
            from telegram_alertas import enviar_alerta_servicio
            _n = sum(1 for k in ("seguro", "principal", "alto_valor") if tiers.get(k))
            enviar_alerta_servicio(
                f"✅ <b>SharpIQ — Picks de hoy publicados</b>\n\n"
                f"Ya hay {_n} pick(s) del día disponibles para suscriptores VIP.\n"
                f"🔒 Accede → https://sharpiq.co"
            )
        except Exception:
            pass
    except Exception as e:
        LOG.error(f"Telegram tiers error: {e}")

    # ── Aviso privado a Yamid ────────────────────────────────────
    try:
        from telegram_alertas import enviar_aviso_yamid
        lineas = []
        for k, emoji in [("seguro", "🛡️"), ("principal", "⭐"), ("alto_valor", "🔥")]:
            t = tiers.get(k)
            if t:
                steam_tag = " ⚡steam" if t.get("steam") else ""
                kelly_tag = f" | Kelly {t.get('kelly_pct', '')}%" if t.get("kelly_pct") else ""
                lineas.append(
                    f"{emoji} {t['pred']['local']} vs {t['pred']['visitante']} "
                    f"— {t['mercado_nombre']} @{t['cuota']}{steam_tag}{kelly_tag}"
                )
        enviar_aviso_yamid(
            f"🤖 <b>SharpIQ — 3 Tiers publicados</b>\n\n"
            + "\n".join(lineas)
            + "\n\n✅ Canal VIP + sharpiq.co actualizados"
        )
    except Exception as e:
        LOG.error(f"Yamid aviso error: {e}")

    # ── Actualizar datos.js con los 3 tiers ──────────────────────
    _CK_MAP = {
        "victoria_local":"1","empate":"X","victoria_visita":"2",
        "over15":"over15","under15":"under15","over25":"over25","under25":"under25",
        "over35":"over35","under35":"under35","btts_si":"btts_si","btts_no":"btts_no",
        "doble_12":"doble_12","dnb_local":"dnb_local","dnb_visita":"dnb_visita",
    }
    _STAKE_PCT = {"seguro": 3, "principal": 3, "alto_valor": 2}
    for k in ("seguro", "principal", "alto_valor"):
        t = tiers.get(k)
        if not t:
            continue
        pred      = t["pred"]
        partido   = f"{pred['local']} vs {pred['visitante']}"
        liga      = pred.get("liga", "")
        hora_cot  = _hora_cot(pred.get("hora", "00:00"))
        ev_val    = round(t.get("ev_pinn", t.get("ev", 0)) or 0)
        fecha_ev  = pred.get("fecha_evento") or pred.get("fecha") or None
        # Kelly dinámico — si no hay kelly_pct cae al tope del tier (seguro/principal=3%, alto_valor=2%)
        stake_pct = t.get("kelly_pct") or _STAKE_PCT.get(k, 3)
        _agregar_a_datos_js(partido, liga, t["mercado_nombre"], str(t["cuota"]),
                            hora_cot, ev_val, fecha_evento=fecha_ev,
                            tier=k, stake_pct=stake_pct)
        LOG.info(f"datos.js [{k}]: {partido} | {t['mercado_nombre']} @{t['cuota']} | Kelly {stake_pct}%")

    # ── Git push (robusto ante carreras/conflictos entre workflows) ──
    repo_dir = os.path.join(BASE_DIR, "..")

    def _git(*args):
        return subprocess.run(["git", *args], cwd=repo_dir,
                              capture_output=True, text=True)

    try:
        picks_str = " | ".join(
            tiers[k]["mercado_nombre"]
            for k in ("seguro", "principal", "alto_valor") if tiers.get(k)
        )

        # Si una corrida anterior dejó un rebase a medias, abortarlo (evita exit 128)
        _git("rebase", "--abort")

        # 1) Commitear primero los cambios locales (datos.js + bloque inline de index.html)
        _git("add", "datos.js", "index.html")
        commit = _git("commit", "-m",
                      f"auto: picks {date.today().isoformat()} — {picks_str}")
        sin_cambios = "nothing to commit" in (commit.stdout + commit.stderr)
        if sin_cambios:
            LOG.info("Git: sin cambios locales para commitear")

        # 2) push → si la rama está detrás, integrar con rebase y reintentar
        pushed = False
        for intento in range(3):
            push = _git("push", "origin", "main")
            if push.returncode == 0:
                pushed = True
                break
            pull = _git("pull", "--rebase", "origin", "main")
            if pull.returncode != 0:
                # Conflicto irreconciliable: abortar para dejar el repo limpio.
                # datos.js se regenera la próxima corrida, así no se corrompe nada.
                _git("rebase", "--abort")
                LOG.error(f"Git: conflicto de rebase (intento {intento+1}/3): "
                          f"{(pull.stderr or pull.stdout).strip()[:200]}")
                break

        if pushed:
            LOG.info("GitHub actualizado")
        elif not sin_cambios:
            LOG.error("Git: no se pudo hacer push tras 3 intentos")
    except Exception as e:
        LOG.error(f"Git error: {e}")

    # ── Canal free: TODOS los picks del día (1 gratis descubierto + resto tapados) ──
    try:
        from telegram_alertas import enviar_picks_free
        _fecha_free = None
        for _k in ("seguro", "principal", "alto_valor"):
            if tiers.get(_k):
                _fecha_free = tiers[_k]["pred"].get("fecha_evento")
                break
        enviar_picks_free(tiers, fecha=_fecha_free)
        print("  Canal free (todos los picks) enviado")
    except Exception as e:
        print(f"  Free canal error: {e}")

    # ── Para el mejor pick: CLV snapshot + narrativa + mercados ext
    mejor_tier = tiers.get("alto_valor") or tiers.get("principal") or tiers.get("seguro")

    if mejor_tier:
        try:
            from database import inicializar, guardar_snapshot, guardar_picks_clv
            inicializar()
            pred       = mejor_tier["pred"]
            fixture_id = pred.get("id")
            if fixture_id:
                guardar_snapshot(
                    fixture_id, pred["local"], pred["visitante"],
                    date.today().isoformat(), "apertura",
                    pred.get("cuotas", {})
                )
                # Registrar pick en picks_clv para tracking de CLV
                guardar_picks_clv(
                    fixture_id,
                    pred["local"], pred["visitante"],
                    date.today().isoformat(),
                    mejor_tier.get("mercado", ""),
                    float(mejor_tier.get("cuota", 0)),
                )
                LOG.info(f"CLV snapshot apertura guardado — fixture {fixture_id}")
        except Exception as e:
            LOG.error(f"CLV snapshot error: {e}")

        # ── CLV tracking PostgreSQL (db_clv): registra los 3 tiers en apertura.
        registrar_tiers_clv(tiers)

        try:
            from telegram_alertas import enviar_mercados_ext_vip
            enviar_mercados_ext_vip(mejor_tier["pred"])
            LOG.info("Mercados extendidos enviados (VIP)")
        except Exception as e:
            LOG.error(f"Mercados ext error: {e}")

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

    # ── Auto-resultados: actualizar picks pendientes de días anteriores ──
    try:
        from auto_resultados import correr as _correr_resultados
        _correr_resultados()
    except Exception as e:
        LOG.error(f"Auto-resultados error: {e}")

    # ── Monitor en vivo ──────────────────────────────────────────
    try:
        monitor_path = os.path.join(BASE_DIR, "live_monitor.py")
        subprocess.Popen(
            [sys.executable, monitor_path],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        LOG.info("Monitor en vivo iniciado")
    except Exception as e:
        LOG.error(f"Monitor en vivo error: {e}")

    return tiers


if __name__ == "__main__":
    correr()
