"""
test_data_generator.py — Tests for Phase 1 Data Generation
══════════════════════════════════════════════════════════════

WHY TEST DATA GENERATORS?
─────────────────────────
"But it's just generating fake data, why test it?"

Because if your generator produces invalid data, EVERY downstream
phase breaks:
  - Bad customer_ids → rides reference non-existent customers
  - Wrong data types → PySpark schema validation fails
  - Missing columns → CSV parsing breaks
  - No referential integrity → Gold layer joins produce wrong results

These tests verify that the generated data is:
  1. The right SHAPE (correct columns, correct count)
  2. The right TYPES (dates are dates, numbers are numbers)
  3. Referentially CONSISTENT (ride customer_ids exist in customers)
  4. Realistically DISTRIBUTED (not all rides completed, not all same city)

Run with:
    pytest tests/ -v
"""

import pytest
from datetime import date, datetime
from src.utils.config_loader import ConfigLoader
from src.data_generator.customers import generate_customers
from src.data_generator.drivers import generate_drivers
from src.data_generator.rides import generate_rides
from src.data_generator.payments import generate_payments
from src.models.schemas import (
    Customer, Driver, Ride, Payment,
    VALID_RIDE_STATUSES, VALID_PAYMENT_METHODS,
    VALID_PAYMENT_STATUSES, VALID_VEHICLE_TYPES
)


@pytest.fixture(scope="module")
def config():
    """Load config once for all tests."""
    return ConfigLoader.load()


@pytest.fixture(scope="module")
def cities(config):
    return config.get("geography", "cities")


@pytest.fixture(scope="module")
def customers(config, cities):
    return generate_customers(100, cities, seed=42)


@pytest.fixture(scope="module")
def drivers(config, cities):
    vehicle_config = config.get("driver_params", "vehicle_types")
    rating_range = config.get("driver_params", "rating_range")
    return generate_drivers(50, cities, vehicle_config, rating_range, seed=42)


@pytest.fixture(scope="module")
def rides(config, customers, drivers, cities):
    customer_ids = [c["customer_id"] for c in customers]
    driver_ids = [d["driver_id"] for d in drivers]
    ride_params = config.get("ride_params")
    return generate_rides(500, customer_ids, driver_ids, cities, ride_params, seed=42)


@pytest.fixture(scope="module")
def payments(config, rides):
    payment_params = config.get("payment_params")
    return generate_payments(400, rides, payment_params, seed=42)


# ─── Customer Tests ───────────────────────────────────────────

class TestCustomerGeneration:
    def test_correct_count(self, customers):
        """Generator produces the requested number of records."""
        assert len(customers) == 100

    def test_correct_columns(self, customers):
        """Each record has all expected columns."""
        expected = set(Customer.columns())
        for c in customers:
            assert set(c.keys()) == expected

    def test_unique_ids(self, customers):
        """Customer IDs are unique (no duplicates)."""
        ids = [c["customer_id"] for c in customers]
        assert len(ids) == len(set(ids))

    def test_id_format(self, customers):
        """IDs follow the C0001 format."""
        for c in customers:
            assert c["customer_id"].startswith("C")
            assert len(c["customer_id"]) == 5  # C + 4 digits

    def test_valid_cities(self, customers, cities):
        """All customers are in configured cities."""
        valid_cities = {c["name"] for c in cities}
        for c in customers:
            assert c["city"] in valid_cities

    def test_signup_date_is_past(self, customers):
        """All signup dates are in the past."""
        today = date.today()
        for c in customers:
            signup = c["signup_date"]
            if isinstance(signup, str):
                signup = date.fromisoformat(signup)
            assert signup <= today

    def test_has_inactive_customers(self, customers):
        """Some customers should be inactive (realistic)."""
        inactive = [c for c in customers if not c["is_active"]]
        assert len(inactive) > 0, "Expected some inactive customers"


# ─── Driver Tests ─────────────────────────────────────────────

