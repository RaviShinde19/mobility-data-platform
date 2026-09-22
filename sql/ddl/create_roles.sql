-- ══════════════════════════════════════════════════════════════
-- Mobility Data Platform — RBAC Role Definitions
-- ══════════════════════════════════════════════════════════════
-- Phase 2: Database-Level Access Control
--
-- Three roles with scoped permissions (AGENTS.md Rule 5):
--   etl_writer   → Full CRUD on all tables (pipeline use)
--   data_analyst → Read-only on all tables (analytical queries)
--   bi_reader    → Read-only on aggregated views (dashboard use)
--
-- This same pattern transfers directly to Redshift (Phase 9).
-- ══════════════════════════════════════════════════════════════


-- ── Drop existing roles if re-running (idempotent) ──────────
-- We use DO blocks because DROP ROLE IF EXISTS doesn't handle
-- roles that own objects well. This approach is safer.
DO $$
BEGIN
    -- Revoke all privileges first to avoid dependency errors
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bi_reader') THEN
        EXECUTE 'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM bi_reader';
        DROP ROLE bi_reader;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'data_analyst') THEN
        EXECUTE 'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM data_analyst';
        DROP ROLE data_analyst;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etl_writer') THEN
        EXECUTE 'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM etl_writer';
        DROP ROLE etl_writer;
    END IF;
END
$$;


-- ── 1. ETL Writer ───────────────────────────────────────────
-- Used by: Data pipeline scripts (loader.py, future ETL jobs)
-- Can: Read, write, update, delete all tables
-- Why: Pipeline needs full access to load and transform data

CREATE ROLE etl_writer WITH LOGIN PASSWORD 'etl_writer_2026';

GRANT CONNECT ON DATABASE mobility_db TO etl_writer;
GRANT USAGE ON SCHEMA public TO etl_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO etl_writer;

-- Also grant on future tables (so new tables get permissions automatically)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO etl_writer;


-- ── 2. Data Analyst ─────────────────────────────────────────
-- Used by: Analysts running ad-hoc queries
-- Can: Read all tables (SELECT only)
-- Cannot: INSERT, UPDATE, DELETE, DROP, CREATE
-- Why: Analysts explore data but should never modify it

CREATE ROLE data_analyst WITH LOGIN PASSWORD 'analyst_readonly_2026';

GRANT CONNECT ON DATABASE mobility_db TO data_analyst;
GRANT USAGE ON SCHEMA public TO data_analyst;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO data_analyst;

-- Also grant on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO data_analyst;


-- ── 3. BI Reader ────────────────────────────────────────────
-- Used by: BI tools (Power BI, Tableau) connecting to the database
-- Can: Read from specific views only (aggregated data)
-- Cannot: See raw tables with PII data
-- Why: Dashboards should only see aggregated metrics, not raw PII

CREATE ROLE bi_reader WITH LOGIN PASSWORD 'bi_reader_2026';

GRANT CONNECT ON DATABASE mobility_db TO bi_reader;
GRANT USAGE ON SCHEMA public TO bi_reader;

-- bi_reader gets NO table access initially.
-- Access will be granted only on specific aggregated VIEWS:

-- ── Aggregated views for BI ─────────────────────────────────
-- These views expose ONLY aggregate metrics — no PII leaks

CREATE OR REPLACE VIEW v_rides_by_city AS
SELECT
    pickup_city,
    ride_status,
    COUNT(*)                            AS total_rides,
    ROUND(AVG(fare)::numeric, 2)        AS avg_fare,
    ROUND(AVG(distance_km)::numeric, 2) AS avg_distance,
    ROUND(AVG(surge_multiplier)::numeric, 2) AS avg_surge
FROM rides
GROUP BY pickup_city, ride_status;

CREATE OR REPLACE VIEW v_revenue_by_method AS
SELECT
    payment_method,
    payment_status,
    COUNT(*)                            AS total_payments,
    ROUND(SUM(amount)::numeric, 2)      AS total_revenue,
    ROUND(AVG(amount)::numeric, 2)      AS avg_payment,
    ROUND(SUM(tip_amount)::numeric, 2)  AS total_tips
FROM payments
GROUP BY payment_method, payment_status;

CREATE OR REPLACE VIEW v_driver_performance AS
SELECT
    d.vehicle_type,
    d.city,
    COUNT(r.ride_id)                        AS total_rides,
    ROUND(AVG(r.fare)::numeric, 2)          AS avg_fare,
    ROUND(AVG(r.distance_km)::numeric, 2)   AS avg_distance
FROM drivers d
LEFT JOIN rides r ON d.driver_id = r.driver_id
GROUP BY d.vehicle_type, d.city;

CREATE OR REPLACE VIEW v_hourly_demand AS
SELECT
    EXTRACT(HOUR FROM request_time)::int    AS hour_of_day,
    pickup_city,
    COUNT(*)                                AS total_rides,
    ROUND(AVG(fare)::numeric, 2)            AS avg_fare
FROM rides
GROUP BY EXTRACT(HOUR FROM request_time), pickup_city
ORDER BY hour_of_day;

-- Grant BI reader access to views only (not base tables)
GRANT SELECT ON v_rides_by_city TO bi_reader;
GRANT SELECT ON v_revenue_by_method TO bi_reader;
GRANT SELECT ON v_driver_performance TO bi_reader;
GRANT SELECT ON v_hourly_demand TO bi_reader;


-- ══════════════════════════════════════════════════════════════
-- Summary:
--   3 roles created:
--     etl_writer   → SELECT, INSERT, UPDATE, DELETE on all tables
--     data_analyst → SELECT on all tables
--     bi_reader    → SELECT on 4 aggregated views only
--   4 aggregated views created (no PII exposed)
-- ══════════════════════════════════════════════════════════════
