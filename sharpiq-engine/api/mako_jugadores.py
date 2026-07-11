"""
Mako — consulta de estadísticas de jugador BAJO DEMANDA (API-Football).
═══════════════════════════════════════════════════════════════════════════════
Antes Mako solo conocía los ~6 jugadores que el motor pre-calculaba cada mañana.
Si un cliente preguntaba por CUALQUIER otro jugador ("¿cuántas faltas hace
Berge?"), Mako no tenía el dato y quedaba mal ("eso no dice nada" — feedback real
de un cliente, 11-jul-2026).

Este módulo le da a Mako la MISMA capacidad que usamos a mano: buscar un jugador
en API-Football y traer sus promedios REALES (faltas, remates, tarjetas, goles,
asistencias) — por competición y global. Datos reales, nunca inventados.

Independiente y a prueba de fallos: si algo falla, devuelve None y Mako sigue
respondiendo con lo que ya tiene.
"""
from __future__ import annotations

import os

BASE = "https://v3.football.api-sports.io"
_cache: dict[str, dict | None] = {}      # nombre_normalizado -> ficha (o None)

# Estrellas de UNA sola palabra (apodo ≠ apellido real): la búsqueda por nombre
# trae homónimos. Mapa curado con el ID correcto de API-Football (verificado).
_ALIAS = {
    "rodri": 44, "casemiro": 747, "vinicius": 762, "vini": 762,
    "vinicius jr": 762, "vini jr": 762, "rodrygo": 10009, "neymar": 276,
}


def _key() -> str:
    k = os.environ.get("APIFOOTBALL_KEY", "")
    if not k:
        try:
            from config import APIFOOTBALL_KEY as _k
            k = _k or ""
        except Exception:
            k = ""
    return k


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(s.split())


def _get(url: str, params: dict) -> dict:
    import requests
    params = dict(params); params_key = _key()
    r = requests.get(url, headers={"x-apisports-key": params_key}, params=params, timeout=15)
    if r.status_code != 200:
        return {}
    return r.json()


def _buscar_id(nombre: str) -> tuple[int | None, dict]:
    """Devuelve (player_id, perfil) del jugador más parecido, o (None, {}).

    PUNTÚA por coincidencia de nombre COMPLETO (no solo apellido): hay muchos
    'Berge', 'Silva', 'García'. Si la pregunta dice 'Sander Berge' hay que
    preferir al que coincide en NOMBRE y apellido, no al primer 'Berge' cualquiera.
    """
    # Alias de estrellas de una palabra (Rodri, Casemiro, Vinicius...): id directo.
    if _norm(nombre) in _ALIAS:
        return _ALIAS[_norm(nombre)], {}

    palabras = [w for w in _norm(nombre).split() if len(w) >= 3]
    if not palabras:
        return None, {}
    apellido = palabras[-1]      # convención: la última palabra es el apellido

    # La API busca MEJOR por apellido solo (buscar "Sander Berge" completo a veces
    # trae 0; buscar "berge" trae al jugador). Probamos apellido, luego completo.
    cands = []
    for termino in (apellido, nombre.strip()):
        d = _get(f"{BASE}/players/profiles", {"search": termino})
        cands = d.get("response", []) or []
        if cands:
            break
    if not cands:
        return None, {}

    mejor, mejor_sc = None, -1
    for it in cands:
        p = it.get("player", {})
        fn, ln = _norm(p.get("firstname", "")), _norm(p.get("lastname", ""))
        lnw, fnw = ln.split(), fn.split()
        sc = 0
        for w in palabras:
            if w in lnw:   sc += 3      # apellido pesa más
            elif w in fnw: sc += 2      # nombre
            elif w in ln or w in fn: sc += 1
        # EXIGENCIA: el apellido de la pregunta DEBE estar en el nombre del jugador,
        # o descartamos (evita coger un homónimo por el nombre de pila).
        if apellido not in lnw and apellido not in fnw and apellido not in ln:
            continue
        if sc > mejor_sc:
            mejor_sc, mejor = sc, p
    if not mejor:
        return None, {}
    return mejor.get("id"), mejor


def _prom(total, juegos):
    try:
        return round(total / juegos, 2) if juegos else None
    except Exception:
        return None


