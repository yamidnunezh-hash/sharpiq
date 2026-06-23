# -*- coding: utf-8 -*-
"""Mercados PROFUNDOS para SharpIQ.

Proyecta por partido los mercados que pide la gente y que el motor basico NO
daba: remates totales, remates A PUERTA, atajadas del portero, faltas y corners
por equipo. Usa los promedios reales de los ultimos N partidos
(API-Football /fixtures/statistics), cruzando ataque propio vs defensa rival.

Aislado: NO toca motor.py. Se puede llamar desde el flujo o probar a mano.
Cache SQLite (sharpiq.db) con TTL para no gastar API en cada corrida.
"""
import os, sqlite3, json, time

BASE = os.path.dirname(os.path.abspath(__file__))
_DB  = os.path.join(BASE, 'sharpiq.db')
_TTL = 2 * 24 * 3600   # 2 dias

# Claves de API-Football /fixtures/statistics que nos interesan
_K_SHOTS  = 'Total Shots'
_K_SOT    = 'Shots on Goal'
_K_CORN   = 'Corner Kicks'
_K_FOULS  = 'Fouls'
_K_SAVES  = 'Goalkeeper Saves'


def _cache_get(key):
    try:
        con = sqlite3.connect(_DB)
        con.execute("CREATE TABLE IF NOT EXISTS mercados_prof (k TEXT PRIMARY KEY, v TEXT, ts REAL)")
        row = con.execute("SELECT v, ts FROM mercados_prof WHERE k=?", (key,)).fetchone()
        con.close()
        if row and (time.time() - row[1]) < _TTL:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def _cache_set(key, val):
    try:
        con = sqlite3.connect(_DB)
        con.execute("CREATE TABLE IF NOT EXISTS mercados_prof (k TEXT PRIMARY KEY, v TEXT, ts REAL)")
        con.execute("INSERT OR REPLACE INTO mercados_prof VALUES (?,?,?)",
                    (key, json.dumps(val), time.time()))
        con.commit(); con.close()
    except Exception:
        pass


def stats_equipo(team_id, n=5):
    """Promedios de los ultimos N partidos: remates/SoT/corners/faltas/atajadas
    a FAVOR y remates/SoT en CONTRA. Devuelve dict o None. Con cache."""
    if not team_id:
        return None
    ck = f"prof_{team_id}_{n}"
    c = _cache_get(ck)
    if c:
        return c
    from motor import _apifb
    r = _apifb('fixtures', {'team': team_id, 'last': n})
    fxs = (r or {}).get('response') or []
    acc = {'shots_for': 0, 'sot_for': 0, 'corners_for': 0, 'fouls': 0,
           'saves': 0, 'shots_ag': 0, 'sot_ag': 0}
    cnt = 0
    for fx in fxs:
        fid = fx['fixture']['id']
        st = _apifb('fixtures/statistics', {'fixture': fid})
        sresp = (st or {}).get('response') or []
        got = False
        for tm in sresp:
            us = tm['team']['id'] == team_id
            for s in tm.get('statistics', []):
                ty = s.get('type'); v = s.get('value') or 0
                try: v = int(v)
                except (TypeError, ValueError): v = 0
                if us:
                    if   ty == _K_SHOTS: acc['shots_for'] += v; got = True
                    elif ty == _K_SOT:   acc['sot_for']   += v
                    elif ty == _K_CORN:  acc['corners_for'] += v
                    elif ty == _K_FOULS: acc['fouls']     += v
                    elif ty == _K_SAVES: acc['saves']     += v
                else:
                    if   ty == _K_SHOTS: acc['shots_ag'] += v
                    elif ty == _K_SOT:   acc['sot_ag']   += v
        if got:
            cnt += 1
    if cnt == 0:
        return None
    out = {k: round(v / cnt, 2) for k, v in acc.items()}
    out['n'] = cnt
    _cache_set(ck, out)
    return out


def _blend(a, b):
    return round((a + b) / 2.0, 1)


def proyectar(local_id, visita_id, n=5):
    """Proyeccion de mercados profundos del partido. Cruza ataque propio vs
    defensa rival. Devuelve dict con valores esperados, o None si faltan datos."""
    L = stats_equipo(local_id, n)
    V = stats_equipo(visita_id, n)
    if not L or not V:
        return None
    # Remates / a puerta de cada equipo = (ataque propio + defensa que concede el rival) / 2
    L_shots = _blend(L['shots_for'], V['shots_ag'])
    V_shots = _blend(V['shots_for'], L['shots_ag'])
    L_sot   = _blend(L['sot_for'],   V['sot_ag'])
    V_sot   = _blend(V['sot_for'],   L['sot_ag'])
    # Atajadas ~ remates a puerta que enfrenta el portero * 0.7 (los que no son gol)
    L_saves = round(V_sot * 0.7, 1)   # portero LOCAL enfrenta los SoT del VISITANTE
    V_saves = round(L_sot * 0.7, 1)
    corners = round(L['corners_for'] + V['corners_for'], 1)
    faltas  = round(L['fouls'] + V['fouls'], 1)
    return {
        'local_remates':   L_shots, 'visita_remates':   V_shots,
        'local_sot':       L_sot,   'visita_sot':       V_sot,
        'local_atajadas':  L_saves, 'visita_atajadas':  V_saves,
        'corners_total':   corners, 'faltas_total':     faltas,
        'remates_total':   round(L_shots + V_shots, 1),
        'sot_total':       round(L_sot + V_sot, 1),
        'n': min(L['n'], V['n']),
    }


if __name__ == '__main__':
    # Prueba: Portugal (27) vs Uzbekistan (1568)
    import sys
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 27
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 1568
    p = proyectar(a, b)
    print(json.dumps(p, ensure_ascii=False, indent=1) if p else "Sin datos")
