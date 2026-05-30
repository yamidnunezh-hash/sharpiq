# -*- coding: utf-8 -*-
"""
SharpIQ — Auto Resultados
Detecta partidos publicados que ya terminaron, evalúa la predicción
y actualiza datos.js automáticamente con win/loss + push a GitHub.
"""
import os, sys, re, json, subprocess, logging
from datetime import date, timedelta

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from config import APIFOOTBALL_KEY
from motor import _apifb, LIGAS_APIFB, LOG

# Mapeo predicción (display) → clave de mercado en DB
_PRED_TO_MERCADO = {
    "victoria local":     "victoria_local",
    "victoria visitante": "victoria_visita",
    "empate":             "empate",
    "over 2.5":           "over25",
    "under 2.5":          "under25",
    "over 1.5":           "over15",
    "under 1.5":          "under15",
    "over 3.5":           "over35",
    "under 3.5":          "under35",
    "ambos marcan":       "btts_si",
    "tarjetas over":      "btts_si",  # fallback genérico
    "corners over":       "btts_si",
}

def _pred_to_mercado_key(prediccion):
    p = prediccion.lower()
    for k, v in _PRED_TO_MERCADO.items():
        if k in p:
            return v
    return prediccion

DATOS_PATH = os.path.join(BASE_DIR, "..", "datos.js")


# ── PARSER DE datos.js ──────────────────────────────────────────

def _extraer_array(texto, nombre):
    """Extrae los objetos de un array JS por nombre de constante."""
    patron = rf'const\s+{nombre}\s*=\s*\[(.*?)\];'
    m = re.search(patron, texto, re.DOTALL)
    if not m:
        return []
    contenido = m.group(1).strip()
    if not contenido:
        return []
    # Cada objeto entre { }
    objetos = re.findall(r'\{[^}]+\}', contenido, re.DOTALL)
    resultado = []
    for obj in objetos:
        item = {}
        for campo in re.finditer(r'(\w+)\s*:\s*"([^"]*)"', obj):
            item[campo.group(1)] = campo.group(2)
        if item:
            resultado.append(item)
    return resultado

def leer_datos():
    with open(DATOS_PATH, encoding='utf-8') as f:
        return f.read()

def escribir_datos(texto):
    with open(DATOS_PATH, 'w', encoding='utf-8') as f:
        f.write(texto)


# ── NORMALIZACIÓN DE NOMBRES ─────────────────────────────────────

_STOPWORDS = {'fc', 'cf', 'cd', 'sc', 'ac', 'as', 'sk', 'bv', 'sv',
              'de', 'del', 'los', 'las', 'el', 'la', 'the', 'united',
              'city', 'sport', 'club', 'atletico', 'atletico'}

def _normalizar(nombre):
    n = nombre.lower()
    n = re.sub(r'[áàä]', 'a', n)
    n = re.sub(r'[éèë]', 'e', n)
    n = re.sub(r'[íìï]', 'i', n)
    n = re.sub(r'[óòö]', 'o', n)
    n = re.sub(r'[úùü]', 'u', n)
    n = re.sub(r'[^a-z0-9 ]', '', n)
    palabras = [p for p in n.split() if p not in _STOPWORDS]
    return set(palabras)

def _similitud(a, b):
    sa, sb = _normalizar(a), _normalizar(b)
    if not sa or not sb:
        return 0
    interseccion = len(sa & sb)
    return interseccion / max(len(sa), len(sb))

def buscar_fixture(local_js, visita_js, fixtures_api):
    """Encuentra el fixture de la API que mejor coincide con los nombres del JS."""
    mejor, mejor_score = None, 0.4  # umbral mínimo
    for f in fixtures_api:
        local_api   = f['teams']['home']['name']
        visita_api  = f['teams']['away']['name']
        score = (_similitud(local_js, local_api) + _similitud(visita_js, visita_api)) / 2
        if score > mejor_score:
            mejor_score = score
            mejor = f
    return mejor


# ── EVALUADOR DE PREDICCIONES ────────────────────────────────────

