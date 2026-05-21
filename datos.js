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
    fecha:      "21/05/26",
    partido:    "VfL Wolfsburg vs SC Paderborn 07",
    liga:       "Bundesliga",
    prediccion: "Victoria Visitante (2)",
    cuota:      "2.12",
    hora:       "13:30 COT",
    status:     "vip"
  },
  {
    fecha:      "21/05/26",
    partido:    "Águilas Doradas vs Deportivo Pereira",
    liga:       "Copa Colombia",
    prediccion: "Victoria Local (1)",
    cuota:      "2.30",
    hora:       "15:30 COT",
    status:     "vip"
  },
  {
    fecha:      "21/05/26",
    partido:    "Jaguares vs Ind. Yumbo",
    liga:       "Copa Colombia",
    prediccion: "Victoria Local (1)",
    cuota:      "2.30",
    hora:       "16:00 COT",
    status:     "vip"
  },
  {
    fecha:      "21/05/26",
    partido:    "Atletico-MG vs Cienciano",
    liga:       "Copa Sudamericana",
    prediccion: "Victoria Local (1)",
    cuota:      "2.30",
    hora:       "17:00 COT",
    status:     "vip"
  },
  {
    fecha:      "21/05/26",
    partido:    "Puerto Cabello vs Juventud",
    liga:       "Copa Sudamericana",
    prediccion: "Victoria Local (1)",
    cuota:      "2.30",
    hora:       "17:00 COT",
    status:     "vip"
  },
  {
    fecha:      "21/05/26",
    partido:    "Deportivo La Guaira vs Independ. Rivadavia",
    liga:       "Copa Libertadores",
    prediccion: "Victoria Local (1)",
    cuota:      "2.30",
    hora:       "17:00 COT",
    status:     "vip"
  },
];

// ── HISTORIAL DE PREDICCIONES ─────────────────────────────────
// Las primeras 3 entradas son visibles al público.
// El resto queda bloqueado (solo VIP).
// resultado: "win" | "loss" | "pending"
// ORDEN: más reciente primero — el algoritmo calcula racha desde arriba.
const PREDICCIONES_HISTORIAL = [
  {
    fecha:      "20/05/26",
    partido:    "Fortaleza FC vs Orsomarso",
    liga:       "Copa Colombia",
    prediccion: "Victoria Local (1) — EV +0%",
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
