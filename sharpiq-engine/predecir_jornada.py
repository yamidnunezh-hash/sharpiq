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
import mercados_profundos as mp


def _gfgc(tid, n=8):
    """Promedio de goles a favor/en contra y forma (0-1) de los ultimos n."""
    r = _apifb('fixtures', {'team': tid, 'last': n})
    gf = gc = c = pts = 0
    for fx in ((r or {}).get('response') or []):
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
        'lam_l': round(lam_l, 3), 'lam_v': round(lam_v, 3),
    }


def _goleadores(local, vis, liga_id, season, m):
    """Player props: top goleadores probables (nombre + % de marcar). Robusto."""
    try:
        import player_props as pp
        props = pp.calcular_props_partido(local, vis, liga_id,
                                          m.get('lam_l', 1.2), m.get('lam_v', 1.2), season)
        return ' &middot; '.join(f"{p['nombre']} {p['prob_scorer']}%" for p in props[:3])
    except Exception:
        return ''


def _hora_cot(iso):
    try:
        u = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        return (u - timedelta(hours=5)).strftime('%H:%M COT')
    except Exception:
        return ''


# Ligas principales para el análisis del día + goleadores (IDs de API-Football).
# Se extiende más allá del Mundial pero acotado, para no disparar el uso de la API.
_LIGAS_ANALISIS = {
    1, 15,                     # Mundial FIFA, Mundial de Clubes
    2, 3, 848,                 # Champions, Europa League, Conference
    39, 140, 135, 78, 61,      # Premier, LaLiga, Serie A, Bundesliga, Ligue 1
    94, 88,                    # Primeira Liga (POR), Eredivisie (NED)
    13, 11,                    # Copa Libertadores, Copa Sudamericana
    71, 72, 128, 262, 253,     # Brasileirão A/B, Liga Argentina, Liga MX, MLS
}
_MAX_PARTIDOS = 30             # tope de partidos por corrida (cuida la cuota de la API)


def main(fechas):
    preds = []
    profs = []
    goles = []
    vistos = set()
    for fecha in fechas:
        if len(preds) >= _MAX_PARTIDOS:
            break
        r = _apifb('fixtures', {'date': fecha})
        for fx in ((r or {}).get('response') or []):
            if len(preds) >= _MAX_PARTIDOS:
                break
            lg = fx['league']
            nombre = (lg.get('name') or '').lower()
            if lg.get('id') not in _LIGAS_ANALISIS and 'world cup' not in nombre and 'mundial' not in nombre:
                continue
            # incluir no-empezados Y en juego; excluir solo los YA terminados/cancelados
            if fx['fixture']['status']['short'] in ('FT', 'AET', 'PEN', 'CANC', 'PST', 'ABD', 'AWD', 'WO'):
                continue
            h, a = fx['teams']['home'], fx['teams']['away']
            key = (h['id'], a['id'])
            if key in vistos:
                continue
            vistos.add(key)
            m = _predecir(h['id'], a['id'])
            profs.append(mp.proyectar(h['id'], a['id']))
            _es_mundial = lg.get('id') in (1, 15) or 'world cup' in nombre or 'mundial' in nombre
            _season = int(fecha[:4]) if _es_mundial else None  # ligas domésticas: temporada por defecto
            goles.append(_goleadores(h['name'], a['name'], lg.get('id'), _season, m))
            preds.append({
                'local': h['name'], 'visitante': a['name'],
                'liga': lg.get('name') or 'Fútbol',
                'liga_code': 'liga_' + str(lg.get('id') or ''),
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
    print(f"Partidos analizados (Mundial + ligas principales): {len(preds)}")
    if not preds:
        print("Sin partidos. Nada que inyectar.")
        return
    items = ga.generar_items(preds)
    # --- enriquecer cada analisis con MERCADOS PROFUNDOS (remates/atajadas/etc.) ---
    for it, prof, pr, gole in zip(items, profs, preds, goles):
        it['eqL'] = pr.get('local', '')      # nombre EN INGLES (para resolver el logo)
        it['eqV'] = pr.get('visitante', '')
        if gole:
            it['gole'] = gole                # player props: goleadores probables
        # JUGADA del modelo (la ve el DUENO/VIP en la pagina de detalle): mercado mas confiable
        _vl = float(it.get('vl') or 0); _vv = float(it.get('vv') or 0)
        _o = float(it.get('o25') or 0); _u = float(it.get('u25') or 0)
        _lc, _vs = (it.get('partido', '').split(' vs ') + [''])[:2]
        _fav, _fp = (_lc, _vl) if _vl >= _vv else (_vs, _vv)
        if   _fp >= 60: it['pick'] = 'Gana ' + _fav
        elif _o >= 60:  it['pick'] = 'Over 2.5 goles'
        elif _u >= 60:  it['pick'] = 'Under 2.5 goles'
        elif _fp >= 44: it['pick'] = 'Doble oportunidad: ' + _fav + ' o empate'
        else:           it['pick'] = 'Partido parejo - mejor pasar'
        if not prof:
            continue
        try:
            loc, vis = it['partido'].split(' vs ')
        except ValueError:
            loc, vis = 'el local', 'el visitante'
        it['cuerpo_largo'] = it.get('cuerpo_largo', '') + (
            f" En mercados profundos (datos reales, muestra {prof['n']} partidos), "
            f"el modelo proyecta {prof['remates_total']} remates totales "
            f"({prof['local_sot']} a puerta de {loc}, {prof['visita_sot']} de {vis}); "
            f"el portero de {vis} haria ~{prof['visita_atajadas']} atajadas; "
            f"y {prof['corners_total']} corners y {prof['faltas_total']} faltas en total.")
        it['remT'] = str(prof['remates_total'])
        it['sotL'] = str(prof['local_sot']); it['sotV'] = str(prof['visita_sot'])
        it['ataL'] = str(prof['local_atajadas']); it['ataV'] = str(prof['visita_atajadas'])
        it['corT'] = str(prof['corners_total']); it['falT'] = str(prof['faltas_total'])
    ga.inyectar(ga._to_js(items))
    print(f"ANALISIS_DIA inyectado: {len(items)} partidos (con mercados profundos).")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        fechas = sys.argv[1:]
    else:
        hoy = datetime.utcnow() - timedelta(hours=5)
        fechas = [(hoy + timedelta(days=d)).strftime('%Y-%m-%d') for d in (0, 1)]
    main(fechas)
