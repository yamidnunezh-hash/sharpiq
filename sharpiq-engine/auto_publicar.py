# -*- coding: utf-8 -*-
"""
SharpIQ — Auto Publicar
Toma la mejor predicción del día y la publica en datos.js + push + Telegram.
Solo publica si tiene cuota REAL de la API (no estimada) y EV >= 15%.
"""
import os, sys, re, json, subprocess, logging
from datetime import date, datetime, timezone, timedelta

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
DATOS_PATH  = os.path.join(BASE_DIR, "..", "datos.js")
INDEX_PATH  = os.path.join(BASE_DIR, "..", "index.html")
JSON_PATH   = os.path.join(BASE_DIR, "..", "predicciones.json")

# Marcadores para el bloque de datos inline en index.html
_DATA_START = "<!-- SHARPIQ_DATA_START -->"
_DATA_END   = "<!-- SHARPIQ_DATA_END -->"


def _hoy_cot():
    """Fecha de HOY en hora de Colombia (UTC-5).
    OJO: en GitHub Actions el reloj del servidor es UTC. La corrida de las
    7 PM COT se ejecuta a las 00:23 UTC (ya es el dia siguiente en UTC), asi
    que _hoy_cot() daria la fecha de MANANA. Esto la corrige a la fecha real
    de Colombia. Usar SIEMPRE esto en vez de _hoy_cot() para fechas de picks."""
    return (datetime.now(timezone.utc) - timedelta(hours=5)).date()


def _get_log():
    """Reutiliza el logger del motor si ya fue inicializado, o crea uno propio."""
    lg = logging.getLogger("sharpiq.motor")
    if not lg.handlers:
        log_dir  = os.path.join(BASE_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"motor_{_hoy_cot().isoformat()}.log")
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
                fecha_evento   = _p.get("fecha_evento") or _hoy_cot().isoformat(),
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


def _dedup_proximos_texto(texto):
    """Dedup + limpieza de PROXIMOS_EVENTOS. Solo afecta PENDIENTES; los
    resueltos (win/loss) se conservan intactos para el historial. Reglas:
      - colapsa el MISMO mercado aunque cambie el sufijo '— EV +X%'
      - tarjetas FUERA (mercado demasiado volatil; decision de producto)
      - maximo 2 picks por (partido, fecha): 1 SEGURO + 1 RECOMENDADO
    Evita picks repetidos/saturados en la web."""
    try:
        m = re.search(r'(const\s+PROXIMOS_EVENTOS\s*=\s*\[)(.*?)(\];)', texto, re.S)
        if not m:
            return texto
        head, body, tail = m.group(1), m.group(2), m.group(3)
        objs = re.findall(r'\{[^{}]*\}', body)
        def _campo(o, k):
            mm = re.search(k + r'\s*:\s*["\']([^"\']*)["\']', o)
            return mm.group(1) if mm else ""
        def _norm_pred(o):
            # quita ' — EV +X%' para que el mismo mercado no se duplique entre corridas
            return re.sub(r'\s*[-—]\s*EV\s*[+\-]?[0-9.]+%', '',
                          _campo(o, 'prediccion')).strip().lower()
        def _es_pend(o):
            return _campo(o, 'resultado') in ('', 'pendiente', 'pending')
        # 1) dedup por (partido, fecha, mercado-normalizado); prefiere el resuelto
        best = {}; orden = []
        for o in objs:
            part = _campo(o, 'partido')
            if not part:
                continue
            key = (part, _campo(o, 'fecha'), _norm_pred(o))
            res = _campo(o, 'resultado')
            if key not in best:
                best[key] = o; orden.append(key)
            elif res in ('win', 'loss') and _campo(best[key], 'resultado') not in ('win', 'loss'):
                best[key] = o
        objs2 = [best[k] for k in orden]
        # 2) tarjetas FUERA (solo pendientes; los resueltos se quedan por integridad)
        objs2 = [o for o in objs2
                 if not (_es_pend(o) and 'tarjeta' in _campo(o, 'prediccion').lower())]
        # 3) NUNCA se borra un pick ya publicado.
        #
        # Aqui habia un recorte a "max 2 pendientes por (partido, fecha)" ordenando
        # por tier. Cada corrida del motor volvia a aplicarlo, asi que un pick
        # publicado a las 11am podia ser DESALOJADO a la 1pm por otro de mejor tier
        # y desaparecer sin resolverse. Paso 29 veces en 224 picks (12.9%): el VIP
        # veia la jugada, la apostaba, y nunca aparecia en el historial.
        # (Caso real: France vs Morocco "Ambos Marcan @2.04 ALTO VALOR", 09/07 —
        #  lo echaron dos picks "seguro" y el partido termino 2-0: era derrota.)
        #
        # El tope de 2 por partido ahora se aplica AL AGREGAR (_agregar_a_datos_js),
        # que es donde corresponde. Publicado es publicado.
        kept = objs2
        if len(kept) == len(objs):
            return texto   # nada que limpiar
        nuevo_body = "\n  " + ",\n  ".join(kept) + "\n"
        return texto[:m.start()] + head + nuevo_body + tail + texto[m.end():]
    except Exception:
        return texto


