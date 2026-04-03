# Project Notes

Important context for working on this project — covers hard-won lessons, pipeline logic, and future plans.

## Two Repositories

| Repo | Purpose |
|------|---------|
| `MLBOdds` | Python data pipeline — fetches odds and results, stores in Supabase |
| `mlb-odds-frontend` | Next.js frontend — displays today's odds and yesterday's results |

Both share the same Supabase database.

---

## Data Pipeline

### Order of Operations
The GitHub Actions workflow runs daily at 10 AM ET and executes in this order:

1. **Fetch yesterday's scores** (`fetch_and_store_results()`) — must run first so that yesterday's games already exist in the `games` table when results tries to link to them
2. **Fetch today's odds** (`fetch_and_store()`) — runs second, populates `games` and `odds` for today

If this order is reversed, results will have no matching game to link to and won't display on the frontend.

### When Results First Appear
The pipeline only stores results for games with a `detailedState` of `"Final"` from the MLB Stats API. Games are fetched across a two-day window (yesterday + today in UTC) to account for late night ET games that finish after midnight UTC.

---

## Known Quirks & Fixes

### GMT/ET Timezone Issue
Both the Odds API and the frontend query use UTC. MLB games run until ~11:59 PM ET which is 3:59 AM UTC the next day. Without adjustment, games starting after ~8 PM ET get cut off.

**Fix in Python (odds fetch):**
```python
eastern = pytz.timezone("America/New_York")
today = datetime.now(eastern)
end_of_day = today + timedelta(days=0.75)
commence_from = today.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
commence_to = end_of_day.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
```

**Fix in Python (results fetch):**
```python
"startDate": yesterday,
"endDate": today,  # spans two UTC days to catch late ET games
```

**Fix in frontend (Supabase query):**
```js
const tomorrow = new Date(Date.now() + 86400000).toISOString().split("T")[0];
.lte("commence_time", `${tomorrow}T03:59:59Z`)  // covers up to 11:59 PM ET
```

### Odds API Date Format
The Odds API requires dates in exactly this format: `YYYY-MM-DDTHH:MM:SSZ`

Python's `.isoformat()` produces `+00:00` instead of `Z` which the API rejects.
Always use `.strftime("%Y-%m-%dT%H:%M:%SZ")` instead.

### American Odds Format
The Odds API returns decimal odds by default (e.g. `1.91`).
Always include `"oddsFormat": "american"` in the API params to get American format (e.g. `-110`, `+145`).

### Team Name Matching
The Odds API and MLB Stats API use slightly different team name formats. If results are not linking to games, check whether team names match exactly between the two APIs. A name mapping dictionary may be needed if mismatches are found.

---

## Environment Variables

| Variable | Used In | Where Stored |
|----------|---------|--------------|
| `ODDS_API_KEY` | Python pipeline | `.env` locally, GitHub Secrets for Actions |
| `SUPABASE_URL` | Python pipeline + frontend | `.env` / `.env.local` locally, GitHub Secrets + Vercel env vars |
| `SUPABASE_KEY` | Python pipeline + frontend | `.env` / `.env.local` locally, GitHub Secrets + Vercel env vars |
| `NEXT_PUBLIC_SUPABASE_URL` | Frontend only | `.env.local` locally, Vercel env vars |
| `NEXT_PUBLIC_SUPABASE_KEY` | Frontend only | `.env.local` locally, Vercel env vars |

Note: Frontend variables must be prefixed with `NEXT_PUBLIC_` to be accessible in the browser.

---

## External APIs

### The Odds API
- **Docs:** https://the-odds-api.com/liveapi/guides/v4/
- **Endpoint:** `GET /v4/sports/baseball_mlb/odds`
- **Key params:** `regions=us`, `oddsFormat=american`, `dateFormat=iso`, `bookmakers=betmgm,draftkings,fanduel,caesars`
- **Quota:** Each bookmaker in a request counts as one request. Free tier = 500/month. Check `x-requests-remaining` header after each call.

### MLB Stats API
- **Free, no API key required**
- **Endpoint:** `GET https://statsapi.mlb.com/api/v1/schedule`
- **Key params:** `sportId=1`, `startDate`, `endDate`, `hydrate=linescore`
- **Filter:** Only process games where `status.detailedState == "Final"`

---

## Future Plans

### Visualizations (once full season of data is available)
- Cover rate by bookmaker — which book's lines are sharpest?
- Over/under hit rate by day of week, game time, team
- Line movement vs actual outcome
- Best value bookmaker per market type
- Team trends: which teams cover most/least often

### Tech stack for visualizations
- **Recharts** — pairs well with Next.js, beginner friendly
- Add a `/visualizations` page to the frontend once enough data is collected (aim for 4+ weeks minimum)

### Potential additions
- Results summary stats on the results page (cover rate %, over rate %)
- Historical results browser (navigate to any past date)
- Email or push notification if a line moves significantly from open
