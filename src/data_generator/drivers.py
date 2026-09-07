"""
drivers.py — Driver Data Generator
═══════════════════════════════════

WHAT THIS DOES:
───────────────
Generates realistic driver records with:
  - Vehicle types distributed by config weights (more Sedans, fewer Bikes)
  - Ratings between 3.0-5.0 (skewed towards higher ratings — realistic)
  - Indian license numbers
  - City assignments

WEIGHTED RANDOM SELECTION:
──────────────────────────
We don't just pick vehicle types randomly with equal probability.
In reality:
  - 35% of drivers have Sedans
  - 30% Hatchbacks
  - 20% SUVs
  - 10% Autos
  - 5% Bikes

This is done using random.choices(weights=...) which lets us
control the distribution. This makes our synthetic data MORE
realistic and leads to better analytics.

SYSTEM DESIGN NOTE:
───────────────────
In a real ride-hailing platform, drivers are a separate microservice:

  Driver Service
    ├── Registration API
    ├── Profile management
    ├── Document verification
    ├── Rating system
    └── Availability tracking

Our generator simulates the OUTPUT of this service — what you'd
see if you queried the driver database.
"""

import random
from datetime import date, timedelta
from dataclasses import asdict

from faker import Faker

from src.models.schemas import Driver
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

fake = Faker("en_IN")


def _generate_license_number() -> str:
    """
    Generate a realistic Indian driving license number.
    Format: XX-YYZZZZZZZZZZ (State-Year-Number)
    """
    states = ["MH", "KA", "DL", "TN", "TS", "AP", "GJ", "RJ"]
    state = random.choice(states)
    year = random.randint(15, 26)
    number = random.randint(10000000, 99999999)
    return f"{state}-{year:02d}{number}"


def generate_drivers(
    num_drivers: int,
    cities: list[dict],
    vehicle_config: list[dict],
    rating_range: list[float],
    seed: int = 42
) -> list[dict]:
    """
    Generate a list of driver records.

    Args:
        num_drivers: How many drivers to generate.
        cities: City config list from config.yaml.
        vehicle_config: Vehicle types with probability weights.
                        e.g., [{"type": "Sedan", "weight": 0.35}, ...]
        rating_range: [min_rating, max_rating] e.g., [3.0, 5.0]
        seed: Random seed for reproducibility.

    Returns:
        List of driver dicts.
    """
    Faker.seed(seed + 100)  # Different seed offset from customers
    random.seed(seed + 100)

    city_names = [c["name"] for c in cities]
    vehicle_types = [v["type"] for v in vehicle_config]
    vehicle_weights = [v["weight"] for v in vehicle_config]

    drivers = []

    logger.info(f"Starting driver generation: {num_drivers} records")

    for i in range(1, num_drivers + 1):
        city = random.choice(city_names)

        # Weighted vehicle type selection
        vehicle_type = random.choices(vehicle_types, weights=vehicle_weights, k=1)[0]

        # Rating: skewed towards higher values (most drivers are decent)
        # Using beta distribution: more mass near the top
        raw_rating = random.betavariate(5, 2)  # Skewed high
        min_r, max_r = rating_range
        rating = round(min_r + raw_rating * (max_r - min_r), 1)

        # Join date: randomly in the last 3 years
        days_ago = random.randint(1, 1095)
        join = date.today() - timedelta(days=days_ago)

        # 8% of drivers are inactive
        is_active = random.random() > 0.08

        driver = Driver(
            driver_id=f"D{i:04d}",
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            phone=fake.phone_number(),
            city=city,
            vehicle_type=vehicle_type,
            license_number=_generate_license_number(),
            rating=rating,
            join_date=join,
            is_active=is_active
        )

        drivers.append(asdict(driver))

    # Log distribution summary
    vehicle_dist = {}
    for d in drivers:
        vt = d["vehicle_type"]
        vehicle_dist[vt] = vehicle_dist.get(vt, 0) + 1

    avg_rating = sum(d["rating"] for d in drivers) / len(drivers)

    logger.info(
        f"Driver generation complete: {len(drivers)} records | "
        f"Avg rating: {avg_rating:.2f} | "
        f"Vehicle distribution: {vehicle_dist}"
    )

    return drivers
