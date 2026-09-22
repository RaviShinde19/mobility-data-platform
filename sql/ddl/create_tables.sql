-- ══════════════════════════════════════════════════════════════
-- Mobility Data Platform — DDL (Data Definition Language)
-- ══════════════════════════════════════════════════════════════
-- Phase 2: PostgreSQL Local Relational Store
--
-- This script creates all 4 tables with:
--   • Correct PostgreSQL types (mapped from Python dataclasses)
--   • PRIMARY KEY constraints (unique row identity)
--   • FOREIGN KEY constraints (referential integrity)
--   • CHECK constraints (data validation)
--   • NOT NULL constraints (mandatory fields)
--   • Indexes for common query patterns
--
-- DESIGN DECISIONS:
--   1. VARCHAR over TEXT — enforces max length, catches data issues
--   2. DECIMAL over FLOAT for money — no rounding errors
--   3. DECIMAL(10,6) for GPS coords — ~11cm precision
--   4. Strict CHECKs on fare/distance — catches bad source data
--   5. IF NOT EXISTS — safe to run multiple times (idempotent)
--
-- EXECUTION ORDER MATTERS:
--   customers, drivers → rides → payments
--   (because rides references customers/drivers,
--    payments references rides)
-- ══════════════════════════════════════════════════════════════


-- ── 1. Customers ────────────────────────────────────────────
-- Source: data/raw/customers/customers.csv
-- PII fields: first_name, last_name, email, phone (CONFIDENTIAL)

CREATE TABLE IF NOT EXISTS customers (
    customer_id     VARCHAR(10)     PRIMARY KEY,
    first_name      VARCHAR(100)    NOT NULL,
    last_name       VARCHAR(100)    NOT NULL,
    email           VARCHAR(255)    NOT NULL,
    phone           VARCHAR(20)     NOT NULL,
    city            VARCHAR(50)     NOT NULL,
    signup_date     DATE            NOT NULL,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,

    -- Prevent duplicate emails (same person registering twice)
    CONSTRAINT uq_customer_email UNIQUE (email)
);

-- Index for city-based queries (e.g., "rides in Mumbai")
CREATE INDEX IF NOT EXISTS idx_customers_city ON customers(city);


-- ── 2. Drivers ──────────────────────────────────────────────
-- Source: data/raw/drivers/drivers.csv
-- PII fields: first_name, last_name, phone, license_number (CONFIDENTIAL)

CREATE TABLE IF NOT EXISTS drivers (
    driver_id       VARCHAR(10)     PRIMARY KEY,
    first_name      VARCHAR(100)    NOT NULL,
    last_name       VARCHAR(100)    NOT NULL,
    phone           VARCHAR(20)     NOT NULL,
    city            VARCHAR(50)     NOT NULL,
    vehicle_type    VARCHAR(20)     NOT NULL,
    license_number  VARCHAR(30)     NOT NULL,
    rating          DECIMAL(3,1)    NOT NULL,
    join_date       DATE            NOT NULL,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,

    -- Rating must be between 1.0 and 5.0
    CONSTRAINT chk_driver_rating CHECK (rating >= 1.0 AND rating <= 5.0),

    -- Vehicle type must be one of our known types
    CONSTRAINT chk_vehicle_type CHECK (
        vehicle_type IN ('Sedan', 'Hatchback', 'SUV', 'Auto', 'Bike')
    ),

    -- License numbers should be unique
    CONSTRAINT uq_driver_license UNIQUE (license_number)
);

-- Index for city and vehicle type queries
CREATE INDEX IF NOT EXISTS idx_drivers_city ON drivers(city);
CREATE INDEX IF NOT EXISTS idx_drivers_vehicle_type ON drivers(vehicle_type);


-- ── 3. Rides ────────────────────────────────────────────────
-- Source: data/raw/rides/rides.csv
-- CORE transactional table — links customers to drivers
-- RESTRICTED fields: pickup_lat, pickup_lon, dropoff_lat, dropoff_lon

