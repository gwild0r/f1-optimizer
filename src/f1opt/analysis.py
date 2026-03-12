"""Analytical functions: value metrics, form, expected points."""

from .db import get_connection
from . import config


def points_per_million(entity_id: str, season: int = 2025) -> float | None:
    """Total fantasy points / current price. Core value metric."""
    conn = get_connection()

    # Try fantasy_players table first (from API)
    row = conn.execute(
        "SELECT current_price, season_score FROM fantasy_players WHERE player_id = ? AND season = ?",
        (entity_id, season),
    ).fetchone()
    if row and row["current_price"] > 0:
        conn.close()
        return row["season_score"] / row["current_price"]

    # Fallback: fantasy_points + fantasy_prices tables
    pts = conn.execute(
        "SELECT SUM(points) as total FROM fantasy_points WHERE entity_id = ? AND season = ?",
        (entity_id, season),
    ).fetchone()
    price = conn.execute(
        "SELECT price FROM fantasy_prices WHERE entity_id = ? AND season = ? ORDER BY round DESC LIMIT 1",
        (entity_id, season),
    ).fetchone()
    conn.close()

    if pts and price and price["price"] > 0:
        return (pts["total"] or 0) / price["price"]
    return None


def form_score(entity_id: str, last_n: int = 5, season: int = 2025) -> float:
    """Weighted moving average of recent fantasy points. More recent = higher weight."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT points FROM fantasy_points
           WHERE entity_id = ? AND season = ?
           ORDER BY round DESC LIMIT ?""",
        (entity_id, season, last_n),
    ).fetchall()
    conn.close()

    if not rows:
        return 0.0

    # Weights: most recent gets highest weight
    total_weight = 0
    weighted_sum = 0
    for i, row in enumerate(rows):
        weight = last_n - i  # e.g. 5, 4, 3, 2, 1
        weighted_sum += row["points"] * weight
        total_weight += weight

    return weighted_sum / total_weight if total_weight else 0.0


def race_form_score(driver_id: str, last_n: int = 5, season: int = 2025) -> float:
    """Form based on actual F1 race results (points scored)."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT points FROM race_results
           WHERE driver_id = ? AND season = ? AND session = 'race'
           ORDER BY round DESC LIMIT ?""",
        (driver_id, season, last_n),
    ).fetchall()
    conn.close()

    if not rows:
        return 0.0

    total_weight = 0
    weighted_sum = 0
    for i, row in enumerate(rows):
        weight = last_n - i
        weighted_sum += row["points"] * weight
        total_weight += weight

    return weighted_sum / total_weight if total_weight else 0.0


def track_affinity(driver_id: str, circuit_id: str) -> float | None:
    """Average finishing position at a specific circuit across all seasons."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT rr.position FROM race_results rr
           JOIN races r ON rr.season = r.season AND rr.round = r.round
           WHERE rr.driver_id = ? AND r.circuit_id = ? AND rr.session = 'race'
           AND rr.position IS NOT NULL""",
        (driver_id, circuit_id),
    ).fetchall()
    conn.close()

    if not rows:
        return None
    return sum(r["position"] for r in rows) / len(rows)


def expected_fantasy_points(entity_id: str, season: int = 2026) -> float:
    """Estimate expected fantasy points for next race.

    Priority:
    1. Per-round fantasy form score (if we have round-by-round data)
    2. Season average from fantasy_players table (season_score / rounds_played)
    3. Race results form as a proxy
    """
    # Try fantasy-based form first (per-round data)
    form = form_score(entity_id, last_n=5, season=season)
    if form > 0:
        return form

    # Fallback: use season_score from fantasy_players as a per-race estimate
    conn = get_connection()
    row = conn.execute(
        "SELECT season_score FROM fantasy_players WHERE player_id = ? AND season = ?",
        (entity_id, season),
    ).fetchone()

    # Count locked gamedays from cached schedule data
    sched_row = conn.execute(
        "SELECT response FROM api_cache WHERE url = 'schedule'", ()
    ).fetchone()
    num_rounds = 1
    if sched_row:
        import json as _json
        try:
            sched = _json.loads(sched_row["response"])
            # Count distinct gamedays that are locked (completed)
            locked_gds = set()
            for entry in sched.get("Data", {}).get("Value", []):
                if entry.get("GDIsLocked", 0) == 1:
                    locked_gds.add(entry["GamedayId"])
            if locked_gds:
                num_rounds = len(locked_gds)
        except Exception:
            pass
    else:
        # Fallback to race_results table
        rr = conn.execute(
            "SELECT COUNT(DISTINCT round) as cnt FROM race_results WHERE season = ? AND session = 'race'",
            (season,),
        ).fetchone()
        if rr and rr["cnt"] > 0:
            num_rounds = rr["cnt"]
    conn.close()

    if row and row["season_score"] != 0:
        return row["season_score"] / num_rounds

    # Final fallback: race results form
    race_form = race_form_score(entity_id, last_n=5, season=season)
    if race_form > 0:
        return race_form * 2.5

    return 0.0


def value_board(season: int = 2025) -> list[dict]:
    """All players ranked by points-per-million. The 'shopping list' view."""
    conn = get_connection()

    players = conn.execute(
        "SELECT * FROM fantasy_players WHERE season = ? ORDER BY season_score DESC",
        (season,),
    ).fetchall()
    conn.close()

    board = []
    for p in players:
        ppm = p["season_score"] / p["current_price"] if p["current_price"] > 0 else 0
        board.append({
            "player_id": p["player_id"],
            "display_name": p["display_name"],
            "short_name": p["short_name"],
            "team_name": p["team_name"],
            "player_type": p["player_type"],
            "price": p["current_price"],
            "season_score": p["season_score"],
            "ppm": ppm,
            "form": form_score(p["player_id"], season=season),
            "expected": expected_fantasy_points(p["player_id"], season=season),
        })

    # Sort by PPM descending
    board.sort(key=lambda x: x["ppm"], reverse=True)
    return board


def driver_value_board(season: int = 2025) -> list[dict]:
    """Value board filtered to drivers only."""
    return [e for e in value_board(season) if e["player_type"] == "driver"]


def constructor_value_board(season: int = 2025) -> list[dict]:
    """Value board filtered to constructors only."""
    return [e for e in value_board(season) if e["player_type"] == "constructor"]
