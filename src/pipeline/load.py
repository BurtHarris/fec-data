"""Transform downloaded FEC ZIP artifacts into DuckDB raw tables."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sqlite3
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import duckdb

from pipeline.etl_config import DEFAULT_ETL_CONFIG_PATH, load_etl_model_config, repo_root


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


def drop_legacy_duckdb_metadata_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Drop legacy metadata/QA tables from DuckDB now managed in SQLite."""

    rows = conn.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ('etl', 'review')
        """
    ).fetchall()

    for schema, table in rows:
        conn.execute(f"DROP TABLE IF EXISTS {schema}.{table}")


def latest_loaded_hash(
    conn: sqlite3.Connection,
    cycle: int,
    table: str,
    target_table: str,
    source_zip_path: str,
) -> str | None:
    """Read the most recent source file hash for this exact table load target."""

    row = conn.execute(
        """
        SELECT source_file_hash
        FROM etl_load_history
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
    conn: sqlite3.Connection,
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
                DELETE FROM etl_current_state
        WHERE entity_type = 'table'
          AND cycle = ?
          AND table_name = ?
        """,
        [cycle, table],
    )

    conn.execute(
        """
        INSERT INTO etl_current_state (
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
            COALESCE((SELECT MAX(state_id) + 1 FROM etl_current_state), 1),
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
            CURRENT_TIMESTAMP
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
    conn.commit()


def upsert_current_state_failure(
    conn: sqlite3.Connection,
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
                DELETE FROM etl_current_state
        WHERE entity_type = 'table'
          AND cycle = ?
          AND table_name = ?
        """,
        [cycle, table],
    )

    conn.execute(
        """
        INSERT INTO etl_current_state (
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
            COALESCE((SELECT MAX(state_id) + 1 FROM etl_current_state), 1),
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
            CURRENT_TIMESTAMP
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
    conn.commit()


def insert_load_history(
    conn: sqlite3.Connection,
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
        INSERT INTO etl_load_history (
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
            COALESCE((SELECT MAX(load_id) + 1 FROM etl_load_history), 1),
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            CURRENT_TIMESTAMP
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
    conn.commit()


def resolve_targets(cycle: int, selected_tables: list[str], root: Path) -> list[LoadTarget]:
    """Resolve table metadata and local file paths for this load run."""

    cycle_suffix = str(cycle)[-2:]
    config_path = root / DEFAULT_ETL_CONFIG_PATH
    configs = load_etl_model_config(config_path, cycle_suffix=cycle_suffix)
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


def infer_cycles_from_data(root: Path) -> list[int]:
    """Infer cycle years from downloaded ZIP layout under data/<cycle>/."""

    data_dir = root / "data"
    if not data_dir.exists():
        return []

    cycles: list[int] = []
    for child in data_dir.iterdir():
        if not child.is_dir() or not child.name.isdigit() or len(child.name) != 4:
            continue

        cycle = int(child.name)
        cycle_suffix = child.name[-2:]
        has_matching_zip = any(
            item.is_file() and re.match(rf"^[a-z0-9_]+{cycle_suffix}\.zip$", item.name)
            for item in child.iterdir()
        )
        if has_matching_zip:
            cycles.append(cycle)

    return sorted(cycles)


def infer_tables_for_cycle(cycle: int, root: Path, default_tables: list[str]) -> list[str]:
    """Infer tables by checking which expected ZIP files exist for a cycle."""

    cycle_suffix = str(cycle)[-2:]
    cycle_dir = root / "data" / str(cycle)
    inferred: list[str] = []

    for table in default_tables:
        if (cycle_dir / f"{table}{cycle_suffix}.zip").exists():
            inferred.append(table)

    return inferred


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
    parser.add_argument("--cycle", type=int, help="Election cycle year (for example: 2026)")
    parser.add_argument(
        "--tables",
        nargs="*",
        help="Optional table list (comma-separated or repeated names): cm cn indiv",
    )
    parser.add_argument("--db-path", default="db/fec.duckdb", help="DuckDB file path")
    parser.add_argument(
        "--metadata-db-path",
        default="db/fec-metadata.sqlite",
        help="SQLite metadata database path",
    )
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

    root = repo_root()

    if args.cycle is not None and args.cycle % 2 != 0:
        raise SystemExit(f"Cycle must be an even election year: {args.cycle}")

    cycles = [args.cycle] if args.cycle is not None else infer_cycles_from_data(root)
    if not cycles:
        raise SystemExit("No cycles could be inferred from downloaded ZIPs under data/<cycle>/. Use --cycle.")

    db_path = Path(args.db_path)
    if not db_path.is_absolute():
        db_path = root / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    metadata_db_path = Path(args.metadata_db_path)
    if not metadata_db_path.is_absolute():
        metadata_db_path = root / metadata_db_path
    metadata_db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_sql_path = Path(args.schema_sql)
    if not schema_sql_path.is_absolute():
        schema_sql_path = root / schema_sql_path
    if not schema_sql_path.exists():
        raise SystemExit(f"Schema SQL not found: {schema_sql_path}")

    metadata_schema_sql_path = root / "sql" / "schema" / "001_create_metadata_sqlite.sql"
    if not metadata_schema_sql_path.exists():
        raise SystemExit(f"Metadata schema SQL not found: {metadata_schema_sql_path}")

    extract_root = root / "tmp" / "load-fec"
    extract_root.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path))
    metadata_conn = sqlite3.connect(str(metadata_db_path))
    try:
        conn.execute(schema_sql_path.read_text(encoding="utf-8"))
        drop_legacy_duckdb_metadata_tables(conn)
        metadata_conn.executescript(metadata_schema_sql_path.read_text(encoding="utf-8"))
        metadata_conn.commit()

        total_loaded = 0
        total_skipped = 0
        total_failed = 0
        total_targets = 0

        for cycle in cycles:
            cycle_suffix = str(cycle)[-2:]
            configs = load_etl_model_config(root / DEFAULT_ETL_CONFIG_PATH, cycle_suffix=cycle_suffix)
            default_tables = [item.name for item in configs]
            selected_tables = (
                normalize_tables(args.tables, default_tables)
                if args.tables
                else infer_tables_for_cycle(cycle, root, default_tables)
            )

            if not selected_tables:
                print(f"Cycle {cycle}: no table ZIPs inferred, skipping.", flush=True)
                continue

            print(f"Cycle {cycle}: loading tables {', '.join(selected_tables)}", flush=True)
            targets = resolve_targets(cycle, selected_tables, root)
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
                        metadata_conn,
                        cycle=cycle,
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
                        "{CYCLE}": str(cycle),
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
                        metadata_conn,
                        cycle=cycle,
                        table=target.table,
                        source_zip_path=source_zip_path,
                        source_entry_name=target.source_entry,
                        source_file_hash=source_hash,
                        target_table=target.target_table,
                        row_count=row_count,
                        duration_ms=duration_ms,
                    )
                    upsert_current_state_success(
                        metadata_conn,
                        cycle=cycle,
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
                        metadata_conn,
                        cycle=cycle,
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
                f"Load summary for {cycle}: loaded {loaded_count}, skipped {skipped_count}, "
                f"failed {failed_count}, total {total}.",
                flush=True,
            )

            total_loaded += loaded_count
            total_skipped += skipped_count
            total_failed += failed_count
            total_targets += total

        print(
            f"Overall load summary: loaded {total_loaded}, skipped {total_skipped}, "
            f"failed {total_failed}, total {total_targets}.",
            flush=True,
        )

        if total_failed > 0:
            raise SystemExit(1)
    finally:
        metadata_conn.close()
        conn.close()


if __name__ == "__main__":
    main()
