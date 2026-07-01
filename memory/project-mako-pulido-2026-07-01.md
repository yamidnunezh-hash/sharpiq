---
name: project-mako-pulido-2026-07-01
description: 2026-07-01 Sesión grande de pulido de Mako (probado en vivo con Harold Lozano). Bugs reales cazados y arreglados + capacidades nuevas.
metadata:
  type: project
---

# Mako — sesión de pulido 2026-07-01 (todo desplegado)

Yamid probó Mako con un interesado (Harold Lozano) y cada test cazó un hueco REAL. Todo en
sharpiq-engine/api/mako.py salvo lo indicado. SW frontend llegó a v95.

## Capacidades nuevas
- **Enrutamiento por dificultad** (`_es_compleja`): preguntas de análisis/comparación/consejo ->
  **Opus 4.8** (MODELO_COMPLEJO, máxima potencia); factuales -> Haiku (MODELO_SIMPLE). Misma
  ANTHROPIC_API_KEY da todos los modelos (nada nuevo que configurar). Tunable a Sonnet en 1 línea.
- **Modo conversación general** (`_responder_general` + `_SYSTEM_GENERAL`): si no hay partido,
  Mako CONVERSA natural (saluda, se presenta, enseña de apuestas) como una IA de verdad, SIN
  inventar datos. Adiós al robótico "No encontré ese partido". Gratis (no cobra crédito).
- **Resumen de la jornada** (`_resumen_dia`, `_es_resumen`, `_es_mundial`): "¿qué hay hoy?" ->
  top picks por SharpScore; chip/filtro Mundial. `_bonito_mercado` traduce claves crudas.
- **Remates por jugador** (LA CEREZA que pidió Harold): `player_props.py` funciones
  obtener_remates_equipo/formato_remates_partido usan `/players` (shots.total/on). predecir_jornada
  los escribe en **props_jugadores.json** (archivo DEDICADO, no el frágil ANALISIS_DIA). Mako
  `_props_de` lo lee -> ficha muestra "H. Kane ~3.33 rem (2.0 a puerta)". Esto ARREGLÓ también los
  goleadores (estaban rotos: generar_items filtra 'soccer' y predecir_jornada usa 'liga_1').
  El pipeline sube props_jugadores.json (motor.yml + auto_publicar). Costo $0 (plan API-Football Pro
  ya lo cubre, 7500 req/día usando ~300).

## Bugs reales arreglados
- **mercados_ext truncado a 400 chars** -> los DISPAROS/paradas quedaban cortados. Ahora se extraen
  limpios (córners/tarjetas/disparos-visitante/atajadas-local esperados). Etiquetas exactas (el
  disparos_esperados es del VISITANTE, no total).
- **Nombres español→inglés** (`_ALIAS`, `_expandir_alias`): el motor guarda "England/Belgium/USA"
  pero el usuario escribe "Inglaterra/Bélgica/Estados Unidos". 40+ países. CRÍTICO para el Mundial.
- **Partidos EN VIVO** (`_buscar_live`, `_texto_live`): si el partido ya arrancó salió de
  predicciones.json; Mako lo busca en live_scores.json y da el marcador. OJO (dato de Yamid): en
  vivo SOLO hay marcador (goles), NO stats minuto a minuto (remates) -> Mako lo aclara honesto. Los
  remates son PRE-partido; no desgastarse en remates en vivo.
- **Perder el hilo** (saltaba a otro partido): el frontend recuerda `ultimoPartido` y lo envía como
  `partido_actual`; backend `_por_nombres` lo reengancha. Robusto ante traducción y resúmenes previos.
- **Créditos a medianoche HORA COLOMBIA** (`_hoy_col`, UTC-5) — antes reiniciaban a las 7pm COT.
- UX: QUITADOS los chips de ejemplo (Yamid: "que la gente pregunte y ya"); saludo dice "evento" no
  "partido" (multideporte).

## Pendiente / notas
- Stats por jugador EN VIVO (remates minuto a minuto) = otra API/feed; Yamid dijo no desgastarse (los
  remates son pre-partido). Clubes en español (Bayern->Bayern Munich): agregar aliases según aparezcan.
- Activar **auto-reload** del saldo Anthropic antes de mostrarlo en serio (que no se quede sin IA).
- Ver [[project-mako-v1-shipped]], [[project-validacion-motor-2026-07-01]].
