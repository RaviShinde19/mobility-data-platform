"""
main.py — Entry Point for the Mobility Data Platform
═════════════════════════════════════════════════════

This is the single entry point for running the data platform.

Usage:
    python main.py generate     # Generate synthetic data
    python main.py --help       # Show available commands

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

Phase 1 Commands:
  generate    Generate synthetic data (customers, drivers, rides, payments)
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Pipeline command to run")

    # ── Generate command ──────────────────────────────────────
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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # ── Load configuration ────────────────────────────────────
    config = ConfigLoader.load(args.config)
    logger = setup_logger("main", config)

    logger.info(f"Mobility Data Platform — Command: {args.command}")
    logger.info(f"Started at: {datetime.now().isoformat()}")

    # ── Dispatch to command handler ───────────────────────────
    if args.command == "generate":
        # Override ride count if specified
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

    else:
        logger.error(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
