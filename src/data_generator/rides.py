"""
rides.py — Ride Data Generator
═══════════════════════════════

WHAT THIS DOES:
───────────────
Generates realistic ride records. This is the CORE dataset —
rides connect customers, drivers, locations, and time.

KEY DESIGN DECISIONS:
─────────────────────
1. REFERENTIAL INTEGRITY
   Every ride references a REAL customer_id and driver_id.
   We don't generate random IDs — we pick from the actual
   lists of customers and drivers. This means our data has
   proper foreign-key relationships from the start.

   This is CRITICAL because in Phase 6 (Data Quality), we'll
   validate that every ride's customer_id exists in the customer
   dataset. If we generated random IDs, that check would fail.

2. REALISTIC TIME PATTERNS
   - Rides cluster during peak hours (8-10 AM, 5-9 PM)
   - Weekend vs weekday patterns differ
   - pickup_time is NULL if ride was cancelled before pickup
   - dropoff_time is NULL if ride didn't complete

3. INTENTIONAL DATA QUALITY ISSUES
   We deliberately inject some bad data:
   - ~2% of rides have negative distances (data quality test)
   - ~1% have zero fare (data quality test)
   - ~3% have slightly inconsistent city names (standardization test)

   These simulate real-world data problems that our Silver layer
   transformations will need to handle.

INFRASTRUCTURE NOTE — Data Volume:
──────────────────────────────────
10,000 rides generates ~2MB of CSV. This is fine for local dev.

  10K rides    →  ~2 MB   →  runs in seconds   (laptop)
  1M rides     →  ~200 MB →  runs in minutes    (laptop)
  100M rides   →  ~20 GB  →  needs Spark cluster (cloud)
  1B rides     →  ~200 GB →  needs distributed   (production)

The SAME pipeline code works at all scales — that's the power
of designing for distributed processing from the start.
"""

import random
from datetime import datetime, timedelta
from dataclasses import asdict

from src.models.schemas import Ride
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def _get_peak_hour_weight(hour: int) -> float:
    """
    Return a weight for the given hour to simulate realistic
    ride demand patterns.

    Peak hours (high demand):
      Morning: 8-10 AM  (commute)
      Evening: 5-9 PM   (commute + social)

    Low demand:
      Late night: 1-5 AM
    """
    peak_weights = {
        0: 0.3, 1: 0.15, 2: 0.1, 3: 0.08, 4: 0.08, 5: 0.1,
        6: 0.3, 7: 0.6, 8: 1.0, 9: 1.0, 10: 0.7, 11: 0.6,
        12: 0.7, 13: 0.6, 14: 0.5, 15: 0.5, 16: 0.6, 17: 0.9,
        18: 1.0, 19: 1.0, 20: 0.8, 21: 0.7, 22: 0.5, 23: 0.4
    }
    return peak_weights.get(hour, 0.5)


