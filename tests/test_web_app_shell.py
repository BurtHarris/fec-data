import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi import Request

from pipeline.data_scope import CANONICAL_DATA_SCOPE_PATH
from pipeline.web.app import SCREEN_ROUTES, create_app, render_shell
from pipeline.web.command_runner import CommandRequest, CommandRunRecord


class _StubRunner:
    def __init__(self, active_run: CommandRunRecord | None = None) -> None:
        self._active_run = active_run
        self._records: dict[int, CommandRunRecord] = {}
        self.last_request: CommandRequest | None = None
        if active_run is not None:
            assert active_run.run_number is not None
            self._records[active_run.run_number] = active_run

    def get_active_run(self) -> CommandRunRecord | None:
        return self._active_run

    def get_run(self, run_number: int) -> CommandRunRecord | None:
        return self._records.get(run_number)

    def list_recent_runs(self, limit: int = 25) -> list[CommandRunRecord]:
        return sorted(
            self._records.values(),
            key=lambda record: (record.requested_at, record.run_number or 0),
            reverse=True,
        )[:limit]

    def admit_and_launch(self, request: CommandRequest) -> CommandRunRecord:
        self.last_request = request
        if request.armed and request.confirmed:
            lifecycle_state = "running"
            admission_status = "admitted"
            rejection_reason = None
            launch_status = "launched"
            pid = 999
            command_line = f"uv run {request.command}"
            log_path = f"logs\\{request.command}.log"
        else:
            lifecycle_state = "rejected"
            admission_status = "rejected"
            rejection_reason = "run request rejected: app is not armed"
            launch_status = "not_started"
            pid = None
            command_line = None
            log_path = None

        record = CommandRunRecord(
            run_number=len(self._records) + 1,
            requested_at="2026-05-31T14:10:00Z",
            operator_id=request.operator_id,
            command=request.command,
            payload_json="{}",
            admission_status=admission_status,
            rejection_reason=rejection_reason,
            launch_status=launch_status,
            launch_error=None,
            launched_at="2026-05-31T14:10:05Z" if admission_status == "admitted" else None,
            pid=pid,
            command_line=command_line,
            log_path=log_path,
            lifecycle_state=lifecycle_state,
            completed_at=None if admission_status == "admitted" else "2026-05-31T14:10:00Z",
            exit_code=None,
        )
        assert record.run_number is not None
        self._records[record.run_number] = record
        if admission_status == "admitted":
            self._active_run = record
        return record

    def cancel_run(self, run_number: int) -> CommandRunRecord:
        record = self._records.get(run_number)
        if record is None:
            raise KeyError(f"run not found: {run_number}")
        canceled = CommandRunRecord(
            run_number=record.run_number,
            requested_at=record.requested_at,
            operator_id=record.operator_id,
            command=record.command,
            payload_json=record.payload_json,
            admission_status=record.admission_status,
            rejection_reason=record.rejection_reason,
            launch_status=record.launch_status,
            launch_error=record.launch_error,
            launched_at=record.launched_at,
            pid=record.pid,
            command_line=record.command_line,
            log_path=record.log_path,
            lifecycle_state="canceled",
            completed_at="2026-05-31T14:12:00Z",
            exit_code=-15,
        )
        assert canceled.run_number is not None
        self._records[canceled.run_number] = canceled
        if self._active_run and self._active_run.run_number == run_number:
            self._active_run = None
        return canceled


def _write_data_scope(root: Path, content: str) -> Path:
    config_path = root / CANONICAL_DATA_SCOPE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8", newline="\n")
    return config_path


def _write_metadata_history(metadata_db_path: Path, rows: list[tuple[object, ...]]) -> Path:
    metadata_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(metadata_db_path)
    try:
        conn.execute(
            """
            CREATE TABLE etl_fetch_history (
                fetch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle INTEGER NOT NULL,
                table_name TEXT NOT NULL,
                zip_name TEXT,
                source_url TEXT,
                fetch_status TEXT NOT NULL,
                http_status INTEGER,
                content_length INTEGER,
                response_date TEXT,
                last_modified TEXT,
                etag TEXT,
                local_file_size INTEGER,
                fetched_at TEXT NOT NULL,
                error_text TEXT
            )
            """
        )
        conn.executemany(
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
                fetched_at,
                error_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return metadata_db_path


def _render_dashboard_html(root: Path, active_run: CommandRunRecord | None = None) -> str:
    app = create_app(repo_root_path=root, runner=_StubRunner(active_run))
    dashboard_route = next((route for route in app.routes if getattr(route, "path", None) == "/dashboard"), None)
    assert dashboard_route is not None
    response = dashboard_route.endpoint()
    return response.body.decode("utf-8")


def _make_request(path: str, body: bytes = b"") -> Request:
    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
        },
        receive=receive,
    )


