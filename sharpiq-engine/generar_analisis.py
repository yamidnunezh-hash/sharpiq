# -*- coding: utf-8 -*-
"""Genera el 'Analisis del Dia' (notas auto-escritas por partido), VARIADAS
(elige el angulo segun los datos + rota vocabulario), y lo inyecta como
`const ANALISIS_DIA = [...]` en datos.js + index.html. Cero LLM."""
import json, os, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _pick(lst, i): return lst[i % len(lst)]
TRAD = {
 'Mexico':'México','South Korea':'Corea del Sur','Korea Republic':'Corea del Sur',
 'USA':'Estados Unidos','United States':'Estados Unidos','Morocco':'Marruecos',
 'Scotland':'Escocia','South Africa':'Sudáfrica','Czech Republic':'República Checa',
 'Czechia':'República Checa','Bosnia & Herzegovina':'Bosnia y Herzegovina',
 'Switzerland':'Suiza','Canada':'Canadá','Qatar':'Catar','England':'Inglaterra',
 'Croatia':'Croacia','France':'Francia','DR Congo':'RD Congo','Congo DR':'RD Congo',
 'Algeria':'Argelia','Jordan':'Jordania','Iraq':'Irak','Norway':'Noruega','Iran':'Irán',
 'New Zealand':'Nueva Zelanda','Sweden':'Suecia','Tunisia':'Túnez','Spain':'España',
 'Cape Verde':'Cabo Verde','Belgium':'Bélgica','Egypt':'Egipto','Saudi Arabia':'Arabia Saudita',
 'Panama':'Panamá','Uzbekistan':'Uzbekistán','Brazil':'Brasil','Japan':'Japón',
 'Germany':'Alemania','Italy':'Italia','Netherlands':'Países Bajos','Poland':'Polonia',
 'Denmark':'Dinamarca','Cameroon':'Camerún','Peru':'Perú','Wales':'Gales','Turkey':'Turquía',
 'Greece':'Grecia','Ireland':'Irlanda','Serbia':'Serbia','Ukraine':'Ucrania','Nigeria':'Nigeria',
}
def _trad(n): return TRAD.get((n or '').strip(), n)

import unicodedata as _ud
def _slug(s):
    s = _ud.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def _esc(s): return (s or "").replace("\\", "\\\\").replace('"', '\\"')

def _forma_adj(v, i):
    if v >= 0.7:  return _pick(["llega en gran forma", "atraviesa un gran momento", "viene encendido", "llega lanzado"], i)
    if v >= 0.5:  return _pick(["llega con altibajos", "alterna buenos y malos resultados", "viene irregular", "no termina de despegar"], i)
    return _pick(["atraviesa una mala racha", "llega tocado de confianza", "viene de capa caida", "necesita reaccionar"], i)

