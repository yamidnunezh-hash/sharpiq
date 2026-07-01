---
name: project-mako-v1-shipped
description: 2026-06-30 Mako AI Analyst v1 CONSTRUIDO y desplegado (chat + creditos + aterrizado en el motor). Falta agregar ANTHROPIC_API_KEY en Railway para pasar de modo basico a IA completa.
metadata:
  type: project
---

# Mako AI Analyst v1 — construido y en vivo (2026-06-30)

Segundo gran activo (ver [[project-mako-plan-build]]). El analista deportivo personal:
el cliente pregunta LIBRE, Mako encuentra el partido en predicciones.json, arma una ficha de
datos REALES y responde con Claude Haiku (aterrizado, sin inventar, sin promesas).

## Backend (Railway, ya desplegado)
- **sharpiq-engine/api/mako.py** router `/mako`:
  - `GET /mako/estado` -> creditos del usuario.
  - `POST /mako/preguntar {pregunta}` -> encuentra partido (_encontrar fuzzy por nombres),
    arma ficha (_ficha: prob 1X2, goles, forma, mercados_ext, h2h), responde (_responder).
  - Modelo: **claude-haiku-4-5** (import anthropic LAZY). Prompt _SYSTEM aterrizado + seguro
    (solo datos dados, sin inventar, sin prometer ganar, explica el porque, breve, español latino).
  - Si NO hay match -> lista partidos disponibles y NO cobra credito.
  - Fallback: si no hay ANTHROPIC_API_KEY -> "modo basico" (muestra la ficha) para no romperse.
- **Creditos** (tabla `mako_uso` en db.py): Free = trial 10 preguntas O 7 dias (lo que llegue
  primero). VIP/admin = 20/dia (reset diario). Constantes al tope de mako.py (faciles de tunear).
  Copy suave: "Te queda 1 consulta gratuita" / "Has utilizado tus consultas incluidas. Mako puede
  seguir... con SharpIQ Pro."
- requirements.txt: +anthropic. main.py: router registrado. Verificado vivo (HTTP 401).

## Frontend (GitHub Pages, ya desplegado)
- **mako.html**: chat UI estilo SharpIQ (burbujas Mako/usuario, contador de creditos, chips de
  ejemplo, upsell suave al agotar trial, -> registro.html?plan=vip). Exige sesion (sharpiq_token).
- **cuenta.html**: boton "🦈 Pregúntale a Mako AI" -> mako.html. SW v86->v87.

## IA COMPLETA — RESUELTO (2026-06-30)
Yamid agrego **ANTHROPIC_API_KEY** en Railway (proyecto delightful-adaptation, servicio web).
Tiene cuenta Individual en console.anthropic.com con USD 5.00 de saldo prepago. Verificado:
`GET /mako/salud` -> {ia_configurada: true, modelo: claude-haiku-4-5}. Mako ya responde
conversacional (no modo basico). Diagnostico `/mako/salud` (sin secretos) queda para debug.
Costo ~15 COP/pregunta. NO pegar la key en el chat (va directo a Railway).

## Mejoras ya hechas (2026-06-30, mismo dia)
- **Marcadores EN VIVO**: mako.py lee live_scores.json (_live_de), enriquece la ficha con el
  marcador si el partido esta live/finished. Se actualiza cada 10 min. OJO: el capturador
  (live_scores_update.py) ahora captura MLB/etc. pero NO el futbol del Mundial en vivo -> Mako
  responde honesto "no tengo el marcador en vivo" para esos. Pendiente: arreglar el capturador de
  futbol en vivo.
- **Memoria de conversacion (no perder el hilo)**: el chat envia `historial` (ultimos 10 msgs);
  el backend lo usa para encontrar el partido aunque la pregunta de seguimiento no lo nombre
  ("y a cuota 1.60?") y le da contexto al modelo. Prompt regla 8: conversacion continua.
- Verificado en produccion: Mako respondio EXCELENTE preguntas de corners (10.8 esperados, Over 9
  75.1%, con el porque), de VALOR (cuota 1.60 -> prob implicita 62.5% vs 75% del modelo = plusvalia)
  y de Harry Kane (honesto: no tiene remates por jugador). Yamid encantado ("es el homerun").

## Goleadores — HECHO (2026-06-30)
`_goleadores_de(local, visita)` en mako.py lee el campo `gole` de ANALISIS_DIA en datos.js (por
nombres) y lo suma a la ficha. Verificado: England vs DR Congo -> "H. Kane 58.2% · Y. Wissa 40.8%".
Mako ya responde "¿que chance tiene Kane de marcar?". (Mexico-Ecuador no tenia gole calculado ->
Mako lo dice honesto.)

## Futbol en vivo — YA CUBIERTO
live_scores_update.py YA incluye `soccer_fifa_world_cup` en SPORTS. El capturador captura el Mundial;
aparece en `live` cuando el partido esta realmente EN JUEGO. La vez que Mako dijo "no tengo el
marcador" el partido estaba "upcoming" (no habia arrancado), no era un bug. Mako lo lee via _live_de.

## Goleadores EXTENDIDOS a ligas principales — HECHO (2026-06-30)
predecir_jornada.py ya NO es solo Mundial: `_LIGAS_ANALISIS` incluye Champions/Europa/Conference,
Premier/LaLiga/Serie A/Bundesliga/Ligue 1, Primeira/Eredivisie, Libertadores/Sudamericana,
Brasileirao A-B/Argentina/Liga MX/MLS. Tope `_MAX_PARTIDOS=30` (cuida la API). Corrige la liga
hardcodeada a "Mundial" -> usa el nombre real. Temporada por liga (Mundial=2026, domesticas default).
Aplica en la proxima corrida del motor cuando esas ligas tengan partidos PROXIMOS. Hoy solo habia
Mundial (ya empezado) -> no habia nada nuevo que mostrar, pero el codigo queda listo. Europeas estan
fuera de temporada hasta agosto; en temporada ahora: Mundial, Libertadores, Sudamericana, Brasil,
Liga MX, MLS, Argentina.

