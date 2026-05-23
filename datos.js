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
    fecha:      "22/05/26",
    partido:    "Carolina Hurricanes vs Montréal Canadiens",
    liga:       "NHL",
    prediccion: "Gana Carolina Hurricanes",
    cuota:      "1.82",
    hora:       "13:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Colorado Avalanche vs Vegas Golden Knights",
    liga:       "NHL",
    prediccion: "Gana Vegas Golden Knights — EV +30%",
    cuota:      "3.65",
    hora:       "14:00 COT",
    status:     "vip"
  }
];

// ── HISTORIAL DE PREDICCIONES ─────────────────────────────────
// Las primeras 3 entradas son visibles al público.
// El resto queda bloqueado (solo VIP).
// resultado: "win" | "loss" | "pending"
// ORDEN: más reciente primero — el algoritmo calcula racha desde arriba.
const PREDICCIONES_HISTORIAL = [
  {
    fecha:      "22/05/26",
    partido:    "New York Yankees vs Tampa Bay Rays",
    liga:       "MLB",
    prediccion: "Tampa Bay Rays",
    cuota:      "",
    resultado:  "loss"
  },
  {
    fecha:      "21/05/26",
    partido:    "VfL Wolfsburg vs SC Paderborn 07",
    liga:       "Bundesliga",
    prediccion: "Victoria Visitante (2)",
    cuota:      "2.12",
    resultado:  "loss"
  },
  {
    fecha:      "20/05/26",
    partido:    "Fortaleza FC vs Orsomarso",
    liga:       "Copa Colombia",
    prediccion: "Victoria Local (1)",
    cuota:      "2.21",
    resultado:  "loss"
  },
  {
    fecha:      "19/05/26",
    partido:    "Independiente Santa Fe vs CA Platense",
    liga:       "Copa Libertadores",
    prediccion: "Over 2.5 Goles",
    cuota:      "2.24",
    resultado:  "win"
  },
  {
    fecha:      "19/05/26",
    partido:    "Club Always Ready vs Mirassol FC",
    liga:       "Copa Libertadores",
    prediccion: "Under 2.5 Goles",
    cuota:      "1.86",
    resultado:  "loss"
  },
  {
    fecha:      "19/05/26",
    partido:    "Fluminense FC vs Club Bolívar",
    liga:       "Copa Libertadores",
    prediccion: "Under 2.5 Goles",
    cuota:      "1.21",
    resultado:  "loss"
  },
  {
    fecha:      "19/05/26",
    partido:    "Chelsea FC vs Tottenham Hotspur FC",
    liga:       "Premier League",
    prediccion: "Under 2.5 Goles",
    cuota:      "2.12",
    resultado:  "loss"
  },
  {
    fecha:      "19/05/26",
    partido:    "AFC Bournemouth vs Manchester City FC",
    liga:       "Premier League",
    prediccion: "Under 2.5 Goles",
    cuota:      "2.88",
    resultado:  "win"
  },
  {
    fecha:      "19/05/26",
    partido:    "Chelsea vs Tottenham",
    liga:       "Premier League",
    prediccion: "Victoria Local (1)",
    cuota:      "1.97",
    resultado:  "win"
  },
  {
    fecha:      "18/05/26",
    partido:    "Bayern Munich vs PSG",
    liga:       "Champions League",
    prediccion: "Victoria Local (1)",
    cuota:      "2.24",
    resultado:  "loss"
  },
];
