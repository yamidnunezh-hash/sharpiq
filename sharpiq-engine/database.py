# -*- coding: utf-8 -*-
"""
SharpIQ — Base de Datos Local
SQLite: se llena sola cada día, crece para siempre, costo = $0
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sharpiq.db")


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar():
    conn = conectar()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS partidos (
        fixture_id   INTEGER PRIMARY KEY,
        fecha        TEXT,
        liga_id      INTEGER,
        liga_nombre  TEXT,
        local        TEXT,
        visitante    TEXT,
        goles_local  INTEGER,
        goles_visita INTEGER,
        estado       TEXT,
        guardado_en  TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS estadisticas_partido (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        fixture_id            INTEGER,
        equipo                TEXT,
        es_local              INTEGER,
        tiros_puerta          INTEGER,
        tiros_fuera           INTEGER,
        tiros_total           INTEGER,
        tiros_bloqueados      INTEGER,
        corners               INTEGER,
        tarjetas_amarillas    INTEGER,
        tarjetas_rojas        INTEGER,
        faltas                INTEGER,
        posesion              TEXT,
        pases_totales         INTEGER,
        pases_precisos        INTEGER,
        UNIQUE(fixture_id, equipo)
    );

    CREATE TABLE IF NOT EXISTS cuotas_apertura (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        fixture_id      INTEGER,
        fecha_consulta  TEXT,
        cuota_1         REAL,
        cuota_x         REAL,
        cuota_2         REAL,
        cuota_over15    REAL,
        cuota_under15   REAL,
        cuota_over25    REAL,
        cuota_under25   REAL,
        cuota_over35    REAL,
        cuota_under35   REAL,
        cuota_btts_si   REAL,
        cuota_btts_no   REAL,
        UNIQUE(fixture_id)
    );

    CREATE TABLE IF NOT EXISTS promedios_equipo (
        equipo              TEXT PRIMARY KEY,
        liga_id             INTEGER,
        partidos_jugados    INTEGER DEFAULT 0,
        goles_favor_avg     REAL DEFAULT 1.3,
        goles_contra_avg    REAL DEFAULT 1.3,
        tiros_puerta_avg    REAL DEFAULT 3.5,
        tiros_fuera_avg     REAL DEFAULT 3.0,
        corners_avg         REAL DEFAULT 5.0,
        tarjetas_avg        REAL DEFAULT 1.8,
        faltas_avg          REAL DEFAULT 12.0,
        posesion_avg        REAL DEFAULT 50.0,
        forma_reciente      REAL DEFAULT 0.5,
        actualizado_en      TEXT DEFAULT (datetime('now'))
    );
    """)

    conn.commit()
    conn.close()
    print(f"  DB lista: {DB_PATH}")


# ── GUARDAR PARTIDO ─────────────────────────────────────────────
def guardar_partido(fixture_id, fecha, liga_id, liga_nombre, local, visitante,
                    goles_local, goles_visita, estado):
    conn = conectar()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO partidos
            (fixture_id, fecha, liga_id, liga_nombre, local, visitante,
             goles_local, goles_visita, estado)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (fixture_id, fecha, liga_id, liga_nombre, local, visitante,
              goles_local, goles_visita, estado))
        conn.commit()
    finally:
        conn.close()


# ── GUARDAR ESTADÍSTICAS ─────────────────────────────────────────
def guardar_estadisticas(fixture_id, equipo, es_local, stats):
    conn = conectar()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO estadisticas_partido
            (fixture_id, equipo, es_local, tiros_puerta, tiros_fuera,
             tiros_total, tiros_bloqueados, corners, tarjetas_amarillas,
             tarjetas_rojas, faltas, posesion, pases_totales, pases_precisos)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (fixture_id, equipo, es_local,
              stats.get("tiros_puerta", 0),
              stats.get("tiros_fuera", 0),
              stats.get("tiros_total", 0),
              stats.get("tiros_bloqueados", 0),
              stats.get("corners", 0),
              stats.get("tarjetas_amarillas", 0),
              stats.get("tarjetas_rojas", 0),
              stats.get("faltas", 0),
              stats.get("posesion", "50%"),
              stats.get("pases_totales", 0),
              stats.get("pases_precisos", 0)))
        conn.commit()
    finally:
        conn.close()


