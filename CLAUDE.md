# SharpIQ — Contexto Completo del Proyecto

## Qué es SharpIQ
Plataforma de predicciones deportivas basada en IA y modelos estadísticos.
Eslogan: **"La ventaja inteligente"**
Usuario: Yamid Núñez — ingeniero SENA Cazucá. SharpIQ es su proyecto de vida.
**Este es dinero real. Cada pick publicado impacta a suscriptores que apuestan con él.**
Dominio: **sharpiq.co** (CNAME → GitHub Pages). API: **api.sharpiq.co** (Railway).

## Modelo de negocio
- Canal Telegram VIP → picks diarios (3 tiers) — $15 USD/mes vía MercadoPago
- Canal Telegram Free → teaser del partido, no da el pick
- Web `sharpiq.co` → vitrina pública con picks, historial, stats
- Sistema de referidos → 20% de comisión del primer mes VIP ($3)
- Objetivo futuro: eSports → crypto → forex

---

## ARQUITECTURA GENERAL

SharpIQ tiene **3 grandes piezas**:

1. **Motor de predicciones (Python)** — `sharpiq-engine/*.py`
   Corre en GitHub Actions 4x/día. Analiza partidos, calcula EV vs Pinnacle,
   clasifica picks en tiers, publica en Telegram y actualiza el frontend.

2. **Backend API (FastAPI + PostgreSQL)** — `sharpiq-engine/api/`
   Corre en Railway (uvicorn). Maneja usuarios, login JWT, suscripciones
   MercadoPago, referidos y entrega de picks según plan.

3. **Frontend web estático (HTML/CSS/JS vanilla + PWA)** — raíz del repo
   Servido por GitHub Pages. Vitrina pública + área de cuenta + panel admin.

```
                    ┌──────────────────────────────────────┐
                    │  GitHub Actions (cron 4x/día + live)   │
                    │  motor.py → predicciones.json          │
                    │  auto_publicar.py → datos.js + Telegram │
                    └───────────────┬────────────────────────┘
                                    │ git push
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
    ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │ GitHub Pages      │  │ Railway (FastAPI) │  │ Cloudflare Worker │
    │ sharpiq.co        │  │ api.sharpiq.co    │  │ MP webhook → VIP  │
    │ index.html, etc.  │  │ auth/pagos/picks  │  │ Telegram invites  │
    └──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## ESTRUCTURA DE ARCHIVOS (inventario completo)

### Raíz — Frontend web (GitHub Pages)
```
index.html          # Landing principal (159 KB). Picks + historial INLINE (datos.js incrustado)
estadisticas.html   # Stats verificables: KPIs, Chart.js (bankroll, win rate), simulador
predicciones.html   # Panel admin del motor: grid de predicciones, botón PUBLICAR
admin.html          # Panel admin completo: predicciones/datos/usuarios/reportes
login.html          # Login JWT (+ bypass admin SHA-256 offline)
registro.html       # Alta de cuenta (free/VIP), soporta ?ref= referidos
cuenta.html         # Dashboard usuario: Mis Picks / Referidos / Pagos / Config
bienvenido.html     # Splash post-pago MercadoPago (?status=approved/pending/failure)
sharpiq-perfiles-telegram.html  # Generador de avatares PNG para canales Telegram

datos.js            # PROXIMOS_EVENTOS[] + PREDICCIONES_HISTORIAL[] (editado por motor)
sw.js               # Service Worker (CACHE_VERSION sharpiq-v12): caché + push
manifest.json       # PWA manifest (standalone, dark #0a1428, icons 192/512)
CNAME               # sharpiq.co

predicciones.json   # Corpus completo (~1.3 MB, 150+ predicciones) — GENERADO, gitignored
mejor_prediccion.json  # Pick destacado del día — GENERADO, gitignored
live_scores.json    # Marcadores en vivo (live/upcoming/finished) — actualizado cada 10 min

