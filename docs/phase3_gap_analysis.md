# Phase 3 — Gap Analysis: Plan vs. Build vs. Industry Standard

---

## Category 1: Planned but NOT Implemented

These items were explicitly mentioned in `phase3_planning.md` but we skipped them during the actual build.

### Gap 1: S3 Lifecycle Policies (AGENTS.md Rule 8)
- **Where in plan:** Section 3, Step 3, Lines 417-425
- **What was planned:**
  - `quarantine/` → Auto-delete after 30 days
  - `bronze/` → Move to Glacier (cheap storage) after 90 days
- **What we built:** Nothing. No lifecycle rules applied.
- **Why it matters:** Without lifecycle rules, old quarantine data and raw Bronze data sit in expensive Standard storage forever. On 14M records, this costs ~$0.35/month instead of ~$0.06/month after Glacier transition. More importantly, AGENTS.md Rule 8 explicitly requires retention policies.
- **Impact:** Medium (cost optimization + AGENTS.md compliance)
- **Fix:** Add `put_bucket_lifecycle_configuration()` call to `setup_s3.py`

---

### Gap 2: `file_exists()` Idempotency Check Before Upload
- **Where in plan:** Section 4, Step 4, Line 458 and Step 5, Line 485
- **What was planned:** A function `file_exists(s3_key)` that checks if a file already exists in S3 BEFORE uploading. If it exists, skip the upload (unless `--force` flag is used).
- **What we built:** We upload unconditionally. If the file exists, it gets overwritten silently.
- **Why it matters:** Both approaches are idempotent (no data duplication). But the planned version is MORE EFFICIENT — it avoids re-uploading a 1.7 MB file over the internet when it's already there. In production with 14M records (hundreds of MB), this saves significant time and bandwidth.
- **Impact:** Low for learning, Medium for production
- **Fix:** Add `head_object()` check before `upload_file()` in `s3_uploader.py`

---

### Gap 3: `--date` and `--force` CLI Arguments
- **Where in plan:** Section 4, Step 6, Lines 515-516
- **What was planned:**
  - `python main.py upload-bronze --date 2026-01-15` (upload to a specific date partition)
  - `python main.py upload-bronze --force` (re-upload even if files exist)
- **What we built:** No arguments. Always uploads to today's date, always overwrites.
- **Why it matters:** `--date` is critical for backfilling historical data. If you need to re-process data from January, you need to tell the script to upload to the January partition, not today's partition.
- **Impact:** Medium (needed for backfill scenarios)
- **Fix:** Add `argparse` arguments to `upload-bronze` subparser in `main.py`

---

### Gap 4: Prefix Structure Pre-Creation
- **Where in plan:** Section 4, Step 3, Line 414
- **What was planned:** `setup_s3.py` should create empty "folder" markers for `bronze/`, `silver/`, `gold/`, `quarantine/` after bucket creation.
- **What we built:** No prefix pre-creation. The folders only appear when data is uploaded.
- **Why it matters:** Low impact. S3 doesn't actually have "folders" — prefixes are created automatically when you upload a file. However, pre-creating them makes the bucket look organized in the AWS Console even before any data is uploaded.
- **Impact:** Low (cosmetic)
- **Fix:** Add 4x `put_object()` calls with empty bodies to create placeholder markers

---

### Gap 5: Tests — Missing Specific Test Cases
- **Where in plan:** Section 4, Step 9, Lines 596-603
- **What was planned:** 7 specific tests including:
  - `test_build_bronze_key` (unit test for the key construction function)
  - `test_upload_idempotent` (run upload twice, verify no duplicates)
  - `test_encryption_enabled` (verify uploaded OBJECT has encryption header)
  - `test_invalid_file_path` (verify error handling for missing files)
- **What we built:** 9 tests, but different ones. We tested bucket-level security and data integrity. We did NOT test:
  - The `build_s3_key()` function in isolation
  - Idempotency (uploading twice)
  - Per-object encryption headers
  - Error handling for invalid file paths
- **Impact:** Medium (testing gaps)

---

### Gap 6: Screenshots Directory for Portfolio Evidence
- **Where in plan:** Section 11, Checklist 7, Lines 887-904
- **What was planned:** Create `docs/screenshots/phase3/` and capture 7 specific screenshots from the AWS Console for interview evidence.
- **What we built:** Nothing. No screenshots directory, no evidence captured.
- **Impact:** High for interviews (recruiters want visual proof)
- **Fix:** Create the directory and capture screenshots via browser

---

### Gap 7: `.gitignore` Verification for AWS Credentials
- **Where in plan:** Section 11, Checklist 0, Lines 786-800
- **What was planned:** Verify that `.aws/` and `credentials` are in `.gitignore` so secret keys never get pushed to GitHub.
- **What we built:** Never verified this.
- **Impact:** HIGH (security risk — if credentials leak to GitHub, your AWS account is compromised)
- **Fix:** Check and update `.gitignore` immediately

