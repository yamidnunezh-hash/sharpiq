// ============================================================
//  SharpIQ — ARCHIVO DE DATOS
//  Solo edita este archivo para actualizar la web.
//  No toques el HTML. Guarda el archivo y recarga el sitio.
// ============================================================

// ── PRÓXIMOS EVENTOS ─────────────────────────────────────────
// Agrega aquí los partidos de los próximos días.
// Cuando terminen, muévelos a PREDICCIONES_HISTORIAL y pon el resultado.
// status: "vip" = bloqueado para no suscriptores, "free" = visible para todos
const PROXIMOS_EVENTOS = [
  {
    fecha:      "18/05/26",
    partido:    "Barcelona vs Villarreal",
    liga:       "LaLiga",
    prediccion: "Barcelona Gana + Over 1.5",
    cuota:      "1.65",
    hora:       "21:00 CET",
    status:     "vip"
  },
  {
    fecha:      "18/05/26",
    partido:    "Celtics vs Knicks",
    liga:       "NBA",
    prediccion: "Over 215.5 Puntos",
    cuota:      "1.88",
    hora:       "01:30 CET",
    status:     "vip"
  },
  {
    fecha:      "19/05/26",
    partido:    "Man City vs Man United",
    liga:       "Premier League",
    prediccion: "Ambos Marcan — Sí",
    cuota:      "1.73",
    hora:       "17:30 CET",
    status:     "vip"
  },
  {
    fecha:      "20/05/26",
    partido:    "PSG vs Marseille",
    liga:       "Ligue 1",
    prediccion: "PSG -1 Hándicap",
    cuota:      "1.92",
    hora:       "21:00 CET",
    status:     "vip"
  }
];

// ── HISTORIAL DE PREDICCIONES ─────────────────────────────────
// Las primeras 3 entradas son visibles al público.
// El resto queda bloqueado (solo VIP).
// resultado: "win" | "loss" | "pending"
const PREDICCIONES_HISTORIAL = [
  {
    fecha:      "17/05/26",
    partido:    "Arsenal vs Chelsea",
    liga:       "Premier League",
    prediccion: "Over 2.5 Goles",
    cuota:      "1.78",
    resultado:  "win"
  },
  {
    fecha:      "17/05/26",
    partido:    "Lakers vs Celtics",
    liga:       "NBA",
    prediccion: "Total Over 218.5",
    cuota:      "1.91",
    resultado:  "win"
  },
  {
    fecha:      "16/05/26",
    partido:    "Real Madrid vs Atlético",
    liga:       "LaLiga",
    prediccion: "Ambos Marcan",
    cuota:      "1.82",
    resultado:  "loss"
  },
  {
    fecha:      "15/05/26",
    partido:    "PSG vs Bayern Munich",
    liga:       "Champions League",
    prediccion: "Hándicap -0.5",
    cuota:      "2.10",
    resultado:  "win"
  },
  {
    fecha:      "15/05/26",
    partido:    "Warriors vs Nuggets",
    liga:       "NBA",
    prediccion: "Spread -4.5",
    cuota:      "1.95",
    resultado:  "win"
  },
  {
    fecha:      "14/05/26",
    partido:    "Inter vs Juventus",
    liga:       "Serie A",
    prediccion: "Over 2.5 Goles",
    cuota:      "1.72",
    resultado:  "win"
  },
  {
    fecha:      "13/05/26",
    partido:    "Barcelona vs Sevilla",
    liga:       "LaLiga",
    prediccion: "1 Resultado Local",
    cuota:      "1.55",
    resultado:  "win"
  },
  {
    fecha:      "12/05/26",
    partido:    "Dortmund vs Leipzig",
    liga:       "Bundesliga",
    prediccion: "Over 2.5 Goles",
    cuota:      "1.69",
    resultado:  "win"
  },
  {
    fecha:      "11/05/26",
    partido:    "Roma vs Napoli",
    liga:       "Serie A",
    prediccion: "Doble Oportunidad 1X",
    cuota:      "1.44",
    resultado:  "loss"
  },
  {
    fecha:      "10/05/26",
    partido:    "Heat vs Thunder",
    liga:       "NBA",
    prediccion: "Thunder Gana",
    cuota:      "1.77",
    resultado:  "win"
  }
];
