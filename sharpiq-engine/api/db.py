"""
SharpIQ — Conexión PostgreSQL Railway
"""
import os
import sys
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import DATABASE_PUBLIC_URL
    DB_URL = DATABASE_PUBLIC_URL
except ImportError:
    DB_URL = os.environ.get("DATABASE_URL", "")


def get_conn():
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)


@contextmanager
def db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def inicializar_db():
    """Crea tablas si no existen."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id              SERIAL PRIMARY KEY,
            email           TEXT UNIQUE NOT NULL,
            nombre          TEXT NOT NULL,
            password_hash   TEXT NOT NULL,
            plan            TEXT NOT NULL DEFAULT 'free',
            referido_por    INTEGER REFERENCES usuarios(id),
            codigo_ref      TEXT UNIQUE,
            fecha_registro  TIMESTAMP DEFAULT NOW(),
            activo          BOOLEAN DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS suscripciones (
            id                  SERIAL PRIMARY KEY,
            usuario_id          INTEGER REFERENCES usuarios(id),
            plan                TEXT NOT NULL,
            precio_usd          NUMERIC(10,2),
            fecha_inicio        TIMESTAMP DEFAULT NOW(),
            fecha_fin           TIMESTAMP,
            mp_subscription_id  TEXT,
            mp_payer_email      TEXT,
            estado              TEXT DEFAULT 'active',
            UNIQUE(usuario_id, estado)
        );

        CREATE TABLE IF NOT EXISTS pagos (
            id              SERIAL PRIMARY KEY,
            usuario_id      INTEGER REFERENCES usuarios(id),
            monto           NUMERIC(10,2),
            moneda          TEXT DEFAULT 'USD',
            mp_payment_id   TEXT,
            mp_status       TEXT,
            concepto        TEXT,
            fecha           TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS referidos (
            id              SERIAL PRIMARY KEY,
            referidor_id    INTEGER REFERENCES usuarios(id),
            referido_id     INTEGER REFERENCES usuarios(id),
            meses_gratis_ganados    INTEGER DEFAULT 0,
            meses_gratis_aplicados  INTEGER DEFAULT 0,
            fecha           TIMESTAMP DEFAULT NOW(),
            UNIQUE(referido_id)
        );
        -- Migracion defensiva: si la tabla ya existia con el esquema viejo ($ comision),
        -- agrega las columnas nuevas sin tocar las viejas (no hay saldos que migrar).
        ALTER TABLE referidos ADD COLUMN IF NOT EXISTS meses_gratis_ganados   INTEGER DEFAULT 0;
        ALTER TABLE referidos ADD COLUMN IF NOT EXISTS meses_gratis_aplicados INTEGER DEFAULT 0;
        -- Idempotencia de pagos: evita doble activación/recompensa si MercadoPago
        -- reenvía el mismo webhook (mismo mp_payment_id).
        CREATE UNIQUE INDEX IF NOT EXISTS pagos_mp_payment_id_uniq ON pagos (mp_payment_id);

        CREATE TABLE IF NOT EXISTS picks_publicados (
            id              SERIAL PRIMARY KEY,
            fecha           TEXT NOT NULL,
            partido         TEXT NOT NULL,
            liga            TEXT,
            prediccion      TEXT NOT NULL,
            cuota           TEXT,
            hora            TEXT,
            emoji           TEXT DEFAULT '⚽',
            plan_requerido  TEXT DEFAULT 'vip',
            resultado       TEXT DEFAULT 'pendiente',
            ev_pinn         NUMERIC(6,2),
            publicado_en    TIMESTAMP DEFAULT NOW()
        );
        """)
    print("[OK] DB inicializada — tablas listas")
