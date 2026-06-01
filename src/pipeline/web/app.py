"""Operations web app shell for local-trusted workflows."""

from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field
import yaml

from pipeline.data_scope import CANONICAL_DATA_SCOPE_PATH, load_data_scope_config, parse_year_range
from pipeline.etl_config import repo_root
from pipeline.metadata_store import DownloadMetadataStore, DownloadStatusRecord, build_sqlite_metadata_store
from pipeline.web.command_runner import CommandAuditStore, CommandRequest, CommandRunner, CommandRunRecord
from pipeline.web.health import collect_health_metrics, render_health
from pipeline.web.upstream_changes import load_upstream_changes_report
from pipeline.web.upstream_render import render_upstream_changes


SCREEN_ROUTES: tuple[tuple[str, str], ...] = (
    # ("/dashboard", "Dashboard"),
    # ("/runs", "Runs"),
    # ("/data-scope-config", "Data Scope Config"),
    ("/history", "History"),
    ("/health", "Health"),
    # ("/upstream-changes", "Upstream Changes"),
)

def render_shell(active_path: str, body_html: str | None = None, extra_head_html: str = "") -> str:
    """Render a minimal server-side HTML shell with nav placeholders."""

    nav_items: list[str] = []
    active_label = ""
    for path, label in SCREEN_ROUTES:
        is_active = "true" if path == active_path else "false"
        class_name = "active" if path == active_path else ""
        if path == active_path:
            active_label = label
        nav_items.append(
            "<a class='nav-link "
            f"{class_name}' data-active='{is_active}' href='{path}'>{escape(label)}</a>"
        )

    escaped_label = escape(active_label or "Dashboard")
    panel_body = body_html or "<p>Placeholder screen. Operational data wiring is planned in follow-up slices.</p>"
    return f"""<!doctype html>
<html lang='en'>
  <head>
    <meta charset='utf-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>MoneyTrail Operations</title>
    {extra_head_html}
    <style>
      :root {{
        --bg: #f6f7ef;
        --panel: #fffef8;
        --ink: #1f2d2a;
        --accent: #0d5c63;
        --line: #d8ded4;
      }}
      body {{
        margin: 0;
        font-family: "Segoe UI", "Trebuchet MS", sans-serif;
        color: var(--ink);
        background: radial-gradient(circle at 15% 15%, #e8f0e6, var(--bg) 45%);
      }}
      .layout {{
        max-width: 980px;
        margin: 0 auto;
        padding: 1.25rem;
      }}
      .header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
      }}
      .title {{
        margin: 0;
        font-size: 1.4rem;
      }}
      .badge {{
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 0.3rem 0.7rem;
        font-size: 0.82rem;
        background: var(--panel);
      }}
      .nav {{
        margin-top: 1rem;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.5rem;
      }}
      .nav-link {{
        text-decoration: none;
        padding: 0.6rem 0.75rem;
        border: 1px solid var(--line);
        border-radius: 0.55rem;
        background: var(--panel);
        color: var(--ink);
        text-align: center;
        font-size: 0.9rem;
      }}
      .nav-link.active {{
        border-color: var(--accent);
        background: #d8ecee;
        font-weight: 600;
      }}
      .panel {{
        margin-top: 1rem;
        border: 1px solid var(--line);
        border-radius: 0.75rem;
        background: var(--panel);
        padding: 1rem;
      }}
      .panel h2 {{
        margin: 0 0 0.5rem 0;
      }}
      .dashboard-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
      }}
      .subpanel {{
        border: 1px solid var(--line);
        border-radius: 0.65rem;
        padding: 0.9rem;
        background: #fcfcf6;
      }}
      .subpanel h3 {{
        margin: 0 0 0.75rem 0;
        font-size: 1rem;
      }}
      .detail-list {{
        margin: 0;
        padding: 0;
      }}
      .detail-row {{
        display: grid;
        grid-template-columns: 9rem 1fr;
        gap: 0.75rem;
        padding: 0.2rem 0;
      }}
      .detail-row dt {{
        font-weight: 600;
      }}
      .detail-row dd {{
        margin: 0;
        overflow-wrap: anywhere;
      }}
      .muted {{
        color: #53615d;
      }}
      .status-pill {{
        display: inline-block;
        padding: 0.18rem 0.5rem;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: #eef4e7;
        font-size: 0.82rem;
        font-weight: 600;
      }}
      .stack {{
        display: grid;
        gap: 1rem;
      }}
      .form-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
      }}
      .field {{
        display: grid;
        gap: 0.35rem;
      }}
      .field label {{
        font-weight: 600;
      }}
      .field input,
      .field select,
      .field textarea {{
        border: 1px solid var(--line);
        border-radius: 0.45rem;
        padding: 0.55rem 0.65rem;
        font: inherit;
        background: white;
      }}
      .field textarea {{
        min-height: 14rem;
        resize: vertical;
      }}
      .checkbox-grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.5rem;
      }}
      .checkbox-item,
      .toggle-row {{
        display: flex;
        align-items: center;
        gap: 0.45rem;
      }}
      .actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        align-items: center;
      }}
      .button {{
        border: 1px solid var(--accent);
        border-radius: 0.5rem;
        background: var(--accent);
        color: white;
        padding: 0.6rem 0.9rem;
        font: inherit;
        cursor: pointer;
      }}
      .button.secondary {{
        background: white;
        color: var(--accent);
      }}
      .message {{
        border: 1px solid var(--line);
        border-radius: 0.65rem;
        padding: 0.75rem 0.9rem;
        background: #f7faf2;
      }}
      .message.error {{
        border-color: #b76868;
        background: #fff5f3;
      }}
      .metric-grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.75rem;
      }}
      .metric-card {{
        border: 1px solid var(--line);
        border-radius: 0.65rem;
        padding: 0.85rem 0.9rem;
        background: #fcfcf6;
      }}
      .metric-card strong {{
        display: block;
        font-size: 1.35rem;
        margin-top: 0.2rem;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
      }}
      th,
      td {{
        padding: 0.55rem 0.6rem;
        border-bottom: 1px solid var(--line);
        text-align: left;
        vertical-align: top;
      }}
      th {{
        font-size: 0.85rem;
      }}
      @media (max-width: 760px) {{
        .nav {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        .dashboard-grid {{
          grid-template-columns: 1fr;
        }}
        .metric-grid,
        .form-grid,
        .checkbox-grid {{
          grid-template-columns: 1fr;
        }}
        .detail-row {{
          grid-template-columns: 1fr;
          gap: 0.25rem;
        }}
      }}
    </style>
  </head>
  <body>
    <main class='layout'>
      <header class='header'>
        <h1 class='title'>MoneyTrail Operations Web App</h1>
        <span class='badge'>Local-Trusted Mode</span>
      </header>
      <nav class='nav'>{''.join(nav_items)}</nav>
      <section class='panel'>
        <h2>{escaped_label}</h2>
        {panel_body}
      </section>
    </main>
  </body>
</html>
"""


