-- ══════════════════════════════════════════════════════════════
-- Mobility Data Platform — Sample Analytical Queries
-- ══════════════════════════════════════════════════════════════
-- Phase 2: Practice SQL queries that answer real business questions
--
-- These same queries will be run again in:
--   Phase 8 (Athena — over S3 data)
--   Phase 9 (Redshift — warehouse)
-- The SQL is nearly identical — learn once, apply everywhere.
-- ══════════════════════════════════════════════════════════════


-- ┌──────────────────────────────────────────────────────────┐
-- │ Query 1: Total rides per city                           │
-- │ Business question: "Which city has the most rides?"     │
-- │ SQL concepts: GROUP BY, COUNT, ORDER BY                 │
-- └──────────────────────────────────────────────────────────┘
SELECT
    pickup_city,
    COUNT(*)        AS total_rides,
    COUNT(CASE WHEN ride_status = 'completed' THEN 1 END) AS completed,
    COUNT(CASE WHEN ride_status = 'cancelled' THEN 1 END) AS cancelled
FROM rides
GROUP BY pickup_city
ORDER BY total_rides DESC;


-- ┌──────────────────────────────────────────────────────────┐
-- │ Query 2: Average fare by ride status                    │
-- │ Business question: "What do completed vs cancelled      │
-- │                     rides cost on average?"             │
-- │ SQL concepts: GROUP BY, AVG, ROUND                      │
-- └──────────────────────────────────────────────────────────┘
SELECT
    ride_status,
    COUNT(*)                            AS ride_count,
    ROUND(AVG(fare)::numeric, 2)        AS avg_fare,
    ROUND(MIN(fare)::numeric, 2)        AS min_fare,
    ROUND(MAX(fare)::numeric, 2)        AS max_fare
FROM rides
GROUP BY ride_status
ORDER BY ride_count DESC;


-- ┌──────────────────────────────────────────────────────────┐
-- │ Query 3: Peak demand hours                              │
-- │ Business question: "What time of day has most rides?"   │
-- │ SQL concepts: EXTRACT, aggregate functions               │
-- └──────────────────────────────────────────────────────────┘
SELECT
    EXTRACT(HOUR FROM request_time)::int  AS hour_of_day,
    COUNT(*)                              AS total_rides,
    ROUND(AVG(fare)::numeric, 2)          AS avg_fare,
    ROUND(AVG(surge_multiplier)::numeric, 2) AS avg_surge
FROM rides
GROUP BY EXTRACT(HOUR FROM request_time)
ORDER BY hour_of_day;


-- ┌──────────────────────────────────────────────────────────┐
-- │ Query 4: Revenue by payment method                      │
-- │ Business question: "How much revenue does UPI vs        │
-- │                     Credit Card generate?"              │
-- │ SQL concepts: SUM, GROUP BY, percentage calculation      │
-- └──────────────────────────────────────────────────────────┘
SELECT
    payment_method,
    COUNT(*)                            AS total_txns,
    ROUND(SUM(amount)::numeric, 2)      AS total_revenue,
    ROUND(AVG(amount)::numeric, 2)      AS avg_amount,
    ROUND(SUM(tip_amount)::numeric, 2)  AS total_tips,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER(),
        1
    )                                   AS pct_of_total
FROM payments
WHERE payment_status = 'completed'
GROUP BY payment_method
ORDER BY total_revenue DESC;


-- ┌──────────────────────────────────────────────────────────┐
-- │ Query 5: Top 10 drivers by completed rides              │
-- │ Business question: "Who are our most active drivers?"   │
-- │ SQL concepts: JOIN, COUNT, ORDER BY, LIMIT               │
-- └──────────────────────────────────────────────────────────┘
SELECT
    d.driver_id,
    d.first_name || ' ' || d.last_name  AS driver_name,
    d.vehicle_type,
    d.city,
    d.rating,
    COUNT(r.ride_id)                    AS completed_rides,
    ROUND(SUM(r.fare)::numeric, 2)      AS total_earnings
FROM drivers d
JOIN rides r ON d.driver_id = r.driver_id
WHERE r.ride_status = 'completed'
GROUP BY d.driver_id, d.first_name, d.last_name,
         d.vehicle_type, d.city, d.rating
ORDER BY completed_rides DESC
LIMIT 10;


