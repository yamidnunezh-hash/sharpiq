# -*- coding: utf-8 -*-
"""
Verificación PRIVADA del sistema de referidos (mes gratis).
Corre el código de PRODUCCIÓN real (_registrar_pago / _activar_vip) contra la
DB de Railway, con usuarios de prueba que se crean y BORRAN al final.

Ejecutar (inyecta DATABASE_URL de Railway):
    railway run python verificar_referidos.py

No toca usuarios reales: todo usa el prefijo de email "_qa_ref_".
"""
import os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "sharpiq-engine"))

from api.db import db, inicializar_db         # noqa: E402
from api.pagos import _registrar_pago, _activar_vip  # noqa: E402

PREFIJO = "_qa_ref_"
OK = "✓"; FAIL = "✗"
_fallos = []

def chk(nombre, cond):
    print(f"  [{OK if cond else FAIL}] {nombre}")
    if not cond:
        _fallos.append(nombre)

def _mk_user(cur, etiqueta, codigo=None):
    cur.execute("""INSERT INTO usuarios (email, nombre, password_hash, plan, codigo_ref)
                   VALUES (%s,%s,'x','free',%s) RETURNING id""",
                (f"{PREFIJO}{etiqueta}@sharpiq.test", f"QA {etiqueta}", codigo))
    return cur.fetchone()["id"]

def _link(cur, referidor_id, referido_id):
    cur.execute("""INSERT INTO referidos (referidor_id, referido_id)
                   VALUES (%s,%s) ON CONFLICT (referido_id) DO NOTHING""",
                (referidor_id, referido_id))

def _fin(uid):
    with db() as c:
        cur = c.cursor()
        cur.execute("""SELECT fecha_fin FROM suscripciones
                       WHERE usuario_id=%s AND estado='active'""", (uid,))
        r = cur.fetchone()
        return r["fecha_fin"] if r else None

def _ref(referido_id):
    with db() as c:
        cur = c.cursor()
        cur.execute("""SELECT meses_gratis_ganados AS g, meses_gratis_aplicados AS a
                       FROM referidos WHERE referido_id=%s""", (referido_id,))
        return cur.fetchone()

def _pago(pid):
    return {"id": pid, "status": "approved", "transaction_amount": 15,
            "currency_id": "USD", "payer": {"email": f"{PREFIJO}payer@sharpiq.test"}}

def _dias(a, b):
    return None if (a is None or b is None) else round((a - b).total_seconds() / 86400)


def main():
    print("=== Asegurando esquema (idempotente) ===")
    inicializar_db()   # aplica meses_gratis_* + indice unico si faltan
    print("=== Creando usuarios de prueba ===")
    with db() as c:
        cur = c.cursor()
        R  = _mk_user(cur, "R",  "QAREF0001")   # referidor con VIP activo
        D  = _mk_user(cur, "D",  "QAREF0003")   # referido de R
        R2 = _mk_user(cur, "R2", "QAREF0002")   # referidor SIN VIP
        D2 = _mk_user(cur, "D2", "QAREF0004")   # referido de R2
        _link(cur, R, D)
        _link(cur, R2, D2)
    print(f"  R={R} D={D} | R2={R2} D2={D2}")

    try:
        # ── ESCENARIO A: referidor con VIP activo → +30 días al instante ──
        print("\n=== A) Referidor con VIP activo ===")
        _activar_vip(R, "SUB-R", "r@test")          # R activa su propio VIP (now+30)
        fin_R_antes = _fin(R)
        _registrar_pago(D, _pago("PAY-D-1"))        # D paga (flujo real)
        fin_R_despues = _fin(D)  # de D, para confirmar que D quedó VIP
        chk("D quedó VIP (tiene fecha_fin)", _fin(D) is not None)
        d = _dias(_fin(R), fin_R_antes)
        chk(f"R recibió +30 días (delta={d})", d is not None and 28 <= d <= 32)
        rr = _ref(D)
        chk("referidos(D): ganados=1, aplicados=1", rr["g"] == 1 and rr["a"] == 1)

        # ── ESCENARIO B: renovación del MISMO referido NO vuelve a sumar ──
        print("\n=== B) Renovación del referido NO duplica ===")
        fin_R_pre_renov = _fin(R)
        _registrar_pago(D, _pago("PAY-D-2"))        # D renueva (nuevo payment id)
        d2 = _dias(_fin(R), fin_R_pre_renov)
        chk(f"R NO cambió por la renovación (delta={d2})", d2 == 0)
        rr = _ref(D)
        chk("referidos(D) sigue ganados=1, aplicados=1", rr["g"] == 1 and rr["a"] == 1)

        # ── ESCENARIO C: referidor SIN VIP → pendiente, se aplica al reactivar ──
        print("\n=== C) Referidor sin VIP → pendiente y luego aplicado ===")
        _registrar_pago(D2, _pago("PAY-D2-1"))      # D2 paga; R2 no tiene VIP
        rr = _ref(D2)
        chk("referidos(D2): ganados=1, aplicados=0 (pendiente)", rr["g"] == 1 and rr["a"] == 0)
        chk("R2 aún sin suscripción activa", _fin(R2) is None)
        _activar_vip(R2, "SUB-R2", "r2@test")        # R2 activa VIP → aplica pendiente
        # base 30 + 30 pendiente ≈ 60 días desde ahora
        d3 = _dias(_fin(R2), datetime.utcnow())
        chk(f"R2 fecha_fin ≈ now+60 (mes pagado + mes gratis) (delta={d3})", d3 is not None and 58 <= d3 <= 62)
        rr = _ref(D2)
        chk("referidos(D2): aplicados=1 tras reactivar", rr["a"] == 1)

        # ── ESCENARIO D: webhook DUPLICADO no re-activa ──
        print("\n=== D) Webhook duplicado (idempotencia) ===")
        fin_R_pre_dup = _fin(R)
        _registrar_pago(D, _pago("PAY-D-1"))        # MISMO payment id que en A
        d4 = _dias(_fin(R), fin_R_pre_dup)
        chk(f"Pago duplicado NO sumó nada (delta={d4})", d4 == 0)

    finally:
        print("\n=== Limpiando datos de prueba ===")
        with db() as c:
            cur = c.cursor()
            cur.execute("SELECT id FROM usuarios WHERE email LIKE %s", (PREFIJO + "%",))
            ids = [r["id"] for r in cur.fetchall()]
            if ids:
                cur.execute("DELETE FROM pagos WHERE usuario_id = ANY(%s)", (ids,))
                cur.execute("DELETE FROM suscripciones WHERE usuario_id = ANY(%s)", (ids,))
                cur.execute("DELETE FROM referidos WHERE referidor_id = ANY(%s) OR referido_id = ANY(%s)", (ids, ids))
                cur.execute("DELETE FROM usuarios WHERE id = ANY(%s)", (ids,))
            print(f"  Borrados {len(ids)} usuarios de prueba + sus filas.")

    print("\n" + ("=" * 40))
    if _fallos:
        print(f"RESULTADO: {len(_fallos)} FALLO(S) -> {_fallos}")
        sys.exit(1)
    print("RESULTADO: TODO OK ✓ — el sistema de referidos funciona como se espera.")


if __name__ == "__main__":
    main()
