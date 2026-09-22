"""
connection.py — PostgreSQL Connection Manager
══════════════════════════════════════════════

WHY THIS EXISTS:
────────────────
Every database query needs a connection (a network link between
Python and PostgreSQL). This module provides a clean, reusable
way to get connections without repeating boilerplate code.

DESIGN DECISIONS:
─────────────────
1. Context manager pattern — connections are automatically closed
   even if your code throws an error. No leaked connections.

2. Credentials from environment variables — AGENTS.md Rule 1
   says "Zero Hardcoded Secrets." We read from .env / env vars.

3. Config fallback — non-sensitive defaults (host, port, db name)
   come from config.yaml so there's one source of truth.

4. Transaction management — autocommit=False by default.
   You commit when ready, rollback on error. This prevents
   partial data writes (e.g., half of a CSV loaded).

USAGE:
──────
    from src.database.connection import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM customers;")
            print(cur.fetchone()[0])
    # Connection is automatically returned/closed here

SCALING NOTE:
─────────────
  Current: Simple get_connection() — one connection per call
  Medium:  psycopg2.pool.ThreadedConnectionPool — reuse connections
  Large:   PgBouncer (external connection pooler) — thousands of clients
"""

import os
from contextlib import contextmanager

import psycopg2
from dotenv import load_dotenv

from src.utils.config_loader import ConfigLoader
from src.utils.logger import setup_logger


# Load .env files — checks both project root and docker/ directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', 'docker', '.env'))


def _get_db_config() -> dict:
    """
    Build database connection parameters from environment + config.

    Priority order:
      1. Environment variables (POSTGRES_HOST, POSTGRES_PORT, etc.)
      2. config.yaml database section
      3. Hardcoded defaults (localhost, 5432)

    Returns dict with keys: host, port, dbname, user, password
    """
    # Try to load config.yaml for non-sensitive defaults
    try:
        config = ConfigLoader.load()
        db_config = config.get("database") or {}
    except Exception:
        db_config = {}

    return {
        "host": os.getenv("POSTGRES_HOST", db_config.get("host", "localhost")),
        "port": int(os.getenv("POSTGRES_PORT", db_config.get("port", 5432))),
        "dbname": os.getenv("POSTGRES_DB", db_config.get("dbname", "mobility_db")),
        "user": os.getenv("POSTGRES_USER", db_config.get("user", "mobility_admin")),
        "password": os.getenv("POSTGRES_PASSWORD", db_config.get("password", "")),
    }


@contextmanager
def get_connection(autocommit: bool = False):
    """
    Context manager that provides a PostgreSQL connection.

    Usage:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")

    Args:
        autocommit: If True, each statement is committed immediately.
                    If False (default), you must call conn.commit() explicitly.
                    Use autocommit=True for DDL statements (CREATE TABLE).
                    Use autocommit=False for data loading (so you can rollback).

    Yields:
        psycopg2 connection object

    Raises:
        psycopg2.OperationalError: If connection fails (DB not running, wrong creds)
    """
    config = _get_db_config()
    logger = setup_logger("database.connection")

    conn = None
    try:
        conn = psycopg2.connect(**config)
        conn.autocommit = autocommit

        logger.debug(
            f"Connected to PostgreSQL: {config['host']}:{config['port']}"
            f"/{config['dbname']} as {config['user']}"
        )

        yield conn

    except psycopg2.OperationalError as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        logger.error(
            "Is the Docker container running? Try:\n"
            "  docker compose -f docker/docker-compose.yml up -d"
        )
        raise
    except Exception as e:
        # Rollback any uncommitted changes on error
        if conn and not conn.closed and not autocommit:
            conn.rollback()
            logger.warning("Transaction rolled back due to error")
        raise
    finally:
        if conn and not conn.closed:
            conn.close()
            logger.debug("Connection closed")


def test_connection() -> bool:
    """
    Quick health check — can we connect and run a simple query?

    Returns True if connection is healthy, False otherwise.
    """
    logger = setup_logger("database.connection")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                logger.info(f"PostgreSQL connection OK: {version[:50]}...")
                return True
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False
