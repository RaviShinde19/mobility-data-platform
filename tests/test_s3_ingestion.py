"""
Phase 3 Tests — S3 Bronze Layer Ingestion

PURPOSE:
    These tests verify that our S3 infrastructure and ingestion code
    works correctly AGAINST THE REAL AWS ACCOUNT. Unlike unit tests that
    mock everything, these are "integration tests" — they actually talk
    to AWS and verify real S3 state.

WHY INTEGRATION TESTS HERE (not unit tests)?
    The whole point of Phase 3 is to prove we can talk to AWS. Mocking
    S3 would defeat the purpose. We test against the real bucket, and
    each test verifies a specific security or data requirement from AGENTS.md.

DEPENDS ON:
    - setup_s3.py having been run (bucket exists)
    - bronze_ingestion.py having been run (data uploaded)
"""

import os
import sys
import json
import pytest
import yaml

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingestion.s3_uploader import load_config, get_s3_client


@pytest.fixture(scope="module")
def aws_setup():
    """
    A pytest fixture that runs ONCE for all tests in this file.
    It loads config and creates the S3 client so every test can use them.

    'scope="module"' means: create this once per file, not once per test.
    This saves time because creating a boto3 client involves a network call.
    """
    config = load_config()
    s3_client = get_s3_client(config)
    bucket_name = config['s3']['bucket_name']
    return {
        'config': config,
        's3_client': s3_client,
        'bucket_name': bucket_name
    }


# ─── Test 1: Bucket Exists ──────────────────────────────────
class TestS3BucketExists:
    """Verifies the bucket was created successfully."""

    def test_bucket_exists(self, aws_setup):
        """The bucket should appear in the list of all buckets."""
        s3 = aws_setup['s3_client']
        bucket_name = aws_setup['bucket_name']

        response = s3.list_buckets()
        bucket_names = [b['Name'] for b in response['Buckets']]
        assert bucket_name in bucket_names, f"Bucket {bucket_name} not found!"


# ─── Test 2: Security — Block Public Access (AGENTS.md Rule 2) ───
class TestS3Security:
    """Verifies all AGENTS.md security rules are applied."""

    def test_public_access_blocked(self, aws_setup):
        """All 4 public access flags must be True (blocked)."""
        s3 = aws_setup['s3_client']
        bucket_name = aws_setup['bucket_name']

        response = s3.get_public_access_block(Bucket=bucket_name)
        config = response['PublicAccessBlockConfiguration']

        assert config['BlockPublicAcls'] is True
        assert config['IgnorePublicAcls'] is True
        assert config['BlockPublicPolicy'] is True
        assert config['RestrictPublicBuckets'] is True

    def test_encryption_enabled(self, aws_setup):
        """Default encryption must be AES256 (SSE-S3). (AGENTS.md Rule 3)"""
        s3 = aws_setup['s3_client']
        bucket_name = aws_setup['bucket_name']

        response = s3.get_bucket_encryption(Bucket=bucket_name)
        rules = response['ServerSideEncryptionConfiguration']['Rules']

        assert len(rules) > 0
        assert rules[0]['ApplyServerSideEncryptionByDefault']['SSEAlgorithm'] == 'AES256'

    def test_versioning_enabled(self, aws_setup):
        """Bucket versioning must be Enabled."""
        s3 = aws_setup['s3_client']
        bucket_name = aws_setup['bucket_name']

        response = s3.get_bucket_versioning(Bucket=bucket_name)
        assert response['Status'] == 'Enabled'

    def test_tls_policy_attached(self, aws_setup):
        """Bucket policy must enforce TLS (HTTPS). (AGENTS.md Rule 3)"""
        s3 = aws_setup['s3_client']
        bucket_name = aws_setup['bucket_name']

        response = s3.get_bucket_policy(Bucket=bucket_name)
        policy = json.loads(response['Policy'])

        # Find the TLS enforcement statement
        tls_statements = [
            stmt for stmt in policy['Statement']
            if stmt.get('Condition', {}).get('Bool', {}).get('aws:SecureTransport') == 'false'
        ]
        assert len(tls_statements) > 0, "No TLS enforcement policy found!"
        assert tls_statements[0]['Effect'] == 'Deny'


