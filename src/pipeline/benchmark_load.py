"""Benchmark dbt zipfs raw-load performance for one FEC cycle."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import yaml

from pipeline.etl_config import DEFAULT_ETL_CONFIG_PATH, load_etl_model_config, repo_root


FACT_TABLES = {"indiv", "oppexp", "oth", "pas2"}


@dataclass(frozen=True)
class TableMetric:
    approach: str
    table_name: str
    duration_ms: int | None
    row_count: int | None
    status: str


@dataclass(frozen=True)
class ApproachResult:
    approach: str
    duration_ms: int
    status: str
    db_path: Path
    log_path: Path
    table_metrics: tuple[TableMetric, ...]
    metadata_db_path: Path | None = None


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def selected_tables_for_args(root: Path, cycle: int, raw_tables: list[str] | None) -> list[str]:
    defaults = default_tables_for_cycle(root, cycle)
    if raw_tables:
        return normalize_tables(raw_tables, defaults)
    return defaults


def run_command(command: list[str], cwd: Path, log_path: Path) -> tuple[int, int]:
    start = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as log_handle:
        process = subprocess.run(
            command,
            cwd=str(cwd),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    duration_ms = int((time.perf_counter() - start) * 1000)
    return process.returncode, duration_ms


def create_profile_dir(root: Path, db_path: Path, threads: int = 1) -> Path:
    profile_root = Path(tempfile.mkdtemp(prefix="dbt-profile-", dir=str(root / "tmp")))
    profile = {
        "moneytrail": {
            "target": "bench",
            "outputs": {
                "bench": {
                    "type": "duckdb",
                    "path": db_path.as_posix(),
                    "threads": threads,
                }
            },
        }
    }
    with (profile_root / "profiles.yml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(profile, handle, sort_keys=False)
    return profile_root


def fetch_row_counts(db_path: Path, cycle: int, tables: list[str]) -> dict[str, int | None]:
    results: dict[str, int | None] = {table: None for table in tables}
    if not db_path.exists():
        return results

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        for table in tables:
            target_name = f"{table}_{cycle}"
            exists = conn.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'raw_fec' AND table_name = ?
                """,
                [target_name],
            ).fetchone()[0]
            if exists:
                results[table] = conn.execute(f"SELECT COUNT(*) FROM raw_fec.{target_name}").fetchone()[0]
    finally:
        conn.close()

    return results


def parse_dbt_metrics(run_results_path: Path) -> dict[str, int | None]:
    metrics: dict[str, int | None] = {}
    if not run_results_path.exists():
        return metrics

    payload = json.loads(run_results_path.read_text(encoding="utf-8"))
    for result in payload.get("results", []):
        unique_id = result.get("unique_id", "")
        if not isinstance(unique_id, str) or not unique_id.startswith("model."):
            continue
        table_name = unique_id.rsplit(".", 1)[-1]
        execution_time = result.get("execution_time")
        if isinstance(execution_time, (int, float)):
            metrics[table_name] = int(float(execution_time) * 1000)
        else:
            metrics[table_name] = None
    return metrics


def run_dbt_benchmark(root: Path, cycle: int, tables: list[str], run_dir: Path, dbt_threads: int) -> ApproachResult:
    db_path = run_dir / "dbt.duckdb"
    target_path = run_dir / "dbt-target"
    target_path.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "dbt.log"
    profile_dir = create_profile_dir(root, db_path, threads=dbt_threads)
    try:
        command = [
            "uv",
            "run",
            "dbt",
            "run",
            "--project-dir",
            str(root),
            "--profiles-dir",
            str(profile_dir),
            "--target-path",
            str(target_path),
            "--vars",
            f"{{cycle: {cycle}}}",
            "--select",
        ]
        if tables and tables != default_tables_for_cycle(root, cycle):
            command.extend(tables)
        else:
            command.append("raw_fec")

        return_code, duration_ms = run_command(command, root, log_path)
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)

    row_counts = fetch_row_counts(db_path, cycle, tables)
    dbt_metrics = parse_dbt_metrics(target_path / "run_results.json")
    table_metrics = tuple(
        TableMetric(
            approach="dbt_zipfs",
            table_name=table,
            duration_ms=dbt_metrics.get(table),
            row_count=row_counts.get(table),
            status="success" if row_counts.get(table) is not None else "missing",
        )
        for table in tables
    )
    return ApproachResult(
        approach="dbt_zipfs",
        duration_ms=duration_ms,
        status="success" if return_code == 0 else f"failed({return_code})",
        db_path=db_path,
        metadata_db_path=None,
        log_path=log_path,
        table_metrics=table_metrics,
    )


