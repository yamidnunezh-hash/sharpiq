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
  { fecha:"2026-07-08", partido:"Ponte Preta vs Criciúma", liga:"Brasileirão Serie B",
    mercado:"Disparos a puerta", prediccion:"Rómulo Otero — Más de 0.5 disparos a puerta", cuota:"1.64",
    analisis:"Análisis realizado junto a Mako AI 🦈 — Rómulo Otero es el rematador de mayor volumen de Criciúma (1.33 remates, 0.53 a puerta por partido) y referente en balón parado. El modelo proyecta ~3.6 disparos a puerta del visitante, lo que respalda su línea individual. Valor en el +0.5 disparos a puerta.",
    tier:"principal", resultado:"pendiente" },
];