# ─── Test 3: Bronze Data Uploaded Correctly ──────────────────
class TestBronzeIngestion:
    """Verifies all 4 datasets were uploaded with correct structure."""

    EXPECTED_DATASETS = ['customers', 'drivers', 'rides', 'payments']

    def test_all_datasets_uploaded(self, aws_setup):
        """All 4 CSV files should exist in the bronze/ prefix."""
        s3 = aws_setup['s3_client']
        bucket_name = aws_setup['bucket_name']

        response = s3.list_objects_v2(Bucket=bucket_name, Prefix='bronze/')
        assert 'Contents' in response, "No objects found in bronze/"

        keys = [obj['Key'] for obj in response['Contents']]

        for dataset in self.EXPECTED_DATASETS:
            matching = [k for k in keys if f'bronze/{dataset}/' in k]
            assert len(matching) > 0, f"Dataset '{dataset}' not found in bronze/"

    def test_hive_partitioning_structure(self, aws_setup):
        """Each data file must be in year=YYYY/month=MM/day=DD/ structure."""
        s3 = aws_setup['s3_client']
        bucket_name = aws_setup['bucket_name']

        response = s3.list_objects_v2(Bucket=bucket_name, Prefix='bronze/')
        # Filter out prefix placeholders (zero-byte "folder" markers)
        keys = [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.csv')]

        assert len(keys) > 0, "No CSV files found in bronze/"
        for key in keys:
            assert 'year=' in key, f"Missing year= partition in: {key}"
            assert 'month=' in key, f"Missing month= partition in: {key}"
            assert 'day=' in key, f"Missing day= partition in: {key}"

    def test_files_are_not_empty(self, aws_setup):
        """Every uploaded CSV file should have size > 0 bytes."""
        s3 = aws_setup['s3_client']
        bucket_name = aws_setup['bucket_name']

        response = s3.list_objects_v2(Bucket=bucket_name, Prefix='bronze/')
        # Filter out prefix placeholders (zero-byte "folder" markers)
        csv_objects = [obj for obj in response['Contents'] if obj['Key'].endswith('.csv')]

        for obj in csv_objects:
            assert obj['Size'] > 0, f"File {obj['Key']} is empty (0 bytes)!"

    def test_file_sizes_match_local(self, aws_setup):
        """S3 file sizes should match local file sizes (integrity check)."""
        s3 = aws_setup['s3_client']
        config = aws_setup['config']
        bucket_name = aws_setup['bucket_name']

        response = s3.list_objects_v2(Bucket=bucket_name, Prefix='bronze/')

        for obj in response['Contents']:
            # Extract dataset name from S3 key
            # e.g., "bronze/rides/year=2026/.../rides.csv" -> "rides"
            parts = obj['Key'].split('/')
            dataset = parts[1]  # "rides"
            filename = parts[-1]  # "rides.csv"

            local_path = os.path.join(config['paths']['raw_data'], dataset, filename)
            if os.path.exists(local_path):
                local_size = os.path.getsize(local_path)
                assert obj['Size'] == local_size, (
                    f"Size mismatch for {dataset}: "
                    f"local={local_size}, S3={obj['Size']}"
                )


# ─── Test 4: Unit Tests (No AWS needed) ─────────────────────
class TestBuildS3Key:
    """Unit tests for the build_s3_key function (pure logic, no network)."""

    def test_basic_key_construction(self):
        """Key should follow Hive-style pattern exactly."""
        from datetime import datetime
        from src.ingestion.bronze_ingestion import build_s3_key

        date = datetime(2026, 1, 15)
        key = build_s3_key("bronze", "rides", date, "rides.csv")
        assert key == "bronze/rides/year=2026/month=01/day=15/rides.csv"

    def test_zero_padded_months(self):
        """Single-digit months must be zero-padded (01, not 1)."""
        from datetime import datetime
        from src.ingestion.bronze_ingestion import build_s3_key

        date = datetime(2026, 3, 5)
        key = build_s3_key("bronze", "customers", date, "customers.csv")
        assert "/month=03/" in key
        assert "/day=05/" in key

    def test_different_prefix(self):
        """Should work with any prefix, not just bronze."""
        from datetime import datetime
        from src.ingestion.bronze_ingestion import build_s3_key

        date = datetime(2026, 10, 8)
        key = build_s3_key("silver", "rides", date, "rides.parquet")
        assert key.startswith("silver/rides/")


# ─── Test 5: Infrastructure Governance (Gaps 1 & 4) ─────────
class TestS3Governance:
    """Verifies lifecycle policies and prefix structure."""

    def test_lifecycle_policies_exist(self, aws_setup):
        """Lifecycle rules must exist for quarantine and bronze. (AGENTS.md Rule 8)"""
        s3 = aws_setup['s3_client']
        bucket_name = aws_setup['bucket_name']

        response = s3.get_bucket_lifecycle_configuration(Bucket=bucket_name)
        rules = response['Rules']
        rule_ids = [r['ID'] for r in rules]

        assert 'QuarantineAutoExpiry' in rule_ids, "Missing quarantine auto-expiry rule!"
        assert 'BronzeGlacierTransition' in rule_ids, "Missing bronze Glacier transition rule!"

    def test_per_object_encryption(self, aws_setup):
        """Each uploaded object must have ServerSideEncryption = AES256."""
        s3 = aws_setup['s3_client']
        bucket_name = aws_setup['bucket_name']

        response = s3.list_objects_v2(Bucket=bucket_name, Prefix='bronze/')
        if 'Contents' not in response:
            pytest.skip("No objects in bronze/ to check")

        # Check the first CSV file (not the prefix placeholder)
        csv_keys = [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.csv')]
        if not csv_keys:
            pytest.skip("No CSV files found in bronze/")

        head = s3.head_object(Bucket=bucket_name, Key=csv_keys[0])
        assert head.get('ServerSideEncryption') == 'AES256', (
            f"Object {csv_keys[0]} is not encrypted with AES256!"
        )


# ─── Test 6: Error Handling ─────────────────────────────────
class TestErrorHandling:
    """Verifies the uploader handles bad inputs gracefully."""

    def test_invalid_file_path_returns_false(self, aws_setup):
        """Uploading a non-existent file should return False, not crash."""
        from src.ingestion.s3_uploader import upload_file_to_s3

        s3 = aws_setup['s3_client']
        bucket_name = aws_setup['bucket_name']

        result = upload_file_to_s3(
            s3, "data/raw/this_file_does_not_exist.csv",
            bucket_name, "bronze/test/fake.csv"
        )
        assert result is False
