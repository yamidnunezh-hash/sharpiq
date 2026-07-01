# -*- coding: utf-8 -*-
"""
SharpIQ — Modelo financiero 🦈💰
Decidir precio y comisiones con NÚMEROS, no intuición (paso previo al programa
de Partners, según la Visión Estratégica 2026).

Responde: coste real por usuario, margen, break-even, cuánto puede pagarse a un
Partner sin comprometer la empresa, y cuántos clientes necesita un Partner para
que le resulte atractivo.

⚠️  Todos los SUPUESTOS de abajo son estimaciones para VALIDAR con Yamid.
    Cambia los números y vuelve a correr:  python modelo_financiero.py
"""

# ════════════════════════════════════════════════════════════════════════
#  SUPUESTOS  (⚠️ VALIDAR — son estimaciones, no datos confirmados)
# ════════════════════════════════════════════════════════════════════════
TRM = 4000                      # COP por USD (para mostrar en pesos)

# --- Costos FIJOS mensuales (no dependen del # de usuarios) en USD ---
COSTOS_FIJOS = {
    "The Odds API":     30.0,   # ⚠️ VALIDAR tu plan real
    "API-Football":     25.0,   # ⚠️ VALIDAR tu plan real
    "Railway (API+DB)": 10.0,   # ⚠️ VALIDAR
    "Dominio+otros":     2.0,   # amortizado
    # Anthropic (Mako) NO va aquí: es variable por uso (abajo)
}

# --- Costo VARIABLE por usuario Pro activo / mes (USD) ---
MAKO_PREGUNTAS_MES   = 150      # ⚠️ VALIDAR uso real promedio (no todos usan 20/día)
MAKO_COSTO_PREGUNTA  = 15 / TRM # ~15 COP/pregunta (Haiku) -> USD
COMISION_PAGO_PCT     = 0.05    # ⚠️ MercadoPago Colombia ~5% (+ IVA). VALIDAR

# --- Precio e ingresos ---
PRECIOS_A_PROBAR = [15, 30, 45, 60]   # USD/mes (el doc dice: NO fijar 60 aún)

# --- Programa de Partners ---
COMISION_PARTNER_PCT = 0.25     # % del pago mensual, RECURRENTE mientras el cliente renueve
PARTNER_INGRESO_META = 500      # USD/mes que haría "atractivo" ser Partner (⚠️ VALIDAR)

# --- Escenarios de crecimiento (# usuarios Pro pagando) ---
ESCENARIOS_USUARIOS = [10, 50, 100, 500]


# ════════════════════════════════════════════════════════════════════════
#  CÁLCULOS
# ════════════════════════════════════════════════════════════════════════
FIJOS_TOTAL   = sum(COSTOS_FIJOS.values())
MAKO_VARIABLE = MAKO_PREGUNTAS_MES * MAKO_COSTO_PREGUNTA


def economia_unitaria(precio, con_partner):
    """Margen de contribución por usuario/mes (USD). con_partner=True descuenta comisión."""
    fee     = precio * COMISION_PAGO_PCT
    partner = precio * COMISION_PARTNER_PCT if con_partner else 0.0
    costo_u = fee + partner + MAKO_VARIABLE
    return {
        "precio": precio, "fee_pago": fee, "comision_partner": partner,
        "mako": MAKO_VARIABLE, "costo_total_usuario": costo_u,
        "margen": precio - costo_u,
        "margen_pct": (precio - costo_u) / precio * 100 if precio else 0,
    }


def break_even(precio, con_partner):
    """Cuántos usuarios se necesitan para cubrir los costos fijos."""
    m = economia_unitaria(precio, con_partner)["margen"]
    return (FIJOS_TOTAL / m) if m > 0 else float("inf")


def _cop(usd):
    return f"{usd*TRM:,.0f} COP"


def linea(): print("─" * 68)


