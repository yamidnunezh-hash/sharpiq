---
name: project-zona-partner-plan-2026-07-03
description: Plan LISTO para construir la Zona Partner (dashboard de socios) de SharpIQ. Decisiones cerradas. Yamid quiere "con todos los juguetes" (premium). Falta ARRANCAR (Fase 1).
metadata:
  type: project
---

# Zona Partner — plan cerrado, listo para construir (2026-07-03)

Es el motor de crecimiento (afiliados/multinivel legal). Sigue de [[project-cripto-landing-jwt-2026-07-03]]
(las tablas partners/comisiones/payouts ya existen). Yamid dijo "hacemos esto con todos los juguetes"
= quiere lo MEJOR, no algo superficial. NO empezar a codear hasta que diga "arrancamos".

## DECISIONES CERRADAS (de Yamid)
- **Modelo:** estilo bróker (unilevel, multinivel LEGAL — como los IB de trading).
- **Comisiones 3 niveles:** **30% / 7% / 5%** (modo "atraer muchos partners rápido").
- **Precio VIP: sube a $20 USD** (~80.000 COP) — antes $15. El precio mayor FINANCIA las comisiones
  generosas. Con $20 y 42% repartido ($8,40), a Yamid le queda $11,60 (58% margen) = gana MÁS que
  antes. Cambiar `PRECIO_VIP_USD` a 20 en Railway al construir. (Ojo conversión: $80k es salto desde
  $60k; ajustable si baja.)
- **Ubicación:** PESTAÑA dentro de cuenta.html (junto a Mis Picks / Referidos / Pagos / Config).
- **Quién es Partner:** CUALQUIERA que quiera — auto-inscripción GRATIS (botón "Activar mi cuenta de
  Partner"), sin barrera de entrada (esto además ayuda a que sea legal).
- **Pagos del CLIENTE:** MANTENER LOS DOS — MercadoPago (la mayoría en LatAm: tarjeta/PSE/Nequi) +
  Cripto (segmento cripto + seguro si MP restringe apuestas). Comisiones a partners se pagan en cripto.

## LEGAL
- Yamid NO tiene abogado. Conclusión dada: NO se necesita "firma de abogado" para operar; lo que la
  ley exige es CUMPLIR (Ley 1700/2013). Las 4 reglas de oro + producto real (SharpIQ lo es) = legal.
- Plan: construir TODA la estructura ya (1 nivel es inequívocamente legal), y ENCENDER el pago
  multinivel (niveles 2-3) tras UNA consulta legal barata/gratis (consultorio jurídico universitario,
  Cámara de Comercio, o SENA Emprende — Yamid es del SENA).

## EL ÁRBOL GENEALÓGICO (pregunta de Yamid: ¿comprar API?)
- NO se compra ninguna API. Los datos del árbol son NUESTROS (usuarios.referido_por). La visualización
  se hace con **D3.js (gratis)** — árbol interactivo premium. Costo $0.

## ROADMAP (fases, todas aditivas — no tocan web/Mako/pagos)
1. Base del motor: `api/partners.py` (inscribirse, dashboard data, wallet) + DEVENGO (al pagar un
   referido, crear comisiones subiendo la cadena; empezar por 1 nivel; `comisiones.pago_id` UNIQUE ya
   da idempotencia). SE PUEDE YA.
2. Pestaña "Zona Partner" en cuenta.html: KPIs (clientes activos, comisión del mes, total ganado,
   próximo pago), mis referidos, mis comisiones, mi enlace, mi wallet. SE PUEDE YA.
3. Árbol genealógico con D3.js (gratis). SE PUEDE YA.
4. Payouts: partner solicita retiro → Yamid aprueba → pago en cripto (NOWPayments Mass Payouts). SE PUEDE YA.
5. Encender el multinivel (niveles 2-3) → TRAS consulta legal.

## Recomendación de arranque
Empezar por Fase 1 (base + devengo). Construir 1 nivel legal primero; dejar estructura lista para 3.

## Artefacto (plano visual)
Blueprint "Zona Partner" (con $20 y 30/7/5): https://claude.ai/code/artifact/2521229d-fd9a-478a-a169-b3356fcde5c4
Ver también [[project-cripto-pago-automatico-resuelto-2026-07-03]] (el pago cripto ya es automático).
