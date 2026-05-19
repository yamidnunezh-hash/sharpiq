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
    partido:    "Inter Milan vs Juventus",
    liga:       "Serie A",
    prediccion: "Victoria Local (1)",
    cuota:      "1.76",
    hora:       "15:45 COT",
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
const PREDICCIONES_HISTORIAL = [
  {
    fecha:      "18/05/26",
    partido:    "Bayern Munich vs PSG",
    liga:       "Champions League",
    prediccion: "Victoria Local (1)",
    cuota:      "2.24",
    resultado:  "pending"
  }
];
