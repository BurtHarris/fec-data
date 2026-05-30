"""Download FEC bulk ZIP files for a cycle.

This module intentionally stays small: dbt owns the DuckDB loading and tests,
while this downloader only caches raw ZIP artifacts under data/<cycle>/.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml


DEFAULT_TABLES = ("ccl", "cm", "cn", "indiv", "oppexp", "oth", "pas2", "weball")
DEFAULT_COVERAGE_CONFIG = Path("config") / "fec_bulk_coverage.yml"


@dataclass(frozen=True)
class DownloadPlan:
    """A single expected FEC ZIP artifact."""

    cycle: int
    table: str
    url: str
    zip_path: Path
    meta_path: Path


def repo_root() -> Path:
    """Find the repository root from this source file location."""

    return Path(__file__).resolve().parents[2]


def normalize_tables(raw_tables: list[str] | None) -> list[str]:
    """Accept comma-separated or repeated table names, matching the old scripts."""

    if not raw_tables:
        return list(DEFAULT_TABLES)

    tables: list[str] = []
    for value in raw_tables:
        tables.extend(part.strip().lower() for part in value.split(",") if part.strip())

    invalid = sorted(set(tables) - set(DEFAULT_TABLES))
    if invalid:
        valid = ", ".join(DEFAULT_TABLES)
        raise SystemExit(f"Unknown table(s): {', '.join(invalid)}. Valid tables: {valid}")

    return tables


def parse_year_range(raw_value: Any, context: str) -> tuple[int, int]:
    """Parse a year range such as 2020-2026 or a single year."""

    if isinstance(raw_value, int):
        return raw_value, raw_value

    if not isinstance(raw_value, str):
        raise SystemExit(f"{context} must be a year or year range string")

    value = raw_value.strip()
    if not value:
        raise SystemExit(f"{context} cannot be empty")

    if "-" in value:
        start_text, end_text = [part.strip() for part in value.split("-", 1)]
        start_year = int(start_text)
        end_year = int(end_text)
    else:
        start_year = end_year = int(value)

    if start_year > end_year:
        raise SystemExit(f"{context} start year must not be greater than end year")

    return start_year, end_year


def year_in_range(year: int, year_range: tuple[int, int]) -> bool:
    """Return True when a year falls within an inclusive range."""

    start_year, end_year = year_range
    return start_year <= year <= end_year


def year_range_values(year_range: tuple[int, int]) -> list[int]:
    """Expand an inclusive year range into even election cycles only."""

    start_year, end_year = year_range
    first = start_year if start_year % 2 == 0 else start_year + 1
    return list(range(first, end_year + 1, 2))


def validate_even_cycle(cycle: int, context: str) -> None:
    """Fail fast when a provided cycle year is not even."""

    if cycle % 2 != 0:
        raise SystemExit(f"{context} must be an even election cycle year: {cycle}")


def load_coverage_config(path: Path) -> dict[str, Any] | None:
    """Read cycle coverage config; missing file means use built-in defaults."""

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}

    if not isinstance(loaded, dict):
        raise SystemExit(f"Coverage config must be a mapping: {path}")

    return loaded


def normalize_group_tables(values: list[Any], context: str) -> list[str]:
    """Normalize a list of table names in a coverage group."""

    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise SystemExit(f"{context} entries must be strings")
        normalized.append(value.strip().lower())
    return normalized


def resolve_cycle_tables(cycle: int, config: dict[str, Any] | None) -> list[str]:
    """Resolve tables for one cycle using the top-level config ranges."""

    validate_even_cycle(cycle, "cycle")

    if not config:
        return list(DEFAULT_TABLES)

    coverage_range = parse_year_range(config.get("coverage"), "coverage")
    facts_range = parse_year_range(config.get("facts"), "facts")
    groups_raw = config.get("table_groups", {})

    if not isinstance(groups_raw, dict):
        raise SystemExit("table_groups must be a mapping")

    if facts_range[0] < coverage_range[0] or facts_range[1] > coverage_range[1]:
        raise SystemExit("facts range must be fully contained within coverage range")

    if not year_in_range(cycle, coverage_range):
        return []

    groups: dict[str, list[str]] = {}
    for name, tables in groups_raw.items():
        if not isinstance(name, str) or not isinstance(tables, list):
            raise SystemExit("table_groups entries must be name: [table, ...]")
        groups[name] = normalize_group_tables(tables, f"table_groups.{name}")

    if "dimensions" not in groups or "facts" not in groups:
        raise SystemExit("table_groups must define dimensions and facts")

    tables = list(groups["dimensions"])
    if year_in_range(cycle, facts_range):
        tables.extend(groups["facts"])

    resolved: list[str] = []
    seen: set[str] = set()
    for table in tables:
        if table in seen:
            continue
        seen.add(table)
        resolved.append(table)

    invalid = sorted(set(resolved) - set(DEFAULT_TABLES))
    if invalid:
        valid = ", ".join(DEFAULT_TABLES)
        raise SystemExit(f"Unknown table(s) in coverage config: {', '.join(invalid)}. Valid tables: {valid}")

    return resolved


def build_plan(cycle: int, table: str, root: Path) -> DownloadPlan:
    """Create URL and local paths for one FEC bulk file."""

    yy = str(cycle)[-2:]
    file_stem = f"{table}{yy}"
    cycle_dir = root / "data" / str(cycle)
    return DownloadPlan(
        cycle=cycle,
        table=table,
        url=f"https://www.fec.gov/files/bulk-downloads/{cycle}/{file_stem}.zip",
        zip_path=cycle_dir / f"{file_stem}.zip",
        meta_path=cycle_dir / f".{file_stem}.json",
    )


def read_meta(path: Path) -> dict[str, str]:
    """Read cached HTTP metadata; missing or invalid metadata just means recheck."""

    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def format_bytes(value: int) -> str:
    """Render byte counts in the units people usually expect to see."""

    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MB"
    if value >= 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value} bytes"


def print_progress(plan: DownloadPlan, downloaded: int, total: int | None, started_at: float) -> None:
    """Print a compact progress line for one active download."""

    elapsed = max(time.monotonic() - started_at, 0.001)
    rate = downloaded / elapsed
    if total:
        percent = min((downloaded / total) * 100, 100)
        print(
            f"{plan.zip_path.name}: {percent:5.1f}% "
            f"({format_bytes(downloaded)} / {format_bytes(total)}, {format_bytes(int(rate))}/s)",
            flush=True,
        )
    else:
        print(
            f"{plan.zip_path.name}: {format_bytes(downloaded)} downloaded "
            f"({format_bytes(int(rate))}/s)",
            flush=True,
        )


def download_one(plan: DownloadPlan, force: bool, progress_interval: float) -> str:
    """Download one file, using ETag/Last-Modified headers when available."""

    plan.zip_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "fec-data-dbt/0.1"}
    cached = read_meta(plan.meta_path)

    # Conditional requests let the FEC server answer 304 Not Modified when our
    # local ZIP is still current, so repeated runs are fast and gentle.
    if not force and plan.zip_path.exists():
        if etag := cached.get("etag"):
            headers["If-None-Match"] = etag
        if last_modified := cached.get("last_modified"):
            headers["If-Modified-Since"] = last_modified

    request = Request(plan.url, headers=headers)
    try:
        with urlopen(request, timeout=120) as response:
            total_header = response.headers.get("Content-Length", "")
            total = int(total_header) if total_header.isdigit() else None
            part_path = plan.zip_path.with_suffix(plan.zip_path.suffix + ".part")
            downloaded = 0
            started_at = time.monotonic()
            last_progress_at = 0.0

            print(f"starting {plan.zip_path.name} from {plan.url}", flush=True)
            with part_path.open("wb") as output:
                while True:
                    # Stream in chunks so large files show life while they download.
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    downloaded += len(chunk)

                    now = time.monotonic()
                    if now - last_progress_at >= progress_interval:
                        print_progress(plan, downloaded, total, started_at)
                        last_progress_at = now

            shutil.move(str(part_path), str(plan.zip_path))
            meta = {
                "url": plan.url,
                "etag": response.headers.get("ETag", ""),
                "last_modified": response.headers.get("Last-Modified", ""),
                "content_length": total_header or str(downloaded),
            }
            plan.meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            print_progress(plan, downloaded, total, started_at)
            return f"downloaded {plan.zip_path.name} ({downloaded:,} bytes)"
    except HTTPError as exc:
        if exc.code == 304:
            return f"skipped {plan.zip_path.name} (not modified)"
        raise RuntimeError(f"failed {plan.zip_path.name}: HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"failed {plan.zip_path.name}: {exc.reason}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Download FEC bulk ZIP files.")
    parser.add_argument(
        "--cycles",
        nargs="*",
        type=int,
        help="Debug only: explicit cycle years to download instead of reading the coverage range.",
    )
    parser.add_argument(
        "--tables",
        nargs="*",
        help="Debug only: explicit table names to download instead of using coverage selection.",
    )
    parser.add_argument(
        "--coverage-config",
        default=str(DEFAULT_COVERAGE_CONFIG),
        help="Coverage YAML path used by default operation.",
    )
    parser.add_argument(
        "--strict-coverage",
        action="store_true",
        help="Fail when a debug cycle is outside the configured coverage range.",
    )
    parser.add_argument("--force", action="store_true", help="Download even if cached metadata matches.")
    parser.add_argument("--parallelism", type=int, default=4, help="Maximum concurrent downloads.")
    parser.add_argument(
        "--progress-interval",
        type=float,
        default=5.0,
        help="Seconds between progress lines for active downloads.",
    )
    args = parser.parse_args()

    root = repo_root()
    config_path = Path(args.coverage_config)
    if not config_path.is_absolute():
        config_path = root / config_path
    config = load_coverage_config(config_path)
    if config is None:
        raise SystemExit(f"Coverage config not found: {config_path}")

    if args.cycles:
        cycles = list(dict.fromkeys(args.cycles))
        for cycle in cycles:
            validate_even_cycle(cycle, "--cycles entry")
    else:
        coverage_range = parse_year_range(config.get("coverage"), "coverage")
        cycles = year_range_values(coverage_range)

    if args.tables:
        tables = normalize_tables(args.tables)
    else:
        tables = []

    plans: list[DownloadPlan] = []
    for cycle in cycles:
        if args.tables:
            cycle_tables = tables
        else:
            cycle_tables = resolve_cycle_tables(cycle, config)
            if args.cycles and args.strict_coverage and not cycle_tables:
                raise SystemExit(f"Cycle {cycle} is outside the configured coverage range")

        if not cycle_tables:
            print(f"cycle {cycle} resolved to zero tables; skipping downloads", flush=True)
            continue

        print(f"cycle {cycle}: {', '.join(cycle_tables)}", flush=True)
        plans.extend(build_plan(cycle, table, root) for table in cycle_tables)

    if not plans:
        print("no downloads were configured", flush=True)
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallelism) as executor:
        futures = [executor.submit(download_one, plan, args.force, args.progress_interval) for plan in plans]
        for future in concurrent.futures.as_completed(futures):
            print(future.result())


if __name__ == "__main__":
    main()