assets/             # logo, favicon, hero.mp4, robots, imágenes de fondo
INSTRUCCIONES.md    # Doc genérico del "kit web" (NO cubre SharpIQ — heredado de plantilla)
```

### Deploy / build (raíz)
```
Procfile            # web: uvicorn sharpiq-engine.api.main:app --host 0.0.0.0 --port $PORT
nixpacks.toml       # Railway build: python311 + git, pip install -r requirements.txt
requirements.txt    # requests, numpy, scipy, psycopg2-binary, fastapi, uvicorn, pyjwt, pydantic[email]
.gitignore          # IGNORA: config.py, predicciones.json, mejor_prediccion.json, __pycache__
```

### Automatización (.github/workflows/) — horas en COT = UTC-5
```
motor.yml         # 4x/día (7am,11am,3pm,7pm COT). Corre auto_resultados→recolector→motor→auto_publicar
resultados.yml    # Diario 11pm COT (4am UTC). Solo auto_resultados.py (resuelve W/L)
live_scores.yml   # Cada 10 min. live_scores_update.py → commit live_scores.json si cambia
live_monitor.yml  # Cada 5 min. live_monitor.py → alertas Telegram en vivo (EV en gol/medio tiempo)
```
Secrets (GitHub): `FOOTBALL_DATA_KEY, ODDS_API_KEY, APIFOOTBALL_KEY, TELEGRAM_TOKEN, TELEGRAM_YAMID_ID, TELEGRAM_FREE_ID, TELEGRAM_CHAT_ID` (+ MP/CF en resultados.yml).

### Scripts locales Windows (.bat)
```
SHARPIQ.bat         # Corre motor.py + abre predicciones.html en servidor.py:8080
SHARPIQ_AUTO.bat    # Corre motor.py una vez, log a motor_log.txt (para Task Scheduler)
ABRIR-PANEL.bat     # Sirve predicciones.html en :8000
sharpiq-engine/run-motor.bat        # Pipeline completo: referidos→resultados→recolector→motor→publicar
sharpiq-engine/run-motor-tarde.bat  # Solo motor.py (turno tarde, ligero)
```

---

## MOTOR DE PREDICCIONES (`sharpiq-engine/*.py`)

### Núcleo
| Archivo | Qué hace |
|---------|----------|
| **motor.py** | Core (~165 KB). Itera ligas, obtiene forma/H2H/lesiones, calcula matriz Poisson + Dixon-Coles, ajusta con xG, detecta steam moves, calcula EV real vs Pinnacle, clasifica tiers, guarda `predicciones.json` + `mejor_prediccion.json`, lanza alertas Telegram. Funciones clave: `procesar_partido()`, `clasificar_tiers()`, `kelly_stake()`, `guardar_predicciones()`, `_alertar_steam()` |
| **motor_cron.py** | Loop cron alternativo (Railway/local): corre motor 9am/4pm y resultados 11:30pm COT. No usado si se confía en GitHub Actions |
| **stats_mercados.py** | Mercados extendidos: corners, tarjetas, hándicap asiático, disparos. Caché SQLite 7 días (`stats_ext_cache`) para no gastar API |
| **stats_partido.py** | CLI de inspección: `python stats_partido.py "Local" "Visitante"` → forma, H2H, bajas |
| **xg_integracion.py** | Ajusta lambdas Poisson con proxy xG (shots on target × 0.33), blend conservador `XG_BLEND=0.25`. Reusa caché de stats_mercados (0 API extra) |
| **player_props.py** | Probabilidad de goleador "anytime" vía topscorers + Poisson. Caché 24h |
| **arbitraje.py** | Detecta arbitraje (suma de prob. implícitas < 100%) entre casas, calcula stakes óptimas |
| **analisis_cop_lib.py** | Modelo Poisson+Dixon-Coles especializado Copa Libertadores (escala 0.95) |
| **analisis_cop_suda.py** | Idem para Copa Sudamericana (escala 1.05) |

### Publicación y resultados
| Archivo | Qué hace |
|---------|----------|
| **auto_publicar.py** | Orquestador de salida: lee `predicciones.json`, inserta mejor pick en `datos.js` + bloque inline de `index.html`, push notification, mensaje Telegram VIP, git commit+push |
| **auto_resultados.py** | Detecta partidos publicados ya finalizados, hace matching fuzzy de nombres, evalúa W/L/Push, marca `datos.js` con ✅/❌ |
| **telegram_alertas.py** | Gestor central Telegram: `enviar_alerta_value_bet()`, `enviar_resumen_dia()`, `enviar_aviso_yamid()`, GIFs, webhook bot. Destinos: VIP, Free, privado Yamid |
| **enviar_picks_manual.py** | Envío manual de ejemplo (free bloqueado vs VIP completo) |
| **limpiar_telegram.py** | Borrado de mensajes del bot (uso puntual) |

### Tiempo real
| Archivo | Qué hace |
|---------|----------|
| **live_monitor.py** | Cada 5 min: recalcula EV en momentos clave (inicio, 45', 60', 75') de partidos publicados, alerta solo si hay valor. Anti-spam en `live_alertas` (SQLite) |
| **live_scores_update.py** | Cada 10 min: escribe `live_scores.json` con NBA/NHL/MLB/tenis/fútbol. Nunca expone API key al frontend |

### Datos / persistencia
| Archivo | Qué hace |
|---------|----------|
| **database.py** | SQLite local (`sharpiq.db`). Tablas: `partidos`, `estadisticas_partido`, `cuotas_apertura`, `movimientos_cuotas`, `promedios_equipo`. Crece sola, costo $0 |
| **db_clv.py** | PostgreSQL Railway para CLV tracking (futuro). Tablas `picks`, `odds_history`. Requiere `psycopg2` |
| **recolector.py** | Recolección nocturna: guarda resultados+stats del día anterior en SQLite. CLI: `ayer|semana|mes|YYYY-MM-DD` |
| **sharpiq.db** | Base SQLite versionada (la suben los workflows) |
| **historial_cuotas.csv** | Cuotas de apertura acumuladas (base para CLV) |

### Notificaciones y pagos
| Archivo | Qué hace |
|---------|----------|
| **push_notifications.py** | Push web vía VAPID (`pywebpush`). Guarda subs en `push_subs.json`, limpia expiradas |
| **vapid_private.pem** | Clave privada VAPID (push) |
| **bot_handler.py** | Gestión VIP: captura email/chat_id del bot, escribe Cloudflare KV, genera link MercadoPago con `external_reference=chat_id` |
| **procesar_referidos.py** | Stub → llama `procesar_updates_bot()` de telegram_alertas |
| **mp_webhook_worker.js** | **Cloudflare Worker** (deploy aparte): recibe webhook MP, al aprobar crea link VIP único en Telegram (member_limit=1), actualiza KV, notifica a Yamid; al cancelar expulsa |
| **servidor.py** | HTTP server local (estáticos + API): `/api/vapid-public-key`, `/api/proximos`, `/api/pendientes`, `POST /api/publicar` (Bearer), `POST /api/subscribe` |
| **config.py** | ⚠️ GITIGNOREADO. Define: `FOOTBALL_DATA_KEY, ODDS_API_KEY, APIFOOTBALL_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_YAMID_ID, TELEGRAM_FREE_ID, PANEL_TOKEN, VAPID_*, MP_*, CF_*, DATABASE_URL` |

### APIs externas usadas
- **The Odds API** → cuotas en tiempo real (Pinnacle + mejores bookmakers)
  - Fútbol: `h2h, totals, alternate_totals, spreads (AH), btts, double_chance, draw_no_bet`
  - US sports: `h2h, spreads, totals` · CONMEBOL a veces solo `h2h, totals`
- **API-Football (api-sports.io)** → stats históricas, forma, H2H, lesiones, topscorers
- **Football-Data.org** → fixtures de ligas top europeas
- **Pinnacle** (vía Odds API) → benchmark de probabilidad real (no-vig = precio justo)

---

## BACKEND API (`sharpiq-engine/api/`)

**Stack:** FastAPI + PostgreSQL (Railway) + JWT HS256 (30 días) + MercadoPago.
Arranque: `uvicorn sharpiq-engine.api.main:app` (ver Procfile). CORS: `sharpiq.co`, `www.sharpiq.co`, localhost.

| Archivo | Responsabilidad / Endpoints |
|---------|------------------------------|
| **main.py** | App FastAPI, CORS, startup `inicializar_db()`. `GET /` health. `POST /admin/publicar-pick` (solo_admin → escribe pick en `datos.js` vía GitHub API). Registra routers |
| **db.py** | Conexión psycopg2 (`RealDictCursor`), context manager `db()`, `inicializar_db()`. 5 tablas: `usuarios, suscripciones, pagos, referidos, picks_publicados` |
| **auth.py** | JWT. `POST /auth/register`, `POST /auth/login` (bypass admin hardcoded para Yamid), `GET /auth/me`, `POST /auth/cambiar-password`. Roles: `usuario_activo`, `solo_vip`, `solo_admin`. Hash SHA-256, códigos ref de 8 chars |
| **members.py** | `GET /members/dashboard` → perfil + suscripción + últimos pagos + stats referidos |
| **pagos.py** | MercadoPago. Plan VIP $15/mes. `GET /pagos/planes`, `POST /pagos/checkout-publico`, `POST /pagos/suscribir/{plan}`, `POST /pagos/webhook` (activa/desactiva VIP, registra pago, comisiona referidor $3), `GET /pagos/mi-suscripcion` |
| **picks.py** | Fuente: `predicciones.json`. `GET /picks/hoy` (VIP=completo filtrado EV≥5% / Free=2 previews bloqueados), `GET /picks/historial`, `GET /picks/stats` (público: win rate, ROI), `POST /picks/publicar` (solo_vip), `PATCH /picks/resultado/{id}` |
| **referidos.py** | `GET /referidos/mis-referidos` (código, link, stats 20%), `GET /referidos/ranking` (top 10 del mes) |

### Tablas PostgreSQL
- **usuarios**: id, email(UNIQUE), nombre, password_hash, plan(free/vip/admin), referido_por, codigo_ref(UNIQUE), fecha_registro, activo
- **suscripciones**: usuario_id, plan, precio_usd, fecha_inicio/fin, mp_subscription_id, mp_payer_email, estado · UNIQUE(usuario_id, estado)
- **pagos**: usuario_id, monto, moneda, mp_payment_id, mp_status, concepto, fecha
- **referidos**: referidor_id, referido_id, comision_usd, pagado · UNIQUE(referido_id)
- **picks_publicados**: fecha, partido, liga, prediccion, cuota, hora, emoji, plan_requerido, resultado, ev_pinn

---

## FRONTEND (detalle)

**Tech:** HTML5 + CSS3 (grid/flex/variables) + JS vanilla (Fetch, localStorage, crypto.subtle). Chart.js v4 para gráficas. Google Fonts (Orbitron/Inter/Space Mono). PWA con SW + manifest.

- **Auth en cliente:** JWT en `localStorage` (`sharpiq_token`); el plan se lee decodificando el payload (`atob`).
- **index.html / estadisticas.html:** NO llaman API → leen `datos.js` (inline). Todo cálculo de KPIs en el cliente.
- **cuenta.html / login.html / registro.html / bienvenido.html:** SÍ llaman API (`api.sharpiq.co`): auth, dashboard, picks/hoy, pagos, referidos.
- **datos.js** (editado por el motor): `PROXIMOS_EVENTOS[]` (fecha, partido, liga, prediccion, cuota, hora, status, tier, stake_pct, resultado) + `PREDICCIONES_HISTORIAL[]`.
- **sw.js:** network-first para HTML/JS/datos.js (datos.js con `no-store`), cache-first para assets, maneja `push`. Subir `CACHE_VERSION` invalida caché.

### Diseño / CSS (index.html)
- Variables: `--bg0`..`--card`, `--t1`..`--t3`, `--border`.
- Dark mode: `html[data-theme="dark"]`, toggle en navbar, persiste en localStorage. Flash prevention en `<head>` antes del CSS.
- Tiers colores: alto_valor=`#F59E0B`, principal=`#0066CC`, seguro=`#22C55E`. Corporativo: cyan `#00C8FF`, purple `#7B5CF0`.
- ⚠️ `navAuthArea`: su `innerHTML` lo sobrescribe JS → NO meter elementos dentro.

---

## FLUJO DE PUBLICACIÓN (end-to-end)

1. GitHub Actions (motor.yml) detecta la ventana horaria y corre el pipeline.
2. `motor.py` → analiza todos los partidos contra Pinnacle, EV para TODOS los mercados, escribe `predicciones.json` + `mejor_prediccion.json`.
3. `clasificar_tiers()` → selecciona picks SEGURO / PRINCIPAL / ALTO VALOR (el mejor EV gana, sin importar el tipo de mercado).
4. `auto_publicar.py` → actualiza `datos.js` + bloque inline de `index.html`, publica en Telegram VIP/Free, push, y hace git commit+push.
5. Más tarde, `auto_resultados.py` resuelve W/L y vuelve a marcar `datos.js`.
6. El frontend (GitHub Pages) sirve `datos.js` actualizado; la API entrega picks según plan.

### Tiers y criterios (data-driven, NO por tipo de mercado)
| Tier | Prob mínima | EV vs Pinnacle | Cuota |
|------|------------|----------------|-------|
| SEGURO | ≥ 65% | > 0% | ≤ 1.95 |
| PRINCIPAL | ≥ 50% | ≥ 2% | 1.55 - 3.00 |
| ALTO VALOR | ≥ 20% | ≥ 7% | 1.75 - 10.0 |

**Regla dura (feedback del usuario):** no publicar prob < 30% ni cuota > 5.5. Calidad > cantidad.

## SEGURIDAD CRÍTICA
- **NUNCA** hacer git push de `config.py` ni de `vapid_private.pem`. Contienen claves reales. Verificar `.gitignore` SIEMPRE antes de commitear. (Ambos están en `.gitignore` desde 2026-06-03; `vapid_private.pem` se había filtrado y se ROTÓ.)
- ⚠️ **OJO doc histórico:** `predicciones.json` y `mejor_prediccion.json` **SÍ están trackeados** (force-add `git add -f` en `motor.yml`), NO gitignored — la API de Railway los necesita. No contienen secretos. (El `.gitignore` los lista pero el `-f` los fuerza.)
- **JWT_SECRET** debe estar puesto en Railway (env var); si falta, el default público de `auth.py` permite forjar tokens. Verificar.
- No exponer API keys al frontend: las cuotas/scores se sirven via JSON pre-generado.

---

## Metodología de análisis de partidos

### Cuando Yamid pida analizar un partido, SIEMPRE evaluar estos factores:

**1. Calidad relativa de los equipos** — diferencia real de nivel (coef. UEFA/CONMEBOL, posición en liga). En Copa Lib grupos A/B > C/D; en Suda la brecha es mayor (venezolanos/bolivianos más débiles).

**2. Factor altitud (CRÍTICO para CONMEBOL)**
| Ciudad | Altitud | Efecto en goles |
|--------|---------|-----------------|
| Cusco (Cienciano) | 3400m | -20% goles aprox |
| La Paz (Bolívar) | 3600m | -25% goles aprox |
| Quito (LDU/Ind. del Valle) | 2800m | -12% goles aprox |
| Bogotá (Millonarios/Santa Fe) | 2600m | -8% goles aprox |
| Medellín (Atlético Nacional) | 1500m | -2% goles aprox |

Un equipo argentino/brasileño nunca se adapta a 3600m en 24-48h de viaje.

**3. Local vs Visitante** — ventaja local CONMEBOL fuerte (~65% gana el local en Copa). Brasileños/argentinos de visita son cautelosos; viaje largo = cansancio/rotación.

**4. Contexto de la competición** — fase de grupos (puntos) ATACAN → más goles; eliminatoria ida → visitante busca no perder; vuelta depende del marcador. ¿Qué se juega cada equipo?

**5. Forma reciente (últimos 5)** — racha positiva = más confianza; negativa = defensivo o desesperado. Distinguir liga vs copa.

**6. H2H** — dominio histórico, tendencia de goles. H2H reciente (últimos 3) pesa más.

**7. Lesiones y bajas** — falta goleador → menos goles; falta portero titular → más goles; suspensiones en copa.

**8. Estilo de juego** — presión alta → abierto → más goles; bloque bajo → Under; contraataque → goles en transición.

### Framework de decisión para picks
```
ANÁLISIS: [Local] vs [Visitante]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Calidad: Local [MAYOR/IGUAL/MENOR] al visitante
Altitud: [Ciudad] [Xm] → [Sin efecto/Leve/Significativo/Extremo]
Contexto: [Grupo/Eliminatoria] — [Qué se juega cada equipo]
Forma local (últimos 5): [W-W-D-L-W tipo]
Forma visitante (últimos 5): [idem]
H2H reciente: [breve]
Estilo: [cómo juega cada equipo]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mercado recomendado: [Gana X / Under 2.5 / Over 1.5 / etc.]
Justificación: [1-2 oraciones]
Cuota objetivo: [rango con valor]
Confianza: [ALTA / MEDIA / BAJA]
Veredicto: [PUBLICAR / ESPERAR / DESCARTAR]
```

### Reglas de publicación
- **PUBLICAR**: análisis cualitativo COINCIDE con EV positivo vs Pinnacle.
- **ESPERAR**: EV positivo pero el análisis tiene dudas → buscar más info.
- **DESCARTAR**: el análisis contradice el pick aunque el EV sea positivo.

**Nunca publicar solo por EV. El EV confirma el análisis, no lo reemplaza.**

### Cuándo usar cada mercado
| Mercado | Cuándo aplicar |
|---------|---------------|
| Gana X | Favorito claro (>70% prob) + altitud/local a favor |
| Under 2.5 | Equipos parejos + altitud + visita cautelosa |
| Over 2.5 | Gran diferencia de calidad (≥2 divisiones) + local atacante |
| Over 1.5 | Favorito claro que marcará + equipo débil que también puede marcar |
| BTTS | Ambos necesitan atacar (contexto de puntos) |
| Hándicap Asiático | Favorito muy claro pero cuota 1X2 muy baja |
| Draw No Bet | Favorito moderado donde el empate es el único riesgo |
| Double Chance | Partido parejo donde el favorito puede perder por poco |

---

## CAMBIOS RECIENTES — sesión 2026-05-29 (todo en `origin/main`)

### Motor (`sharpiq-engine/`)
- **6 fallas corregidas**: git push robusto (commit primero, reintentos, aborta rebase en conflicto, incluye `index.html`) en `auto_publicar.py` y `auto_resultados.py`; umbrales ALTO VALOR alineados a política (`AV_MAX_CUOTA` 10→5.5, `AV_MIN_PROB` 20→30); **corners** ya no devuelve 0 (cae al promedio de liga cuando la API no trae corners); **xG** solo se aplica con disparos reales (no empujón uniforme); **corte 48h ANTES** del análisis (no gasta API en partidos lejanos tipo Mundial); `_fetch_odds_ext` pide solo `h2h,totals,spreads` (evita 422 por liga, gana hándicap asiático).
- **Umbrales SEGURO/PRINCIPAL** recuperados (se habían perdido): SEGURO 62%/cuota≤2.10, PRINCIPAL 45%.
- **`datetime.utcnow()` migrado** a `datetime.now(timezone.utc)` en motor.py y auto_publicar.py; `propagate=False` en loggers.
- **3 claves de tenis inválidas** eliminadas (daban 404 "Unknown sport").
- **Zona horaria**: helper único `_commence_a_cot()` (UTC→COT ajustando fecha al cruzar medianoche); player props guardaba `hora` en COT y duplicaba conversión → ahora UTC + `fecha_evento` COT. Ver [[web-index-arquitectura]].
- **Blend Poisson/mercado recalibrado por LIQUIDEZ**: Champions/top-5/Mundial 78% Pinnacle (el modelo no se despega del precio sharp), ligas medias 55%, poco líquidas 38%. Corrige el sobre-EV en partidos de alta liquidez (la final PSG-Arsenal pasó de "+17% inflado" a ~−9%@1.67 / +3%@1.90).

### Telegram (`telegram_alertas.py`)
- Cada pick de `enviar_tiers_vip` ahora incluye **análisis experto automático** (`_analisis_experto`): prob 1X2 + goles, EV+Kelly, forma reciente (GF/GC+pts), H2H, y lectura cualitativa (contexto final/altitud + mercado). Ya no es "Gana X @1.70".

### Web (`index.html`, `sw.js`) — bug crítico + rediseño completo
- **BUG CRÍTICO resuelto** (picks/EN VIVO salían vacíos): (1) DOCTYPE truncado `<!DOCTYP`→`<!DOCTYPE html>` causaba quirks mode (grids colapsaban); (2) **`_isPending` usado fuera de scope** lanzaba ReferenceError que detenía todo el JS → `_renderPicks` nunca corría. Ambos corregidos. Técnica de diagnóstico en [[web-index-arquitectura]].
- **Tema OSCURO forzado** (paleta navy `#0a0e1a`, anula preferencia `light` vieja).
- **Rediseño completo Sofascore/Flashscore (5 bloques)**:
  1. Navbar premium dark (blur, logo glow, links neón, botón VIP gradiente, barra de ligas).
  2. Tarjetas de picks: borde **neón por tier** (AV=verde, SEGURO=azul, PRINCIPAL=dorado), equipos lado a lado con **escudos reales** (API-Football vía `TEAM_IDS` embebido como `window.SHARPIQ_TEAM_IDS` + `sharpiqTeamLogo()`, fallback a iniciales), cuota como botón-pill, campo `analisis` renderizado.
  3. EN VIVO: agrupado por liga, score grande centrado, countdown animado, estados (EN VIVO pulsante/INICIANDO/FINAL), borde verde en grupos con pick.
  4. Estadísticas: curva de bankroll (sparkline SVG) en el dashboard.
  5. Predicciones: filtros combinados liga + resultado (Ganados/Perdidos/Pendientes), tabla premium.
- **Service Worker** (`sw.js`): `CACHE_VERSION` se bumpea en cada deploy para forzar recarga (va por **v22**). Importante seguir bumpeándolo.

---

## ESTADO ACTUAL DEL PROYECTO (29 mayo 2026)

### Última ejecución del motor (2026-05-29, 7:31 AM COT) — ✅ FUNCIONAL
- 150 predicciones generadas, 156 partidos de fútbol con Pinnacle.
- Mejor predicción: Athletic Club (MG) vs Fortaleza — Over 2.5.
- Saludo matutino enviado al canal free; tiers VIP enviados; `datos.js` actualizado (pick destacado: Stephanie Han @1.25); monitor en vivo iniciado.

### Picks activos en datos.js (verificar al inicio de cada sesión)
- Copa Sudamericana 27/05: Cienciano vs CA Juventud — Under 2.5 @ 1.81
- Copa Sudamericana 27/05: Caracas vs Botafogo — Under 2.5 @ 1.75
- Copa Lib 28/05: Bolívar vs Ind. Rivadavia — Gana Bolívar @ 2.32
- Copa Lib 28/05: Corinthians vs Platense — Under 2.5 @ 1.96
- Copa Lib 28/05: Cerro Porteño vs Sporting Cristal — Under 2.5 @ 1.89
- Copa Lib 28/05: Peñarol vs Independiente Santa Fe — Under 2.5 @ 1.79
- Copa Lib 29/05: Boca Juniors vs U. Católica — Under 2.5 @ 2.01
- Champions League Final 30/05: PSG vs Arsenal — **Under 2.5 @ 1.90** (PRINCIPAL, stake 2%; corregido tras recalibrar blend)

### Historial reciente (últimos 10): 8W / 2L
OKC Thunder ✓ · Vegas Golden Knights ✓ · Jelena Ostapenko ✓ · Mariano Navone ✓ · Cleveland Cavaliers ✓ · Milwaukee Brewers ✓ · Olimpia Asunción Under ✓ · Montréal Canadiens ✓ · Moutet ✗ · Marin Cilic ✗

### Estado por subsistema
| Subsistema | Estado | Notas |
|-----------|--------|-------|
| Motor predicciones | ✅ | Genera 150+ picks/día, análisis OK |
| Publicación Telegram | ✅ | 3 tiers (seguro/principal/alto_valor) |
| Live scores / monitor | ✅ | Update 10 min / alertas 5 min |
| Backend API (Railway) | ✅ | auth, pagos, picks, referidos |
| Git push (motor) | ✅ | Robusto: commit primero, reintentos, aborta rebase en conflicto |
| Web sharpiq.co | ✅ | Rediseño Sofascore completo (5 bloques), tema oscuro, escudos reales, EN VIVO, bankroll |

---

## QUÉ FALTA / PENDIENTES

### Bugs / deuda técnica conocida
- _(resuelto 29/05)_ ~~Scripts `fix_*.py` sueltos en raíz~~ — eliminados; eran parches de migración de un solo uso ya aplicados (el bloque inline `SHARPIQ_DATA` ya vive en `index.html`).

### Roadmap / mejoras planificadas
- **2026-06-08**: contratar **API-NBA Pro $19/mes** para player props NBA (puntos, rebotes, asistencias).
- Expansión futura del negocio: eSports → crypto → forex.

### Cerrado en la sesión 29/05 (segunda tanda)
- **CLV tracking (`db_clv.py` + PostgreSQL) integrado al flujo automático**: `auto_publicar.py` inserta el mejor pick en apertura (`guardar_pick`, con `inicializar()` idempotente) y `auto_resultados.py` registra el cierre (`actualizar_cierre`) y el resultado (`actualizar_resultado`). Las 3 escrituras casan por `(partido, mercado)` usando la misma clave canónica de `_pred_to_mercado_key` (`over25`, `victoria_local`, …). Todo envuelto en try/except → no-op silencioso si `DATABASE_PUBLIC_URL`/psycopg2 no están configurados (no rompe el flujo de producción). Convive con el CLV en SQLite (`database.py`), que sigue siendo la fuente que alimenta la web. Ver [[project-motor-estado]].
- **`INSTRUCCIONES.md` reescrito**: ahora documenta SharpIQ (las 3 piezas, operación diaria, workflows, config.py, seguridad, recordatorios de frontend) en vez de la plantilla genérica "kit web". Apunta a `CLAUDE.md` para el detalle técnico.

### Cerrado en la sesión 29/05 (cuarta tanda — BUG CRÍTICO de IDs)
- **`TEAM_IDS` estaba cruzado para casi todos los equipos no-europeos-top → CORRUPCIÓN DE PREDICCIONES.** Verificado contra API-Football: `Boca Juniors`→405 (Odense, Dinamarca), `River Plate`→547 (Girona), `Fortaleza`→2020 (Milton SC, Canadá), `Athletic Club`→532 (Valencia), toda la Liga MX corrida, Uruguay/Perú/Chile/Brasil mezclados con europeos. Como `obtener_forma_reciente`/H2H/lesiones hacen `TEAM_IDS.get(equipo)`, **los picks de CONMEBOL y Liga MX se calcularon con forma del equipo equivocado.** Regenerado desde API-Football trayendo equipos **por-liga** (nombres oficiales, sin ambigüedad de búsqueda): 732 entradas en `motor.py`, 745 en el frontend (`SHARPIQ_TEAM_IDS`). Método confiable porque los nombres oficiales por-liga son exactamente los que el motor recibe de los fixtures. Colisión genuina manejada: `Athletic Club` existe idéntico en España (Bilbao 531) y Brasil (MG 13975) → default Brasil + key `athletic club mg` para desambiguar.
- **Logos del frontend (`sharpiqTeamLogo`) reescritos**: (1) IDs corregidos arriba; (2) matcher endurecido — conserva el paréntesis para desambiguar (`Athletic Club (MG)`→13975 vs Valencia), fuzzy ESTRICTO por subconjunto de palabras (antes `indexOf` con `len≥4` daba falsos positivos: la clave `club` matcheaba casi todo); (3) **logos multideporte ESPN CDN** (`SHARPIQ_SPORT_LOGOS`, 95 equipos NHL/NBA/MLB → `a.espncdn.com/i/teamlogos/{liga}/500/{abbr}.png`) — antes solo había escudos de fútbol (API-Football) y NHL/NBA/MLB salían con iniciales. Verificado: todas las URLs devuelven `200 image/png`. SW v23→v24.
- **Factor ALTITUD real implementado** (antes solo documentado): `_ALTITUD_EQUIPOS` + `_factor_altitud()` en `motor.py` reducen los goles en `calcular_goles_esperados` según la altura del estadio **local**, cargando el grueso sobre el visitante de tierra baja (el local está aclimatado). Bandas calibradas con los efectos documentados: La Paz 3600m ≈−23%, Cusco 3400m ≈−18%, Quito/Pasto 2850m ≈−12%, Bogotá 2640m ≈−8%, Medellín 1500m ≈−2%. **No aplica en sede neutral** (finales) y **se suaviza si el visitante también es de altura** (aclimatado). Cierra la mayor brecha entre la metodología documentada y el código.
- **xG `disparos_contra` verificado — NO era bug numérico**: los 3 consumidores leían el campo como "disparos a puerta propios" y `stats_mercados` guardaba ahí `shots.on` (a puerta), así que el cálculo era correcto. Se saneó el **nombre engañoso**: `disparos_favor`→`disparos_totales`, `disparos_contra`→`disparos_puerta` en todo el código + esquema SQLite (con **migración segura**: `inicializar()` descarta la tabla `stats_ext_cache` vieja, regenerable TTL 7d). Docstring de `xg_integracion.py` corregido (0.33 y blend 75/25, no 0.35 / 60/40).
- **Fin del fallback silencioso a stats default → flag NO CONFIABLE**: `get_stats_equipo` ya no inventa stats `{1.35,1.35,0.75}` en silencio; loguea `⚠ Sin stats reales` y marca `_sin_datos`. `calcular_goles_esperados` calcula `no_confiable = sin_datos AND sin forma reciente` (guardado en `_CONF_CACHE` por par local/visitante) y lo loguea. `predecir_partido` y el analizador sharp-odds adjuntan `"confiable"` al pick. **`clasificar_tiers` y `seleccionar_mejor_prediccion` excluyen los no confiables** → un pick basado en datos inventados nunca llega a suscriptores ni a la web. Resuelve el punto débil #4 (datos inventados sin aviso).

---

## Comandos frecuentes
```bash
# Correr el motor manualmente
cd sharpiq-engine && python motor.py

# Publicar picks del día (datos.js + Telegram + git push)
cd sharpiq-engine && python auto_publicar.py

# Resolver resultados (W/L)
cd sharpiq-engine && python auto_resultados.py

# Inspeccionar un partido antes de analizar
cd sharpiq-engine && python stats_partido.py "Local" "Visitante"

# Verificar sintaxis del motor
python -m py_compile sharpiq-engine/motor.py

# Levantar la API localmente
uvicorn sharpiq-engine.api.main:app --reload

# Pipeline completo local (Windows)
sharpiq-engine\run-motor.bat
```
