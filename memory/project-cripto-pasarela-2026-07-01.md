---
name: project-cripto-pasarela-2026-07-01
description: Plan/investigación para incorporar pagos cripto (USDT/USDC) a SharpIQ — cobrar suscripciones + pagar comisiones a Partners + ganarse el fee de transacción. Siguiente gran bloque tras Mako.
metadata:
  type: project
---

# Cripto para SharpIQ — plan (2026-07-01)

Viene de la Visión Estratégica 2026 (ver [[project-sharpiq-os-vision]]). Tras cerrar Mako, el
siguiente gran bloque es la pasarela cripto. Yamid quiere que también **nos ganemos el fee de
transacción** (negocio sobre negocio).

## Dos flujos
1. **COBRAR** suscripciones en USDT/USDC a clientes LatAm (sobre todo Colombia).
2. **PAGAR** comisiones automáticas a la wallet de cada Partner vía API (mass payouts) — requisito duro.

## Decisiones madre (mi análisis técnico)
- Moneda: **USDT/USDC** (stablecoins ~$1, sin volatilidad). Red: **Tron TRC-20** para USDT (fees de
  red bajísimos, la más usada en LatAm); USDC en Polygon/Base.
- **Pasarela (recomendado) vs self-custody**: pasarela maneja seguridad/conversión/compliance y da
  API para cobrar Y pagar; self-custody = manejar llaves privadas = riesgo alto para un principiante.
- Se enchufa PARALELO a MercadoPago: cobrar = invoice + webhook/IPN -> activa VIP (igual que el
  webhook MP que ya existe); pagar = tabla `referidos` -> job suma comisiones -> API payout -> marca pagado.

## Monetizar el fee (lo que pidió Yamid) — SÍ es viable
Cripto cuesta ~0.5-1% vs MercadoPago ~5% -> el ahorro financia una comisión propia. Formas:
(a) marcar el precio con recargo (spread), (b) descontar un fee del payout al Partner. Aún sale más
barato que MP para todos.

## Estado: INVESTIGACIÓN PROFUNDA corriendo (deep-research, background)
Lanzada 2026-07-01. Compara NOWPayments, CoinPayments, Bitso Business, Binance Pay, Coinbase
Commerce, etc.: disponibilidad Colombia, fees reales cobro+payout, payouts automáticos por API,
KYC, rampa a COP, integración FastAPI/Railway, y CÓMO cobrar markup propio + riesgos legales/impuestos
cripto en Colombia. Hipótesis inicial: NOWPayments (cobra+paga por API, ~0.5%) o Bitso (rampa COP).
El reporte final se entrega a Yamid EN ESPAÑOL (él solo habla español; lo interno en inglés es normal).

## Riesgos a vigilar
Compliance/impuestos cripto Colombia (verificar, no soy experto legal); el Partner necesita wallet;
seguridad de la API key de payout (tratar como config.py, NUNCA al chat ni a git).
