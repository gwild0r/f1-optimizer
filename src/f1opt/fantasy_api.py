"""Client for the F1 Fantasy API at fantasy.formula1.com.

Two data sources:
1. Static feeds at /feeds/ — public-ish JSON files for stats, schedule, config
2. Authenticated API at /services/user/ — user-specific data (team, gamedays)

Both require the session cookie. Feeds also require the `entity` header.
"""

import json
import time
from datetime import datetime, timezone

import requests
from rich.console import Console

from . import config
from .db import get_connection

console = Console(stderr=True)

# Tour ID for the current season (2026 = 4, discovered from schedule feed)
CURRENT_TOUR_ID = 4


class FantasyAPIClient:
    """HTTP client for F1 Fantasy endpoints."""

    def __init__(self, cookie: str | None = None):
        self.cookie = cookie or config.F1F_COOKIE
        self.game_id = config.F1F_GAME_ID
        self.league_id = config.F1F_LEAGUE_ID
        self.user_id = config.F1F_USER_ID
        self.base_url = "https://fantasy.formula1.com"
        self.session = requests.Session()
        self.session.headers.update({
            "Cookie": self.cookie,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Referer": "https://fantasy.formula1.com/en/my-team",
            "Accept": "application/json, text/plain, */*",
            "entity": "Wh@t$|_||>",
        })
        self._last_request = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_request = time.time()

    def _buster(self) -> str:
        return str(int(time.time() * 1000))

    def _get(self, path: str, label: str = "") -> dict | None:
        self._throttle()
        url = f"{self.base_url}/{path}"
        try:
            resp = self.session.get(url, params={"buster": self._buster()}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self._cache(label or path, data)
                return data
            else:
                console.print(f"[dim]{resp.status_code} {path}[/dim]")
                return None
        except Exception as e:
            console.print(f"[red]Error: {path} — {e}[/red]")
            return None

    def _cache(self, key: str, data: dict):
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO api_cache (url, response, fetched_at) VALUES (?, ?, ?)",
            (key, json.dumps(data), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    # === STATIC FEEDS (player data, schedule, config) ===

    def get_driver_stats(self, tour_id: int = CURRENT_TOUR_ID) -> dict | None:
        """Driver statistics including prices, fantasy points, PPM."""
        return self._get(f"feeds/statistics/drivers_{tour_id}.json", "driver_stats")

    def get_constructor_stats(self, tour_id: int = CURRENT_TOUR_ID) -> dict | None:
        """Constructor statistics including prices and fantasy points."""
        return self._get(f"feeds/statistics/constructors_{tour_id}.json", "constructor_stats")

    def get_schedule(self) -> dict | None:
        """Race schedule with gameday IDs, session times, lock status."""
        return self._get("feeds/schedule/raceday_en.json", "schedule")

    def get_constraints(self) -> dict | None:
        """Game constraints: budget cap, active gameday, deadlines."""
        return self._get("feeds/limits/constraints.json", "constraints")

    def get_circuit_config(self) -> dict | None:
        """Circuit configurations for the season."""
        return self._get("feeds/circuit/configurations_en.json", "circuit_config")

    def get_boosters(self) -> dict | None:
        """Available boosters (chips) info."""
        return self._get("feeds/booster/boosters.json", "boosters")

    def get_mixapi(self) -> dict | None:
        """Live game status — maintenance, feed busters, live flags."""
        return self._get("feeds/live/mixapi.json", "mixapi")

    def get_player_popup(self, player_id: str) -> dict | None:
        """Detailed stats popup for a specific player."""
        return self._get(f"feeds/popup/playerstats_{player_id}.json", f"player_{player_id}")

    # === AUTHENTICATED API (user-specific) ===

    def get_league_standings(self) -> dict | None:
        """Private league standings."""
        path = (
            f"services/user/leaderboard/{self.game_id}/"
            f"pvtleagueuserrankget/1/{self.league_id}/0/1/1/50/"
        )
        return self._get(path, "league_standings")

    def get_my_team(self, gameday_id: int = 1, phase_id: int = 1) -> dict | None:
        """Your team for a specific gameday.

        optType=1 means regular team, teamNo=1 is your first (only) team.
        """
        path = (
            f"services/user/gameplay/{self.game_id}/"
            f"getteam/1/1/{gameday_id}/{phase_id}"
        )
        return self._get(path, f"my_team_gd{gameday_id}")

    def get_user_gamedays(self) -> dict | None:
        """Your gameday history — chips used, team IDs, matchday details."""
        path = f"services/user/gameplay/{self.game_id}/getusergamedaysv1/1"
        return self._get(path, "user_gamedays")

    # === HIGH-LEVEL HELPERS ===

    def fetch_all_players(self, tour_id: int = CURRENT_TOUR_ID) -> list[dict]:
        """Fetch all drivers and constructors with prices/points.

        Returns a unified list of player dicts ready for DB import.
        """
        players = []

        # Drivers
        driver_data = self.get_driver_stats(tour_id)
        if driver_data:
            for stat in driver_data["Data"]["statistics"]:
                if stat["config"]["key"] == "fPoints":
                    for p in stat["participants"]:
                        players.append({
                            "player_id": str(p["playerid"]),
                            "player_type": "driver",
                            "display_name": p["playername"],
                            "short_name": p["playername"].split()[-1][:3].upper(),
                            "team_name": p["teamname"],
                            "team_id": str(p.get("teamid", "")),
                            "current_price": float(p["curvalue"]),
                            "season_score": float(p["statvalue"]),
                        })
                    break

        # Constructors
        constructor_data = self.get_constructor_stats(tour_id)
        if constructor_data:
            for stat in constructor_data["Data"]["statistics"]:
                if stat["config"]["key"] == "fPoints":
                    for p in stat["participants"]:
                        players.append({
                            "player_id": str(p.get("teamid", p.get("playerid", ""))),
                            "player_type": "constructor",
                            "display_name": p["teamname"],
                            "short_name": p["teamname"][:3].upper(),
                            "team_name": p["teamname"],
                            "team_id": str(p.get("teamid", "")),
                            "current_price": float(p["curvalue"]),
                            "season_score": float(p["statvalue"]),
                        })
                    break

        return players

    def fetch_enriched_players(self, tour_id: int = CURRENT_TOUR_ID) -> list[dict]:
        """Fetch all players with additional stats (PPM, price change, etc)."""
        players = self.fetch_all_players(tour_id)

        # Build lookup by player_id
        lookup = {p["player_id"]: p for p in players}

        # Enrich with PPM data from driver stats
        for feed_func, ptype in [
            (self.get_driver_stats, "driver"),
            (self.get_constructor_stats, "constructor"),
        ]:
            data = feed_func(tour_id)
            if not data:
                continue
            for stat in data["Data"]["statistics"]:
                key = stat["config"]["key"]
                if key in ("pointsPermillion", "priceChange", "mostPicked", "fAvg"):
                    for p in stat["participants"]:
                        pid = str(p.get("playerid", p.get("teamid", "")))
                        if pid in lookup:
                            lookup[pid][key] = float(p["statvalue"])

        return players

    def dump_cache(self) -> dict:
        """Return all cached API responses."""
        conn = get_connection()
        rows = conn.execute("SELECT url, response, fetched_at FROM api_cache").fetchall()
        conn.close()
        return {
            row["url"]: {
                "data": json.loads(row["response"]),
                "fetched_at": row["fetched_at"],
            }
            for row in rows
        }
