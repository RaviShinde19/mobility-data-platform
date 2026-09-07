# Real-Time Mobility Data Platform — Phased Implementation Plan

This project will be built in **11 phases**, each introducing new concepts and technologies. You'll learn by building — each phase produces working code that builds on the previous one.

---

## Phase Overview

| Phase | Title | Key Technologies | What You Learn |
|-------|-------|-----------------|----------------|
| 1 | **Project Setup & Data Generation** | Python, Faker, CSV/JSON | Project structure, synthetic data generation, configuration management |
| 2 | **PostgreSQL — Local Relational Store** | Python, PostgreSQL, psycopg2, Docker | Relational modeling, SQL DDL, Python-DB interaction, Docker basics |
| 3 | **Amazon S3 — Bronze Layer Ingestion** | Python, boto3, S3 | Cloud storage, raw data landing, date-partitioned uploads |
| 4 | **PySpark — Local Transformations (Bronze → Silver)** | PySpark, Parquet | Spark DataFrames, cleaning, deduplication, validation, columnar storage |
| 5 | **PySpark — Silver → Gold (Dimensional Modeling)** | PySpark, Star Schema | Fact/dimension tables, surrogate keys, joins, business logic |
| 6 | **Data Quality & Error Handling** | Python, PySpark | Validation rules, rejected records, referential integrity, quarantine zone |
| 7 | **AWS Glue — Managed Cloud ETL** | AWS Glue, Glue Catalog, PySpark | Managed Spark, crawlers, data catalog, cloud-scale ETL |
| 8 | **Amazon Athena — Query the Lake** | Athena, SQL, Glue Catalog | Serverless SQL over S3, ad-hoc analytics, lake querying |
| 9 | **Amazon Redshift — Data Warehouse** | Redshift, SQL, COPY command | Warehouse loading, analytical SQL, star schema queries |
| 10 | **Apache Airflow — Pipeline Orchestration** | Airflow, Docker Compose, DAGs | Workflow orchestration, task dependencies, scheduling, retries |
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

### Verification
- Run the generator and verify CSV/JSON files are created
- Verify referential integrity (all ride customer_ids exist in customers)
- Verify data distributions look realistic

---

## Phase 2: PostgreSQL — Local Relational Store

### Goal
Set up PostgreSQL in Docker, create the relational schema, and load generated data using Python.

### What You'll Learn
- Docker and Docker Compose basics
- SQL DDL (CREATE TABLE, constraints, indexes)
- Python database interaction with `psycopg2`
- Relational schema design
- Data loading patterns (COPY vs INSERT)

### Files to Create

#### [NEW] Docker setup
- `docker/docker-compose.yml` — PostgreSQL service
- `docker/.env` — Database credentials (not committed)

#### [NEW] Database layer
- `src/database/connection.py` — Connection pooling and management
- `src/database/schema.py` — DDL statements and schema creation
- `src/database/loader.py` — Bulk data loading from CSV

#### [NEW] SQL scripts
- `sql/ddl/create_tables.sql` — Full schema with constraints
- `sql/queries/sample_queries.sql` — Practice analytical queries

### Verification
- Docker container runs PostgreSQL
- Tables created with proper constraints
- Data loads successfully
- Sample queries return expected results

---

## Phase 3: Amazon S3 — Bronze Layer Ingestion

### Goal
Upload raw generated data to S3 in a date-partitioned Bronze layer structure.

### What You'll Learn
- AWS S3 concepts (buckets, prefixes, objects)
- boto3 Python SDK
- Date-based partitioning strategy
- IAM basics and credential management
- Idempotent uploads

### Files to Create

#### [NEW] S3 ingestion
- `src/ingestion/s3_uploader.py` — Upload files to S3 with partitioning
- `src/ingestion/bronze_ingestion.py` — Orchestrate Bronze layer loading

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

---

## Phase 4: PySpark — Bronze → Silver Transformations

### Goal
Read Bronze data from S3 (or local), apply cleaning/validation/deduplication, and write Silver layer as Parquet.

### What You'll Learn
- PySpark DataFrames and operations
- Data type casting and standardization
- Deduplication with `dropDuplicates()`
- Null handling strategies
- Writing Parquet files
- Column transformations

### Files to Create

#### [NEW] PySpark transformations
- `src/transformations/spark_session.py` — Spark session factory
- `src/transformations/bronze_to_silver.py` — Main transformation pipeline
- `src/transformations/cleaners/ride_cleaner.py` — Ride-specific cleaning
- `src/transformations/cleaners/customer_cleaner.py`
- `src/transformations/cleaners/driver_cleaner.py`
- `src/transformations/cleaners/payment_cleaner.py`

### Key Transformations
```
Bronze CSV → Read into Spark DataFrame
  → Cast data types (strings → timestamps, decimals, integers)
  → Standardize city names ("pune" / "PUNE" → "Pune")
  → Handle nulls (reject vs. default vs. keep)
  → Deduplicate on primary keys
  → Filter invalid records (fare > 0, distance >= 0)
  → Derive timestamp fields (ride_date, ride_hour, day_of_week)
  → Write as Parquet to Silver
```

### Verification
- Silver Parquet files are created
- Record count: Bronze ≥ Silver (some records filtered/deduped)
- Data types are correct in Parquet schema
- No duplicates in Silver

---

## Phase 5: PySpark — Silver → Gold (Dimensional Model)

### Goal
Build fact and dimension tables from Silver data using PySpark joins and transformations.

### What You'll Learn
- Dimensional modeling concepts
- Surrogate key generation
- Multi-table joins in Spark
- Aggregation and window functions
- Star schema design
- Partitioned Parquet writes

### Files to Create

