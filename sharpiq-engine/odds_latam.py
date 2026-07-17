# -*- coding: utf-8 -*-
"""
SharpIQ — Cuotas LATAM reales (odds-api.io)

POR QUE EXISTE (16-jul-26):
The Odds API (la que ya usa el motor) NO trae casas LatAm: nada de BetPlay,
Rushbet, Wplay, Caliente. Sus 48 casas son gringas/europeas. Resultado: el
motor calculaba valor contra cuotas que el cliente colombiano NO PUEDE TOMAR
(el caso Fanatics 1.31 vs BetPlay 1.20, y el "Madrid 1.9 vs casas 1.4").

odds-api.io SI trae BETPLAY (la casa #1 de Colombia, patrocina la Liga BetPlay)
y BETANO (BR/MX/PE). Verificado cruzando contra The Odds API: los numeros y el
home/away CUADRAN.

LA FORMULA DEL PRODUCTO:
    The Odds API  -> PINNACLE -> devig -> CUOTA JUSTA (la verdad)
    odds-api.io   -> BETPLAY  -> lo que el cliente REALMENTE consigue
    -------------------------------------------------------------
    VALOR REAL = lo que paga BetPlay vs lo que deberia pagar

Eso es lo que OddsJam/RebelBetting NO pueden hacer: no tienen casas LatAm.

LIMITE DEL PLAN FREE: 2 casas, 100 requests/HORA -> cache obligatorio.
"""
import os, sqlite3, json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "sharpiq.db")
API      = "https://api.odds-api.io/v3"

# Casas del plan free. OJO: los nombres deben ir EXACTOS como los devuelve la API.
CASAS_FREE = "Betplay,Betano"
CASA_CLIENTE = "Betplay"          # la casa de referencia del cliente colombiano

# Ligas LatAm que nos interesan (substring del league.name de odds-api.io)
LIGAS_LATAM = (
    "colombia - liga dimayor",
    "colombia - torneo dimayor",
    "colombia - copa dimayor",
    "mexico - liga mx, apertura",
    "brazil - brasileiro serie a",
    "brazil - brasileiro serie b",
)

# BUG CAZADO EN LA PRIMERA PRUEBA (16-jul-26): "mexico - U21 liga mx, apertura"
# CONTIENE "mexico - liga mx, apertura" -> el filtro por substring colaba los
# partidos SUB-21. Como el Tijuana vs Tigres sub-21 tiene los MISMOS nombres de
# equipo que el de primera, buscar_evento() agarraba el equivocado y comparaba
# la cuota justa de PRIMERA contra la cuota de SUB-21 -> "+97% de valor" falso.
# Sin esta exclusion, el motor publicaria picks de fantasia.
EXCLUIR = ("u21", "u20", "u23", "u19", "sub-21", "sub-20",
           "women", "femenina", "femenino", "reserves", "youth")


def _liga_valida(nombre):
    n = (nombre or "").lower()
    if any(x in n for x in EXCLUIR):
        return False
    return any(k in n for k in LIGAS_LATAM)


def _key():
    from config import ODDSAPI_IO_KEY
    return ODDSAPI_IO_KEY


# ── CACHE (el free tier son 100 req/HORA: sin cache lo quemamos) ──────
def _db():
    return sqlite3.connect(DB_PATH)


def _init():
    with _db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS latam_cache (
            clave       TEXT PRIMARY KEY,
            data_json   TEXT,
            actualizado TEXT
        )""")


def _cache_get(clave, minutos=15):
    _init()
    with _db() as c:
        row = c.execute("SELECT data_json, actualizado FROM latam_cache WHERE clave=?",
                        (clave,)).fetchone()
    if not row:
        return None
    edad = (datetime.now() - datetime.fromisoformat(row[1])).total_seconds() / 60
    return json.loads(row[0]) if edad <= minutos else None


def _cache_put(clave, data):
    _init()
    with _db() as c:
        c.execute("INSERT OR REPLACE INTO latam_cache (clave, data_json, actualizado) VALUES (?,?,?)",
                  (clave, json.dumps(data), datetime.now().isoformat()))


# ── NORMALIZACION DE NOMBRES ─────────────────────────────────────────
# The Odds API dice "Tijuana"; odds-api.io dice "Club Tijuana de Caliente".
# Sin esto no emparejamos nada.
_RUIDO = (" de caliente", "club ", " uanl", " fc", "fc ", " cf", "cf ", " unam",
          " sc", " ec", " rj", " sp", " rs", " ba", " mg", " pr", "deportivo ",
          " futbol club", " football club", " atletico", " atlético", " de ",
          " fútbol", " futbol", "-", ".", "  ")


def _norm(s):
    s = (s or "").lower().strip()
    for a, b in (("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")):
        s = s.replace(a, b)
    for r in _RUIDO:
        s = s.replace(r, " ")
    return " ".join(s.split())


def _parecen(a, b):
    """True si dos nombres de equipo son el mismo (tolerante)."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    pa, pb = set(na.split()), set(nb.split())
    comunes = pa & pb
    # comparten una palabra larga (evita match por "de", "fc", etc.)
    return any(len(p) >= 5 for p in comunes)


