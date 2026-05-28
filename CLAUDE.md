# SharpIQ — Contexto Completo del Proyecto

## Qué es SharpIQ
Plataforma de predicciones deportivas basada en IA y modelos estadísticos.
Eslogan: **"La ventaja inteligente"**
Usuario: Yamid Núñez — ingeniero SENA Cazucá. SharpIQ es su proyecto de vida.
**Este es dinero real. Cada pick publicado impacta a suscriptores que apuestan con él.**

## Modelo de negocio
- Canal Telegram VIP → picks diarios (3 tiers)
- Canal Telegram Free → teaser del partido, no da el pick
- Web `sharpiq.co` → vitrina pública con picks, historial, stats
- Objetivo futuro: eSports → crypto → forex

## Arquitectura técnica

### Archivos clave
```
kit-web-scrolling/
├── index.html          # Web completa (todo en un solo archivo)
├── datos.js            # Picks actuales + historial (se edita manualmente o via motor)
├── sw.js               # Service Worker (caché, push notifications)
├── sharpiq-engine/
│   ├── motor.py        # Motor principal — analiza partidos y clasifica picks
│   ├── stats_mercados.py # Modelos Poisson para corners/tarjetas/remates
│   ├── auto_publicar.py  # Orquestador — corre el motor y publica en Telegram/web
│   ├── telegram_alertas.py # Mensajes a canales Telegram
│   ├── config.py        # API keys (GITIGNOREADO — nunca commitear)
│   ├── database.py      # SQLite para CLV tracking
│   └── logs/            # Logs de operación
```

### Flujo de publicación
1. `motor.py` → `guardar_predicciones()` → `analizar_futbol_sharp()` (fútbol) + `analizar_deporte_sharp()` (otros)
2. Cada partido se analiza contra cuotas Pinnacle → EV calculado para TODOS los mercados
3. `clasificar_tiers()` → selecciona 3 picks: SEGURO / PRINCIPAL / ALTO VALOR
4. `auto_publicar.py` → publica en Telegram VIP + actualiza datos.js + git push

### APIs utilizadas
- **The Odds API** → cuotas en tiempo real (Pinnacle + mejores bookmakers)
  - Mercados fútbol: `h2h, totals, alternate_totals, spreads (AH), btts, double_chance, draw_no_bet`
  - Mercados US sports: `h2h, spreads, totals`
  - CONMEBOL a veces solo soporta `h2h, totals`
- **API-Football (api-sports.io)** → estadísticas históricas, forma, H2H, lesiones
- **Pinnacle** → benchmark de probabilidad real (no-vig odds = precio justo del mercado)

### Tiers y criterios (datos-driven, NO por tipo de mercado)
| Tier | Prob mínima | EV vs Pinnacle | Cuota |
|------|------------|----------------|-------|
| SEGURO | ≥ 65% | > 0% | ≤ 1.95 |
| PRINCIPAL | ≥ 50% | ≥ 2% | 1.55 - 3.00 |
| ALTO VALOR | ≥ 20% | ≥ 7% | 1.75 - 10.0 |

Cualquier mercado puede ser cualquier tier — el mejor EV gana.

## SEGURIDAD CRÍTICA
**NUNCA** hacer git push de `config.py`. Contiene API keys reales.
El archivo está en `.gitignore`. Verificar SIEMPRE antes de commitear.

---

## Metodología de análisis de partidos

### Cuando Yamid pida analizar un partido, SIEMPRE evaluar estos factores:

**1. Calidad relativa de los equipos**
- ¿Cuál es la diferencia real de nivel? (coeficiente UEFA/CONMEBOL, posición en su liga)
- ¿El favorito es claro o es partido parejo?
- En Copa Lib: Grupos A/B tienen mejores equipos que C/D
- En Copa Suda: brecha de calidad mayor — equipos venezolanos/bolivianos son más débiles

**2. Factor altitud (CRÍTICO para CONMEBOL)**
| Ciudad | Altitud | Efecto en goles |
|--------|---------|-----------------|
| Cusco (Cienciano) | 3400m | -20% goles aprox |
| La Paz (Bolívar) | 3600m | -25% goles aprox |
| Quito (LDU/Ind. del Valle) | 2800m | -12% goles aprox |
| Bogotá (Millonarios/Santa Fe) | 2600m | -8% goles aprox |
| Medellín (Atlético Nacional) | 1500m | -2% goles aprox |

Un equipo argentino/brasileño nunca se adapta a 3600m en 24-48h de viaje.

**3. Local vs Visitante**
- Ventaja local en CONMEBOL es muy fuerte (~65% gana el local en Copa)
- Equipos brasileños/argentinos como visitante en Copa son más cautelosos
- Viaje largo (ej: Botafogo a Caracas) = cansancio, rotación posible

**4. Contexto de la competición**
- **Fase de grupos** (puntos): los equipos ATACAN para ganar → más goles que eliminatorias
- **Eliminatoria ida**: el visitante frecuentemente busca no perder → menos goles
- **Eliminatoria vuelta**: depende del marcador de ida
- ¿Qué se juega cada equipo? ¿Necesita ganar para clasificar?

**5. Forma reciente (últimos 5 partidos)**
- Equipo en racha positiva → más confianza, mejor juego
- Equipo en racha negativa → puede ser defensivo o desesperado
- Considerar si los partidos recientes fueron de liga o copa (diferentes intensidades)

