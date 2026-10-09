"""
Teardown Script — The "Emergency Exit" / Clean Slate

PURPOSE:
    Completely removes the S3 bucket and ALL objects inside it.
    Use this when you want to:
    1. Start fresh (corrupted data, wrong partition structure)
    2. Stop AWS charges (delete everything after taking screenshots)
    3. Clean up after the project is complete

WHY THIS FILE EXISTS (Build Order):
    This file DEPENDS ON:
    - config/config.yaml (to know which bucket to delete)
    - src/ingestion/s3_uploader.py (to reuse the get_s3_client function)
    
    We build teardown BEFORE IAM policies (Step 7) so we always have
    an escape hatch if something goes wrong.

IMPORTANT S3 RULE:
    You CANNOT delete a bucket that still has objects in it.
    You must delete all objects AND all version markers first.
    This script handles that automatically.

SAFETY:
    This script asks for confirmation before deleting anything.
    It prints exactly what it will delete so you can verify.
"""

import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingestion.s3_uploader import load_config, get_s3_client


def teardown_s3():
    """
    What this does step by step:
    1. Reads config to get bucket name
    2. Asks for user confirmation (safety measure)
    3. Lists all objects in the bucket
    4. Deletes all objects (including version markers)
    5. Deletes the empty bucket itself
    6. Verifies the bucket no longer exists
    """
    config = load_config()
    bucket_name = config['s3']['bucket_name']

    print("=" * 65)
    print("  S3 TEARDOWN - DELETE EVERYTHING")
    print("=" * 65)
    print(f"  Bucket: {bucket_name}")
    print(f"  Region: {config['aws']['region']}")
    print("=" * 65)

    # --- Safety Confirmation ---
    # In production, you'd use proper CLI argument parsing.
    # For learning, a simple input() prompt prevents accidental deletion.
    print("\n  WARNING: This will PERMANENTLY delete the bucket and ALL data.")
    confirm = input("  Type 'DELETE' to confirm: ")

    if confirm != 'DELETE':
        print("  Aborted. Nothing was deleted.")
        return

    s3_client = get_s3_client(config)

    # --- Step 1: Delete all objects ---
    # We use list_objects_v2() to get every object in the bucket.
    # "v2" is the newer version of the API — it handles large buckets better
    # by paginating (returning 1000 objects at a time).
    print("\n[*] Deleting all objects in the bucket...")
    
    try:
        # Paginator handles buckets with more than 1000 objects automatically.
        # Without it, list_objects_v2 only returns the first 1000 objects,
        # and you'd silently leave the rest behind.
        paginator = s3_client.get_paginator('list_objects_v2')
        
        total_deleted = 0
        for page in paginator.paginate(Bucket=bucket_name):
            if 'Contents' not in page:
                break
            
            # Build a batch delete request (faster than deleting one by one)
            objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
            
            s3_client.delete_objects(
                Bucket=bucket_name,
                Delete={'Objects': objects_to_delete}
            )
            total_deleted += len(objects_to_delete)
            print(f"    Deleted {total_deleted} objects so far...")

        print(f"    [SUCCESS] Deleted {total_deleted} objects total.")

    except Exception as e:
        print(f"    [ERROR] Failed to delete objects: {e}")
        sys.exit(1)

    # --- Step 2: Delete all version markers (required because we enabled versioning) ---
    # When versioning is ON, deleting an object doesn't actually remove it —
    # it creates a "delete marker." To truly wipe the bucket, we must also
    # remove these markers and any old versions of objects.
    print("\n[*] Deleting version markers (from versioning)...")
    
    try:
        paginator = s3_client.get_paginator('list_object_versions')
        
        total_versions = 0
        for page in paginator.paginate(Bucket=bucket_name):
            versions_to_delete = []
            
            # Delete all versions of every object
            for version in page.get('Versions', []):
                versions_to_delete.append({
                    'Key': version['Key'],
                    'VersionId': version['VersionId']
                })
            
            # Delete all "delete markers" (the invisible tombstones)
            for marker in page.get('DeleteMarkers', []):
                versions_to_delete.append({
                    'Key': marker['Key'],
                    'VersionId': marker['VersionId']
                })
            
            if versions_to_delete:
                s3_client.delete_objects(
                    Bucket=bucket_name,
                    Delete={'Objects': versions_to_delete}
                )
                total_versions += len(versions_to_delete)

        print(f"    [SUCCESS] Deleted {total_versions} version markers.")

    except Exception as e:
        print(f"    [ERROR] Failed to delete versions: {e}")
        sys.exit(1)

    # --- Step 3: Delete the empty bucket ---
    print(f"\n[*] Deleting bucket: {bucket_name}...")
    
    try:
        s3_client.delete_bucket(Bucket=bucket_name)
        print(f"    [SUCCESS] Bucket {bucket_name} deleted.")
    except Exception as e:
        print(f"    [ERROR] Failed to delete bucket: {e}")
        sys.exit(1)

    print("\n" + "=" * 65)
    print("  TEARDOWN COMPLETE")
    print("  All AWS resources for this project have been removed.")
    print("  Your AWS bill for S3 will stop accumulating.")
    print("=" * 65)


if __name__ == "__main__":
    teardown_s3()
