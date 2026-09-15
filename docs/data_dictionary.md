# Mobility Data Platform — Data Dictionary

This document serves as the central data catalog for the raw generated data (Bronze layer). It includes the data classification tags that drive our masking and security policies in the Silver and Gold layers.

## Data Classification Levels
- **PUBLIC**: No restriction. Passes through unchanged.
- **INTERNAL**: Internal business identifiers. Replaced with surrogate keys in Gold.
- **CONFIDENTIAL**: Personally Identifiable Information (PII). Must be masked/hashed in Silver. Dropped in Gold.
- **RESTRICTED**: Highly sensitive geospatial data. Obfuscated to H3 hex indices in Silver.

---

## 1. Customers Dataset
**Source File**: `customers.csv` / `customers.json`
**Description**: Registered users of the ride-hailing platform.

| Column | Type | Description | Example | Classification |
|--------|------|-------------|---------|----------------|
| `customer_id` | String | Unique platform identifier | C00142 | INTERNAL |
| `first_name` | String | User's first name | Rahul | CONFIDENTIAL |
| `last_name` | String | User's last name | Sharma | CONFIDENTIAL |
| `email` | String | Contact email address | rahul.s@example.com | CONFIDENTIAL |
| `phone` | String | Contact phone number | +919876543210 | CONFIDENTIAL |
| `city` | String | Registration city | Mumbai | PUBLIC |
| `signup_date` | Date | Date the account was created | 2024-01-15 | PUBLIC |
| `is_active` | Boolean | Account status | True | PUBLIC |

---

## 2. Drivers Dataset
**Source File**: `drivers.csv` / `drivers.json`
**Description**: Registered drivers/partners on the platform.

| Column | Type | Description | Example | Classification |
|--------|------|-------------|---------|----------------|
| `driver_id` | String | Unique platform identifier | D0042 | INTERNAL |
| `first_name` | String | Driver's first name | Amit | CONFIDENTIAL |
| `last_name` | String | Driver's last name | Singh | CONFIDENTIAL |
| `phone` | String | Contact phone number | +919123456789 | CONFIDENTIAL |
| `city` | String | Operating city | Mumbai | PUBLIC |
| `vehicle_type` | String | Type of vehicle | Sedan | PUBLIC |
| `license_number` | String | Driving license ID | MH0120100012345 | CONFIDENTIAL |
| `rating` | Float | Driver rating (1.0 to 5.0) | 4.8 | PUBLIC |
| `join_date` | Date | Date joined platform | 2023-11-20 | PUBLIC |
| `is_active` | Boolean | Account status | True | PUBLIC |

---

## 3. Rides Dataset
**Source File**: `rides.csv` / `rides.json`
**Description**: The core transactional entity linking customers to drivers.

| Column | Type | Description | Example | Classification |
|--------|------|-------------|---------|----------------|
| `ride_id` | String | Unique ride identifier | R054321 | INTERNAL |
| `customer_id` | String | FK to Customers | C00142 | INTERNAL |
| `driver_id` | String | FK to Drivers | D0042 | INTERNAL |
| `pickup_city` | String | City where ride started | Mumbai | PUBLIC |
| `pickup_area` | String | Neighborhood of pickup | Bandra | PUBLIC |
| `dropoff_city` | String | City where ride ended | Mumbai | PUBLIC |
| `dropoff_area` | String | Neighborhood of dropoff | Andheri | PUBLIC |
| `pickup_lat` | Float | Exact pickup latitude | 19.0543 | RESTRICTED |
| `pickup_lon` | Float | Exact pickup longitude | 72.8361 | RESTRICTED |
| `dropoff_lat` | Float | Exact dropoff latitude | 19.1136 | RESTRICTED |
| `dropoff_lon` | Float | Exact dropoff longitude | 72.8697 | RESTRICTED |
| `request_time` | Timestamp | Time ride was requested | 2026-09-15T08:30:00Z | PUBLIC |
| `pickup_time` | Timestamp | Time trip started (can be null) | 2026-09-15T08:35:00Z | PUBLIC |
| `dropoff_time` | Timestamp | Time trip ended (can be null) | 2026-09-15T09:10:00Z | PUBLIC |
| `distance_km` | Float | Trip distance | 12.5 | PUBLIC |
| `fare` | Float | Calculated fare amount | 450.0 | PUBLIC |
| `surge_multiplier` | Float | Surge pricing applied | 1.2 | PUBLIC |
| `ride_status` | String | completed/cancelled/ongoing/no_show | completed | PUBLIC |

---

## 4. Payments Dataset
**Source File**: `payments.csv` / `payments.json`
**Description**: Payment transactions for rides.

| Column | Type | Description | Example | Classification |
|--------|------|-------------|---------|----------------|
| `payment_id` | String | Unique payment identifier | P043210 | INTERNAL |
| `ride_id` | String | FK to Rides | R054321 | INTERNAL |
| `customer_id` | String | FK to Customers | C00142 | INTERNAL |
| `amount` | Float | Total payment amount | 450.0 | PUBLIC |
| `payment_method` | String | UPI/Card/Cash/Wallet | UPI | PUBLIC |
| `payment_status` | String | completed/failed/pending/refunded | completed | PUBLIC |
| `payment_time` | Timestamp | Time of transaction | 2026-09-15T09:12:00Z | PUBLIC |
| `tip_amount` | Float | Tip added to fare | 20.0 | PUBLIC |
