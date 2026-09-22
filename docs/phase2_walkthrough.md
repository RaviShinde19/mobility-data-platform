# Phase 2 — Walkthrough & What You Learned

## What Was Built

| Component | File(s) | Purpose |
|-----------|---------|---------|
| Docker Compose | `docker/docker-compose.yml` | Runs PostgreSQL 16 in a container |
| Credentials | `docker/.env` + `.env.example` | Password management (gitignored) |
| Table DDL | `sql/ddl/create_tables.sql` | 4 tables, 4 FKs, 8 CHECKs, 13 indexes |
| RBAC SQL | `sql/ddl/create_roles.sql` | 3 roles + 4 aggregated views |
| Sample queries | `sql/queries/sample_queries.sql` | 10 business analytical queries |
| Connection manager | `src/database/connection.py` | Context-manager PostgreSQL connections |
| Schema manager | `src/database/schema.py` | DDL execution with idempotency |
| Data loader | `src/database/loader.py` | Staging → validate → load pattern |
| CLI command | `main.py` → `load-postgres` | One command runs everything |
| Integration tests | `tests/test_database.py` | 25 tests covering all aspects |

## Final Results

```
============================================================
  POSTGRESQL LOAD SUMMARY
============================================================
  Tables      : 4
  customers   :    998 rows  (2 rejected — duplicate emails)
  drivers     :    500 rows  (0 rejected)
  rides       :  9,780 rows  (220 rejected — bad data caught)
  payments    :  7,790 rows  (175 rejected — orphan references)
  Total       : 19,068 loaded, 397 rejected
  RBAC roles  : bi_reader, data_analyst, etl_writer
  Time        : 1.9s
============================================================

Tests: 52/52 passed (27 Phase 1 + 25 Phase 2)
```

## Bugs We Hit & Fixed (Real Learning)

### Bug 1: Docker Hub timeout
- **Problem**: ISP throttling Docker Hub → image download timed out
- **Fix**: Changed DNS to Google (8.8.8.8), added registry mirror, used mobile hotspot
- **Lesson**: Network issues are the #1 DevOps headache. Always have fallback DNS/mirrors.

### Bug 2: Unicode encoding on Windows
- **Problem**: `✓` character can't be printed by Windows `cp1252` console
- **Fix**: Set `PYTHONIOENCODING=utf-8` before running
- **Lesson**: Always consider the output encoding of your target environment.

### Bug 3: Duplicate email UNIQUE violation
- **Problem**: CSV had 2 customers with the same email → UNIQUE constraint rejected the INSERT
- **Fix**: Added `DISTINCT ON (email)` to the staging INSERT query
- **Lesson**: Source data always has duplicates. Your staging pattern must handle dedup.

## Key Concepts You Now Understand

1. **Docker** — Images, containers, volumes, port mapping, health checks
2. **SQL DDL** — CREATE TABLE with types, constraints (PK, FK, CHECK, UNIQUE)
3. **COPY vs INSERT** — Bulk loading is 40-100x faster than row-by-row
4. **Staging pattern** — Load everything → validate → insert valid rows → log rejects
5. **Cascading rejections** — 220 rejected rides caused 175 payment rejections downstream
6. **RBAC** — etl_writer (full), data_analyst (read-only), bi_reader (views only)
7. **Idempotency** — `IF NOT EXISTS` + TRUNCATE → safe to re-run without errors
8. **Context managers** — `with get_connection() as conn:` auto-closes connections
