"""Load downloaded FEC ZIP artifacts into DuckDB raw tables."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import duckdb

from fec_pipeline.raw_fec_config import DEFAULT_SCHEMA_PATH, load_raw_fec_model_config, repo_root


@dataclass(frozen=True)
class LoadTarget:
    """Resolved load metadata for one raw table in one cycle."""

    table: str
    source_entry: str
    zip_path: Path
    transform_sql_path: Path
    target_table: str


def normalize_tables(raw_tables: list[str] | None, defaults: list[str]) -> list[str]:
    """Accept comma-separated or repeated table names."""

    if not raw_tables:
        return list(defaults)

    tables: list[str] = []
    for value in raw_tables:
        tables.extend(part.strip().lower() for part in value.split(",") if part.strip())

    invalid = sorted(set(tables) - set(defaults))
    if invalid:
        valid = ", ".join(defaults)
        raise SystemExit(f"Unknown table(s): {', '.join(invalid)}. Valid tables: {valid}")

    return tables


def render_template(template: str, replacements: dict[str, str]) -> str:
    """Replace known token placeholders in SQL templates."""

    rendered = template
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    return rendered


def quote_sql(value: str) -> str:
    """Return a single-quoted SQL string literal."""

    return "'" + value.replace("'", "''") + "'"


def file_sha256(path: Path) -> str:
    """Compute the SHA256 digest for one file."""

    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def table_exists(conn: duckdb.DuckDBPyConnection, schema: str, table: str) -> bool:
    """Return True when a table exists in information_schema."""

    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = ?
          AND table_name = ?
        """,
        [schema, table],
    ).fetchone()
    return bool(row and row[0] > 0)


def latest_loaded_hash(
    conn: duckdb.DuckDBPyConnection,
    cycle: int,
    table: str,
    target_table: str,
    source_zip_path: str,
) -> str | None:
    """Read the most recent source file hash for this exact table load target."""

    row = conn.execute(
        """
        SELECT source_file_hash
        FROM etl.load_history
        WHERE cycle = ?
          AND table_name = ?
          AND target_table_name = ?
          AND source_zip_path = ?
          AND source_file_hash IS NOT NULL
        ORDER BY load_id DESC
        LIMIT 1
        """,
        [cycle, table, target_table, source_zip_path],
    ).fetchone()

    if not row:
        return None
    return row[0]


def upsert_current_state_success(
    conn: duckdb.DuckDBPyConnection,
    cycle: int,
    table: str,
    zip_name: str,
    source_zip_path: str,
    source_entry_name: str,
    target_table: str,
    row_count: int,
    duration_ms: int,
) -> None:
    """Write current-state metadata for a successful load."""

    conn.execute(
        """
        DELETE FROM etl.current_state
        WHERE entity_type = 'table'
          AND cycle = ?
          AND table_name = ?
        """,
        [cycle, table],
    )

    conn.execute(
        """
        INSERT INTO etl.current_state (
            state_id,
            entity_type,
            cycle,
            table_name,
            entity_name,
            last_operation,
            operation_status,
            quality_status,
            source_url,
            source_zip_path,
            source_entry_name,
            target_table_name,
            http_status,
            content_length,
            row_count,
            duration_ms,
            response_date,
            last_modified,
            etag,
            error_text,
            updated_at
        )
        SELECT
            COALESCE((SELECT MAX(state_id) + 1 FROM etl.current_state), 1),
            'table',
            ?,
            ?,
            ?,
            'load',
            'Completed',
            'pass',
            NULL,
            ?,
            ?,
            ?,
            NULL,
            NULL,
            ?,
            ?,
            NULL,
            NULL,
            NULL,
            NULL,
            NOW()
        """,
        [
            cycle,
            table,
            zip_name,
            source_zip_path,
            source_entry_name,
            target_table,
            row_count,
            duration_ms,
        ],
    )


