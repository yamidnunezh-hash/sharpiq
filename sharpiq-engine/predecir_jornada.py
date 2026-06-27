# -*- coding: utf-8 -*-
"""Predice TODA la jornada del Mundial con el MODELO (Poisson sobre forma real
via API-Football PRO) — SIN depender de The Odds API — y lo monta en la web
(ANALISIS_DIA) reutilizando la maquinaria de generar_analisis.

Uso: python predecir_jornada.py [YYYY-MM-DD ...]   (por defecto hoy+manana COT)
"""
import sys
from datetime import datetime, timedelta
from scipy.stats import poisson
from motor import _apifb
import generar_analisis as ga


def _gfgc(tid, n=8):
    """Promedio de goles a favor/en contra y forma (0-1) de los ultimos n."""
    r = _apifb('fixtures', {'team': tid, 'last': n})
    gf = gc = c = pts = 0
    for fx in (r.get('response') or []):
        gh, gaa = fx['goals']['home'], fx['goals']['away']
        if gh is None:
            continue
        home = fx['teams']['home']['id'] == tid
        a, b = (gh, gaa) if home else (gaa, gh)
        gf += a; gc += b; c += 1
        pts += 3 if a > b else (1 if a == b else 0)
    if not c:
        return 1.2, 1.2, 0.40
    return gf / c, gc / c, round(pts / (3 * c), 3)


def _pct(x):
    return int(round(x * 100))


def _predecir(local_id, visita_id):
    gf_l, gc_l, fo_l = _gfgc(local_id)
    gf_v, gc_v, fo_v = _gfgc(visita_id)
    lam_l = ((gf_l + gc_v) / 2) * 1.05   # leve ventaja local
    lam_v = (gf_v + gc_l) / 2
    pl = pe = pv = o25 = 0.0
    for i in range(8):
        for j in range(8):
            p = poisson.pmf(i, lam_l) * poisson.pmf(j, lam_v)
            if i > j: pl += p
            elif i == j: pe += p
            else: pv += p
            if i + j > 2: o25 += p
    return {
        'vl': _pct(pl), 've': _pct(pe), 'vv': _pct(pv),
        'o25': _pct(o25), 'u25': _pct(1 - o25),
        'gf_l': round(gf_l, 2), 'gc_l': round(gc_l, 2), 'fo_l': fo_l,
        'gf_v': round(gf_v, 2), 'gc_v': round(gc_v, 2), 'fo_v': fo_v,
    }


def _hora_cot(iso):
    try:
        u = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        return (u - timedelta(hours=5)).strftime('%H:%M COT')
    except Exception:
        return ''


def main(fechas):
    preds = []
    vistos = set()
    for fecha in fechas:
        r = _apifb('fixtures', {'date': fecha})
        for fx in (r.get('response') or []):
            lg = fx['league']
            nombre = (lg.get('name') or '').lower()
            if lg.get('id') != 1 and 'world cup' not in nombre and 'mundial' not in nombre:
                continue
            if fx['fixture']['status']['short'] not in ('NS', 'TBD'):
                continue
            h, a = fx['teams']['home'], fx['teams']['away']
            key = (h['id'], a['id'])
            if key in vistos:
                continue
            vistos.add(key)
            m = _predecir(h['id'], a['id'])
            preds.append({
                'local': h['name'], 'visitante': a['name'],
                'liga': 'FIFA Mundial 2026', 'liga_code': 'soccer_fifa_world_cup',
                'hora': _hora_cot(fx['fixture']['date']), 'fecha_evento': fecha,
                'probabilidades': {
                    'victoria_local': m['vl'], 'empate': m['ve'],
                    'victoria_visita': m['vv'], 'over25': m['o25'], 'under25': m['u25'],
                },
                'forma_local': {'forma': m['fo_l'], 'ataque_reciente': m['gf_l'],
                                'defensa_reciente': m['gc_l']},
                'forma_visita': {'forma': m['fo_v'], 'ataque_reciente': m['gf_v'],
                                 'defensa_reciente': m['gc_v']},
            })
            print(f"  {h['name']} vs {a['name']} | {m['vl']}/{m['ve']}/{m['vv']} "
                  f"O2.5={m['o25']}%")
    print(f"Partidos del Mundial encontrados: {len(preds)}")
    if not preds:
        print("Sin partidos. Nada que inyectar.")
        return
    items = ga.generar_items(preds)
    ga.inyectar(ga._to_js(items))
    print(f"ANALISIS_DIA inyectado: {len(items)} partidos en la web.")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        fechas = sys.argv[1:]
    else:
        hoy = datetime.utcnow() - timedelta(hours=5)
        fechas = [(hoy + timedelta(days=d)).strftime('%Y-%m-%d') for d in (0, 1)]
    main(fechas)
