"""
customers.py — Customer Data Generator
═══════════════════════════════════════

WHAT THIS DOES:
───────────────
Generates realistic customer records for the mobility platform.
Each customer has:
  - A unique sequential ID (C0001, C0002, ...)
  - Realistic Indian names (using Faker's en_IN locale)
  - Valid email and phone
  - A city from our configured list
  - A signup date in the past

WHY SEQUENTIAL IDs:
───────────────────
In real systems, IDs come from databases (auto-increment) or
distributed ID generators (Snowflake IDs, UUIDs). We use
sequential IDs because:
  1. Easy to trace in logs during debugging
  2. Predictable for testing
  3. Easy to reference in rides and payments

In production, you'd use UUIDs or database-generated IDs.
"""

import random
from datetime import date, timedelta
from dataclasses import asdict

from faker import Faker

from src.models.schemas import Customer
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Indian locale for realistic names
fake = Faker("en_IN")


def generate_customers(
    num_customers: int,
    cities: list[dict],
    seed: int = 42
) -> list[dict]:
    """
    Generate a list of customer records.

    Args:
        num_customers: How many customers to generate.
        cities: List of city config dicts from config.yaml.
                Each dict has: name, areas, lat_range, lon_range.
        seed: Random seed for reproducibility.

    Returns:
        List of customer dicts ready for CSV/JSON writing.

    DESIGN NOTE — Why return dicts, not dataclass instances?
    ─────────────────────────────────────────────────────────
    Dicts are more flexible for serialization (CSV, JSON, Parquet).
    We validate via the dataclass constructor, then convert to dict.
    This pattern is called "validate on creation, serialize as needed."
    """
    Faker.seed(seed)
    random.seed(seed)

    city_names = [c["name"] for c in cities]
    customers = []

    logger.info(f"Starting customer generation: {num_customers} records")

    for i in range(1, num_customers + 1):
        city = random.choice(city_names)

        # Signup date: randomly in the last 2 years
        days_ago = random.randint(1, 730)
        signup = date.today() - timedelta(days=days_ago)

        # Some customers may have deactivated (5% chance)
        is_active = random.random() > 0.05

        customer = Customer(
            customer_id=f"C{i:04d}",
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            email=fake.email(),
            phone=fake.phone_number(),
            city=city,
            signup_date=signup,
            is_active=is_active
        )

        customers.append(asdict(customer))

    logger.info(
        f"Customer generation complete: {len(customers)} records | "
        f"Active: {sum(1 for c in customers if c['is_active'])} | "
        f"Inactive: {sum(1 for c in customers if not c['is_active'])}"
    )

    return customers
