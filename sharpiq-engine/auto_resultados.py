# -*- coding: utf-8 -*-
"""
SharpIQ — Auto Resultados
Detecta partidos publicados que ya terminaron, evalúa la predicción
y actualiza datos.js automáticamente con win/loss + push a GitHub.
"""
import os, sys, re, json, subprocess
from datetime import date, timedelta

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from config import APIFOOTBALL_KEY
from motor import _apifb, LIGAS_APIFB

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

def mover_a_historial(texto, evento, resultado):
    """Quita el evento de PROXIMOS_EVENTOS y lo agrega al inicio de HISTORIAL."""
    # Construir el bloque del evento para buscarlo y eliminarlo
    # Buscamos el bloque que contenga el partido exacto
    patron_bloque = r'\{\s*' + ''.join(
        rf'\s*{k}\s*:\s*"{re.escape(v)}"\s*,' for k, v in evento.items() if k != 'status'
    )
    # Búsqueda más simple: por el campo 'partido'
    partido_esc = re.escape(evento['partido'])
    # Eliminar el bloque completo del evento de PROXIMOS_EVENTOS
    patron = r'\s*\{[^}]*partido\s*:\s*"' + partido_esc + r'"[^}]*\},?'
    texto_nuevo = re.sub(patron, '', texto, count=1)

    # Construir entrada para HISTORIAL
    tier_str      = f'\n    tier:       "{evento["tier"]}",'      if evento.get("tier")      else ""
    stake_pct_str = f'\n    stake_pct:  "{evento["stake_pct"]}",'  if evento.get("stake_pct") else ""
    nueva_entrada = f'''  {{
    fecha:      "{evento.get('fecha', date.today().strftime('%d/%m/%y'))}",
    partido:    "{evento['partido']}",
    liga:       "{evento['liga']}",
    prediccion: "{evento['prediccion']}",
    cuota:      "{evento['cuota']}",
    resultado:  "{resultado}"{tier_str}{stake_pct_str}
  }},'''

    # Insertar al inicio del historial
    texto_nuevo = re.sub(
        r'(const\s+PREDICCIONES_HISTORIAL\s*=\s*\[)',
        r'\1\n' + nueva_entrada,
        texto_nuevo
    )
    return texto_nuevo


# ── MAIN ─────────────────────────────────────────────────────────

def correr():
    print("\n SharpIQ — Auto Resultados")

    texto = leer_datos()
    proximos = _extraer_array(texto, 'PROXIMOS_EVENTOS')

    if not proximos:
        print("  Sin eventos pendientes en datos.js")
        return 0

    print(f"  Eventos pendientes: {len(proximos)}")

    # Obtener partidos finalizados de hoy y ayer
    fechas = [date.today().isoformat(), (date.today() - timedelta(days=1)).isoformat()]
    fixtures_ft = []
    for fecha in fechas:
        data = _apifb("fixtures", {"date": fecha})
        if data and data.get("response"):
            for f in data["response"]:
                if f["fixture"]["status"]["short"] == "FT":
                    fixtures_ft.append(f)

    print(f"  Partidos FT encontrados en API: {len(fixtures_ft)}")

    actualizados = 0
    for evento in proximos:
        partido = evento.get('partido', '')
        partes  = partido.split(' vs ')
        if len(partes) != 2:
            continue
        local_js, visita_js = partes[0].strip(), partes[1].strip()

        fixture = buscar_fixture(local_js, visita_js, fixtures_ft)
        if not fixture:
            print(f"  ⏳ Sin resultado aún: {partido}")
            continue

        gl = fixture["score"]["fulltime"]["home"] or 0
        gv = fixture["score"]["fulltime"]["away"] or 0
        resultado = evaluar(evento.get('prediccion', ''), gl, gv, local_js, visita_js)

        emoji = "✅" if resultado == 'win' else "❌"
        print(f"  {emoji} {partido} | {gl}-{gv} | {evento.get('prediccion','')} → {resultado.upper()}")

        texto = mover_a_historial(texto, evento, resultado)
        actualizados += 1

        # Registrar resultado en PostgreSQL (CLV tracking)
        try:
            from db_clv import actualizar_resultado as _db_resultado
            mercado_key = _pred_to_mercado_key(evento.get('prediccion', ''))
            _db_resultado(partido, mercado_key, resultado)
        except Exception as _dbe:
            print(f"  DB CLV resultado: {_dbe}")

        # Guardar snapshot de cierre y calcular CLV
        clv_texto = ""
        try:
            from motor import buscar_cuotas_partido, LIGAS_ODDS
            from database import inicializar, guardar_snapshot, get_movimiento
            inicializar()
            fid = fixture.get("fixture", {}).get("id")
            liga_id = str(fixture.get("league", {}).get("id", ""))
            sport_key = LIGAS_ODDS.get(liga_id)
            if fid and sport_key:
                cuotas_cierre = buscar_cuotas_partido(local_js, visita_js, sport_key)
                if cuotas_cierre:
                    guardar_snapshot(fid, local_js, visita_js,
                                     date.today().isoformat(), "tarde", cuotas_cierre)
                    mov = get_movimiento(fid)
                    if mov and mov.get("mercados"):
                        mercados = mov["mercados"]
                        lineas_clv = []
                        for m, datos in mercados.items():
                            pct = datos.get("cambio_pct", 0)
                            if abs(pct) >= 3:
                                dir = "▼" if pct < 0 else "▲"
                                lineas_clv.append(f"{m}: {datos['apertura']} → {datos['actual']} ({dir}{abs(pct)}%)")
                        if lineas_clv:
                            clv_texto = "\n📊 <b>CLV:</b> " + " | ".join(lineas_clv)
                            print(f"  CLV: {' | '.join(lineas_clv)}")
        except Exception as clv_e:
            print(f"  CLV error: {clv_e}")

        # Notificar resultado — free + VIP
        try:
            from telegram_alertas import enviar_resultado_free, enviar_resultado_vip, enviar_aviso_yamid
            resultado_texto = f"WIN ✅  {gl}-{gv}" if resultado == 'win' else f"LOSS ❌  {gl}-{gv}"
            enviar_resultado_free(partido, resultado_texto, emoji)
            enviar_resultado_vip(partido, resultado_texto, emoji)
            # Reporte CLV privado a Yamid
            if clv_texto:
                enviar_aviso_yamid(f"📈 CLV {partido}\n{resultado_texto}{clv_texto}")
        except Exception as te:
            print(f"  Telegram resultado error: {te}")

    if actualizados > 0:
        escribir_datos(texto)
        print(f"\n  datos.js actualizado ({actualizados} resultado/s)")

        # Git push automático
        repo_dir = os.path.join(BASE_DIR, "..")
        try:
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=repo_dir, capture_output=True)
            subprocess.run(["git", "add", "datos.js"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m",
                f"auto: resultados actualizados ({date.today().isoformat()})"],
                cwd=repo_dir, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, check=True)
            print("  GitHub actualizado ✓")
        except subprocess.CalledProcessError as e:
            print(f"  Git error: {e}")
    else:
        print("  Sin nuevos resultados disponibles")

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
        print(f"  ROI {roi['mes']}: {roi['roi_pct']:+.1f}% | {ganancia_fmt} COP")
    except Exception as e:
        print(f"  ROI telegram error: {e}")


if __name__ == "__main__":
    correr()
    # Enviar resumen ROI los lunes
    if date.today().weekday() == 0:
        enviar_resumen_roi_semanal()
