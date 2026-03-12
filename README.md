# F1 Fantasy Optimizer

A Python CLI tool that pulls live data from the F1 Fantasy API and uses integer linear programming to find the optimal team within a budget cap.

## What it does

- Syncs current driver/constructor prices and fantasy points from fantasy.formula1.com
- Ranks players by points-per-million (PPM) to surface underpriced picks
- Solves for the mathematically best 5 drivers + 2 constructors + turbo driver within your budget
- Supports locking in players you want to keep and excluding ones you don't
- Pulls historical race results from Jolpica for track affinity analysis

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

You'll need your cookie from fantasy.formula1.com (DevTools → Application → Cookies) and your game/league IDs.

## Usage

```bash
f1opt init                              # Initialize the database
f1opt fantasy sync                      # Sync prices and points
f1opt analyze value                     # PPM rankings
f1opt optimize                          # Best team for $100M
f1opt optimize --lock 131 --budget 98   # Lock Verstappen, custom budget
f1opt fantasy team --gameday 2          # Your current team
f1opt fantasy standings                 # League standings
f1opt fantasy schedule                  # Race calendar
```

See [USAGE.md](USAGE.md) for the full weekly workflow and tips.

## Stack

- **PuLP** — integer linear programming solver (CBC backend)
- **Typer + Rich** — CLI and terminal output
- **SQLite** — local data store
- **Jolpica API** — historical race results (formerly Ergast)
- **F1 Fantasy API** — live prices, points, team data

## Requirements

Python 3.10+
