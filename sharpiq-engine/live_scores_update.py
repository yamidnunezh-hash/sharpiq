# -*- coding: utf-8 -*-
"""
SharpIQ — Live Scores Updater
Consulta The Odds API /scores cada 10 min y guarda live_scores.json en la raiz.
Corre desde GitHub Actions — nunca expone la API key en el frontend.
"""
import os, sys, json, requests
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import ODDS_API_KEY

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
OUT_PATH  = os.path.join(BASE_DIR, "..", "live_scores.json")

SPORTS = [
    "basketball_nba",
    "icehockey_nhl",
    "baseball_mlb",
    "tennis_atp",
    "tennis_wta",
    "soccer_conmebol_copa_libertadores",
    "soccer_conmebol_copa_sudamericana",
    "soccer_brazil_campeonato",
    "soccer_brazil_serie_b",
    "soccer_fifa_world_cup",
]

SPORT_LABELS = {
    "basketball_nba":                    "NBA",
    "icehockey_nhl":                     "NHL",
    "baseball_mlb":                      "MLB",
    "tennis_atp":                        "ATP",
    "tennis_wta":                        "WTA",
    "soccer_conmebol_copa_libertadores": "Copa Libertadores",
    "soccer_conmebol_copa_sudamericana": "Copa Sudamericana",
    "soccer_brazil_campeonato":          "Brasileirao",
    "soccer_brazil_serie_b":             "Brasileirao B",
    "soccer_fifa_world_cup":             "Mundial FIFA",
}

SPORT_EMOJI = {
    "basketball_nba": "🏀", "icehockey_nhl": "🏒", "baseball_mlb": "⚾",
    "tennis_atp": "🎾",     "tennis_wta": "🎾",
}


def fetch_scores(sport_key):
    try:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores",
            params={"apiKey": ODDS_API_KEY, "daysFrom": 1},
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
        return []
    except Exception:
        return []


def hora_cot(utc_str):
    """Convierte ISO UTC a hora COT (UTC-5) y devuelve fecha+hora legibles."""
    try:
        dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        cot = dt - timedelta(hours=5)
        return {
            "fecha": cot.strftime("%d/%m/%y"),
            "hora":  cot.strftime("%H:%M COT"),
            "iso":   cot.isoformat(),
            "ts":    int(cot.timestamp()),
        }
    except Exception:
        return {"fecha": "", "hora": utc_str, "iso": utc_str, "ts": 0}


def correr():
    now_utc = datetime.now(timezone.utc)
    live    = []
    upcoming = []
    finished = []

    for sport in SPORTS:
        games = fetch_scores(sport)
        label = SPORT_LABELS.get(sport, sport)
        emoji = SPORT_EMOJI.get(sport, "⚽")

        for g in games:
            t = hora_cot(g.get("commence_time", ""))
            scores = g.get("scores") or []
            score_map = {s["name"]: s["score"] for s in scores}
            completed = g.get("completed", False)

            entry = {
                "id":         g.get("id", ""),
                "sport":      sport,
                "liga":       label,
                "emoji":      emoji,
                "home":       g.get("home_team", ""),
                "away":       g.get("away_team", ""),
                "fecha":      t["fecha"],
                "hora":       t["hora"],
                "ts":         t["ts"],
                "completed":  completed,
                "score_home": score_map.get(g.get("home_team", ""), None),
                "score_away": score_map.get(g.get("away_team", ""), None),
            }

            if completed:
                finished.append(entry)
            elif scores:
                live.append(entry)
            else:
                upcoming.append(entry)

    # Ordenar upcoming por hora
    upcoming.sort(key=lambda x: x["ts"])
    live.sort(key=lambda x: x["ts"])
    finished.sort(key=lambda x: x["ts"], reverse=True)

    output = {
        "updated":  now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "live":     live[:10],
        "upcoming": upcoming[:15],
        "finished": finished[:10],
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"live_scores.json actualizado — {len(live)} en vivo | {len(upcoming)} próximos | {len(finished)} terminados")


if __name__ == "__main__":
    correr()
