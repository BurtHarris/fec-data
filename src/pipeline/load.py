"""Load FEC raw tables through dbt using DuckDB zipfs paths."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from pipeline.cli_common import default_tables_for_cycle, normalize_tables, validate_even_cycle
from pipeline.etl_config import repo_root


def run_dbt_load(
    root: Path,
    cycle: int,
    tables: list[str],
    dbt_threads: int,
    profiles_dir: str,
    extra_select: str | None,
) -> int:
    """Execute dbt run for the selected tables/cycle."""

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

    validate_even_cycle(args.cycle)
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
