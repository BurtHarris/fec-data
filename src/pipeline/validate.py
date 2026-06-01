"""Run dbt validation routines and emit markdown exception reports."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from pipeline.cli_common import validate_even_cycle
from pipeline.etl_config import repo_root
from pipeline.validation_report import write_validation_report


def run_dbt_validation(root: Path, cycle: int, profiles_dir: str, selector: str) -> int:
    """Execute dbt tests for the selected validation scope."""

    command = [
        "uv",
        "run",
        "dbt",
        "test",
        "--project-dir",
        str(root),
        "--profiles-dir",
        profiles_dir,
        "--vars",
        f"{{cycle: {cycle}}}",
        "--select",
        selector,
    ]
    result = subprocess.run(command, cwd=str(root), check=False)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Run validation checks and generate exception reports.")
    parser.add_argument("--cycle", type=int, required=True, help="Election cycle year (for example: 2026)")
    parser.add_argument(
        "--profiles-dir",
        default=".",
        help="dbt profiles directory. Defaults to repository root (.).",
    )
    parser.add_argument(
        "--select",
        default="tag:early_quality",
        help="dbt selector for tests. Defaults to tag:early_quality.",
    )
    parser.add_argument(
        "--skip-report",
        action="store_true",
        help="Skip markdown exception report generation.",
    )
    args = parser.parse_args()

    validate_even_cycle(args.cycle)
    root = repo_root()

    code = run_dbt_validation(root=root, cycle=args.cycle, profiles_dir=args.profiles_dir, selector=args.select)

    if not args.skip_report:
        report_path = write_validation_report(root=root, cycle=args.cycle)
        print(f"Validation report written to {report_path.as_posix()}", flush=True)

    if code != 0:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
