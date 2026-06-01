"""Download metadata persistence and dashboard state for SQLite-backed tracking."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

from pipeline.data_scope import CANONICAL_DATA_SCOPE_PATH, load_data_scope_config


_SCHEMA_LOCK = Lock()


@dataclass(frozen=True)
class SqliteMetadataConfig:
    path: Path

    @property
    def source_label(self) -> str:
        return str(self.path)


@dataclass(frozen=True)
class CachedFetchMetadata:
    response_date: str | None = None
    last_modified: str | None = None
    etag: str | None = None
    content_length: int | None = None


@dataclass(frozen=True)
class DownloadStatusRecord:
    cycle: int
    table_name: str
    zip_name: str
    source_url: str
    fetch_status: str
    last_attempt_at: str
    updated_at: str
    http_status: int | None = None
    content_length: int | None = None
    response_date: str | None = None
    last_modified: str | None = None
    etag: str | None = None
    local_file_size: int | None = None
    bytes_downloaded: int | None = None
    progress_pct: float | None = None
    download_started_at: str | None = None
    download_completed_at: str | None = None
    error_text: str | None = None


@dataclass(frozen=True)
class FetchHistoryRecord:
    cycle: int
    table_name: str
    zip_name: str
    source_url: str
    fetch_status: str
    fetched_at: str
    http_status: int | None = None
    content_length: int | None = None
    response_date: str | None = None
    last_modified: str | None = None
    etag: str | None = None
    local_file_size: int | None = None
    bytes_downloaded: int | None = None
    download_started_at: str | None = None
    error_text: str | None = None
    fetch_id: int | None = None


class DownloadMetadataStore(Protocol):
    source_label: str

    def load_cached_fetch_metadata(self, cycle: int, table_name: str) -> CachedFetchMetadata: ...

    def record_download_status(self, record: DownloadStatusRecord) -> None: ...

    def record_fetch_history(self, record: FetchHistoryRecord) -> None: ...

    def list_download_statuses(self, limit: int = 100) -> tuple[DownloadStatusRecord, ...]: ...

    def load_successful_fetch_history(self) -> tuple[FetchHistoryRecord, ...]: ...


class SqliteDownloadMetadataStore:
    """Persist download metadata in SQLite and expose dashboard-friendly status rows."""

    def __init__(self, config: SqliteMetadataConfig, schema_path: Path) -> None:
        self._config = config
        self._schema_path = schema_path
        self.source_label = config.source_label
        self._config.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._config.path, timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def _ensure_schema(self) -> None:
        schema_sql = self._schema_path.read_text(encoding="utf-8")
        with _SCHEMA_LOCK:
            conn = self._connect()
            try:
                conn.executescript(schema_sql)
                conn.commit()
            finally:
                conn.close()

    def load_cached_fetch_metadata(self, cycle: int, table_name: str) -> CachedFetchMetadata:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT response_date, last_modified, etag, content_length
                FROM etl_download_status
                WHERE cycle = ? AND table_name = ?
                LIMIT 1
                """,
                (cycle, table_name),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return CachedFetchMetadata()
        return CachedFetchMetadata(
            response_date=_normalize_optional_text(row[0]),
            last_modified=_normalize_optional_text(row[1]),
            etag=_normalize_optional_text(row[2]),
            content_length=_normalize_optional_int(row[3]),
        )

    def record_download_status(self, record: DownloadStatusRecord) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO etl_download_status (
                    cycle,
                    table_name,
                    zip_name,
                    source_url,
                    fetch_status,
                    http_status,
                    content_length,
                    response_date,
                    last_modified,
                    etag,
                    local_file_size,
                    bytes_downloaded,
                    progress_pct,
                    download_started_at,
                    download_completed_at,
                    last_attempt_at,
                    error_text,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cycle, table_name) DO UPDATE SET
                    zip_name = excluded.zip_name,
                    source_url = excluded.source_url,
                    fetch_status = excluded.fetch_status,
                    http_status = excluded.http_status,
                    content_length = excluded.content_length,
                    response_date = excluded.response_date,
                    last_modified = excluded.last_modified,
                    etag = excluded.etag,
                    local_file_size = excluded.local_file_size,
                    bytes_downloaded = excluded.bytes_downloaded,
                    progress_pct = excluded.progress_pct,
                    download_started_at = excluded.download_started_at,
                    download_completed_at = excluded.download_completed_at,
                    last_attempt_at = excluded.last_attempt_at,
                    error_text = excluded.error_text,
                    updated_at = excluded.updated_at
                """,
                (
                    record.cycle,
                    record.table_name,
                    record.zip_name,
                    record.source_url,
                    record.fetch_status,
                    record.http_status,
                    record.content_length,
                    record.response_date,
                    record.last_modified,
                    record.etag,
                    record.local_file_size,
                    record.bytes_downloaded,
                    record.progress_pct,
                    record.download_started_at,
                    record.download_completed_at,
                    record.last_attempt_at,
                    record.error_text,
                    record.updated_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def record_fetch_history(self, record: FetchHistoryRecord) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO etl_fetch_history (
                    cycle,
                    table_name,
                    zip_name,
                    source_url,
                    fetch_status,
                    http_status,
                    content_length,
                    response_date,
                    last_modified,
                    etag,
                    local_file_size,
                    bytes_downloaded,
                    download_started_at,
                    fetched_at,
                    error_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.cycle,
                    record.table_name,
                    record.zip_name,
                    record.source_url,
                    record.fetch_status,
                    record.http_status,
                    record.content_length,
                    record.response_date,
                    record.last_modified,
                    record.etag,
                    record.local_file_size,
                    record.bytes_downloaded,
                    record.download_started_at,
                    record.fetched_at,
                    record.error_text,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def list_download_statuses(self, limit: int = 100) -> tuple[DownloadStatusRecord, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    cycle,
                    table_name,
                    zip_name,
                    source_url,
                    fetch_status,
                    last_attempt_at,
                    updated_at,
                    http_status,
                    content_length,
                    response_date,
                    last_modified,
                    etag,
                    local_file_size,
                    bytes_downloaded,
                    progress_pct,
                    download_started_at,
                    download_completed_at,
                    error_text
                FROM etl_download_status
                ORDER BY cycle DESC, table_name ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        finally:
            conn.close()
        return tuple(_status_record_from_row(row) for row in rows)

    def load_successful_fetch_history(self) -> tuple[FetchHistoryRecord, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(fetch_id, rowid) AS sequence_number,
                    cycle,
                    table_name,
                    zip_name,
                    source_url,
                    fetch_status,
                    http_status,
                    content_length,
                    response_date,
                    last_modified,
                    etag,
                    local_file_size,
                    bytes_downloaded,
                    download_started_at,
                    fetched_at,
                    error_text
                FROM etl_fetch_history
                WHERE TRIM(COALESCE(table_name, '')) != ''
                  AND TRIM(COALESCE(fetched_at, '')) != ''
                ORDER BY cycle ASC, table_name ASC, fetched_at ASC, COALESCE(fetch_id, rowid) ASC
                """
            ).fetchall()
        finally:
            conn.close()
        return tuple(_history_record_from_row(row) for row in rows)


