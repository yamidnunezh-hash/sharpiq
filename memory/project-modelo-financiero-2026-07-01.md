---
name: project-modelo-financiero-2026-07-01
description: Modelo financiero de SharpIQ (costos reales, márgenes, break-even, viabilidad de Partners). Herramienta sharpiq-engine/modelo_financiero.py. Base para decidir precio y comisión con números.
metadata:
  type: project
---

# Modelo financiero SharpIQ (2026-07-01)

Construido a pedido de la Visión Estratégica (decidir precio/comisión con números, no intuición,
ANTES del programa de Partners). Herramienta: **sharpiq-engine/modelo_financiero.py** (supuestos
editables al tope; correr `python modelo_financiero.py`).

## Costos REALES (confirmados por Yamid)
- The Odds API: **$50/mes** · API-Football: **$19/mes** (plan Pro, 7500 req/día, usa ~300) ·
  Railway: ~$10 (VALIDAR en dashboard) · dominio+otros ~$2 -> **FIJOS ~$81/mes**.
- Mako (variable): ~$0.56/usuario/mes con Haiku (150 preg × ~15 COP). Con Opus en las complejas
  sube a ~$1.20-1.66/usuario. Sigue baratísimo.
- MercadoPago Colombia ~5% (VALIDAR). Cripto sería ~0.5-1% (ver [[project-cripto-pasarela-2026-07-01]]).

## Hallazgos
- **Márgenes altísimos** (SaaS de manual): 91-94% venta directa; 66-69% vía Partner (comisión 25%).
- **Break-even ~6 usuarios** a $15. Riesgo financiero mínimo. Se autofinancia con clientes.
- **Argumento para subir el precio** (número, no intuición): a $15 un Partner necesita ~133 clientes
  para ganar $500/mes; a $30 -> 67; a $45 -> 44; a $60 -> 33. Precio bajo NO hace atractivo el
  programa de Partners. El doc de ChatGPT pide NO fijar $60 aún hasta validar con el mercado.

## Pendiente
- Confirmar costo real de Railway. Definir precio final y % de comisión Partner CON el modelo.
- Ver [[project-sharpiq-os-vision]] y [[project-validacion-motor-2026-07-01]].
