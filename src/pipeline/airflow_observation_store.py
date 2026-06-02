"""SQLite persistence helpers for Airflow-based upstream metadata observations."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_SCHEMA_VERSION = 1
MAX_ERROR_MESSAGE_LEN = 500


class DomainSchemaVersionError(RuntimeError):
    """Raised when the domain observation schema version is incompatible."""


@dataclass(frozen=True)
class ObservationRecord:
    cycle: int
    table_name: str
    zip_name: str
    source_url: str
    fetch_status: str
    http_status: int | None
    response_date: str | None
    last_modified: str | None
    etag: str | None
    content_length: int | None
    error_class: str | None
    error_message: str | None
    dag_id: str
    dag_run_id: str
    task_id: str
    map_index: int
    try_number: int


@dataclass(frozen=True)
class ObservationInsertResult:
    observation_id: int
    change_detected: bool | None


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _normalize_optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _truncate_error_message(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= MAX_ERROR_MESSAGE_LEN:
        return value
    return value[: MAX_ERROR_MESSAGE_LEN - 3] + "..."


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def ensure_domain_schema(db_path: Path) -> None:
    """Create missing tables and enforce compatible schema version."""

    conn = _connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS airflow_domain_schema_version (
                version INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS airflow_upstream_observation_history (
                observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                observed_at TEXT NOT NULL,
                cycle INTEGER NOT NULL,
                table_name TEXT NOT NULL,
                zip_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                fetch_status TEXT NOT NULL,
                http_status INTEGER,
                response_date TEXT,
                last_modified TEXT,
                etag TEXT,
                content_length INTEGER,
                change_detected INTEGER,
                error_class TEXT,
                error_message TEXT,
                dag_id TEXT NOT NULL,
                dag_run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                map_index INTEGER NOT NULL,
                try_number INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_airflow_obs_cycle_table_time
                ON airflow_upstream_observation_history (cycle, table_name, observed_at);

            CREATE INDEX IF NOT EXISTS idx_airflow_obs_dag_run
                ON airflow_upstream_observation_history (dag_id, dag_run_id);

            CREATE TABLE IF NOT EXISTS airflow_upstream_snapshot (
                cycle INTEGER NOT NULL,
                table_name TEXT NOT NULL,
                zip_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                fetch_status TEXT NOT NULL,
                http_status INTEGER,
                response_date TEXT,
                last_modified TEXT,
                etag TEXT,
                content_length INTEGER,
                change_detected INTEGER,
                error_class TEXT,
                error_message TEXT,
                last_observed_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_observation_id INTEGER NOT NULL,
                dag_id TEXT NOT NULL,
                dag_run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                map_index INTEGER NOT NULL,
                try_number INTEGER NOT NULL,
                PRIMARY KEY (cycle, table_name)
            );
            """
        )

        row = conn.execute("SELECT version FROM airflow_domain_schema_version LIMIT 1").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO airflow_domain_schema_version (version, updated_at) VALUES (?, ?)",
                (EXPECTED_SCHEMA_VERSION, iso_utc_now()),
            )
            conn.commit()
            return

        current_version = int(row[0])
        if current_version != EXPECTED_SCHEMA_VERSION:
            raise DomainSchemaVersionError(
                "Domain observation schema mismatch: "
                f"expected={EXPECTED_SCHEMA_VERSION} found={current_version}"
            )

        conn.commit()
    finally:
        conn.close()


def _find_previous_success(
    conn: sqlite3.Connection,
    cycle: int,
    table_name: str,
) -> tuple[str | None, str | None, int | None] | None:
    return conn.execute(
        """
        SELECT etag, last_modified, content_length
        FROM airflow_upstream_observation_history
        WHERE cycle = ?
          AND table_name = ?
          AND fetch_status = 'succeeded'
        ORDER BY observation_id DESC
        LIMIT 1
        """,
        (cycle, table_name),
    ).fetchone()


def _compute_change_detected(
    fetch_status: str,
    previous_success: tuple[str | None, str | None, int | None] | None,
    current_etag: str | None,
    current_last_modified: str | None,
    current_content_length: int | None,
) -> bool | None:
    if fetch_status != "succeeded":
        return None
    if previous_success is None:
        return False

    prev_etag, prev_last_modified, prev_content_length = previous_success
    return (
        prev_etag != current_etag
        or prev_last_modified != current_last_modified
        or prev_content_length != current_content_length
    )