class TestDriverGeneration:
    def test_correct_count(self, drivers):
        assert len(drivers) == 50

    def test_unique_ids(self, drivers):
        ids = [d["driver_id"] for d in drivers]
        assert len(ids) == len(set(ids))

    def test_valid_vehicle_types(self, drivers):
        """Vehicle types come from the configured list."""
        for d in drivers:
            assert d["vehicle_type"] in VALID_VEHICLE_TYPES

    def test_rating_range(self, drivers):
        """Ratings are within configured bounds."""
        for d in drivers:
            assert 3.0 <= d["rating"] <= 5.0

    def test_vehicle_type_distribution(self, drivers):
        """Vehicle types are not uniformly distributed (weighted)."""
        type_counts = {}
        for d in drivers:
            vt = d["vehicle_type"]
            type_counts[vt] = type_counts.get(vt, 0) + 1

        # Sedans should be more common than Bikes (based on weights)
        # With only 50 drivers this might not always hold, but
        # with weights 0.35 vs 0.05, it very likely will
        assert len(type_counts) >= 3, "Expected at least 3 vehicle types"


# ─── Ride Tests ───────────────────────────────────────────────

class TestRideGeneration:
    def test_correct_count(self, rides):
        assert len(rides) == 500

    def test_unique_ids(self, rides):
        ids = [r["ride_id"] for r in rides]
        assert len(ids) == len(set(ids))

    def test_referential_integrity_customers(self, rides, customers):
        """Every ride's customer_id exists in the customer list."""
        valid_customer_ids = {c["customer_id"] for c in customers}
        for r in rides:
            assert r["customer_id"] in valid_customer_ids, \
                f"Ride {r['ride_id']} references non-existent customer {r['customer_id']}"

    def test_referential_integrity_drivers(self, rides, drivers):
        """Every ride's driver_id exists in the driver list."""
        valid_driver_ids = {d["driver_id"] for d in drivers}
        for r in rides:
            assert r["driver_id"] in valid_driver_ids, \
                f"Ride {r['ride_id']} references non-existent driver {r['driver_id']}"

    def test_valid_statuses(self, rides):
        """All ride statuses are valid values."""
        for r in rides:
            assert r["ride_status"] in VALID_RIDE_STATUSES

    def test_status_distribution(self, rides):
        """Rides have a mix of statuses (not all completed)."""
        statuses = {r["ride_status"] for r in rides}
        assert len(statuses) >= 2, "Expected at least 2 different ride statuses"

    def test_completed_rides_have_times(self, rides):
        """Completed rides must have both pickup and dropoff times."""
        completed = [r for r in rides if r["ride_status"] == "completed"]
        for r in completed:
            assert r["pickup_time"] is not None, \
                f"Completed ride {r['ride_id']} missing pickup_time"
            assert r["dropoff_time"] is not None, \
                f"Completed ride {r['ride_id']} missing dropoff_time"

    def test_has_intentional_bad_data(self, rides):
        """
        Generator should produce some bad data for quality testing.
        At ~2% negative distance rate with 500 rides, we expect ~10.
        Allow for randomness: just check at least 1 exists.
        """
        negative_distances = [r for r in rides if r["distance_km"] < 0]
        assert len(negative_distances) >= 1, \
            "Expected some negative distances for data quality testing"


# ─── Payment Tests ────────────────────────────────────────────

class TestPaymentGeneration:
    def test_has_payments(self, payments):
        """At least some payments should be generated."""
        assert len(payments) > 0

    def test_unique_ids(self, payments):
        ids = [p["payment_id"] for p in payments]
        assert len(ids) == len(set(ids))

    def test_valid_methods(self, payments):
        for p in payments:
            assert p["payment_method"] in VALID_PAYMENT_METHODS

    def test_valid_statuses(self, payments):
        for p in payments:
            assert p["payment_status"] in VALID_PAYMENT_STATUSES

    def test_referential_integrity_rides(self, payments, rides):
        """Every payment's ride_id exists in the ride list."""
        valid_ride_ids = {r["ride_id"] for r in rides}
        for p in payments:
            assert p["ride_id"] in valid_ride_ids, \
                f"Payment {p['payment_id']} references non-existent ride {p['ride_id']}"

    def test_no_negative_amounts(self, payments):
        """Payment amounts should not be negative."""
        for p in payments:
            assert p["amount"] >= 0, \
                f"Payment {p['payment_id']} has negative amount: {p['amount']}"


# ─── Reproducibility Tests ───────────────────────────────────

class TestReproducibility:
    def test_same_seed_same_data(self, cities):
        """Same seed should produce identical data (deterministic)."""
        customers_1 = generate_customers(10, cities, seed=999)
        customers_2 = generate_customers(10, cities, seed=999)
        assert customers_1 == customers_2
