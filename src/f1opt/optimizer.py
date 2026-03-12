"""ILP-based team optimizer using PuLP.

Solves: pick 5 drivers + 2 constructors + 1 turbo driver under a budget cap
to maximize expected fantasy points.
"""

from pulp import LpMaximize, LpProblem, LpBinary, lpSum, LpVariable, value as lp_value

from .db import get_connection
from .analysis import expected_fantasy_points
from .models import FantasyPlayer, TeamPick
from . import config


def _load_players(season: int = 2025) -> list[FantasyPlayer]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM fantasy_players WHERE season = ?", (season,)
    ).fetchall()
    conn.close()
    return [
        FantasyPlayer(
            player_id=r["player_id"],
            player_type=r["player_type"],
            display_name=r["display_name"],
            short_name=r["short_name"],
            team_name=r["team_name"],
            season=r["season"],
            current_price=r["current_price"],
            season_score=r["season_score"],
        )
        for r in rows
    ]


def optimize_team(
    season: int = 2025,
    budget: float | None = None,
    locked: list[str] | None = None,
    excluded: list[str] | None = None,
    num_drivers: int = 5,
    num_constructors: int = 2,
    current_team_ids: set[str] | None = None,
    max_transfers: int | None = None,
) -> TeamPick | None:
    """Find the optimal team composition.

    Args:
        season: F1 season year
        budget: Budget cap in millions (default from config)
        locked: Player IDs that MUST be in the team
        excluded: Player IDs that MUST NOT be in the team
        num_drivers: Number of driver slots (default 5)
        num_constructors: Number of constructor slots (default 2)
        current_team_ids: Set of player IDs on your current team (for transfer limit)
        max_transfers: Max players you can swap out without penalty (None = unlimited)

    Returns:
        TeamPick with optimal team, or None if infeasible.
    """
    budget = budget or config.BUDGET_CAP
    locked = set(locked or [])
    excluded = set(excluded or [])

    players = _load_players(season)
    if not players:
        return None

    drivers = [p for p in players if p.player_type == "driver"]
    constructors = [p for p in players if p.player_type == "constructor"]

    # Calculate expected points for each player
    exp_pts = {}
    for p in players:
        exp_pts[p.player_id] = expected_fantasy_points(p.player_id, season)

    # Build ILP
    prob = LpProblem("F1_Fantasy_Optimizer", LpMaximize)

    # Decision variables: x[i] = 1 if player i is selected
    x = {p.player_id: LpVariable(f"x_{p.player_id}", cat=LpBinary) for p in players}

    # Turbo variable: t[j] = 1 if driver j is the turbo driver
    t = {d.player_id: LpVariable(f"t_{d.player_id}", cat=LpBinary) for d in drivers}

    # Objective: maximize expected points + turbo bonus (turbo driver scored 2x)
    prob += lpSum(
        exp_pts[p.player_id] * x[p.player_id] for p in players
    ) + lpSum(
        exp_pts[d.player_id] * t[d.player_id] for d in drivers
    ), "Total_Expected_Points"

    # Budget constraint
    prob += lpSum(
        p.current_price * x[p.player_id] for p in players
    ) <= budget, "Budget"

    # Exactly num_drivers drivers
    prob += lpSum(x[d.player_id] for d in drivers) == num_drivers, "Driver_Count"

    # Exactly num_constructors constructors
    prob += lpSum(x[c.player_id] for c in constructors) == num_constructors, "Constructor_Count"

    # Exactly one turbo driver
    prob += lpSum(t[d.player_id] for d in drivers) == 1, "One_Turbo"

    # Turbo must be a selected driver
    for d in drivers:
        prob += t[d.player_id] <= x[d.player_id], f"Turbo_Selected_{d.player_id}"

    # Lock constraints
    for pid in locked:
        if pid in x:
            prob += x[pid] == 1, f"Lock_{pid}"

    # Exclude constraints
    for pid in excluded:
        if pid in x:
            prob += x[pid] == 0, f"Exclude_{pid}"

    # Transfer limit: at most max_transfers players can differ from current team
    if current_team_ids and max_transfers is not None:
        # Count how many current-team players are dropped (not selected)
        current_in_pool = [pid for pid in current_team_ids if pid in x]
        # Must keep at least (team_size - max_transfers) current players
        min_keep = len(current_in_pool) - max_transfers
        if min_keep > 0:
            prob += lpSum(x[pid] for pid in current_in_pool) >= min_keep, "Transfer_Limit"

    # Solve
    from pulp import PULP_CBC_CMD
    prob.solve(PULP_CBC_CMD(msg=0))

    if prob.status != 1:  # 1 = Optimal
        return None

    # Extract solution
    selected_drivers = [d for d in drivers if lp_value(x[d.player_id]) > 0.5]
    selected_constructors = [c for c in constructors if lp_value(x[c.player_id]) > 0.5]
    turbo = next((d for d in drivers if lp_value(t[d.player_id]) > 0.5), None)

    selected_ids = {p.player_id for p in selected_drivers + selected_constructors}
    total_cost = sum(p.current_price for p in selected_drivers + selected_constructors)
    total_expected = lp_value(prob.objective) or 0.0

    return TeamPick(
        drivers=selected_drivers,
        constructors=selected_constructors,
        turbo_driver=turbo,
        total_cost=total_cost,
        expected_points=total_expected,
        budget_remaining=budget - total_cost,
        details={
            "budget": budget,
            "locked": list(locked),
            "excluded": list(excluded),
            "max_transfers": max_transfers,
            "transfers_used": (
                len(current_team_ids - selected_ids) if current_team_ids else None
            ),
            "player_expected_points": {
                p.player_id: exp_pts[p.player_id]
                for p in selected_drivers + selected_constructors
            },
        },
    )


def compare_teams(current: TeamPick, optimized: TeamPick) -> dict:
    """Compare current team vs optimized suggestion."""
    current_ids = {p.player_id for p in current.drivers + current.constructors}
    opt_ids = {p.player_id for p in optimized.drivers + optimized.constructors}

    return {
        "transfers_out": current_ids - opt_ids,
        "transfers_in": opt_ids - current_ids,
        "kept": current_ids & opt_ids,
        "points_diff": optimized.expected_points - current.expected_points,
        "cost_diff": optimized.total_cost - current.total_cost,
    }
