// SharpIQ — ARCHIVO DE DATOS
// Actualizado: 2026-05-29
// NO editar manualmente

const PROXIMOS_EVENTOS = [
  {
    fecha:      "06/06/26",
    partido:    "Joshua Padley vs Aqib Fiaz",
    liga:       "Boxeo",
    prediccion: "Gana Joshua Padley — EV +4%",
    cuota:      "1.28",
    hora:       "16:00 COT",
    status:     "vip",
    tier:       "seguro",
    stake_pct:  "5.0"
  },
  {
    fecha:      "06/06/26",
    partido:    "Bryce Mitchell vs Santiago Luna",
    liga:       "UFC / MMA",
    prediccion: "Gana Santiago Luna — EV +3%",
    cuota:      "2.16",
    hora:       "16:00 COT",
    status:     "vip",
    tier:       "principal",
    stake_pct:  "1.3"
  },
  {
    fecha:      "06/06/26",
    partido:    "FC Tokyo vs Cerezo Osaka",
    liga:       "J-League",
    prediccion: "Over 2.5 Goles",
    cuota:      "1.7",
    hora:       "00:00 COT",
    status:     "vip",
    tier:       "principal",
    stake_pct:  "1.0"
  },
  {
    fecha:      "05/06/26",
    partido:    "Texas Rangers vs Cleveland Guardians",
    liga:       "MLB",
    prediccion: "Gana Texas Rangers — EV +3%",
    cuota:      "2.24",
    hora:       "19:16 COT",
    status:     "vip",
    tier:       "principal",
    stake_pct:  "1.4"
  },
  {
    fecha:      "06/06/26",
    partido:    "Tokyo Verdy vs Gamba Osaka",
    liga:       "J-League",
    prediccion: "Under 2.5 Goles",
    cuota:      "1.5",
    hora:       "02:00 COT",
    status:     "vip",
    tier:       "seguro",
    stake_pct:  "5.0"
  },
  {
    fecha:      "05/06/26",
    partido:    "Sussex vs Leicestershire",
    liga:       "T20 Blast",
    prediccion: "Gana Leicestershire — EV +2%",
    cuota:      "2.0",
    hora:       "13:00 COT",
    status:     "vip",
    tier:       "principal",
    stake_pct:  "1.1"
  },
  {
    fecha:      "04/06/26",
    partido:    "HSV Hamburg vs HSG Wetzlar",
    liga:       "Balonmano Bundesliga",
    prediccion: "Gana HSV Hamburg — EV +6%",
    cuota:      "1.77",
    hora:       "12:00 COT",
    status:     "vip",
    tier:       "principal",
    stake_pct:  "3.6"
  },
  {
    fecha:      "03/06/26",
    partido:    "Felix Auger-Aliassime vs Flavio Cobolli",
    liga:       "ATP Roland Garros",
    prediccion: "Gana Flavio Cobolli — EV +2%",
    cuota:      "2.0",
    hora:       "04:00 COT",
    status:     "vip",
    tier:       "principal",
    stake_pct:  "1.0"
  },
  {
    fecha:      "03/06/26",
    partido:    "Anna Kalinskaya vs Maja Chwalinska",
    liga:       "WTA Roland Garros",
    prediccion: "Gana Maja Chwalinska — EV +2%",
    cuota:      "2.05",
    hora:       "04:00 COT",
    status:     "vip",
    tier:       "principal",
    stake_pct:  "1.2"
  },
  {
    fecha:      "02/06/26",
    partido:    "Carolina Hurricanes vs Vegas Golden Knights",
    liga:       "NHL",
    prediccion: "Gana Vegas Golden Knights — EV +24%",
    cuota:      "3.0",
    hora:       "19:00 COT",
    status:     "vip",
    tier:       "alto_valor",
    stake_pct:  "5.0"
  },
  {
    fecha:      "31/05/26",
    partido:    "Palmeiras vs Chapecoense",
    liga:       "Brasileirao Serie A",
    prediccion: "Gana Palmeiras — EV +3%",
    cuota:      "1.37",
    hora:       "14:00 COT",
    status:     "vip",
    tier:       "seguro",
    stake_pct:  "2",
    analisis:   "Palmeiras (local) en gran forma: viene de ganar 3-0 a Flamengo de visita, GF 2.4/GC 0.8 por partido, sin bajas. Calidad muy superior a Chapecoense. A cuota 1.37 el valor es ajustado (prob ~75% vs 73% de equilibrio = EV +3%): pick SEGURO de bajo riesgo, stake reducido 2%. No es un valorazo, entra por calidad, forma y localia."
  },
  {
    fecha:      "31/05/26",
    partido:    "Palestino vs Audax Italiano",
    liga:       "Campeonato Chileno",
    prediccion: "Under 2.5 Goles — EV +28%",
    cuota:      "1.9",
    hora:       "19:00 COT",
    status:     "vip",
    tier:       "principal",
    stake_pct:  "5.0"
  },
  {
    fecha:      "30/05/26",
    partido:    "Kevin Lerena vs Ryad Merhy",
    liga:       "Boxeo",
    prediccion: "Gana Ryad Merhy — EV +4%",
    cuota:      "2.3",
    hora:       "13:00 COT",
    status:     "vip",
    tier:       "principal",
    stake_pct:  "1.7"
  },
  {
    fecha:      "31/05/26",
    partido:    "Gent vs Genk",
    liga:       "Belgian First Div",
    prediccion: "Under 2.5 Goles — EV +85%",
    cuota:      "2.05",
    hora:       "11:30 COT",
    status:     "vip",
    tier:       "alto_valor",
    stake_pct:  "5.0"
  },
  {
    fecha:      "31/05/26",
    partido:    "Penrith Panthers vs New Zealand Warriors",
    liga:       "NRL Rugby League",
    prediccion: "Gana Penrith Panthers — EV +2%",
    cuota:      "1.77",
    hora:       "03:15 COT",
    status:     "vip",
    tier:       "principal",
    stake_pct:  "1.5"
  },
  {
    fecha:      "30/05/26",
    partido:    "Stephanie Han vs Holly Holm",
    liga:       "Boxeo",
    prediccion: "Gana Stephanie Han — EV +2%",
    cuota:      "1.25",
    hora:       "16:55 COT",
    status:     "vip",
    tier:       "seguro",
    stake_pct:  "4.3"
  },
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
    resultado:  "loss"
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
    resultado:  "loss"
  },
  {
    fecha:      "30/05/26",
    partido:    "PSG vs Arsenal",
    liga:       "UEFA Champions League Final",
    prediccion: "Under 2.5 goles — EV +3% (a >=1.90)",
    cuota:      "1.90",
    hora:       "11:00 COT",
    status:     "vip",
    tier:       "principal",
    stake_pct:  "2",
    analisis:   "Final a partido unico + Arsenal con defensa de elite (0.2 goles encajados/partido en sus ultimos 5) -> se proyectan pocos goles. Modelo recalibrado vs Pinnacle (78% peso al mercado en Champions): ~54% Under 2.5. Valor SOLO a cuota >=1.90 (a 1.67 no hay valor). Stake reducido 2%: el edge es modesto, NO es alto valor.",
    resultado:  "win"
  }
];

const PREDICCIONES_HISTORIAL = [
  {
    fecha:      "29/05/26",
    partido:    "Carolina Hurricanes vs Montréal Canadiens",
    liga:       "NHL",
    prediccion: "Gana Carolina Hurricanes — EV +16%",
    cuota:      "1.70",
    resultado:  "loss"
  },
  {
    fecha:      "30/05/26",
    partido:    "PSG vs Arsenal",
    liga:       "UEFA Champions League Final",
    prediccion: "Under 2.5 goles — EV +3% (a >=1.90)",
    cuota:      "1.90",
    resultado:  "win"
  },
  {
    fecha:      "30/05/26",
    partido:    "Athletic Club (MG) vs Fortaleza",
    liga:       "Brasileirao B",
    prediccion: "Over 2.5 goles — EV +80%",
    cuota:      "2.40",
    resultado:  "loss"
  },
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
