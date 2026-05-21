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
            fecha           DATE NOT NULL,
            partido         TEXT NOT NULL,
            liga            TEXT,
            mercado         TEXT,
            prob_modelo     FLOAT,
            cuota_apertura  FLOAT,
            cuota_pinnacle  FLOAT,
            ev_apertura     FLOAT,
            cuota_cierre    FLOAT,
            ev_cierre       FLOAT,
            clv             FLOAT,
            resultado       TEXT,
            publicado       BOOLEAN DEFAULT TRUE,
            creado          TIMESTAMP DEFAULT NOW()
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS odds_history (
            id          SERIAL PRIMARY KEY,
            partido     TEXT NOT NULL,
            mercado     TEXT NOT NULL,
            bookmaker   TEXT NOT NULL,
            cuota       FLOAT,
            ts          TIMESTAMP DEFAULT NOW()
        );
        """)
        c.commit()
    print("  DB inicializada OK")


def guardar_pick(fecha, partido, liga, mercado, prob_modelo,
                 cuota_apertura, cuota_pinnacle=None):
    ev = round((prob_modelo / 100) * cuota_apertura - 1, 4) if cuota_apertura else None
    with _conn() as c:
        cur = c.cursor()
        cur.execute("""
            INSERT INTO picks (fecha, partido, liga, mercado, prob_modelo,
                               cuota_apertura, cuota_pinnacle, ev_apertura)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (fecha, partido, liga, mercado, prob_modelo,
              cuota_apertura, cuota_pinnacle, ev))
        pick_id = cur.fetchone()[0]
        c.commit()
    return pick_id


def actualizar_cierre(partido, mercado, cuota_cierre):
    """Registra la cuota de cierre y calcula CLV."""
    with _conn() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT id, prob_modelo, cuota_apertura
            FROM picks WHERE partido=%s AND mercado=%s
            ORDER BY creado DESC LIMIT 1
        """, (partido, mercado))
        row = cur.fetchone()
        if not row:
            return
        pick_id, prob, q_open = row
        ev_cierre = round((prob / 100) * cuota_cierre - 1, 4) if cuota_cierre else None
        clv = round(cuota_cierre - q_open, 4) if (cuota_cierre and q_open) else None
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


def resumen_clv(dias=30):
    """Retorna métricas de CLV de los últimos N días."""
    with _conn() as c:
        cur = c.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                ROUND(AVG(ev_apertura)::numeric, 3) AS ev_promedio,
                ROUND(AVG(clv)::numeric, 3)         AS clv_promedio,
                SUM(CASE WHEN resultado='win' THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN resultado='loss' THEN 1 ELSE 0 END) AS losses
            FROM picks
            WHERE fecha >= NOW() - INTERVAL '%s days'
              AND resultado IS NOT NULL
        """, (dias,))
        return cur.fetchone()


def guardar_odds_history(partido, mercado, bookmaker, cuota):
    with _conn() as c:
        cur = c.cursor()
        cur.execute("""
            INSERT INTO odds_history (partido, mercado, bookmaker, cuota)
            VALUES (%s,%s,%s,%s)
        """, (partido, mercado, bookmaker, cuota))
        c.commit()


if __name__ == "__main__":
    inicializar()
    print("Tablas creadas OK")