def evaluar(prediccion, gl, gv, local="", visitante=""):
    """Devuelve 'win', 'loss' según la predicción y marcador real."""
    p = prediccion.lower()
    total = gl + gv

    if 'under25' in p or 'under 2.5' in p:
        return 'win' if total <= 2 else 'loss'
    if 'over25'  in p or 'over 2.5'  in p:
        return 'win' if total >= 3 else 'loss'
    if 'under35' in p or 'under 3.5' in p:
        return 'win' if total <= 3 else 'loss'
    if 'over35'  in p or 'over 3.5'  in p:
        return 'win' if total >= 4 else 'loss'
    if 'under15' in p or 'under 1.5' in p:
        return 'win' if total <= 1 else 'loss'
    if 'over15'  in p or 'over 1.5'  in p:
        return 'win' if total >= 2 else 'loss'
    if 'over325' in p or 'over 3.25' in p:
        return 'win' if total >= 4 else 'loss'
    if 'under325' in p or 'under 3.25' in p:
        return 'win' if total <= 3 else 'loss'
    if 'over175' in p or 'over 1.75' in p:
        return 'win' if total >= 2 else 'loss'
    if 'under175' in p or 'under 1.75' in p:
        return 'win' if total <= 1 else 'loss'
    if 'btts' in p or 'ambos marcan' in p:
        return 'win' if gl > 0 and gv > 0 else 'loss'
    if 'victoria local' in p or '(1)' in p:
        return 'win' if gl > gv else 'loss'
    if 'victoria visitante' in p or '(2)' in p:
        return 'win' if gv > gl else 'loss'
    if 'empate' in p or '(x)' in p:
        return 'win' if gl == gv else 'loss'
    if 'doble_1x' in p or '1x' in p:
        return 'win' if gl >= gv else 'loss'
    if 'doble_x2' in p or 'x2' in p:
        return 'win' if gv >= gl else 'loss'
    if 'draw no bet' in p or 'dnb' in p:
        if 'local' in p:
            return 'win' if gl > gv else ('push' if gl == gv else 'loss')
        if 'visitante' in p or 'visita' in p:
            return 'win' if gv > gl else ('push' if gl == gv else 'loss')

    # "Gana [Equipo]" o bare team name — picks de NBA/NHL/MLB/NFL/fútbol
    # Limpiar sufijos como " — EV +24%" antes de comparar
    p_clean = p.split(' —')[0].split(' ev')[0].strip()
    team_pred = p_clean.replace('gana ', '').strip()
    if team_pred and (local or visitante):
        if local and (team_pred in local.lower() or local.lower() in team_pred):
            return 'win' if gl > gv else 'loss'
        if visitante and (team_pred in visitante.lower() or visitante.lower() in team_pred):
            return 'win' if gv > gl else 'loss'

    print(f"  ⚠ No reconozco predicción: '{prediccion}' — marcada como loss")
    return 'loss'


# ── ACTUALIZAR datos.js ──────────────────────────────────────────

def _actualizar_en_proximos(texto, partido, resultado):
    """
    Actualiza resultado:"pendiente" → win/loss/push en PROXIMOS_EVENTOS (in-place).
    La entrada se mantiene visible en la web con el resultado correcto.
    """
    partido_esc = re.escape(partido)
    # Reemplaza solo el campo resultado del bloque que contiene este partido
    patron = re.compile(
        r'(partido:\s*"' + partido_esc + r'"[^}]*?resultado:\s*")(pendiente)(")',
        re.DOTALL,
    )
    nuevo, n = patron.subn(r'\g<1>' + resultado + r'\g<3>', texto)
    return nuevo, n


def _agregar_a_historial(texto, evento, resultado):
    """
    Añade la entrada al inicio de PREDICCIONES_HISTORIAL si aún no existe.
    Evita duplicados buscando el partido antes de insertar.
    """
    partido_esc = re.escape(evento['partido'])
    if re.search(r'partido:\s*"' + partido_esc + r'"', texto):
        # ya existe en historial (puede estar en PROXIMOS o en HISTORIAL)
        # Verificar si YA está en PREDICCIONES_HISTORIAL específicamente
        hist_match = re.search(
            r'PREDICCIONES_HISTORIAL\s*=\s*\[(.*)',
            texto, re.DOTALL
        )
        if hist_match and partido_esc.replace(r'\ ', ' ') in hist_match.group(1).replace('\\', ''):
            return texto  # ya está en historial, no duplicar

    nueva_entrada = f'''  {{
    fecha:      "{evento.get('fecha', date.today().strftime('%d/%m/%y'))}",
    partido:    "{evento['partido']}",
    liga:       "{evento.get('liga', '')}",
    prediccion: "{evento.get('prediccion', '')}",
    cuota:      "{evento.get('cuota', '')}",
    resultado:  "{resultado}"
  }},'''

    return re.sub(
        r'(const\s+PREDICCIONES_HISTORIAL\s*=\s*\[)',
        r'\1\n' + nueva_entrada,
        texto
    )


