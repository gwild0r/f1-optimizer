"""CLI interface for the F1 Fantasy Optimizer."""

import json
from typing import Optional

import typer
from rich.console import Console

from . import db, ingest, analysis, optimizer, display
from .fantasy_api import FantasyAPIClient

app = typer.Typer(name="f1opt", help="F1 Fantasy team optimizer")
console = Console()

# --- Subcommands ---
ingest_app = typer.Typer(help="Ingest race data from Jolpica API")
fantasy_app = typer.Typer(help="F1 Fantasy API operations")
analyze_app = typer.Typer(help="Analysis and value metrics")

app.add_typer(ingest_app, name="ingest")
app.add_typer(fantasy_app, name="fantasy")
app.add_typer(analyze_app, name="analyze")


def _check_cookie(client: FantasyAPIClient):
    if not client.cookie:
        console.print("[red]No F1F_COOKIE set. Add it to .env first.[/red]")
        raise typer.Exit(1)


def _import_players_to_db(players: list[dict], season: int = 2026):
    """Write player list into fantasy_players table."""
    conn = db.get_connection()
    count = 0
    for p in players:
        conn.execute(
            """INSERT OR REPLACE INTO fantasy_players
               (player_id, player_type, display_name, short_name, team_name,
                season, current_price, season_score, image_url, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                p["player_id"],
                p["player_type"],
                p["display_name"],
                p["short_name"],
                p["team_name"],
                season,
                p["current_price"],
                p["season_score"],
                "",
                json.dumps(p),
            ),
        )
        count += 1
    conn.commit()
    conn.close()
    return count


# --- Init ---
@app.command()
def init():
    """Initialize the database."""
    db.init_db()
    console.print("[green]Database initialized.[/green]")


# --- Ingest commands ---
@ingest_app.command("season")
def ingest_season(season: int = typer.Argument(2025)):
    """Ingest full season data from Jolpica."""
    db.init_db()
    ingest.fetch_season(season)


@ingest_app.command("round")
def ingest_round(
    season: int = typer.Argument(...),
    round_num: int = typer.Argument(...),
):
    """Ingest data for a specific round."""
    db.init_db()
    ingest.fetch_results(season, round_num)
    ingest.fetch_qualifying(season, round_num)


# --- Fantasy API commands ---
@fantasy_app.command("sync")
def fantasy_sync(tour_id: int = typer.Option(4, "--tour", "-t", help="Tour ID (2026=4)")):
    """Sync all player data from F1 Fantasy — prices, points, stats."""
    db.init_db()
    client = FantasyAPIClient()
    _check_cookie(client)

    console.print("[bold]Syncing player data from F1 Fantasy...[/bold]")
    players = client.fetch_enriched_players(tour_id)
    if not players:
        console.print("[red]No player data returned. Cookie may be expired.[/red]")
        raise typer.Exit(1)

    count = _import_players_to_db(players, season=2026)
    drivers = sum(1 for p in players if p["player_type"] == "driver")
    constructors = sum(1 for p in players if p["player_type"] == "constructor")
    console.print(
        f"[green]Synced {count} players ({drivers} drivers, {constructors} constructors)[/green]"
    )


@fantasy_app.command("standings")
def fantasy_standings():
    """Fetch and display league standings."""
    db.init_db()
    client = FantasyAPIClient()
    _check_cookie(client)
    data = client.get_league_standings()
    if data:
        display.print_standings(data)
    else:
        console.print("[red]Could not fetch standings. Check your cookie.[/red]")


@fantasy_app.command("team")
def fantasy_team(
    gameday: int = typer.Option(2, "--gameday", "-g", help="Gameday ID"),
):
    """Show your current team."""
    db.init_db()
    client = FantasyAPIClient()
    _check_cookie(client)

    # Get team data
    team_data = client.get_my_team(gameday_id=gameday)
    if not team_data:
        console.print("[red]Could not fetch team.[/red]")
        raise typer.Exit(1)

    # Get player names from stats
    players = client.fetch_all_players()
    player_lookup = {p["player_id"]: p for p in players}

    team = team_data["Data"]["Value"]
    if "userTeam" in team and team["userTeam"]:
        ut = team["userTeam"][0]
        console.print(f"\n[bold]Your Team (Gameday {gameday})[/bold]")
        console.print(f"Balance: [cyan]${ut.get('teambal', '?')}M[/cyan]")
        console.print(f"Overall Points: [green]{ut.get('ovpoints', '?')}[/green]")
        console.print(f"Gameday Points: [green]{ut.get('gdpoints', '?')}[/green]\n")

        from rich.table import Table
        table = Table(show_lines=True)
        table.add_column("Pos", width=4)
        table.add_column("Player", style="bold")
        table.add_column("Team", style="dim")
        table.add_column("Price", justify="right", style="cyan")
        table.add_column("Season Pts", justify="right", style="green")
        table.add_column("Role", style="yellow")

        for p in ut.get("playerid", []):
            pid = str(p["id"])
            info = player_lookup.get(pid, {})
            name = info.get("display_name", f"ID:{pid}")
            team_name = info.get("team_name", "")
            price = info.get("current_price", 0)
            score = info.get("season_score", 0)
            role = ""
            if p.get("iscaptain"):
                role = "TD (2x)"
            elif p.get("ismgcaptain"):
                role = "Mega"
            console.print
            table.add_row(
                str(p["playerpostion"]),
                name,
                team_name,
                f"${price:.1f}M",
                f"{score:.0f}",
                role,
            )

        console.print(table)


@fantasy_app.command("schedule")
def fantasy_schedule():
    """Show the race schedule with gameday IDs and lock status."""
    db.init_db()
    client = FantasyAPIClient()
    _check_cookie(client)
    data = client.get_schedule()
    if not data:
        console.print("[red]Could not fetch schedule.[/red]")
        return

    from rich.table import Table
    table = Table(title="F1 Fantasy Schedule")
    table.add_column("GD", width=3)
    table.add_column("Race", style="bold")
    table.add_column("Session")
    table.add_column("Date")
    table.add_column("Status")

    seen_meetings = set()
    for entry in data["Data"]["Value"]:
        gd = entry["GamedayId"]
        meeting = entry["MeetingName"]
        session_type = entry["SessionType"]
        date = entry.get("SessionStartDateISO8601", "")[:10]
        locked = entry.get("GDIsLocked", 0)
        current = entry.get("GDIsCurrent", 0)

        status = ""
        if current == 1:
            status = "[yellow]NEXT[/yellow]"
        elif locked == 1:
            status = "[dim]done[/dim]"
        else:
            status = "[green]open[/green]"

        key = f"{gd}-{session_type}"
        if key not in seen_meetings:
            seen_meetings.add(key)
            table.add_row(str(gd), meeting, session_type, date, status)

    console.print(table)


@fantasy_app.command("cache")
def fantasy_cache():
    """Show all cached API responses (for debugging)."""
    db.init_db()
    client = FantasyAPIClient()
    cache = client.dump_cache()
    if not cache:
        console.print("[dim]No cached responses.[/dim]")
        return
    for key, val in cache.items():
        console.print(f"\n[bold]{key}[/bold] (fetched {val['fetched_at']})")
        raw = json.dumps(val["data"], indent=2)
        if len(raw) > 2000:
            console.print(raw[:2000] + "\n... (truncated)")
        else:
            console.print_json(raw)


@fantasy_app.command("probe")
def fantasy_probe(
    path: str = typer.Argument(..., help="URL path, e.g. feeds/statistics/drivers_4.json"),
):
    """Probe a custom API path and print the response."""
    db.init_db()
    client = FantasyAPIClient()
    _check_cookie(client)
    data = client._get(path, label=f"probe:{path}")
    if data:
        console.print_json(json.dumps(data, indent=2)[:8000])
    else:
        console.print("[red]No response.[/red]")


# --- Analyze commands ---
@analyze_app.command("value")
def analyze_value(
    season: int = typer.Option(2026, "--season", "-s"),
    player_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Filter: driver or constructor"
    ),
):
    """Show the value board — all players ranked by points-per-million."""
    db.init_db()
    if player_type == "driver":
        board = analysis.driver_value_board(season)
    elif player_type == "constructor":
        board = analysis.constructor_value_board(season)
    else:
        board = analysis.value_board(season)

    if not board:
        console.print(
            "[yellow]No player data. Run 'f1opt fantasy sync' first.[/yellow]"
        )
        return
    display.print_value_board(board)


@analyze_app.command("form")
def analyze_form(
    player_id: str = typer.Argument(...),
    last_n: int = typer.Option(5, "--last", "-n"),
    season: int = typer.Option(2026, "--season", "-s"),
):
    """Show form score for a specific player."""
    db.init_db()
    score = analysis.form_score(player_id, last_n=last_n, season=season)
    race_score = analysis.race_form_score(player_id, last_n=last_n, season=season)
    console.print(f"[bold]{player_id}[/bold]")
    console.print(f"  Fantasy form (last {last_n}): [magenta]{score:.1f}[/magenta]")
    console.print(f"  Race form (last {last_n}):    [blue]{race_score:.1f}[/blue]")


# --- Optimize command ---
@app.command()
def optimize(
    season: int = typer.Option(2026, "--season", "-s"),
    budget: float = typer.Option(100.0, "--budget", "-b"),
    lock: Optional[list[str]] = typer.Option(
        None, "--lock", "-l", help="Player IDs to lock in"
    ),
    exclude: Optional[list[str]] = typer.Option(
        None, "--exclude", "-x", help="Player IDs to exclude"
    ),
    max_transfers: Optional[int] = typer.Option(
        None, "--max-transfers", "-m",
        help="Max transfers allowed (default: unlimited). Use 2 for free transfers."
    ),
    gameday: int = typer.Option(2, "--gameday", "-g", help="Current gameday (to load your team)"),
):
    """Find the optimal team within budget."""
    db.init_db()

    # If transfer limit is set, fetch current team to constrain changes
    current_team_ids = None
    if max_transfers is not None:
        client = FantasyAPIClient()
        _check_cookie(client)
        team_data = client.get_my_team(gameday_id=gameday)
        if team_data and "Data" in team_data:
            team = team_data["Data"]["Value"]
            if "userTeam" in team and team["userTeam"]:
                ut = team["userTeam"][0]
                current_team_ids = {str(p["id"]) for p in ut.get("playerid", [])}
                console.print(
                    f"[dim]Current team has {len(current_team_ids)} players. "
                    f"Max {max_transfers} transfer(s) allowed.[/dim]\n"
                )

        if not current_team_ids:
            console.print("[yellow]Could not fetch current team — running without transfer limit.[/yellow]")

    result = optimizer.optimize_team(
        season=season,
        budget=budget,
        locked=lock,
        excluded=exclude,
        current_team_ids=current_team_ids,
        max_transfers=max_transfers,
    )
    if result:
        display.print_team(result)
        # Show transfer summary when constrained
        if current_team_ids and result:
            opt_ids = {p.player_id for p in result.drivers + result.constructors}
            transfers_out = current_team_ids - opt_ids
            transfers_in = opt_ids - current_team_ids
            if transfers_out:
                console.print(f"\n[bold]Transfers ({len(transfers_out)}/{max_transfers}):[/bold]")
                # Load player names for display
                conn = db.get_connection()
                for pid in transfers_out:
                    row = conn.execute(
                        "SELECT display_name FROM fantasy_players WHERE player_id = ?", (pid,)
                    ).fetchone()
                    name = row["display_name"] if row else pid
                    console.print(f"  [red]OUT:[/red] {name}")
                for pid in transfers_in:
                    row = conn.execute(
                        "SELECT display_name FROM fantasy_players WHERE player_id = ?", (pid,)
                    ).fetchone()
                    name = row["display_name"] if row else pid
                    console.print(f"  [green]IN:[/green]  {name}")
                conn.close()
            else:
                console.print("\n[green]No transfers needed — your team is already optimal![/green]")
    else:
        console.print("[red]Optimization failed. Run 'f1opt fantasy sync' first.[/red]")


if __name__ == "__main__":
    app()
