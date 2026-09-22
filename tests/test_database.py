"""
test_database.py — Phase 2 Integration Tests
═════════════════════════════════════════════

Tests that verify:
  1. Database connection works
  2. Tables exist with correct columns
  3. Row counts are reasonable
  4. Foreign key constraints are enforced
  5. CHECK constraints reject bad data
  6. RBAC roles have correct permissions
  7. Data integrity after loading

NOTE: These tests REQUIRE a running PostgreSQL container.
Run: docker compose -f docker/docker-compose.yml up -d
Then: pytest tests/test_database.py -v
"""

import pytest
import psycopg2

from src.database.connection import get_connection, test_connection
from src.database.schema import get_table_info
from src.database.loader import get_row_counts


# ── Skip all tests if PostgreSQL is not available ────────────
@pytest.fixture(scope="session", autouse=True)
def require_postgres():
    """Skip all tests in this module if PostgreSQL is not running."""
    if not test_connection():
        pytest.skip(
            "PostgreSQL is not running. Start it with:\n"
            "  docker compose -f docker/docker-compose.yml up -d",
            allow_module_level=True
        )


# ══════════════════════════════════════════════════════════════
# Connection Tests
# ══════════════════════════════════════════════════════════════

class TestConnection:
    """Test that database connectivity works."""

    def test_connection_works(self):
        """Can we connect and run a simple query?"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                result = cur.fetchone()
                assert result == (1,)

    def test_correct_database(self):
        """Are we connected to mobility_db?"""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database();")
                db_name = cur.fetchone()[0]
                assert db_name == "mobility_db"


# ══════════════════════════════════════════════════════════════
# Schema Tests
# ══════════════════════════════════════════════════════════════

class TestSchema:
    """Test that tables exist with correct structure."""

    def test_all_tables_exist(self):
        """All 4 tables should be present."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name;
                """)
                tables = [row[0] for row in cur.fetchall()]
                assert "customers" in tables
                assert "drivers" in tables
                assert "rides" in tables
                assert "payments" in tables

    def test_customers_columns(self):
        """Customers table should have correct columns."""
        info = get_table_info()
        assert "customers" in info
        columns = {c["column"] for c in info["customers"]}
        expected = {
            "customer_id", "first_name", "last_name", "email",
            "phone", "city", "signup_date", "is_active"
        }
        assert expected == columns

    def test_drivers_columns(self):
        """Drivers table should have correct columns."""
        info = get_table_info()
        assert "drivers" in info
        columns = {c["column"] for c in info["drivers"]}
        expected = {
            "driver_id", "first_name", "last_name", "phone",
            "city", "vehicle_type", "license_number", "rating",
            "join_date", "is_active"
        }
        assert expected == columns

    def test_rides_columns(self):
        """Rides table should have correct columns."""
        info = get_table_info()
        assert "rides" in info
        columns = {c["column"] for c in info["rides"]}
        expected = {
            "ride_id", "customer_id", "driver_id",
            "pickup_city", "pickup_area", "dropoff_city", "dropoff_area",
            "pickup_lat", "pickup_lon", "dropoff_lat", "dropoff_lon",
            "request_time", "pickup_time", "dropoff_time",
            "distance_km", "fare", "surge_multiplier", "ride_status"
        }
        assert expected == columns

    def test_payments_columns(self):
        """Payments table should have correct columns."""
        info = get_table_info()
        assert "payments" in info
        columns = {c["column"] for c in info["payments"]}
        expected = {
            "payment_id", "ride_id", "customer_id",
            "amount", "payment_method", "payment_status",
            "payment_time", "tip_amount"
        }
        assert expected == columns


# ══════════════════════════════════════════════════════════════
# Data Loading Tests
# ══════════════════════════════════════════════════════════════

class TestDataLoading:
    """Test that data was loaded correctly."""

    def test_customers_count(self):
        """Should have ~1000 customers (some rejected for duplicate emails)."""
        counts = get_row_counts()
        assert counts["customers"] >= 990, f"Too few customers: {counts['customers']}"
        assert counts["customers"] <= 1000, f"Too many customers: {counts['customers']}"

    def test_drivers_count(self):
        """Should have exactly 500 drivers (no rejections expected)."""
        counts = get_row_counts()
        assert counts["drivers"] == 500

    def test_rides_count_less_than_source(self):
        """Rides should be fewer than 10000 (bad data was rejected)."""
        counts = get_row_counts()
        assert counts["rides"] < 10000, "Some rides should have been rejected"
        assert counts["rides"] > 9000, "Most rides should have loaded"

    def test_payments_loaded(self):
        """Payments should have loaded (at least some)."""
        counts = get_row_counts()
        assert counts["payments"] > 0

    def test_no_negative_distances_in_db(self):
        """All rides in DB should have non-negative distance."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM rides WHERE distance_km < 0;")
                count = cur.fetchone()[0]
                assert count == 0, f"Found {count} rides with negative distance"

    def test_no_negative_fares_in_db(self):
        """All rides in DB should have non-negative fare."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM rides WHERE fare < 0;")
                count = cur.fetchone()[0]
                assert count == 0, f"Found {count} rides with negative fare"


# ══════════════════════════════════════════════════════════════
# Constraint Tests
# ══════════════════════════════════════════════════════════════

class TestConstraints:
    """Test that database constraints actually work."""

    def test_fk_rejects_invalid_customer(self):
        """Inserting a ride with non-existent customer should fail."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                with pytest.raises(psycopg2.errors.ForeignKeyViolation):
                    cur.execute("""
                        INSERT INTO rides (ride_id, customer_id, driver_id,
                            pickup_city, pickup_area, dropoff_city, dropoff_area,
                            pickup_lat, pickup_lon, dropoff_lat, dropoff_lon,
                            request_time, distance_km, fare, surge_multiplier,
                            ride_status)
                        VALUES ('RTEST1', 'C9999', 'D0001', 'Test', 'Test',
                            'Test', 'Test', 0, 0, 0, 0, NOW(),
                            10.0, 100.0, 1.0, 'completed');
                    """)

    def test_check_rejects_negative_fare(self):
        """Inserting a ride with negative fare should fail."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get a valid customer and driver ID first
                cur.execute("SELECT customer_id FROM customers LIMIT 1;")
                cid = cur.fetchone()[0]
                cur.execute("SELECT driver_id FROM drivers LIMIT 1;")
                did = cur.fetchone()[0]

                with pytest.raises(psycopg2.errors.CheckViolation):
                    cur.execute(f"""
                        INSERT INTO rides (ride_id, customer_id, driver_id,
                            pickup_city, pickup_area, dropoff_city, dropoff_area,
                            pickup_lat, pickup_lon, dropoff_lat, dropoff_lon,
                            request_time, distance_km, fare, surge_multiplier,
                            ride_status)
                        VALUES ('RTEST2', '{cid}', '{did}', 'Test', 'Test',
                            'Test', 'Test', 0, 0, 0, 0, NOW(),
                            10.0, -50.0, 1.0, 'completed');
                    """)

    def test_pk_rejects_duplicate(self):
        """Inserting a duplicate customer_id should fail."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT customer_id FROM customers LIMIT 1;")
                existing_id = cur.fetchone()[0]

                with pytest.raises(psycopg2.errors.UniqueViolation):
                    cur.execute(f"""
                        INSERT INTO customers (customer_id, first_name, last_name,
                            email, phone, city, signup_date, is_active)
                        VALUES ('{existing_id}', 'Test', 'User',
                            'unique_test@example.com', '+91 99999',
                            'Mumbai', '2026-01-01', true);
                    """)


# ══════════════════════════════════════════════════════════════
# Referential Integrity Tests
# ══════════════════════════════════════════════════════════════

class TestReferentialIntegrity:
    """Test that foreign key relationships are valid in loaded data."""

    def test_all_ride_customers_exist(self):
        """Every customer_id in rides must exist in customers."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM rides r
                    LEFT JOIN customers c ON r.customer_id = c.customer_id
                    WHERE c.customer_id IS NULL;
                """)
                orphan_count = cur.fetchone()[0]
                assert orphan_count == 0, f"{orphan_count} rides reference missing customers"

    def test_all_ride_drivers_exist(self):
        """Every driver_id in rides must exist in drivers."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM rides r
                    LEFT JOIN drivers d ON r.driver_id = d.driver_id
                    WHERE d.driver_id IS NULL;
                """)
                orphan_count = cur.fetchone()[0]
                assert orphan_count == 0, f"{orphan_count} rides reference missing drivers"

    def test_all_payment_rides_exist(self):
        """Every ride_id in payments must exist in rides."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM payments p
                    LEFT JOIN rides r ON p.ride_id = r.ride_id
                    WHERE r.ride_id IS NULL;
                """)
                orphan_count = cur.fetchone()[0]
                assert orphan_count == 0, f"{orphan_count} payments reference missing rides"


# ══════════════════════════════════════════════════════════════
# RBAC Tests
# ══════════════════════════════════════════════════════════════

class TestRBAC:
    """Test that RBAC roles have correct permissions."""

    def test_roles_exist(self):
        """All 3 roles should exist."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT rolname FROM pg_roles
                    WHERE rolname IN ('etl_writer', 'data_analyst', 'bi_reader')
                    ORDER BY rolname;
                """)
                roles = [row[0] for row in cur.fetchall()]
                assert "bi_reader" in roles
                assert "data_analyst" in roles
                assert "etl_writer" in roles

    def test_analyst_can_read(self):
        """data_analyst should be able to SELECT."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE data_analyst;")
                cur.execute("SELECT COUNT(*) FROM customers;")
                count = cur.fetchone()[0]
                assert count > 0

    def test_analyst_cannot_write(self):
        """data_analyst should NOT be able to INSERT."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE data_analyst;")
                with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                    cur.execute("""
                        INSERT INTO customers (customer_id, first_name, last_name,
                            email, phone, city, signup_date, is_active)
                        VALUES ('CRBAC', 'RBAC', 'Test',
                            'rbac@test.com', '+91 00000', 'Test', '2026-01-01', true);
                    """)

    def test_bi_reader_can_read_views(self):
        """bi_reader should be able to read aggregated views."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE bi_reader;")
                cur.execute("SELECT * FROM v_rides_by_city LIMIT 1;")
                result = cur.fetchone()
                assert result is not None

    def test_bi_reader_cannot_read_tables(self):
        """bi_reader should NOT be able to read base tables (PII protection)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE bi_reader;")
                with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                    cur.execute("SELECT * FROM customers LIMIT 1;")