def upsert_current_state_failure(
    conn: duckdb.DuckDBPyConnection,
    cycle: int,
    table: str,
    zip_name: str,
    source_zip_path: str,
    source_entry_name: str,
    target_table: str,
    duration_ms: int,
    error_text: str,
) -> None:
    """Write current-state metadata for a failed load."""

    conn.execute(
        """
        DELETE FROM etl.current_state
        WHERE entity_type = 'table'
          AND cycle = ?
          AND table_name = ?
        """,
        [cycle, table],
    )

    conn.execute(
        """
        INSERT INTO etl.current_state (
            state_id,
            entity_type,
            cycle,
            table_name,
            entity_name,
            last_operation,
            operation_status,
            quality_status,
            source_url,
            source_zip_path,
            source_entry_name,
            target_table_name,
            http_status,
            content_length,
            row_count,
            duration_ms,
            response_date,
            last_modified,
            etag,
            error_text,
            updated_at
        )
        SELECT
            COALESCE((SELECT MAX(state_id) + 1 FROM etl.current_state), 1),
            'table',
            ?,
            ?,
            ?,
            'load',
            'Failed',
            'error',
            NULL,
            ?,
            ?,
            ?,
            NULL,
            NULL,
            NULL,
            ?,
            NULL,
            NULL,
            NULL,
            ?,
            NOW()
        """,
        [
            cycle,
            table,
            zip_name,
            source_zip_path,
            source_entry_name,
            target_table,
            duration_ms,
            error_text,
        ],
    )


def insert_load_history(
    conn: duckdb.DuckDBPyConnection,
    cycle: int,
    table: str,
    source_zip_path: str,
    source_entry_name: str,
    source_file_hash: str,
    target_table: str,
    row_count: int,
    duration_ms: int,
) -> None:
    """Append one load-history record."""

    conn.execute(
        """
        INSERT INTO etl.load_history (
            load_id,
            cycle,
            table_name,
            source_zip_path,
            source_entry_name,
            source_file_hash,
            target_table_name,
            row_count,
            duration_ms,
            loaded_at
        )
        SELECT
            COALESCE((SELECT MAX(load_id) + 1 FROM etl.load_history), 1),
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            NOW()
        """,
        [
            cycle,
            table,
            source_zip_path,
            source_entry_name,
            source_file_hash,
            target_table,
            row_count,
            duration_ms,
        ],
    )


def resolve_targets(cycle: int, selected_tables: list[str], root: Path) -> list[LoadTarget]:
    """Resolve table metadata and local file paths for this load run."""

    cycle_suffix = str(cycle)[-2:]
    schema_path = root / DEFAULT_SCHEMA_PATH
    configs = load_raw_fec_model_config(schema_path, cycle_suffix=cycle_suffix)
    config_by_name = {item.name: item for item in configs}

    cycle_dir = root / "data" / str(cycle)
    if not cycle_dir.exists():
        raise SystemExit(f"Cycle directory not found: {cycle_dir}")

    transform_dir = root / "sql" / "transform"
    if not transform_dir.exists():
        raise SystemExit(f"Transform SQL directory not found: {transform_dir}")

    targets: list[LoadTarget] = []
    for table in selected_tables:
        source_entry = config_by_name[table].source_entry
        zip_path = cycle_dir / f"{table}{cycle_suffix}.zip"
        transform_sql_path = transform_dir / f"load_{table}.sql"
        target_table = f"raw_fec.{table}_{cycle}"
        targets.append(
            LoadTarget(
                table=table,
                source_entry=source_entry,
                zip_path=zip_path,
                transform_sql_path=transform_sql_path,
                target_table=target_table,
            )
        )

    return targets


def extract_source_entry(zip_path: Path, source_entry: str, extract_root: Path) -> Path:
    """Extract one source entry from one ZIP archive and return the file path."""

    extract_dir = extract_root / zip_path.stem
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as archive:
        try:
            archive.extract(source_entry, path=extract_dir)
        except KeyError as exc:
            raise RuntimeError(f"Entry {source_entry} not found in {zip_path}") from exc

    extracted = extract_dir / source_entry
    if not extracted.exists():
        raise RuntimeError(f"Extracted source not found: {extracted}")
    return extracted


