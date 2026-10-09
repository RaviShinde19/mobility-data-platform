"""
Bronze Ingestion — The "What to Upload" Module

PURPOSE:
    This script takes the raw CSV files from data/raw/ and uploads them into
    the Bronze layer of our S3 data lake, organized in Hive-style date
    partitions (year=YYYY/month=MM/day=DD).

WHY THIS FILE EXISTS (Build Order):
    This file DEPENDS ON:
    - config/config.yaml (for bucket name, prefixes, region)
    - src/ingestion/s3_uploader.py (for the upload_file_to_s3 function)
    - scripts/setup_s3.py having been run (the bucket must already exist)

    This file is DEPENDED ON BY:
    - Phase 4 (PySpark Bronze -> Silver) will READ from the paths we create here

WHAT IS "BRONZE INGESTION"?
    "Ingestion" = moving raw data from a source into a centralized store.
    "Bronze"    = the first layer of the medallion architecture (raw, untouched data).
    
    Bronze data is an EXACT COPY of the source files. We do NOT clean,
    filter, or transform anything here. That's Silver's job (Phase 4).
    The only thing we add is the date-partitioned folder structure.

DATA FLOW:
    INPUT:  data/raw/rides/rides.csv (flat file on your laptop)
    OUTPUT: s3://bucket/bronze/rides/year=2026/month=10/day=08/rides.csv
    
    The file CONTENT is identical. Only the LOCATION changes.

CONCEPTS IN THIS FILE:
    - datetime.now() — Gets today's date to build the partition path
    - Hive-style partitioning — year=YYYY/month=MM/day=DD folder naming
    - Idempotency — Running the script twice produces the same result
    - Pipeline Run ID — Unique identifier for each execution (lineage tracking)
    - Backfilling — Using --date to upload data to a historical partition
"""

import os
import sys
import uuid
from datetime import datetime

# Add project root to Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.ingestion.s3_uploader import load_config, get_s3_client, upload_file_to_s3, _log_event


# These are the 4 datasets we generated in Phase 1.
# Each one maps to a subfolder in data/raw/ and will become
# a subfolder in s3://bucket/bronze/
DATASETS = ['customers', 'drivers', 'rides', 'payments']


def build_s3_key(prefix, dataset_name, date, filename):
    """
    Builds the Hive-style partitioned S3 key (the "address" of the file in S3).

    What this does step by step:
    1. Takes the prefix ("bronze"), dataset ("rides"), and today's date
    2. Formats them into the Hive partition pattern
    3. Returns the full S3 key

    Example:
        build_s3_key("bronze", "rides", 2026-10-08, "rides.csv")
        -> "bronze/rides/year=2026/month=10/day=08/rides.csv"

    WHY Hive-style?
        When Phase 8 (Athena) runs a query like:
            SELECT * FROM rides WHERE year=2026 AND month=09
        Athena can skip ALL other month folders and only scan September's data.
        On 14 million records, this means scanning 1.2M rows instead of 14M.
        This optimization is called "partition pruning" — it's why big data
        queries return in 2 seconds instead of 2 minutes.
    """
    return (
        f"{prefix}/{dataset_name}/"
        f"year={date.year}/month={date.month:02d}/day={date.day:02d}/"
        f"{filename}"
    )


