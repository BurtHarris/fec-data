"""Data Scope Config service for workflow selection and run snapshots."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_TABLES = ("ccl", "cm", "cn", "indiv", "oppexp", "oth", "pas2", "weball")
CANONICAL_DATA_SCOPE_PATH = Path("config") / "data_scope.yml"


def parse_year_range(raw_value: Any, context: str) -> tuple[int, int]:
    """Parse a year range such as 2020-2026 or a single year."""

    if isinstance(raw_value, bool):
        raise SystemExit(f"{context} must be a year or year range string")

    if isinstance(raw_value, int):
        return raw_value, raw_value

    if not isinstance(raw_value, str):
        raise SystemExit(f"{context} must be a year or year range string")

    value = raw_value.strip()
    if not value:
        raise SystemExit(f"{context} cannot be empty")

    try:
        if "-" in value:
            start_text, end_text = [part.strip() for part in value.split("-", 1)]
            start_year = int(start_text)
            end_year = int(end_text)
        else:
            start_year = end_year = int(value)
    except ValueError as exc:
        raise SystemExit(f"{context} must be a year or year range string") from exc

    if start_year > end_year:
        raise SystemExit(f"{context} start year must not be greater than end year")

    return start_year, end_year


def _format_year_range(year_range: tuple[int, int]) -> str:
    start_year, end_year = year_range
    return str(start_year) if start_year == end_year else f"{start_year}-{end_year}"


def _normalize_group_tables(values: list[Any], context: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise SystemExit(f"{context} entries must be strings")
        table = value.strip().lower()
        if not table or table in seen:
            continue
        seen.add(table)
        normalized.append(table)

    invalid = sorted(set(normalized) - set(DEFAULT_TABLES))
    if invalid:
        valid = ", ".join(DEFAULT_TABLES)
        raise SystemExit(f"Unknown table(s) in data scope config: {', '.join(invalid)}. Valid tables: {valid}")

    return normalized


def normalize_data_scope_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a raw Data Scope config mapping."""

    coverage_range = parse_year_range(config.get("coverage"), "coverage")
    facts_range = parse_year_range(config.get("facts"), "facts")
    groups_raw = config.get("table_groups", {})

    if not isinstance(groups_raw, dict):
        raise SystemExit("table_groups must be a mapping")

    if facts_range[0] < coverage_range[0] or facts_range[1] > coverage_range[1]:
        raise SystemExit("facts range must be fully contained within coverage range")

    dimensions = groups_raw.get("dimensions")
    facts = groups_raw.get("facts")
    if not isinstance(dimensions, list) or not isinstance(facts, list):
        raise SystemExit("table_groups must define dimensions and facts lists")

    return {
        "version": 1,
        "coverage": _format_year_range(coverage_range),
        "facts": _format_year_range(facts_range),
        "table_groups": {
            "dimensions": _normalize_group_tables(dimensions, "table_groups.dimensions"),
            "facts": _normalize_group_tables(facts, "table_groups.facts"),
        },
    }


def load_data_scope_config(path: Path) -> dict[str, Any]:
    """Load and validate Data Scope config from disk."""

    if not path.exists():
        raise SystemExit(f"Data Scope config not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}

    if not isinstance(loaded, dict):
        raise SystemExit(f"Data Scope config must be a mapping: {path}")

    return normalize_data_scope_config(loaded)


def save_data_scope_config(path: Path, config: dict[str, Any]) -> None:
    """Validate and persist canonical Data Scope config to disk."""

    normalized = normalize_data_scope_config(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(normalized, handle, sort_keys=False)


def snapshot_data_scope(config: dict[str, Any]) -> dict[str, Any]:
    """Create an immutable run snapshot from normalized config."""

    normalized = normalize_data_scope_config(config)
    return deepcopy(normalized)