# ── GUARDAR CUOTAS ───────────────────────────────────────────────
def guardar_cuotas(fixture_id, cuotas):
    from datetime import datetime
    conn = conectar()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO cuotas_apertura
            (fixture_id, fecha_consulta, cuota_1, cuota_x, cuota_2,
             cuota_over15, cuota_under15, cuota_over25, cuota_under25,
             cuota_over35, cuota_under35, cuota_btts_si, cuota_btts_no)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (fixture_id, datetime.now().isoformat(),
              cuotas.get("1"), cuotas.get("X"), cuotas.get("2"),
              cuotas.get("over15"), cuotas.get("under15"),
              cuotas.get("over25"), cuotas.get("under25"),
              cuotas.get("over35"), cuotas.get("under35"),
              cuotas.get("btts_si"), cuotas.get("btts_no")))
        conn.commit()
    finally:
        conn.close()


# ── ACTUALIZAR PROMEDIOS DEL EQUIPO ─────────────────────────────
def actualizar_promedios_equipo(equipo, liga_id):
    conn = conectar()
    try:
        rows = conn.execute("""
            SELECT e.*, p.goles_local, p.goles_visita, p.local
            FROM estadisticas_partido e
            JOIN partidos p ON e.fixture_id = p.fixture_id
            WHERE e.equipo = ? AND p.estado = 'FT'
            ORDER BY p.fecha DESC LIMIT 20
        """, (equipo,)).fetchall()

        if not rows:
            conn.close()
            return

        n = len(rows)
        totals = {k: 0 for k in ["tiros_puerta","tiros_fuera","corners",
                                   "tarjetas_amarillas","faltas","pases_totales"]}
        goles_favor = goles_contra = puntos = 0

        for r in rows:
            for k in totals:
                totals[k] += r[k] or 0
            es_local = r["es_local"]
            gf = r["goles_local"] if es_local else r["goles_visita"]
            gc = r["goles_visita"] if es_local else r["goles_local"]
            gf = gf or 0; gc = gc or 0
            goles_favor += gf; goles_contra += gc
            if gf > gc: puntos += 3
            elif gf == gc: puntos += 1

        forma = round(puntos / (n * 3), 3)

        conn.execute("""
            INSERT OR REPLACE INTO promedios_equipo
            (equipo, liga_id, partidos_jugados, goles_favor_avg, goles_contra_avg,
             tiros_puerta_avg, tiros_fuera_avg, corners_avg, tarjetas_avg,
             faltas_avg, forma_reciente, actualizado_en)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
        """, (equipo, liga_id, n,
              round(goles_favor/n, 2), round(goles_contra/n, 2),
              round(totals["tiros_puerta"]/n, 2),
              round(totals["tiros_fuera"]/n, 2),
              round(totals["corners"]/n, 2),
              round(totals["tarjetas_amarillas"]/n, 2),
              round(totals["faltas"]/n, 2),
              forma))
        conn.commit()
    finally:
        conn.close()


# ── LEER PROMEDIOS PARA EL MOTOR ────────────────────────────────
def get_promedios(equipo):
    conn = conectar()
    try:
        row = conn.execute(
            "SELECT * FROM promedios_equipo WHERE equipo = ?", (equipo,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ── RESUMEN DE LA DB ─────────────────────────────────────────────
def resumen():
    conn = conectar()
    try:
        partidos   = conn.execute("SELECT COUNT(*) FROM partidos WHERE estado='FT'").fetchone()[0]
        equipos    = conn.execute("SELECT COUNT(*) FROM promedios_equipo").fetchone()[0]
        stats      = conn.execute("SELECT COUNT(*) FROM estadisticas_partido").fetchone()[0]
        cuotas     = conn.execute("SELECT COUNT(*) FROM cuotas_apertura").fetchone()[0]
        ligas      = conn.execute("SELECT COUNT(DISTINCT liga_nombre) FROM partidos").fetchone()[0]
        print(f"\n  SharpIQ DB:")
        print(f"  Partidos guardados : {partidos}")
        print(f"  Equipos con perfil : {equipos}")
        print(f"  Registros de stats : {stats}")
        print(f"  Cuotas de apertura : {cuotas}")
        print(f"  Ligas cubiertas    : {ligas}")
    finally:
        conn.close()


if __name__ == "__main__":
    inicializar()
    resumen()