class InMemoryDownloadMetadataStore:
    """Small in-memory metadata store used by tests."""

    def __init__(
        self,
        *,
        source_label: str = "in-memory",
        statuses: tuple[DownloadStatusRecord, ...] = (),
        history: tuple[FetchHistoryRecord, ...] = (),
    ) -> None:
        self.source_label = source_label
        self._statuses = {(record.cycle, record.table_name): record for record in statuses}
        self._history = list(history)

    def load_cached_fetch_metadata(self, cycle: int, table_name: str) -> CachedFetchMetadata:
        record = self._statuses.get((cycle, table_name))
        if record is None:
            return CachedFetchMetadata()
        return CachedFetchMetadata(
            response_date=record.response_date,
            last_modified=record.last_modified,
            etag=record.etag,
            content_length=record.content_length,
        )

    def record_download_status(self, record: DownloadStatusRecord) -> None:
        self._statuses[(record.cycle, record.table_name)] = record

    def record_fetch_history(self, record: FetchHistoryRecord) -> None:
        sequence_number = len(self._history) + 1 if record.fetch_id is None else record.fetch_id
        self._history.append(
            FetchHistoryRecord(
                cycle=record.cycle,
                table_name=record.table_name,
                zip_name=record.zip_name,
                source_url=record.source_url,
                fetch_status=record.fetch_status,
                fetched_at=record.fetched_at,
                http_status=record.http_status,
                content_length=record.content_length,
                response_date=record.response_date,
                last_modified=record.last_modified,
                etag=record.etag,
                local_file_size=record.local_file_size,
                bytes_downloaded=record.bytes_downloaded,
                download_started_at=record.download_started_at,
                error_text=record.error_text,
                fetch_id=sequence_number,
            )
        )

    def list_download_statuses(self, limit: int = 100) -> tuple[DownloadStatusRecord, ...]:
        records = sorted(self._statuses.values(), key=lambda record: (-record.cycle, record.table_name))
        return tuple(records[:limit])

    def load_successful_fetch_history(self) -> tuple[FetchHistoryRecord, ...]:
        return tuple(
            sorted(
                self._history,
                key=lambda record: (record.cycle, record.table_name, record.fetched_at, record.fetch_id or 0),
            )
        )


