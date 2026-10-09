import sys
import os
import yaml
import boto3
from botocore.exceptions import ClientError
import json

# Add the project root to the Python path so we can import config if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def create_s3_bucket():
    """
    Step-by-step S3 Setup:
    1. Reads configuration from config.yaml
    2. Initializes boto3 client (which automatically reads your ~/.aws/credentials)
    3. Creates the bucket
    4. Applies security policies (Encryption, Public Access Block, TLS enforcement)
    """
    config = load_config()
    
    bucket_name = config['s3']['bucket_name']
    region = config['aws']['region']
    use_localstack = config['aws']['use_localstack']

    # 1. Initialize the boto3 client
    print(f"[*] Initializing boto3 client for region: {region}...")
    if use_localstack:
        s3_client = boto3.client('s3', endpoint_url=config['aws']['localstack_endpoint'], region_name=region)
        print("    (Using LocalStack endpoint)")
    else:
        s3_client = boto3.client('s3', region_name=region)
        print("    (Using Real AWS)")

    # 2. Create the Bucket
    print(f"\n[*] Attempting to create bucket: {bucket_name}")
    try:
        # Note: us-east-1 does not require LocationConstraint, but ap-south-1 does!
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        print(f"    [SUCCESS] Bucket {bucket_name} created.")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'BucketAlreadyOwnedByYou':
            print(f"    [INFO] Bucket {bucket_name} already exists and is owned by you. Skipping creation.")
        else:
            print(f"    [ERROR] Failed to create bucket: {e}")
            sys.exit(1)

    # 3. Apply Security Rule: Block Public Access
    print("\n[*] Applying Security: Blocking Public Access...")
    s3_client.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            'BlockPublicAcls': True,
            'IgnorePublicAcls': True,
            'BlockPublicPolicy': True,
            'RestrictPublicBuckets': True
        }
    )
    print("    [SUCCESS] All public access blocked.")

    # 4. Apply Security Rule: Default Encryption (SSE-S3)
    print("\n[*] Applying Security: Default AES256 Encryption...")
    s3_client.put_bucket_encryption(
        Bucket=bucket_name,
        ServerSideEncryptionConfiguration={
            'Rules': [
                {
                    'ApplyServerSideEncryptionByDefault': {
                        'SSEAlgorithm': 'AES256'
                    },
                    'BucketKeyEnabled': True
                }
            ]
        }
    )
    print("    [SUCCESS] SSE-S3 Encryption enabled.")

    # 5. Apply Security Rule: Enforce TLS (HTTPS) via Bucket Policy
    print("\n[*] Applying Security: Enforcing TLS (HTTPS) transit...")
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "EnforceTLSRequestsOnly",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}",
                    f"arn:aws:s3:::{bucket_name}/*"
                ],
                "Condition": {
                    "Bool": {
                        "aws:SecureTransport": "false"
                    }
                }
            }
        ]
    }
    s3_client.put_bucket_policy(
        Bucket=bucket_name,
        Policy=json.dumps(bucket_policy)
    )
    print("    [SUCCESS] TLS-only Bucket Policy attached.")

    # 6. Apply Data Governance: Enable Versioning
    print("\n[*] Applying Governance: Enabling Object Versioning...")
    s3_client.put_bucket_versioning(
        Bucket=bucket_name,
        VersioningConfiguration={'Status': 'Enabled'}
    )
    print("    [SUCCESS] Versioning enabled.")

    # 7. Apply Data Governance: S3 Lifecycle Policies (AGENTS.md Rule 8)
    # Lifecycle rules automate cost management and data retention.
    # Without these, old quarantine data and raw Bronze data sit in
    # expensive Standard storage forever.
    print("\n[*] Applying Governance: S3 Lifecycle Policies...")
    s3_client.put_bucket_lifecycle_configuration(
        Bucket=bucket_name,
        LifecycleConfiguration={
            'Rules': [
                {
                    # Quarantine data that hasn't been investigated in 30 days
                    # is unlikely to ever be investigated. Auto-delete it.
                    'ID': 'QuarantineAutoExpiry',
                    'Filter': {'Prefix': 'quarantine/'},
                    'Status': 'Enabled',
                    'Expiration': {'Days': 30}
                },
                {
                    # Bronze raw data is rarely re-read once Silver is built.
                    # Move it to Glacier (cheap deep-freeze storage) after 90 days.
                    # Glacier costs ~$0.004/GB vs Standard's $0.023/GB (83% cheaper).
                    'ID': 'BronzeGlacierTransition',
                    'Filter': {'Prefix': 'bronze/'},
                    'Status': 'Enabled',
                    'Transitions': [
                        {
                            'Days': 90,
                            'StorageClass': 'GLACIER'
                        }
                    ]
                }
            ]
        }
    )
    print("    [SUCCESS] Lifecycle: quarantine/ -> delete after 30d, bronze/ -> Glacier after 90d.")

    # 8. Pre-create prefix "folders" for all medallion layers
    # S3 doesn't have real folders, but creating zero-byte objects with
    # trailing slashes makes the bucket look organized in the AWS Console
    # even before any data is uploaded.
    print("\n[*] Pre-creating medallion layer prefixes...")
    for prefix in ['bronze/', 'silver/', 'gold/', 'quarantine/']:
        s3_client.put_object(Bucket=bucket_name, Key=prefix, Body=b'')
        print(f"    [SUCCESS] Created prefix: {prefix}")

    print(f"\n[DONE] S3 Setup Complete! Your Data Lake ({bucket_name}) is ready.")

if __name__ == "__main__":
    create_s3_bucket()
