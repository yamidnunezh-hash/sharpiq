---
name: project-sharpiq-os-vision
description: Vision estrategica SharpIQ OS (2026-06-30) — pivote a vender el MOTOR de analisis (no los picks), ecosistema de 4 productos, asistente IA llamado "Mako". FASE DE IDEAS, nada construido aun.
metadata:
  type: project
---

# SharpIQ OS — vision estrategica (fase de ideas, 2026-06-30)

Yamid quiere evolucionar SharpIQ de "vendo picks" a **plataforma de inteligencia deportiva**
("SharpIQ OS", tipo Bloomberg/TradingView: vendes la herramienta, no la apuesta). Surgio de
conversaciones con ChatGPT + refinado conmigo. **IMPORTANTE: es fase de ORGANIZAR IDEAS, no
hemos construido nada de esto todavia.**

## El pivote clave
Vender el **MOTOR de analisis** (decision-support), NO el pick. El motor da probabilidades,
EV, riesgo, forma y un SharpScore -> **el cliente decide**. Ventajas: (1) sin promesa =
menos riesgo legal, (2) uso recurrente = mas dinamico, (3) mas facil de vender. Matiz mio:
conservar una "jugada sugerida" redactada como analisis probabilistico SIN garantia (mantener
el gancho de la recomendacion sin la promesa peligrosa).

## Insight que lo hace alcanzable: UN motor, 4 llaves
Los "4 productos" NO son 4 empresas — son el MISMO motor (que ya existe = el moat) abierto de
4 formas:
- **SharpIQ Lite** (gratis): 2 picks, stats, historial, comunidad. Atrae miles. ~90% listo.
- **SharpIQ Pro** ($60k COP/mes): lo actual. 100% listo, YA VENDE.
- **SharpIQ AI** (creditos): el asistente **"Mako"** — preguntale al motor por un partido y
  responde con analisis (no apuesta por ti). "Aqui esta el dinero" recurrente. Motor listo,
  falta capa IA + sistema de creditos. Modelo freemium: pocos creditos gratis (con cuenta =
  captura leads), Premium/VIP muchos mas. Ver [[project-pago-vip-register-first-2026-06-29]].
- **SharpIQ API** (devs): exponer /predictions /valuebet /devig /expectedgoals. El motor ya
  calcula todo, falta exponerlo.

## Mako (nombre del asistente IA)
- Reemplaza "Alfred" (nombre de un proyecto ANTERIOR — Yamid NO quiere nada de esa pagina).
- "Finn" se descarto: suena a "fin" (terminar) en espanol.
- **Mako** = tiburon mako (el mas rapido/inteligente). Doble sentido: un apostador PRO se llama
  "un sharp". Sin mala connotacion en espanol ni ingles, escala internacional.

## SharpScore (idea top, alto valor / bajo esfuerzo)
Puntuacion propia 0-100 por pick (nivel + stake sugerido + riesgo) = marca de SharpIQ. Los
ingredientes YA existen en motor.py: probabilidad (Poisson/Dixon-Coles), EV vs Pinnacle,
tiers (clasificar_tiers), stake (kelly_stake), forma (obtener_forma_reciente), blend por
liquidez. Es EMPAQUETAR campos existentes, no construir de cero. Dias, no meses.

## Legal (hacer pronto, protege)
Suavizar lenguaje: "rentabilidad garantizada" / "EV positivo garantizado" -> "analisis
probabilistico, sin garantia de ganancias".

## Expansion / mercado
Colombia -> LATAM -> Espana -> Brasil -> ingles. El motor "habla de numeros", escala sin
fronteras. Partners (no MLM): 30% recurrente mientras el referido pague (modelo SaaS limpio).

## Orden de ejecucion (disciplina — financiado por clientes, NO por fe)
1. HOY: vender **Pro** (ya existe) + **SharpScore** (arma de venta) + suavizar legal ->
   conseguir 10-20 clientes primero.
2. Con ingresos: construir **AI/Mako + creditos** (dinero recurrente).
3. Con traccion: **API** + expansion LATAM.
4. Escala: cursos, inversion, marca continental.
La trampa a evitar: enamorarse del plan a 5 anos (SharpIQ 2030 / $100M) y descuidar conseguir
los primeros clientes. Un plan hermoso con 0-3 clientes es fantasia.

## Division de trabajo acordada
ChatGPT = estrategia/lluvia de ideas (a ciegas, sin el codigo). Claude Code (yo) = ejecucion
en el repo real (ya anclado en VS Code, no necesita que le peguen archivos). Yamid = dueno/
vision. NO anclar dos agentes de codigo al mismo repo (se pisan).

## Mako: DECIDIDO (2026-06-30) — ver [[project-mako-plan-build]]
Interfaz: el cliente pregunta LIBRE (lenguaje natural) + Mako con PROMPT obligatorio (aterriza
+ seguridad + tono). Modelo Haiku (~15 COP/pregunta). Free: picks gratis para siempre, pero
Mako en prueba "7 dias O 10 preguntas, lo que llegue primero". Creditos: Pro 5/dia, Elite 20/dia.
NBA/multideporte: un motor, modulos por deporte (deep = NBA+futbol por ahora); API-NBA en oct
2026 ([[project-recordatorio-api-nba-oct2026]]). Fase de IDEAS cerrada, listo para codear.

## Pendiente
- Precio final del plan Elite (~$100k propuesto, a confirmar).
- Empezar el trabajo: recomendado SharpScore primero (arma de venta), luego construir Mako.
- Documento maestro "SharpIQ OS" de 1-2 paginas como norte (opcional, no hecho aun).