def run_bronze_ingestion(partition_date=None):
    """
    Main function: Uploads all 4 CSV datasets to the Bronze layer in S3.

    Parameters:
        partition_date — Optional datetime object. If provided, uploads to that
                         date's partition instead of today's. This is used for
                         "Backfilling" — loading historical data into the lake.

    What this does step by step:
    1. Generate a unique Pipeline Run ID (for lineage tracking)
    2. Load config.yaml to get bucket name and prefix settings
    3. Create the boto3 S3 client (the "remote control")
    4. Determine the partition date (today or --date override)
    5. Loop through each dataset (customers, drivers, rides, payments)
    6. For each dataset:
       a. Build the local file path (data/raw/rides/rides.csv)
       b. Build the S3 destination key (bronze/rides/year=.../rides.csv)
       c. Build governance tags (pipeline_run_id, contains_pii, source)
       d. Call upload_file_to_s3() from our uploader module
    7. Print a summary of what succeeded and what failed
    """
    # --- Generate Pipeline Run ID (Gap 9: Lineage Tracking) ---
    # Every time this script runs, it generates a unique ID.
    # This ID is tagged on every file uploaded during this run.
    # If something goes wrong in Silver, you can trace back:
    # "Which Bronze batch caused this?" -> check the run ID.
    # AGENTS.md Rule 6: "Record source origin, pipeline run ID, job timestamps"
    run_id = f"bronze-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"

    config = load_config()
    s3_client = get_s3_client(config)

    bucket_name = config['s3']['bucket_name']
    bronze_prefix = config['s3']['prefix_bronze']

    # Use the provided date or default to today
    # This enables "Backfilling" — uploading to a historical date partition
    target_date = partition_date if partition_date else datetime.now()

    _log_event("ingestion_started", run_id,
               bucket=bucket_name, partition_date=target_date.strftime('%Y-%m-%d'),
               datasets=DATASETS)

    print("=" * 65)
    print("  BRONZE LAYER INGESTION -- Batch Upload to S3")
    print("=" * 65)
    print(f"  Bucket:    {bucket_name}")
    print(f"  Region:    {config['aws']['region']}")
    print(f"  Partition: year={target_date.year}/month={target_date.month:02d}/day={target_date.day:02d}")
    print(f"  Datasets:  {', '.join(DATASETS)}")
    print(f"  Run ID:    {run_id}")
    print("=" * 65)

    # Track results for the summary
    results = {'success': [], 'failed': []}

    for dataset in DATASETS:
        print(f"\n[{dataset.upper()}]")

        # Build the local path where Phase 1 saved the CSV
        # e.g., "data/raw/rides/rides.csv"
        local_file = os.path.join(
            config['paths']['raw_data'],
            dataset,
            f"{dataset}.csv"
        )

        # Build the S3 destination key with Hive-style partitioning
        # e.g., "bronze/rides/year=2026/month=10/day=08/rides.csv"
        s3_key = build_s3_key(
            bronze_prefix,
            dataset,
            target_date,
            f"{dataset}.csv"
        )

        # Build S3 Object Tags for governance and lineage (Gap 10)
        # These tags are attached to the uploaded file in S3.
        # AGENTS.md Rule 4: PII must be tracked
        # AGENTS.md Rule 6: Lineage tracking on every batch
        tags = {
            'pipeline_run_id': run_id,
            'source': 'local_csv',
            'dataset': dataset,
            'layer': 'bronze',
            'contains_pii': 'true',     # Bronze always has raw PII
            'ingestion_date': target_date.strftime('%Y-%m-%d')
        }

        # Upload using our reusable uploader module
        success = upload_file_to_s3(
            s3_client, local_file, bucket_name, s3_key,
            pipeline_run_id=run_id, tags=tags
        )

        if success:
            results['success'].append(dataset)
        else:
            results['failed'].append(dataset)

    # --- Final Summary ---
    print("\n" + "=" * 65)
    print("  INGESTION SUMMARY")
    print("=" * 65)
    print(f"  Run ID:    {run_id}")
    print(f"  Succeeded: {len(results['success'])}/{len(DATASETS)} -- {', '.join(results['success']) or 'None'}")
    print(f"  Failed:    {len(results['failed'])}/{len(DATASETS)} -- {', '.join(results['failed']) or 'None'}")

    if results['failed']:
        _log_event("ingestion_completed", run_id,
                   status="partial_failure", succeeded=len(results['success']),
                   failed=len(results['failed']))
        print("\n  [WARNING] Some datasets failed to upload. Check the errors above.")
        sys.exit(1)
    else:
        _log_event("ingestion_completed", run_id,
                   status="success", datasets_uploaded=len(DATASETS))
        print(f"\n  [SUCCESS] All {len(DATASETS)} datasets ingested into Bronze layer!")
        print(f"  Verify with: aws s3 ls s3://{bucket_name}/{bronze_prefix}/ --recursive")

    print("=" * 65)


if __name__ == "__main__":
    run_bronze_ingestion()
