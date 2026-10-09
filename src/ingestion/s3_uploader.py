"""
S3 Uploader — The "Delivery Truck" Module

PURPOSE:
    This module provides a reusable function to upload any local file to an S3
    bucket. It handles the boto3 connection, error handling, and file size
    verification. It does NOT know about Bronze, Silver, or Gold — it just
    uploads whatever you tell it to.

WHY THIS FILE EXISTS:
    We separated the "how to upload" logic from the "what to upload" logic
    (Separation of Concerns). This way, bronze_ingestion.py, and later
    silver/gold scripts, can all reuse this same uploader without duplicating code.

FIRST-TIME CONCEPTS IN THIS FILE:
    - boto3.client() — Creates a connection object to an AWS service
    - upload_file() — boto3's method to stream a local file to S3
    - ClientError — The specific exception boto3 throws when AWS rejects a request
    - botocore.config.Config — Configures retry logic (exponential backoff)
    - hashlib.md5() — Computes MD5 checksum for data integrity verification
    - S3 Object Tagging — Attaching key-value metadata to uploaded files
"""

import os
import sys
import yaml
import json
import hashlib
import logging
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


# ── Structured JSON Logger ──────────────────────────────────────
# Instead of print(), production pipelines emit structured JSON logs.
# These feed into monitoring tools (CloudWatch, Datadog) for alerting.
# AGENTS.md Rule 8: "pipeline operations emit structured JSON audit logs"
def _get_logger():
    """Creates a logger that outputs structured JSON lines."""
    logger = logging.getLogger('s3_uploader')
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def _log_event(event, pipeline_run_id=None, **kwargs):
    """
    Emits a structured JSON log entry.

    Why structured JSON instead of print()?
    - CloudWatch, Datadog, and ELK Stack can parse JSON logs automatically
    - You can search/filter: "show me all 'upload_failed' events from last week"
    - Each log entry is self-contained with timestamp, event type, and metadata

    AGENTS.md Rule 8: "pipeline operations emit structured JSON audit logs"
    AGENTS.md Rule 6: "Record source origin, pipeline run ID, job timestamps"
    """
    logger = _get_logger()
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "pipeline_run_id": pipeline_run_id,
        **kwargs
    }
    logger.info(json.dumps(log_entry))


