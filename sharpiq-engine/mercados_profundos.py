# -*- coding: utf-8 -*-
"""Mercados PROFUNDOS para SharpIQ.

Proyecta por partido los mercados que pide la gente y que el motor basico NO
daba: remates totales, remates A PUERTA, atajadas del portero, faltas y corners
por equipo. Usa los promedios reales de los ultimos partidos
(API-Football /fixtures/statistics), cruzando ataque propio vs defensa rival.

Calidad de muestra: pide hasta 12 partidos, SALTA los que no tienen estadistica
(no inventa) y se queda con hasta 8 partidos CON datos reales, PONDERANDO los
mas recientes (pesan mas). Asi la muestra es solida y no de 3 partidos.

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


def stats_equipo(team_id, n=12, objetivo=8):
    """Promedio PONDERADO (recientes pesan mas) de los partidos CON estadistica
    dentro de los ultimos `n`. Salta los partidos sin datos (NO inventa) y apunta
    a `objetivo` partidos con datos para una muestra solida. Mide remates/SoT/
    corners/faltas/atajadas a FAVOR y remates/SoT en CONTRA. Devuelve dict (con
    'n' = partidos reales usados) o None. Con cache."""
    if not team_id:
        return None
    ck = f"prof_v2_{team_id}_{n}_{objetivo}"
    c = _cache_get(ck)
    if c:
        return c
    from motor import _apifb
    r = _apifb('fixtures', {'team': team_id, 'last': n})
    fxs = (r or {}).get('response') or []
    keys = ('shots_for', 'sot_for', 'corners_for', 'fouls', 'saves',
            'shots_ag', 'sot_ag')
    acc = {k: 0.0 for k in keys}
    wsum = 0.0
    usados = 0   # solo partidos CON estadistica (la recencia se cuenta sobre estos)
    for fx in fxs:   # API-Football los devuelve del mas reciente al mas viejo
        fid = fx['fixture']['id']
        st = _apifb('fixtures/statistics', {'fixture': fid})
        sresp = (st or {}).get('response') or []
        vals = {k: 0 for k in keys}
        got = False
        for tm in sresp:
            us = tm['team']['id'] == team_id
            for s in tm.get('statistics', []):
                ty = s.get('type'); v = s.get('value') or 0
                try: v = int(v)
                except (TypeError, ValueError): v = 0
                if us:
                    if   ty == _K_SHOTS: vals['shots_for'] = v; got = True
                    elif ty == _K_SOT:   vals['sot_for']   = v
                    elif ty == _K_CORN:  vals['corners_for'] = v
                    elif ty == _K_FOULS: vals['fouls']     = v
                    elif ty == _K_SAVES: vals['saves']     = v
                else:
                    if   ty == _K_SHOTS: vals['shots_ag'] = v
                    elif ty == _K_SOT:   vals['sot_ag']   = v
        if not got:
            continue   # partido sin estadistica -> NO se inventa, se salta
        w = 0.9 ** usados   # recencia: el mas reciente pesa 1, luego 0.9, 0.81...
        for k in keys:
            acc[k] += vals[k] * w
        wsum += w
        usados += 1
        if usados >= objetivo:
            break
    if usados == 0:
        return None
    out = {k: round(acc[k] / wsum, 2) for k in keys}
    out['n'] = usados
    _cache_set(ck, out)
    return out


def _blend(a, b):
    return round((a + b) / 2.0, 1)


def proyectar(local_id, visita_id, n=12):
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
        'muestra_local':   L['n'],  'muestra_visita':   V['n'],
        'n': min(L['n'], V['n']),
    }


if __name__ == '__main__':
    # Prueba: Portugal (27) vs Uzbekistan (1568)
    import sys
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 27
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 1568
    p = proyectar(a, b)
    print(json.dumps(p, ensure_ascii=False, indent=1) if p else "Sin datos")
