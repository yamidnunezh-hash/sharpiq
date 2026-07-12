// ═══════════════════════════════════════════════════════════════
//  EL TIPSTER EXPERTO — picks curados a mano (selección humana)
//  Este archivo NO lo toca el motor. Estadística INDEPENDIENTE
//  del modelo automático. Editar a mano para agregar/actualizar.
//
//  Para AGREGAR un pick: copia un bloque { ... } dentro del array.
//  Campos:
//    fecha       "2026-07-08"
//    partido     "Equipo A vs Equipo B"
//    liga        "Mundial 2026"
//    mercado     "Remates" | "Córners" | "Tarjetas" | "Combinada" | ...
//    prediccion  "Egipto +6.5 tiros"
//    cuota       "1.67"
//    analisis    "Tu análisis en texto (opcional)"
//    tier        "seguro" | "principal" | "alto_valor"
//    resultado   "pendiente" | "ganado" | "perdido"
// ═══════════════════════════════════════════════════════════════
window.TIPSTER_PICKS = [
  { fecha:"2026-07-11", partido:"Noruega vs Inglaterra", liga:"Mundial 2026",
    mercado:"Faltas de jugador", prediccion:"Erling Haaland — Más de 0.5 faltas cometidas", cuota:"1.53",
    analisis:"Pick del Tipster — analizado con datos reales (API-Football). Haaland promedia 1.25 faltas por partido en este Mundial (5 en 4 partidos), por encima de su registro general. Ante una Inglaterra físicamente fuerte que le disputará cada balón, se espera que baje a pelear y cometa al menos una falta. La línea de 0.5 (una sola falta basta) tiene respaldo en el dato del torneo. Mercado resuelto con Opta Data.",
    tier:"seguro", resultado:"pendiente" },   // Se liquida al FINAL con datos Opta — no marcar hasta que la casa lo confirme

  { fecha:"2026-07-10", partido:"España vs Bélgica", liga:"Mundial 2026",
    mercado:"Disparos a puerta", prediccion:"Lamine Yamal — Más de 1.5 disparos a puerta", cuota:"1.95",
    analisis:"Pick del Tipster — analizado junto a Mako AI 🦈. Yamal es el principal generador de peligro de España por banda derecha: entra desde el perfil zurdo a rematar y acumula tiros a puerta con regularidad. Ante una Bélgica que concede espacios entre líneas, se espera volumen de llegada. Elegimos la línea de 1.5 (y no la de 0.5) porque ahí está el valor real: a cuota 1.95 el mercado paga lo que el análisis vale. Mercado resuelto con Opta Data.",
    tier:"principal", resultado:"ganado" },   // 2 tiros a puerta al 61' (Opta) ✅ Más de 1.5 cumplido

  { fecha:"2026-07-09", partido:"Francia vs Marruecos", liga:"Mundial 2026",
    mercado:"Combinada", prediccion:"Más de 1.5 goles  +  Más de 8.5 córners", cuota:"1.66",
    analisis:"Combinada del Tipster (2 selecciones) — analizada junto a Mako AI 🦈. Francia llega con ataque potente y Marruecos con la defensa exigida (0.743 goles en contra en sus últimos 5), un escenario que empuja goles y córners: partido de alto ritmo y llegadas para ambos lados. Los dos mercados (Más de 1.5 goles y Más de 8.5 córners) son de los más fuertes de nuestro historial.",
    tier:"principal", resultado:"ganado" },   // 2-0 (2 goles) · 5+5 = 10 córners ✅
];
