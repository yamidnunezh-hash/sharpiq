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
    partido:    "Fiorentina vs Atalanta",
    liga:       "Serie A",
    prediccion: "Tarjetas Over 3.5",
    cuota:      "2.27",
    hora:       "13:45 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "VPS vs HJK Helsinki",
    liga:       "Veikkausliiga",
    prediccion: "Tarjetas Over 4.5",
    cuota:      "2.27",
    hora:       "11:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Djurgardens IF vs IF Brommapojkarna",
    liga:       "Allsvenskan",
    prediccion: "Tarjetas Over 4.5",
    cuota:      "2.27",
    hora:       "12:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Ried vs Rapid Vienna",
    liga:       "Austrian Bundesliga",
    prediccion: "Tarjetas Over 4.5",
    cuota:      "2.62",
    hora:       "12:30 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Sudtirol vs Bari",
    liga:       "Serie B",
    prediccion: "Tarjetas Over 4.5",
    cuota:      "2.62",
    hora:       "13:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Rot-Weiß Essen vs SpVgg Greuther Fürth",
    liga:       "Bundesliga 2",
    prediccion: "Tarjetas Over 4.5",
    cuota:      "2.62",
    hora:       "13:30 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Derry City vs St Patrick's Athl.",
    liga:       "League of Ireland",
    prediccion: "Tarjetas Over 4.5",
    cuota:      "2.27",
    hora:       "13:45 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Galway United vs Bohemians",
    liga:       "League of Ireland",
    prediccion: "Tarjetas Over 4.5",
    cuota:      "2.27",
    hora:       "13:45 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Shelbourne vs Waterford",
    liga:       "League of Ireland",
    prediccion: "Tarjetas Over 4.5",
    cuota:      "2.27",
    hora:       "13:45 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Drogheda United vs Dundalk",
    liga:       "League of Ireland",
    prediccion: "Tarjetas Over 4.5",
    cuota:      "2.27",
    hora:       "14:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Shamrock Rovers vs Sligo Rovers",
    liga:       "League of Ireland",
    prediccion: "Tarjetas Over 4.5",
    cuota:      "2.27",
    hora:       "14:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Everton de Vina vs Coquimbo Unido",
    liga:       "Primera División Chile",
    prediccion: "Tarjetas Over 4.5",
    cuota:      "2.12",
    hora:       "14:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Nautico Recife vs Cuiaba",
    liga:       "Brasileirao Serie B",
    prediccion: "Tarjetas Over 4.5",
    cuota:      "2.27",
    hora:       "17:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "San Antonio Spurs vs Oklahoma City Thunder",
    liga:       "NBA",
    prediccion: "San Antonio Spurs",
    cuota:      "",
    hora:       "14:40 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Cleveland Cavaliers vs New York Knicks",
    liga:       "NBA",
    prediccion: "Cleveland Cavaliers",
    cuota:      "",
    hora:       "14:10 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Chicago Cubs vs Houston Astros",
    liga:       "MLB",
    prediccion: "Houston Astros",
    cuota:      "",
    hora:       "08:21 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Cincinnati Reds vs St. Louis Cardinals",
    liga:       "MLB",
    prediccion: "Cincinnati Reds",
    cuota:      "",
    hora:       "12:41 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Philadelphia Phillies vs Cleveland Guardians",
    liga:       "MLB",
    prediccion: "Philadelphia Phillies",
    cuota:      "",
    hora:       "12:41 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "New York Yankees vs Tampa Bay Rays",
    liga:       "MLB",
    prediccion: "Tampa Bay Rays",
    cuota:      "",
    hora:       "13:06 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Toronto Blue Jays vs Pittsburgh Pirates",
    liga:       "MLB",
    prediccion: "Toronto Blue Jays",
    cuota:      "",
    hora:       "13:08 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Boston Red Sox vs Minnesota Twins",
    liga:       "MLB",
    prediccion: "Boston Red Sox",
    cuota:      "",
    hora:       "13:11 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Miami Marlins vs New York Mets",
    liga:       "MLB",
    prediccion: "New York Mets",
    cuota:      "",
    hora:       "13:11 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Atlanta Braves vs Washington Nationals",
    liga:       "MLB",
    prediccion: "Washington Nationals",
    cuota:      "",
    hora:       "13:15 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Baltimore Orioles vs Detroit Tigers",
    liga:       "MLB",
    prediccion: "Baltimore Orioles",
    cuota:      "",
    hora:       "13:16 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Kansas City Royals vs Seattle Mariners",
    liga:       "MLB",
    prediccion: "Kansas City Royals",
    cuota:      "",
    hora:       "13:41 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Milwaukee Brewers vs Los Angeles Dodgers",
    liga:       "MLB",
    prediccion: "Milwaukee Brewers",
    cuota:      "",
    hora:       "13:41 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Los Angeles Angels vs Texas Rangers",
    liga:       "MLB",
    prediccion: "Los Angeles Angels",
    cuota:      "",
    hora:       "15:39 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Arizona Diamondbacks vs Colorado Rockies",
    liga:       "MLB",
    prediccion: "Colorado Rockies",
    cuota:      "",
    hora:       "15:41 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "San Diego Padres vs Athletics",
    liga:       "MLB",
    prediccion: "San Diego Padres",
    cuota:      "",
    hora:       "15:41 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "San Francisco Giants vs Chicago White Sox",
    liga:       "MLB",
    prediccion: "Chicago White Sox",
    cuota:      "",
    hora:       "16:16 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Colorado Avalanche vs Vegas Golden Knights",
    liga:       "NHL",
    prediccion: "Vegas Golden Knights",
    cuota:      "",
    hora:       "14:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Carolina Hurricanes vs Montréal Canadiens",
    liga:       "NHL",
    prediccion: "Montréal Canadiens",
    cuota:      "",
    hora:       "13:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Seattle Seahawks vs New England Patriots",
    liga:       "NFL",
    prediccion: "Seattle Seahawks",
    cuota:      "",
    hora:       "14:15 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Los Angeles Rams vs San Francisco 49ers",
    liga:       "NFL",
    prediccion: "Los Angeles Rams",
    cuota:      "",
    hora:       "14:35 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Pittsburgh Steelers vs Atlanta Falcons",
    liga:       "NFL",
    prediccion: "Pittsburgh Steelers",
    cuota:      "",
    hora:       "07:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Indianapolis Colts vs Baltimore Ravens",
    liga:       "NFL",
    prediccion: "Indianapolis Colts",
    cuota:      "",
    hora:       "07:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Houston Texans vs Buffalo Bills",
    liga:       "NFL",
    prediccion: "Houston Texans",
    cuota:      "",
    hora:       "07:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Carolina Panthers vs Chicago Bears",
    liga:       "NFL",
    prediccion: "Chicago Bears",
    cuota:      "",
    hora:       "07:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Cincinnati Bengals vs Tampa Bay Buccaneers",
    liga:       "NFL",
    prediccion: "Tampa Bay Buccaneers",
    cuota:      "",
    hora:       "07:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Jacksonville Jaguars vs Cleveland Browns",
    liga:       "NFL",
    prediccion: "Jacksonville Jaguars",
    cuota:      "",
    hora:       "07:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Detroit Lions vs New Orleans Saints",
    liga:       "NFL",
    prediccion: "New Orleans Saints",
    cuota:      "",
    hora:       "07:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Tennessee Titans vs New York Jets",
    liga:       "NFL",
    prediccion: "New York Jets",
    cuota:      "",
    hora:       "07:00 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Los Angeles Chargers vs Arizona Cardinals",
    liga:       "NFL",
    prediccion: "Arizona Cardinals",
    cuota:      "",
    hora:       "10:25 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Minnesota Vikings vs Green Bay Packers",
    liga:       "NFL",
    prediccion: "Minnesota Vikings",
    cuota:      "",
    hora:       "10:25 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Las Vegas Raiders vs Miami Dolphins",
    liga:       "NFL",
    prediccion: "Miami Dolphins",
    cuota:      "",
    hora:       "10:25 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Philadelphia Eagles vs Washington Commanders",
    liga:       "NFL",
    prediccion: "Washington Commanders",
    cuota:      "",
    hora:       "10:25 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "New York Giants vs Dallas Cowboys",
    liga:       "NFL",
    prediccion: "New York Giants",
    cuota:      "",
    hora:       "14:20 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Kansas City Chiefs vs Denver Broncos",
    liga:       "NFL",
    prediccion: "Kansas City Chiefs",
    cuota:      "",
    hora:       "14:15 COT",
    status:     "vip"
  },
  {
    fecha:      "22/05/26",
    partido:    "Orlando Storm vs DC Defenders",
    liga:       "UFL",
    prediccion: "DC Defenders",
    cuota:      "",
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
