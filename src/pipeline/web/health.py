"""Health metrics collection and rendering for the Monitoring & Health dashboard."""

from __future__ import annotations

import collections
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Protocol

from pipeline.metadata_store import DownloadStatusRecord


LOG_TAIL_LINES = 50


class _RunnerProtocol(Protocol):
    def list_recent_runs(self, limit: int = 25) -> list[object]: ...


@dataclass(frozen=True)
class DuckdbTableInfo:
    name: str
    row_count: int


@dataclass(frozen=True)
class DuckdbHealthInfo:
    db_path: Path
    file_size_bytes: int | None
    last_modified: str | None
    tables: tuple[DuckdbTableInfo, ...]
    error: str | None


@dataclass(frozen=True)
class CycleDownloadSummary:
    cycle: int
    downloaded_tables: int
    total_tables: int
    failed_tables: int
    last_successful_at: str | None


@dataclass(frozen=True)
class RecentRun:
    run_number: int | None
    command: str
    operator_id: str
    lifecycle_state: str
    completed_at: str | None
    exit_code: int | None
    log_path: str | None


@dataclass
class HealthMetrics:
    collected_at: str
    duckdb: DuckdbHealthInfo
    cycle_summaries: tuple[CycleDownloadSummary, ...]
    recent_failed_runs: tuple[RecentRun, ...]
    recent_completed_runs: tuple[RecentRun, ...]
    log_tail: str | None
    log_path: str | None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "n/a"
    if value >= 1024 * 1024 * 1024:
        return f"{value / (1024 ** 3):.2f} GB"
    if value >= 1024 * 1024:
        return f"{value / (1024 ** 2):.1f} MB"
    if value >= 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value} bytes"


def collect_duckdb_info(db_path: Path) -> DuckdbHealthInfo:
    if not db_path.exists():
        return DuckdbHealthInfo(
            db_path=db_path,
            file_size_bytes=None,
            last_modified=None,
            tables=(),
            error="DuckDB file not found",
        )

    try:
        stat = db_path.stat()
        file_size = stat.st_size
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError as exc:
        return DuckdbHealthInfo(
            db_path=db_path,
            file_size_bytes=None,
            last_modified=None,
            tables=(),
            error=f"Could not stat DuckDB file: {exc}",
        )

    try:
        import duckdb  # type: ignore[import]

        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            table_rows = conn.execute("SHOW TABLES").fetchall()
            tables: list[DuckdbTableInfo] = []
            for (table_name,) in table_rows:
                try:
                    count_row = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()
                    row_count = int(count_row[0]) if count_row else 0
                except Exception:
                    row_count = -1
                tables.append(DuckdbTableInfo(name=table_name, row_count=row_count))
        finally:
            conn.close()
    except Exception as exc:
        return DuckdbHealthInfo(
            db_path=db_path,
            file_size_bytes=file_size,
            last_modified=last_modified,
            tables=(),
            error=f"Could not query DuckDB: {exc}",
        )

    return DuckdbHealthInfo(
        db_path=db_path,
        file_size_bytes=file_size,
        last_modified=last_modified,
        tables=tuple(sorted(tables, key=lambda t: t.name)),
        error=None,
    )


def collect_cycle_summaries(
    statuses: tuple[DownloadStatusRecord, ...],
) -> tuple[CycleDownloadSummary, ...]:
    by_cycle: dict[int, list[DownloadStatusRecord]] = collections.defaultdict(list)
    for status in statuses:
        by_cycle[status.cycle].append(status)

    summaries: list[CycleDownloadSummary] = []
    for cycle in sorted(by_cycle.keys(), reverse=True):
        cycle_statuses = by_cycle[cycle]
        downloaded = [s for s in cycle_statuses if s.fetch_status in {"downloaded", "not_modified"}]
        failed = [s for s in cycle_statuses if s.fetch_status in {"error", "failed"}]

        completion_timestamps = [
            s.download_completed_at
            for s in downloaded
            if s.download_completed_at is not None
        ]
        last_successful_at = max(completion_timestamps) if completion_timestamps else None

        summaries.append(
            CycleDownloadSummary(
                cycle=cycle,
                downloaded_tables=len(downloaded),
                total_tables=len(cycle_statuses),
                failed_tables=len(failed),
                last_successful_at=last_successful_at,
            )
        )

    return tuple(summaries)