class OperationsWebAppShellTests(unittest.TestCase):
    def test_healthz_endpoint_is_registered(self) -> None:
        app = create_app()

        health_route = next((route for route in app.routes if getattr(route, "path", None) == "/healthz"), None)

        self.assertIsNotNone(health_route)
        self.assertEqual(health_route.endpoint(), {"status": "ok"})

    def test_shell_routes_render_navigation_placeholders(self) -> None:
        html = render_shell("/dashboard")

        for _, label in SCREEN_ROUTES:
            self.assertIn(label, html)

    def test_dashboard_route_renders_canonical_scope_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_data_scope(
                root,
                """version: 1
coverage: 2018-2026
facts: 2022-2026
table_groups:
  dimensions: [cm, cn, ccl, weball]
  facts: [indiv, oppexp, oth, pas2]
""",
            )

            html = _render_dashboard_html(root)

        self.assertIn("Current Data Scope Config", html)
        self.assertIn("2018-2026", html)
        self.assertIn("2022-2026", html)
        self.assertIn("cm, cn, ccl, weball", html)
        self.assertIn("indiv, oppexp, oth, pas2", html)
        self.assertIn(str(config_path), html)
        self.assertIn("No active Workflow Run.", html)

    def test_dashboard_route_reports_missing_scope_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            html = _render_dashboard_html(Path(temp_dir))

        self.assertIn("Status", html)
        self.assertIn("unavailable", html)
        self.assertIn("Data Scope config not found", html)

    def test_dashboard_route_reports_invalid_scope_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_data_scope(
                root,
                """version: 1
coverage: 2024-2026
facts: 2022-2026
table_groups:
  dimensions: [cm]
  facts: [indiv]
""",
            )

            html = _render_dashboard_html(root)

        self.assertIn("unavailable", html)
        self.assertIn("facts range must be fully contained within coverage range", html)

    def test_dashboard_route_renders_active_run_summary(self) -> None:
        active_run = CommandRunRecord(
            run_number=123,
            requested_at="2026-05-31T14:00:00Z",
            operator_id="alice & bob",
            command="fetch",
            payload_json="{}",
            admission_status="admitted",
            rejection_reason=None,
            launch_status="launched",
            launch_error=None,
            launched_at="2026-05-31T14:00:05Z",
            pid=4242,
            command_line="pwsh ./scripts/run.ps1",
            log_path="logs\\run-123.log",
            lifecycle_state="running",
            completed_at=None,
            exit_code=None,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_data_scope(
                root,
                """version: 1
coverage: 2024-2026
facts: 2026
table_groups:
  dimensions: [cm]
  facts: [indiv]
""",
            )

            html = _render_dashboard_html(root, active_run)

        self.assertIn("running", html)
        self.assertIn("fetch", html)
        self.assertIn("123", html)
        self.assertIn("alice &amp; bob", html)
        self.assertIn("logs\\run-123.log", html)

    def test_data_scope_route_renders_current_config_and_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_data_scope(
                root,
                """version: 1
coverage: 2018-2026
facts: 2022-2026
table_groups:
  dimensions: [cm, cn, ccl, weball]
  facts: [indiv, oppexp, oth, pas2]
""",
            )
            app = create_app(repo_root_path=root, runner=_StubRunner())
            route = next((route for route in app.routes if getattr(route, "path", None) == "/data-scope-config"), None)
            assert route is not None

            response = route.endpoint()
            html = response.body.decode("utf-8")

        self.assertIn("Canonical Data Scope Config", html)
        self.assertIn(str(config_path), html)
        self.assertIn("Resolved YAML Preview", html)
        self.assertIn("coverage: 2018-2026", html)
        self.assertIn("facts: 2022-2026", html)
        self.assertIn("In-app editing is deferred to developer workflows for now.", html)

    def test_data_scope_route_reports_missing_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(repo_root_path=Path(temp_dir), runner=_StubRunner())
            route = next((route for route in app.routes if getattr(route, "path", None) == "/data-scope-config"), None)
            assert route is not None

            response = route.endpoint()
            html = response.body.decode("utf-8")

        self.assertIn("Data Scope config not found", html)
        self.assertIn("Resolved YAML preview unavailable", html)

    def test_data_scope_route_is_read_only(self) -> None:
        app = create_app(runner=_StubRunner())
        registered_paths = {route.path for route in app.routes if hasattr(route, "path")}

        self.assertIn("/data-scope-config", registered_paths)
        self.assertNotIn("/data-scope-config/save", registered_paths)

    def test_history_route_renders_recent_run_records(self) -> None:
        runner = _StubRunner()
        completed = CommandRunRecord(
            run_number=1,
            requested_at="2026-05-31T13:00:00Z",
            operator_id="alice",
            command="fetch",
            payload_json="{}",
            admission_status="admitted",
            rejection_reason=None,
            launch_status="launched",
            launch_error=None,
            launched_at="2026-05-31T13:00:05Z",
            pid=111,
            command_line="uv run download",
            log_path="logs\\run-1.log",
            lifecycle_state="completed",
            completed_at="2026-05-31T13:10:00Z",
            exit_code=0,
        )
        rejected = CommandRunRecord(
            run_number=2,
            requested_at="2026-05-31T14:00:00Z",
            operator_id="bob",
            command="load",
            payload_json="{}",
            admission_status="rejected",
            rejection_reason="run request rejected: app is not armed",
            launch_status="not_started",
            launch_error=None,
            launched_at=None,
            pid=None,
            command_line=None,
            log_path=None,
            lifecycle_state="rejected",
            completed_at="2026-05-31T14:00:00Z",
            exit_code=None,
        )
        runner._records = {1: completed, 2: rejected}
        app = create_app(runner=runner)
        route = next((route for route in app.routes if getattr(route, "path", None) == "/history"), None)
        assert route is not None

        response = route.endpoint()
        html = response.body.decode("utf-8")

        self.assertIn("Run History", html)
        self.assertIn(">2<", html)
        self.assertIn(">1<", html)
        self.assertIn("rejected", html)
        self.assertIn("completed", html)
        self.assertIn("logs\\run-1.log", html)

    def test_history_route_renders_empty_state(self) -> None:
        app = create_app(runner=_StubRunner())
        route = next((route for route in app.routes if getattr(route, "path", None) == "/history"), None)
        assert route is not None

        response = route.endpoint()
        html = response.body.decode("utf-8")

        self.assertIn("No persisted Workflow Runs yet.", html)

    def test_upstream_changes_route_renders_empty_state_when_db_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app = create_app(
                repo_root_path=root,
                runner=_StubRunner(),
                metadata_db_path=root / "db" / "fec-metadata.sqlite",
            )
            route = next((route for route in app.routes if getattr(route, "path", None) == "/upstream-changes"), None)
            assert route is not None

            response = route.endpoint()
            html = response.body.decode("utf-8")

        self.assertIn("Metadata history database not found", html)
        self.assertIn("Metadata history status", html)

    def test_upstream_changes_route_renders_change_tables_when_history_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            metadata_db_path = _write_metadata_history(
                root / "db" / "fec-metadata.sqlite",
                [
                    (
                        2024,
                        "indiv",
                        "indiv24.zip",
                        "https://example.test/indiv24.zip",
                        "success",
                        200,
                        100,
                        None,
                        "Mon, 01 Jan 2024 00:00:00 GMT",
                        "etag-a",
                        100,
                        "2024-01-01T00:00:00Z",
                        None,
                    ),
                    (
                        2024,
                        "indiv",
                        "indiv24.zip",
                        "https://example.test/indiv24.zip",
                        "success",
                        200,
                        120,
                        None,
                        "Tue, 06 Feb 2024 00:00:00 GMT",
                        "etag-b",
                        120,
                        "2024-02-06T00:00:00Z",
                        None,
                    ),
                ],
            )
            app = create_app(repo_root_path=root, runner=_StubRunner(), metadata_db_path=metadata_db_path)
            route = next((route for route in app.routes if getattr(route, "path", None) == "/upstream-changes"), None)
            assert route is not None

            response = route.endpoint()
            html = response.body.decode("utf-8")

        self.assertIn("Upstream metadata shifts", html)
        self.assertIn("Recent change events", html)
        self.assertIn("Monthly burst windows", html)
        self.assertIn("Cadence by asset", html)
        self.assertIn("indiv", html)
        self.assertIn("content_length", html)
        self.assertIn("etag", html)

    def test_runs_route_renders_form_and_active_run(self) -> None:
        active_run = CommandRunRecord(
            run_number=7,
            requested_at="2026-05-31T14:00:00Z",
            operator_id="alice",
            command="fetch",
            payload_json="{}",
            admission_status="admitted",
            rejection_reason=None,
            launch_status="launched",
            launch_error=None,
            launched_at="2026-05-31T14:00:05Z",
            pid=4242,
            command_line="uv run fetch",
            log_path="logs\\run-7.log",
            lifecycle_state="running",
            completed_at=None,
            exit_code=None,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_data_scope(
                root,
                """version: 1
coverage: 2018-2026
facts: 2022-2026
table_groups:
  dimensions: [cm, cn]
  facts: [indiv, oth]
""",
            )
            app = create_app(repo_root_path=root, runner=_StubRunner(active_run))
            runs_route = next((route for route in app.routes if getattr(route, "path", None) == "/runs"), None)

            self.assertIsNotNone(runs_route)
            response = runs_route.endpoint()
            html = response.body.decode("utf-8")

        self.assertIn("Submit Workflow Run", html)
        self.assertIn("Cancel active run", html)
        self.assertIn("Recent Run Log", html)
        self.assertIn("run-7.log", html)
        self.assertIn("refresh", html)
        self.assertIn("Run Request Source", html)
        self.assertIn("Derived cycle", html)
        self.assertIn("2026", html)
        self.assertIn("coverage: 2018-2026", html)
        self.assertNotIn("dbt threads", html)
        self.assertNotIn("Force fetch", html)

    def test_runs_submit_redirects_to_selected_run(self) -> None:
        runner = _StubRunner()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_data_scope(
                root,
                """version: 1
coverage: 2018-2026
facts: 2022-2026
table_groups:
  dimensions: [cm, cn]
  facts: [indiv, oth]
""",
            )
            app = create_app(repo_root_path=root, runner=runner)
            submit_route = next((route for route in app.routes if getattr(route, "path", None) == "/runs/submit"), None)
            assert submit_route is not None

            request = _make_request(
                "/runs/submit",
                b"operator_id=alice&command=fetch&armed=on&confirmed=on",
            )
            response = asyncio.run(submit_route.endpoint(request))

        self.assertEqual(response.status_code, 303)
        self.assertIn("/runs?run_number=1", response.headers["location"])
        saved = runner.get_run(1)
        self.assertIsNotNone(saved)
        assert saved is not None
        assert runner.last_request is not None
        self.assertEqual(saved.command, "fetch")
        self.assertEqual(saved.lifecycle_state, "running")
        self.assertEqual(runner.last_request.cycle, 2026)
        self.assertEqual(runner.last_request.tables, ("cm", "cn", "indiv", "oth"))

    def test_runs_submit_missing_scope_config_renders_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(repo_root_path=Path(temp_dir), runner=_StubRunner())
            submit_route = next((route for route in app.routes if getattr(route, "path", None) == "/runs/submit"), None)
            assert submit_route is not None

            request = _make_request(
                "/runs/submit",
                b"operator_id=alice&command=fetch&armed=on&confirmed=on",
            )
            response = asyncio.run(submit_route.endpoint(request))
            html = response.body.decode("utf-8")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Data Scope config not found", html)

    def test_runs_cancel_redirects_with_status(self) -> None:
        active_run = CommandRunRecord(
            run_number=9,
            requested_at="2026-05-31T14:00:00Z",
            operator_id="alice",
            command="load",
            payload_json="{}",
            admission_status="admitted",
            rejection_reason=None,
            launch_status="launched",
            launch_error=None,
            launched_at="2026-05-31T14:00:05Z",
            pid=4242,
            command_line="uv run load",
            log_path="logs\\run-9.log",
            lifecycle_state="running",
            completed_at=None,
            exit_code=None,
        )
        runner = _StubRunner(active_run)
        app = create_app(runner=runner)
        cancel_route = next(
            (route for route in app.routes if getattr(route, "path", None) == "/runs/{run_number}/cancel"),
            None,
        )
        assert cancel_route is not None

        response = cancel_route.endpoint(9)

        self.assertEqual(response.status_code, 303)
        self.assertIn("run_number=9", response.headers["location"])
        self.assertEqual(runner.get_run(9).lifecycle_state, "canceled")

    def test_expected_placeholder_routes_are_registered(self) -> None:
        app = create_app()
        registered_paths = {route.path for route in app.routes if hasattr(route, "path")}

        self.assertIn("/", registered_paths)
        self.assertIn("/api/runs/submit", registered_paths)
        self.assertIn("/api/runs/active", registered_paths)
        self.assertIn("/api/runs/{run_number}", registered_paths)
        self.assertIn("/api/runs/{run_number}/cancel", registered_paths)
        for path, _ in SCREEN_ROUTES:
            self.assertIn(path, registered_paths)


if __name__ == "__main__":
    unittest.main()
