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

        -- Verificación de correo (anti-abuso del trial de Mako). Default TRUE => los
        -- usuarios EXISTENTES quedan verificados (grandfather); el registro nuevo pone
        -- FALSE solo si el SMTP está configurado (para poder enviar el correo).
        ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email_verificado   BOOLEAN DEFAULT TRUE;
        ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS token_verificacion TEXT;

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

        -- Uso de Mako (asistente IA): controla el trial free (10 preguntas o 7 dias)
        -- y el limite diario de los VIP.
        CREATE TABLE IF NOT EXISTS mako_uso (
            usuario_id      INTEGER PRIMARY KEY REFERENCES usuarios(id),
            total_usos      INTEGER DEFAULT 0,
            inicio_trial    TIMESTAMP,
            usos_hoy        INTEGER DEFAULT 0,
            fecha_hoy       DATE
        );

        -- ── MOTOR DE PARTNERS (comisiones recurrentes + payouts cripto) ──────────
        -- Un Partner es un usuario habilitado para ganar comisión RECURRENTE por los
        -- clientes que trae. Idempotencia dura (payouts cripto son irreversibles):
        --   comisiones.pago_id UNIQUE  -> una comisión por pago (webhook reenviado no duplica)
        --   payouts UNIQUE(partner_id, periodo) -> un solo lote de pago por periodo
        CREATE TABLE IF NOT EXISTS partners (
            id              SERIAL PRIMARY KEY,
            usuario_id      INTEGER UNIQUE NOT NULL REFERENCES usuarios(id),
            es_partner      BOOLEAN DEFAULT TRUE,
            pct_comision    NUMERIC(5,2) DEFAULT 25.00,   -- % de comisión recurrente
            crypto_red      TEXT,                          -- 'BSC' | 'POLYGON' | 'TRON'...
            crypto_address  TEXT,                          -- wallet del partner
            min_payout_usd  NUMERIC(10,2) DEFAULT 20.00,   -- umbral mínimo para pagar
            activo          BOOLEAN DEFAULT TRUE,
            fecha_alta      TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS comisiones (
            id              SERIAL PRIMARY KEY,
            partner_id      INTEGER NOT NULL REFERENCES partners(id),
            cliente_id      INTEGER REFERENCES usuarios(id),   -- el cliente que pagó
            pago_id         INTEGER REFERENCES pagos(id),       -- el pago que la generó
            periodo         TEXT,                               -- ej. '2026-07'
            monto_usd       NUMERIC(10,2) NOT NULL,
            moneda          TEXT DEFAULT 'USD',
            estado          TEXT DEFAULT 'pendiente',           -- pendiente | pagada | anulada
            fecha           TIMESTAMP DEFAULT NOW()
        );
        -- Idempotencia: una sola comisión por pago (si el webhook se reenvía, no duplica).
        CREATE UNIQUE INDEX IF NOT EXISTS comisiones_pago_id_uniq ON comisiones (pago_id);

        CREATE TABLE IF NOT EXISTS payouts (
            id                SERIAL PRIMARY KEY,
            partner_id        INTEGER NOT NULL REFERENCES partners(id),
            periodo           TEXT NOT NULL,                    -- lote por periodo
            monto_total_usd   NUMERIC(12,2) NOT NULL,
            crypto_red        TEXT,
            crypto_address    TEXT,
            txid              TEXT,                             -- hash de la transacción on-chain
            estado            TEXT DEFAULT 'pendiente',         -- pendiente | aprobado | enviado | completado | fallido
            creado            TIMESTAMP DEFAULT NOW(),
            UNIQUE(partner_id, periodo)
        );
        """)
    print("[OK] DB inicializada — tablas listas")