# ── MAIN ─────────────────────────────────────────────────────────

def correr():
    LOG.info("=== SharpIQ Auto Resultados START ===")

    texto = leer_datos()
    proximos = _extraer_array(texto, 'PROXIMOS_EVENTOS')

    pendientes = [e for e in proximos if e.get('resultado') == 'pendiente']
    if not pendientes:
        LOG.info("Auto-resultados: no hay picks pendientes")
        return 0

    LOG.info(f"Auto-resultados: {len(pendientes)} picks pendientes")

    # Buscar partidos finalizados en los últimos 3 días (cubre fines de semana)
    fechas = [
        (date.today() - timedelta(days=i)).isoformat()
        for i in range(3)
    ]
    fixtures_ft = []
    for fecha_iso in fechas:
        data = _apifb("fixtures", {"date": fecha_iso})
        if data and data.get("response"):
            for f in data["response"]:
                if f["fixture"]["status"]["short"] in ("FT", "AET", "PEN"):
                    fixtures_ft.append(f)

    LOG.info(f"Partidos FT en API (últimos 3 días): {len(fixtures_ft)}")

    actualizados = 0
    for evento in pendientes:
        partido = evento.get('partido', '')
        partes  = partido.split(' vs ')
        if len(partes) != 2:
            continue
        local_js, visita_js = partes[0].strip(), partes[1].strip()

        fixture = buscar_fixture(local_js, visita_js, fixtures_ft)
        if not fixture:
            LOG.info(f"  Sin resultado aún: {partido}")
            continue

        gl = fixture["score"]["fulltime"]["home"] or 0
        gv = fixture["score"]["fulltime"]["away"] or 0
        resultado = evaluar(evento.get('prediccion', ''), gl, gv, local_js, visita_js)

        emoji = "✅" if resultado == 'win' else ("➖" if resultado == 'push' else "❌")
        LOG.info(f"  {emoji} {partido} [{gl}-{gv}] → {resultado.upper()}")

        # Actualizar in-place en PROXIMOS_EVENTOS (mantiene la entry visible en web)
        texto, n_upd = _actualizar_en_proximos(texto, partido, resultado)
        if not n_upd:
            LOG.warning(f"  No se pudo actualizar resultado en PROXIMOS: {partido}")

        # Agregar al historial si no está ya
        texto = _agregar_a_historial(texto, evento, resultado)
        actualizados += 1

        # Registrar en DB CLV
        try:
            from db_clv import actualizar_resultado as _db_resultado
            mercado_key = _pred_to_mercado_key(evento.get('prediccion', ''))
            _db_resultado(partido, mercado_key, resultado)
        except Exception as _dbe:
            LOG.debug(f"DB CLV resultado: {_dbe}")

        # Snapshot de cierre + cálculo CLV
        clv_texto = ""
        try:
            from motor import LIGAS_ODDS
            from database import inicializar, guardar_snapshot, calcular_clv, actualizar_clv_pick
            from config import ODDS_API_KEY
            import requests as _req
            inicializar()
            fid     = fixture.get("fixture", {}).get("id")
            liga_id = str(fixture.get("league", {}).get("id", ""))
            sport_key = LIGAS_ODDS.get(liga_id)

            if fid and sport_key and ODDS_API_KEY:
                # Pedir cuotas actuales (≈ cierre del mercado)
                _col_map = {
                    "h2h":    {"1": "cuota_1", "X": "cuota_x", "2": "cuota_2"},
                    "totals": {"Over 2.5": "cuota_over25", "Under 2.5": "cuota_under25",
                               "Over 1.5": "cuota_over15", "Under 1.5": "cuota_under15"},
                }
                cuotas_cierre = {}
                try:
                    _r = _req.get(
                        "https://api.the-odds-api.com/v4/sports/{}/odds".format(sport_key),
                        params={"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "h2h,totals",
                                "bookmakers": "pinnacle,betcris"},
                        timeout=10,
                    )
                    if _r.status_code == 200:
                        for ev in _r.json():
                            h = ev.get("home_team", ""); a = ev.get("away_team", "")
                            if local_js.lower()[:8] in h.lower() or h.lower()[:8] in local_js.lower():
                                for bm in ev.get("bookmakers", []):
                                    if bm["key"] == "pinnacle":
                                        for mkt in bm.get("markets", []):
                                            for out in mkt.get("outcomes", []):
                                                nm, pr = out["name"], out["price"]
                                                if mkt["key"] == "h2h":
                                                    if nm == h: cuotas_cierre["1"] = pr
                                                    elif nm == a: cuotas_cierre["2"] = pr
                                                    else: cuotas_cierre["X"] = pr
                                                elif mkt["key"] == "totals":
                                                    if "Over" in nm: cuotas_cierre[f"over{nm.split()[-1].replace('.','').replace('5','5')}"] = pr
                                                    else: cuotas_cierre[f"under{nm.split()[-1].replace('.','').replace('5','5')}"] = pr
                except Exception:
                    pass

                if cuotas_cierre:
                    guardar_snapshot(fid, local_js, visita_js,
                                     date.today().isoformat(), "cierre", cuotas_cierre)

                    # ── CLV tracking PostgreSQL (db_clv): registra la cuota de cierre
                    #    del mercado del pick → calcula CLV (cierre - apertura) sobre la
                    #    fila insertada por db_clv.guardar_pick en auto_publicar.
                    try:
                        from db_clv import actualizar_cierre as _db_cierre
                        # mercado_key (over25/victoria_local/...) → clave en cuotas_cierre
                        _mk_to_cierre = {
                            "victoria_local": "1", "victoria_visita": "2", "empate": "X",
                            "over25": "over25", "under25": "under25",
                            "over15": "over15", "under15": "under15",
                        }
                        _cierre_key = _mk_to_cierre.get(mercado_key, mercado_key)
                        _cuota_cierre = cuotas_cierre.get(_cierre_key)
                        if _cuota_cierre:
                            _db_cierre(partido, mercado_key, float(_cuota_cierre))
                            LOG.info(f"  CLV (PostgreSQL) cierre — {mercado_key} @ {_cuota_cierre}")
                    except Exception as _ce:
                        LOG.debug(f"CLV PostgreSQL actualizar_cierre: {_ce}")

                # Calcular CLV para mercados estándar
                _mk_cols = {"over25": "cuota_over25", "under25": "cuota_under25",
                            "over15": "cuota_over15", "under15": "cuota_under15",
                            "victoria_local": "cuota_1", "victoria_visita": "cuota_2"}
                for mk_key, col in _mk_cols.items():
                    clv = calcular_clv(fid, col)
                    if clv:
                        dir_arrow = "▲" if clv["clv_pct"] > 0 else "▼"
                        linea = f"{mk_key}: {clv['apertura']}→{clv['cierre']} CLV{dir_arrow}{abs(clv['clv_pct'])}%"
                        actualizar_clv_pick(fid, mk_key, clv["cierre"], clv["clv_pct"])
                        clv_texto += linea + " | "

                if clv_texto:
                    clv_texto = clv_texto.rstrip(" | ")
                    LOG.info(f"  CLV: {clv_texto}")
        except Exception as clv_e:
            LOG.debug(f"CLV snapshot: {clv_e}")

        # Notificar en Telegram
        try:
            from telegram_alertas import enviar_resultado_free, enviar_resultado_vip, enviar_aviso_yamid
            resultado_texto = f"WIN ✅  {gl}-{gv}" if resultado == 'win' else (
                f"PUSH ➖  {gl}-{gv}" if resultado == 'push' else f"LOSS ❌  {gl}-{gv}"
            )
            enviar_resultado_free(partido, resultado_texto, emoji)
            enviar_resultado_vip(partido, resultado_texto, emoji)
            if clv_texto:
                enviar_aviso_yamid(f"📈 CLV {partido}\n{resultado_texto}\n📊 {clv_texto}")
        except Exception as te:
            LOG.error(f"Telegram resultado: {te}")

    if actualizados > 0:
        escribir_datos(texto)
        LOG.info(f"datos.js actualizado — {actualizados} resultado/s")

        repo_dir = os.path.join(BASE_DIR, "..")

        def _git(*args):
            return subprocess.run(["git", *args], cwd=repo_dir,
                                  capture_output=True, text=True)
        try:
            # Abortar cualquier rebase a medias de una corrida previa (evita exit 128)
            _git("rebase", "--abort")
            _git("add", "datos.js", "index.html")
            commit = _git("commit", "-m", f"auto: resultados {date.today().isoformat()}")
            sin_cambios = "nothing to commit" in (commit.stdout + commit.stderr)

            pushed = False
            for intento in range(3):
                push = _git("push", "origin", "main")
                if push.returncode == 0:
                    pushed = True
                    break
                pull = _git("pull", "--rebase", "origin", "main")
                if pull.returncode != 0:
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
    else:
        LOG.info("Auto-resultados: sin nuevos resultados disponibles")

    return actualizados