---

## Category 2: NOT Planned AND NOT Implemented (Industry Standard Gaps)

These are practices found in production-grade data pipelines that were missing from both our plan AND our build.

### Industry Gap 1: Structured Logging (JSON Audit Logs)
- **What it is:** Instead of `print("SUCCESS")`, production pipelines emit structured JSON log entries like:
  ```json
  {"timestamp": "2026-10-08T19:24:26Z", "event": "file_uploaded", "dataset": "rides", "s3_key": "bronze/rides/...", "file_size_bytes": 1729378, "duration_seconds": 2.3, "pipeline_run_id": "run-abc123"}
  ```
- **Why it matters:** AGENTS.md Rule 8 explicitly says "pipeline operations emit structured JSON audit logs." Our scripts use plain `print()` statements. In production, these JSON logs feed into monitoring tools (CloudWatch, Datadog) for alerting and debugging. They also serve as the "lineage tracking" required by AGENTS.md Rule 6.
- **Impact:** High (AGENTS.md compliance + observability)

---

### Industry Gap 2: Pipeline Run ID / Batch ID (Lineage Tracking)
- **What it is:** Every time you run `upload-bronze`, the script should generate a unique ID (like `run-20261008-193000-abc123`) and tag every uploaded file with it.
- **Why it matters:** AGENTS.md Rule 6 says "Record source origin, pipeline run ID, job timestamps, and transformation lineage on every batch." If something goes wrong in Silver, you need to trace back: "Which Bronze batch caused this?" Without a Run ID, you have no way to connect a Silver problem to a specific Bronze upload.
- **Impact:** High (AGENTS.md compliance + debugging)

---

### Industry Gap 3: S3 Object Tagging (Metadata)
- **What it is:** When uploading to S3, you can attach key-value tags to each file:
  ```python
  s3.put_object_tagging(
      Bucket=bucket, Key=key,
      Tagging={'TagSet': [
          {'Key': 'pipeline_run_id', 'Value': 'run-abc123'},
          {'Key': 'source', 'Value': 'local_csv'},
          {'Key': 'contains_pii', 'Value': 'true'}
      ]}
  )
  ```
- **Why it matters:** Tags allow you to search, audit, and apply policies to specific files. For example: "Delete all files tagged `contains_pii=true` that are older than 90 days." This directly supports AGENTS.md Rule 4 (PII handling) and Rule 8 (retention).
- **Impact:** Medium (data governance)

---

### Industry Gap 4: Upload Retry Logic (Exponential Backoff)
- **What it is:** If an upload fails due to a network glitch, the script should automatically retry 3 times with increasing wait times (1s, 2s, 4s) before giving up.
- **Why it matters:** On a home Wi-Fi connection uploading 14M records, you WILL hit occasional network timeouts. Without retry logic, the entire pipeline crashes and you have to restart manually. With retry logic, transient failures are handled silently.
- **Impact:** Medium (reliability)

---

### Industry Gap 5: Checksum Verification (MD5/SHA-256)
- **What it is:** Instead of just comparing file sizes (which we do), compute a cryptographic hash (MD5 or SHA-256) of the local file and compare it to the S3 object's ETag.
- **Why it matters:** Two files can have the exact same size but completely different content (e.g., a corrupted file that's the right number of bytes but wrong data). Size matching catches gross corruption; checksum matching catches subtle corruption.
- **Impact:** Low-Medium (our size check covers 99% of cases)

---

## Summary Table

| # | Gap | Source | Impact | Fix Effort |
|:-:|-----|--------|:------:|:----------:|
| 1 | S3 Lifecycle Policies | Plan ✅ Build ❌ | Medium | 15 min |
| 2 | `file_exists()` check | Plan ✅ Build ❌ | Low-Med | 10 min |
| 3 | `--date` / `--force` flags | Plan ✅ Build ❌ | Medium | 15 min |
| 4 | Prefix pre-creation | Plan ✅ Build ❌ | Low | 5 min |
| 5 | Missing test cases | Plan ✅ Build ❌ | Medium | 20 min |
| 6 | Screenshots directory | Plan ✅ Build ❌ | High | 15 min |
| 7 | `.gitignore` verification | Plan ✅ Build ❌ | **HIGH** | 2 min |
| 8 | Structured JSON logging | Plan ❌ Build ❌ | High | 30 min |
| 9 | Pipeline Run ID | Plan ❌ Build ❌ | High | 20 min |
| 10 | S3 Object Tagging | Plan ❌ Build ❌ | Medium | 15 min |
| 11 | Upload retry logic | Plan ❌ Build ❌ | Medium | 15 min |
| 12 | Checksum verification | Plan ❌ Build ❌ | Low-Med | 10 min |