-- ┌──────────────────────────────────────────────────────────┐
-- │ Query 6: Cancellation rate by city                      │
-- │ Business question: "Which city has the worst            │
-- │                     cancellation problem?"              │
-- │ SQL concepts: CASE WHEN, calculated fields               │
-- └──────────────────────────────────────────────────────────┘
SELECT
    pickup_city,
    COUNT(*)                            AS total_rides,
    COUNT(CASE WHEN ride_status = 'cancelled' THEN 1 END) AS cancellations,
    ROUND(
        100.0 * COUNT(CASE WHEN ride_status = 'cancelled' THEN 1 END) / COUNT(*),
        1
    )                                   AS cancellation_rate_pct
FROM rides
GROUP BY pickup_city
ORDER BY cancellation_rate_pct DESC;


-- ┌──────────────────────────────────────────────────────────┐
-- │ Query 7: Monthly ride trend                             │
-- │ Business question: "Are rides growing month over month?"│
-- │ SQL concepts: DATE_TRUNC, time series analysis           │
-- └──────────────────────────────────────────────────────────┘
SELECT
    DATE_TRUNC('month', request_time)::date  AS month,
    COUNT(*)                                 AS total_rides,
    COUNT(CASE WHEN ride_status = 'completed' THEN 1 END) AS completed,
    ROUND(SUM(fare)::numeric, 2)             AS total_revenue
FROM rides
GROUP BY DATE_TRUNC('month', request_time)
ORDER BY month;


-- ┌──────────────────────────────────────────────────────────┐
-- │ Query 8: Average trip distance (completed rides)        │
-- │ Business question: "How far do people typically travel?"│
-- │ SQL concepts: AVG with WHERE filter, percentiles         │
-- └──────────────────────────────────────────────────────────┘
SELECT
    pickup_city,
    COUNT(*)                                    AS completed_rides,
    ROUND(AVG(distance_km)::numeric, 2)         AS avg_distance_km,
    ROUND(MIN(distance_km)::numeric, 2)         AS min_distance_km,
    ROUND(MAX(distance_km)::numeric, 2)         AS max_distance_km,
    ROUND(
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY distance_km)::numeric,
        2
    )                                           AS median_distance_km
FROM rides
WHERE ride_status = 'completed'
  AND distance_km > 0
GROUP BY pickup_city
ORDER BY avg_distance_km DESC;


-- ┌──────────────────────────────────────────────────────────┐
-- │ Query 9: Customers with most rides                      │
-- │ Business question: "Who are our power users?"           │
-- │ SQL concepts: JOIN, COUNT, aggregate, LIMIT              │
-- └──────────────────────────────────────────────────────────┘
SELECT
    c.customer_id,
    c.first_name || ' ' || c.last_name  AS customer_name,
    c.city,
    c.is_active,
    COUNT(r.ride_id)                    AS total_rides,
    COUNT(CASE WHEN r.ride_status = 'completed' THEN 1 END) AS completed_rides,
    ROUND(SUM(r.fare)::numeric, 2)      AS total_spent
FROM customers c
JOIN rides r ON c.customer_id = r.customer_id
GROUP BY c.customer_id, c.first_name, c.last_name, c.city, c.is_active
ORDER BY total_rides DESC
LIMIT 10;


-- ┌──────────────────────────────────────────────────────────┐
-- │ Query 10: Payment success rate                          │
-- │ Business question: "What % of payments succeed?"        │
-- │ SQL concepts: CASE WHEN, percentage, sub-grouping        │
-- └──────────────────────────────────────────────────────────┘
SELECT
    payment_method,
    COUNT(*)                            AS total_txns,
    COUNT(CASE WHEN payment_status = 'completed' THEN 1 END) AS successful,
    COUNT(CASE WHEN payment_status = 'failed' THEN 1 END)    AS failed,
    COUNT(CASE WHEN payment_status = 'refunded' THEN 1 END)  AS refunded,
    COUNT(CASE WHEN payment_status = 'pending' THEN 1 END)   AS pending,
    ROUND(
        100.0 * COUNT(CASE WHEN payment_status = 'completed' THEN 1 END) / COUNT(*),
        1
    )                                   AS success_rate_pct
FROM payments
GROUP BY payment_method
ORDER BY success_rate_pct DESC;
