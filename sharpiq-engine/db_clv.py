# -*- coding: utf-8 -*-
"""
SharpIQ — Base de datos PostgreSQL + CLV tracking
Almacena cuotas de apertura/cierre y mide Closing Line Value real.
"""
import os, sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

try:
    from config import DATABASE_PUBLIC_URL
    DB_URL = DATABASE_PUBLIC_URL
except ImportError:
    DB_URL = os.environ.get("DATABASE_PUBLIC_URL", "")


def _conn():
    if not psycopg2:
        raise RuntimeError("psycopg2 no instalado — pip install psycopg2-binary")
    return psycopg2.connect(DB_URL, sslmode="require")


def inicializar():
    """Crea las tablas si no existen."""
    with _conn() as c:
        cur = c.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS picks (
            id              SERIAL PRIMARY KEY,
            pick_uid        TEXT UNIQUE,          -- ID unico (evento_id+mercado): dedup + match sin nombres fragiles
            evento_id       TEXT,                 -- id del evento en The Odds API (re-consultar en Fase 2)
            fecha_evento    DATE,                 -- fecha del PARTIDO (no la de registro)
            comienzo        TIMESTAMP,            -- hora UTC exacta del kickoff (open/close de Fase 2)
            partido         TEXT NOT NULL,
            liga            TEXT,
            liga_code       TEXT,                 -- sport_key (re-consultar la cuota en Fase 2)
            mercado         TEXT,                 -- key canonica consistente (todos los deportes)
            tier            TEXT,                 -- seguro | principal | alto_valor
            casa            TEXT,                 -- bookmaker de la cuota de apertura
            prob_modelo     FLOAT,
            cuota_apertura  FLOAT,
            cuota_pinnacle  FLOAT,
            ev_apertura     FLOAT,                -- EV REAL del motor (blended/capped), NO recalculado
            cuota_cierre    FLOAT,                -- la llena la Fase 2 (ultima captura antes del kickoff)
            ev_cierre       FLOAT,
            clv             FLOAT,
            resultado       TEXT,
            creado          TIMESTAMP DEFAULT NOW()
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS odds_history (
            id          SERIAL PRIMARY KEY,
            pick_uid    TEXT,                 -- a que pick pertenece este snapshot (match sin nombres)
            evento_id   TEXT,
            partido     TEXT,
            mercado     TEXT,
            bookmaker   TEXT,
            cuota       FLOAT,
            ts          TIMESTAMP DEFAULT NOW()
        );
        """)
        c.commit()
    print("  DB inicializada OK")


def guardar_pick(pick_uid, evento_id, fecha_evento, comienzo, partido, liga, liga_code,
                 mercado, tier, casa, prob_modelo, cuota_apertura, ev_apertura,
                 cuota_pinnacle=None):
    """Registra un pick en apertura. `ev_apertura` es el EV REAL del motor
    (blended/capped) — NO se recalcula aqui. `pick_uid` hace dedup (ON CONFLICT)."""
    with _conn() as c:
        cur = c.cursor()
        cur.execute("""
            INSERT INTO picks (pick_uid, evento_id, fecha_evento, comienzo, partido, liga,
                               liga_code, mercado, tier, casa, prob_modelo,
                               cuota_apertura, ev_apertura, cuota_pinnacle)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (pick_uid) DO NOTHING
            RETURNING id
        """, (pick_uid, evento_id, fecha_evento, comienzo, partido, liga, liga_code,
              mercado, tier, casa, prob_modelo, cuota_apertura, ev_apertura,
              cuota_pinnacle))
        row = cur.fetchone()
        c.commit()
    return row[0] if row else None


def actualizar_cierre(pick_uid, cuota_cierre):
    """Registra la cuota de cierre y calcula CLV. Matchea por pick_uid (no nombres)."""
    with _conn() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT id, prob_modelo, cuota_apertura
            FROM picks WHERE pick_uid=%s
        """, (pick_uid,))
        row = cur.fetchone()
        if not row:
            return
        pick_id, prob, q_open = row
        ev_cierre = round((prob / 100) * cuota_cierre - 1, 4) if (cuota_cierre and prob) else None
        clv = round((q_open / cuota_cierre - 1) * 100, 2) if (cuota_cierre and q_open) else None  # CLV%: + = mejor precio que el cierre
        cur.execute("""
            UPDATE picks SET cuota_cierre=%s, ev_cierre=%s, clv=%s
            WHERE id=%s
        """, (cuota_cierre, ev_cierre, clv, pick_id))
        c.commit()


def actualizar_resultado(partido, mercado, resultado):
    """win | loss | push"""
    with _conn() as c:
        cur = c.cursor()
        cur.execute("""
            UPDATE picks SET resultado=%s
            WHERE partido=%s AND mercado=%s AND resultado IS NULL
        """, (resultado, partido, mercado))
        c.commit()


def resumen_clv():
    """Metricas ACUMULADAS de CLV desde el inicio de la medicion. El CLV se mide
    sobre picks con cierre (clv NOT NULL); el yield sobre resueltos (win/loss)."""
    with _conn() as c:
        cur = c.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT
                MIN(creado)::date                                    AS fecha_inicio,
                COUNT(*) FILTER (WHERE clv IS NOT NULL)              AS n_cierre,
                ROUND(AVG(clv) FILTER (WHERE clv IS NOT NULL)::numeric, 2)  AS clv_promedio,
                COUNT(*) FILTER (WHERE clv > 0)                      AS batieron,
                COUNT(*) FILTER (WHERE resultado='win')              AS wins,
                COUNT(*) FILTER (WHERE resultado='loss')             AS losses,
                COUNT(*) FILTER (WHERE resultado IN ('win','loss'))  AS n_resueltos,
                ROUND((SUM(CASE WHEN resultado='win'  THEN cuota_apertura-1
                                WHEN resultado='loss' THEN -1 ELSE 0 END)
                       / NULLIF(COUNT(*) FILTER (WHERE resultado IN ('win','loss')),0) * 100)::numeric, 2) AS yield_pct
            FROM picks
        """)
        r = dict(cur.fetchone() or {})
        nc = r.get("n_cierre") or 0
        r["pct_batio"] = round(100.0 * (r.get("batieron") or 0) / nc, 1) if nc else None
        cur.execute("""
            SELECT tier,
                   COUNT(*) FILTER (WHERE clv IS NOT NULL) AS n,
                   ROUND(AVG(clv) FILTER (WHERE clv IS NOT NULL)::numeric, 2) AS clv
            FROM picks WHERE tier IS NOT NULL GROUP BY tier
        """)
        r["por_tier"] = {x["tier"]: {"n": x["n"], "clv": x["clv"]} for x in cur.fetchall()}
        return r


def guardar_odds_history(pick_uid, evento_id, partido, mercado, bookmaker, cuota):
    """Un snapshot del movimiento de la cuota. pick_uid lo ata a su pick (sin nombres)."""
    with _conn() as c:
        cur = c.cursor()
        cur.execute("""
            INSERT INTO odds_history (pick_uid, evento_id, partido, mercado, bookmaker, cuota)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (pick_uid, evento_id, partido, mercado, bookmaker, cuota))
        c.commit()


if __name__ == "__main__":
    inicializar()
    print("Tablas creadas OK")
