---
name: project-sharpscore-shipped
description: 2026-06-30 SharpScore(TM) construido y desplegado — el sello 0-100 de SharpIQ (primer "activo de marca"). En vitrina, cuenta VIP, Telegram, API y pagina de detalle.
metadata:
  type: project
---

# SharpScore™ — construido y en vivo (2026-06-30)

Primer activo del plan [[project-sharpiq-os-vision]] / [[project-mako-plan-build]]. Puntuacion
0-100 por pick = la marca de SharpIQ ("un apostador PRO = un sharp").

## Formula (sharpiq-engine/sharpscore.py)
`SharpScore = 50% probabilidad + 25% EV(vs Pinnacle) + 25% tier/confianza`, clamp 1-99.
- prob_c = prob (0-100); ev_c = clamp(50 + ev*3.5, 0,100); tier_c = seguro90/principal75/altovalor70/def65.
- `calcular(prob, ev, tier)` -> int; `nivel(score)` -> (etiqueta, estrellas); `color(score)`.
- Niveles: >=80 Maxima confianza ★★★★★ / 70-79 Alta ★★★★ / 60-69 Solida ★★★ / 50-59 Moderada ★★ / <50 Especulativa ★.
- Ejemplos reales: seguro69%->71, principal52%->62, altovalor32%->56, seguro78%->78. Honesto y diferencia bien.

## Donde se muestra (todo desplegado)
- **auto_publicar.py** `_agregar_a_datos_js`: calcula y guarda campo `sharpscore` en cada entry de datos.js.
- **index.html** (vitrina): badge SharpScore en cada tarjeta, VISIBLE HASTA EN PICKS BLOQUEADOS
  (gancho de conversion: el free ve el numero alto pero no el pick). Fallback client-side desde prob+tier.
- **api/picks.py** `_leer_proximos`: entrega `sharpscore` + `prob` por pick (o lo calcula si falta).
- **cuenta.html** (Mis Picks VIP): badge SharpScore por pick.
- **telegram_alertas.py** `enviar_alerta_value_bet`: linea "🦈 SharpScore X/100 · nivel ★★★★".
- **pronostico.html** (detalle): panel SharpScore grande (confianza del modelo, tier principal por defecto).
- SW v82->v85. Commits 5d08067, 8139b31, 18677dd.

## Nota
Los picks ya en datos.js (viejos) muestran el SharpScore por el FALLBACK client-side/API (prob+tier);
la proxima corrida del motor ya lo guarda con EV incluido (mas preciso). Un solo modulo compartido
-> cuando haya NBA, el mismo SharpScore aplica automatico.