def _render_detail_rows(rows: list[tuple[str, str] | tuple[str, str, bool]]) -> str:
    items: list[str] = []
    for row in rows:
        if len(row) == 3:
            label, value, allow_html = row
        else:
            label, value = row
            allow_html = False
        rendered_value = value if allow_html else escape(value)
        items.append(f"<div class='detail-row'><dt>{escape(label)}</dt><dd>{rendered_value}</dd></div>")
    return f"<dl class='detail-list'>{''.join(items)}</dl>"


def _render_table(headers: list[str], rows: list[list[str]]) -> str:
    head_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return (
        "<div style='overflow-x:auto'>"
        f"<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"
        "</div>"
    )


def _render_log_cell(run_number: int | None, log_path: str | None, *, internal_link: bool = False) -> str:
    if not log_path:
        return "n/a"
    if internal_link and run_number is not None:
        href = f"/history/logs/{run_number}"
        return f"<a href='{escape(href)}'>View log</a>"
    try:
        href = Path(log_path).as_uri()
        return f"<a href='{escape(href)}'>{escape(log_path)}</a>"
    except ValueError:
        return escape(log_path)


def _resolve_history_log_path(repo_root_path: Path, record: CommandRunRecord) -> Path:
    if not record.log_path:
        raise HTTPException(status_code=404, detail="log not found")

    candidate = Path(record.log_path)
    if not candidate.is_absolute():
        candidate = repo_root_path / candidate

    resolved = candidate.resolve()
    logs_root = (repo_root_path / "logs").resolve()
    if not resolved.is_relative_to(logs_root):
        raise HTTPException(status_code=404, detail="log not found")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="log not found")
    return resolved


def _history_report_directory(repo_root_path: Path, run_number: int | None) -> Path | None:
    if run_number is None:
        return None
    return repo_root_path / "artifacts" / "reports" / "ops-web" / f"run-{run_number}"


def _list_history_report_artifacts(repo_root_path: Path, run_number: int | None) -> list[Path]:
    report_directory = _history_report_directory(repo_root_path, run_number)
    if report_directory is None or not report_directory.exists() or not report_directory.is_dir():
        return []
    return sorted(
        (
            artifact_path
            for artifact_path in report_directory.iterdir()
            if artifact_path.is_file() and artifact_path.suffix.lower() == ".html"
        ),
        key=lambda artifact_path: artifact_path.name.lower(),
    )


def _render_history_report_cell(repo_root_path: Path, run_number: int | None) -> str:
    artifacts = _list_history_report_artifacts(repo_root_path, run_number)
    if not artifacts or run_number is None:
        return "n/a"
    return "<br>".join(
        f"<a href='/history/reports/{run_number}/{quote(artifact_path.name, safe='')}'>{escape(artifact_path.name)}</a>"
        for artifact_path in artifacts
    )