def _to_recent_run(record: object) -> RecentRun:
    return RecentRun(
        run_number=getattr(record, "run_number", None),
        command=str(getattr(record, "command", "")),
        operator_id=str(getattr(record, "operator_id", "")),
        lifecycle_state=str(getattr(record, "lifecycle_state", "")),
        completed_at=getattr(record, "completed_at", None),
        exit_code=getattr(record, "exit_code", None),
        log_path=getattr(record, "log_path", None),
    )


def collect_recent_runs(runner: _RunnerProtocol) -> tuple[tuple[RecentRun, ...], tuple[RecentRun, ...]]:
    """Return (recent_failed, recent_completed) run tuples."""
    records = runner.list_recent_runs(limit=50)
    failed: list[RecentRun] = []
    completed: list[RecentRun] = []
    for record in records:
        run = _to_recent_run(record)
        state = run.lifecycle_state
        if state in {"failed", "canceled"}:
            failed.append(run)
        elif state == "completed":
            completed.append(run)
    return tuple(failed[:10]), tuple(completed[:5])


def collect_log_tail(logs_dir: Path, n: int = LOG_TAIL_LINES) -> tuple[str | None, str | None]:
    """Return (tail_text, log_path) from the most recent log file under logs_dir."""
    if not logs_dir.exists():
        return None, None

    log_files = sorted(
        (p for p in logs_dir.rglob("*.log") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not log_files:
        return None, None

    latest = log_files[0]
    try:
        lines = latest.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = "\n".join(lines[-n:])
        return tail, str(latest)
    except OSError as exc:
        return f"(could not read log: {exc})", str(latest)


def collect_health_metrics(
    repo_root: Path,
    metadata_store: object | None,
    runner: _RunnerProtocol,
) -> HealthMetrics:
    db_path = repo_root / "db" / "fec.duckdb"
    duckdb_info = collect_duckdb_info(db_path)

    statuses: tuple[DownloadStatusRecord, ...] = ()
    if metadata_store is not None:
        try:
            statuses = metadata_store.list_download_statuses(limit=500)  # type: ignore[union-attr]
        except Exception:
            statuses = ()
    cycle_summaries = collect_cycle_summaries(statuses)

    recent_failed, recent_completed = collect_recent_runs(runner)

    log_tail, log_path = collect_log_tail(repo_root / "logs")

    return HealthMetrics(
        collected_at=_utc_now_iso(),
        duckdb=duckdb_info,
        cycle_summaries=cycle_summaries,
        recent_failed_runs=recent_failed,
        recent_completed_runs=recent_completed,
        log_tail=log_tail,
        log_path=log_path,
    )


# ---------------------------------------------------------------------------
# HTML rendering helpers
# ---------------------------------------------------------------------------


def _status_pill(text: str, ok: bool) -> str:
    color = "#d4edda" if ok else "#f8d7da"
    border = "#b8dacc" if ok else "#f5c6cb"
    return (
        f"<span style='display:inline-block;padding:0.15rem 0.5rem;border-radius:999px;"
        f"border:1px solid {border};background:{color};font-size:0.82rem;font-weight:600'>"
        f"{escape(text)}</span>"
    )


def render_health(metrics: HealthMetrics) -> str:
    # --- DuckDB panel ---
    if metrics.duckdb.error and metrics.duckdb.file_size_bytes is None:
        db_summary = f"<p class='muted'>{escape(metrics.duckdb.error)}</p>"
    else:
        size_str = _format_bytes(metrics.duckdb.file_size_bytes)
        modified_str = metrics.duckdb.last_modified or "unknown"
        error_note = f"<p class='muted'>Warning: {escape(metrics.duckdb.error)}</p>" if metrics.duckdb.error else ""
        db_summary = f"""
<dl class='detail-list'>
  <div class='detail-row'><dt>Path</dt><dd>{escape(str(metrics.duckdb.db_path))}</dd></div>
  <div class='detail-row'><dt>File size</dt><dd>{escape(size_str)}</dd></div>
  <div class='detail-row'><dt>Last modified</dt><dd>{escape(modified_str)}</dd></div>
</dl>
{error_note}"""

    if metrics.duckdb.tables:
        table_rows = "".join(
            f"<tr><td>{escape(t.name)}</td><td style='text-align:right'>"
            f"{escape(str(t.row_count) if t.row_count >= 0 else 'error')}</td></tr>"
            for t in metrics.duckdb.tables
        )
        tables_html = (
            "<div style='overflow-x:auto'>"
            "<table><thead><tr><th>Table</th><th>Row count</th></tr></thead>"
            f"<tbody>{table_rows}</tbody></table></div>"
        )
    elif not metrics.duckdb.error:
        tables_html = "<p class='muted'>No tables found in DuckDB.</p>"
    else:
        tables_html = ""

    # --- Cycle download summaries panel ---
    if metrics.cycle_summaries:
        cycle_rows = "".join(
            f"<tr>"
            f"<td>{escape(str(s.cycle))}</td>"
            f"<td>{escape(str(s.downloaded_tables))}/{escape(str(s.total_tables))}</td>"
            f"<td>{_status_pill('ok', s.failed_tables == 0) if s.failed_tables == 0 else _status_pill(f'{s.failed_tables} failed', False)}</td>"
            f"<td>{escape(s.last_successful_at or 'n/a')}</td>"
            f"</tr>"
            for s in metrics.cycle_summaries
        )
        cycles_html = (
            "<div style='overflow-x:auto'>"
            "<table><thead><tr>"
            "<th>Cycle</th><th>Downloaded / Total</th><th>Status</th><th>Last success</th>"
            "</tr></thead>"
            f"<tbody>{cycle_rows}</tbody></table></div>"
        )
    else:
        cycles_html = "<p class='muted'>No download status data available. Run a fetch workflow to populate.</p>"

    # --- Recent failed runs ---
    if metrics.recent_failed_runs:
        failed_rows = "".join(
            f"<tr>"
            f"<td>{escape(str(r.run_number) if r.run_number is not None else 'n/a')}</td>"
            f"<td>{escape(r.command)}</td>"
            f"<td>{escape(r.operator_id)}</td>"
            f"<td>{_status_pill(r.lifecycle_state, False)}</td>"
            f"<td>{escape(r.completed_at or 'n/a')}</td>"
            f"<td>{escape(str(r.exit_code) if r.exit_code is not None else 'n/a')}</td>"
            f"</tr>"
            for r in metrics.recent_failed_runs
        )
        failed_html = (
            "<div style='overflow-x:auto'>"
            "<table><thead><tr>"
            "<th>Run</th><th>Command</th><th>Operator</th><th>State</th><th>Completed</th><th>Exit</th>"
            "</tr></thead>"
            f"<tbody>{failed_rows}</tbody></table></div>"
        )
    else:
        failed_html = "<p class='muted'>No failed or canceled runs in recent history.</p>"

    # --- Recent completed runs ---
    if metrics.recent_completed_runs:
        completed_rows = "".join(
            f"<tr>"
            f"<td>{escape(str(r.run_number) if r.run_number is not None else 'n/a')}</td>"
            f"<td>{escape(r.command)}</td>"
            f"<td>{escape(r.operator_id)}</td>"
            f"<td>{escape(r.completed_at or 'n/a')}</td>"
            f"</tr>"
            for r in metrics.recent_completed_runs
        )
        completed_html = (
            "<div style='overflow-x:auto'>"
            "<table><thead><tr>"
            "<th>Run</th><th>Command</th><th>Operator</th><th>Completed</th>"
            "</tr></thead>"
            f"<tbody>{completed_rows}</tbody></table></div>"
        )
    else:
        completed_html = "<p class='muted'>No completed runs in recent history.</p>"

    # --- Log tail ---
    if metrics.log_tail is not None:
        log_path_note = f"<p class='muted'>Source: {escape(metrics.log_path or 'unknown')}</p>" if metrics.log_path else ""
        log_html = (
            f"{log_path_note}"
            "<div class='field'>"
            f"<textarea readonly style='font-family:monospace;font-size:0.82rem;min-height:12rem'>"
            f"{escape(metrics.log_tail)}</textarea></div>"
        )
    else:
        log_html = "<p class='muted'>No log files found under logs/.</p>"

    return f"""
<p class='muted'>Read-only pipeline status snapshot. Collected at {escape(metrics.collected_at)}.</p>
<div class='stack'>
  <div class='dashboard-grid'>
    <section class='subpanel'>
      <h3>DuckDB Database</h3>
      {db_summary}
    </section>
    <section class='subpanel'>
      <h3>Table Row Counts</h3>
      {tables_html}
    </section>
  </div>
  <section class='subpanel'>
    <h3>Download Status by Cycle</h3>
    <p class='muted'>Last successful download and progress per FEC election cycle.</p>
    {cycles_html}
  </section>
  <div class='dashboard-grid'>
    <section class='subpanel'>
      <h3>Recent Failed / Canceled Runs</h3>
      {failed_html}
    </section>
    <section class='subpanel'>
      <h3>Recent Completed Runs</h3>
      {completed_html}
    </section>
  </div>
  <section class='subpanel'>
    <h3>Log Tail (last {LOG_TAIL_LINES} lines)</h3>
    {log_html}
  </section>
</div>
"""
