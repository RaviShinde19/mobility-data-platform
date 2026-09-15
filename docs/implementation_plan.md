# Real-Time Mobility Data Platform — Phased Implementation Plan

This project will be built in **11 phases**, each introducing new concepts and technologies. You'll learn by building — each phase produces working code that builds on the previous one.

**Cross-cutting principles** embedded into every phase:
- **Data Governance**: Classification, lineage, cataloging, schema enforcement
- **Data Security**: Encryption, access control, PII masking, least privilege
- **Reliability**: Pipeline idempotency, error recovery, testing
- **Operational Readiness**: Monitoring, alerting, runbooks, cost awareness

---

## Phase Overview

| Phase | Title | Key Technologies | What You Learn |
|-------|-------|-----------------|----------------|
| 1 | **Project Setup & Data Generation** | Python, Faker, CSV/JSON | Project structure, synthetic data generation, configuration management, data classification |
| 2 | **PostgreSQL — Local Relational Store** | Python, PostgreSQL, psycopg2, Docker | Relational modeling, SQL DDL, Python-DB interaction, Docker basics, database RBAC |
| 3 | **Amazon S3 — Bronze Layer Ingestion** | Python, boto3, S3, IAM | Cloud storage, raw data landing, S3 security, IAM least privilege, encryption |
| 4 | **PySpark — Local Transformations (Bronze → Silver)** | PySpark, Parquet | Spark DataFrames, cleaning, deduplication, PII masking, geospatial obfuscation, Spark tuning |
| 5 | **PySpark — Silver → Gold (Dimensional Modeling)** | PySpark, Star Schema | Fact/dimension tables, surrogate keys, broadcast joins, partition strategy |
| 6 | **Data Quality & Error Handling** | Python, PySpark, Great Expectations | Validation rules, quarantine zone, reprocessing, data assertion suites, quality alerting |
| 7 | **AWS Glue — Managed Cloud ETL** | AWS Glue, Glue Catalog, PySpark | Managed Spark, crawlers, data catalog, incremental processing, job bookmarks |
| 8 | **Amazon Athena — Query the Lake** | Athena, SQL, Glue Catalog | Serverless SQL over S3, ad-hoc analytics, partition pruning, cost optimization |
| 9 | **Amazon Redshift — Data Warehouse** | Redshift Serverless, SQL, COPY | Warehouse loading, distribution/sort keys, RBAC, analytical SQL |
| 10 | **Apache Airflow — Pipeline Orchestration** | Airflow, Docker Compose, DAGs | Workflow orchestration, alerting, backfill strategy, idempotent DAGs |
| 11 | **Power BI — Dashboards & Visualization** | Power BI, DAX | KPI dashboards, operational analytics, data storytelling |

---

## Phase 1: Project Setup & Data Generation

### Goal
Set up the project structure and build a synthetic data generator that creates realistic mobility data (customers, drivers, rides, payments) in CSV and JSON formats.

### What You'll Learn
- How to structure a data engineering project
- How to generate realistic test data with Python's `Faker` library
- Configuration management with YAML
- Logging best practices
- Working with CSV and JSON formats
- **Data classification — understanding which fields are PII, confidential, or public**

### Files to Create

