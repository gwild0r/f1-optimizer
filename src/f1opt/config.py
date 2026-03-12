"""Configuration: loads .env and exposes typed settings."""

import os
from dotenv import load_dotenv

load_dotenv()

# F1 Fantasy API credentials
F1F_COOKIE: str = os.getenv("F1F_COOKIE", "")
F1F_GAME_ID: str = os.getenv("F1F_GAME_ID", "75393a4e-0009-11f0-b57f-13ad5af721a0")
F1F_LEAGUE_ID: str = os.getenv("F1F_LEAGUE_ID", "9631802")
F1F_USER_ID: str = os.getenv("F1F_USER_ID", "188505834")

# External APIs
JOLPICA_BASE_URL: str = "https://api.jolpi.ca/ergast/f1"

# Optimizer defaults
BUDGET_CAP: float = 100.0
