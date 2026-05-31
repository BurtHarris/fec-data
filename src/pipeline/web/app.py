"""Operations web app shell for local-trusted workflows."""

from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from pipeline.data_scope import CANONICAL_DATA_SCOPE_PATH, DEFAULT_TABLES, load_data_scope_config
from pipeline.etl_config import repo_root
from pipeline.web.command_runner import CommandAuditStore, CommandRequest, CommandRunner, CommandRunRecord


SCREEN_ROUTES: tuple[tuple[str, str], ...] = (
    ("/dashboard", "Dashboard"),
    ("/runs", "Runs"),
    ("/data-scope-config", "Data Scope Config"),
    ("/history", "History"),
    ("/upstream-changes", "Upstream Changes"),
)


def render_shell(active_path: str, body_html: str | None = None) -> str:
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
        grid-template-columns: repeat(5, minmax(0, 1fr));
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
      .field select {{
        border: 1px solid var(--line);
        border-radius: 0.45rem;
        padding: 0.55rem 0.65rem;
        font: inherit;
        background: white;
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
      @media (max-width: 760px) {{
        .nav {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        .dashboard-grid {{
          grid-template-columns: 1fr;
        }}
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


def _render_detail_rows(rows: list[tuple[str, str]]) -> str:
    items = [
        f"<div class='detail-row'><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>"
        for label, value in rows
    ]
    return f"<dl class='detail-list'>{''.join(items)}</dl>"


def _format_record(record: CommandRunRecord) -> str:
    return _render_detail_rows(
        [
            ("Status", record.lifecycle_state),
            ("Command", record.command),
            ("Operator", record.operator_id),
            ("Request ID", record.request_id),
            ("Requested", record.requested_at),
            ("Launched", record.launched_at or "not launched"),
            ("Completed", record.completed_at or "in progress"),
            ("Admission", record.admission_status),
            ("Launch", record.launch_status),
            ("PID", str(record.pid) if record.pid is not None else "n/a"),
            ("Exit code", str(record.exit_code) if record.exit_code is not None else "n/a"),
            ("Log path", record.log_path or "n/a"),
            ("Command line", record.command_line or "n/a"),
            ("Rejection", record.rejection_reason or "n/a"),
            ("Launch error", record.launch_error or "n/a"),
        ]
    )


def _render_dashboard(repo_root_path: Path, active_run: CommandRunRecord | None) -> str:
    config_path = repo_root_path / CANONICAL_DATA_SCOPE_PATH

    try:
        config = load_data_scope_config(config_path)
        scope_html = _render_detail_rows(
            [
                ("Status", "configured"),
                ("Coverage", str(config["coverage"])),
                ("Facts", str(config["facts"])),
                ("Dimension tables", ", ".join(config["table_groups"]["dimensions"]) or "(none)"),
                ("Fact tables", ", ".join(config["table_groups"]["facts"]) or "(none)"),
                ("Config path", str(config_path)),
            ]
        )
    except SystemExit as exc:
        scope_html = _render_detail_rows(
            [
                ("Status", "unavailable"),
                ("Config path", str(config_path)),
                ("Message", str(exc)),
            ]
        )

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
                ("Request ID", active_run.request_id),
                ("Requested", active_run.requested_at),
                ("Launched", active_run.launched_at or "not launched"),
                ("PID", str(active_run.pid) if active_run.pid is not None else "n/a"),
                ("Launch", active_run.launch_status),
                ("Log path", active_run.log_path or "n/a"),
            ]
        )

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
"""
    return render_shell("/dashboard", body_html=body_html)


def _render_runs(
    active_run: CommandRunRecord | None,
    request_record: CommandRunRecord | None,
    message: str | None = None,
    error_message: str | None = None,
    form_values: dict[str, str] | None = None,
    selected_tables: tuple[str, ...] = (),
) -> str:
    values = {
        "operator_id": "",
        "command": "fetch",
        "cycle": "",
        "dbt_threads": "",
        **(form_values or {}),
    }
    selected = set(selected_tables)
    table_inputs = "".join(
        (
            "<label class='checkbox-item'>"
            f"<input type='checkbox' name='tables' value='{escape(table)}' {'checked' if table in selected else ''}>"
            f"<span>{escape(table)}</span>"
            "</label>"
        )
        for table in DEFAULT_TABLES
    )

    message_html = ""
    if message:
        message_html += f"<section class='message'><strong>Workflow Run update.</strong> {escape(message)}</section>"
    if error_message:
        message_html += f"<section class='message error'><strong>Workflow Run error.</strong> {escape(error_message)}</section>"

    active_html = (
        "<p class='muted'>No active Workflow Run. You can submit a new allowlisted command below.</p>"
        if active_run is None
        else _format_record(active_run)
    )
    request_html = (
        "<p class='muted'>No recently submitted Workflow Run is selected.</p>"
        if request_record is None
        else _format_record(request_record)
    )
    cancel_form = ""
    if active_run is not None:
        cancel_form = (
            f"<form method='post' action='/runs/{escape(active_run.request_id)}/cancel'>"
            "<button class='button secondary' type='submit'>Cancel active run</button>"
            "</form>"
        )

    body_html = f"""
<div class='stack'>
  {message_html}
  <section class='subpanel'>
    <h3>Submit Workflow Run</h3>
    <p class='muted'>Launch an allowlisted fetch, load, or benchmark workflow run. Run controls stay gated behind armed and confirmed toggles.</p>
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
        <div class='field'>
          <label for='cycle'>Cycle</label>
          <input id='cycle' name='cycle' type='number' value='{escape(values["cycle"])}' min='1970' step='2' required>
        </div>
        <div class='field'>
          <label for='dbt_threads'>dbt threads (load and benchmark-load)</label>
          <input id='dbt_threads' name='dbt_threads' type='number' value='{escape(values["dbt_threads"])}' min='1'>
        </div>
      </div>
      <div class='field'>
        <label>Tables</label>
        <div class='checkbox-grid'>{table_inputs}</div>
      </div>
      <div class='actions'>
        <label class='toggle-row'><input name='force' type='checkbox' {'checked' if values.get('force') == 'on' else ''}> <span>Force fetch</span></label>
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
      <h3>Active Workflow Run</h3>
      <p class='muted'>The Run Lock permits one active Workflow Run at a time.</p>
      {active_html}
      <div class='actions'>{cancel_form}</div>
    </section>
    <section class='subpanel'>
      <h3>Selected Run Result</h3>
      <p class='muted'>Shows the persisted audit record for the run selected by redirect after submission or cancel.</p>
      {request_html}
    </section>
  </div>
</div>
"""
    return render_shell("/runs", body_html=body_html)


def create_app(repo_root_path: Path | None = None, runner: CommandRunner | None = None) -> FastAPI:
    """Create the operations web app instance."""

    app = FastAPI(title="MoneyTrail Operations", version="0.1.0")
    resolved_repo_root = repo_root_path or repo_root()
    app_runner = runner
    if app_runner is None:
        store = CommandAuditStore(resolved_repo_root / Path("db") / "ops_web.sqlite")
        app_runner = CommandRunner(repo_root=resolved_repo_root, store=store)

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
        request_id: str
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
        request_id: str | None = None
        lifecycle_state: str | None = None

    class RunStatusResponse(BaseModel):
        request_id: str
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
            request_id=record.request_id,
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
        return ActiveRunResponse(active=True, request_id=record.request_id, lifecycle_state=record.lifecycle_state)

    @app.get("/api/runs/{request_id}", response_model=RunStatusResponse)
    def run_status(request_id: str) -> RunStatusResponse:
        record = app_runner.get_run(request_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        return RunStatusResponse(
            request_id=record.request_id,
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

    @app.post("/api/runs/{request_id}/cancel", response_model=RunStatusResponse)
    def cancel_run(request_id: str) -> RunStatusResponse:
        try:
            record = app_runner.cancel_run(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return RunStatusResponse(
            request_id=record.request_id,
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
        return HTMLResponse(content=_render_dashboard(resolved_repo_root, app_runner.get_active_run()))

    @app.get("/runs", response_class=HTMLResponse, include_in_schema=False)
    def runs(request_id: str | None = None, message: str | None = None, error: str | None = None) -> HTMLResponse:
        selected_record = app_runner.get_run(request_id) if request_id else None
        return HTMLResponse(
            content=_render_runs(
                active_run=app_runner.get_active_run(),
                request_record=selected_record,
                message=message,
                error_message=error,
            )
        )

    @app.post("/runs/submit", include_in_schema=False)
    async def submit_run_page(request: Request) -> RedirectResponse:
        form_data = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
        form_values = {
            "operator_id": form_data.get("operator_id", [""])[0],
            "command": form_data.get("command", ["fetch"])[0],
            "cycle": form_data.get("cycle", [""])[0],
            "dbt_threads": form_data.get("dbt_threads", [""])[0],
            "force": "on" if "force" in form_data else "",
            "armed": "on" if "armed" in form_data else "",
            "confirmed": "on" if "confirmed" in form_data else "",
        }
        selected_tables = tuple(table.strip().lower() for table in form_data.get("tables", []) if table.strip())

        try:
            cycle = int(form_values["cycle"])
        except ValueError:
            return HTMLResponse(
                content=_render_runs(
                    active_run=app_runner.get_active_run(),
                    request_record=None,
                    error_message="cycle must be a whole year",
                    form_values=form_values,
                    selected_tables=selected_tables,
                ),
                status_code=400,
            )

        dbt_threads_raw = form_values["dbt_threads"].strip()
        try:
            dbt_threads = int(dbt_threads_raw) if dbt_threads_raw else None
        except ValueError:
            return HTMLResponse(
                content=_render_runs(
                    active_run=app_runner.get_active_run(),
                    request_record=None,
                    error_message="dbt threads must be a whole number",
                    form_values=form_values,
                    selected_tables=selected_tables,
                ),
                status_code=400,
            )

        record = app_runner.admit_and_launch(
            build_command_request(
                command=form_values["command"],
                operator_id=form_values["operator_id"],
                armed="armed" in form_data,
                confirmed="confirmed" in form_data,
                cycle=cycle,
                tables=list(selected_tables),
                force="force" in form_data,
                dbt_threads=dbt_threads,
            )
        )
        params = urlencode(
            {
                "request_id": record.request_id,
                "message": f"Workflow Run {record.request_id} saved with {record.lifecycle_state} status.",
            }
        )
        return RedirectResponse(url=f"/runs?{params}", status_code=303)

    @app.post("/runs/{request_id}/cancel", include_in_schema=False)
    def cancel_run_page(request_id: str) -> RedirectResponse:
        try:
            record = app_runner.cancel_run(request_id)
        except KeyError as exc:
            params = urlencode({"error": str(exc)})
            return RedirectResponse(url=f"/runs?{params}", status_code=303)

        params = urlencode(
            {
                "request_id": record.request_id,
                "message": f"Workflow Run {record.request_id} is now {record.lifecycle_state}.",
            }
        )
        return RedirectResponse(url=f"/runs?{params}", status_code=303)

    for path, label in SCREEN_ROUTES:
        if path in {"/dashboard", "/runs"}:
            continue

        def render_page(page_path: str = path, page_label: str = label) -> HTMLResponse:
            del page_label
            return HTMLResponse(content=render_shell(page_path))

        app.get(path, response_class=HTMLResponse, include_in_schema=False)(render_page)

    return app


app = create_app()