#### [NEW] Project Structure
```
mobility-platform/
├── config/
│   └── config.yaml              # All configurable parameters
├── src/
│   ├── __init__.py
│   ├── data_generator/
│   │   ├── __init__.py
│   │   ├── generator.py         # Main data generation orchestrator
│   │   ├── customers.py         # Customer data generator
│   │   ├── drivers.py           # Driver data generator
│   │   ├── rides.py             # Rides data generator
│   │   └── payments.py          # Payments data generator
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py            # Logging setup
│   │   └── config_loader.py     # YAML config loader
│   └── models/
│       ├── __init__.py
│       └── schemas.py           # Data schemas / field definitions
├── data/
│   └── raw/                     # Generated data lands here
│       ├── customers/
│       ├── drivers/
│       ├── rides/
│       └── payments/
├── logs/
├── tests/
│   └── test_data_generator.py
├── docs/
│   └── data_dictionary.md       # Column-level documentation with PII classification
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

#### Key Design Decisions
- **Referential integrity in generated data**: Rides reference valid customer_ids and driver_ids. Payments reference valid ride_ids.
- **Realistic distributions**: Not all rides are completed — some are cancelled. Not all payments succeed.
- **Configurable volume**: Generate 100 records for testing or 100,000 for load testing via config.
- **Indian cities focus**: Pune, Mumbai, Bangalore, Delhi, Hyderabad, Chennai — to match a realistic ride-hailing context.

### Data Governance Tasks (Phase 1)

#### [NEW] Data Classification Matrix
Tag every field in the schema with a sensitivity classification. This drives all downstream masking and access control decisions:

| Classification | Meaning | Example Fields | What Happens in Silver/Gold |
|---------------|---------|----------------|---------------------------|
| **PUBLIC** | No restriction | city, vehicle_type, ride_status | Passes through unchanged |
| **INTERNAL** | Internal use only | customer_id, driver_id, ride_id | Replaced with surrogate keys in Gold |
| **CONFIDENTIAL** | PII — must be masked | first_name, last_name, email, phone | Hashed/masked in Silver, removed in Gold |
| **RESTRICTED** | Sensitive location data | pickup_lat, pickup_lon, dropoff_lat, dropoff_lon | Obfuscated to H3 hex index in Silver |

Add this classification as metadata in `schemas.py` — it will be used by the masking logic in Phase 4.

#### [NEW] Data Dictionary
Create `docs/data_dictionary.md` documenting every column across all 4 datasets with: column name, data type, description, example value, PII classification, and source.

#### [NEW] Architecture Diagram
Add a Mermaid architecture diagram to `README.md` showing the complete V1 pipeline flow visually. This replaces the ASCII art for interviewer-facing documentation.

### Verification
- Run the generator and verify CSV/JSON files are created
- Verify referential integrity (all ride customer_ids exist in customers)
- Verify data distributions look realistic
- **Data classification matrix exists for all fields**
- **Data dictionary document created**

---

## Phase 2: PostgreSQL — Local Relational Store

### Goal
Set up PostgreSQL in Docker, create the relational schema, and load generated data using Python. Implement database-level access control.

### What You'll Learn
- Docker and Docker Compose basics
- SQL DDL (CREATE TABLE, constraints, indexes)
- Python database interaction with `psycopg2`
- Relational schema design
- Data loading patterns (COPY vs INSERT)
- **Database RBAC — creating roles with scoped permissions**

### Files to Create

#### [NEW] Docker setup
- `docker/docker-compose.yml` — PostgreSQL service
- `docker/.env` — Database credentials (not committed)

#### [NEW] Database layer
- `src/database/connection.py` — Connection pooling and management
- `src/database/schema.py` — DDL statements and schema creation
- `src/database/loader.py` — Bulk data loading from CSV
- `src/database/rbac.py` — Role creation and permission grants

#### [NEW] SQL scripts
- `sql/ddl/create_tables.sql` — Full schema with constraints
- `sql/ddl/create_roles.sql` — RBAC role definitions
- `sql/queries/sample_queries.sql` — Practice analytical queries

### Database Security Tasks (Phase 2)

#### Database RBAC
Create dedicated database roles with scoped permissions:

```sql
-- 1. Create specialized roles
CREATE ROLE etl_writer;      -- Can read/write Silver and Gold schemas
CREATE ROLE data_analyst;    -- Can read Gold schema only
CREATE ROLE bi_reader;       -- Can read Gold aggregated views only

