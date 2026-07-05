---
name: project-zona-partner-construida-2026-07-03
description: Zona Partner CONSTRUIDA (Fases 1-3): motor backend, dashboard premium estilo Movve y árbol genealógico D3. Comisión 50% (35/10/5). Falta Fase 4 (payouts admin) y encender multinivel tras abogado.
metadata:
  type: project
---

# Zona Partner — CONSTRUIDA Fases 1-3 (2026-07-03)

Ejecuta el plan de [[project-zona-partner-plan-2026-07-03]]. Todo desplegado en main. SW v108.

## Decisiones finales aplicadas
- **Comisión 50% en 3 niveles: 35 / 10 / 5** (pagos.py COM_NIVELES, defaults 35/10/5).
- **Precio VIP $20** (pre-lanzamiento; sube a $35-50 en ago/sep con las ligas). OJO: `PRECIO_VIP_USD`
  en Railway TODAVÍA está en 15 — hay que ponerlo en 20 cuando Yamid quiera.
- Estrategia: carrera de 90 días para agarrar volumen con la comunidad de redes del amigo de Yamid.
- **Interruptor legal `COM_MULTINIVEL`** (pagos.py): default OFF -> solo paga NIVEL 1 (legal ya).
  Poner `COM_MULTINIVEL=1` en Railway tras consulta legal para encender N2 y N3.

## Lo construido (todo aditivo, no toca Mako/pagos/web)
- **api/partners.py**: /estado, /inscribir (auto, gratis, cualquiera), /dashboard, /arbol (consulta
  recursiva 3 niveles), /wallet, /solicitar-payout. Registrado en main.py (prefix /partners).
- **Devengo** (pagos.py `_devengar_comisiones`): al pagar un referido (MP o cripto), sube la cadena
  `usuarios.referido_por` y crea comisión para cada referidor que sea PARTNER activo. Base = PRECIO_VIP_USD.
  Enganchado en `_registrar_pago` (MP) y `_registrar_pago_cripto`. Idempotente por UNIQUE(pago_id,partner_id).
- **DB**: comisiones ganó columnas `nivel` + `pct`; el índice UNIQUE(pago_id) se cambió a
  UNIQUE(pago_id, partner_id) para permitir 3 comisiones por pago (multinivel).
- **Dashboard premium (cuenta.html, pestaña "🤝 Zona Partner")**: tarjeta de RANGO con barra
  (Bronce/Plata/Oro/Zafiro/Esmeralda/Diamante por # directos VIP), KPIs, gráfico SVG de comisiones/mes,
  "Tus directos" con badge Activo/Inactivo + generado por cada uno, wallet, solicitar payout, comisiones.
- **Árbol genealógico D3** (cuenta.html): interactivo, expandir/colapsar, zoom/pan, colores por nivel
  (N1 morado, N2 verde, N3 dorado; tú cyan), resumen por nivel. D3 se carga bajo demanda desde
  jsdelivr (GRATIS, sin comprar API — los DATOS son nuestros). Verificado bonito con red demo.

## Unificación (pedido de Yamid)
Se ELIMINÓ por completo el viejo "1 mes gratis" por referido (nadie lo había ganado) y la pestaña
"Referidos". Ahora hay UN solo sistema: Zona Partner (comisión cash). Se quitaron
_recompensar_referidor, la aplicación de meses pendientes en _activar_vip, y las funciones/panel
huérfanos (cargarReferidos, copiarRef).

## Datos demo (borrables)
Se crearon 6 usuarios "Demo" bajo el código de Yamid (UQRKBXSK) para ver el árbol: Carlos/Maria/Jorge
(N1) -> Ana/Luis (N2) -> Sofia (N3). Son de prueba, se pueden borrar.

## PENDIENTE
1. **Fase 4 — Payouts (lado admin)**: aprobar y pagar comisiones en cripto (NOWPayments Mass Payouts).
   El partner ya solicita; falta el panel admin para aprobar + ejecutar el pago.
2. Poner **PRECIO_VIP_USD=20** en Railway.
3. Probar el flujo end-to-end: referido paga -> comisión aparece -> nodo verde.
4. Encender **COM_MULTINIVEL=1** tras consulta legal (SENA/universidad gratis).