def main():
    print("\n🦈  MODELO FINANCIERO SharpIQ  (USD, TRM " + f"{TRM:,}" + " COP/USD)")
    linea()
    print(f"Costos FIJOS/mes: ${FIJOS_TOTAL:.0f}  ({', '.join(f'{k} ${v:.0f}' for k,v in COSTOS_FIJOS.items())})")
    print(f"Costo Mako/usuario/mes: ${MAKO_VARIABLE:.2f}  ({MAKO_PREGUNTAS_MES} preg × ~15 COP)")
    print(f"Comisión pago: {COMISION_PAGO_PCT*100:.0f}%  |  Comisión Partner: {COMISION_PARTNER_PCT*100:.0f}% recurrente")

    # 1) ECONOMÍA POR USUARIO según precio
    print("\n💵  MARGEN POR USUARIO/MES  (venta directa, SIN partner)")
    linea()
    print(f"{'Precio':>7}{'Costo/usr':>11}{'Margen':>10}{'Margen%':>9}{'Break-even':>12}")
    for p in PRECIOS_A_PROBAR:
        e = economia_unitaria(p, con_partner=False)
        be = break_even(p, con_partner=False)
        print(f"${p:>6}{e['costo_total_usuario']:>10.2f}${e['margen']:>8.2f}"
              f"{e['margen_pct']:>8.0f}%{be:>10.0f} u")

    print("\n💵  MARGEN POR USUARIO/MES  (vendido por un PARTNER, comisión recurrente)")
    linea()
    print(f"{'Precio':>7}{'Comis.Part':>12}{'Costo/usr':>11}{'Margen SIQ':>12}{'Margen%':>9}")
    for p in PRECIOS_A_PROBAR:
        e = economia_unitaria(p, con_partner=True)
        print(f"${p:>6}{e['comision_partner']:>11.2f}{e['costo_total_usuario']:>11.2f}"
              f"${e['margen']:>10.2f}{e['margen_pct']:>8.0f}%")

    # 2) ESCENARIOS DE CRECIMIENTO (mezcla: mitad directa, mitad por partner)
    print("\n📈  ESCENARIOS  (asumiendo 50% ventas directas / 50% por Partner)")
    linea()
    for p in PRECIOS_A_PROBAR:
        m_dir = economia_unitaria(p, False)["margen"]
        m_par = economia_unitaria(p, True)["margen"]
        m_mix = (m_dir + m_par) / 2
        print(f"\n  Precio ${p}/mes  (margen mezcla ${m_mix:.2f}/usuario):")
        print(f"    {'Usuarios':>9}{'Ingreso':>11}{'Ganancia neta':>15}{'/mes COP':>16}")
        for n in ESCENARIOS_USUARIOS:
            ingreso = n * p
            ganancia = n * m_mix - FIJOS_TOTAL
            print(f"    {n:>9}{ingreso:>10.0f}${ganancia:>13.0f}   {_cop(ganancia):>15}")

    # 3) ¿ATRACTIVO PARA EL PARTNER?
    print("\n🤝  ¿CUÁNTOS CLIENTES NECESITA UN PARTNER?")
    linea()
    print(f"Meta de ingreso del Partner: ${PARTNER_INGRESO_META}/mes ({_cop(PARTNER_INGRESO_META)})")
    print(f"{'Precio':>7}{'Comis/cliente':>15}{'Clientes p/ meta':>18}")
    for p in PRECIOS_A_PROBAR:
        com_cli = p * COMISION_PARTNER_PCT
        clientes = PARTNER_INGRESO_META / com_cli if com_cli else float("inf")
        print(f"${p:>6}{com_cli:>13.2f} USD{clientes:>13.0f} clientes")

    print("\n📌 Lectura: margen% sano en SaaS > 60-70%. Si el Partner necesita")
    print("   demasiados clientes para su meta, sube el precio o la comisión.")
    print("   ⚠️ Ajusta los SUPUESTOS arriba con tus costos REALES y vuelve a correr.\n")


if __name__ == "__main__":
    main()