def _resolve_history_report_path(repo_root_path: Path, run_number: int, artifact_name: str) -> Path:
    report_directory = _history_report_directory(repo_root_path, run_number)
    if report_directory is None:
        raise HTTPException(status_code=404, detail="report artifact not found")
    report_root = report_directory.resolve()
    candidate = (report_directory / artifact_name).resolve()
    if not candidate.is_relative_to(report_root):
        raise HTTPException(status_code=404, detail="report artifact not found")
    if not candidate.exists() or not candidate.is_file() or candidate.suffix.lower() != ".html":
        raise HTTPException(status_code=404, detail="report artifact not found")
    return candidate


def _format_record(repo_root_path: Path, record: CommandRunRecord, *, internal_log_link: bool = False) -> str:
    return _render_detail_rows(
        [
            ("Status", record.lifecycle_state),
            ("Command", record.command),
            ("Operator", record.operator_id),
            ("Run", str(record.run_number) if record.run_number is not None else "pending"),
            ("Requested", record.requested_at),
            ("Launched", record.launched_at or "not launched"),
            ("Completed", record.completed_at or "in progress"),
            ("Admission", record.admission_status),
            ("Launch", record.launch_status),
            ("PID", str(record.pid) if record.pid is not None else "n/a"),
            ("Exit code", str(record.exit_code) if record.exit_code is not None else "n/a"),
            ("Log path", _render_log_cell(record.run_number, record.log_path, internal_link=internal_log_link), True),
            ("Reports", _render_history_report_cell(repo_root_path, record.run_number), True),
            ("Command line", record.command_line or "n/a"),
            ("Rejection", record.rejection_reason or "n/a"),
            ("Launch error", record.launch_error or "n/a"),
        ]
    )


def _format_progress_cell(status: DownloadStatusRecord) -> str:
    if status.progress_pct is not None:
        return f"{status.progress_pct:.1f}%"
    if status.bytes_downloaded is not None and status.content_length is not None and status.content_length > 0:
        return f"{(status.bytes_downloaded / status.content_length) * 100:.1f}%"
    if status.fetch_status in {"downloaded", "not_modified"}:
        return "100.0%"
    return "n/a"


def _format_bytes_cell(value: int | None) -> str:
    if value is None:
        return "n/a"
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MB"
    if value >= 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value} bytes"


def _render_download_status_table(statuses: tuple[DownloadStatusRecord, ...]) -> str:
    if not statuses:
        return "<p class='muted'>No cycle/table download status is available yet.</p>"

    rows = []
    for status in statuses:
        rows.append(
            "<tr>"
            f"<td>{escape(str(status.cycle))}</td>"
            f"<td>{escape(status.table_name)}</td>"
            f"<td>{escape(status.fetch_status)}</td>"
            f"<td>{escape(_format_progress_cell(status))}</td>"
            f"<td>{escape(_format_bytes_cell(status.bytes_downloaded))}</td>"
            f"<td>{escape(_format_bytes_cell(status.content_length))}</td>"
            f"<td>{escape(status.updated_at)}</td>"
            f"<td>{escape(status.error_text or 'n/a')}</td>"
            "</tr>"
        )
    return (
        "<div style='overflow-x:auto'>"
        "<table><thead><tr>"
        "<th>Cycle</th><th>Table</th><th>Status</th><th>Progress</th>"
        "<th>Downloaded</th><th>Total</th><th>Updated</th><th>Error</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def _load_download_status_view(
    repo_root_path: Path,
    metadata_store: DownloadMetadataStore | None,
) -> tuple[list[tuple[str, str]], str]:
    if metadata_store is None:
        return [
            ("Status", "unavailable"),
            ("Source DB", "metadata_database.sqlite is not configured"),
        ], "<p class='muted'>Configure metadata_database.sqlite.path in config\\data_scope.yml to expose cycle/table download progress.</p>"

    try:
        statuses = metadata_store.list_download_statuses(limit=100)
    except Exception as exc:
        return [
            ("Status", "unavailable"),
            ("Source DB", metadata_store.source_label),
            ("Message", str(exc)),
        ], "<p class='muted'>The dashboard could not read download status from the metadata store.</p>"

    downloading_count = sum(1 for status in statuses if status.fetch_status == "downloading")
    summary_rows = [
        ("Status", "ready"),
        ("Source DB", metadata_store.source_label),
        ("Tracked cycle/table pairs", str(len(statuses))),
        ("Active downloads", str(downloading_count)),
        ("Config path", str(repo_root_path / CANONICAL_DATA_SCOPE_PATH)),
    ]
    return summary_rows, _render_download_status_table(statuses)


def _render_unavailable_upstream_changes(message: str) -> str:
    class _UnavailableMetadataStore:
        source_label = "metadata_database.sqlite is not configured"

        @staticmethod
        def load_successful_fetch_history() -> tuple[object, ...]:
            raise RuntimeError(message)

    return render_upstream_changes(load_upstream_changes_report(_UnavailableMetadataStore()))


