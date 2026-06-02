"""Config validation helpers for Airflow metadata scan DAGs."""

from __future__ import annotations

from pathlib import Path

from pipeline.data_scope import load_data_scope_config
from pipeline.download import build_plan, normalize_tables, parse_year_range, resolve_cycle_tables, year_range_values


def validate_manual_overrides(cycles_override: object, tables_override: object) -> tuple[list[int] | None, list[str] | None]:
    """Validate manual DAG run overrides and normalize table input."""

    cycles: list[int] | None = None
    if cycles_override is not None:
        if not isinstance(cycles_override, list):
            raise ValueError("dag_run.conf.cycles must be a list of even years")
        for value in cycles_override:
            if not isinstance(value, int) or value % 2 != 0:
                raise ValueError("dag_run.conf.cycles entries must be even integer years")
        cycles = sorted(dict.fromkeys(cycles_override))

    tables: list[str] | None = None
    if tables_override is not None:
        if not isinstance(tables_override, list):
            raise ValueError("dag_run.conf.tables must be a list of table names")
        for value in tables_override:
            if not isinstance(value, str):
                raise ValueError("dag_run.conf.tables entries must be strings")
        tables = normalize_tables(tables_override)

    return cycles, tables


def resolve_scan_targets(
    config_path: Path,
    repo_root: Path,
    cycles_override: list[int] | None,
    tables_override: list[str] | None,
) -> list[dict[str, object]]:
    """Resolve cycle/table scan targets into upstream artifact metadata targets."""

    config = load_data_scope_config(config_path)

    if cycles_override:
        cycles = sorted(dict.fromkeys(cycles_override))
    else:
        coverage_range = parse_year_range(config.get("coverage"), "coverage")
        cycles = year_range_values(coverage_range)

    explicit_tables: list[str] | None = None
    if tables_override:
        explicit_tables = normalize_tables(tables_override)

    targets: list[dict[str, object]] = []
    for cycle in cycles:
        cycle_tables = explicit_tables if explicit_tables is not None else resolve_cycle_tables(cycle, config)
        for table in cycle_tables:
            plan = build_plan(cycle, table, repo_root)
            targets.append(
                {
                    "cycle": cycle,
                    "table_name": table,
                    "zip_name": plan.zip_path.name,
                    "source_url": plan.url,
                }
            )

    return targets
