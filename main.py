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


def fetch_and_store_results():
    yesterday = (datetime.now(eastern) - timedelta(days=1)).strftime("%Y-%m-%d")

    response = requests.get(
        "https://statsapi.mlb.com/api/v1/schedule",
        params={
            "sportId": 1,
            "startDate": yesterday,
            "endDate": today,
            "hydrate": "linescore"
        }
    )

    data = response.json()

    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            # Only process completed games
            if game["status"]["detailedState"] != "Final":
                continue

            home_team = game["teams"]["home"]["team"]["name"]
            away_team = game["teams"]["away"]["team"]["name"]
            home_score = game["teams"]["home"]["score"]
            away_score = game["teams"]["away"]["score"]

            # Look up the game in our database
            result = supabase.table("games")\
                .select("id")\
                .eq("home_team", home_team)\
                .eq("away_team", away_team)\
                .execute()

            if not result.data:
                print(f"Game not found in DB: {away_team} @ {home_team}")
                continue

            game_id = result.data[0]["id"]

            # Get the odds we stored to calculate covers
            odds = supabase.table("odds")\
                .select("spread_home, total_over")\
                .eq("game_id", game_id)\
                .limit(1)\
                .execute()

            if not odds.data:
                continue

            spread = odds.data[0]["spread_home"]
            total = odds.data[0]["total_over"]

            home_covered = (home_score + spread) > away_score if spread else None
            away_covered = not home_covered if spread else None
            went_over = (home_score + away_score) > total if total else None
            went_under = not went_over if total else None

            supabase.table("results").insert({
                "game_id": game_id,
                "home_score": home_score,
                "away_score": away_score,
                "home_covered": home_covered,
                "away_covered": away_covered,
                "went_over": went_over,
                "went_under": went_under,
            }).execute()

            print(f"Stored result: {away_team} @ {home_team} — {away_score}-{home_score}")


fetch_and_store()
fetch_and_store_results()
