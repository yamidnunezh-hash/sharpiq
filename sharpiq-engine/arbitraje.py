# -*- coding: utf-8 -*-
"""
SharpIQ — Detector de Arbitraje
Escanea las cuotas de múltiples casas de apuestas y detecta oportunidades
donde la suma de probabilidades implícitas es menor a 100% (ganancia garantizada).

Uso: se llama desde motor.py al final del reporte del día.
Envía alerta inmediata a Yamid cuando detecta arbitraje real.
"""
import os, sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


# ── DETECTOR PRINCIPAL ────────────────────────────────────────────

def detectar_arbitraje_partido(partido_odds):
    """
    partido_odds: dict con estructura de the-odds-api
    Devuelve dict con detalles si hay arbitraje, None si no.
    """
    home = partido_odds.get("home_team", "")
    away = partido_odds.get("away_team", "")

    # Recopilar mejor cuota de CADA casa para cada resultado
    mejor_1 = {"cuota": 0, "casa": ""}
    mejor_x = {"cuota": 0, "casa": ""}
    mejor_2 = {"cuota": 0, "casa": ""}

    for bm in partido_odds.get("bookmakers", []):
        nombre_casa = bm.get("title", "")
        for market in bm.get("markets", []):
            if market.get("key") != "h2h":
                continue
            prices = {o["name"]: o["price"] for o in market.get("outcomes", [])}
            c1 = prices.get(home, 0)
            cx = next((v for k, v in prices.items() if k not in [home, away]), 0)
            c2 = prices.get(away, 0)

            if c1 > mejor_1["cuota"]:
                mejor_1 = {"cuota": c1, "casa": nombre_casa}
            if cx > mejor_x["cuota"]:
                mejor_x = {"cuota": cx, "casa": nombre_casa}
            if c2 > mejor_2["cuota"]:
                mejor_2 = {"cuota": c2, "casa": nombre_casa}

    if not all([mejor_1["cuota"], mejor_x["cuota"], mejor_2["cuota"]]):
        return None

    # Suma de probabilidades implícitas
    impl_1 = 1 / mejor_1["cuota"]
    impl_x = 1 / mejor_x["cuota"]
    impl_2 = 1 / mejor_2["cuota"]
    suma_impl = impl_1 + impl_x + impl_2

    if suma_impl >= 1.0:
        return None   # No hay arbitraje

    # Ganancia garantizada (%)
    profit_pct = round((1 / suma_impl - 1) * 100, 2)

    # Stakes óptimas para un bankroll de 100 unidades
    bankroll = 100
    stake_1 = round((impl_1 / suma_impl) * bankroll, 2)
    stake_x = round((impl_x / suma_impl) * bankroll, 2)
    stake_2 = round((impl_2 / suma_impl) * bankroll, 2)

    return {
        "local":    home,
        "visitante": away,
        "profit_pct": profit_pct,
        "suma_impl":  round(suma_impl * 100, 2),
        "1": {"cuota": mejor_1["cuota"], "casa": mejor_1["casa"], "stake": stake_1},
        "X": {"cuota": mejor_x["cuota"], "casa": mejor_x["casa"], "stake": stake_x},
        "2": {"cuota": mejor_2["cuota"], "casa": mejor_2["casa"], "stake": stake_2},
    }


def escanear_arbitraje(partidos_odds_lista):
    """
    Escanea una lista de partidos de the-odds-api.
    Devuelve lista de oportunidades ordenadas por profit_pct desc.
    """
    oportunidades = []
    for p in partidos_odds_lista:
        arb = detectar_arbitraje_partido(p)
        if arb:
            oportunidades.append(arb)

    oportunidades.sort(key=lambda x: x["profit_pct"], reverse=True)
    return oportunidades


def construir_alerta_arbitraje(arb):
    """Construye el texto de la alerta Telegram."""
    return (
        f"⚡ <b>ARBITRAJE DETECTADO — SharpIQ</b>\n\n"
        f"⚽ <b>{arb['local']} vs {arb['visitante']}</b>\n\n"
        f"💰 <b>Ganancia garantizada: +{arb['profit_pct']}%</b>\n"
        f"📊 Suma impl.: {arb['suma_impl']}% (debe ser &lt;100%)\n\n"
        f"🏦 <b>Stakes por 100 unidades:</b>\n"
        f"• 1 {arb['local']}: {arb['1']['stake']}u @ <b>{arb['1']['cuota']}</b> [{arb['1']['casa']}]\n"
        f"• X Empate: {arb['X']['stake']}u @ <b>{arb['X']['cuota']}</b> [{arb['X']['casa']}]\n"
        f"• 2 {arb['visitante']}: {arb['2']['stake']}u @ <b>{arb['2']['cuota']}</b> [{arb['2']['casa']}]\n\n"
        f"⏰ <b>Actúa rápido — las cuotas cambian</b>\n\n"
        f"<i>SharpIQ — La ventaja inteligente</i>"
    )


def correr_scan(cuotas_por_liga: dict):
    """
    Punto de entrada desde motor.py.
    cuotas_por_liga: {sport_key: [lista_partidos_odds]}
    Devuelve número de arbitrajes encontrados y envía alertas.
    """
    from telegram_alertas import enviar_aviso_yamid

    todos = []
    for lista in cuotas_por_liga.values():
        if isinstance(lista, list):
            todos.extend(lista)

    oportunidades = escanear_arbitraje(todos)

    if not oportunidades:
        print("  Arbitraje: sin oportunidades hoy")
        return 0

    for arb in oportunidades:
        texto = construir_alerta_arbitraje(arb)
        enviar_aviso_yamid(texto)
        print(f"  ⚡ ARBITRAJE: {arb['local']} vs {arb['visitante']} → +{arb['profit_pct']}%")

    return len(oportunidades)
