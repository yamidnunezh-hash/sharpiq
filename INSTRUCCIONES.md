# SharpIQ — Guía de operación

> **SharpIQ — "La ventaja inteligente"**
> Plataforma de predicciones deportivas basada en IA y modelos estadísticos.
> Dominio: **sharpiq.co** · API: **api.sharpiq.co**
>
> Para la documentación técnica completa (arquitectura, archivos, metodología de
> análisis) ver [`CLAUDE.md`](CLAUDE.md). Este documento es la guía rápida de operación.

---

## 1. Las 3 piezas del sistema

1. **Motor de predicciones (Python)** — `sharpiq-engine/*.py`
   Corre en GitHub Actions 4x/día. Analiza partidos, calcula EV vs Pinnacle,
   clasifica picks en tiers, publica en Telegram y actualiza la web.
2. **Backend API (FastAPI + PostgreSQL)** — `sharpiq-engine/api/`
   Corre en Railway. Maneja usuarios, login JWT, suscripciones MercadoPago y referidos.
3. **Frontend web estático (HTML/CSS/JS + PWA)** — raíz del repo
   Servido por GitHub Pages (`sharpiq.co`): vitrina pública, área de cuenta, panel admin.

```
GitHub Actions (cron 4x/día) ──► motor.py ──► predicciones.json
                                      │
                          auto_publicar.py
                          ├─► datos.js + index.html  ──► git push ──► GitHub Pages (sharpiq.co)
                          ├─► Telegram VIP / Free
                          └─► push notifications
Railway (FastAPI) ──► api.sharpiq.co (auth, pagos, picks, referidos)
Cloudflare Worker ──► webhook MercadoPago ──► invita/expulsa del canal VIP
```

---

## 2. Operación diaria

### El motor corre solo
GitHub Actions ejecuta el pipeline automáticamente (horas en COT = UTC-5):

| Workflow | Frecuencia | Qué hace |
|----------|-----------|----------|
| `motor.yml` | 7am, 11am, 3pm, 7pm | resultados → recolector → motor → publicar |
| `resultados.yml` | 11pm | resuelve W/L del día |
| `live_scores.yml` | cada 10 min | actualiza `live_scores.json` |
| `live_monitor.yml` | cada 5 min | alertas Telegram en vivo |

**No hay que hacer nada manualmente** para la operación normal. Los comandos de abajo
son solo para pruebas, depuración o publicaciones puntuales.

### Correr el motor a mano (Windows)
```bat
SHARPIQ.bat                          REM motor.py + abre el panel en :8080
sharpiq-engine\run-motor.bat         REM pipeline completo local
```

### Comandos Python frecuentes
```bash
cd sharpiq-engine

python motor.py                      # generar predicciones del día
python auto_publicar.py             # publicar: datos.js + Telegram + git push
python auto_resultados.py           # resolver resultados (W/L) + CLV de cierre
python stats_partido.py "Local" "Visitante"   # inspeccionar un partido

python -m py_compile motor.py        # verificar sintaxis antes de commitear
```

### Levantar la API localmente
```bash
uvicorn sharpiq-engine.api.main:app --reload
```

---

## 3. Configuración (config.py)

⚠️ **`sharpiq-engine/config.py` está gitignored y NUNCA se debe subir.** Contiene claves reales.
Si falta, el motor no corre. Define como mínimo:

```
FOOTBALL_DATA_KEY, ODDS_API_KEY, APIFOOTBALL_KEY
TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_YAMID_ID, TELEGRAM_FREE_ID
PANEL_TOKEN, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY
MP_ACCESS_TOKEN, CF_* (Cloudflare)
DATABASE_URL          # PostgreSQL Railway (API)
DATABASE_PUBLIC_URL   # PostgreSQL Railway (CLV tracking, db_clv.py)
```

En GitHub Actions estas claves viven como **Secrets** del repositorio, no en `config.py`.

---

## 4. Seguridad crítica

- **NUNCA** hacer `git push` de `config.py` ni de `vapid_private.pem` — contienen claves reales.
  Verificar `.gitignore` SIEMPRE antes de commitear.
- `predicciones.json` y `mejor_prediccion.json` están gitignored (se regeneran solos).
- No exponer API keys al frontend: las cuotas y marcadores se sirven vía JSON pre-generado.

---

## 5. Frontend — recordatorios

- **`index.html` y `estadisticas.html` NO llaman a la API**: leen los datos incrustados
  inline (bloque `<!-- SHARPIQ_DATA_START -->`, equivalente a `datos.js`).
- **`cuenta.html`, `login.html`, `registro.html`, `bienvenido.html` SÍ llaman a la API**
  (`api.sharpiq.co`): auth, dashboard, picks, pagos, referidos.
- **Service Worker (`sw.js`)**: al hacer cualquier deploy de la web hay que **subir
  `CACHE_VERSION`** (ej. `sharpiq-v22` → `v23`) para forzar la recarga en los navegadores.
- ⚠️ El `innerHTML` de `navAuthArea` lo sobrescribe el JS → no meter elementos dentro.

---

## 6. Estructura del repositorio

```
kit-web-scrolling/
├── INSTRUCCIONES.md     <- Este archivo (guía de operación)
├── CLAUDE.md            <- Documentación técnica completa
├── index.html           <- Landing (picks + historial inline)
├── estadisticas.html    <- Stats: KPIs, gráficas Chart.js, simulador
├── predicciones.html    <- Panel admin del motor
├── admin.html           <- Panel admin completo
├── login/registro/cuenta/bienvenido.html  <- Área de usuario (usan la API)
├── datos.js             <- Datos editados por el motor
├── sw.js / manifest.json / CNAME           <- PWA + dominio
├── assets/              <- logo, favicon, hero.mp4, imágenes
├── .github/workflows/   <- Automatización (motor, resultados, live)
└── sharpiq-engine/      <- Motor Python + API FastAPI
    ├── motor.py             <- Core de predicciones
    ├── auto_publicar.py     <- Publicación (web + Telegram + git)
    ├── auto_resultados.py   <- Resolución de W/L + CLV de cierre
    ├── database.py / db_clv.py  <- Persistencia (SQLite / PostgreSQL CLV)
    └── api/                 <- Backend FastAPI (Railway)
```

Para el inventario detallado de cada archivo, la metodología de análisis de partidos
y los tiers de publicación, ver **[`CLAUDE.md`](CLAUDE.md)**.