def stats_jugador(nombre: str, temporada: int = 2026) -> dict | None:
    """Ficha de datos REALES de un jugador. None si no se encuentra o no hay key.

    Devuelve promedios por partido de faltas (cometidas/recibidas), remates
    (totales/a puerta), tarjetas (amarillas/rojas), goles y asistencias — global
    y desglosado por competición (con foco en el Mundial si juega selección).
    """
    if not nombre or not _key():
        return None
    ck = _norm(nombre)
    if ck in _cache:
        return _cache[ck]

    pid, perfil = _buscar_id(nombre)
    if not pid:
        _cache[ck] = None
        return None

    comps = []
    agg = {"pj": 0, "fc": 0, "fd": 0, "st": 0, "so": 0, "ya": 0, "rj": 0, "go": 0, "as": 0}
    mundial = None
    for season in (temporada, temporada - 1):
        d = _get(f"{BASE}/players", {"id": pid, "season": season})
        resp = d.get("response", []) or []
        if not resp:
            continue
        # El perfil viene en la respuesta de stats -> úsalo (completa los alias).
        _pj = resp[0].get("player", {}) or {}
        if _pj.get("lastname") or _pj.get("name"):
            perfil = _pj
        for st in resp[0].get("statistics", []):
            g = st.get("games", {}) or {}
            apps = g.get("appearences") or 0
            if not apps:
                continue
            f = st.get("fouls", {}) or {}
            sh = st.get("shots", {}) or {}
            c = st.get("cards", {}) or {}
            go = st.get("goals", {}) or {}
            lg = (st.get("league", {}) or {}).get("name", "")
            fila = {
                "competicion": lg, "temporada": season, "pj": apps,
                "faltas_cometidas_prom": _prom(f.get("committed") or 0, apps),
                "faltas_recibidas_prom": _prom(f.get("drawn") or 0, apps),
                "remates_prom":          _prom(sh.get("total") or 0, apps),
                "remates_puerta_prom":   _prom(sh.get("on") or 0, apps),
                "amarillas_prom":        _prom(c.get("yellow") or 0, apps),
                "goles":                 go.get("total") or 0,
                "asistencias":           go.get("assists") or 0,
            }
            comps.append(fila)
            agg["pj"] += apps
            agg["fc"] += f.get("committed") or 0
            agg["fd"] += f.get("drawn") or 0
            agg["st"] += sh.get("total") or 0
            agg["so"] += sh.get("on") or 0
            agg["ya"] += c.get("yellow") or 0
            agg["rj"] += c.get("red") or 0
            agg["go"] += go.get("total") or 0
            agg["as"] += go.get("assists") or 0
            if "world cup" in _norm(lg) and mundial is None:
                mundial = fila
        if comps:      # ya tenemos la temporada más reciente con datos
            break

    if not comps:
        _cache[ck] = None
        return None

    pj = agg["pj"]
    ficha = {
        "jugador": f"{perfil.get('firstname','')} {perfil.get('lastname','')}".strip() or nombre,
        "posicion": perfil.get("position"),
        "nacionalidad": perfil.get("nationality"),
        "partidos_total": pj,
        "global": {
            "faltas_cometidas_prom": _prom(agg["fc"], pj),
            "faltas_recibidas_prom": _prom(agg["fd"], pj),
            "remates_prom":          _prom(agg["st"], pj),
            "remates_puerta_prom":   _prom(agg["so"], pj),
            "amarillas_prom":        _prom(agg["ya"], pj),
            "goles":                 agg["go"],
            "asistencias":           agg["as"],
        },
        "mundial": mundial,        # None si no juega selección / sin datos
        "por_competicion": comps[:8],
    }
    _cache[ck] = ficha
    return ficha


def texto_para_mako(nombre: str) -> str | None:
    """Ficha en texto compacto para inyectar en el prompt de Mako. None si no hay."""
    f = stats_jugador(nombre)
    if not f:
        return None
    g = f["global"]
    L = [f"DATOS REALES de {f['jugador']} ({f.get('posicion') or '—'}, {f.get('nacionalidad') or '—'}) "
         f"· {f['partidos_total']} partidos [fuente: API-Football, promedios POST-partido]:"]
    L.append(f"  GLOBAL/partido -> faltas cometidas {g['faltas_cometidas_prom']} · "
             f"faltas recibidas {g['faltas_recibidas_prom']} · remates {g['remates_prom']} "
             f"(a puerta {g['remates_puerta_prom']}) · amarillas {g['amarillas_prom']} · "
             f"goles {g['goles']} · asistencias {g['asistencias']}")
    m = f.get("mundial")
    if m:
        L.append(f"  MUNDIAL ({m['pj']} PJ)/partido -> faltas cometidas {m['faltas_cometidas_prom']} · "
                 f"remates {m['remates_prom']} (a puerta {m['remates_puerta_prom']}) · "
                 f"amarillas {m['amarillas_prom']} · goles {m['goles']}")
    L.append("  (Recuerda: props por jugador son POST-partido y muestra chica = indicio, no certeza.)")
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    nombre = " ".join(sys.argv[1:]) or "Haaland"
    print(texto_para_mako(nombre) or f"No encontré datos de '{nombre}'")