def main() -> None:
    parser = argparse.ArgumentParser(description="Load FEC ZIP files into DuckDB raw_fec tables.")
    parser.add_argument("--cycle", required=True, type=int, help="Election cycle year (for example: 2026)")
    parser.add_argument(
        "--tables",
        nargs="*",
        help="Optional table list (comma-separated or repeated names): cm cn indiv",
    )
    parser.add_argument("--db-path", default="db/fec.duckdb", help="DuckDB file path")
    parser.add_argument(
        "--schema-sql",
        default="sql/schema/001_create_fec_schemas.sql",
        help="Schema SQL file to initialize ETL objects",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reload even when source file hash has not changed",
    )
    args = parser.parse_args()

    if args.cycle % 2 != 0:
        raise SystemExit(f"Cycle must be an even election year: {args.cycle}")

    root = repo_root()
    cycle_suffix = str(args.cycle)[-2:]
    configs = load_raw_fec_model_config(root / DEFAULT_SCHEMA_PATH, cycle_suffix=cycle_suffix)
    default_tables = [item.name for item in configs]
    selected_tables = normalize_tables(args.tables, default_tables)
    targets = resolve_targets(args.cycle, selected_tables, root)

    db_path = Path(args.db_path)
    if not db_path.is_absolute():
        db_path = root / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_sql_path = Path(args.schema_sql)
    if not schema_sql_path.is_absolute():
        schema_sql_path = root / schema_sql_path
    if not schema_sql_path.exists():
        raise SystemExit(f"Schema SQL not found: {schema_sql_path}")

    extract_root = root / "tmp" / "load-fec"
    extract_root.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(schema_sql_path.read_text(encoding="utf-8"))

        total = len(targets)
        loaded_count = 0
        skipped_count = 0
        failed_count = 0

        for index, target in enumerate(targets, start=1):
            zip_name = target.zip_path.name
            print(f"[{index}/{total}] Processing {zip_name}...", flush=True)

            if not target.zip_path.exists():
                print(f"Warning: ZIP not found, skipping: {target.zip_path}", flush=True)
                skipped_count += 1
                continue

            if not target.transform_sql_path.exists():
                failed_count += 1
                print(f"Error: load SQL template not found: {target.transform_sql_path}", flush=True)
                continue

            start = time.perf_counter()
            source_zip_path = target.zip_path.as_posix()
            source_hash = file_sha256(target.zip_path)

            table_name_only = target.target_table.split(".", 1)[1]
            if not args.force and table_exists(conn, "raw_fec", table_name_only):
                previous_hash = latest_loaded_hash(
                    conn,
                    cycle=args.cycle,
                    table=target.table,
                    target_table=target.target_table,
                    source_zip_path=source_zip_path,
                )
                if previous_hash == source_hash:
                    skipped_count += 1
                    print(
                        f"[{index}/{total}] Skipped {zip_name}; unchanged source hash for {target.target_table}",
                        flush=True,
                    )
                    continue

            extracted_source = extract_source_entry(target.zip_path, target.source_entry, extract_root)
            source_path = extracted_source.as_posix()
            template = target.transform_sql_path.read_text(encoding="utf-8")
            load_sql = render_template(
                template,
                {
                    "{TARGET_TABLE}": target.target_table,
                    "{SOURCE_PATH}": source_path.replace("'", "''"),
                    "{CYCLE}": str(args.cycle),
                    "{TABLE_NAME}": target.table,
                    "{ZIP_PATH}": source_zip_path.replace("'", "''"),
                    "{ENTRY_NAME_SQL}": quote_sql(target.source_entry),
                },
            )

            try:
                conn.execute(load_sql)
                row_count = conn.execute(f"SELECT COUNT(*) FROM {target.target_table}").fetchone()[0]
                duration_ms = int((time.perf_counter() - start) * 1000)

                # Some legacy SQL templates insert load_history; remove duplicates by writing history here only.
                insert_load_history(
                    conn,
                    cycle=args.cycle,
                    table=target.table,
                    source_zip_path=source_zip_path,
                    source_entry_name=target.source_entry,
                    source_file_hash=source_hash,
                    target_table=target.target_table,
                    row_count=row_count,
                    duration_ms=duration_ms,
                )
                upsert_current_state_success(
                    conn,
                    cycle=args.cycle,
                    table=target.table,
                    zip_name=zip_name,
                    source_zip_path=source_zip_path,
                    source_entry_name=target.source_entry,
                    target_table=target.target_table,
                    row_count=row_count,
                    duration_ms=duration_ms,
                )

                loaded_count += 1
                print(f"[{index}/{total}] Loaded {zip_name} into {target.target_table}", flush=True)
            except Exception as exc:  # noqa: BLE001 - report per-table failure and continue.
                failed_count += 1
                duration_ms = int((time.perf_counter() - start) * 1000)
                upsert_current_state_failure(
                    conn,
                    cycle=args.cycle,
                    table=target.table,
                    zip_name=zip_name,
                    source_zip_path=source_zip_path,
                    source_entry_name=target.source_entry,
                    target_table=target.target_table,
                    duration_ms=duration_ms,
                    error_text=str(exc),
                )
                print(f"Error loading {zip_name}: {exc}", flush=True)

        print(
            f"Load summary for {args.cycle}: loaded {loaded_count}, skipped {skipped_count}, "
            f"failed {failed_count}, total {total}.",
            flush=True,
        )
        if failed_count > 0:
            raise SystemExit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