def calcular_roi(datos_texto, bankroll=5_000_000):
    """Calcula ROI del mes actual a partir de PREDICCIONES_HISTORIAL en datos.js."""
    historial = _extraer_array(datos_texto, 'PREDICCIONES_HISTORIAL')
    mes_actual = date.today().strftime('%m/%y')

    picks_mes = [p for p in historial
                 if p.get('resultado') in ('win', 'loss', 'push')
                 and p.get('fecha', '').endswith(mes_actual)]

    if not picks_mes:
        return None

    total_picks  = len(picks_mes)
    wins         = sum(1 for p in picks_mes if p.get('resultado') == 'win')
    losses       = sum(1 for p in picks_mes if p.get('resultado') == 'loss')
    ganancia_net = 0
    total_apostado = 0

    for p in picks_mes:
        pct   = float(p.get('stake_pct') or 3) / 100
        stake = bankroll * pct
        total_apostado += stake
        try:
            cuota = float(p.get('cuota') or 1)
        except (ValueError, TypeError):
            cuota = 1.0
        if p.get('resultado') == 'win':
            ganancia_net += stake * (cuota - 1)
        elif p.get('resultado') == 'loss':
            ganancia_net -= stake

    roi_pct = (ganancia_net / total_apostado * 100) if total_apostado > 0 else 0
    win_rate = (wins / total_picks * 100) if total_picks > 0 else 0

    return {
        "picks":    total_picks,
        "wins":     wins,
        "losses":   losses,
        "win_rate": round(win_rate, 1),
        "apostado": round(total_apostado),
        "ganancia": round(ganancia_net),
        "roi_pct":  round(roi_pct, 1),
        "mes":      mes_actual,
    }


