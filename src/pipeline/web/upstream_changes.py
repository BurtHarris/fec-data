"""Analytics helpers for the Upstream Changes operations screen."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median


SUCCESS_FETCH_STATUSES = {"downloaded", "fetched", "success"}


@dataclass(frozen=True)
class UpstreamChangeEvent:
    cycle: int
    table_name: str
    fetched_at: str
    previous_fetched_at: str
    changed_fields: tuple[str, ...]
    current_etag: str | None
    previous_etag: str | None
    current_last_modified: str | None
    previous_last_modified: str | None
    current_content_length: int | None
    previous_content_length: int | None


@dataclass(frozen=True)
class UpstreamCadenceSummary:
    cycle: int
    table_name: str
    change_count: int
    median_interval_days: float | None
    latest_change_at: str


@dataclass(frozen=True)
class UpstreamMonthlyRollup:
    month_label: str
    change_count: int
    asset_count: int


@dataclass(frozen=True)
class UpstreamTableSummary:
    table_name: str
    change_count: int
    cycle_count: int
    latest_change_at: str


@dataclass(frozen=True)
class UpstreamChangesReport:
    source_path: Path
    status: str
    message: str
    successful_fetch_count: int = 0
    tracked_asset_count: int = 0
    change_event_count: int = 0
    latest_fetch_at: str | None = None
    recent_events: tuple[UpstreamChangeEvent, ...] = ()
    cadence_summaries: tuple[UpstreamCadenceSummary, ...] = ()
    monthly_rollups: tuple[UpstreamMonthlyRollup, ...] = ()
    table_summaries: tuple[UpstreamTableSummary, ...] = ()


@dataclass(frozen=True)
class _FetchHistoryRow:
    sequence_number: int
    cycle: int
    table_name: str
    fetched_at: str
    fetched_at_dt: datetime
    etag: str | None
    last_modified: str | None
    content_length: int | None


def load_upstream_changes_report(
    metadata_db_path: Path,
    recent_limit: int = 12,
    cadence_limit: int = 12,
    rollup_limit: int = 12,
) -> UpstreamChangesReport:
    """Load upstream metadata history and derive deterministic change analytics."""

    if not metadata_db_path.exists():
        return UpstreamChangesReport(
            source_path=metadata_db_path,
            status="unavailable",
            message=f"Metadata history database not found: {metadata_db_path}",
        )

    conn = sqlite3.connect(metadata_db_path)
    try:
        if not _table_exists(conn, "etl_fetch_history"):
            return UpstreamChangesReport(
                source_path=metadata_db_path,
                status="unavailable",
                message="Metadata history table etl_fetch_history is unavailable.",
            )
        rows = _load_successful_fetch_rows(conn)
    finally:
        conn.close()

    if not rows:
        return UpstreamChangesReport(
            source_path=metadata_db_path,
            status="empty",
            message="No successful fetch history is available yet.",
        )

    events = _detect_change_events(rows)
    cadence_summaries = _build_cadence_summaries(events, limit=cadence_limit)
    monthly_rollups = _build_monthly_rollups(events, limit=rollup_limit)
    table_summaries = _build_table_summaries(events)

    latest_fetch_at = max(rows, key=lambda row: (row.fetched_at_dt, row.sequence_number)).fetched_at
    recent_events = tuple(
        sorted(events, key=lambda event: _sort_key(event.fetched_at), reverse=True)[:recent_limit]
    )
    status = "ready" if events else "empty"
    message = (
        "Upstream metadata shifts derived from successful fetch history."
        if events
        else "Successful fetch history exists, but no upstream metadata shifts have been detected yet."
    )
    return UpstreamChangesReport(
        source_path=metadata_db_path,
        status=status,
        message=message,
        successful_fetch_count=len(rows),
        tracked_asset_count=len({(row.cycle, row.table_name) for row in rows}),
        change_event_count=len(events),
        latest_fetch_at=latest_fetch_at,
        recent_events=recent_events,
        cadence_summaries=cadence_summaries,
        monthly_rollups=monthly_rollups,
        table_summaries=table_summaries,
    )


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _load_successful_fetch_rows(conn: sqlite3.Connection) -> list[_FetchHistoryRow]:
    records: list[_FetchHistoryRow] = []
    rows = conn.execute(
        """
        SELECT
            rowid,
            fetch_id,
            cycle,
            table_name,
            fetch_status,
            http_status,
            content_length,
            last_modified,
            etag,
            fetched_at
        FROM etl_fetch_history
        WHERE TRIM(COALESCE(table_name, '')) != ''
          AND TRIM(COALESCE(fetched_at, '')) != ''
        ORDER BY
            cycle ASC,
            table_name ASC,
            fetched_at ASC,
            COALESCE(fetch_id, rowid) ASC,
            rowid ASC
        """
    ).fetchall()

    for row in rows:
        rowid, fetch_id, cycle, table_name, fetch_status, http_status, content_length, last_modified, etag, fetched_at = row
        if not _is_successful_fetch(fetch_status, http_status):
            continue
        cycle_number = _normalize_cycle(cycle)
        table = _normalize_text(table_name)
        fetched = _normalize_text(fetched_at)
        if cycle_number is None or table is None or fetched is None:
            continue
        fetched_at_dt = _parse_timestamp(fetched)
        if fetched_at_dt is None:
            continue
        sequence_number = int(fetch_id) if isinstance(fetch_id, int) else int(rowid)
        records.append(
            _FetchHistoryRow(
                sequence_number=sequence_number,
                cycle=cycle_number,
                table_name=table,
                fetched_at=fetched,
                fetched_at_dt=fetched_at_dt,
                etag=_normalize_text(etag),
                last_modified=_normalize_text(last_modified),
                content_length=_normalize_int(content_length),
            )
        )

    return records


def _is_successful_fetch(fetch_status: object, http_status: object) -> bool:
    normalized_status = (_normalize_text(fetch_status) or "").lower()
    status_code = _normalize_int(http_status)
    if status_code is not None and 200 <= status_code < 300 and normalized_status not in {"error", "failed"}:
        return True
    return normalized_status in SUCCESS_FETCH_STATUSES


def _normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _normalize_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _normalize_cycle(value: object) -> int | None:
    normalized = _normalize_int(value)
    if normalized is None or normalized < 0:
        return None
    return normalized


def _parse_timestamp(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _sort_key(timestamp: str) -> tuple[datetime, str]:
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return (datetime.min.replace(tzinfo=timezone.utc), timestamp)
    return (parsed, timestamp)


def _detect_change_events(rows: list[_FetchHistoryRow]) -> list[UpstreamChangeEvent]:
    events: list[UpstreamChangeEvent] = []
    previous_by_asset: dict[tuple[int, str], _FetchHistoryRow] = {}

    for row in rows:
        asset_key = (row.cycle, row.table_name)
        previous = previous_by_asset.get(asset_key)
        if previous is not None:
            changed_fields = _changed_fields(previous, row)
            if changed_fields:
                events.append(
                    UpstreamChangeEvent(
                        cycle=row.cycle,
                        table_name=row.table_name,
                        fetched_at=row.fetched_at,
                        previous_fetched_at=previous.fetched_at,
                        changed_fields=changed_fields,
                        current_etag=row.etag,
                        previous_etag=previous.etag,
                        current_last_modified=row.last_modified,
                        previous_last_modified=previous.last_modified,
                        current_content_length=row.content_length,
                        previous_content_length=previous.content_length,
                    )
                )
        previous_by_asset[asset_key] = row

    return events


def _changed_fields(previous: _FetchHistoryRow, current: _FetchHistoryRow) -> tuple[str, ...]:
    changed_fields: list[str] = []
    if _field_changed(previous.etag, current.etag):
        changed_fields.append("etag")
    if _field_changed(previous.last_modified, current.last_modified):
        changed_fields.append("last_modified")
    if _field_changed(previous.content_length, current.content_length):
        changed_fields.append("content_length")
    return tuple(changed_fields)


def _field_changed(previous: str | int | None, current: str | int | None) -> bool:
    if current is None:
        return False
    if previous is None:
        return True
    return current != previous


def _build_cadence_summaries(
    events: list[UpstreamChangeEvent],
    limit: int,
) -> tuple[UpstreamCadenceSummary, ...]:
    by_asset: dict[tuple[int, str], list[UpstreamChangeEvent]] = {}
    for event in events:
        by_asset.setdefault((event.cycle, event.table_name), []).append(event)

    summaries: list[UpstreamCadenceSummary] = []
    for (cycle, table_name), asset_events in by_asset.items():
        ordered = sorted(asset_events, key=lambda event: _sort_key(event.fetched_at))
        median_interval_days: float | None = None
        if len(ordered) >= 2:
            intervals = [
                (_parse_timestamp(current.fetched_at) - _parse_timestamp(previous.fetched_at)).total_seconds() / 86400.0
                for previous, current in zip(ordered, ordered[1:], strict=False)
            ]
            median_interval_days = round(float(median(intervals)), 1)
        summaries.append(
            UpstreamCadenceSummary(
                cycle=cycle,
                table_name=table_name,
                change_count=len(ordered),
                median_interval_days=median_interval_days,
                latest_change_at=ordered[-1].fetched_at,
            )
        )

    ordered_summaries = sorted(
        summaries,
        key=lambda summary: (
            summary.change_count,
            summary.median_interval_days is not None,
            summary.median_interval_days or -1.0,
            _sort_key(summary.latest_change_at),
            summary.table_name,
            summary.cycle,
        ),
        reverse=True,
    )
    return tuple(ordered_summaries[:limit])


def _build_monthly_rollups(
    events: list[UpstreamChangeEvent],
    limit: int,
) -> tuple[UpstreamMonthlyRollup, ...]:
    grouped: dict[str, set[tuple[int, str]]] = {}
    counts: dict[str, int] = {}
    for event in events:
        parsed = _parse_timestamp(event.fetched_at)
        if parsed is None:
            continue
        month_label = parsed.strftime("%Y-%m")
        counts[month_label] = counts.get(month_label, 0) + 1
        grouped.setdefault(month_label, set()).add((event.cycle, event.table_name))

    rollups = [
        UpstreamMonthlyRollup(
            month_label=month_label,
            change_count=counts[month_label],
            asset_count=len(grouped[month_label]),
        )
        for month_label in grouped
    ]
    ordered_rollups = sorted(rollups, key=lambda rollup: rollup.month_label, reverse=True)
    return tuple(ordered_rollups[:limit])


def _build_table_summaries(events: list[UpstreamChangeEvent]) -> tuple[UpstreamTableSummary, ...]:
    grouped: dict[str, list[UpstreamChangeEvent]] = {}
    for event in events:
        grouped.setdefault(event.table_name, []).append(event)

    summaries: list[UpstreamTableSummary] = []
    for table_name, table_events in grouped.items():
        latest = max(table_events, key=lambda event: _sort_key(event.fetched_at))
        summaries.append(
            UpstreamTableSummary(
                table_name=table_name,
                change_count=len(table_events),
                cycle_count=len({event.cycle for event in table_events}),
                latest_change_at=latest.fetched_at,
            )
        )

    ordered = sorted(
        summaries,
        key=lambda summary: (summary.change_count, summary.cycle_count, _sort_key(summary.latest_change_at), summary.table_name),
        reverse=True,
    )
    return tuple(ordered)