def _agregar_a_datos_js(partido, liga, mercado, cuota, hora, ev, fecha_evento=None, tier="principal", stake_pct=3, prob=""):
    if fecha_evento:
        try:
            from datetime import date as _date
            d = _date.fromisoformat(fecha_evento)
            fecha_str = d.strftime('%d/%m/%y')
        except Exception:
            fecha_str = _hoy_cot().strftime('%d/%m/%y')
    else:
        fecha_str = _hoy_cot().strftime('%d/%m/%y')

    # El EV es metrica INTERNA (se mueve con la cuota) -> NO se muestra al cliente.
    ev_tag = ""
    # SharpScore(TM): el sello 0-100 de SharpIQ (prob + EV + tier). SI se muestra.
    try:
        import sharpscore
        _ss = sharpscore.calcular(prob=prob, ev=ev, tier=tier)
    except Exception:
        _ss = ""
    nueva_entrada = f"""  {{
    fecha:      "{fecha_str}",
    partido:    "{partido}",
    liga:       "{liga}",
    prediccion: "{mercado}{ev_tag}",
    cuota:      "{cuota}",
    hora:       "{hora}",
    status:     "vip",
    tier:       "{tier}",
    stake_pct:  "{stake_pct}",
    prob:       "{prob}",
    sharpscore: "{_ss}",
    resultado:  "pendiente"
  }},"""

    patron = r'(const\s+PROXIMOS_EVENTOS\s*=\s*\[)'

    # Actualizar datos.js (backup)
    with open(DATOS_PATH, encoding="utf-8") as f:
        texto = f.read()

    # TOPE AL AGREGAR (no borrando): si ya hay 2 picks PENDIENTES de este mismo
    # partido+fecha, no se publica un tercero. Antes el tope se aplicaba en la
    # limpieza, que desalojaba picks ya publicados -> desaparecian sin resolverse.
    # Tambien evita re-publicar un pick identico que ya existe.
    try:
        _i = texto.find('PROXIMOS_EVENTOS'); _j = texto.find('PREDICCIONES_HISTORIAL')
        _prox = texto[_i:_j if _j > _i else len(texto)]
        _pend, _existe = 0, False
        for _b in re.findall(r'\{[^{}]*\}', _prox, re.S):
            _gp = (re.search(r'partido:\s*"([^"]*)"', _b) or [None, ''])[1]
            _gf = (re.search(r'fecha:\s*"([^"]*)"', _b) or [None, ''])[1]
            _gr = (re.search(r'resultado:\s*"([^"]*)"', _b) or [None, ''])[1]
            _gm = (re.search(r'prediccion:\s*"([^"]*)"', _b) or [None, ''])[1]
            if _gp == partido and _gf == fecha_str:
                if _gm.split('—')[0].strip() == str(mercado).split('—')[0].strip():
                    _existe = True
                if _gr in ('', 'pendiente', 'pending'):
                    _pend += 1
        if _existe or _pend >= 2:
            LOG.info(f"datos.js: NO se agrega {partido} | {mercado} "
                     f"(ya hay {_pend} pendiente(s) o el pick ya existe)")
            return
    except Exception:
        pass

    texto_nuevo = re.sub(patron, r'\1\n' + nueva_entrada, texto)
    texto_nuevo = _dedup_proximos_texto(texto_nuevo)
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

    # Saludo matutino al canal free — solo en la MAÑANA (5-11 COT) y una vez por día.
    # Antes solo miraba el marcador; sin chequeo de hora mandaba "Buenos días" en
    # corridas de tarde/noche (crons retrasados + logs/ no persiste entre runs).
    import os as _os
    from datetime import datetime as _dtap, timezone as _tzap, timedelta as _tdap
    BASE_DIR_AP = _os.path.dirname(_os.path.abspath(__file__))
    _saludo_sent = _os.path.join(BASE_DIR_AP, "logs", f"saludo_{_hoy_cot().isoformat()}.sent")
    _hcot_ap = (_dtap.now(_tzap.utc) - _tdap(hours=5)).hour
    _es_manana_ap = 5 <= _hcot_ap < 11
    if _es_manana_ap and not _os.path.exists(_saludo_sent):
        try:
            from telegram_alertas import enviar_saludo_manana_free
            partidos_hoy = [
                {
                    "local":     p["local"],
                    "visitante": p["visitante"],
                    "liga":      p.get("liga", ""),
                    "hora":      _hora_cot_de_pred(p),
                    "fecha":     p.get("fecha_evento", _hoy_cot().isoformat()),
                }
                for p in reporte.get("predicciones", [])
            ]
            enviar_saludo_manana_free(partidos_hoy)
            open(_saludo_sent, "w").close()
            LOG.info("Saludo matutino enviado al canal free")
        except Exception as e:
            LOG.error(f"Saludo free error: {e}")
    elif not _es_manana_ap:
        LOG.info(f"Saludo matutino: skip (hora COT {_hcot_ap}h — solo en la mañana)")
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
                fecha_ev = t["pred"].get("fecha_evento", _hoy_cot().isoformat())
                if fecha_ev == _hoy_cot().isoformat() and ahora_cot_mins >= partido_cot_mins:
                    LOG.warning(f"Tier {k} descartado — {t['pred']['local']} ya empezó ({cot_h:02d}:{m} COT)")
                    tiers[k] = None
                elif cot_h > HASTA_HORA_COT and fecha_ev == _hoy_cot().isoformat():
                    LOG.warning(f"Tier {k} fuera de ventana — {t['pred']['local']} a las {cot_h:02d}:{m} COT (ventana hasta {HASTA_HORA_COT:02d}:00)")
                    tiers[k] = None
        except Exception:
            pass

    # ── DOS PICKS POR PARTIDO DE FUTBOL: SEGURO + RECOMENDADO (sin limite/ventana) ──
    # Para CADA partido de futbol de HOY que aun no empieza, publica DOS picks:
    #   - SEGURO      -> mayor probabilidad (la banca, cuota baja)
    #   - RECOMENDADO -> mejor valor/EV real (mas upside, cuota un poco mas alta)
    # Sin filtro de ventana ni limite de 3. El producto nunca queda vacio con futbol.
    # Bloque AUTONOMO y a prueba de fallos: si algo revienta, NO afecta los 3 tiers.
    _mundial_publicados = 0
    try:
        _NOM = {
            "victoria_local": "Victoria Local", "empate": "Empate", "victoria_visita": "Victoria Visitante",
            "over05": "Over 0.5 Goles", "under05": "Under 0.5 Goles", "over15": "Over 1.5 Goles", "under15": "Under 1.5 Goles",
            "over25": "Over 2.5 Goles", "under25": "Under 2.5 Goles", "over35": "Over 3.5 Goles", "under35": "Under 3.5 Goles",
            "over45": "Over 4.5 Goles", "under45": "Under 4.5 Goles", "btts_si": "Ambos Marcan", "btts_no": "Ambos No Marcan",
            "doble_1x": "Doble Oportunidad 1X", "doble_x2": "Doble Oportunidad X2", "doble_12": "Doble Oportunidad 12",
            "dnb_local": "Draw No Bet Local", "dnb_visita": "Draw No Bet Visitante",
        }
        def _nombre(_mk, _vb):
            return _vb.get("mercado_nombre") or _NOM.get(_mk) or _mk.replace("_", " ").title()
        def _familia(_mk):
            """Mercados que son 'la misma apuesta con otra cara'.

            Contar la diversidad por clave exacta no sirve: 'Over 1.5' y 'Under 3.5'
            son claves distintas pero AMBAS son goles, y el motor terminaba ofreciendo
            la misma jugada 6 veces al dia creyendo que variaba.
            """
            if _mk.startswith("corners_"):                      return "corners"
            if _mk.startswith("cards_"):                        return "tarjetas"
            if _mk.startswith("ah_"):                           return "handicap"
            if _mk.startswith(("over", "under")):               return "goles"
            if _mk.startswith("btts"):                          return "btts"
            if _mk.startswith(("doble_", "dnb_")):              return "resultado"
            if _mk in ("victoria_local", "empate", "victoria_visita"): return "resultado"
            return _mk

        def _candidatos(_p):
            """TODOS los picks publicables de un partido, no solo dos.

            Devolver varios permite que, si el mejor mercado ya llego a su tope de
            diversidad, el partido aporte su segunda mejor jugada en vez de quedarse
            fuera. Antes solo se ofrecia una y el partido se perdia.
            """
            _cands = []
            for _mk, _vb in (_p.get("value_bets") or {}).items():
                if not _vb:
                    continue
                if _mk.startswith("cards_"):
                    continue   # tarjetas FUERA: mercado volatil, no se puede prever
                if _mk in ("btts_si", "btts_no"):
                    # BTTS/Ambos Marcan = 50% historico, sin ventaja -> NUNCA se publica.
                    # Este bloque NO pasa por clasificar_tiers (que ya lo filtra), asi que
                    # necesita su propio corte. Sin esto, el mercado se sigue publicando.
                    continue
                _pr = float(_vb.get("pinn_prob") or 0)
                _cu = float(_vb.get("cuota") or 0)
                _e  = _vb.get("ev_pinn")
                _e  = _e if _e is not None else 0.0
                # Piso 1.45: este bloque NO pasa por clasificar_tiers, asi que hay que
                # repetirle el piso aqui (mismo hueco por el que se colo el BTTS).
                # Debajo de 1.45 el breakeven (>69%) supera el techo historico del motor.
                if _pr < 40 or _cu < 1.45 or _cu > 3.0:
                    continue
                _cands.append((_mk, _vb, _pr, _cu, _e))
            _out = []
            # SEGURO: mayor probabilidad (banca; cuota <=1.95, EV no muy negativo).
            # Nunca corners como SEGURO (mercado menos predecible) -> solo mercados solidos.
            for c in _cands:
                if c[2] >= 58 and c[3] <= 1.95 and c[4] >= -2 and not c[0].startswith("corners_"):
                    _out.append((c, "seguro", 3))
            # RECOMENDADO: mejor valor real (EV>=1), cuota con recorrido
            for c in _cands:
                if c[4] >= 1 and c[2] >= 48 and 1.55 <= c[3] <= 2.80:
                    _out.append((c, "alto_valor", 2))
            return _out
        _mund_list = []
        # ── PASO 1: REVISAR TODOS los eventos y juntar candidatos en UN pool ──
        _pool = []
        for _p in reporte.get("predicciones", []):
            if _p.get("confiable") is False:
                continue
            if "soccer" not in str(_p.get("liga_code", "")).lower():
                continue   # solo futbol (excluye NHL/MLB/balonmano)
            # Liga en OBSERVACIÓN (paper trading): NO se publica. Este bloque no
            # pasa por clasificar_tiers, así que necesita su propio filtro (misma
            # lección que el escape de BTTS).
            try:
                from motor import LIGAS_EN_OBSERVACION as _OBS
            except Exception:
                _OBS = set()
            if str(_p.get("liga_code", "")) in _OBS:
                continue
            if not _p.get("cuotas_reales"):
                continue
            if (_p.get("fecha_evento") or _hoy_cot().isoformat()) != _hoy_cot().isoformat():
                continue
            try:  # descartar si el partido ya empezo (COT)
                _hh, _mm = (_p.get("hora", "00:00")).split(":")
                _coth = (int(_hh) - 5 + 24) % 24
                _ah = datetime.now(timezone.utc).replace(tzinfo=None)
                if (((_ah.hour - 5) % 24) * 60 + _ah.minute) >= _coth * 60 + int(_mm):
                    continue
            except Exception:
                pass
            _part = f"{_p['local']} vs {_p['visitante']}"
            _hcot = _hora_cot(_p.get("hora", "00:00"))
            _fev  = _p.get("fecha_evento") or _hoy_cot().isoformat()
            for _et, _tier, _stk in _candidatos(_p):   # TODOS los publicables de este partido
                # CALIDAD global = EV + probabilidad + empujon al seguro (la banca)
                _cal = (_et[4] or 0) + _et[2] / 100.0 + (0.4 if _tier == "seguro" else 0.0)
                _pool.append((_cal, _part, _p.get("liga", ""), _et, _tier, _stk, _hcot, _fev))
        # ── PASO 2: RANKEAR por calidad y publicar los MEJORES, VARIADOS ──
        #   - max 2 veces el mismo mercado exacto en todo el dia
        #   - max 3 veces la misma FAMILIA de mercado (goles, resultado, corners...)
        #     Sin esto, "Over 1.5" + "Under 3.5" + "Under 2.5" pasaban como si fueran
        #     tres mercados distintos y el dia entero era la misma apuesta.
        #   - max 1 pick por familia EN EL MISMO PARTIDO (nada de Over 1.5 y Under 3.5 juntos)
        #   - max 2 picks por partido · tope 12 picks (calidad > cantidad)
        _pool.sort(key=lambda x: -x[0])
        _usados = {}
        _por_fam = {}
        _fam_part = set()
        _por_part = {}
        for _cal, _part, _lg, _et, _tier, _stk, _hcot, _fev in _pool:
            _mk2, _vb2 = _et[0], _et[1]
            _fam = _familia(_mk2)
            if _usados.get(_mk2, 0) >= 2:
                continue
            if _por_fam.get(_fam, 0) >= 3:
                continue
            if (_part, _fam) in _fam_part:
                continue
            if _por_part.get(_part, 0) >= 2:
                continue
            _agregar_a_datos_js(
                _part, _lg, _nombre(_mk2, _vb2), str(_vb2.get("cuota")),
                _hcot, round(_vb2.get("ev_pinn") or 0), fecha_evento=_fev,
                tier=_tier, stake_pct=_stk, prob=round(_vb2.get("pinn_prob") or 0))
            _usados[_mk2] = _usados.get(_mk2, 0) + 1
            _por_fam[_fam] = _por_fam.get(_fam, 0) + 1
            _fam_part.add((_part, _fam))
            _por_part[_part] = _por_part.get(_part, 0) + 1
            _mund_list.append(f"{_part} — {_vb2.get('mercado_nombre', _mk2)} ({_tier})")
            _mundial_publicados += 1
            LOG.info(f"datos.js [{_tier}]: {_part} | {_vb2.get('mercado_nombre', _mk2)} @{_vb2.get('cuota')}")
            if _mundial_publicados >= 12:
                break
        if _mundial_publicados:
            _rd = os.path.join(BASE_DIR, "..")
            def _gm(*a):
                return subprocess.run(["git", *a], cwd=_rd, capture_output=True, text=True)
            _gm("rebase", "--abort")
            _gm("add", "datos.js", "index.html")
            _cm = _gm("commit", "-m", f"auto: picks por partido {_hoy_cot().isoformat()}")
            if "nothing to commit" not in (_cm.stdout + _cm.stderr):
                for _i in range(3):
                    if _gm("push", "origin", "main").returncode == 0:
                        break
                    if _gm("pull", "--rebase", "--autostash", "origin", "main").returncode != 0:
                        _gm("rebase", "--abort")
                        break
            LOG.info(f"Mundial: {_mundial_publicados} pick(s) publicados a la web")
            try:
                from telegram_alertas import enviar_aviso_yamid
                enviar_aviso_yamid("🌍 <b>Picks de hoy publicados (seguro + recomendado)</b>\n\n"
                                   + "\n".join(f"• {x}" for x in _mund_list)
                                   + "\n\n✅ sharpiq.co actualizado")
            except Exception:
                pass
    except Exception as _eM:
        LOG.error(f"Bloque Mundial error (NO afecta los tiers): {_eM}")

    # Tarjetas FUERA tambien del VIP de Telegram (mercado volatil, decision de producto)
    for _k in ("seguro", "principal", "alto_valor"):
        _t = tiers.get(_k)
        if _t and "tarjeta" in str(_t.get("mercado_nombre", "")).lower():
            tiers[_k] = None
    if tiers.get("extra"):
        tiers["extra"] = [x for x in tiers["extra"]
                          if "tarjeta" not in str(x.get("mercado_nombre", "")).lower()]

    tiene_alguno = any(tiers.get(k) for k in ("seguro", "principal", "alto_valor"))
    if not tiene_alguno and not _mundial_publicados:
        # Solo avisar a Yamid UNA vez al día, no en cada turno
        _sin_picks_sent = os.path.join(BASE_DIR_AP, "logs", f"sin_picks_{_hoy_cot().isoformat()}.sent")
        if not os.path.exists(_sin_picks_sent):
            try:
                from telegram_alertas import enviar_alerta_servicio, enviar_mensaje, get_chat_id
                from config import TELEGRAM_FREE_ID
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
                    enviar_mensaje(_msg_sin, chat_id=get_chat_id())      # VIP
                    enviar_mensaje(_msg_sin, chat_id=TELEGRAM_FREE_ID)   # Free: cierra el saludo de la manana
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
        enviar_tiers_vip(tiers["seguro"], tiers["principal"], tiers["alto_valor"], extras=tiers.get("extra"))
        LOG.info("Tiers VIP enviados a Telegram")
        # Aviso de SERVICIO al canal Alertas (sin revelar los picks, eso es perk VIP)
        try:
            from telegram_alertas import enviar_alerta_servicio
            _n = len([x for x in (tiers.get("seguro"), tiers.get("principal"), tiers.get("alto_valor")) if x]) + len(tiers.get("extra") or [])
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
    _items = [(_k, tiers.get(_k)) for _k in ("seguro", "principal", "alto_valor")]
    _items += [(_t.get("tier", "principal"), _t) for _t in (tiers.get("extra") or [])]
    for k, t in _items:
        if not t:
            continue
        # El futbol lo publica el bloque de 2 picks por partido (fuente unica) ->
        # aqui solo van los NO-futbol (NHL/MLB/etc), para no duplicar picks en la web.
        if "soccer" in str(t.get("pred", {}).get("liga_code", "")).lower():
            continue
        pred      = t["pred"]
        partido   = f"{pred['local']} vs {pred['visitante']}"
        liga      = pred.get("liga", "")
        hora_cot  = _hora_cot(pred.get("hora", "00:00"))
        ev_val    = round(t.get("ev_pinn", t.get("ev", 0)) or 0)
        fecha_ev  = pred.get("fecha_evento") or pred.get("fecha") or None
        # Kelly dinámico — si no hay kelly_pct cae al tope del tier (seguro/principal=3%, alto_valor=2%)
        stake_pct = t.get("kelly_pct") or _STAKE_PCT.get(k, 3)
        prob_modelo = round(t.get("pinn_prob") or t.get("prob") or 0)
        _agregar_a_datos_js(partido, liga, t["mercado_nombre"], str(t["cuota"]),
                            hora_cot, ev_val, fecha_evento=fecha_ev,
                            tier=k, stake_pct=stake_pct, prob=prob_modelo)
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
                      f"auto: picks {_hoy_cot().isoformat()} — {picks_str}")
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
            pull = _git("pull", "--rebase", "--autostash", "origin", "main")
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
                    _hoy_cot().isoformat(), "apertura",
                    pred.get("cuotas", {})
                )
                # Registrar pick en picks_clv para tracking de CLV
                guardar_picks_clv(
                    fixture_id,
                    pred["local"], pred["visitante"],
                    _hoy_cot().isoformat(),
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
    # ── "Analisis del Dia": regenerar (auto, cada corrida) + publicar a la web ──
    # AISLADO: si algo revienta aqui, NO afecta la publicacion de picks (ya hecha).
    try:
        import sys as _sys, subprocess as _sp
        _eng = os.path.dirname(os.path.abspath(__file__))
        _rd  = os.path.join(_eng, "..")
        _sp.run([_sys.executable, "generar_analisis.py"], cwd=_eng,
                capture_output=True, text=True, timeout=120)
        # Jornada del Mundial con el MODELO (NO depende de The Odds API): si hay
        # partidos del Mundial, SOBREESCRIBE ANALISIS_DIA con la jornada (banderas
        # + mercados profundos). Si no hay partidos, deja intacto lo de generar_analisis.
        # Esto evita que el motor "borre" la jornada cuando no hay picks EV (Odds API caida).
        _sp.run([_sys.executable, "predecir_jornada.py"], cwd=_eng,
                capture_output=True, text=True, timeout=300)
        def _gA(*a):
            return _sp.run(["git", *a], cwd=_rd, capture_output=True, text=True)
        _gA("add", "datos.js", "index.html", "props_jugadores.json")
        _cmA = _gA("commit", "-m", "auto: analisis del dia")
        if "nothing to commit" not in (_cmA.stdout + _cmA.stderr):
            for _iA in range(3):
                if _gA("push", "origin", "main").returncode == 0:
                    LOG.info("Analisis del Dia publicado a la web")
                    break
                if _gA("pull", "--rebase", "--autostash", "origin", "main").returncode != 0:
                    _gA("rebase", "--abort"); break
    except Exception as _eA:
        LOG.error(f"Analisis del Dia (no afecta picks): {_eA}")
