# -*- coding: utf-8 -*-
"""Genera el 'Análisis del Día' (notas auto-escritas por partido) y lo inyecta
como `const ANALISIS_DIA = [...]` en datos.js + index.html. Lo corre el motor
tras publicar; tambien se puede correr a mano. Cero LLM: plantillas + datos."""
import json, os, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _forma(f):
    v = f.get('forma', 0) or 0
    return "llega en gran forma" if v >= 0.7 else ("viene en forma regular" if v >= 0.5 else "atraviesa una racha irregular")

def _esc(s):
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')

def generar_items(preds):
    items = []
    for p in preds:
        if 'soccer' not in str(p.get('liga_code', '')).lower():
            continue
        pr = p.get('probabilidades') or {}
        if not pr:
            continue
        loc, vis = p.get('local'), p.get('visitante')
        fl, fv = p.get('forma_local', {}) or {}, p.get('forma_visita', {}) or {}
        pp = p.get('prediccion_principal', {}) or {}
        vl = pr.get('victoria_local'); o25 = pr.get('over25')
        atk_l = fl.get('ataque_reciente'); atk_v = fv.get('ataque_reciente')
        # titulo
        fav = loc if (vl or 0) >= 50 else (vis if (pr.get('victoria_visita') or 0) >= 50 else None)
        titulo = (f"{fav} parte como favorito ante " + (vis if fav == loc else loc)) if fav else f"{loc} vs {vis}: duelo parejo"
        # cuerpo
        c = f"{loc} {_forma(fl)}"
        if atk_l: c += f", con un ataque de {atk_l} goles por partido"
        c += f". {vis} {_forma(fv)}"
        if atk_v: c += f" (promedia {atk_v})"
        c += "."
        if vl is not None:
            c += f" El modelo SharpIQ proyecta {vl}% de victoria local"
            if o25 is not None: c += f" y {o25}% de Over 2.5 goles"
            c += "."
        items.append({
            "partido": f"{loc} vs {vis}", "liga": p.get('liga', ''),
            "titulo": titulo, "cuerpo": c,
            "pick": pp.get('mercado', ''), "prob": pp.get('prob', ''),
            "hora": p.get('hora', ''),
        })
    return items

def to_js(items):
    filas = []
    for it in items:
        filas.append("  { " + ", ".join(f'{k}: "{_esc(str(v))}"' for k, v in it.items()) + " }")
    return "const ANALISIS_DIA = [\n" + ",\n".join(filas) + "\n];"

def inyectar(js_block):
    for path in (os.path.join(BASE, 'datos.js'), os.path.join(BASE, 'index.html')):
        s = open(path, encoding='utf-8', errors='replace').read()
        if 'const ANALISIS_DIA' in s:
            s = re.sub(r'const ANALISIS_DIA = \[.*?\];', js_block, s, count=1, flags=re.S)
        else:
            # insertar justo despues de PREDICCIONES_HISTORIAL = [...];
            s = re.sub(r'(const PREDICCIONES_HISTORIAL\s*=\s*\[.*?\];)',
                       lambda m: m.group(1) + "\n" + js_block, s, count=1, flags=re.S)
        open(path, 'w', encoding='utf-8').write(s)

if __name__ == '__main__':
    d = json.load(open(os.path.join(BASE, 'predicciones.json'), encoding='utf-8'))
    items = generar_items(d.get('predicciones', []))[:8]
    inyectar(to_js(items))
    print(f"ANALISIS_DIA generado: {len(items)} notas inyectadas en datos.js + index.html")