def enviar_resumen_roi_semanal():
    """Envía resumen de ROI semanal a Yamid los lunes."""
    texto = leer_datos()
    roi = calcular_roi(texto)
    if not roi:
        return

    emoji_roi = "🟢" if roi["ganancia"] >= 0 else "🔴"
    ganancia_fmt = f"+${roi['ganancia']:,.0f}" if roi["ganancia"] >= 0 else f"-${abs(roi['ganancia']):,.0f}"

    msg = (
        f"📊 <b>SharpIQ — ROI {roi['mes']}</b>\n\n"
        f"📌 Picks: {roi['picks']} | ✅ {roi['wins']} W / ❌ {roi['losses']} L\n"
        f"🎯 Win Rate: {roi['win_rate']}%\n"
        f"💵 Total apostado: ${roi['apostado']:,.0f} COP\n"
        f"{emoji_roi} Ganancia neta: {ganancia_fmt} COP\n"
        f"📈 ROI: {roi['roi_pct']:+.1f}%\n\n"
        f"<i>Bankroll base: $5.000.000 COP · SharpIQ</i>"
    )
    try:
        from telegram_alertas import enviar_aviso_yamid
        enviar_aviso_yamid(msg)
        LOG.info(f"ROI {roi['mes']}: {roi['roi_pct']:+.1f}% | {ganancia_fmt} COP")
    except Exception as e:
        LOG.error(f"ROI telegram error: {e}")


if __name__ == "__main__":
    correr()
    # Enviar resumen ROI los lunes
    if date.today().weekday() == 0:
        enviar_resumen_roi_semanal()