class _ErrorMetadataStore:
    def __init__(self, source_label: str, message: str) -> None:
        self.source_label = source_label
        self._message = message

    def list_download_statuses(self, limit: int = 100) -> tuple[DownloadStatusRecord, ...]:
        raise RuntimeError(self._message)

    def load_successful_fetch_history(self) -> tuple[object, ...]:
        raise RuntimeError(self._message)


def _render_dashboard(
    repo_root_path: Path,
    active_run: CommandRunRecord | None,
    metadata_store: DownloadMetadataStore | None,
) -> tuple[str, bool]:
    config_path = repo_root_path / CANONICAL_DATA_SCOPE_PATH

    try:
        config = load_data_scope_config(config_path)
        scope_rows = [
            ("Status", "configured"),
            ("Coverage", str(config["coverage"])),
            ("Facts", str(config["facts"])),
            ("Dimension tables", ", ".join(config["table_groups"]["dimensions"]) or "(none)"),
            ("Fact tables", ", ".join(config["table_groups"]["facts"]) or "(none)"),
            ("Config path", str(config_path)),
        ]
        sqlite_config = config.get("metadata_database", {}).get("sqlite", {})
        if isinstance(sqlite_config, dict) and sqlite_config.get("path"):
            scope_rows.append(
                (
                    "Metadata DB",
                    str(sqlite_config["path"]),
                )
            )
        scope_html = _render_detail_rows(
            scope_rows
        )
    except SystemExit as exc:
        scope_html = _render_detail_rows(
            [
                ("Status", "unavailable"),
                ("Config path", str(config_path)),
                ("Message", str(exc)),
            ]
        )

    download_summary_rows, download_status_html = _load_download_status_view(repo_root_path, metadata_store)

    if active_run is None:
        run_html = (
            "<p class='muted'>No active Workflow Run. Run history remains available through the API-backed audit log.</p>"
        )
    else:
        run_html = _render_detail_rows(
            [
                ("Status", active_run.lifecycle_state),
                ("Command", active_run.command),
                ("Operator", active_run.operator_id),
                ("Run", str(active_run.run_number) if active_run.run_number is not None else "pending"),
                ("Requested", active_run.requested_at),
                ("Launched", active_run.launched_at or "not launched"),
                ("PID", str(active_run.pid) if active_run.pid is not None else "n/a"),
                ("Launch", active_run.launch_status),
                ("Log path", _render_log_cell(active_run.run_number, active_run.log_path, internal_link=True), True),
                ("Reports", _render_history_report_cell(repo_root_path, active_run.run_number), True),
            ]
        )

    dashboard_should_refresh = active_run is not None
    if metadata_store is not None:
        try:
            dashboard_should_refresh = dashboard_should_refresh or any(
                status.fetch_status == "downloading" for status in metadata_store.list_download_statuses(limit=100)
            )
        except Exception:
            pass

    body_html = f"""
<div class='dashboard-grid'>
  <section class='subpanel'>
    <h3>Data Scope</h3>
    <p class='muted'>Current Data Scope Config from the canonical config path used for future Workflow Runs.</p>
    {scope_html}
  </section>
  <section class='subpanel'>
    <h3>Workflow Run</h3>
    <p class='muted'>Current active Workflow Run state from the command audit store.</p>
    {run_html}
  </section>
</div>
<section class='subpanel' style='margin-top: 1rem;'>
  <h3>Download Progress</h3>
  <p class='muted'>Each cycle/table pair reflects the latest MySQL-backed download status, including active progress while ZIP files stream.</p>
  {_render_detail_rows(download_summary_rows)}
  {download_status_html}
</section>
"""
    return body_html, dashboard_should_refresh


def _load_scope_view_state(config_path: Path) -> tuple[list[tuple[str, str]], str | None, str]:
    try:
        config = load_data_scope_config(config_path)
    except SystemExit as exc:
        preview = "Resolved YAML preview unavailable until the Data Scope config validates."
        return [
            ("Status", "unavailable"),
            ("Config path", str(config_path)),
        ], str(exc), preview

    preview = yaml.safe_dump(config, sort_keys=False)
    summary_rows = [
        ("Status", "configured"),
        ("Config path", str(config_path)),
        ("Coverage", str(config["coverage"])),
        ("Facts", str(config["facts"])),
        ("Dimension tables", ", ".join(config["table_groups"]["dimensions"]) or "(none)"),
        ("Fact tables", ", ".join(config["table_groups"]["facts"]) or "(none)"),
    ]
    sqlite_config = config.get("metadata_database", {}).get("sqlite", {})
    if isinstance(sqlite_config, dict) and sqlite_config.get("path"):
        summary_rows.append(
            (
                "Metadata DB",
                str(sqlite_config["path"]),
            )
        )
    return summary_rows, None, preview


