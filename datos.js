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
    partido:    "Chelsea vs Tottenham",
    liga:       "Premier League",
    prediccion: "Victoria Local (1)",
    cuota:      "1.72",
    hora:       "20:00 COT",
    status:     "free"
  },

  {
    fecha:      "18/05/26",
    partido:    "Bayern Munich vs PSG",
    liga:       "Champions League",
    prediccion: "Victoria Local (1)",
    cuota:      "2.24",
    hora:       "16:00 COT",
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
    fecha:      "19/05/26",
    partido:    "Chelsea vs Tottenham",
    liga:       "Premier League",
    prediccion: "Victoria Local (1)",
    cuota:      "1.72",
    resultado:  "pending"
  },
  {
    fecha:      "18/05/26",
    partido:    "Bayern Munich vs PSG",
    liga:       "Champions League",
    prediccion: "Victoria Local (1)",
    cuota:      "2.24",
    resultado:  "pending"
  },
  {
    fecha:      "17/05/26",
    partido:    "Arsenal vs Man United",
    liga:       "Premier League",
    prediccion: "Over 2.5 Goles",
    cuota:      "1.68",
    resultado:  "win"
  },
  {
    fecha:      "16/05/26",
    partido:    "Real Madrid vs Sevilla",
    liga:       "La Liga",
    prediccion: "Victoria Local (1)",
    cuota:      "1.55",
    resultado:  "win"
  },
  {
    fecha:      "15/05/26",
    partido:    "PSG vs Monaco",
    liga:       "Ligue 1",
    prediccion: "Victoria Local (1)",
    cuota:      "1.62",
    resultado:  "win"
  },
  {
    fecha:      "14/05/26",
    partido:    "Man City vs Aston Villa",
    liga:       "Premier League",
    prediccion: "Victoria Local (1)",
    cuota:      "1.50",
    resultado:  "win"
  },
  {
    fecha:      "13/05/26",
    partido:    "Atletico Madrid vs Getafe",
    liga:       "La Liga",
    prediccion: "Victoria Local (1)",
    cuota:      "1.48",
    resultado:  "loss"
  },
  {
    fecha:      "12/05/26",
    partido:    "Juventus vs Fiorentina",
    liga:       "Serie A",
    prediccion: "Victoria Local (1)",
    cuota:      "1.70",
    resultado:  "win"
  },
  {
    fecha:      "11/05/26",
    partido:    "Chelsea vs Brighton",
    liga:       "Premier League",
    prediccion: "Over 2.5 Goles",
    cuota:      "1.72",
    resultado:  "win"
  },
  {
    fecha:      "10/05/26",
    partido:    "Inter Milan vs Lazio",
    liga:       "Serie A",
    prediccion: "Over 2.5 Goles",
    cuota:      "1.75",
    resultado:  "loss"
  },
  {
    fecha:      "29/04/26",
    partido:    "Real Madrid vs Barcelona",
    liga:       "La Liga",
    prediccion: "Over 2.5 Goles",
    cuota:      "1.78",
    resultado:  "win"
  },
  {
    fecha:      "27/04/26",
    partido:    "Liverpool vs Arsenal",
    liga:       "Premier League",
    prediccion: "Over 2.5 Goles",
    cuota:      "1.82",
    resultado:  "win"
  },
  {
    fecha:      "26/04/26",
    partido:    "Bayern Munich vs Dortmund",
    liga:       "Bundesliga",
    prediccion: "Victoria Local (1)",
    cuota:      "1.65",
    resultado:  "win"
  },
  {
    fecha:      "25/04/26",
    partido:    "PSG vs Lille",
    liga:       "Ligue 1",
    prediccion: "Victoria Local (1)",
    cuota:      "1.57",
    resultado:  "loss"
  },
  {
    fecha:      "23/04/26",
    partido:    "Manchester City vs Chelsea",
    liga:       "Premier League",
    prediccion: "Victoria Local (1)",
    cuota:      "1.85",
    resultado:  "win"
  },
  {
    fecha:      "22/04/26",
    partido:    "Atletico Madrid vs Real Madrid",
    liga:       "La Liga",
    prediccion: "Empate (X)",
    cuota:      "3.20",
    resultado:  "win"
  },
  {
    fecha:      "19/04/26",
    partido:    "Arsenal vs Newcastle",
    liga:       "Premier League",
    prediccion: "Over 2.5 Goles",
    cuota:      "1.68",
    resultado:  "loss"
  }
];
