"""
generator.py — Data Generation Orchestrator
════════════════════════════════════════════

WHAT THIS DOES:
───────────────
This is the ORCHESTRATOR — it coordinates the generation of all
four datasets in the correct order.

WHY ORDER MATTERS:
──────────────────
The datasets have DEPENDENCIES:

  1. Customers  → no dependencies (generate first)
  2. Drivers    → no dependencies (generate first)
  3. Rides      → depends on customer_ids AND driver_ids
  4. Payments   → depends on ride data (ride_ids, fares, times)

This is a DAG (Directed Acyclic Graph):

  Customers ──┐
              ├──→ Rides ──→ Payments
  Drivers ───┘

This same DAG concept appears again in:
  - Phase 5: PySpark join order
  - Phase 7: Glue job dependencies
  - Phase 10: Airflow DAG definition

DESIGN PATTERN — Orchestrator:
──────────────────────────────
The orchestrator pattern separates:
  - WHAT to do (generate customers, drivers, rides, payments)
  - HOW to do it (individual generator modules)
  - WHEN to do it (dependency order)
  - WHERE to save it (file I/O)

This separation means you can:
  - Change how customers are generated without touching this file
  - Add new datasets without changing existing generators
  - Switch output format (CSV → JSON → Parquet) in one place
"""

import csv
import json
import os
from datetime import datetime, date
from pathlib import Path

from src.data_generator.customers import generate_customers
from src.data_generator.drivers import generate_drivers
from src.data_generator.rides import generate_rides
from src.data_generator.payments import generate_payments
from src.utils.config_loader import ConfigLoader
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class CustomEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles datetime and date objects.

    Python's default json.dumps() can't serialize datetime objects.
    This encoder converts them to ISO format strings:
      datetime(2026, 8, 25, 10, 30) → "2026-08-25T10:30:00"
      date(2026, 8, 25)             → "2026-08-25"
    """
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def _write_csv(data: list[dict], filepath: Path) -> None:
    """Write a list of dicts to a CSV file."""
    if not data:
        logger.warning(f"No data to write to {filepath}")
        return

    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    size_mb = filepath.stat().st_size / (1024 * 1024)
    logger.info(f"Written CSV: {filepath} ({len(data)} rows, {size_mb:.2f} MB)")


def _write_json(data: list[dict], filepath: Path) -> None:
    """Write a list of dicts to a JSON file."""
    if not data:
        logger.warning(f"No data to write to {filepath}")
        return

    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, cls=CustomEncoder)

    size_mb = filepath.stat().st_size / (1024 * 1024)
    logger.info(f"Written JSON: {filepath} ({len(data)} rows, {size_mb:.2f} MB)")


def run_data_generation(config: ConfigLoader) -> dict:
    """
    Run the complete data generation pipeline.

    Pipeline Order (DAG):
    ─────────────────────
      Customers ──┐
                  ├──→ Rides ──→ Payments
      Drivers ───┘

    Args:
        config: Loaded ConfigLoader instance.

    Returns:
        Dict with summary statistics for each dataset.
    """
    start_time = datetime.now()

    logger.info("=" * 60)
    logger.info("MOBILITY DATA GENERATION — STARTING")
    logger.info("=" * 60)

    # ── Load configuration ────────────────────────────────────
    num_customers = config.get("data_generation", "num_customers")
    num_drivers = config.get("data_generation", "num_drivers")
    num_rides = config.get("data_generation", "num_rides")
    num_payments = config.get("data_generation", "num_payments")
    output_dir = config.get("data_generation", "output_dir")
    formats = config.get("data_generation", "formats")
    seed = config.get("data_generation", "random_seed")

    cities = config.get("geography", "cities")
    ride_params = config.get("ride_params")
    driver_params = config.get("driver_params")
    payment_params = config.get("payment_params")

    logger.info(f"Configuration loaded:")
    logger.info(f"  Customers: {num_customers}")
    logger.info(f"  Drivers:   {num_drivers}")
    logger.info(f"  Rides:     {num_rides}")
    logger.info(f"  Payments:  {num_payments}")
    logger.info(f"  Formats:   {formats}")
    logger.info(f"  Seed:      {seed}")
    logger.info(f"  Cities:    {[c['name'] for c in cities]}")

    # ── Step 1: Generate Customers (no dependencies) ──────────
    logger.info("-" * 40)
    logger.info("STEP 1/4: Generating Customers")
    customers = generate_customers(num_customers, cities, seed)

    # ── Step 2: Generate Drivers (no dependencies) ────────────
    logger.info("-" * 40)
    logger.info("STEP 2/4: Generating Drivers")
    drivers = generate_drivers(
        num_drivers, cities,
        driver_params["vehicle_types"],
        driver_params["rating_range"],
        seed
    )

    # ── Step 3: Generate Rides (depends on customers + drivers)
    logger.info("-" * 40)
    logger.info("STEP 3/4: Generating Rides")
    customer_ids = [c["customer_id"] for c in customers]
    driver_ids = [d["driver_id"] for d in drivers]
    rides = generate_rides(
        num_rides, customer_ids, driver_ids, cities, ride_params, seed
    )

    # ── Step 4: Generate Payments (depends on rides) ──────────
    logger.info("-" * 40)
    logger.info("STEP 4/4: Generating Payments")
    payments = generate_payments(num_payments, rides, payment_params, seed)

    # ── Write output files ────────────────────────────────────
    logger.info("-" * 40)
    logger.info("Writing output files...")

    datasets = {
        "customers": customers,
        "drivers": drivers,
        "rides": rides,
        "payments": payments,
    }

    base_path = Path(output_dir)

    for name, data in datasets.items():
        if "csv" in formats:
            _write_csv(data, base_path / name / f"{name}.csv")
        if "json" in formats:
            _write_json(data, base_path / name / f"{name}.json")

    # ── Summary ───────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).total_seconds()

    summary = {
        "customers_generated": len(customers),
        "drivers_generated": len(drivers),
        "rides_generated": len(rides),
        "payments_generated": len(payments),
        "output_dir": str(base_path.resolve()),
        "formats": formats,
        "elapsed_seconds": round(elapsed, 2),
    }

    logger.info("=" * 60)
    logger.info("MOBILITY DATA GENERATION — COMPLETE")
    logger.info(f"  Total time: {elapsed:.2f} seconds")
    logger.info(f"  Customers: {len(customers)}")
    logger.info(f"  Drivers:   {len(drivers)}")
    logger.info(f"  Rides:     {len(rides)}")
    logger.info(f"  Payments:  {len(payments)}")
    logger.info(f"  Output:    {base_path.resolve()}")
    logger.info("=" * 60)

    return summary