**6. H2H (historial directo)**
- ¿Hay un equipo que domina históricamente este enfrentamiento?
- ¿Los partidos entre ellos suelen ser de pocos o muchos goles?
- H2H reciente (últimos 3) pesa más que histórico total

**7. Lesiones y bajas importantes**
- Si falta el goleador principal → menos goles
- Si falta el portero titular → más goles
- Suspensiones acumuladas en copa

**8. Estilo de juego**
- Equipos que presionan alto → partidos abiertos → más goles
- Equipos de bloque bajo → partidos cerrados → Under
- Equipos que contraatacan → goles en transición → puede ser cualquiera

---

## Framework de decisión para picks

### Para cada partido, completar esta evaluación:

```
ANÁLISIS: [Local] vs [Visitante]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Calidad: Local [MAYOR/IGUAL/MENOR] al visitante
Altitud: [Ciudad] [Xm] → [Sin efecto/Leve/Significativo/Extremo]
Contexto: [Grupo/Eliminatoria] — [Qué se juega cada equipo]
Forma local (últimos 5): [W-W-D-L-W tipo]
Forma visitante (últimos 5): [idem]
H2H reciente: [breve]
Estilo: [descripción breve de cómo juega cada equipo]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mercado recomendado: [Gana X / Under 2.5 / Over 1.5 / etc.]
Justificación: [1-2 oraciones]
Cuota objetivo: [rango donde hay valor]
Confianza: [ALTA / MEDIA / BAJA]
Veredicto: [PUBLICAR / ESPERAR / DESCARTAR]
```

### Reglas de publicación
- **PUBLICAR**: análisis cualitativo COINCIDE con EV positivo vs Pinnacle
- **ESPERAR**: EV positivo pero análisis cualitativo tiene dudas → buscar más info
- **DESCARTAR**: análisis cualitativo contradice el pick aunque EV sea positivo

**Nunca publicar solo por EV. El EV confirma el análisis, no lo reemplaza.**

### Cuándo usar cada mercado
| Mercado | Cuándo aplicar |
|---------|---------------|
| Gana X | Favorito claro (>70% prob) + altitud/local a favor |
| Under 2.5 | Equipos parejos + altitud + visita cautelosa |
| Over 2.5 | Gran diferencia de calidad (≥2 divisiones) + equipo local atacante |
| Over 1.5 | Favorito claro que marcará + equipo débil que también puede marcar |
| BTTS | Ambos equipos necesitan atacar (contexto de puntos) |
| Hándicap Asiático | Favorito muy claro pero cuota 1X2 muy baja |
| Draw No Bet | Favorito moderado donde el empate es el único riesgo |
| Double Chance | Partido parejo donde el favorito puede perder por poco |

---

## Estado actual del proyecto (mayo 2026)

### Picks activos en datos.js (verificar al inicio de cada sesión)
- Copa Sudamericana 27/05: Cienciano vs CA Juventud (17:00 COT) — Under 2.5 @ 1.81
- Copa Sudamericana 27/05: Caracas vs Botafogo (17:00 COT) — Under 2.5 @ 1.75
- Copa Lib 28/05: Bolívar vs Ind. Rivadavia (19:30 COT) — Gana Bolívar @ 2.32
- Copa Lib 28/05: Corinthians vs Platense (19:30 COT) — Under 2.5 @ 1.96
- Copa Lib 28/05: Cerro Porteño vs Sporting Cristal (17:00 COT) — Under 2.5 @ 1.89
- Copa Lib 28/05: Peñarol vs Independiente Santa Fe (19:30 COT) — Under 2.5 @ 1.79
- Copa Lib 29/05: Boca Juniors vs U. Católica (19:30 COT) — Under 2.5 @ 2.01
- Champions League Final 30/05: PSG vs Arsenal — Gana Arsenal @ 2.20 + Under 2.5 @ 1.90

### Historial reciente (últimos 10): 8W / 2L
- Oklahoma City Thunder WIN ✓ | Vegas Golden Knights WIN ✓
- Jelena Ostapenko WIN ✓ | Mariano Navone WIN ✓
- Cleveland Cavaliers WIN ✓ | Milwaukee Brewers WIN ✓
- Olimpia Asunción Under WIN ✓ | Montréal Canadiens WIN ✓
- Moutet LOSS ✗ | Marin Cilic LOSS ✗

### Recordatorios pendientes
- 2026-06-08: Contratar API-NBA Pro $19/mes para player props NBA

---

## Diseño web (index.html)
- CSS variables: `--bg0` a `--card`, `--t1` a `--t3`, `--border`
- Dark mode: `html[data-theme="dark"]` — toggle en navbar, persiste en localStorage
- Tiers colores: alto_valor=#F59E0B, principal=#0066CC, seguro=#22C55E
- Flash prevention en `<head>` antes del CSS
- `navAuthArea` su innerHTML es sobreescrito por JS → NO meter elementos dentro

## Comandos frecuentes
```bash
# Correr motor manualmente
cd sharpiq-engine && python motor.py

# Publicar picks del día
cd sharpiq-engine && python auto_publicar.py

# Verificar sintaxis motor
python -m py_compile sharpiq-engine/motor.py
```
