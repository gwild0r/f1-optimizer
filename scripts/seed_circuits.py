"""Seed circuit trait classifications."""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))

from f1opt.db import init_db

CIRCUIT_TRAITS = [
    ("albert_park", "balanced", "Melbourne - medium speed, mix of fast and slow corners"),
    ("shanghai", "power", "Shanghai - long straights, heavy braking zones"),
    ("suzuka", "high_downforce", "Suzuka - high-speed flowing corners, technical"),
    ("bahrain", "balanced", "Bahrain - mix of slow corners and straights, high tire deg"),
    ("jeddah", "power", "Jeddah - ultra high speed street circuit, low downforce"),
    ("miami", "balanced", "Miami - medium speed, mix of corners and straights"),
    ("imola", "high_downforce", "Imola - old-school, narrow, high downforce"),
    ("monaco", "street", "Monaco - ultra slow, maximum downforce, qualifying is race"),
    ("catalunya", "balanced", "Barcelona - benchmark circuit, balanced setup"),
    ("villeneuve", "power", "Montreal - stop/start, heavy braking, low downforce"),
    ("red_bull_ring", "power", "Spielberg - short lap, heavy braking, low downforce"),
    ("silverstone", "high_downforce", "Silverstone - fast flowing corners, high speed"),
    ("hungaroring", "high_downforce", "Budapest - slow and twisty, like Monaco without walls"),
    ("spa", "power", "Spa - long straights, fast corners, low downforce"),
    ("zandvoort", "high_downforce", "Zandvoort - narrow, banked corners, high downforce"),
    ("monza", "power", "Monza - temple of speed, minimum downforce"),
    ("baku", "street", "Baku - long straight + tight street section"),
    ("marina_bay", "street", "Singapore - night street race, high downforce, brutal"),
    ("americas", "balanced", "COTA - mix of everything, elevation changes"),
    ("rodriguez", "power", "Mexico City - high altitude, thin air, long straights"),
    ("interlagos", "balanced", "Interlagos - short lap, elevation, unpredictable weather"),
    ("losail", "high_downforce", "Losail - fast flowing, high speed corners"),
    ("yas_marina", "balanced", "Abu Dhabi - mix of slow and medium speed corners"),
    ("vegas", "power", "Las Vegas - long straights, low downforce, cold temps"),
]


def main():
    conn = init_db()
    for circuit_id, circuit_type, notes in CIRCUIT_TRAITS:
        conn.execute(
            "INSERT OR REPLACE INTO circuit_traits VALUES (?, ?, ?)",
            (circuit_id, circuit_type, notes),
        )
    conn.commit()
    conn.close()
    print(f"Seeded {len(CIRCUIT_TRAITS)} circuit traits.")


if __name__ == "__main__":
    main()
