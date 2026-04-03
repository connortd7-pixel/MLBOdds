# MLB Odds Tracker

A Python script that fetches daily MLB betting odds from [The Odds API](https://the-odds-api.com/) and stores them in a [Supabase](https://supabase.com/) database for analysis and comparison across bookmakers.

## Features

- Fetches daily MLB spreads, totals, and moneylines
- Supports multiple bookmakers (BetMGM, DraftKings, FanDuel, Caesars, etc.)
- Stores data in Supabase for easy querying and line comparison
- Filters to today's games only using Eastern Time
- Designed to run once daily via GitHub Actions (10 AM ET)

## Requirements

- Python 3.11+
- A free [Odds API key](https://the-odds-api.com/)
- A [Supabase](https://supabase.com/) project

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/mlb-odds-tracker.git
cd mlb-odds-tracker
```

2. Install dependencies:
```bash
pip install requests supabase pytz
```

3. Set up your environment variables (see Configuration below).

## Configuration

Create a `.env` file in the root of the project (this file is excluded from Git):

```
ODDS_API_KEY=your_odds_api_key_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key_here
```

## Database Setup

Run the following SQL in your Supabase project to create the required tables:

```sql
create table games (
  id uuid default gen_random_uuid() primary key,
  api_game_id text unique,
  sport text default 'MLB',
  home_team text,
  away_team text,
  commence_time timestamptz,
  created_at timestamptz default now()
);

create table odds (
  id uuid default gen_random_uuid() primary key,
  game_id uuid references games(id) on delete cascade,
  bookmaker text,
  fetched_at timestamptz default now(),
  spread_home numeric,
  spread_home_price numeric,
  spread_away numeric,
  spread_away_price numeric,
  total_over numeric,
  total_over_price numeric,
  total_under numeric,
  total_under_price numeric,
  ml_home numeric,
  ml_away numeric
);
```

## Usage

Run the script manually:
```bash
python main.py
```

Or let GitHub Actions run it automatically at 10 AM ET every day (see `.github/workflows/fetch_odds.yml`).

## Automated Scheduling

This project includes a GitHub Actions workflow that runs the script daily at 10 AM Eastern Time. To enable it:

1. Push this repo to GitHub
2. Go to **Settings → Secrets and variables → Actions**
3. Add the following secrets:
   - `ODDS_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`

The workflow also supports manual triggers from the **Actions** tab in GitHub.

## Bookmakers Supported

| Key | Bookmaker |
|-----|-----------|
| `betmgm` | BetMGM |
| `draftkings` | DraftKings |
| `fanduel` | FanDuel |
| `caesars` | Caesars |
| `pointsbet` | PointsBet |
| `betonlineag` | BetOnline |

Edit the `bookmakers` parameter in `main.py` to add or remove books.

## API Quota

The Odds API free tier includes 500 requests/month. Each bookmaker in a request counts as one request. Running once daily with 4 bookmakers uses ~120 requests/month.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
