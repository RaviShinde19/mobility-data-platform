"""
logger.py — Centralized Logging Setup
══════════════════════════════════════

WHY THIS EXISTS:
────────────────
In a data pipeline, logging is NOT optional. When a pipeline processes
10,000 rides and 47 fail, you need to know:
  - WHICH 47 failed?
  - WHY did they fail?
  - WHEN did the failure happen?
  - Which STAGE of the pipeline was running?

print() statements don't give you any of this. Proper logging gives you:
  1. Timestamps — when things happened
  2. Log levels — INFO vs WARNING vs ERROR (filter noise)
  3. Module names — which component logged the message
  4. File output — survives terminal closure, searchable later
  5. Structured format — parseable by log aggregation tools

INFRASTRUCTURE vs SYSTEM DESIGN NOTE:
──────────────────────────────────────
This is a simple file-based logger. At scale, you'd replace this with:

  SCALE 1 (Current) — Local files
    App → logger → logs/mobility_platform.log

  SCALE 2 (Medium) — Centralized logging
    App → logger → CloudWatch / ELK Stack
    Multiple services send logs to ONE searchable system

  SCALE 3 (Large) — Distributed tracing
    App → OpenTelemetry → Jaeger/Datadog
    Track a single request across 10+ microservices

The INTERFACE stays the same (logger.info("message")) — only the
BACKEND changes. This is a key system design principle:
  "Program to an interface, not an implementation."
"""

import os
import logging
from pathlib import Path
from src.utils.config_loader import ConfigLoader


def setup_logger(name: str, config: ConfigLoader | None = None) -> logging.Logger:
    """
    Create a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module).
              This creates a hierarchy: src.data_generator.customers
              lets you filter logs per module.

        config: Optional ConfigLoader instance. If None, uses defaults.

    Returns:
        Configured logging.Logger instance.

    Usage:
        from src.utils.logger import setup_logger
        logger = setup_logger(__name__)

        logger.info("Generated 1000 customers")
        logger.warning("47 rides had missing driver_id")
        logger.error("Failed to write to S3", exc_info=True)
    """

    # Pull settings from config, with sensible defaults
    if config:
        log_level = config.get("logging", "level", default="INFO")
        log_dir = config.get("logging", "log_dir", default="logs")
        log_file = config.get("logging", "log_file", default="mobility_platform.log")
        console_output = config.get("logging", "console_output", default=True)
        file_output = config.get("logging", "file_output", default=True)
        log_format = config.get(
            "logging", "format",
            default="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
        )
    else:
        log_level = "INFO"
        log_dir = "logs"
        log_file = "mobility_platform.log"
        console_output = True
        file_output = True
        log_format = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"

    # Create the logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid duplicate handlers if setup_logger is called multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(log_format)

    # Console handler — see logs while developing
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler — persist logs for debugging later
    if file_output:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(
            log_path / log_file,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
