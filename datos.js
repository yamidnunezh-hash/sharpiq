// SharpIQ — ARCHIVO DE DATOS
// Actualizado: 2026-05-29
// NO editar manualmente

const PROXIMOS_EVENTOS = [
  {
    fecha:      "29/05/26",
    partido:    "Nice vs Saint Etienne",
    liga:       "Ligue 1",
    prediccion: "Under 2.5 Goles — EV +40%",
    cuota:      "1.62",
    hora:       "13:45 COT",
    status:     "vip",
    tier:       "seguro",
    stake_pct:  "5.0"
  },
  {
    fecha:      "29/05/26",
    partido:    "Carolina Hurricanes vs Montréal Canadiens",
    liga:       "NHL",
    prediccion: "Gana Carolina Hurricanes — EV +16%",
    cuota:      "1.70",
    hora:       "19:15 COT",
    status:     "vip",
    tier:       "principal",
    stake_pct:  "5",
    resultado:  "pendiente"
  },
  {
    fecha:      "29/05/26",
    partido:    "Boca Juniors vs U. Católica (Chile)",
    liga:       "Copa Libertadores",
    prediccion: "Under 2.5 goles — EV +37%",
    cuota:      "2.01",
    hora:       "19:30 COT",
    status:     "vip",
    tier:       "seguro",
    stake_pct:  "5",
    resultado:  "win"
  },
  {
    fecha:      "30/05/26",
    partido:    "Athletic Club (MG) vs Fortaleza",
    liga:       "Brasileirao B",
    prediccion: "Over 2.5 goles — EV +80%",
    cuota:      "2.40",
    hora:       "16:00 COT",
    status:     "vip",
    tier:       "alto_valor",
    stake_pct:  "5",
    resultado:  "pendiente"
  },
  {
    fecha:      "30/05/26",
    partido:    "PSG vs Arsenal",
    liga:       "UEFA Champions League Final",
    prediccion: "Gana Arsenal — EV +22%",
    cuota:      "2.20",
    hora:       "11:00 COT",
    status:     "vip",
    tier:       "principal",
    stake_pct:  "3",
    resultado:  "pendiente"
  }
];