def _render_scope_editor(
    summary_rows: list[tuple[str, str]],
    preview_yaml: str,
    error_message: str | None = None,
) -> str:
    message_html = ""
    if error_message:
        message_html += f"<section class='message error'><strong>Data Scope error.</strong> {escape(error_message)}</section>"

    body_html = f"""
<div class='stack'>
  {message_html}
  <section class='subpanel'>
    <h3>Canonical Data Scope Config</h3>
    <p class='muted'>The canonical YAML is already readable as-is. In-app editing is deferred to developer workflows for now.</p>
    {_render_detail_rows(summary_rows)}
  </section>
  <section class='subpanel'>
    <h3>Resolved YAML Preview</h3>
    <p class='muted'>Shows the canonical YAML that current and future Workflow Runs read from disk.</p>
    <div class='field'>
      <textarea readonly>{escape(preview_yaml)}</textarea>
    </div>
  </section>
</div>
"""
    return render_shell("/data-scope-config", body_html=body_html)


def _render_history(repo_root_path: Path, records: list[CommandRunRecord]) -> str:
    if not records:
        body_html = """
<div class='stack'>
  <section class='subpanel'>
    <h3>Run History</h3>
    <p class='muted'>No persisted Workflow Runs yet. Rejected, failed, canceled, and completed runs will appear here once the audit log has entries.</p>
  </section>
</div>
"""
        return render_shell("/history", body_html=body_html)

    lifecycle_counts: dict[str, int] = {}
    for record in records:
        lifecycle_counts[record.lifecycle_state] = lifecycle_counts.get(record.lifecycle_state, 0) + 1
    summary_rows = [(state, str(count)) for state, count in sorted(lifecycle_counts.items())]
    table_rows = [
        [
            escape(record.requested_at),
            escape(record.command),
            escape(record.operator_id),
            escape(record.lifecycle_state),
            escape(record.admission_status),
            escape(record.launched_at or "n/a"),
            escape(record.completed_at or "n/a"),
            escape(str(record.exit_code) if record.exit_code is not None else "n/a"),
            _render_log_cell(record.run_number, record.log_path, internal_link=True),
            _render_history_report_cell(repo_root_path, record.run_number),
            escape(str(record.run_number) if record.run_number is not None else "n/a"),
        ]
        for record in records
    ]

    body_html = f"""
<div class='stack'>
  <section class='subpanel'>
    <h3>Run History</h3>
    <p class='muted'>Recent Workflow Runs from the persisted audit log, including rejected attempts and terminal outcomes.</p>
    {_render_detail_rows(summary_rows)}
  </section>
  <section class='subpanel'>
    <h3>Recent audit records</h3>
    {_render_table(
        ["Requested", "Command", "Operator", "Lifecycle", "Admission", "Launched", "Completed", "Exit", "Log", "Reports", "Run"],
        table_rows,
    )}
  </section>
</div>
"""
    return render_shell("/history", body_html=body_html)


def _load_runs_scope_state(config_path: Path) -> tuple[dict[str, object] | None, list[tuple[str, str]], str | None, str]:
    try:
        config = load_data_scope_config(config_path)
    except SystemExit as exc:
        preview = "Resolved YAML preview unavailable until the Data Scope config validates."
        return None, [("Config path", str(config_path)), ("Status", "unavailable")], str(exc), preview

    _, facts_end_year = parse_year_range(config["facts"], "facts")
    tables: list[str] = []
    seen: set[str] = set()
    for group_name in ("dimensions", "facts"):
        for table in config["table_groups"][group_name]:
            if table in seen:
                continue
            seen.add(table)
            tables.append(table)

    return (
        {
            "cycle": facts_end_year,
            "tables": tuple(tables),
        },
        [
            ("Config path", str(config_path)),
            ("Coverage", str(config["coverage"])),
            ("Facts", str(config["facts"])),
            ("Derived cycle", str(facts_end_year)),
            ("Run tables", ", ".join(tables) or "(none)"),
        ],
        None,
        yaml.safe_dump(config, sort_keys=False),
    )