def load_config():
    """
    Reads config.yaml from the project root.

    Why a function? Because multiple scripts need the config (setup_s3.py,
    this uploader, bronze_ingestion.py). Instead of copying the same 3 lines
    everywhere, we centralize it.
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'config', 'config.yaml'
    )
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_s3_client(config):
    """
    Creates and returns a boto3 S3 client WITH retry logic.

    What this does step by step:
    1. Reads the region from config.yaml (ap-south-1 = Mumbai)
    2. Configures retry behavior (exponential backoff)
    3. Checks if we're using LocalStack or Real AWS (the toggle in config)
    4. Creates the client — this is the "remote control" for S3
    5. Returns it so the caller can use it

    NEW CONCEPT — Exponential Backoff (Gap 11):
        If a network request fails, we don't immediately retry. We wait:
        - Attempt 1: fails -> wait 1 second
        - Attempt 2: fails -> wait 2 seconds
        - Attempt 3: fails -> wait 4 seconds
        This prevents hammering a struggling AWS server with rapid-fire retries,
        which would make the problem worse. boto3 handles this automatically
        when we set the retry config.
    """
    region = config['aws']['region']

    # Configure automatic retry with exponential backoff.
    # 'adaptive' mode is boto3's smartest retry strategy — it reads
    # HTTP response headers from AWS to dynamically adjust retry timing.
    retry_config = Config(
        retries={
            'max_attempts': 5,       # Try up to 5 times before giving up
            'mode': 'adaptive'       # Uses response headers to optimize wait time
        }
    )

    if config['aws']['use_localstack']:
        return boto3.client(
            's3',
            endpoint_url=config['aws']['localstack_endpoint'],
            region_name=region,
            config=retry_config
        )
    else:
        return boto3.client('s3', region_name=region, config=retry_config)


def _compute_md5(file_path):
    """
    Computes the MD5 hash of a local file.

    NEW CONCEPT — Checksum Verification (Gap 12):
        Two files can have the exact same size but completely different content
        (e.g., a corrupted file that's the right number of bytes but wrong data).
        
        MD5 generates a unique 32-character "fingerprint" of the file contents.
        If even ONE bit is different, the fingerprint changes completely.
        
        We compute this locally, upload the file, then compare it to the S3
        object's ETag (which is also an MD5 hash for non-multipart uploads).
    """
    md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        # Read in 8KB chunks to handle large files without loading them
        # entirely into memory (important for 14M record files)
        for chunk in iter(lambda: f.read(8192), b''):
            md5.update(chunk)
    return md5.hexdigest()


def upload_file_to_s3(s3_client, local_file_path, bucket_name, s3_key,
                       pipeline_run_id=None, tags=None):
    """
    Uploads a single file from your laptop to S3.

    Parameters:
        s3_client       — The boto3 client (our "remote control")
        local_file_path — Full path to the file on your laptop
        bucket_name     — The S3 bucket name
        s3_key          — The destination path INSIDE the bucket
        pipeline_run_id — Unique ID for this pipeline run (for lineage tracking)
        tags            — Dict of key-value tags to attach to the uploaded object

    What this does step by step:
    1. Checks if the local file actually exists (prevents FileNotFoundError)
    2. Computes the MD5 checksum of the local file
    3. Calls boto3's upload_file() — streams bytes to AWS (with auto-retry)
    4. After upload, verifies size match AND checksum match
    5. Applies S3 Object Tags (for governance and lineage)

    Returns:
        True if upload succeeded and integrity verified, False otherwise
    """
    # --- Pre-check: Does the file even exist locally? ---
    if not os.path.exists(local_file_path):
        _log_event("upload_error", pipeline_run_id,
                   error="file_not_found", file_path=local_file_path)
        print(f"    [ERROR] File not found: {local_file_path}")
        print(f"           Have you run 'python main.py generate' first?")
        return False

    local_file_size = os.path.getsize(local_file_path)
    file_name = os.path.basename(local_file_path)

    # Compute local MD5 checksum BEFORE uploading
    local_md5 = _compute_md5(local_file_path)

    print(f"    Uploading {file_name} ({local_file_size:,} bytes) -> s3://{bucket_name}/{s3_key}")

    try:
        # --- THE ACTUAL UPLOAD ---
        # upload_file() streams the file in chunks (not all at once).
        # For files > 8 MB, boto3 automatically splits them into parts
        # and uploads them in parallel (called "multipart upload").
        # The retry_config we set in get_s3_client() handles transient
        # network failures automatically (exponential backoff).
        s3_client.upload_file(
            Filename=local_file_path,
            Bucket=bucket_name,
            Key=s3_key
        )
    except ClientError as e:
        _log_event("upload_failed", pipeline_run_id,
                   dataset=file_name, s3_key=s3_key, error=str(e))
        print(f"    [ERROR] Upload failed: {e}")
        return False

    # --- Post-check: Verify file integrity (Size + Checksum) ---
    try:
        response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
        s3_file_size = response['ContentLength']
        # S3's ETag for non-multipart uploads is the MD5 hash wrapped in quotes
        s3_etag = response['ETag'].strip('"')

        size_match = (s3_file_size == local_file_size)
        # For multipart uploads, S3 ETag is not a simple MD5, so we only
        # compare checksums when the ETag doesn't contain a dash (non-multipart)
        checksum_match = (s3_etag == local_md5) if '-' not in s3_etag else True

        if size_match and checksum_match:
            print(f"    [SUCCESS] Uploaded and verified ({s3_file_size:,} bytes, MD5: {local_md5[:8]}...)")
        elif not size_match:
            print(f"    [WARNING] Size mismatch! Local: {local_file_size:,} vs S3: {s3_file_size:,}")
            _log_event("integrity_warning", pipeline_run_id,
                       dataset=file_name, type="size_mismatch",
                       local_size=local_file_size, s3_size=s3_file_size)
            return False
        else:
            print(f"    [WARNING] Checksum mismatch! Local: {local_md5} vs S3: {s3_etag}")
            _log_event("integrity_warning", pipeline_run_id,
                       dataset=file_name, type="checksum_mismatch")
            return False

    except ClientError as e:
        print(f"    [ERROR] Could not verify upload: {e}")
        return False

    # --- Apply S3 Object Tags (Gap 10: Governance & Lineage) ---
    # Tags are key-value metadata attached to S3 objects. They enable:
    # - Data governance: "show me all files with contains_pii=true"
    # - Cost allocation: "how much storage does the 'rides' dataset use?"
    # - Lineage tracking: "which pipeline run produced this file?"
    if tags:
        try:
            tag_set = [{'Key': k, 'Value': str(v)} for k, v in tags.items()]
            s3_client.put_object_tagging(
                Bucket=bucket_name,
                Key=s3_key,
                Tagging={'TagSet': tag_set}
            )
        except ClientError as e:
            # Tagging failure is non-fatal — the file was uploaded successfully
            print(f"    [WARNING] Could not apply tags: {e}")

    # --- Emit structured audit log (Gap 8: AGENTS.md Rule 8) ---
    _log_event("file_uploaded", pipeline_run_id,
               dataset=file_name, s3_key=s3_key,
               file_size_bytes=local_file_size, md5=local_md5)

    return True
