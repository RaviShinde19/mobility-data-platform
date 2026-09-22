"""
main.py — Entry Point for the Mobility Data Platform
═════════════════════════════════════════════════════

This is the single entry point for running the data platform.

Usage:
    python main.py generate        # Generate synthetic data
    python main.py load-postgres   # Load data into PostgreSQL
    python main.py --help          # Show available commands

DESIGN PATTERN — CLI Entry Point:
─────────────────────────────────
In production data platforms, the entry point typically:
  1. Parses command-line arguments
  2. Loads configuration
  3. Sets up logging
  4. Dispatches to the appropriate pipeline step

As we add phases, this file grows:
  Phase 1: python main.py generate
  Phase 2: python main.py load-postgres
  Phase 3: python main.py upload-bronze
  Phase 4: python main.py transform-silver
  Phase 5: python main.py transform-gold
  ...

This keeps the entry point consistent across all phases.
"""

import sys
import argparse
from datetime import datetime

from src.utils.config_loader import ConfigLoader
from src.utils.logger import setup_logger
from src.data_generator.generator import run_data_generation


def main():
    parser = argparse.ArgumentParser(
        description="Mobility Data Platform — Data Engineering Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py generate              Generate synthetic mobility data
  python main.py generate --count 50000  Generate with custom ride count
  python main.py load-postgres          Load data into PostgreSQL

Phase 1 Commands:
  generate        Generate synthetic data (customers, drivers, rides, payments)

Phase 2 Commands:
  load-postgres   Create tables, load data, set up RBAC roles
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Pipeline command to run")

    # ── Phase 1: Generate command ────────────────────────────
    gen_parser = subparsers.add_parser(
        "generate",
        help="Generate synthetic mobility data"
    )
    gen_parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config YAML file (default: config/config.yaml)"
    )
    gen_parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Override number of rides to generate"
    )

    # ── Phase 2: Load PostgreSQL command ─────────────────────
    pg_parser = subparsers.add_parser(
        "load-postgres",
        help="Create PostgreSQL tables, load CSV data, set up RBAC"
    )
    pg_parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config YAML file"
    )
    pg_parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Path to data/raw/ directory (default: data/raw)"
    )
    pg_parser.add_argument(
        "--skip-rbac",
        action="store_true",
        help="Skip RBAC role creation"
    )
    pg_parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all tables before creating (clean slate)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # ── Load configuration ────────────────────────────────────
    config_path = getattr(args, 'config', None)
    config = ConfigLoader.load(config_path)
    logger = setup_logger("main", config)

    logger.info(f"Mobility Data Platform — Command: {args.command}")
    logger.info(f"Started at: {datetime.now().isoformat()}")

    # ── Dispatch to command handler ───────────────────────────
    if args.command == "generate":
        _handle_generate(args, config, logger)

    elif args.command == "load-postgres":
        _handle_load_postgres(args, config, logger)

    else:
        logger.error(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


def _handle_generate(args, config, logger):
    """Handle the 'generate' command (Phase 1)."""
    if args.count:
        config._instance["data_generation"]["num_rides"] = args.count
        logger.info(f"Ride count overridden to: {args.count}")

    summary = run_data_generation(config)

    print("\n" + "=" * 50)
    print("  DATA GENERATION SUMMARY")
    print("=" * 50)
    print(f"  Customers : {summary['customers_generated']:,}")
    print(f"  Drivers   : {summary['drivers_generated']:,}")
    print(f"  Rides     : {summary['rides_generated']:,}")
    print(f"  Payments  : {summary['payments_generated']:,}")
    print(f"  Time      : {summary['elapsed_seconds']}s")
    print(f"  Output    : {summary['output_dir']}")
    print("=" * 50)


def _handle_load_postgres(args, config, logger):
    """Handle the 'load-postgres' command (Phase 2)."""
    # Import here to avoid ImportError if psycopg2 isn't installed
    from src.database.connection import test_connection
    from src.database.schema import create_tables, create_roles, drop_all_tables
    from src.database.loader import load_all_tables, get_row_counts

    start_time = datetime.now()

    # Step 0: Test connection
    print("\n" + "=" * 60)
    print("  PHASE 2: PostgreSQL Data Loading Pipeline")
    print("=" * 60)

    print("\n[1/4] Testing database connection...")
    if not test_connection():
        print("\n❌ Cannot connect to PostgreSQL!")
        print("   Make sure Docker is running:")
        print("   docker compose -f docker/docker-compose.yml up -d")
        sys.exit(1)
    print("  ✓ Connection successful\n")

    # Step 1: Optional reset
    if args.reset:
        print("[1.5/4] Dropping existing tables (--reset)...")
        dropped = drop_all_tables()
        print(f"  ✓ Dropped: {', '.join(dropped)}\n")

    # Step 2: Create tables
    print("[2/4] Creating tables...")
    schema_result = create_tables()
    if schema_result["tables_created"]:
        print(f"  ✓ Created: {', '.join(schema_result['tables_created'])}")
    if schema_result["already_existed"]:
        print(f"  ℹ Already existed: {', '.join(schema_result['already_existed'])}")
    print(f"  Total tables: {schema_result['total_tables']}\n")

    # Step 3: Load data
    print("[3/4] Loading data from CSV files...")
    load_result = load_all_tables(data_dir=args.data_dir)

    print()
    for table, info in load_result["results"].items():
        status = "✓" if info["rejected"] == 0 else "⚠"
        print(f"  {status} {table:12s}: {info['loaded']:>6,} loaded, {info['rejected']:>4,} rejected (of {info['staged']:,} staged)")
        for reason, count in info["reasons"].items():
            print(f"    └─ {reason}: {count:,}")

    print(f"\n  Total loaded:   {load_result['total_loaded']:,}")
    print(f"  Total rejected: {load_result['total_rejected']:,}")

    # Step 4: RBAC
    if not args.skip_rbac:
        print("\n[4/4] Setting up RBAC roles...")
        rbac_result = create_roles()
        print(f"  ✓ Roles: {', '.join(rbac_result['roles'])}")
        print(f"  ✓ Aggregated views created for bi_reader")
    else:
        print("\n[4/4] RBAC skipped (--skip-rbac)")

    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    counts = get_row_counts()

    print("\n" + "=" * 60)
    print("  POSTGRESQL LOAD SUMMARY")
    print("=" * 60)
    print(f"  Tables      : {schema_result['total_tables']}")
    for table, count in counts.items():
        print(f"  {table:12s}: {count:>6,} rows")
    print(f"  Rejected    : {load_result['total_rejected']:,} rows (bad data caught)")
    if not args.skip_rbac:
        print(f"  RBAC roles  : {', '.join(rbac_result['roles'])}")
    print(f"  Time        : {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()