def _render_runs(
    repo_root_path: Path,
    active_run: CommandRunRecord | None,
    recent_runs: list[CommandRunRecord],
    scope_summary_rows: list[tuple[str, str]],
    scope_preview_yaml: str,
    message: str | None = None,
    error_message: str | None = None,
    form_values: dict[str, str] | None = None,
) -> str:
    values = {
        "operator_id": "",
        "command": "fetch",
        **(form_values or {}),
    }

    message_html = ""
    if message:
        message_html += f"<section class='message'><strong>Workflow Run update.</strong> {escape(message)}</section>"
    if error_message:
        message_html += f"<section class='message error'><strong>Workflow Run error.</strong> {escape(error_message)}</section>"

    active_html = (
        "<p class='muted'>No active Workflow Run. You can submit a new allowlisted command below.</p>"
        if active_run is None
        else _format_record(repo_root_path, active_run, internal_log_link=True)
    )
    cancel_form = ""
    if active_run is not None:
        active_run_number = str(active_run.run_number) if active_run.run_number is not None else "pending"
        cancel_form = (
            f"<form method='post' action='/runs/{active_run_number}/cancel'>"
            "<button class='button secondary' type='submit'>Cancel active run</button>"
            "</form>"
        )

    if recent_runs:
        recent_run_rows = [
            [
                escape(str(record.run_number) if record.run_number is not None else "n/a"),
                escape(record.requested_at),
                escape(record.command),
                escape(record.operator_id),
                escape(record.lifecycle_state),
                escape(record.admission_status),
                escape(str(record.exit_code) if record.exit_code is not None else "n/a"),
                _render_log_cell(record.run_number, record.log_path, internal_link=True),
            ]
            for record in recent_runs
        ]
        recent_runs_html = _render_table(
            ["Run", "Requested", "Command", "Operator", "Lifecycle", "Admission", "Exit", "Log"],
            recent_run_rows,
        )
    else:
        recent_runs_html = (
            "<p class='muted'>No persisted Workflow Runs yet. This log refreshes automatically every 10 seconds once runs exist.</p>"
        )

    body_html = f"""
<div class='stack'>
  {message_html}
  <section class='subpanel'>
    <h3>Submit Workflow Run</h3>
    <p class='muted'>Launch an allowlisted fetch, load, or benchmark workflow run. Cycle and table scope come from the canonical Data Scope YAML.</p>
    <form method='post' action='/runs/submit'>
      <div class='form-grid'>
        <div class='field'>
          <label for='operator_id'>Operator ID</label>
          <input id='operator_id' name='operator_id' type='text' value='{escape(values["operator_id"])}' required>
        </div>
        <div class='field'>
          <label for='command'>Command</label>
          <select id='command' name='command'>
            <option value='fetch' {'selected' if values['command'] == 'fetch' else ''}>fetch</option>
            <option value='load' {'selected' if values['command'] == 'load' else ''}>load</option>
            <option value='benchmark-load' {'selected' if values['command'] == 'benchmark-load' else ''}>benchmark-load</option>
          </select>
        </div>
      </div>
      <div class='actions'>
        <label class='toggle-row'><input name='armed' type='checkbox' {'checked' if values.get('armed') == 'on' else ''}> <span>App is armed</span></label>
        <label class='toggle-row'><input name='confirmed' type='checkbox' {'checked' if values.get('confirmed') == 'on' else ''}> <span>I confirm this Workflow Run</span></label>
      </div>
      <div class='actions'>
        <button class='button' type='submit'>Submit run</button>
      </div>
    </form>
  </section>
  <div class='dashboard-grid'>
    <section class='subpanel'>
      <h3>Run Request Source</h3>
      <p class='muted'>Each Workflow Run uses the canonical Data Scope YAML. The request derives cycle and table scope directly from that file.</p>
      {_render_detail_rows(scope_summary_rows)}
    </section>
    <section class='subpanel'>
      <h3>Resolved YAML Preview</h3>
      <div class='field'>
        <textarea readonly>{escape(scope_preview_yaml)}</textarea>
      </div>
    </section>
  </div>
  <div class='dashboard-grid'>
    <section class='subpanel'>
      <h3>Active Workflow Run</h3>
      <p class='muted'>The Run Lock permits one active Workflow Run at a time.</p>
      {active_html}
      <div class='actions'>{cancel_form}</div>
    </section>
    <section class='subpanel'>
      <h3>Recent Run Log</h3>
      <p class='muted'>Recent audit records are shown here and the page refreshes every 10 seconds while you watch a run progress.</p>
      {recent_runs_html}
    </section>
  </div>
</div>
"""
    return render_shell("/runs", body_html=body_html, extra_head_html="<meta http-equiv='refresh' content='10'>")


