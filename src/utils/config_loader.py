"""
config_loader.py — YAML Configuration Loader
═══════════════════════════════════════════════

WHY THIS EXISTS:
────────────────
In production data platforms, you NEVER hardcode values like:
    num_customers = 1000
    cities = ["Mumbai", "Pune"]

Instead, everything lives in a config file. This gives us:
  1. Single source of truth — change one place, affects everywhere
  2. Environment-specific configs — dev vs staging vs production
  3. No code changes for parameter tweaks
  4. Easy to audit what parameters a pipeline ran with

DESIGN DECISIONS:
─────────────────
• Singleton pattern — config is loaded ONCE and reused everywhere
• YAML over JSON — more readable, supports comments
• Validation — fail fast if config is missing or malformed
"""

import os
import yaml
from pathlib import Path
from typing import Any


class ConfigLoader:
    """
    Loads and provides access to YAML configuration.

    Usage:
        config = ConfigLoader.load()
        num_customers = config.get("data_generation", "num_customers")
    """

    _instance: dict | None = None
    _config_path: Path | None = None

    @classmethod
    def load(cls, config_path: str | None = None) -> "ConfigLoader":
        """
        Load configuration from YAML file.

        The loader searches for config in this order:
        1. Explicit path passed as argument
        2. CONFIG_PATH environment variable
        3. Default: config/config.yaml relative to project root

        This search order is a common pattern in data platforms —
        it lets you override config in different environments without
        changing code.
        """
        if config_path:
            path = Path(config_path)
        elif os.environ.get("CONFIG_PATH"):
            path = Path(os.environ["CONFIG_PATH"])
        else:
            # Walk up from this file to find project root
            project_root = Path(__file__).resolve().parent.parent.parent
            path = project_root / "config" / "config.yaml"

        if not path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {path}\n"
                f"Expected at: {path.resolve()}\n"
                f"Hint: Make sure you're running from the project root directory."
            )

        with open(path, "r", encoding="utf-8") as f:
            cls._instance = yaml.safe_load(f)
            cls._config_path = path

        return cls()

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Navigate nested config with dot-style access.

        Example:
            config.get("data_generation", "num_customers")
            # Equivalent to: config["data_generation"]["num_customers"]

        This is safer than dict chaining because it won't throw
        KeyError — it returns `default` if any key is missing.
        """
        if self._instance is None:
            raise RuntimeError("Config not loaded. Call ConfigLoader.load() first.")

        result = self._instance
        for key in keys:
            if isinstance(result, dict) and key in result:
                result = result[key]
            else:
                return default
        return result

    def get_all(self) -> dict:
        """Return the entire config dictionary."""
        if self._instance is None:
            raise RuntimeError("Config not loaded. Call ConfigLoader.load() first.")
        return self._instance

    @property
    def config_path(self) -> Path | None:
        """Return the path of the loaded config file."""
        return self._config_path