CREATE TABLE IF NOT EXISTS rides (
    ride_id             VARCHAR(10)     PRIMARY KEY,
    customer_id         VARCHAR(10)     NOT NULL,
    driver_id           VARCHAR(10)     NOT NULL,
    pickup_city         VARCHAR(50)     NOT NULL,
    pickup_area         VARCHAR(100)    NOT NULL,
    dropoff_city        VARCHAR(50)     NOT NULL,
    dropoff_area        VARCHAR(100)    NOT NULL,
    pickup_lat          DECIMAL(10,6)   NOT NULL,
    pickup_lon          DECIMAL(10,6)   NOT NULL,
    dropoff_lat         DECIMAL(10,6)   NOT NULL,
    dropoff_lon         DECIMAL(10,6)   NOT NULL,
    request_time        TIMESTAMP       NOT NULL,
    pickup_time         TIMESTAMP,              -- NULL if cancelled before pickup
    dropoff_time        TIMESTAMP,              -- NULL if not completed
    distance_km         DECIMAL(10,2)   NOT NULL,
    fare                DECIMAL(10,2)   NOT NULL,
    surge_multiplier    DECIMAL(4,2)    NOT NULL DEFAULT 1.0,
    ride_status         VARCHAR(20)     NOT NULL,

    -- Referential integrity: ride must reference REAL customer and driver
    CONSTRAINT fk_rides_customer FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id),
    CONSTRAINT fk_rides_driver FOREIGN KEY (driver_id)
        REFERENCES drivers(driver_id),

    -- Data validation: catch bad source data
    -- These will REJECT ~200 negative distances and ~104 zero fares
    CONSTRAINT chk_ride_distance CHECK (distance_km >= 0),
    CONSTRAINT chk_ride_fare CHECK (fare >= 0),
    CONSTRAINT chk_surge CHECK (surge_multiplier >= 1.0),

    -- Status must be one of our known values
    CONSTRAINT chk_ride_status CHECK (
        ride_status IN ('completed', 'cancelled', 'ongoing', 'no_show')
    )
);

-- Indexes for common analytical queries
CREATE INDEX IF NOT EXISTS idx_rides_customer ON rides(customer_id);
CREATE INDEX IF NOT EXISTS idx_rides_driver ON rides(driver_id);
CREATE INDEX IF NOT EXISTS idx_rides_pickup_city ON rides(pickup_city);
CREATE INDEX IF NOT EXISTS idx_rides_status ON rides(ride_status);
CREATE INDEX IF NOT EXISTS idx_rides_request_time ON rides(request_time);


-- ── 4. Payments ─────────────────────────────────────────────
-- Source: data/raw/payments/payments.csv
-- Links to rides — not every ride has a payment

CREATE TABLE IF NOT EXISTS payments (
    payment_id      VARCHAR(10)     PRIMARY KEY,
    ride_id         VARCHAR(10)     NOT NULL,
    customer_id     VARCHAR(10)     NOT NULL,
    amount          DECIMAL(10,2)   NOT NULL,
    payment_method  VARCHAR(20)     NOT NULL,
    payment_status  VARCHAR(20)     NOT NULL,
    payment_time    TIMESTAMP       NOT NULL,
    tip_amount      DECIMAL(10,2)   NOT NULL DEFAULT 0.00,

    -- Referential integrity
    CONSTRAINT fk_payments_ride FOREIGN KEY (ride_id)
        REFERENCES rides(ride_id),
    CONSTRAINT fk_payments_customer FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id),

    -- Data validation
    CONSTRAINT chk_payment_amount CHECK (amount >= 0),
    CONSTRAINT chk_tip_amount CHECK (tip_amount >= 0),

    -- Payment method must be known
    CONSTRAINT chk_payment_method CHECK (
        payment_method IN ('UPI', 'Credit Card', 'Debit Card', 'Cash', 'Wallet')
    ),

    -- Payment status must be known
    CONSTRAINT chk_payment_status CHECK (
        payment_status IN ('completed', 'failed', 'refunded', 'pending')
    )
);

-- Indexes for analytical queries
CREATE INDEX IF NOT EXISTS idx_payments_ride ON payments(ride_id);
CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_method ON payments(payment_method);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(payment_status);


-- ══════════════════════════════════════════════════════════════
-- Summary:
--   4 tables created
--   4 primary keys
--   4 foreign keys (rides→customers, rides→drivers,
--                   payments→rides, payments→customers)
--   8 CHECK constraints
--   2 UNIQUE constraints
--   13 indexes for query performance
-- ══════════════════════════════════════════════════════════════
