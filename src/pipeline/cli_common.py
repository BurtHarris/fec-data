"""Shared CLI helpers for pipeline commands."""

from __future__ import annotations

from pathlib import Path

from pipeline.etl_config import DEFAULT_ETL_CONFIG_PATH, load_etl_model_config


def validate_even_cycle(cycle: int, context: str = "cycle") -> None:
    """Fail fast when a provided cycle year is not even."""

    if cycle % 2 != 0:
        raise SystemExit(f"{context} must be an even election cycle year: {cycle}")


def default_tables_for_cycle(root: Path, cycle: int) -> list[str]:
    """Resolve configured model names for one cycle suffix."""

    cycle_suffix = str(cycle)[-2:]
    config_path = root / DEFAULT_ETL_CONFIG_PATH
    configs = load_etl_model_config(config_path, cycle_suffix=cycle_suffix)
    return [item.name for item in configs]


def normalize_tables(raw_tables: list[str] | None, defaults: list[str]) -> list[str]:
    """Accept comma-separated or repeated table names against a default set."""

    if not raw_tables:
        return defaults

    tables: list[str] = []
    for value in raw_tables:
        tables.extend(part.strip().lower() for part in value.split(",") if part.strip())

    invalid = sorted(set(tables) - set(defaults))
    if invalid:
        valid = ", ".join(defaults)
        raise SystemExit(f"Unknown table(s): {', '.join(invalid)}. Valid tables: {valid}")
    return tables