def create_app(
    repo_root_path: Path | None = None,
    runner: CommandRunner | None = None,
    metadata_store: DownloadMetadataStore | None = None,
) -> FastAPI:
    """Create the operations web app instance."""

    app = FastAPI(title="MoneyTrail Operations", version="0.1.0")
    resolved_repo_root = repo_root_path or repo_root()
    app_runner = runner
    if app_runner is None:
        store = CommandAuditStore(resolved_repo_root / Path("db") / "ops_web.sqlite")
        app_runner = CommandRunner(repo_root=resolved_repo_root, store=store)

    def resolve_metadata_store() -> DownloadMetadataStore | None:
        if metadata_store is not None:
            return metadata_store
        try:
            return build_sqlite_metadata_store(resolved_repo_root)
        except SystemExit:
            return None
        except Exception as exc:
            return _ErrorMetadataStore("configured metadata store", str(exc))

    class RunSubmitPayload(BaseModel):
        command: str = Field(description="Allowlisted command: fetch, load, benchmark-load")
        operator_id: str = Field(description="Manual operator identifier")
        armed: bool = Field(description="Requires explicit armed mode before command admission")
        confirmed: bool = Field(description="Requires explicit confirmation before command admission")
        cycle: int = Field(description="Even election cycle year")
        tables: list[str] = Field(default_factory=list)
        force: bool = False
        dbt_threads: int | None = None

    class RunSubmitResponse(BaseModel):
        run_number: int
        admission_status: str
        rejection_reason: str | None
        launch_status: str
        launch_error: str | None
        lifecycle_state: str
        completed_at: str | None
        exit_code: int | None
        pid: int | None
        command_line: str | None
        log_path: str | None

    class ActiveRunResponse(BaseModel):
        active: bool
        run_number: int | None = None
        lifecycle_state: str | None = None

    class RunStatusResponse(BaseModel):
        run_number: int
        admission_status: str
        launch_status: str
        lifecycle_state: str
        rejection_reason: str | None
        launch_error: str | None
        completed_at: str | None
        exit_code: int | None
        pid: int | None
        log_path: str | None

    def build_command_request(
        command: str,
        operator_id: str,
        armed: bool,
        confirmed: bool,
        cycle: int,
        tables: list[str],
        force: bool,
        dbt_threads: int | None,
    ) -> CommandRequest:
        return CommandRequest(
            command=command,
            operator_id=operator_id,
            armed=armed,
            confirmed=confirmed,
            cycle=cycle,
            tables=tuple(table.strip().lower() for table in tables if table.strip()),
            force=force,
            dbt_threads=dbt_threads,
        )

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard", status_code=307)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/runs/submit", response_model=RunSubmitResponse)
    def submit_run(payload: RunSubmitPayload) -> RunSubmitResponse:
        record = app_runner.admit_and_launch(
            build_command_request(
                command=payload.command,
                operator_id=payload.operator_id,
                armed=payload.armed,
                confirmed=payload.confirmed,
                cycle=payload.cycle,
                tables=payload.tables,
                force=payload.force,
                dbt_threads=payload.dbt_threads,
            )
        )
        return RunSubmitResponse(
            run_number=record.run_number or 0,
            admission_status=record.admission_status,
            rejection_reason=record.rejection_reason,
            launch_status=record.launch_status,
            launch_error=record.launch_error,
            lifecycle_state=record.lifecycle_state,
            completed_at=record.completed_at,
            exit_code=record.exit_code,
            pid=record.pid,
            command_line=record.command_line,
            log_path=record.log_path,
        )

    @app.get("/api/runs/active", response_model=ActiveRunResponse)
    def active_run() -> ActiveRunResponse:
        record = app_runner.get_active_run()
        if record is None:
            return ActiveRunResponse(active=False)
        return ActiveRunResponse(
            active=True,
            run_number=record.run_number,
            lifecycle_state=record.lifecycle_state,
        )

    @app.get("/api/runs/{run_number}", response_model=RunStatusResponse)
    def run_status(run_number: int) -> RunStatusResponse:
        record = app_runner.get_run(run_number)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        return RunStatusResponse(
            run_number=record.run_number or 0,
            admission_status=record.admission_status,
            launch_status=record.launch_status,
            lifecycle_state=record.lifecycle_state,
            rejection_reason=record.rejection_reason,
            launch_error=record.launch_error,
            completed_at=record.completed_at,
            exit_code=record.exit_code,
            pid=record.pid,
            log_path=record.log_path,
        )

    @app.post("/api/runs/{run_number}/cancel", response_model=RunStatusResponse)
    def cancel_run(run_number: int) -> RunStatusResponse:
        try:
            record = app_runner.cancel_run(run_number)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return RunStatusResponse(
            run_number=record.run_number or 0,
            admission_status=record.admission_status,
            launch_status=record.launch_status,
            lifecycle_state=record.lifecycle_state,
            rejection_reason=record.rejection_reason,
            launch_error=record.launch_error,
            completed_at=record.completed_at,
            exit_code=record.exit_code,
            pid=record.pid,
            log_path=record.log_path,
        )

    @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    def dashboard() -> HTMLResponse:
        dashboard_html, should_refresh = _render_dashboard(
            resolved_repo_root,
            app_runner.get_active_run(),
            resolve_metadata_store(),
        )
        extra_head_html = "<meta http-equiv='refresh' content='10'>" if should_refresh else ""
        return HTMLResponse(content=render_shell("/dashboard", body_html=dashboard_html, extra_head_html=extra_head_html))

    @app.get("/data-scope-config", response_class=HTMLResponse, include_in_schema=False)
    def data_scope_config() -> HTMLResponse:
        config_path = resolved_repo_root / CANONICAL_DATA_SCOPE_PATH
        summary_rows, load_error, preview_yaml = _load_scope_view_state(config_path)
        return HTMLResponse(
            content=_render_scope_editor(
                summary_rows=summary_rows,
                preview_yaml=preview_yaml,
                error_message=load_error,
            )
        )

    @app.get("/history", response_class=HTMLResponse, include_in_schema=False)
    def history() -> HTMLResponse:
        return HTMLResponse(content=_render_history(resolved_repo_root, app_runner.list_recent_runs(limit=25)))

    @app.get("/history/logs/{run_number}", response_class=PlainTextResponse, include_in_schema=False)
    def history_log(run_number: int) -> PlainTextResponse:
        record = app_runner.get_run(run_number)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        log_path = _resolve_history_log_path(resolved_repo_root, record)
        return PlainTextResponse(log_path.read_text(encoding="utf-8"))

    @app.get("/history/reports/{run_number}/{artifact_name}", response_class=HTMLResponse, include_in_schema=False)
    def history_report(run_number: int, artifact_name: str) -> HTMLResponse:
        record = app_runner.get_run(run_number)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        report_path = _resolve_history_report_path(resolved_repo_root, run_number, artifact_name)
        return HTMLResponse(report_path.read_text(encoding="utf-8"))

    @app.get("/upstream-changes", response_class=HTMLResponse, include_in_schema=False)
    def upstream_changes() -> HTMLResponse:
        store = resolve_metadata_store()
        if store is None:
            return HTMLResponse(
                content=render_shell(
                    "/upstream-changes",
                    body_html=_render_unavailable_upstream_changes("metadata_database.sqlite config is unavailable"),
                )
            )
        report = load_upstream_changes_report(store)
        return HTMLResponse(content=render_shell("/upstream-changes", body_html=render_upstream_changes(report)))

    @app.get("/health", response_class=HTMLResponse, include_in_schema=False)
    def health() -> HTMLResponse:
        metrics = collect_health_metrics(resolved_repo_root, resolve_metadata_store(), app_runner)
        body_html = render_health(metrics)
        return HTMLResponse(content=render_shell("/health", body_html=body_html))

    @app.get("/runs", response_class=HTMLResponse, include_in_schema=False)
    def runs(run_number: int | None = None, message: str | None = None, error: str | None = None) -> HTMLResponse:
        _, scope_summary_rows, scope_error, scope_preview_yaml = _load_runs_scope_state(
            resolved_repo_root / CANONICAL_DATA_SCOPE_PATH
        )
        recent_runs = app_runner.list_recent_runs(limit=10)
        if run_number is not None:
            selected_record = app_runner.get_run(run_number)
            if selected_record is not None:
                recent_runs = [selected_record] + [record for record in recent_runs if record.run_number != run_number]
        return HTMLResponse(
            content=_render_runs(
                repo_root_path=resolved_repo_root,
                active_run=app_runner.get_active_run(),
                recent_runs=recent_runs,
                scope_summary_rows=scope_summary_rows,
                scope_preview_yaml=scope_preview_yaml,
                message=message,
                error_message=error or scope_error,
            )
        )

    @app.post("/runs/submit", include_in_schema=False)
    async def submit_run_page(request: Request) -> RedirectResponse:
        form_data = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
        form_values = {
            "operator_id": form_data.get("operator_id", [""])[0],
            "command": form_data.get("command", ["fetch"])[0],
            "armed": "on" if "armed" in form_data else "",
            "confirmed": "on" if "confirmed" in form_data else "",
        }
        scope_config, scope_summary_rows, scope_error, scope_preview_yaml = _load_runs_scope_state(
            resolved_repo_root / CANONICAL_DATA_SCOPE_PATH
        )
        if scope_config is None:
            return HTMLResponse(
                content=_render_runs(
                    repo_root_path=resolved_repo_root,
                    active_run=app_runner.get_active_run(),
                    recent_runs=app_runner.list_recent_runs(limit=10),
                    scope_summary_rows=scope_summary_rows,
                    scope_preview_yaml=scope_preview_yaml,
                    error_message=scope_error,
                    form_values=form_values,
                ),
                status_code=400,
            )

        record = app_runner.admit_and_launch(
            build_command_request(
                command=form_values["command"],
                operator_id=form_values["operator_id"],
                armed="armed" in form_data,
                confirmed="confirmed" in form_data,
                cycle=int(scope_config["cycle"]),
                tables=list(scope_config["tables"]),
                force=False,
                dbt_threads=None,
            )
        )
        params = urlencode(
            {
                "run_number": record.run_number,
                "message": f"Workflow Run {record.run_number} saved with {record.lifecycle_state} status.",
            }
        )
        return RedirectResponse(url=f"/runs?{params}", status_code=303)

    @app.post("/runs/{run_number}/cancel", include_in_schema=False)
    def cancel_run_page(run_number: int) -> RedirectResponse:
        try:
            record = app_runner.cancel_run(run_number)
        except KeyError as exc:
            params = urlencode({"error": str(exc)})
            return RedirectResponse(url=f"/runs?{params}", status_code=303)

        params = urlencode(
            {
                "run_number": record.run_number,
                "message": f"Workflow Run {record.run_number} is now {record.lifecycle_state}.",
            }
        )
        return RedirectResponse(url=f"/runs?{params}", status_code=303)

    for path, label in SCREEN_ROUTES:
        if path in {"/dashboard", "/runs", "/data-scope-config", "/history", "/upstream-changes", "/health"}:
            continue

        def render_page(page_path: str = path, page_label: str = label) -> HTMLResponse:
            del page_label
            return HTMLResponse(content=render_shell(page_path))

        app.get(path, response_class=HTMLResponse, include_in_schema=False)(render_page)

    return app


app = create_app()
