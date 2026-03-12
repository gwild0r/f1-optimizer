"""SQLite database schema and connection management."""

import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "fantasy.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS drivers (
    driver_id   TEXT PRIMARY KEY,
    code        TEXT,
    given_name  TEXT,
    family_name TEXT,
    constructor_id TEXT,
    nationality TEXT
);

CREATE TABLE IF NOT EXISTS constructors (
    constructor_id TEXT PRIMARY KEY,
    name           TEXT,
    nationality    TEXT
);

CREATE TABLE IF NOT EXISTS races (
    season      INTEGER,
    round       INTEGER,
    race_name   TEXT,
    circuit_id  TEXT,
    circuit_name TEXT,
    date        TEXT,
    has_sprint  INTEGER DEFAULT 0,
    PRIMARY KEY (season, round)
);

CREATE TABLE IF NOT EXISTS race_results (
    season      INTEGER,
    round       INTEGER,
    driver_id   TEXT,
    session     TEXT,  -- 'race', 'qualifying', 'sprint'
    grid        INTEGER,
    position    INTEGER,
    points      REAL,
    status      TEXT,
    PRIMARY KEY (season, round, driver_id, session)
);

CREATE TABLE IF NOT EXISTS fantasy_prices (
    season      INTEGER,
    round       INTEGER,
    entity_id   TEXT,
    entity_type TEXT,  -- 'driver' or 'constructor'
    price       REAL,
    PRIMARY KEY (season, round, entity_id)
);

CREATE TABLE IF NOT EXISTS fantasy_points (
    season      INTEGER,
    round       INTEGER,
    entity_id   TEXT,
    entity_type TEXT,
    points      REAL,
    breakdown   TEXT,  -- JSON
    PRIMARY KEY (season, round, entity_id)
);

CREATE TABLE IF NOT EXISTS circuit_traits (
    circuit_id   TEXT PRIMARY KEY,
    circuit_type TEXT,  -- 'street', 'high_downforce', 'power', 'balanced'
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS fantasy_players (
    player_id    TEXT PRIMARY KEY,
    player_type  TEXT,  -- 'driver' or 'constructor'
    display_name TEXT,
    short_name   TEXT,
    team_name    TEXT,
    season       INTEGER,
    current_price REAL,
    season_score  REAL,
    image_url    TEXT,
    raw_json     TEXT   -- full API response for this player
);

CREATE TABLE IF NOT EXISTS my_team (
    slot         TEXT PRIMARY KEY,  -- 'driver1'-'driver5', 'constructor1'-'constructor2', 'turbo'
    entity_id    TEXT,
    entity_type  TEXT,
    locked_in    INTEGER DEFAULT 0,
    updated_at   TEXT
);

CREATE TABLE IF NOT EXISTS api_cache (
    url          TEXT PRIMARY KEY,
    response     TEXT,
    fetched_at   TEXT
);
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn
