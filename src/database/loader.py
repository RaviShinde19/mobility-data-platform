"""
loader.py — CSV → PostgreSQL Bulk Data Loader
═══════════════════════════════════════════════

WHY THIS EXISTS:
────────────────
Loads CSV files from data/raw/ into PostgreSQL tables using a
staging pattern. This is the bridge between Phase 1 (CSV files)
and Phase 2 (relational database).

DESIGN DECISIONS:
─────────────────
1. STAGING PATTERN — not direct COPY
   PostgreSQL's COPY command is all-or-nothing: if ONE row
   violates a constraint, the ENTIRE file fails. We can't
   just skip bad rows.

   Solution:
     Step 1: COPY csv → staging_table (no constraints)
     Step 2: INSERT INTO final_table
             SELECT * FROM staging_table
             WHERE [all constraints pass]
     Step 3: Log how many rows were rejected and why
     Step 4: DROP staging_table

   This is a standard ETL pattern used in:
     - Phase 6 (Data Quality → quarantine)
     - Phase 9 (Redshift COPY with manifest)
     - Every production data pipeline

2. LOADING ORDER matters (DAG):
     customers → (no deps)
     drivers   → (no deps)
     rides     → (needs customers + drivers for FK)
     payments  → (needs rides for FK)

3. TRUNCATE before load (idempotent)
   Running the loader twice doesn't create duplicates.

4. COPY via psycopg2's copy_expert()
   Uses PostgreSQL's COPY protocol (fast binary transfer)
   instead of row-by-row INSERT.
"""

import os
import csv
from io import StringIO
from dataclasses import dataclass

from src.database.connection import get_connection
from src.utils.logger import setup_logger

# Default data directory
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'raw')


@dataclass
class LoadResult:
    """Result of loading one table."""
    table_name: str
    rows_staged: int      # Rows in staging (from CSV)
    rows_loaded: int      # Rows that passed validation
    rows_rejected: int    # Rows that failed validation
    rejection_reasons: dict  # Reason → count


def load_all_tables(data_dir: str = None) -> dict:
    """
    Load all 4 CSV files into PostgreSQL tables.

    Loads in dependency order:
      1. customers (no FK deps)
      2. drivers   (no FK deps)
      3. rides     (FK → customers, drivers)
      4. payments  (FK → rides, customers)

    Args:
        data_dir: Path to data/raw/ directory.

    Returns:
        dict with per-table load results and summary.
    """
    logger = setup_logger("database.loader")

    if data_dir is None:
        data_dir = DATA_DIR

    logger.info(f"Starting data load from: {data_dir}")

    results = {}

    # ── Load order matters (DAG) ─────────────────────────────
    load_sequence = [
        {
            "table": "customers",
            "csv_file": os.path.join(data_dir, "customers", "customers.csv"),
            "columns": [
                "customer_id", "first_name", "last_name", "email",
                "phone", "city", "signup_date", "is_active"
            ],
            "staging_ddl": """
                CREATE TEMP TABLE staging_customers (
                    customer_id     VARCHAR(10),
                    first_name      VARCHAR(100),
                    last_name       VARCHAR(100),
                    email           VARCHAR(255),
                    phone           VARCHAR(20),
                    city            VARCHAR(50),
                    signup_date     DATE,
                    is_active       VARCHAR(10)
                )
            """,
            "insert_sql": """
                INSERT INTO customers (customer_id, first_name, last_name,
                    email, phone, city, signup_date, is_active)
                SELECT DISTINCT ON (email)
                    customer_id, first_name, last_name,
                    email, phone, city, signup_date,
                    CASE WHEN is_active = 'True' THEN TRUE ELSE FALSE END
                FROM staging_customers s
                WHERE s.customer_id IS NOT NULL
                  AND s.email IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM customers c
                      WHERE c.customer_id = s.customer_id
                  )
                ORDER BY email, customer_id
            """,
            "reject_checks": {
                "duplicate_email": "email IN (SELECT email FROM staging_customers GROUP BY email HAVING COUNT(*) > 1)"
            }
        },
        {
            "table": "drivers",
            "csv_file": os.path.join(data_dir, "drivers", "drivers.csv"),
            "columns": [
                "driver_id", "first_name", "last_name", "phone",
                "city", "vehicle_type", "license_number", "rating",
                "join_date", "is_active"
            ],
            "staging_ddl": """
                CREATE TEMP TABLE staging_drivers (
                    driver_id       VARCHAR(10),
                    first_name      VARCHAR(100),
                    last_name       VARCHAR(100),
                    phone           VARCHAR(20),
                    city            VARCHAR(50),
                    vehicle_type    VARCHAR(20),
                    license_number  VARCHAR(30),
                    rating          DECIMAL(3,1),
                    join_date       DATE,
                    is_active       VARCHAR(10)
                )
            """,
            "insert_sql": """
                INSERT INTO drivers (driver_id, first_name, last_name,
                    phone, city, vehicle_type, license_number, rating,
                    join_date, is_active)
                SELECT DISTINCT ON (license_number)
                    driver_id, first_name, last_name,
                    phone, city, vehicle_type, license_number, rating,
                    join_date,
                    CASE WHEN is_active = 'True' THEN TRUE ELSE FALSE END
                FROM staging_drivers s
                WHERE s.driver_id IS NOT NULL
                  AND s.vehicle_type IN ('Sedan', 'Hatchback', 'SUV', 'Auto', 'Bike')
                  AND s.rating >= 1.0 AND s.rating <= 5.0
                  AND NOT EXISTS (
                      SELECT 1 FROM drivers d
                      WHERE d.driver_id = s.driver_id
                  )
                ORDER BY license_number, driver_id
            """,
            "reject_checks": {
                "invalid_vehicle_type": "vehicle_type NOT IN ('Sedan', 'Hatchback', 'SUV', 'Auto', 'Bike')",
                "invalid_rating": "rating < 1.0 OR rating > 5.0",
                "duplicate_license": "license_number IN (SELECT license_number FROM staging_drivers GROUP BY license_number HAVING COUNT(*) > 1)"
            }
        },
        {
            "table": "rides",
            "csv_file": os.path.join(data_dir, "rides", "rides.csv"),
            "columns": [
                "ride_id", "customer_id", "driver_id",
                "pickup_city", "pickup_area", "dropoff_city", "dropoff_area",
                "pickup_lat", "pickup_lon", "dropoff_lat", "dropoff_lon",
                "request_time", "pickup_time", "dropoff_time",
                "distance_km", "fare", "surge_multiplier", "ride_status"
            ],
            "staging_ddl": """
                CREATE TEMP TABLE staging_rides (
                    ride_id             VARCHAR(10),
                    customer_id         VARCHAR(10),
                    driver_id           VARCHAR(10),
                    pickup_city         VARCHAR(50),
                    pickup_area         VARCHAR(100),
                    dropoff_city        VARCHAR(50),
                    dropoff_area        VARCHAR(100),
                    pickup_lat          DECIMAL(10,6),
                    pickup_lon          DECIMAL(10,6),
                    dropoff_lat         DECIMAL(10,6),
                    dropoff_lon         DECIMAL(10,6),
                    request_time        TIMESTAMP,
                    pickup_time         TIMESTAMP,
                    dropoff_time        TIMESTAMP,
                    distance_km         DECIMAL(10,2),
                    fare                DECIMAL(10,2),
                    surge_multiplier    DECIMAL(4,2),
                    ride_status         VARCHAR(20)
                )
            """,
            "insert_sql": """
                INSERT INTO rides (ride_id, customer_id, driver_id,
                    pickup_city, pickup_area, dropoff_city, dropoff_area,
                    pickup_lat, pickup_lon, dropoff_lat, dropoff_lon,
                    request_time, pickup_time, dropoff_time,
                    distance_km, fare, surge_multiplier, ride_status)
                SELECT ride_id, customer_id, driver_id,
                    pickup_city, pickup_area, dropoff_city, dropoff_area,
                    pickup_lat, pickup_lon, dropoff_lat, dropoff_lon,
                    request_time, pickup_time, dropoff_time,
                    distance_km, fare, surge_multiplier, ride_status
                FROM staging_rides s
                WHERE s.ride_id IS NOT NULL
                  AND s.distance_km >= 0
                  AND s.fare >= 0
                  AND s.surge_multiplier >= 1.0
                  AND s.ride_status IN ('completed', 'cancelled', 'ongoing', 'no_show')
                  AND EXISTS (
                      SELECT 1 FROM customers c
                      WHERE c.customer_id = s.customer_id
                  )
                  AND EXISTS (
                      SELECT 1 FROM drivers d
                      WHERE d.driver_id = s.driver_id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM rides r
                      WHERE r.ride_id = s.ride_id
                  )
            """,
            "reject_checks": {
                "negative_distance": "distance_km < 0",
                "negative_fare": "fare < 0",
                "zero_fare": "fare = 0 AND ride_status = 'completed'",
                "invalid_surge": "surge_multiplier < 1.0",
                "invalid_status": "ride_status NOT IN ('completed', 'cancelled', 'ongoing', 'no_show')",
                "orphan_customer": "customer_id NOT IN (SELECT customer_id FROM customers)",
                "orphan_driver": "driver_id NOT IN (SELECT driver_id FROM drivers)",
            }
        },
        {
            "table": "payments",
            "csv_file": os.path.join(data_dir, "payments", "payments.csv"),
            "columns": [
                "payment_id", "ride_id", "customer_id",
                "amount", "payment_method", "payment_status",
                "payment_time", "tip_amount"
            ],
            "staging_ddl": """
                CREATE TEMP TABLE staging_payments (
                    payment_id      VARCHAR(10),
                    ride_id         VARCHAR(10),
                    customer_id     VARCHAR(10),
                    amount          DECIMAL(10,2),
                    payment_method  VARCHAR(20),
                    payment_status  VARCHAR(20),
                    payment_time    TIMESTAMP,
                    tip_amount      DECIMAL(10,2)
                )
            """,
            "insert_sql": """
                INSERT INTO payments (payment_id, ride_id, customer_id,
                    amount, payment_method, payment_status,
                    payment_time, tip_amount)
                SELECT payment_id, ride_id, customer_id,
                    amount, payment_method, payment_status,
                    payment_time, tip_amount
                FROM staging_payments s
                WHERE s.payment_id IS NOT NULL
                  AND s.amount >= 0
                  AND s.tip_amount >= 0
                  AND s.payment_method IN ('UPI', 'Credit Card', 'Debit Card', 'Cash', 'Wallet')
                  AND s.payment_status IN ('completed', 'failed', 'refunded', 'pending')
                  AND EXISTS (
                      SELECT 1 FROM rides r
                      WHERE r.ride_id = s.ride_id
                  )
                  AND EXISTS (
                      SELECT 1 FROM customers c
                      WHERE c.customer_id = s.customer_id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM payments p
                      WHERE p.payment_id = s.payment_id
                  )
            """,
            "reject_checks": {
                "negative_amount": "amount < 0",
                "negative_tip": "tip_amount < 0",
                "invalid_method": "payment_method NOT IN ('UPI', 'Credit Card', 'Debit Card', 'Cash', 'Wallet')",
                "invalid_status": "payment_status NOT IN ('completed', 'failed', 'refunded', 'pending')",
                "orphan_ride": "ride_id NOT IN (SELECT ride_id FROM rides)",
                "orphan_customer": "customer_id NOT IN (SELECT customer_id FROM customers)",
            }
        },
    ]

    for spec in load_sequence:
        result = _load_table(spec, logger)
        results[spec["table"]] = result

    # Summary
    total_loaded = sum(r.rows_loaded for r in results.values())
    total_rejected = sum(r.rows_rejected for r in results.values())

    logger.info("=" * 60)
    logger.info("DATA LOAD COMPLETE")
    logger.info("=" * 60)
    for table_name, result in results.items():
        logger.info(
            f"  {table_name:12s}: {result.rows_loaded:,} loaded, "
            f"{result.rows_rejected:,} rejected "
            f"(of {result.rows_staged:,} staged)"
        )
        for reason, count in result.rejection_reasons.items():
            if count > 0:
                logger.info(f"    └─ {reason}: {count:,}")
    logger.info(f"  {'TOTAL':12s}: {total_loaded:,} loaded, {total_rejected:,} rejected")
    logger.info("=" * 60)

    return {
        "results": {k: {
            "staged": v.rows_staged,
            "loaded": v.rows_loaded,
            "rejected": v.rows_rejected,
            "reasons": v.rejection_reasons,
        } for k, v in results.items()},
        "total_loaded": total_loaded,
        "total_rejected": total_rejected,
    }


def _load_table(spec: dict, logger) -> LoadResult:
    """
    Load a single CSV file into its target table using staging pattern.

    Steps:
      1. Create temp staging table (no constraints)
      2. COPY CSV data into staging table
      3. Count rejection reasons (for reporting)
      4. INSERT valid rows from staging → final table
      5. Drop staging table
    """
    table_name = spec["table"]
    csv_file = spec["csv_file"]
    staging_table = f"staging_{table_name}"

    logger.info(f"Loading {table_name} from {csv_file}")

    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Step 1: Create staging table
            cur.execute(f"DROP TABLE IF EXISTS {staging_table};")
            cur.execute(spec["staging_ddl"])
            logger.debug(f"  Created staging table: {staging_table}")

            # Step 2: COPY CSV into staging table
            # Read CSV and use copy_expert for fast bulk loading
            with open(csv_file, 'r', encoding='utf-8') as f:
                # Skip header — we use the HEADER option in COPY
                copy_sql = f"""
                    COPY {staging_table} ({', '.join(spec['columns'])})
                    FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')
                """
                cur.copy_expert(copy_sql, f)

            # Count staged rows
            cur.execute(f"SELECT COUNT(*) FROM {staging_table};")
            rows_staged = cur.fetchone()[0]
            logger.info(f"  Staged {rows_staged:,} rows into {staging_table}")

            # Step 3: Count rejection reasons BEFORE inserting
            rejection_reasons = {}
            for reason_name, condition in spec.get("reject_checks", {}).items():
                cur.execute(f"SELECT COUNT(*) FROM {staging_table} WHERE {condition};")
                count = cur.fetchone()[0]
                if count > 0:
                    rejection_reasons[reason_name] = count
                    logger.info(f"  ⚠ {reason_name}: {count:,} rows will be rejected")

            # Step 4: Truncate target table (idempotent — no duplicates on re-run)
            cur.execute(f"TRUNCATE TABLE {table_name} CASCADE;")

            # Step 5: INSERT valid rows from staging → final table
            cur.execute(spec["insert_sql"])
            rows_loaded = cur.rowcount
            rows_rejected = rows_staged - rows_loaded

            logger.info(
                f"  ✓ {table_name}: {rows_loaded:,} loaded, "
                f"{rows_rejected:,} rejected"
            )

            # Step 6: Drop staging table (cleanup)
            cur.execute(f"DROP TABLE IF EXISTS {staging_table};")

        # Commit the entire transaction
        conn.commit()
        logger.info(f"  ✓ {table_name}: committed")

    return LoadResult(
        table_name=table_name,
        rows_staged=rows_staged,
        rows_loaded=rows_loaded,
        rows_rejected=rows_rejected,
        rejection_reasons=rejection_reasons,
    )


def get_row_counts() -> dict:
    """Get row counts for all tables. Useful for verification."""
    tables = ["customers", "drivers", "rides", "payments"]
    counts = {}

    with get_connection() as conn:
        with conn.cursor() as cur:
            for table in tables:
                cur.execute(f"SELECT COUNT(*) FROM {table};")
                counts[table] = cur.fetchone()[0]

    return counts