#### [NEW] Gold transformations
- `src/transformations/silver_to_gold.py` — Orchestrator
- `src/transformations/dimensions/dim_customer.py`
- `src/transformations/dimensions/dim_driver.py`
- `src/transformations/dimensions/dim_location.py`
- `src/transformations/dimensions/dim_date.py`
- `src/transformations/facts/fact_rides.py`
- `src/transformations/facts/fact_payments.py`

### Output Tables
```
Gold/
├── fact_rides/        — partitioned by year/month
├── fact_payments/     — partitioned by year/month
├── dim_customer/
├── dim_driver/
├── dim_location/
└── dim_date/
```

### Verification
- All dimension and fact tables created as Parquet
- Foreign keys in facts reference valid dimension keys
- Record counts are consistent
- Partitioning is applied to fact tables

---

## Phase 6: Data Quality & Error Handling

### Goal
Add systematic data quality checks and route bad records to a quarantine zone.

### What You'll Learn
- Data quality frameworks and patterns
- Referential integrity validation
- Quarantine/rejected records pattern
- Quality metrics and reporting
- Production error handling

### Files to Create

#### [NEW] Quality framework
- `src/quality/validators.py` — Reusable validation rules
- `src/quality/referential_checks.py` — FK validation
- `src/quality/quality_reporter.py` — Generate quality reports
- `src/quality/quarantine.py` — Route bad records

### Quarantine Structure
```
s3://mobility-data-lake/
├── bronze/
├── silver/
├── gold/
└── rejected/
    ├── rides/
    ├── customers/
    ├── drivers/
    └── payments/
```

### Verification
- Bad records (negative fare, missing IDs, invalid status) land in rejected/
- Quality report shows counts of passed/failed/quarantined
- Silver/Gold are clean — no invalid records

---

## Phase 7: AWS Glue — Managed Cloud ETL

### Goal
Move PySpark transformations to AWS Glue jobs. Set up the Glue Data Catalog.

### What You'll Learn
- AWS Glue jobs and architecture
- Glue Data Catalog and Crawlers
- GlueContext and DynamicFrames
- Cloud-managed Spark execution
- Job bookmarks for incremental processing

### Files to Create

#### [NEW] Glue jobs
- `glue_jobs/bronze_to_silver_glue.py` — Glue version of Bronze→Silver
- `glue_jobs/silver_to_gold_glue.py` — Glue version of Silver→Gold

#### [NEW] Infrastructure config
- `infrastructure/glue/crawler_config.json` — Crawler definitions
- `infrastructure/glue/job_config.json` — Job parameters

### Verification
- Glue jobs run successfully in AWS console
- Crawlers populate the Glue Data Catalog
- Tables visible in Catalog with correct schemas

---

## Phase 8: Amazon Athena — Query the Lake

### Goal
Query Gold layer data directly in S3 using Athena SQL.

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

### Verification
- Athena queries return correct results
- Partitioned queries scan less data
- Results match what we see in local PySpark

---

## Phase 9: Amazon Redshift — Data Warehouse

### Goal
Load Gold layer into Redshift and run analytical queries on the star schema.

### What You'll Learn
- Redshift architecture (columnar, MPP)
- COPY command for bulk loading from S3
- Distribution and sort keys
- Analytical SQL on a star schema
- Athena vs. Redshift trade-offs

### Files to Create

#### [NEW] Redshift scripts
- `sql/redshift/create_schema.sql` — DDL with distribution/sort keys
- `sql/redshift/copy_from_s3.sql` — COPY commands
- `sql/redshift/analytical_queries.sql` — Business analytics
- `src/warehouse/redshift_loader.py` — Python-based loading

### Verification
- All tables loaded in Redshift
- Analytical queries return correct results
- Star schema joins work efficiently
- Compare results with Athena queries

---

## Phase 10: Apache Airflow — Pipeline Orchestration

### Goal
Orchestrate the entire pipeline (ingest → bronze → silver → gold → warehouse) using Airflow DAGs.

### What You'll Learn
- Airflow architecture (scheduler, webserver, workers)
- DAG design and task dependencies
- Operators (Python, Bash, S3, Glue, Redshift)
- Scheduling and retries
- XComs for inter-task communication
- Monitoring and alerting

### Files to Create

#### [NEW] Airflow setup
- `docker/docker-compose-airflow.yml` — Full Airflow stack
- `dags/mobility_pipeline_dag.py` — Main orchestration DAG
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

### Verification
- DAG renders in Airflow UI without errors
- Full pipeline runs end-to-end on schedule
- Failed tasks retry correctly
- Task logs are accessible

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

---

## Notes from Phase 1 Planning

> **Phase 1 First**: Phase 1 was built completely with working code. After studying and understanding it, we move to Phase 2. Each phase builds on the previous one.

> **AWS Account**: Phases 3, 7, 8, 9 require an AWS account. LocalStack can be used for local simulation if needed.

> **Docker**: Phases 2 and 10 require Docker Desktop.

## Design Decisions Made

1. **Data volume**: 1,000 customers, 500 drivers, 10,000 rides, and ~8,000 payments
2. **City focus**: Indian cities (Pune, Mumbai, Bangalore, Delhi, Hyderabad, Chennai)
3. **Intentional bad data**: ~3% dirty data injected for testing cleaning pipeline

---

## Verification Plan

### Automated Tests
- Unit tests for data generators (Phase 1)
- Integration tests for database loading (Phase 2)
- Data quality assertion tests (Phase 6)
- DAG parsing tests for Airflow (Phase 10)

### Manual Verification
- Inspect generated CSV/JSON files
- Query PostgreSQL tables
- Check S3 bucket structure in AWS Console
- Verify Parquet schemas
- Run Athena queries
- Check Airflow UI for DAG runs
- Review Power BI dashboards
