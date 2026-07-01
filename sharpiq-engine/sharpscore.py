# -*- coding: utf-8 -*-
"""
SharpScore™ — el sello de calidad de SharpIQ.

Una puntuación propia de 0 a 100 para cada pick, que combina los ingredientes
que el motor YA calcula:
  - Probabilidad del modelo (Poisson / Dixon-Coles)      -> 50%  (qué tan seguro)
  - Valor real vs el mercado (EV vs Pinnacle)            -> 25%  (cuánto valor)
  - Confianza / liquidez (tier del pick)                 -> 25%  (qué tan sólido)

El número es la MARCA de SharpIQ: "SharpScore 84/100 — Máxima confianza".
Un apostador profesional se llama "un sharp" -> este número es su ventaja.
"""

# Cada tier ya trae dentro el blend por liquidez del motor -> lo usamos como
# señal de confianza/calidad de la casa.
_TIER_CONF = {"seguro": 90, "principal": 75, "alto_valor": 70}

# Pesos de la fórmula (suman 1.0)
_W_PROB = 0.50   # probabilidad de acertar (seguridad)
_W_EV   = 0.25   # valor esperado vs mercado
_W_TIER = 0.25   # confianza / liquidez


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def calcular(prob=0, ev=0, tier="principal"):
    """Devuelve el SharpScore (int 1-99) de un pick.

    prob: probabilidad del modelo en % (0-100).
    ev:   valor esperado vs Pinnacle en % (ej. 5 = +5%). Puede ser 0/None.
    tier: 'seguro' | 'principal' | 'alto_valor'.
    """
    try:
        prob = float(prob or 0)
    except (TypeError, ValueError):
        prob = 0.0
    try:
        ev = float(ev or 0)
    except (TypeError, ValueError):
        ev = 0.0

    prob_c = _clamp(prob, 0, 100)
    # EV normalizado a 0-100: 0% -> 50, +14% -> 100, -14% -> 0
    ev_c   = _clamp(50 + ev * 3.5, 0, 100)
    tier_c = _TIER_CONF.get(str(tier).lower().strip(), 65)

    score = _W_PROB * prob_c + _W_EV * ev_c + _W_TIER * tier_c
    return int(_clamp(round(score), 1, 99))


def nivel(score):
    """Devuelve (etiqueta, estrellas) para un SharpScore."""
    score = int(score or 0)
    if score >= 80:
        return ("Máxima confianza", "★★★★★")
    if score >= 70:
        return ("Alta confianza", "★★★★")
    if score >= 60:
        return ("Sólida", "★★★")
    if score >= 50:
        return ("Moderada", "★★")
    return ("Especulativa", "★")


def color(score):
    """Color sugerido para el badge segun el SharpScore."""
    score = int(score or 0)
    if score >= 80:
        return "#22C55E"   # verde
    if score >= 70:
        return "#00C8FF"   # cyan
    if score >= 60:
        return "#7B5CF0"   # morado
    return "#F59E0B"       # ámbar


if __name__ == "__main__":
    # Prueba rápida con ejemplos reales
    for p, e, t in [(69, 2, "seguro"), (52, 5, "principal"),
                    (32, 12, "alto_valor"), (78, 4, "seguro")]:
        s = calcular(p, e, t)
        n, stars = nivel(s)
        print(f"  prob={p}% ev={e}% {t:11} -> SharpScore {s}/100 · {n} {stars}")