def _generate_request_time(start_date: str, end_date: str) -> datetime:
    """
    Generate a ride request time with realistic hourly distribution.

    Instead of uniform random, we use weighted selection to create
    peak-hour clustering.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    delta = (end - start).days

    # Pick a random day
    random_day = start + timedelta(days=random.randint(0, delta))

    # Pick hour with peak-hour weighting
    hours = list(range(24))
    weights = [_get_peak_hour_weight(h) for h in hours]
    hour = random.choices(hours, weights=weights, k=1)[0]

    minute = random.randint(0, 59)
    second = random.randint(0, 59)

    return random_day.replace(hour=hour, minute=minute, second=second)


def generate_rides(
    num_rides: int,
    customer_ids: list[str],
    driver_ids: list[str],
    cities: list[dict],
    ride_params: dict,
    seed: int = 42
) -> list[dict]:
    """
    Generate ride records with referential integrity.

    Args:
        num_rides: Number of rides to generate.
        customer_ids: Valid customer IDs to reference.
        driver_ids: Valid driver IDs to reference.
        cities: City config with areas and lat/lon ranges.
        ride_params: Ride parameters from config (statuses, fares, etc.)
        seed: Random seed.

    Returns:
        List of ride dicts.
    """
    random.seed(seed + 200)

    # Parse ride parameters
    statuses = [s["status"] for s in ride_params["statuses"]]
    status_weights = [s["weight"] for s in ride_params["statuses"]]

    base_fare_min, base_fare_max = ride_params["base_fare_range"]
    per_km_min, per_km_max = ride_params["per_km_rate_range"]
    dist_min, dist_max = ride_params["distance_range"]
    surge_min, surge_max = ride_params["surge_multiplier_range"]

    date_start = ride_params["date_range"]["start"]
    date_end = ride_params["date_range"]["end"]

    # Build city lookup for area and coordinate generation
    city_lookup = {c["name"]: c for c in cities}
    city_names = list(city_lookup.keys())

    # Intentionally messy city name variants (for standardization testing)
    messy_city_variants = {
        "Mumbai": ["Mumbai", "mumbai", "MUMBAI", "mumbai "],
        "Pune": ["Pune", "pune", "PUNE", "pune "],
        "Bangalore": ["Bangalore", "bangalore", "BANGALORE", "Bengaluru"],
        "Delhi": ["Delhi", "delhi", "DELHI", "New Delhi"],
        "Hyderabad": ["Hyderabad", "hyderabad", "HYDERABAD"],
        "Chennai": ["Chennai", "chennai", "CHENNAI"],
    }

    rides = []

    logger.info(f"Starting ride generation: {num_rides} records")

    for i in range(1, num_rides + 1):
        # Pick customer and driver (referential integrity!)
        customer_id = random.choice(customer_ids)
        driver_id = random.choice(driver_ids)

        # Pick pickup city and area
        pickup_city_clean = random.choice(city_names)
        pickup_config = city_lookup[pickup_city_clean]
        pickup_area = random.choice(pickup_config["areas"])

        # Dropoff: 70% same city, 30% different city (intercity trips)
        if random.random() < 0.70:
            dropoff_city_clean = pickup_city_clean
        else:
            dropoff_city_clean = random.choice(city_names)

        dropoff_config = city_lookup[dropoff_city_clean]
        dropoff_area = random.choice(dropoff_config["areas"])

        # Generate coordinates within city bounds
        pickup_lat = round(random.uniform(*pickup_config["lat_range"]), 6)
        pickup_lon = round(random.uniform(*pickup_config["lon_range"]), 6)
        dropoff_lat = round(random.uniform(*dropoff_config["lat_range"]), 6)
        dropoff_lon = round(random.uniform(*dropoff_config["lon_range"]), 6)

        # ── Intentional data quality issues (~3% messy city names) ──
        if random.random() < 0.03:
            pickup_city = random.choice(
                messy_city_variants.get(pickup_city_clean, [pickup_city_clean])
            )
        else:
            pickup_city = pickup_city_clean

        if random.random() < 0.03:
            dropoff_city = random.choice(
                messy_city_variants.get(dropoff_city_clean, [dropoff_city_clean])
            )
        else:
            dropoff_city = dropoff_city_clean

        # Ride status (weighted)
        ride_status = random.choices(statuses, weights=status_weights, k=1)[0]

        # Request time with peak-hour distribution
        request_time = _generate_request_time(date_start, date_end)

        # Distance
        distance_km = round(random.uniform(dist_min, dist_max), 2)

        # ── Intentional bad data: ~2% negative distance ──
        if random.random() < 0.02:
            distance_km = round(-abs(distance_km), 2)

        # Fare calculation
        base_fare = random.uniform(base_fare_min, base_fare_max)
        per_km_rate = random.uniform(per_km_min, per_km_max)
        surge = round(random.uniform(surge_min, surge_max), 1)

        fare = round((base_fare + per_km_rate * abs(distance_km)) * surge, 2)

        # ── Intentional bad data: ~1% zero fare ──
        if random.random() < 0.01:
            fare = 0.0

        # Pickup and dropoff times depend on ride status
        pickup_time = None
        dropoff_time = None

        if ride_status == "completed":
            pickup_time = request_time + timedelta(minutes=random.randint(2, 15))
            duration_minutes = random.randint(
                ride_params["min_duration_minutes"],
                ride_params["max_duration_minutes"]
            )
            dropoff_time = pickup_time + timedelta(minutes=duration_minutes)

        elif ride_status == "ongoing":
            pickup_time = request_time + timedelta(minutes=random.randint(2, 15))
            # No dropoff yet — ride is in progress

        elif ride_status == "cancelled":
            # 50% cancelled before pickup, 50% after
            if random.random() < 0.5:
                pickup_time = request_time + timedelta(minutes=random.randint(2, 10))

        # no_show: driver arrived but customer didn't — no pickup/dropoff

        ride = Ride(
            ride_id=f"R{i:05d}",
            customer_id=customer_id,
            driver_id=driver_id,
            pickup_city=pickup_city,
            pickup_area=pickup_area,
            dropoff_city=dropoff_city,
            dropoff_area=dropoff_area,
            pickup_lat=pickup_lat,
            pickup_lon=pickup_lon,
            dropoff_lat=dropoff_lat,
            dropoff_lon=dropoff_lon,
            request_time=request_time,
            pickup_time=pickup_time,
            dropoff_time=dropoff_time,
            distance_km=distance_km,
            fare=fare,
            surge_multiplier=surge,
            ride_status=ride_status
        )

        rides.append(asdict(ride))

    # ─── Log summary statistics ──────────────────────────────
    status_counts = {}
    for r in rides:
        s = r["ride_status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    negative_dist = sum(1 for r in rides if r["distance_km"] < 0)
    zero_fare = sum(1 for r in rides if r["fare"] == 0)
    avg_fare = sum(r["fare"] for r in rides) / len(rides)

    logger.info(
        f"Ride generation complete: {len(rides)} records | "
        f"Status distribution: {status_counts}"
    )
    logger.info(
        f"Ride data quality: "
        f"Negative distances: {negative_dist} | "
        f"Zero fares: {zero_fare} | "
        f"Avg fare: ₹{avg_fare:.2f}"
    )

    return rides
