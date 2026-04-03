import requests
from supabase import create_client
from datetime import datetime, timezone, timedelta
import pytz
import os

ODDS_API_KEY = os.environ["ODDS_API_KEY"]
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

eastern = pytz.timezone("US/Eastern")
today = datetime.now(eastern)
end_of_day = today + timedelta(days=0.75)

commence_from = today.strftime("%Y-%m-%dT%H:%M:%SZ")
commence_to = end_of_day.strftime("%Y-%m-%dT%H:%M:%SZ")

def fetch_and_store():
    response = requests.get(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds",
        params={
            "apiKey": "f5880c353c34978903b39b0b83fca149",
            "regions": "us",
            "markets": "spreads,totals,h2h",
            "bookmakers": "betmgm,draftkings,fanduel",
            "dateFormat": "iso",
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


fetch_and_store()
