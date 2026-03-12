"""Data models for F1 and Fantasy entities."""

from dataclasses import dataclass, field


@dataclass
class Driver:
    driver_id: str
    code: str
    given_name: str
    family_name: str
    constructor_id: str
    nationality: str = ""

    @property
    def display_name(self) -> str:
        return f"{self.given_name} {self.family_name}"


@dataclass
class Constructor:
    constructor_id: str
    name: str
    nationality: str = ""


@dataclass
class Race:
    season: int
    round: int
    race_name: str
    circuit_id: str
    circuit_name: str
    date: str
    has_sprint: bool = False


@dataclass
class RaceResult:
    season: int
    round: int
    driver_id: str
    session: str
    grid: int
    position: int | None
    points: float
    status: str


@dataclass
class FantasyPlayer:
    """A player (driver or constructor) from the F1 Fantasy API."""
    player_id: str
    player_type: str  # 'driver' or 'constructor'
    display_name: str
    short_name: str
    team_name: str
    season: int
    current_price: float
    season_score: float
    image_url: str = ""
    raw_json: str = ""


@dataclass
class TeamPick:
    """Result of an optimization run."""
    drivers: list[FantasyPlayer]
    constructors: list[FantasyPlayer]
    turbo_driver: FantasyPlayer | None
    total_cost: float
    expected_points: float
    budget_remaining: float
    details: dict = field(default_factory=dict)
