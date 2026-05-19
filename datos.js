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
    fecha:      "19/05/26",
    partido:    "Club Always Ready vs Mirassol FC",
    liga:       "Copa Libertadores",
    prediccion: "under25 — EV +19.2%",
    cuota:      "6.4",
    hora:       "19:00 COT",
    status:     "free"
  },

  {
    fecha:      "19/05/26",
    partido:    "Fluminense FC vs Club Bolívar",
    liga:       "Copa Libertadores",
    prediccion: "under25 — EV +54.1%",
    cuota:      "1.21",
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
