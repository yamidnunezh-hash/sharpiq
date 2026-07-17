# -*- coding: utf-8 -*-
"""
SharpIQ — Mapa CASA -> PAISES donde el usuario puede abrir cuenta y operar.

POR QUE EXISTE ESTE ARCHIVO (idea de Yamid, 16-jul-26):
Un arbitraje entre FanDuel (solo USA) y BoyleSports (solo UK) es INUTIL para un
colombiano: no puede abrir cuenta en ninguna de las dos. El arbitraje SOLO sirve
si el cliente puede operar en TODAS las casas involucradas. Por eso el producto
se sectoriza: "Arbitraje Colombia", "Arbitraje Mexico", "Arbitraje Espana"...

REGLA: un arb es valido para el pais P solo si TODAS sus casas estan en CASAS[P].

OJO — VERIFICAR CON YAMID: esta tabla es la mejor aproximacion, pero las
licencias cambian seguido (Brasil se regulo en 2025, Peru en 2024...). Yamid
conoce el terreno (apuesta en Rushbet). Antes de vender, confirmar pais por pais.
Los nombres deben coincidir EXACTO con el campo `title` de The Odds API.
"""

# Nombres tal cual los devuelve The Odds API (bookmaker["title"])
CASAS = {
    # ── COLOMBIA (mercado licenciado por Coljuegos) ──────────────────
    # PROBLEMA: casi ninguna casa de The Odds API tiene licencia en CO.
    # Las legales (Wplay, BetPlay, Rushbet, Zamba, YaJuego) NO estan en la API.
    "CO": [
        "Betsson",
        "Codere (IT)",        # Codere opera en CO, pero la API solo trae la version IT
        "Betano (UK)",        # Betano opera en CO como Betano.co
        # FALTAN (no estan en The Odds API): Wplay, BetPlay, Rushbet, Zamba, YaJuego
    ],

    # ── MEXICO (mercado mas abierto) ─────────────────────────────────
    "MX": [
        "1xBet",
        "Betsson",
        "Codere (IT)",        # Codere.mx
        "Betano (UK)",        # Betano.mx
        "Betway",
        "bet365",             # opera en MX (verificar si la API lo trae)
        # FALTAN: Caliente, Strendus, Winpot
    ],

    # ── ESPANA (mercado licenciado, VARIAS casas de la API SI operan) ─
    "ES": [
        "888sport",
        "Betfair",
        "Betway",
        "Codere (IT)",        # Codere.es
        "William Hill",
        "Winamax (FR)",       # Winamax.es
        "Marathon Bet",
        "LeoVegas",
        "Betsson",
    ],

    # ── BRASIL (REGULADO desde 2025 — mercado grande y abierto) ──────
    "BR": [
        "Betano (UK)",        # Betano.bet.br — lider en Brasil
        "Betfair",
        "Betsson",
        "Betway",
        "1xBet",
        # FALTAN: KTO, Superbet, Esportes da Sorte
    ],

    # ── CHILE / PERU / ECUADOR (mercado gris/abierto) ────────────────
    "CL": ["Coolbet", "Betsson", "1xBet", "Betano (UK)", "Betway"],
    "PE": ["Coolbet", "Betsson", "1xBet", "Betano (UK)", "Betfair"],
    "EC": ["Coolbet", "Betsson", "1xBet"],

    # ── ARGENTINA (licencia por provincia) ───────────────────────────
    "AR": ["Betsson", "Betano (UK)", "1xBet", "Codere (IT)"],

    # ── GLOBAL / sharp (sirve de referencia, no todos pueden operar) ──
    "GLOBAL": ["Pinnacle", "1xBet", "Betfair", "Marathon Bet"],
}

NOMBRE_PAIS = {
    "CO": "Colombia", "MX": "Mexico", "ES": "Espana", "BR": "Brasil",
    "CL": "Chile", "PE": "Peru", "EC": "Ecuador", "AR": "Argentina",
}


def casas_de(pais):
    """Lista de casas operables en ese pais. 'GLOBAL' = todas las conocidas."""
    if pais == "TODAS":
        return sorted({c for v in CASAS.values() for c in v})
    return CASAS.get(pais.upper(), [])


def es_operable(casa, pais):
    """True si el cliente de ese pais puede apostar en esa casa."""
    return casa in casas_de(pais)


def paises_disponibles():
    return [p for p in CASAS if p != "GLOBAL"]
