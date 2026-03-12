# F1 Fantasy Optimizer — Usage Guide

## Setup

```bash
cd ~/f1-optimizer
source .venv/bin/activate
```

Your cookie will expire periodically. To refresh it:
1. Open https://fantasy.formula1.com in your browser
2. Log in, then open DevTools (F12) → Application → Cookies
3. Copy the full cookie string
4. Paste it into `.env` as `F1F_COOKIE="..."`

## Weekly Workflow

### 1. Sync latest data

```bash
f1opt fantasy sync
```

Pulls current prices, fantasy points, and PPM for all 22 drivers and 11 constructors directly from the F1 Fantasy API.

### 2. See where the value is

```bash
# Full value board (drivers + constructors sorted by points-per-million)
f1opt analyze value

# Drivers only
f1opt analyze value --type driver

# Constructors only
f1opt analyze value --type constructor
```

PPM (points per million) is the key metric — it tells you who's giving you the most fantasy points per dollar spent. High PPM = underpriced relative to performance.

### 3. Check your current team

```bash
# Show your team for the upcoming gameday
f1opt fantasy team --gameday 2

# Show your team from last gameday
f1opt fantasy team --gameday 1
```

The gameday number comes from the schedule. Use `f1opt fantasy schedule` to see which gameday is next.

### 4. Get the optimal team

```bash
# Default: best possible team for $100M
f1opt optimize

# Custom budget (if you have less than 100M available)
f1opt optimize --budget 96.8

# Lock in players you want to keep (use player IDs from the value board)
f1opt optimize --lock 131 --lock 1982

# Exclude players you don't want
f1opt optimize --exclude 114

# Combine: keep Verstappen (131), drop Hadjar (11032), budget of 98M
f1opt optimize --lock 131 --exclude 11032 --budget 98
```

The optimizer solves for the mathematically best combination of 5 drivers + 2 constructors + turbo driver pick within your budget. It uses integer linear programming — same class of math used for logistics and scheduling.

### 5. Check the schedule

```bash
f1opt fantasy schedule
```

Shows every race, which gameday it belongs to, and whether it's locked (done), open, or next. Sprint weekends have extra sessions.

### 6. League standings

```bash
f1opt fantasy standings
```

Shows your private league rankings and points.

## Player IDs

The optimizer uses F1 Fantasy player IDs (numbers), not driver names. You'll see these in the output of `f1opt fantasy team` and `f1opt analyze value`. Some key ones:

| ID | Player |
|---|---|
| 131 | Max Verstappen |
| 1982 | Oscar Piastri |
| 114 | Liam Lawson |
| 121 | Sergio Perez |
| 11031 | Oliver Bearman |
| 11032 | Isack Hadjar |

Run `f1opt fantasy sync` and then `f1opt analyze value` to see all current IDs.

## Tips

- **Run `f1opt fantasy sync` before every race weekend** to get updated prices. Prices shift based on ownership and performance.
- **Sprint weekends score double sessions** — drivers who qualify well become more valuable on sprint weekends.
- **The turbo driver (TD) gets 2x points.** The optimizer picks the TD automatically — it's always the driver with the highest expected points.
- **PPM matters most early season.** Cheap overperformers (like Bearman at $8M scoring 20 pts = 2.5 PPM) are how you gain ground in your league.
- **Negative PPM = actively hurting you.** Stroll (-3.11 PPM), Hulkenberg (-3.23), Aston Martin (-3.92) are costing you points every race.
- **Budget management:** The optimizer will tell you how much budget you have left. Don't waste it — $1-2M remaining is fine, $10M sitting unused means you're leaving points on the table.

## Refreshing Historical Data

```bash
# Pull race results from a full season (for track affinity analysis)
f1opt ingest season 2025

# Pull a specific round
f1opt ingest round 2025 3
```

## Troubleshooting

- **"No player data"** → Run `f1opt fantasy sync` first
- **"Could not fetch standings / Check your cookie"** → Your cookie expired. Refresh it from the browser.
- **Optimizer picks weird teams** → Early in the season with only 1 race of data, the model has limited signal. It improves every race weekend.
- **"403" on API calls** → Cookie expired or the `entity` header is wrong. Sync again after refreshing the cookie.
