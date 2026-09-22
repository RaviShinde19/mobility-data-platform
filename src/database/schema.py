"""
schema.py — Database Schema Manager
═════════════════════════════════════

WHY THIS EXISTS:
────────────────
Reads SQL DDL files and executes them against PostgreSQL to
create (or verify) the table structure. Wraps the raw SQL
execution with logging, error handling, and idempotency.

DESIGN DECISIONS:
─────────────────
1. Reads SQL from file (not inline Python strings)
   → SQL stays in sql/ddl/ where DBAs and tools expect it
   → Syntax highlighting works in .sql files
   → Same DDL can be run directly via psql if needed

2. IF NOT EXISTS everywhere
   → Safe to run multiple times without errors
   → Tables are only created if they don't already exist

3. Autocommit=True for DDL
   → PostgreSQL auto-commits DDL anyway (CREATE TABLE can't
     be rolled back), so we make it explicit
"""

import os

from src.database.connection import get_connection
from src.utils.logger import setup_logger

# Path to SQL DDL files (relative to project root)
SQL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'sql', 'ddl')


def create_tables(sql_file: str = None) -> dict:
    """
    Execute the CREATE TABLE DDL script.

    Args:
        sql_file: Path to SQL file. Defaults to sql/ddl/create_tables.sql

    Returns:
        dict with keys: tables_created (list), already_existed (list)
    """
    logger = setup_logger("database.schema")

    if sql_file is None:
        sql_file = os.path.join(SQL_DIR, 'create_tables.sql')

    logger.info(f"Reading DDL from: {sql_file}")

    if not os.path.exists(sql_file):
        raise FileNotFoundError(f"DDL file not found: {sql_file}")

    with open(sql_file, 'r', encoding='utf-8') as f:
        ddl_sql = f.read()

    # Get tables BEFORE running DDL
    existing_before = _get_existing_tables()

    with get_connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(ddl_sql)
            logger.info("DDL script executed successfully")

    # Get tables AFTER running DDL
    existing_after = _get_existing_tables()

    # Figure out what was created vs already existed
    new_tables = existing_after - existing_before
    already_existed = existing_before & existing_after

    result = {
        "tables_created": sorted(list(new_tables)),
        "already_existed": sorted(list(already_existed)),
        "total_tables": len(existing_after),
    }

    if new_tables:
        logger.info(f"Created {len(new_tables)} new table(s): {', '.join(sorted(new_tables))}")
    if already_existed:
        logger.info(f"{len(already_existed)} table(s) already existed: {', '.join(sorted(already_existed))}")

    logger.info(f"Total tables in database: {len(existing_after)}")

    return result


def create_roles(sql_file: str = None) -> dict:
    """
    Execute the RBAC role creation script.

    Args:
        sql_file: Path to SQL file. Defaults to sql/ddl/create_roles.sql

    Returns:
        dict with keys: roles (list of role names)
    """
    logger = setup_logger("database.schema")

    if sql_file is None:
        sql_file = os.path.join(SQL_DIR, 'create_roles.sql')

    logger.info(f"Reading RBAC script from: {sql_file}")

    if not os.path.exists(sql_file):
        raise FileNotFoundError(f"RBAC SQL file not found: {sql_file}")

    with open(sql_file, 'r', encoding='utf-8') as f:
        rbac_sql = f.read()

    with get_connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(rbac_sql)
            logger.info("RBAC script executed successfully")

    # Verify roles were created
    roles = _get_custom_roles()

    result = {
        "roles": sorted(list(roles)),
        "total_roles": len(roles),
    }

    logger.info(f"Active roles: {', '.join(sorted(roles))}")

    return result


def drop_all_tables() -> list:
    """
    Drop all project tables (for reset/re-creation).

    Drops in reverse dependency order:
      payments → rides → drivers, customers

    Returns list of dropped table names.
    """
    logger = setup_logger("database.schema")

    # Order matters — drop dependents first
    tables_to_drop = ["payments", "rides", "drivers", "customers"]
    dropped = []

    with get_connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            for table in tables_to_drop:
                cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                dropped.append(table)
                logger.info(f"Dropped table: {table}")

    return dropped


def get_table_info() -> dict:
    """
    Get column info for all tables in the database.

    Returns dict mapping table_name → list of (column_name, data_type, is_nullable)
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name IN ('customers', 'drivers', 'rides', 'payments')
                ORDER BY table_name, ordinal_position;
            """)
            rows = cur.fetchall()

    result = {}
    for table_name, col_name, data_type, nullable in rows:
        if table_name not in result:
            result[table_name] = []
        result[table_name].append({
            "column": col_name,
            "type": data_type,
            "nullable": nullable == "YES",
        })

    return result


def _get_existing_tables() -> set:
    """Get set of table names in the public schema."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
            """)
            return {row[0] for row in cur.fetchall()}


def _get_custom_roles() -> set:
    """Get set of non-system role names."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rolname FROM pg_roles
                WHERE rolname IN ('etl_writer', 'data_analyst', 'bi_reader');
            """)
            return {row[0] for row in cur.fetchall()}
