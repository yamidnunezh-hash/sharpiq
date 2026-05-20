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

def evaluar(prediccion, gl, gv):
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
    nueva_entrada = f'''  {{
    fecha:      "{evento.get('fecha', date.today().strftime('%d/%m/%y'))}",
    partido:    "{evento['partido']}",
    liga:       "{evento['liga']}",
    prediccion: "{evento['prediccion']}",
    cuota:      "{evento['cuota']}",
    resultado:  "{resultado}"
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
        resultado = evaluar(evento.get('prediccion', ''), gl, gv)

        emoji = "✅" if resultado == 'win' else "❌"
        print(f"  {emoji} {partido} | {gl}-{gv} | {evento.get('prediccion','')} → {resultado.upper()}")

        texto = mover_a_historial(texto, evento, resultado)
        actualizados += 1

        # Notificar resultado al canal free
        try:
            from telegram_alertas import enviar_resultado_free
            resultado_texto = f"WIN ✅  {gl}-{gv}" if resultado == 'win' else f"LOSS ❌  {gl}-{gv}"
            enviar_resultado_free(partido, resultado_texto, emoji)
        except Exception as te:
            print(f"  Telegram resultado error: {te}")

    if actualizados > 0:
        escribir_datos(texto)
        print(f"\n  datos.js actualizado ({actualizados} resultado/s)")

        # Git push automático
        repo_dir = os.path.join(BASE_DIR, "..")
        try:
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


if __name__ == "__main__":
    correr()