def metadata_sqlite_schema_path(repo_root: Path) -> Path:
    return repo_root / "sql" / "schema" / "001_create_metadata_sqlite.sql"


def load_sqlite_metadata_config(config: dict[str, Any], repo_root: Path) -> SqliteMetadataConfig:
    metadata_database = config.get("metadata_database")
    if not isinstance(metadata_database, dict):
        raise SystemExit("metadata_database.sqlite config is required in config/data_scope.yml")

    sqlite = metadata_database.get("sqlite")
    if not isinstance(sqlite, dict):
        raise SystemExit("metadata_database.sqlite config is required in config/data_scope.yml")

    raw_path = _normalize_required_text(sqlite.get("path"), "metadata_database.sqlite.path")
    path = Path(raw_path)
    if not path.is_absolute():
        path = repo_root / path

    return SqliteMetadataConfig(path=path)


def build_sqlite_metadata_store(repo_root: Path) -> SqliteDownloadMetadataStore:
    config = load_data_scope_config(repo_root / CANONICAL_DATA_SCOPE_PATH)
    return SqliteDownloadMetadataStore(load_sqlite_metadata_config(config, repo_root), metadata_sqlite_schema_path(repo_root))


def _normalize_required_text(value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise SystemExit(f"{context} must be a string")
    trimmed = value.strip()
    if not trimmed:
        raise SystemExit(f"{context} must not be empty")
    return trimmed


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
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _normalize_optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _status_record_from_row(row: tuple[Any, ...]) -> DownloadStatusRecord:
    return DownloadStatusRecord(
        cycle=int(row[0]),
        table_name=str(row[1]),
        zip_name=str(row[2]),
        source_url=str(row[3]),
        fetch_status=str(row[4]),
        last_attempt_at=str(row[5]),
        updated_at=str(row[6]),
        http_status=_normalize_optional_int(row[7]),
        content_length=_normalize_optional_int(row[8]),
        response_date=_normalize_optional_text(row[9]),
        last_modified=_normalize_optional_text(row[10]),
        etag=_normalize_optional_text(row[11]),
        local_file_size=_normalize_optional_int(row[12]),
        bytes_downloaded=_normalize_optional_int(row[13]),
        progress_pct=_normalize_optional_float(row[14]),
        download_started_at=_normalize_optional_text(row[15]),
        download_completed_at=_normalize_optional_text(row[16]),
        error_text=_normalize_optional_text(row[17]),
    )


def _history_record_from_row(row: tuple[Any, ...]) -> FetchHistoryRecord:
    return FetchHistoryRecord(
        fetch_id=_normalize_optional_int(row[0]),
        cycle=int(row[1]),
        table_name=str(row[2]),
        zip_name=str(row[3]),
        source_url=str(row[4]),
        fetch_status=str(row[5]),
        http_status=_normalize_optional_int(row[6]),
        content_length=_normalize_optional_int(row[7]),
        response_date=_normalize_optional_text(row[8]),
        last_modified=_normalize_optional_text(row[9]),
        etag=_normalize_optional_text(row[10]),
        local_file_size=_normalize_optional_int(row[11]),
        bytes_downloaded=_normalize_optional_int(row[12]),
        download_started_at=_normalize_optional_text(row[13]),
        fetched_at=str(row[14]),
        error_text=_normalize_optional_text(row[15]),
    )