def _generar(p, i):
    loc, vis = _trad(p.get('local')), _trad(p.get('visitante'))
    liga = p.get('liga', ''); pr = p.get('probabilidades') or {}
    fl, fv = p.get('forma_local', {}) or {}, p.get('forma_visita', {}) or {}
    pp = p.get('prediccion_principal', {}) or {}
    vl = pr.get('victoria_local') or 0; vv = pr.get('victoria_visita') or 0
    o25 = pr.get('over25'); u25 = pr.get('under25')
    atk_l = fl.get('ataque_reciente') or 0; atk_v = fv.get('ataque_reciente') or 0
    flv, fvv = fl.get('forma', 0) or 0, fv.get('forma', 0) or 0
    gap = vl - vv

    # --- clasificar el partido para elegir el ANGULO ---
    if vl >= 60 or vv >= 60:
        fav, otro = (loc, vis) if vl >= vv else (vis, loc)
        favp = max(vl, vv)
        tipo = 'favorito'
    elif (o25 or 0) >= 56:  tipo = 'goleador'
    elif (u25 or 0) >= 56:  tipo = 'defensivo'
    elif abs(flv - fvv) >= 0.25: tipo = 'contraste'
    else: tipo = 'parejo'

    # --- TITULO segun tipo (rotado) ---
    if tipo == 'favorito':
        titulo = _pick([f"{fav} parte con ventaja sobre {otro}", f"{fav}, favorito para imponerse a {otro}", f"{fav} buscara dominar a {otro}"], i)
    elif tipo == 'goleador':
        titulo = _pick([f"{loc} vs {vis} promete goles", f"{loc} y {vis}, un duelo de ataque", f"Se esperan goles en {loc} vs {vis}"], i)
    elif tipo == 'defensivo':
        titulo = _pick([f"{loc} vs {vis}, partido de pocos goles", f"{loc} vs {vis} apunta a ser cerrado", f"Duelo tactico entre {loc} y {vis}"], i)
    elif tipo == 'contraste':
        mejor = loc if flv >= fvv else vis
        titulo = _pick([f"{mejor} llega en mejor momento a su duelo", f"{loc} vs {vis}: dos momentos opuestos", f"El presente sonrie a {mejor}"], i)
    else:
        titulo = _pick([f"{loc} vs {vis}: pronostico abierto", f"{loc} y {vis}, un pulso parejo", f"{loc} vs {vis}, a cara o cruz"], i)

    # --- CUERPO: 1a frase segun tipo ---
    if tipo == 'favorito':
        c = _pick([f"El modelo ve a {fav} como claro favorito ({favp}%) en este cruce.",
                   f"Los numeros respaldan a {fav}, con un {favp}% de probabilidad de ganar.",
                   f"{fav} llega como el equipo a batir, con {favp}% segun el modelo."], i)
    elif tipo == 'goleador':
        c = _pick([f"Todo apunta a un partido abierto: el modelo da {o25}% de Over 2.5 goles.",
                   f"Se espera espectaculo ofensivo, con un {o25}% de probabilidad de superar los 2.5 goles.",
                   f"Las defensas podrian sufrir: {o25}% de chance de Over 2.5."], i)
    elif tipo == 'defensivo':
        c = _pick([f"Pinta cerrado y de pocos goles: {u25}% de probabilidad de Under 2.5.",
                   f"El modelo proyecta un duelo tactico, con {u25}% de Under 2.5 goles.",
                   f"No se esperan muchos goles: {u25}% de chance de quedar bajo los 2.5."], i)
    elif tipo == 'contraste':
        mejor = loc if flv >= fvv else vis
        c = _pick([f"El contraste de momento es claro: {mejor} {_forma_adj(max(flv,fvv), i)}, mientras su rival {_forma_adj(min(flv,fvv), i+1)}.",
                   f"{mejor} {_forma_adj(max(flv,fvv), i)} y parte con el animo a favor."], i)
    else:
        c = _pick([f"Partido parejo segun el modelo: {vl}% local, {pr.get('empate',0)}% empate, {vv}% visitante.",
                   f"Pocas certezas: el modelo reparte las opciones casi a partes iguales.",
                   f"Duelo de pronostico reservado, con ligero {('favoritismo local' if vl>=vv else 'favoritismo visitante')}."], i)

    # --- 2a frase: un DATO de forma/ataque (varia cual destaca) ---
    if atk_l and atk_l >= atk_v and atk_l >= 1.8:
        c += " " + _pick([f"{loc} {_forma_adj(flv,i)} y promedia {atk_l} goles por partido.",
                          f"En ataque, {loc} viene fino: {atk_l} goles de media."], i)
    elif atk_v and atk_v >= 1.8:
        c += " " + _pick([f"Ojo con {vis}, que {_forma_adj(fvv,i)} y promedia {atk_v} goles.",
                          f"{vis} llega goleador, con {atk_v} tantos por encuentro."], i)
    else:
        c += " " + _pick([f"Ninguno de los dos llega especialmente fino en ataque.",
                          f"Ambos vienen con cifras goleadoras discretas."], i)

    # --- CUERPO LARGO (para la pagina de detalle): suma el panorama 1X2 + goles ---
    ve = pr.get('empate') or 0
    c_largo = c + " " + _pick([
        f"En el 1X2, el modelo da {vl}% a {loc}, {ve}% al empate y {vv}% a {vis}.",
        f"La probabilidad de resultado queda asi: {vl}% local, {ve}% empate, {vv}% visitante.",
    ], i)
    if o25 is not None:
        c_largo += " " + _pick([
            f"De cara al gol, hay un {o25}% de chance de superar los 2.5 tantos.",
            f"En goles, el modelo proyecta un {o25}% de Over 2.5.",
        ], i)

    return {"partido": f"{loc} vs {vis}", "liga": liga, "titulo": titulo,
            "cuerpo": c, "cuerpo_largo": c_largo, "hora": p.get('hora', ''),
            "slug": _slug(f"{loc}-vs-{vis}"),
            "fL": flv, "aL": atk_l, "dL": fl.get('defensa_reciente') or 0,
            "fV": fvv, "aV": atk_v, "dV": fv.get('defensa_reciente') or 0,
            "vl": vl, "ve": ve, "vv": vv, "o25": o25 or 0, "u25": u25 or 0}

def generar_items(preds):
    out = []; i = 0
    for p in preds:
        if 'soccer' not in str(p.get('liga_code', '')).lower(): continue
        if not (p.get('probabilidades')): continue
        out.append(_generar(p, i)); i += 1
    return out

def _to_js(items):
    filas = ["  { " + ", ".join(f'{k}: "{_esc(str(v))}"' for k, v in it.items()) + " }" for it in items]
    return "const ANALISIS_DIA = [\n" + ",\n".join(filas) + "\n];"

def inyectar(js):
    for path in (os.path.join(BASE, 'datos.js'), os.path.join(BASE, 'index.html')):
        s = open(path, encoding='utf-8', errors='replace').read()
        if 'const ANALISIS_DIA' in s:
            s = re.sub(r'const ANALISIS_DIA = \[.*?\];', lambda m: js, s, count=1, flags=re.S)
        else:
            s = re.sub(r'(const PREDICCIONES_HISTORIAL\s*=\s*\[.*?\];)', lambda m: m.group(1) + "\n" + js, s, count=1, flags=re.S)
        open(path, 'w', encoding='utf-8').write(s)

if __name__ == '__main__':
    d = json.load(open(os.path.join(BASE, 'predicciones.json'), encoding='utf-8'))
    items = generar_items(d.get('predicciones', []))[:8]
    inyectar(_to_js(items))
    print(f"ANALISIS_DIA: {len(items)} notas VARIADAS inyectadas")
    for it in items[:6]: print("\n• " + it['titulo'] + "\n  " + it['cuerpo'])