-- 2. Scoped permissions
GRANT USAGE ON SCHEMA gold TO data_analyst, bi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO data_analyst, bi_reader;
GRANT ALL ON SCHEMA silver, gold TO etl_writer;
```

This establishes the access control pattern that will carry into Redshift (Phase 9).

### Verification
- Docker container runs PostgreSQL
- Tables created with proper constraints
- Data loads successfully
- Sample queries return expected results
- **RBAC roles created and permissions verified**
- **Integration tests for database loading pass**

---

## Phase 3: Amazon S3 — Bronze Layer Ingestion

### Goal
Upload raw generated data to S3 in a date-partitioned Bronze layer structure. Configure S3 security, IAM roles, and encryption from day one.

### What You'll Learn
- AWS S3 concepts (buckets, prefixes, objects)
- boto3 Python SDK
- Date-based partitioning strategy
- **IAM roles and the Principle of Least Privilege**
- **S3 bucket security (Block Public Access, encryption, TLS enforcement)**
- **S3 Versioning for accidental deletion protection**
- Idempotent uploads

### Files to Create

#### [NEW] S3 ingestion
- `src/ingestion/s3_uploader.py` — Upload files to S3 with partitioning
- `src/ingestion/bronze_ingestion.py` — Orchestrate Bronze layer loading

#### [NEW] IAM & Security configuration
- `infrastructure/iam/mobility-ingestion-role.json` — IAM policy for ingestion (PutObject on bronze/* only)
- `infrastructure/iam/mobility-etl-role.json` — IAM policy for Glue ETL (read bronze/*, write silver/*, gold/*, quarantine/*)
- `infrastructure/iam/mobility-analytics-role.json` — IAM policy for Athena/Redshift (read-only on silver/*, gold/*)
- `infrastructure/s3/bucket-policy.json` — TLS enforcement + prefix isolation

#### [NEW] Resource management
- `scripts/teardown_aws.sh` — Destroys ALL AWS resources to avoid surprise bills
- `scripts/setup_s3.sh` — Creates bucket with security config (Block Public Access, encryption, versioning)

### S3 Security Configuration (Phase 3)

Every S3 bucket MUST be configured with:

1. **Block Public Access** — All 4 settings enabled (BlockPublicAcls, IgnorePublicAcls, BlockPublicPolicy, RestrictPublicBuckets)
2. **Default Encryption** — SSE-S3 (AES256) on all objects
3. **TLS Enforcement** — Bucket policy denying any request where `aws:SecureTransport = false`
4. **Versioning Enabled** — Protects against accidental deletion or overwrite
5. **Prefix Isolation** — Separate IAM access for `bronze/`, `silver/`, `gold/`, `quarantine/`

### IAM Role Design

| Role | Permissions | Used By |
|------|------------|---------|
| `mobility-ingestion-role` | `s3:PutObject` on `bronze/*` only | Python ingestion scripts |
| `mobility-etl-role` | `s3:GetObject` on `bronze/*`, `s3:PutObject` on `silver/*`, `gold/*`, `quarantine/*` | Glue/PySpark ETL jobs |
| `mobility-analytics-role` | `s3:GetObject`, `s3:ListBucket` on `silver/*`, `gold/*` only. Explicit `Deny` on `bronze/*` | Athena, Redshift Spectrum |
| `mobility-airflow-role` | Trigger Glue jobs, no direct S3 write | Airflow orchestration |

### S3 Structure Created
```
s3://mobility-data-lake/
└── bronze/
    ├── customers/year=2026/month=09/day=01/customers.csv
    ├── drivers/year=2026/month=09/day=01/drivers.csv
    ├── rides/year=2026/month=09/day=01/rides.csv
    └── payments/year=2026/month=09/day=01/payments.csv
```

### Verification
- Files appear in S3 with correct structure
- Re-running doesn't create duplicates (idempotent)
- Credentials are NOT in source code
- **Block Public Access is ON (verify in AWS Console)**
- **Default encryption is enabled**
- **S3 Versioning is enabled**
- **IAM roles have scoped permissions (no wildcards)**
- **TLS-only bucket policy is active**
- **Teardown script successfully removes all resources**
- **📸 Screenshot: S3 bucket security settings, IAM role policies**

---

## Phase 4: PySpark — Bronze → Silver Transformations

### Goal
Read Bronze data from S3 (or local), apply cleaning/validation/deduplication, **mask PII fields**, **obfuscate geospatial data**, and write Silver layer as Parquet. Apply Spark performance tuning.

### What You'll Learn
- PySpark DataFrames and operations
- Data type casting and standardization
- Deduplication with `dropDuplicates()`
- Null handling strategies
- Writing Parquet files
- Column transformations
- **PII masking — hashing emails, phones, and names using salted SHA-256**
- **Geospatial privacy — converting GPS coordinates to H3 hex indices**
- **Pipeline idempotency — ensuring re-runs don't create duplicates**
- **Spark performance tuning — shuffle partitions, predicate pushdown**
- **Partition strategy — avoiding the small files problem**

### Files to Create

#### [NEW] PySpark transformations
- `src/transformations/spark_session.py` — Spark session factory with tuned configurations
- `src/transformations/bronze_to_silver.py` — Main transformation pipeline
- `src/transformations/cleaners/ride_cleaner.py` — Ride-specific cleaning
- `src/transformations/cleaners/customer_cleaner.py`
- `src/transformations/cleaners/driver_cleaner.py`
- `src/transformations/cleaners/payment_cleaner.py`

#### [NEW] Data protection
- `src/transformations/masking/pii_masker.py` — PII hashing and masking functions
- `src/transformations/masking/geo_obfuscator.py` — H3 hex index conversion for GPS coordinates

#### [NEW] Tests
- `tests/test_bronze_to_silver.py` — Integration tests for Silver transformations
- `tests/test_pii_masker.py` — Unit tests verifying PII is correctly masked

### Key Transformations
```
Bronze CSV → Read into Spark DataFrame
  → Cast data types (strings → timestamps, decimals, integers)
  → Standardize city names ("pune" / "PUNE" → "Pune")
  → Handle nulls (reject vs. default vs. keep)
  → Deduplicate on primary keys
  → Filter invalid records (fare > 0, distance >= 0)
  → Derive timestamp fields (ride_date, ride_hour, day_of_week)
  → [NEW] Mask PII fields (hash emails, phones, names with salted SHA-256)
  → [NEW] Obfuscate GPS coordinates to H3 hex indices (resolution 7 ~1.2 km²)
  → [NEW] Add lineage metadata (_source_file, _pipeline_run_id, _processed_at)
  → Write as Parquet to Silver (mode="overwrite" per partition for idempotency)
```

### PII Masking Rules (Applied in Silver)

| Field | Raw (Bronze) | Masked (Silver) | Method |
|-------|-------------|-----------------|--------|
| email | priya@gmail.com | `a1b2c3d4...` (64-char hash) | SHA-256 with salt |
| phone | +91 98765 43210 | `***-***-3210` | Last 4 digits only |
| first_name | Priya | `P***` | First initial + mask |
| last_name | Patel | `P***` | First initial + mask |
| pickup_lat/lon | 19.0760, 72.8777 | `872a1069fffffff` | H3 hex index (res 7) |
| dropoff_lat/lon | 18.9220, 72.8347 | `872a1068bffffff` | H3 hex index (res 7) |

### Pipeline Idempotency
Silver writes use **partition-based overwrite** — each run writes to a specific date partition (`year=YYYY/month=MM/day=DD`) using `mode="overwrite"`. If the pipeline re-runs for the same date, it replaces the partition instead of appending duplicates.

### Spark Performance Tuning

Configure these in `spark_session.py`:

| Setting | Default | Our Setting | Why |
|---------|---------|-------------|-----|
| `spark.sql.shuffle.partitions` | 200 | 8-16 (for local), 50-100 (for Glue) | Default 200 creates 200 tiny files for small datasets |
| `spark.sql.parquet.compression.codec` | snappy | snappy | Best balance of speed vs compression |
| `spark.sql.sources.partitionOverwriteMode` | static | dynamic | Overwrites only the partitions being written, not entire table |

### Partition Strategy

**Target**: 1 Parquet file per partition between 64 MB and 256 MB. Avoid creating hundreds of tiny files.

```
✅ GOOD: gold/fact_rides/year=2026/month=08/ → 1-3 files, 80 MB each
❌ BAD:  gold/fact_rides/year=2026/month=08/day=01/city=Mumbai/status=completed/ → 1 file, 0.02 MB
```

Use `coalesce(1)` or `coalesce(4)` before writing to control output file count for small datasets.

### Verification
- Silver Parquet files are created
- Record count: Bronze ≥ Silver (some records filtered/deduped)
- Data types are correct in Parquet schema
- No duplicates in Silver
- **PII fields are masked — no raw emails, phones, or names in Silver**
- **GPS coordinates replaced with H3 hex strings**
- **Lineage metadata columns present (_source_file, _pipeline_run_id, _processed_at)**
- **Re-running the pipeline produces identical output (idempotent)**
- **Integration tests pass**
- **📸 Screenshot: Silver Parquet schema showing masked fields**

---

## Phase 5: PySpark — Silver → Gold (Dimensional Model)

### Goal
Build fact and dimension tables from Silver data using PySpark joins and transformations. Apply broadcast joins for dimension tables and ensure idempotent writes.

### What You'll Learn
- Dimensional modeling concepts
- Surrogate key generation
- Multi-table joins in Spark
- Aggregation and window functions
- Star schema design
- Partitioned Parquet writes
- **Broadcast joins — why small dimension tables should be broadcast**
- **Idempotent Gold writes**

### Files to Create

#### [NEW] Gold transformations
- `src/transformations/silver_to_gold.py` — Orchestrator
- `src/transformations/dimensions/dim_customer.py`
- `src/transformations/dimensions/dim_driver.py`
- `src/transformations/dimensions/dim_location.py`
- `src/transformations/dimensions/dim_date.py`
- `src/transformations/facts/fact_rides.py`
- `src/transformations/facts/fact_payments.py`

#### [NEW] Tests
- `tests/test_silver_to_gold.py` — Integration tests verifying star schema integrity

### Output Tables
```
Gold/
├── fact_rides/        — partitioned by year/month
├── fact_payments/     — partitioned by year/month
├── dim_customer/      — surrogate keys, NO raw PII (names/emails are masked)
├── dim_driver/        — surrogate keys, NO raw PII
├── dim_location/      — H3 hex indices, NO raw GPS coordinates
└── dim_date/
```

### Performance: Broadcast Joins
Dimension tables (customers: ~1K rows, drivers: ~500 rows, locations: ~60 rows, dates: ~365 rows) are tiny compared to fact tables (rides: 10K-5M rows). Use `broadcast()` to avoid expensive shuffle joins:

```python
from pyspark.sql.functions import broadcast

# Instead of:
fact_rides = rides.join(dim_customer, on="customer_key")  # SLOW — shuffles both tables

# Do:
fact_rides = rides.join(broadcast(dim_customer), on="customer_key")  # FAST — sends dim to all executors
```

### Gold Layer Security
- Gold tables contain **surrogate keys only** (customer_key, driver_key) — no raw IDs
- **No PII** in Gold — all names, emails, phones were masked in Silver
- **No raw GPS** in Gold — only H3 hex indices from Silver
- Analysts and BI tools query Gold without ever seeing raw data

### Verification
- All dimension and fact tables created as Parquet
- Foreign keys in facts reference valid dimension keys
- Record counts are consistent
- Partitioning is applied to fact tables
- **Gold contains zero raw PII fields**
- **Broadcast joins used for dimension table joins**
- **Re-running produces identical output (idempotent)**
- **Integration tests pass**
- **📸 Screenshot: Gold Parquet schema, row counts**

---

## Phase 6: Data Quality & Error Handling

### Goal
Add systematic data quality checks, route bad records to a quarantine zone, define a reprocessing path for corrected records, and build a data assertion test suite.

### What You'll Learn
- Data quality frameworks and patterns
- Referential integrity validation
- Quarantine/rejected records pattern
- Quality metrics and reporting
- Production error handling
- **Quarantine review and reprocessing workflow**
- **Data assertion suites (Great Expectations or PySpark assertions)**
- **Quality alerting thresholds**

### Files to Create

#### [NEW] Quality framework
- `src/quality/validators.py` — Reusable validation rules
- `src/quality/referential_checks.py` — FK validation
- `src/quality/quality_reporter.py` — Generate quality reports
- `src/quality/quarantine.py` — Route bad records with error metadata
- `src/quality/reprocessor.py` — Reprocess corrected quarantine records

#### [NEW] Data assertion suite
- `src/quality/assertions.py` — Post-pipeline data assertions
- `tests/test_data_quality.py` — Tests for the quality framework itself

### Quarantine Structure
```
s3://mobility-data-lake/
├── bronze/
├── silver/
├── gold/
└── quarantine/
    ├── rides/dt=2026-09-01/
    │   └── failed_records.parquet    ← each record has error metadata
    ├── customers/
    ├── drivers/
    └── payments/
```

### Quarantine Record Format
Every quarantined record includes error metadata for debugging:
```json
{
  "raw_record": "{...original record...}",
  "error_code": "NEGATIVE_DISTANCE",
  "error_message": "distance_km must be >= 0, got -12.5",
  "source_file": "bronze/rides/year=2026/month=08/day=25/rides.csv",
  "pipeline_run_id": "run-2026-09-01-0800",
  "quarantined_at": "2026-09-01T08:15:00Z"
}
```

### Data Assertion Suite (Runs After Each Pipeline Stage)

Assertions that run automatically after Silver and Gold writes:

```python
# Post-Silver assertions
assert silver_df.filter("fare < 0").count() == 0           # No negative fares
assert silver_df.filter("ride_id IS NULL").count() == 0     # No null PKs
assert silver_df.count() > 0                                 # Not empty
assert silver_df.select("ride_id").distinct().count() == silver_df.count()  # No dupes

# Post-Gold assertions
assert fact_rides.filter("customer_key IS NULL").count() == 0  # All FKs valid
assert dim_customer.filter("email LIKE '%@%'").count() == 0    # No raw emails in Gold
```

### Quality Alerting Thresholds
Define thresholds that trigger warnings:

| Metric | Warning Threshold | Critical Threshold |
|--------|------------------|-------------------|
| Daily rejection rate | > 5% | > 15% |
| Duplicate rate | > 0.5% | > 2% |
| Null PK rate | > 0% (any nulls) | — |
| Volume drop vs 7-day avg | > 30% drop | > 60% drop |

### Quarantine Reprocessing Path
When quarantined records are investigated and corrected:
1. Fix the root cause (e.g., upstream data source issue)
2. Move corrected records back to Bronze
3. Re-run the Silver transformation for that date partition
4. Pipeline idempotency ensures no duplicates

### Verification
- Bad records (negative fare, missing IDs, invalid status) land in quarantine/
- Quality report shows counts of passed/failed/quarantined
- Silver/Gold are clean — no invalid records
- **Data assertion suite passes post-Silver and post-Gold**
- **Quality report includes rejection rate, duplicate rate, null rate**
- **Quarantine records include error metadata**
- **📸 Screenshot: Quality report, quarantine record sample**

---

## Phase 7: AWS Glue — Managed Cloud ETL

### Goal
Move PySpark transformations to AWS Glue jobs. Set up the Glue Data Catalog. Implement incremental processing with Glue Job Bookmarks.

### What You'll Learn
- AWS Glue jobs and architecture
- Glue Data Catalog and Crawlers
- GlueContext and DynamicFrames
- Cloud-managed Spark execution
- **Job Bookmarks for incremental processing**
- **Data lineage tracking through catalog metadata**

### Files to Create

#### [NEW] Glue jobs
- `glue_jobs/bronze_to_silver_glue.py` — Glue version of Bronze→Silver (with PII masking)
- `glue_jobs/silver_to_gold_glue.py` — Glue version of Silver→Gold

#### [NEW] Infrastructure config
- `infrastructure/glue/crawler_config.json` — Crawler definitions
- `infrastructure/glue/job_config.json` — Job parameters
- `infrastructure/glue/security_config.json` — Glue security configuration (encryption for local disk and shuffle)

### Incremental Processing with Job Bookmarks
Instead of reprocessing ALL Bronze data every run, Glue Job Bookmarks track what has already been processed:

```
Run 1: Processes bronze/rides/year=2026/month=08/day=25/  → bookmark saved
Run 2: Processes bronze/rides/year=2026/month=08/day=26/  → only NEW data
Run 3: Processes bronze/rides/year=2026/month=08/day=27/  → only NEW data
```

**Without bookmarks**: Every run reads and transforms the entire Bronze history (5M+ records)
**With bookmarks**: Each run processes only new/unprocessed data (~50K records)

### Glue Data Catalog — Governance Metadata
Register all tables with appropriate metadata tags:

| Catalog Database | Tables | Metadata Tags |
|-----------------|--------|---------------|
| `mobility_bronze_db` | rides, customers, drivers, payments | `layer=bronze`, `contains_pii=true` |
| `mobility_silver_db` | rides, customers, drivers, payments | `layer=silver`, `pii_masked=true` |
| `mobility_gold_db` | fact_rides, fact_payments, dim_customer, dim_driver, dim_location, dim_date | `layer=gold`, `pii_masked=true`, `analytical=true` |

### Data Lineage Columns
Every Silver and Gold record includes:
- `_source_file_uri` — S3 path of the source Bronze file
- `_pipeline_run_id` — Unique Glue job run ID
- `_processed_timestamp` — UTC timestamp of transformation

### Verification
- Glue jobs run successfully in AWS console
- Crawlers populate the Glue Data Catalog
- Tables visible in Catalog with correct schemas
- **Job Bookmarks enabled — second run processes only new data**
- **Catalog tables have metadata tags**
- **Lineage columns present in output data**
- **Glue security configuration enabled (local disk encryption)**
- **📸 Screenshot: Glue Console — job run duration, Data Catalog tables, job bookmark status**

---

## Phase 8: Amazon Athena — Query the Lake

### Goal
Query Gold layer data directly in S3 using Athena SQL. Demonstrate partition pruning and cost optimization.

### What You'll Learn
- Serverless SQL querying
- Querying Parquet data over S3
- Using Glue Catalog as metastore
- Cost optimization with partitioning
- Ad-hoc vs. warehouse analytics

### Files to Create

#### [NEW] Athena queries
- `sql/athena/create_tables.sql` — External table definitions
- `sql/athena/analytical_queries.sql` — Business analysis queries
- `sql/athena/kpi_queries.sql` — KPI calculations

### Example Queries
```sql
-- Top cities by ride demand
SELECT city, COUNT(*) as total_rides, AVG(fare) as avg_fare
FROM gold_fact_rides r JOIN gold_dim_location l ON r.location_key = l.location_key
GROUP BY city ORDER BY total_rides DESC;

-- Peak demand hours
SELECT ride_hour, COUNT(*) as demand
FROM gold_fact_rides GROUP BY ride_hour ORDER BY demand DESC;
```

### Cost Optimization — Partition Pruning
Demonstrate the cost difference:

```sql
-- Query 1: Full scan (no partition filter) → scans ~180 MB
SELECT COUNT(*), AVG(fare) FROM gold_fact_rides;

-- Query 2: With partition filter → scans ~15 MB (92% less!)
SELECT COUNT(*), AVG(fare) FROM gold_fact_rides
WHERE year = '2026' AND month = '06';
```

Athena charges $5/TB scanned. Partition pruning directly reduces your bill.

### Verification
- Athena queries return correct results
- Partitioned queries scan less data
- Results match what we see in local PySpark
- **📸 Screenshot: Athena Console — query results, "Data scanned" metric, execution time**

---

## Phase 9: Amazon Redshift — Data Warehouse

### Goal
Load Gold layer into Redshift Serverless and run analytical queries on the star schema. Implement warehouse-level RBAC.

> **Why Redshift Serverless (not Provisioned)?** Provisioned Redshift runs 24/7 at ~$180/month. Serverless charges only when queries run. For a portfolio project with 5-10 pipeline runs, Serverless costs $2-10 vs $180+. New accounts get a $300 trial credit.

### What You'll Learn
- Redshift architecture (columnar, MPP)
- COPY command for bulk loading from S3
- **Distribution keys and sort keys — how to optimize query performance**
- Analytical SQL on a star schema
- Athena vs. Redshift trade-offs
- **Warehouse RBAC — creating analyst and BI reader roles**

### Files to Create

#### [NEW] Redshift scripts
- `sql/redshift/create_schema.sql` — DDL with distribution/sort keys
- `sql/redshift/copy_from_s3.sql` — COPY commands
- `sql/redshift/create_roles.sql` — RBAC role definitions (etl_writer, data_analyst, bi_reader)
- `sql/redshift/analytical_queries.sql` — Business analytics
- `src/warehouse/redshift_loader.py` — Python-based loading

### Distribution & Sort Key Strategy

| Table | Distribution | Sort Key | Rationale |
|-------|-------------|----------|-----------|
| fact_rides | `DISTSTYLE KEY (location_key)` | `request_time` | Co-locates with dim_location for city-based joins; time-sorted for range queries |
| fact_payments | `DISTSTYLE KEY (ride_key)` | `payment_time` | Co-locates with fact_rides for ride-payment joins |
| dim_customer | `DISTSTYLE ALL` | `customer_key` | Small table — replicate to all nodes for fast joins |
| dim_driver | `DISTSTYLE ALL` | `driver_key` | Small table — replicate |
| dim_location | `DISTSTYLE ALL` | `location_key` | Small table — replicate |
| dim_date | `DISTSTYLE ALL` | `date_key` | Small table — replicate |

### Redshift RBAC
```sql
-- Same pattern as PostgreSQL (Phase 2), now in Redshift
CREATE USER etl_loader PASSWORD 'from_secrets_manager';
CREATE USER analyst PASSWORD 'from_secrets_manager';
CREATE USER bi_reader PASSWORD 'from_secrets_manager';

GRANT USAGE ON SCHEMA gold TO analyst, bi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO analyst, bi_reader;
```

### Verification
- All tables loaded in Redshift
- Analytical queries return correct results
- Star schema joins work efficiently
- Compare results with Athena queries
- **Distribution/sort keys applied correctly**
- **RBAC roles created and permissions verified**
- **📸 Screenshot: Redshift query results, execution plan showing sort key usage**

---

## Phase 10: Apache Airflow — Pipeline Orchestration

### Goal
Orchestrate the entire pipeline (ingest → bronze → silver → gold → warehouse) using Airflow DAGs. Implement alerting, idempotent DAGs, and backfill capability.

> **Cost note**: Apache Airflow is open-source and FREE. We run it locally in Docker. DO NOT use AWS MWAA (Managed Workflows for Apache Airflow) — it costs $300+/month.

### What You'll Learn
- Airflow architecture (scheduler, webserver, workers)
- DAG design and task dependencies
- Operators (Python, Bash, S3, Glue, Redshift)
- Scheduling and retries
- XComs for inter-task communication
- **Failure alerting — on_failure_callback**
- **Idempotent DAGs — safe to re-run without duplicates**
- **Backfill strategy — how to reprocess historical data**

### Files to Create

#### [NEW] Airflow setup
- `docker/docker-compose-airflow.yml` — Full Airflow stack
- `dags/mobility_pipeline_dag.py` — Main orchestration DAG (with alerting and idempotency)
- `dags/data_quality_dag.py` — Quality check DAG
- `plugins/operators/custom_operators.py` — Custom operators

### DAG Structure
```
generate_data → upload_bronze → validate_bronze
    → transform_silver → validate_silver
    → transform_gold → validate_gold
    → load_redshift → run_quality_checks
    → notify_completion
```

### Alerting Configuration
```python
# In DAG definition:
default_args = {
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'on_failure_callback': alert_on_failure,   # Email or log alert
    'on_retry_callback': alert_on_retry,
}
```

### Idempotent DAG Design
- Each task operates on a specific `execution_date` partition
- Silver/Gold writes use `mode="overwrite"` per partition
- Re-running a DAG for the same date replaces data, never appends duplicates
- Glue Job Bookmarks track processed data

### Backfill Strategy
When a bug is fixed and historical data needs reprocessing:
```bash
# Reprocess last 7 days:
airflow dags backfill mobility_pipeline \
  --start-date 2026-08-25 \
  --end-date 2026-09-01
```
Because DAGs are idempotent, backfill safely overwrites the affected date partitions.

### Verification
- DAG renders in Airflow UI without errors
- Full pipeline runs end-to-end on schedule
- Failed tasks retry correctly
- Task logs are accessible
- **Failure callbacks trigger alerts**
- **Backfill command successfully reprocesses historical data**
- **Re-running a DAG produces identical results (idempotent)**
- **📸 Screenshot: Airflow UI — DAG graph, task execution timeline, task logs**

---

## Phase 11: Power BI — Dashboards & Visualization

### Goal
Connect Power BI to Redshift and build executive and operational dashboards.

### What You'll Learn
- Power BI data connectivity
- DAX measures and calculations
- Dashboard design best practices
- KPI visualization
- Interactive filtering and drill-down

### Dashboards to Build

#### Executive Dashboard
- Total rides, revenue, avg fare, cancellation rate
- Revenue trend over time
- City-wise performance map

#### Operational Dashboard
- Rides by hour (demand pattern)
- Driver performance metrics
- Cancellation analysis by location
- Payment method distribution

### Verification
- Dashboards connected to live Redshift data
- Filters and drill-downs work correctly
- KPIs match Athena/Redshift query results
- **📸 Screenshot/Recording: Dashboard walkthrough showing KPIs, filters, drill-downs**

---

## AWS Cost Estimate (Portfolio Project)

> **Context**: This is a portfolio project. You'll run the pipeline 5-10 times on real AWS, collect evidence (screenshots, recordings, query results), then tear down all resources.

### Expected Costs

| Service | Usage Pattern | Estimated Total Cost |
|---------|--------------|---------------------|
| **S3** | ~2 GB storage for 1-2 months | **~$0.05** (free tier covers 5 GB) |
| **Glue ETL** | 2 jobs × 10 runs × ~10 min × 2 DPU | **$7-15** ($0.44/DPU-hour) |
| **Glue Catalog** | <1M objects | **Free** |
| **Athena** | ~100 queries × ~50 MB scanned each | **$0.03** ($5/TB) |
| **Redshift Serverless** | 5-10 loading sessions + queries | **$5-15** (covered by $300 trial credit) |
| **Airflow** | Docker on your laptop | **$0** (self-hosted, not MWAA) |
| **IAM, CloudWatch** | Basic usage | **Free** |
| | | |
| **TOTAL** | | **$12-30** (mostly Glue ETL compute) |

### Free Tier & Credits (New AWS Account)

| Service | Free Tier Offer | Covers Our Usage? |
|---------|----------------|-------------------|
| S3 | 5 GB storage + 20K GET + 2K PUT/month for 12 months | ✅ Fully covered |
| Glue Catalog | 1M objects free | ✅ Fully covered |
| Glue ETL | No free tier | ❌ ~$7-15 cost |
| Athena | No free tier, but $5/TB scanned (our data is tiny) | ✅ Pennies |
| Redshift Serverless | $300 credit for 3 months (trial) | ✅ Fully covered |

### ⚠️ Cost Killers to AVOID

| Service | Cost | Alternative |
|---------|------|-------------|
| Redshift Provisioned (dc2.large) | $180/month running 24/7 | Use **Redshift Serverless** (pay-per-query) |
| AWS MWAA (Managed Airflow) | $300+/month | Use **Docker Airflow** on your laptop ($0) |
| Forgetting to delete resources | $180-500/month | Run `scripts/teardown_aws.sh` after every session |

### Teardown Checklist (Run After Every Session)
```bash
# scripts/teardown_aws.sh
# 1. Delete Redshift Serverless workgroup (or pause it)
# 2. Delete Glue jobs and crawlers
# 3. Empty and delete S3 bucket (or keep bucket, delete objects)
# 4. Delete IAM roles and policies
# 5. Verify nothing is running in AWS Console → Billing Dashboard
```

---

## Evidence Collection Strategy (For Interviews)

> **Why**: Interviewers will ask "Show me it works." You need proof.

### What to Capture

| Phase | Evidence to Collect | Format |
|-------|-------------------|--------|
| Phase 1 | Generated data samples, test results | Terminal screenshot |
| Phase 3 | S3 bucket structure, security settings, IAM policies | AWS Console screenshots |
| Phase 4 | Silver Parquet schema (showing masked PII fields), record counts | PySpark output screenshot |
| Phase 5 | Gold star schema, FK validation results | PySpark output screenshot |
| Phase 6 | Quality report, quarantine record samples | Terminal + file screenshots |
| Phase 7 | Glue Console — job run duration, Data Catalog, bookmark status | AWS Console screenshots |
| Phase 8 | Athena query results + "Data scanned" + execution time | Athena Console screenshots |
| Phase 9 | Redshift query results, execution plans | Redshift Console screenshots |
| Phase 10 | Airflow DAG graph, task timeline, logs | Airflow UI screenshots |
| Phase 11 | Dashboard walkthrough | Screen recording |

### Storage
```
docs/
├── screenshots/       ← AWS Console, terminal, query results
├── recordings/        ← Screen recordings of pipeline runs
└── query_results/     ← Saved CSV outputs from Athena/Redshift queries
```

---

## Documentation Deliverables (Built Incrementally)

These documents are created alongside the phases, not as a separate effort:

| Document | Created In | Purpose |
|----------|-----------|---------|
| `docs/data_dictionary.md` | Phase 1 | Column-level docs with PII classification |
| `docs/data_governance_and_security.md` | Exists (update each phase) | Governance architecture blueprint |
| `docs/adr/` | Each phase | Architecture Decision Records (why Parquet? why star schema? why Airflow?) |
| `docs/runbooks/` | Phase 7+ | Operational playbooks (what to do when X fails) |
| `docs/incident_response.md` | Phase 7+ | Data breach response procedure |
| `README.md` | Phase 1 (update each phase) | Project overview with architecture diagram |

### Architecture Decision Records (ADRs)
Short documents recording WHY specific decisions were made:

| ADR | Decision | Phase |
|-----|---------|-------|
| ADR-001 | Why Parquet over CSV/ORC for Silver/Gold | Phase 4 |
| ADR-002 | Why Star Schema over Data Vault | Phase 5 |
| ADR-003 | Why Redshift Serverless over Provisioned | Phase 9 |
| ADR-004 | Why Docker Airflow over AWS MWAA | Phase 10 |
| ADR-005 | Why H3 over GeoHash for geospatial obfuscation | Phase 4 |
| ADR-006 | Why SHA-256 salted hash for PII masking | Phase 4 |

---

## Notes

> **Phase 1 First**: Phase 1 was built completely with working code. After studying and understanding it, we move to Phase 2. Each phase builds on the previous one.

> **AWS Account**: Phases 3, 7, 8, 9 require an AWS account. Total expected cost: $12-30 for 5-10 pipeline runs using free tier + Redshift Serverless trial credit.

> **Docker**: Phases 2 and 10 require Docker Desktop.

> **Evidence**: Capture screenshots and recordings at every phase. Store in `docs/screenshots/` and `docs/recordings/`.

## Design Decisions Made

1. **Data volume**: 1,000 customers, 500 drivers, 10,000 rides, and ~8,000 payments
2. **City focus**: Indian cities (Pune, Mumbai, Bangalore, Delhi, Hyderabad, Chennai)
3. **Intentional bad data**: ~3% dirty data injected for testing cleaning pipeline
4. **Redshift Serverless** over Provisioned (cost: $5-15 vs $180/month)
5. **Docker Airflow** over AWS MWAA (cost: $0 vs $300+/month)
6. **PII masking** with salted SHA-256 in Silver layer
7. **H3 hex indexing** for geospatial privacy in Silver layer
8. **Partition-based overwrite** for pipeline idempotency

---

## V2 Scope (Future Enhancements)

After V1 is complete, these items elevate the platform to production-enterprise grade:

### Streaming & Advanced Processing
- Kafka real-time ingestion
- Spark Structured Streaming
- Delta Lake (ACID transactions, time travel, upserts)
- Databricks / Unity Catalog
- SCD Type 2 (Slowly Changing Dimensions)
- Late-arriving data handling

### Infrastructure & Security
- **VPC Design** — Private subnets for Redshift, RDS, Glue with VPC Endpoints for S3
- **Infrastructure-as-Code** — Terraform for all AWS resources (IAM, S3, Glue, Redshift, VPC)
- **DPDPA/GDPR Compliance** — Consent tracking, Right to Erasure workflow, Data Subject Access Requests
- CI/CD pipeline with security scanning (Bandit, Trufflehog, pip-audit)
- AWS GuardDuty threat detection
- AWS Config compliance rules
- ABAC / Lake Formation tag-based access control

### Advanced Governance
- Schema Registry with backward/forward compatibility rules
- Data contracts between pipeline layers
- Data observability platform (freshness, volume, drift monitoring)
- k-Anonymity / differential privacy validation
- OpenLineage + Marquez for visual lineage graphs

### Operational Maturity
- CloudWatch dashboards and alarms
- Pipeline SLA monitoring
- Chaos testing (what happens when S3 is unreachable?)
- Multi-region disaster recovery

---

## Verification Plan

### Automated Tests
- Unit tests for data generators (Phase 1) ✅
- Integration tests for database loading (Phase 2)
- Integration tests for Bronze→Silver transformations (Phase 4)
- Integration tests for Silver→Gold star schema (Phase 5)
- PII masking verification tests (Phase 4)
- Data quality assertion suite (Phase 6)
- DAG parsing tests for Airflow (Phase 10)

### Manual Verification
- Inspect generated CSV/JSON files
- Query PostgreSQL tables
- Check S3 bucket structure and security settings in AWS Console
- Verify Parquet schemas (confirm PII masking)
- Run Athena queries and record data scanned
- Check Airflow UI for DAG runs
- Review Power BI dashboards
- **Collect screenshots at every phase for evidence portfolio**
