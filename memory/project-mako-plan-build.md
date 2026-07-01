---
name: project-mako-plan-build
description: PLAN ORGANIZADO para construir Mako (asistente IA de SharpIQ) + modelo Free/creditos + rentabilidad + arquitectura NBA/multideporte. Fase de ideas CERRADA 2026-06-30, listo para empezar a codear.
metadata:
  type: project
---

# Mako — plan de construccion (cerrado 2026-06-30, listo para iniciar)

Extension de [[project-sharpiq-os-vision]]. **Mako** = asistente IA de SharpIQ (SharpIQ AI,
el producto de creditos). El cliente le pregunta LIBRE por un partido ("cuantos remates hace
Mbappe?", "Ecuador pierde con Mexico?") y responde con analisis aterrizado en los datos del
motor. NO apuesta por el cliente (sin promesa = menos riesgo legal). Nombre elegido: Mako
(tiburon rapido/inteligente; un apostador PRO = "un sharp"). Descarto "Alfred" (proyecto viejo)
y "Finn" (suena a "fin" en espanol).

## Modelo Free / creditos (AFINADO — decidido)
- **1 pregunta a Mako = 1 credito.**
- **Picks (vista previa): GRATIS PARA SIEMPRE** (2 picks/dia bloqueados en Free, todos en Pro).
  Es el iman de leads + confianza; casi $0 de costo mostrarlos. NO se limita por tiempo.
- **Mako (la IA, que SI cuesta): PRUEBA "7 dias O 10 preguntas, lo que llegue primero"** ->
  despues solo Pro/Elite. (Frase oficial/marketing: "7 dias o 10 preguntas, lo que llegue
  primero" = doble candado.) Regla clave: NO matar el free de los picks, solo el free de la IA.
- **Pro ($60.000 COP/mes):** Mako ~5/dia (~150/mes) + todo lo actual.
- **Elite (~$100.000/mes, precio a confirmar):** Mako ~20/dia (~600/mes).
- **Paquete extra:** +50 creditos por ~$15k (no vencen) — ingreso adicional.
- **4 candados de costo:** (1) exige CUENTA (captura email/lead, no anonimo), (2) reset diario
  en pagos, (3) modelo economico, (4) cache. + preguntas simples (corners/tarjetas) por
  PLANTILLA del motor = $0 (la IA solo para lo conversacional).

## Rentabilidad (numeros REALES — verificados con la referencia de la API)
- Modelo: **Claude Haiku** ($1/M input, $5/M output — pricing oficial). Es el correcto para
  Mako: alto volumen, tarea simple (traducir pregunta + redactar sobre datos ya calculados).
- **Costo por pregunta ~2.300 tok in + ~300 tok out ≈ $0,004 USD ≈ 15 COP.** Menos con cache.
- Pro: costo IA ~2.300 COP/mes vs $60k -> **margen ~96%**. Elite: ~9.100 COP vs $100k -> ~91%.
- Free: ~1.400 COP/mes por usuario que lo exprima = costo de adquisicion (1 cliente Pro paga
  ~43 free). Controlado por el sistema de creditos + el trial de 7d/10preg.
- **Veredicto: muy rentable; el unico gasto a vigilar es el Free y ya esta amarrado.**

## Arquitectura del box Mako (que construir)
```
Cliente pregunta libre
  -> [1] GUARDIA DE CREDITOS (¿tiene? -1; si 0 -> "sube a Premium")
  -> [2] MAKO INTERPRETA (IA barata: ¿que partido? ¿que dato?)
  -> [3] MOTOR (ya existe: motor.py, mercados_profundos, player_props) saca numeros reales <-> CACHE
  -> [4] MAKO REDACTA (IA Haiku + PROMPT: aterrizado, sin promesas, con tono) + SharpScore
  -> respuesta + registra uso
```
YA existe: motor+datos, auth, planes/pagos, web, bot Telegram, SharpScore(ingredientes).
NUEVO a construir: interfaz de chat, sistema de creditos (tabla+descuento), capa IA
(interprete+redactor), PROMPT/cerebro de Mako, cache. El PROMPT es obligatorio (aterriza +
seguridad + tono). Cliente escribe libre; Mako se comporta segun su prompt. Semanas, no meses.

## NBA / multideporte (decidido)
- **UN solo motor, modulos por deporte.** El corazon (EV, tiers, SharpScore, Mako, web, pagos)
  se comparte; cada deporte agrega su modulo de stats. **Mako es agnostico**: lee lo que el
  motor produzca -> el dia que el motor analice NBA, Mako responde de NBA solo.
- **Deportes PROFUNDOS por ahora: NBA + Futbol.** Otros deportes: segun lo que pidan los
  clientes, mas adelante.
- **NBA basico (ganador/handicap/over-under) YA se puede via The Odds API (sin costo nuevo).**
- **NBA profundo (props de jugador: puntos/rebotes/asistencias) -> API-NBA ~$19/mes, en
  OCTUBRE 2026** (temporada). Ver [[project-recordatorio-api-nba-oct2026]].

## APIs (que se paga)
- The Odds API (~$59/mes) — cuotas MULTIDEPORTE (futbol, NBA, tenis, NHL, MLB). YA se paga;
  cubre NBA basico sin costo extra. Ver [[project-odds-api-renovada-2026-06-28]].
- API-Football PRO — stats profundas de FUTBOL. YA se paga.
- Football-Data — fixtures, gratis.
- API-NBA (~$19/mes) — props NBA, comprar en octubre 2026.
- Regla de oro: el motor central cubre muchos deportes con lo que ya se paga; solo se agrega
  una API nueva para PROFUNDIDAD de un deporte cuando vale la pena (en temporada + demanda).

## Orden de ejecucion (financiado por clientes, no por fe)
1. HOY: vender **Pro** (ya existe) + **SharpScore** (arma de venta, ingredientes listos, dias
   no meses) + suavizar lenguaje legal -> conseguir 10-20 clientes.
2. Con ingresos: construir **Mako + creditos** (dinero recurrente).
3. Con traccion: API/expansion (LATAM -> Espana -> Brasil -> ingles), NBA en octubre.
Trampa a evitar: enamorarse del plan a 5 anos con 1-3 clientes. Primero vender.

## Refinamientos de posicionamiento (aportados por ChatGPT, aprobados 2026-06-30)
- **Nombre de venta: "Mako AI Analyst"** (NO "chatbot") -> es un ANALISTA deportivo personal.
- **Copy de creditos SUAVE** (no vender, invitar): al quedar 1 -> "Te queda 1 consulta gratuita";
  al llegar a 0 -> "Has utilizado las 10 consultas incluidas. Mako puede seguir analizando
  cualquier partido al instante con SharpIQ Pro."
- **Explicabilidad SIEMPRE**: nunca "compra este pick"; explicar el porque (xG, fatiga, lesiones,
  localia, clima, cuotas, valor). Genera confianza. (Ya se hace en el campo analisis; formalizar.)
- **"Knowledge Graph"**: que Mako responda con TU conocimiento (el motor), no lo que Claude invente.
  REALIDAD (yo conozco el codigo): ya medio existe = predicciones.json (prob/EV/forma/xG por partido).
  Alimentar a Mako con esos datos estructurados = aterrizado. No hace falta un "graph" exotico para v1.
- **Mako Memory** (recuerda ligas favoritas, banca, historial del usuario) = FASE 2, una tabla de
  perfil + inyeccion al prompt. Va DESPUES de Mako v1, cuando haya usuarios.
- **Mentalidad "activos, no funciones"**: cada desarrollo = un activo dificil de copiar (SharpScore,
  Mako, track record verificado, motor mejorado, perfil del usuario). PERO el activo #1 hoy son
  USUARIOS + PLATA; los demas compounden solo si la empresa vive. Vender primero.
- **Roles**: ChatGPT = estrategia (CSO), Yamid = CEO/Product, Claude Code = ingeniero que construye.
  La estrategia solo vale cuando se convierte en codigo que funciona -> loop apretado idea->construir->aprender.
- **Project Atlas / SharpIQ v2.0** = plan maestro con 4 "biblias" (Product / Technical / Growth / AI).
  Mantenerlas LIGERAS y vivas (las memorias del proyecto ya cumplen ese rol), no un proyecto de docs.

## Como trabajamos
ChatGPT = estrategia/ideas (a ciegas). Claude Code (yo) = ejecucion en el repo real (ya anclado
en VS Code). NO anclar 2 agentes de codigo al mismo repo. Yamid = dueno/vision.
