"""Ingest race data from Jolpica (Ergast) API into the local DB."""

import time
import requests
from rich.console import Console

from . import config
from .db import get_connection

console = Console(stderr=True)

_last_req = 0.0


def _throttled_get(url: str) -> dict | None:
    global _last_req
    elapsed = time.time() - _last_req
    if elapsed < 0.3:
        time.sleep(0.3 - elapsed)
    _last_req = time.time()
    resp = requests.get(url, timeout=15)
    if resp.status_code == 200:
        return resp.json()
    console.print(f"[red]Jolpica {resp.status_code}: {url}[/red]")
    return None


def fetch_schedule(season: int = 2025):
    """Fetch race calendar and store in DB."""
    data = _throttled_get(f"{config.JOLPICA_BASE_URL}/{season}.json")
    if not data:
        return
    races = data["MRData"]["RaceTable"]["Races"]
    conn = get_connection()
    for r in races:
        has_sprint = 1 if "Sprint" in r else 0
        conn.execute(
            "INSERT OR REPLACE INTO races VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                season,
                int(r["round"]),
                r["raceName"],
                r["Circuit"]["circuitId"],
                r["Circuit"]["circuitName"],
                r["date"],
                has_sprint,
            ),
        )
    conn.commit()
    conn.close()
    console.print(f"[green]Imported {len(races)} races for {season}[/green]")


def fetch_drivers(season: int = 2025):
    """Fetch driver list for season."""
    data = _throttled_get(f"{config.JOLPICA_BASE_URL}/{season}/drivers.json")
    if not data:
        return
    drivers = data["MRData"]["DriverTable"]["Drivers"]
    conn = get_connection()
    for d in drivers:
        conn.execute(
            "INSERT OR REPLACE INTO drivers (driver_id, code, given_name, family_name, nationality) VALUES (?, ?, ?, ?, ?)",
            (d["driverId"], d.get("code", ""), d["givenName"], d["familyName"], d.get("nationality", "")),
        )
    conn.commit()
    conn.close()
    console.print(f"[green]Imported {len(drivers)} drivers for {season}[/green]")


def fetch_constructors(season: int = 2025):
    """Fetch constructor list for season."""
    data = _throttled_get(f"{config.JOLPICA_BASE_URL}/{season}/constructors.json")
    if not data:
        return
    constructors = data["MRData"]["ConstructorTable"]["Constructors"]
    conn = get_connection()
    for c in constructors:
        conn.execute(
            "INSERT OR REPLACE INTO constructors VALUES (?, ?, ?)",
            (c["constructorId"], c["name"], c.get("nationality", "")),
        )
    conn.commit()
    conn.close()
    console.print(f"[green]Imported {len(constructors)} constructors for {season}[/green]")


def fetch_results(season: int, round_num: int):
    """Fetch race results for a specific round."""
    data = _throttled_get(
        f"{config.JOLPICA_BASE_URL}/{season}/{round_num}/results.json"
    )
    if not data:
        return
    results = data["MRData"]["RaceTable"]["Races"]
    if not results:
        return
    race_results = results[0].get("Results", [])
    conn = get_connection()
    for r in race_results:
        pos = int(r["position"]) if r.get("position") else None
        conn.execute(
            "INSERT OR REPLACE INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                season,
                round_num,
                r["Driver"]["driverId"],
                "race",
                int(r["grid"]),
                pos,
                float(r["points"]),
                r.get("status", ""),
            ),
        )
        # Update driver -> constructor mapping
        if "Constructor" in r:
            conn.execute(
                "UPDATE drivers SET constructor_id = ? WHERE driver_id = ?",
                (r["Constructor"]["constructorId"], r["Driver"]["driverId"]),
            )
    conn.commit()
    conn.close()
    console.print(f"[green]Imported race results: {season} R{round_num}[/green]")


def fetch_qualifying(season: int, round_num: int):
    """Fetch qualifying results for a specific round."""
    data = _throttled_get(
        f"{config.JOLPICA_BASE_URL}/{season}/{round_num}/qualifying.json"
    )
    if not data:
        return
    results = data["MRData"]["RaceTable"]["Races"]
    if not results:
        return
    quali = results[0].get("QualifyingResults", [])
    conn = get_connection()
    for r in quali:
        conn.execute(
            "INSERT OR REPLACE INTO race_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                season,
                round_num,
                r["Driver"]["driverId"],
                "qualifying",
                0,
                int(r["position"]),
                0,
                "Finished",
            ),
        )
    conn.commit()
    conn.close()
    console.print(f"[green]Imported qualifying: {season} R{round_num}[/green]")


def fetch_season(season: int = 2025):
    """Fetch all available data for a season."""
    console.print(f"[bold]Ingesting {season} season data...[/bold]")
    fetch_schedule(season)
    fetch_drivers(season)
    fetch_constructors(season)

    # Fetch results for completed rounds
    conn = get_connection()
    races = conn.execute(
        "SELECT round FROM races WHERE season = ? AND date <= date('now') ORDER BY round",
        (season,),
    ).fetchall()
    conn.close()

    for race in races:
        r = race["round"]
        fetch_results(season, r)
        fetch_qualifying(season, r)
    console.print(f"[bold green]Season {season} ingestion complete.[/bold green]")
