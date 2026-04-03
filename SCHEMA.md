# Database Schema

This project uses a Supabase (PostgreSQL) database with four tables.

## Tables

### `games`
One row per MLB game. Populated daily by the Python pipeline.

```sql
create table games (
  id uuid default gen_random_uuid() primary key,
  api_game_id text unique,  -- ID from The Odds API, used to prevent duplicate inserts
  sport text default 'MLB',
  home_team text,
  away_team text,
  commence_time timestamptz,
  created_at timestamptz default now()
);
```

### `odds`
One row per bookmaker per game. Multiple rows per game (one per book).

```sql
create table odds (
  id uuid default gen_random_uuid() primary key,
  game_id uuid references games(id) on delete cascade,
  bookmaker text,           -- e.g. 'betmgm', 'draftkings', 'fanduel', 'caesars'
  fetched_at timestamptz default now(),

  -- Spreads
  spread_home numeric,      -- e.g. -1.5
  spread_home_price numeric, -- juice on home spread, e.g. -110
  spread_away numeric,      -- e.g. +1.5
  spread_away_price numeric,

  -- Totals
  total_over numeric,       -- e.g. 8.5
  total_over_price numeric,
  total_under numeric,
  total_under_price numeric,

  -- Moneyline
  ml_home numeric,          -- e.g. -145
  ml_away numeric           -- e.g. +125
);
```

### `results`
One row per game. Populated the following morning by the Python pipeline.

```sql
create table results (
  id uuid default gen_random_uuid() primary key,
  game_id uuid references games(id) on delete cascade,
  home_score int,
  away_score int,
  home_covered boolean,     -- did home team cover the spread?
  away_covered boolean,
  went_over boolean,        -- did the total go over?
  went_under boolean,
  recorded_at timestamptz default now()
);
```

## Key Relationships

```
games (1) ──── (many) odds
games (1) ──── (1) results
```

## Notes

- `games.api_game_id` is the unique key used to upsert games and prevent duplicates on re-runs
- `results` links to `games` via `game_id` — results will not display on the frontend if the corresponding game is not in the `games` table
- All odds are stored in **American format** (e.g. -110, +145) — make sure `oddsFormat=american` is set in the Odds API call
- Odds are stored as `numeric` not `int` to handle half-point spreads and totals