const PREDICCIONES_HISTORIAL = [
  {
    fecha:      "29/05/26",
    partido:    "Boca Juniors vs U. Católica (Chile)",
    liga:       "Copa Libertadores",
    prediccion: "Under 2.5 goles — EV +37%",
    cuota:      "2.01",
    resultado:  "win"
  },
  {fecha:'28/05/26', partido:'Cerro Porteño vs Sporting Cristal',     liga:'Copa Libertadores', prediccion:'Under 2.5 goles', cuota:'1.89', resultado:'win'},
  {fecha:'28/05/26', partido:'América de Cali vs Macará',              liga:'Copa Sudamericana',  prediccion:'Under 2.5 goles', cuota:'1.82', resultado:'loss'},
  {fecha:'28/05/26', partido:'Bolívar vs Independiente Rivadavia',     liga:'Copa Libertadores', prediccion:'Gana Bolívar',    cuota:'2.32', resultado:'loss'},
  {fecha:'28/05/26', partido:'Corinthians vs Platense',                liga:'Copa Libertadores', prediccion:'Under 2.5 goles', cuota:'1.96', resultado:'win'},
  {fecha:'28/05/26', partido:'Peñarol vs Independiente Santa Fe',      liga:'Copa Libertadores', prediccion:'Under 2.5 goles', cuota:'1.79', resultado:'win'},

  {
    fecha:      "27/05/26",
    partido:    "RB Bragantino vs Carabobo FC",
    liga:       "Copa Sudamericana",
    prediccion: "Over 2.5 goles",
    cuota:      "1.89",
    resultado:  "loss"
  },
  {
    fecha:      "27/05/26",
    partido:    "Atlético Mineiro vs Academia Puerto Cabello",
    liga:       "Copa Sudamericana",
    prediccion: "Over 2.5 goles",
    cuota:      "1.86",
    resultado:  "loss"
  },
  {
    fecha:      "27/05/26",
    partido:    "Libertad Asuncion vs UCV FC",
    liga:       "Copa Sudamericana",
    prediccion: "Gana Libertad Asuncion",
    cuota:      "1.43",
    resultado:  "loss"
  },
  {
    fecha:      "28/05/26",
    partido:    "Corinthians vs Platense",
    liga:       "Copa Libertadores",
    prediccion: "Under 2.5 goles — EV +46%",
    cuota:      "1.96",
    resultado:  "win"
  },
  {
    fecha:      "28/05/26",
    partido:    "Peñarol vs Independiente Santa Fe",
    liga:       "Copa Libertadores",
    prediccion: "Under 2.5 goles — EV +33%",
    cuota:      "1.79",
    resultado:  "win"
  },
  {
    fecha:      "28/05/26",
    partido:    "Bolívar vs Independiente Rivadavia",
    liga:       "Copa Libertadores",
    prediccion: "Gana Bolívar — EV +47%",
    cuota:      "2.32",
    resultado:  "loss"
  },
  {
    fecha:      "27/05/26",
    partido:    "Nishesh Basavareddy vs Alex Michelsen",
    liga:       "ATP Roland Garros",
    prediccion: "Gana Alex Michelsen",
    cuota:      "1.56",
    resultado:  "pendiente"
  },
  {
    fecha:      "27/05/26",
    partido:    "Francesca Jones vs Marie Bouzkova",
    liga:       "WTA Roland Garros",
    prediccion: "Gana Marie Bouzkova",
    cuota:      "1.29",
    resultado:  "pendiente"
  },
  {
    fecha:      "27/05/26",
    partido:    "Cienciano vs CA Juventud",
    liga:       "Copa Sudamericana",
    prediccion: "Under 2.5 goles — EV +39%",
    cuota:      "1.81",
    resultado:  "win"
  },
  {
    fecha:      "27/05/26",
    partido:    "Caracas FC vs Botafogo",
    liga:       "Copa Sudamericana",
    prediccion: "Under 2.5 goles — EV +21%",
    cuota:      "1.75",
    resultado:  "loss"
  },
  {
    fecha:      "27/05/26",
    partido:    "Montréal Canadiens vs Carolina Hurricanes",
    liga:       "NHL",
    prediccion: "Gana Montréal Canadiens — EV +28%",
    cuota:      "3.05",
    resultado:  "loss"
  },
  {
    fecha:      "26/05/26",
    partido:    "Vegas Golden Knights vs Colorado Avalanche",
    liga:       "NHL",
    prediccion: "Gana Vegas Golden Knights — EV +33%",
    cuota:      "2.7",
    resultado:  "win"
  },
  {
    fecha:      "27/05/26",
    partido:    "Olimpia Asunción vs Audax Italiano",
    liga:       "Copa Sudamericana",
    prediccion: "Under 2.5 goles — EV +43%",
    cuota:      "2.01",
    resultado:  "win"
  },
  {
    fecha:      "27/05/26",
    partido:    "Jelena Ostapenko vs Magda Linette",
    liga:       "WTA Roland Garros",
    prediccion: "Gana Jelena Ostapenko",
    cuota:      "1.3",
    resultado:  "win"
  },
  {
    fecha:      "26/05/26",
    partido:    "Milwaukee Brewers vs St. Louis Cardinals",
    liga:       "MLB",
    prediccion: "Gana Milwaukee Brewers",
    cuota:      "1.56",
    resultado:  "win"
  },
  {
    fecha:      "26/05/26",
    partido:    "Vit Kopriva vs Corentin Moutet",
    liga:       "ATP Roland Garros",
    prediccion: "Gana Corentin Moutet",
    cuota:      "1.55",
    resultado:  "loss"
  },
  {
    fecha:      "26/05/26",
    partido:    "Marin Cilic vs Moise Kouame",
    liga:       "ATP Roland Garros",
    prediccion: "Gana Marin Cilic",
    cuota:      "1.29",
    resultado:  "loss"
  },
  {
    fecha:      "26/05/26",
    partido:    "Oklahoma City Thunder vs San Antonio Spurs",
    liga:       "NBA",
    prediccion: "Gana Oklahoma City Thunder",
    cuota:      "1.62",
    resultado:  "win"
  },
  {
    fecha:      "25/05/26",
    partido:    "Mariano Navone vs Jenson Brooksby",
    liga:       "ATP Roland Garros",
    prediccion: "Gana Mariano Navone",
    cuota:      "1.29",
    resultado:  "win"
  },
  {
    fecha:      "25/05/26",
    partido:    "Cleveland Cavaliers vs New York Knicks",
    liga:       "NBA Playoffs",
    prediccion: "Gana New York Knicks",
    cuota:      "1.81",
    resultado:  "win"
  }
];
