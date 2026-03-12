"""Rich-based terminal output formatting."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .models import TeamPick

console = Console()


def print_value_board(entries: list[dict], title: str = "Value Board"):
    """Print a formatted value board table."""
    table = Table(title=title, show_lines=False)
    table.add_column("ID", style="dim", width=5)
    table.add_column("Player", style="bold")
    table.add_column("Team", style="dim")
    table.add_column("Type", style="dim", width=6)
    table.add_column("Price", justify="right", style="cyan")
    table.add_column("Season Pts", justify="right", style="green")
    table.add_column("PPM", justify="right", style="yellow bold")
    table.add_column("Form", justify="right", style="magenta")
    table.add_column("Exp Pts", justify="right", style="blue")

    for i, e in enumerate(entries, 1):
        table.add_row(
            e["player_id"],
            e["display_name"],
            e.get("team_name", ""),
            e["player_type"][:4],
            f"${e['price']:.1f}M",
            f"{e['season_score']:.0f}",
            f"{e['ppm']:.2f}",
            f"{e['form']:.1f}" if e.get("form") else "-",
            f"{e['expected']:.1f}" if e.get("expected") else "-",
        )

    console.print(table)


def print_team(team: TeamPick, title: str = "Optimal Team"):
    """Print the optimized team selection."""
    table = Table(title=title, show_lines=True)
    table.add_column("Slot", style="dim", width=14)
    table.add_column("Player", style="bold")
    table.add_column("Team", style="dim")
    table.add_column("Price", justify="right", style="cyan")
    table.add_column("Exp Pts", justify="right", style="green")

    exp_pts = team.details.get("player_expected_points", {})

    for i, d in enumerate(team.drivers, 1):
        is_turbo = team.turbo_driver and d.player_id == team.turbo_driver.player_id
        slot = f"Driver {i}" + (" [TD]" if is_turbo else "")
        name = d.display_name + (" ⚡" if is_turbo else "")
        pts = exp_pts.get(d.player_id, 0)
        display_pts = pts * 2 if is_turbo else pts
        table.add_row(
            slot,
            name,
            d.team_name,
            f"${d.current_price:.1f}M",
            f"{display_pts:.1f}",
        )

    for i, c in enumerate(team.constructors, 1):
        pts = exp_pts.get(c.player_id, 0)
        table.add_row(
            f"Constructor {i}",
            c.display_name,
            "",
            f"${c.current_price:.1f}M",
            f"{pts:.1f}",
        )

    console.print(table)
    console.print(
        Panel(
            f"Total Cost: [cyan]${team.total_cost:.1f}M[/cyan]  |  "
            f"Budget Left: [yellow]${team.budget_remaining:.1f}M[/yellow]  |  "
            f"Expected Points: [green]{team.expected_points:.1f}[/green]",
            title="Summary",
        )
    )


def print_comparison(current: TeamPick, optimized: TeamPick, diff: dict):
    """Print side-by-side comparison of two teams."""
    console.print("\n[bold]Transfer Recommendations[/bold]\n")

    if diff["transfers_out"]:
        console.print("[red]OUT:[/red]")
        for pid in diff["transfers_out"]:
            console.print(f"  - {pid}")

    if diff["transfers_in"]:
        console.print("[green]IN:[/green]")
        for pid in diff["transfers_in"]:
            console.print(f"  + {pid}")

    console.print(f"\nExpected points change: [bold]{diff['points_diff']:+.1f}[/bold]")
    console.print(f"Cost change: {diff['cost_diff']:+.1f}M")


def print_standings(data: dict):
    """Print league standings from API response."""
    try:
        standings = data["Data"]["Value"]["memRank"]
        league_name = data["Data"]["Value"]["leagueInfo"]["leagueName"]
    except (KeyError, TypeError):
        console.print("[red]Could not parse standings data[/red]")
        return

    from urllib.parse import unquote
    table = Table(title=unquote(league_name))
    table.add_column("#", style="dim", width=3)
    table.add_column("Team", style="bold")
    table.add_column("Points", justify="right", style="green")

    for i, team in enumerate(standings, 1):
        table.add_row(
            str(i),
            unquote(team["teamName"]),
            f"{team['ovPoints']:,}",
        )

    console.print(table)
