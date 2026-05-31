"""Load FEC raw tables through dbt using DuckDB zipfs paths."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from pipeline.etl_config import DEFAULT_ETL_CONFIG_PATH, load_etl_model_config, repo_root


def default_tables_for_cycle(root: Path, cycle: int) -> list[str]:
    cycle_suffix = str(cycle)[-2:]
    config_path = root / DEFAULT_ETL_CONFIG_PATH
    configs = load_etl_model_config(config_path, cycle_suffix=cycle_suffix)
    return [item.name for item in configs]


def normalize_tables(raw_tables: list[str] | None, defaults: list[str]) -> list[str]:
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


def run_dbt_load(
    root: Path,
    cycle: int,
    tables: list[str],
    dbt_threads: int,
    profiles_dir: str,
    extra_select: str | None,
) -> int:
    command = [
        "uv",
        "run",
        "dbt",
        "run",
        "--project-dir",
        str(root),
        "--profiles-dir",
        profiles_dir,
        "--vars",
        f"{{cycle: {cycle}}}",
        "--threads",
        str(dbt_threads),
        "--select",
    ]

    if extra_select:
        command.append(extra_select)
    elif tables:
        command.extend(tables)
    else:
        command.append("raw_fec")

    result = subprocess.run(command, cwd=str(root), check=False)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Load FEC raw tables with dbt zipfs.")
    parser.add_argument("--cycle", type=int, required=True, help="Election cycle year (for example: 2026)")
    parser.add_argument(
        "--tables",
        nargs="*",
        help="Optional table list (comma-separated or repeated names): cm cn indiv",
    )
    parser.add_argument(
        "--dbt-threads",
        type=int,
        default=1,
        help="dbt thread count. Defaults to 1 for large-fact stability.",
    )
    parser.add_argument(
        "--profiles-dir",
        default=".",
        help="dbt profiles directory. Defaults to repository root (.).",
    )
    parser.add_argument(
        "--select",
        help="Optional dbt selector override. If provided, this overrides --tables/raw_fec default selection.",
    )
    args = parser.parse_args()

    if args.cycle % 2 != 0:
        raise SystemExit(f"Cycle must be an even election year: {args.cycle}")
    if args.dbt_threads < 1:
        raise SystemExit(f"--dbt-threads must be at least 1: {args.dbt_threads}")

    root = repo_root()
    defaults = default_tables_for_cycle(root, args.cycle)
    tables = normalize_tables(args.tables, defaults)
    code = run_dbt_load(
        root=root,
        cycle=args.cycle,
        tables=tables,
        dbt_threads=args.dbt_threads,
        profiles_dir=args.profiles_dir,
        extra_select=args.select,
    )

    if code != 0:
        raise SystemExit(code)


if __name__ == "__main__":
    main()