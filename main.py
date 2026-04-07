import requests
from supabase import create_client
from datetime import datetime, timezone, timedelta
import pytz
import os

ODDS_API_KEY = os.environ["ODDS_API_KEY"]
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

eastern = pytz.timezone("US/Eastern")
today = datetime.now(eastern)
start_of_day = today.replace(hour=0, minute=0, second=0, microsecond=0)
end_of_day = today.replace(hour=23, minute=59, second=59, microsecond=0)

commence_from = start_of_day.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
commence_to = end_of_day.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def fetch_and_store():
    response = requests.get(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds",
        params={
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "spreads,totals,h2h",
            "bookmakers": "betmgm,draftkings,fanduel",
            "dateFormat": "iso",
            "oddsFormat": "american",
            "commenceTimeFrom": commence_from,
            "commenceTimeTo": commence_to
        }
    )

    print("Status code:", response.status_code)
    print("Response:", response.text)

    games = response.json()

    for game in games:
        # Upsert game (won't duplicate if run again)
        game_row = supabase.table("games").upsert({
            "api_game_id": game["id"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "commence_time": game["commence_time"]
        }, on_conflict="api_game_id").execute()

        game_id = game_row.data[0]["id"]

        # Loop each bookmaker
        for bookmaker in game["bookmakers"]:
            markets = {m["key"]: m["outcomes"] for m in bookmaker["markets"]}

            spreads = {o["name"]: o for o in markets.get("spreads", [])}
            totals = {o["name"]: o for o in markets.get("totals", [])}
            h2h = {o["name"]: o for o in markets.get("h2h", [])}

            supabase.table("odds").insert({
                "game_id": game_id,
                "bookmaker": bookmaker["key"],
                "fetched_at": datetime.now(timezone.utc).isoformat(),

                "spread_home": spreads.get(game["home_team"], {}).get("point"),
                "spread_home_price": spreads.get(game["home_team"], {}).get("price"),
                "spread_away": spreads.get(game["away_team"], {}).get("point"),
                "spread_away_price": spreads.get(game["away_team"], {}).get("price"),

                "total_over": totals.get("Over", {}).get("point"),
                "total_over_price": totals.get("Over", {}).get("price"),
                "total_under": totals.get("Under", {}).get("point"),
                "total_under_price": totals.get("Under", {}).get("price"),

                "ml_home": h2h.get(game["home_team"], {}).get("price"),
                "ml_away": h2h.get(game["away_team"], {}).get("price"),
            }).execute()


def fetch_and_store_results():
    yesterday = datetime.now(eastern) - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    # Fetch yesterday's completed games from MLB Stats API
    response = requests.get(
        "https://statsapi.mlb.com/api/v1/schedule",
        params={
            "sportId": 1,
            "startDate": yesterday_str,
            "endDate": yesterday_str,
            "hydrate": "linescore"
        }
    )
    data = response.json()

    # Build lookup from DB: (home_team, away_team, et_date) -> list of (commence_time, game_id)
    # Stored as a list to support doubleheaders (same matchup, same date, different times)
    all_db_games = supabase.table("games").select("id, home_team, away_team, commence_time").execute()
    game_lookup = {}
    for g in all_db_games.data:
        ct = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
        et_date = ct.astimezone(eastern).strftime("%Y-%m-%d")
        key = (g["home_team"], g["away_team"], et_date)
        game_lookup.setdefault(key, []).append((ct, g["id"]))

    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            detailed_state = game["status"]["detailedState"]
            if detailed_state not in ("Final", "Completed Early", "Postponed"):
                continue

            home_team = game["teams"]["home"]["team"]["name"]
            away_team = game["teams"]["away"]["team"]["name"]

            # Use gameDate (original scheduled time) converted to ET, not officialDate,
            # so postponed games match the original entry rather than the makeup game entry
            mlb_game_time = datetime.fromisoformat(game["gameDate"].replace("Z", "+00:00"))
            game_et_date = mlb_game_time.astimezone(eastern).strftime("%Y-%m-%d")

            candidates = game_lookup.get((home_team, away_team, game_et_date))
            if not candidates:
                print(f"Game not found in DB: {away_team} @ {home_team} ({game_et_date})")
                continue

            # For doubleheaders, match by closest commence_time to the MLB Stats API game time
            # Remove the matched candidate so the second game can't reuse the same game_id
            best = min(candidates, key=lambda x: abs((x[0] - mlb_game_time).total_seconds()))
            candidates.remove(best)
            game_id = best[1]

            if detailed_state == "Postponed":
                supabase.table("results").upsert({
                    "game_id": game_id,
                    "status": "postponed",
                }, on_conflict="game_id").execute()
                print(f"Marked postponed: {away_team} @ {home_team} ({game_et_date})")
                continue

            home_score = game["teams"]["home"]["score"]
            away_score = game["teams"]["away"]["score"]

            supabase.table("results").upsert({
                "game_id": game_id,
                "status": "final",
                "home_score": home_score,
                "away_score": away_score,
            }, on_conflict="game_id").execute()

            print(f"Stored result: {away_team} @ {home_team} — {away_score}-{home_score}")


fetch_and_store_results()
fetch_and_store()