## BUG cazado y arreglado — ANALISIS_DIA vacio (2026-06-30)
Al correr predecir_jornada, si TODOS los partidos del dia ya empezaron, generar_items devuelve 0 y
ANTES inyectaba ANALISIS_DIA VACIO -> borraba goleadores/tarjetas de la web ("se desconfigura").
Ahora `if not items: return` conserva el ANALISIS_DIA actual. Era un bug latente que mordia.

## Ficha COMPLETA de mercados + credito justo (2026-06-30)
- _ficha ahora incluye TODOS los mercados del motor: 1X2, goles Over/Under 1.5/2.5/3.5, **BTTS
  (ambos marcan) btts_si/btts_no**, corners por linea (corners_over_8_5/9_5/10_5), tarjetas
  (cards_over_2_5/3_0), Draw No Bet (dnb_local/visita), + mercados_ext + h2h + goleadores + live.
- BUG corregido: la linea de goles usaba `over225` (2.25 asiatico) etiquetado como "2.5"; ahora
  usa `over25`/`under25` (2.5 real). Las claves de probabilidades: over25=2.5, over225=2.25.
- **Credito justo**: en preguntar(), si la respuesta contiene "no tengo ese dato"/similar, NO se
  cobra la consulta (`_no_dato`). Antes cobraba aunque Mako no pudiera responder.
- mako.html: input mas ancho en movil (media query, padding reducido). SW v91.

## Goles esperados POR EQUIPO — HECHO (2026-06-30)
Yamid preguntaba "cuantos goles hace Belgica". motor.py calculaba goles_esperados_local/visita
(calcular_goles_esperados) pero NO los guardaba. Ahora el flujo sharp-odds (linea ~3767) inicializa
`gl = gv = None` y guarda `goles_esperados_local/visita` en la entrada de predicciones.json. Mako:
`_goles_por_equipo(p)` en mako.py usa el valor exacto del motor si existe; si no, lo ESTIMA desde la
forma reciente (est_l=((ataque_l+defensa_v)/2)*1.05, est_v=(ataque_v+defensa_l)/2) como puente hasta
la proxima corrida. Nueva linea en _ficha: "Goles esperados por equipo (estimado por forma): X ~n · Y ~n".
El valor exacto reemplaza la estimacion tras la 1a corrida del motor.

## Pendiente concreto (lo que SI necesita mas)
- **Remates POR JUGADOR de FUTBOL** (ej. cuantos remates hace Kane): API-Football (la que YA pagamos)
  SI trae shots.total/shots.on por jugador -> es CONSTRUIBLE en el dia (mismo metodo que goleadores:
  promedio de temporada proyectado). Correccion honesta a Yamid: los datos SI estan, solo falta la
  funcion. DECISION 2026-06-30: NO construir aun -> es nicho, goleadores ya cubre la pregunta estrella,
  prioridad = conseguir usuarios Pro. Mako responde honesto "no tengo remates por jugador" (suma
  credibilidad). Construir cuando un usuario pagando lo pida. (NBA player props = otra API, ~oct 2026.)
- **Manejar las preguntas que Mako NO puede responder** (idea de Yamid, a futuro): capturarlas/loguearlas
  -> muestran QUE construir despues y donde pulir. "Toca pulir al maximo". Pendiente de disenar.

## Mako v1.5 — más potente (2026-07-01)
- **Resumen de la jornada**: preguntas tipo "¿qué hay hoy?/qué recomiendas/más valor" ->
  `_resumen_dia` lista top picks rankeados por SharpScore (GRATIS, no cobra crédito; el
  análisis a fondo de cada partido sí cobra). Filtro Mundial (`_es_mundial` + `_LIGAS_MUNDIAL`)
  para que el fútbol no lo tape el tenis/MLB. `_bonito_mercado` traduce claves crudas
  (corners_over_8_5 -> "Más de 8.5 córners"). Texto NEUTRO (no asume goles/córners; sirve tenis/MLB).
- **Créditos a medianoche HORA COLOMBIA** (`_hoy_col`, UTC-5): antes reiniciaban a las 7pm COT
  (el server corre en UTC). VIP sigue 20/día, Free 10 trial.
- **Enrutamiento por dificultad** (`_es_compleja` + `_responder`): preguntas factuales -> Haiku
  (~22 COP); análisis/comparación/consejo -> **Opus 4.8** (~110 COP, MÁXIMA potencia). Constantes
  MODELO_SIMPLE/MODELO_COMPLEJO al tope, tunable a Sonnet con 1 línea. Misma ANTHROPIC_API_KEY da
  todos los modelos (nada nuevo que configurar). Opus gasta el saldo ~5x más rápido en las complejas
  pero son pocas; con $5 alcanza ~400-500 preguntas mezcladas. Se autofinancia con clientes.
- **UX (decisión de Yamid)**: QUITADOS los chips de ejemplo (no le gustaron: "que la gente pregunte
  y ya"). Saludo dice "cualquier EVENTO de hoy" (no "partido") por multideporte. SW v94.
- Recomendar a Yamid activar **auto-reload** del saldo en console.anthropic.com antes de mostrarlo
  en serio (que Mako no se quede sin IA en una demo).

## Siguiente (Fase 2, cuando haya usuarios)
Mako Memory (perfil del usuario: ligas favoritas, banca) + explicabilidad formalizada. Ver
[[project-sharpiq-os-vision]]. Orden: vender Pro/usuarios primero.