def write_results_csv(root: Path, cycle: int, label: str, tables: list[str], results: list[ApproachResult]) -> Path:
    output_dir = root / "logs" / "load-timing"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"benchmark_load_{cycle}_{label}.csv"
    measured_at = utc_now_iso()

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "cycle",
                "label",
                "approach",
                "scope",
                "table_name",
                "duration_ms",
                "row_count",
                "status",
                "log_path",
                "db_path",
                "metadata_db_path",
                "measured_at_utc",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "cycle": cycle,
                    "label": label,
                    "approach": result.approach,
                    "scope": "summary",
                    "table_name": "",
                    "duration_ms": result.duration_ms,
                    "row_count": "",
                    "status": result.status,
                    "log_path": result.log_path.as_posix(),
                    "db_path": result.db_path.as_posix(),
                    "metadata_db_path": result.metadata_db_path.as_posix() if result.metadata_db_path else "",
                    "measured_at_utc": measured_at,
                }
            )
            for metric in result.table_metrics:
                writer.writerow(
                    {
                        "cycle": cycle,
                        "label": label,
                        "approach": result.approach,
                        "scope": "fact" if metric.table_name in FACT_TABLES else "dimension",
                        "table_name": metric.table_name,
                        "duration_ms": metric.duration_ms if metric.duration_ms is not None else "",
                        "row_count": metric.row_count if metric.row_count is not None else "",
                        "status": metric.status,
                        "log_path": result.log_path.as_posix(),
                        "db_path": result.db_path.as_posix(),
                        "metadata_db_path": result.metadata_db_path.as_posix() if result.metadata_db_path else "",
                        "measured_at_utc": measured_at,
                    }
                )

    return output_path


def print_summary(results: list[ApproachResult]) -> None:
    for result in results:
        print(f"{result.approach}: {result.duration_ms} ms ({result.status})", flush=True)
        fact_duration = sum(metric.duration_ms or 0 for metric in result.table_metrics if metric.table_name in FACT_TABLES)
        fact_tables = [metric.table_name for metric in result.table_metrics if metric.table_name in FACT_TABLES]
        if fact_tables:
            print(f"  fact-table subtotal: {fact_duration} ms across {', '.join(fact_tables)}", flush=True)


def benchmark_once(root: Path, cycle: int, tables: list[str], run_root: Path, dbt_threads: int) -> list[ApproachResult]:
    dbt_dir = run_root / "dbt_zipfs"
    dbt_dir.mkdir(parents=True, exist_ok=True)
    return [
        run_dbt_benchmark(root, cycle, tables, dbt_dir, dbt_threads=dbt_threads),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark dbt zipfs raw-load performance.")
    parser.add_argument("--cycle", type=int, required=True, help="Election cycle year (for example: 2026)")
    parser.add_argument(
        "--tables",
        nargs="*",
        help="Optional table list (comma-separated or repeated names): indiv oppexp oth pas2",
    )
    parser.add_argument("--label", help="Optional label to include in the output filename")
    parser.add_argument("--warmup", action="store_true", help="Run one discarded warm-up pass before measuring")
    parser.add_argument("--keep-run-dir", action="store_true", help="Keep isolated benchmark databases and logs")
    parser.add_argument(
        "--dbt-threads",
        type=int,
        default=1,
        help="Thread count for the benchmark's temporary dbt profile. Defaults to 1 to avoid memory pressure on large fact tables.",
    )
    args = parser.parse_args()

    if args.cycle % 2 != 0:
        raise SystemExit(f"Cycle must be an even election year: {args.cycle}")
    if args.dbt_threads < 1:
        raise SystemExit(f"--dbt-threads must be at least 1: {args.dbt_threads}")

    root = repo_root()
    tables = selected_tables_for_args(root, args.cycle, args.tables)
    run_stamp = utc_now_compact()
    label = args.label or run_stamp.lower()
    run_root = root / "tmp" / "benchmark-load" / f"{args.cycle}-{label}"
    run_root.mkdir(parents=True, exist_ok=True)

    try:
        if args.warmup:
            warmup_root = run_root / "warmup"
            warmup_root.mkdir(parents=True, exist_ok=True)
            print(f"Running warm-up benchmark for cycle {args.cycle}...", flush=True)
            benchmark_once(root, args.cycle, tables, warmup_root, dbt_threads=args.dbt_threads)

        measured_root = run_root / "measured"
        measured_root.mkdir(parents=True, exist_ok=True)
        print(f"Benchmarking cycle {args.cycle} tables: {', '.join(tables)}", flush=True)
        results = benchmark_once(root, args.cycle, tables, measured_root, dbt_threads=args.dbt_threads)
        csv_path = write_results_csv(root, args.cycle, label, tables, results)
        print_summary(results)
        print(f"Results written to {csv_path.as_posix()}", flush=True)

        failures = [result for result in results if result.status != "success"]
        if failures:
            failed_names = ", ".join(result.approach for result in failures)
            raise SystemExit(f"Benchmark failed for: {failed_names}")
    finally:
        if not args.keep_run_dir:
            shutil.rmtree(run_root, ignore_errors=True)


if __name__ == "__main__":
    main()