def insert_observation(db_path: Path, record: ObservationRecord) -> ObservationInsertResult:
    """Insert one observation attempt with per-attempt Airflow identity."""

    observed_at = iso_utc_now()
    conn = _connect(db_path)
    try:
        previous_success = _find_previous_success(conn, record.cycle, record.table_name)
        change_detected = _compute_change_detected(
            record.fetch_status,
            previous_success,
            record.etag,
            record.last_modified,
            record.content_length,
        )

        conn.execute(
            """
            INSERT INTO airflow_upstream_observation_history (
                observed_at,
                cycle,
                table_name,
                zip_name,
                source_url,
                fetch_status,
                http_status,
                response_date,
                last_modified,
                etag,
                content_length,
                change_detected,
                error_class,
                error_message,
                dag_id,
                dag_run_id,
                task_id,
                map_index,
                try_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observed_at,
                record.cycle,
                record.table_name,
                record.zip_name,
                record.source_url,
                record.fetch_status,
                record.http_status,
                _normalize_optional_text(record.response_date),
                _normalize_optional_text(record.last_modified),
                _normalize_optional_text(record.etag),
                _normalize_optional_int(record.content_length),
                None if change_detected is None else int(change_detected),
                _normalize_optional_text(record.error_class),
                _truncate_error_message(_normalize_optional_text(record.error_message)),
                record.dag_id,
                record.dag_run_id,
                record.task_id,
                record.map_index,
                record.try_number,
            ),
        )
        observation_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.commit()
        return ObservationInsertResult(observation_id=observation_id, change_detected=change_detected)
    finally:
        conn.close()


def upsert_snapshot_from_run(db_path: Path, dag_id: str, dag_run_id: str) -> int:
    """Update snapshot rows for successful observations in the given DAG run."""

    now = iso_utc_now()
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT h.observation_id,
                   h.observed_at,
                   h.cycle,
                   h.table_name,
                   h.zip_name,
                   h.source_url,
                   h.fetch_status,
                   h.http_status,
                   h.response_date,
                   h.last_modified,
                   h.etag,
                   h.content_length,
                   h.change_detected,
                   h.error_class,
                   h.error_message,
                   h.dag_id,
                   h.dag_run_id,
                   h.task_id,
                   h.map_index,
                   h.try_number
            FROM airflow_upstream_observation_history h
            JOIN (
                SELECT cycle, table_name, MAX(observation_id) AS max_observation_id
                FROM airflow_upstream_observation_history
                WHERE dag_id = ?
                  AND dag_run_id = ?
                  AND fetch_status = 'succeeded'
                GROUP BY cycle, table_name
            ) selected
            ON h.observation_id = selected.max_observation_id
            ORDER BY h.cycle, h.table_name
            """,
            (dag_id, dag_run_id),
        ).fetchall()

        updated = 0
        for row in rows:
            conn.execute(
                """
                INSERT INTO airflow_upstream_snapshot (
                    cycle,
                    table_name,
                    zip_name,
                    source_url,
                    fetch_status,
                    http_status,
                    response_date,
                    last_modified,
                    etag,
                    content_length,
                    change_detected,
                    error_class,
                    error_message,
                    last_observed_at,
                    updated_at,
                    last_observation_id,
                    dag_id,
                    dag_run_id,
                    task_id,
                    map_index,
                    try_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cycle, table_name) DO UPDATE SET
                    zip_name = excluded.zip_name,
                    source_url = excluded.source_url,
                    fetch_status = excluded.fetch_status,
                    http_status = excluded.http_status,
                    response_date = excluded.response_date,
                    last_modified = excluded.last_modified,
                    etag = excluded.etag,
                    content_length = excluded.content_length,
                    change_detected = excluded.change_detected,
                    error_class = excluded.error_class,
                    error_message = excluded.error_message,
                    last_observed_at = excluded.last_observed_at,
                    updated_at = excluded.updated_at,
                    last_observation_id = excluded.last_observation_id,
                    dag_id = excluded.dag_id,
                    dag_run_id = excluded.dag_run_id,
                    task_id = excluded.task_id,
                    map_index = excluded.map_index,
                    try_number = excluded.try_number
                """,
                (
                    int(row[2]),
                    str(row[3]),
                    str(row[4]),
                    str(row[5]),
                    str(row[6]),
                    _normalize_optional_int(row[7]),
                    _normalize_optional_text(row[8]),
                    _normalize_optional_text(row[9]),
                    _normalize_optional_text(row[10]),
                    _normalize_optional_int(row[11]),
                    _normalize_optional_int(row[12]),
                    _normalize_optional_text(row[13]),
                    _normalize_optional_text(row[14]),
                    str(row[1]),
                    now,
                    int(row[0]),
                    str(row[15]),
                    str(row[16]),
                    str(row[17]),
                    int(row[18]),
                    int(row[19]),
                ),
            )
            updated += 1

        conn.commit()
        return updated
    finally:
        conn.close()