# ── EVENTOS ──────────────────────────────────────────────────────────
def obtener_eventos_latam(forzar=False):
    """Todos los partidos LatAm sin jugar. Cache 15 min (1 request)."""
    if not forzar:
        c = _cache_get("eventos_latam", minutos=15)
        if c is not None:
            return c
    import requests
    try:
        r = requests.get(f"{API}/events", params={"apiKey": _key(), "sport": "football"}, timeout=30)
        if r.status_code != 200:
            print(f"    odds-api.io /events -> {r.status_code}")
            return []
        evs = [e for e in r.json()
               if _liga_valida((e.get("league", {}) or {}).get("name", ""))
               and e.get("status") != "settled"]
        _cache_put("eventos_latam", evs)
        print(f"    odds-api.io: {len(evs)} partidos LatAm sin jugar")
        return evs
    except Exception as e:
        print(f"    odds-api.io error: {e}")
        return []


def buscar_evento(local, visitante):
    """Encuentra el evento de odds-api.io que corresponde a este partido."""
    for e in obtener_eventos_latam():
        if _parecen(e.get("home"), local) and _parecen(e.get("away"), visitante):
            return e
    return None


# ── CUOTAS ───────────────────────────────────────────────────────────
def obtener_cuotas_evento(event_id, casas=CASAS_FREE):
    """Cuotas crudas de un evento. Cache 10 min (1 request)."""
    clave = f"odds_{event_id}_{casas}"
    c = _cache_get(clave, minutos=10)
    if c is not None:
        return c
    import requests
    try:
        r = requests.get(f"{API}/odds",
                         params={"apiKey": _key(), "eventId": event_id, "bookmakers": casas},
                         timeout=30)
        if r.status_code != 200:
            return {}
        d = r.json()
        _cache_put(clave, d)
        return d
    except Exception:
        return {}


def _f(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def cuotas_cliente(local, visitante, casa=CASA_CLIENTE):
    """
    Cuotas REALES que consigue el cliente en SU casa, en el formato del motor.
    Devuelve None si no hay datos. Claves: 1, X, 2, over15/25/35, under..., btts_si/no.
    """
    ev = buscar_evento(local, visitante)
    if not ev:
        return None
    d = obtener_cuotas_evento(ev["id"])
    bks = d.get("bookmakers", {}) or {}
    mercados = bks.get(casa) or bks.get(casa.capitalize()) or []
    if not mercados:
        return None

    out = {"casa": casa, "evento_id": ev["id"],
           "local_api": ev.get("home"), "visita_api": ev.get("away")}
    for m in mercados:
        nom  = (m.get("name") or "").lower()
        odds = m.get("odds") or []
        if not odds:
            continue
        if nom == "ml":
            o = odds[0]
            out["1"] = _f(o.get("home")); out["X"] = _f(o.get("draw")); out["2"] = _f(o.get("away"))
        elif nom == "totals":
            for o in odds:
                hdp = o.get("hdp")
                for lim, k in ((1.5, "15"), (2.5, "25"), (3.5, "35")):
                    if hdp is not None and abs(float(hdp) - lim) < 0.01:
                        out[f"over{k}"]  = _f(o.get("over"))
                        out[f"under{k}"] = _f(o.get("under"))
        elif "both teams" in nom:
            o = odds[0]
            out["btts_si"] = _f(o.get("yes")); out["btts_no"] = _f(o.get("no"))
    return out if out.get("1") else None


# ── VALOR REAL ───────────────────────────────────────────────────────
# Un value bet real en un mercado normal va de 1% a ~10%. Si sale +20% o mas,
# NO es valor: es data mala (partido equivocado, cuota vieja, error palpable).
# En la primera prueba salio un "+97%" porque se habia colado un partido SUB-21.
MAX_VALOR_CREIBLE = 20.0


def valor_real(prob_justa_pct, cuota_cliente):
    """
    EV con la cuota que el cliente SI puede tomar.
    prob_justa_pct: probabilidad real (devig de Pinnacle), 0-100.
    Devuelve EV en % (positivo = hay valor DE VERDAD).
    """
    if not cuota_cliente or not prob_justa_pct:
        return None
    p = prob_justa_pct / 100.0
    return round((p * cuota_cliente - 1) * 100, 2)


def es_creible(ev_pct):
    """False si el 'valor' es demasiado bueno para ser verdad (= data mala)."""
    return ev_pct is not None and -MAX_VALOR_CREIBLE <= ev_pct <= MAX_VALOR_CREIBLE


def cuota_justa(prob_justa_pct):
    """La cuota que DEBERIA pagar la casa si no tuviera margen."""
    if not prob_justa_pct:
        return None
    return round(100.0 / prob_justa_pct, 2)


def comparar(local, visitante, mercado, prob_justa_pct, casa=CASA_CLIENTE):
    """
    EL PRODUCTO: compara la cuota justa contra lo que paga la casa del cliente.
    mercado: "1", "X", "2", "over25", "under25", "btts_si"...
    Devuelve dict listo para mostrar en la web, o None.
    """
    cc = cuotas_cliente(local, visitante, casa)
    if not cc or mercado not in cc or not cc[mercado]:
        return None
    paga  = cc[mercado]
    justa = cuota_justa(prob_justa_pct)
    ev    = valor_real(prob_justa_pct, paga)
    if not es_creible(ev):
        # Valor absurdo = data mala, NO se publica. Mejor callar que mentir.
        print(f"    [odds_latam] DESCARTADO {local} vs {visitante} {mercado}: "
              f"valor {ev}% no creible (revisar emparejamiento/cuota)")
        return None
    return {
        "partido":   f"{local} vs {visitante}",
        "mercado":   mercado,
        "casa":      casa,
        "cuota_casa":  paga,
        "cuota_justa": justa,
        "prob_justa":  round(prob_justa_pct, 1),
        "valor_pct":   ev,
        "hay_valor":   ev is not None and ev > 0,
    }
