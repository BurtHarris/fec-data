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
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_TABLES = ("ccl", "cm", "cn", "indiv", "oppexp", "oth", "pas2", "weball")


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
    parser.add_argument("cycle", type=int, help="Election cycle year, e.g. 2026.")
    parser.add_argument("tables", nargs="*", help="Optional table names, e.g. indiv cm.")
    parser.add_argument("--force", action="store_true", help="Download even if cached metadata matches.")
    parser.add_argument("--parallelism", type=int, default=4, help="Maximum concurrent downloads.")
    parser.add_argument(
        "--progress-interval",
        type=float,
        default=5.0,
        help="Seconds between progress lines for active downloads.",
    )
    args = parser.parse_args()

    tables = normalize_tables(args.tables)
    plans = [build_plan(args.cycle, table, repo_root()) for table in tables]

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallelism) as executor:
        futures = [executor.submit(download_one, plan, args.force, args.progress_interval) for plan in plans]
        for future in concurrent.futures.as_completed(futures):
            print(future.result())


if __name__ == "__main__":
    main()
