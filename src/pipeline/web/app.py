"""Operations web app shell for local-trusted workflows."""

from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse, RedirectResponse

from pipeline.etl_config import repo_root
from pipeline.web.command_runner import CommandAuditStore, CommandRequest, CommandRunner


SCREEN_ROUTES: tuple[tuple[str, str], ...] = (
    ("/dashboard", "Dashboard"),
    ("/runs", "Runs"),
    ("/data-scope-config", "Data Scope Config"),
    ("/history", "History"),
    ("/upstream-changes", "Upstream Changes"),
)


def render_shell(active_path: str) -> str:
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
      @media (max-width: 760px) {{
        .nav {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
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
        <p>Placeholder screen. Operational data wiring is planned in follow-up slices.</p>
      </section>
    </main>
  </body>
</html>
"""


def create_app() -> FastAPI:
    """Create the operations web app instance."""

    app = FastAPI(title="MoneyTrail Operations", version="0.1.0")
    store = CommandAuditStore(repo_root() / Path("db") / "ops_web.sqlite")
    runner = CommandRunner(repo_root=repo_root(), store=store)

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

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard", status_code=307)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/runs/submit", response_model=RunSubmitResponse)
    def submit_run(payload: RunSubmitPayload) -> RunSubmitResponse:
        record = runner.admit_and_launch(
            CommandRequest(
                command=payload.command,
                operator_id=payload.operator_id,
                armed=payload.armed,
                confirmed=payload.confirmed,
                cycle=payload.cycle,
                tables=tuple(table.strip().lower() for table in payload.tables if table.strip()),
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
        record = runner.get_active_run()
        if record is None:
            return ActiveRunResponse(active=False)
        return ActiveRunResponse(active=True, request_id=record.request_id, lifecycle_state=record.lifecycle_state)

    @app.get("/api/runs/{request_id}", response_model=RunStatusResponse)
    def run_status(request_id: str) -> RunStatusResponse:
        record = runner.get_run(request_id)
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
            record = runner.cancel_run(request_id)
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

    for path, label in SCREEN_ROUTES:

        def render_page(page_path: str = path, page_label: str = label) -> HTMLResponse:
            del page_label
            return HTMLResponse(content=render_shell(page_path))

        app.get(path, response_class=HTMLResponse, include_in_schema=False)(render_page)

    return app


app = create_app()
