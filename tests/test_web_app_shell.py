import asyncio
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
        self._records: dict[str, CommandRunRecord] = {}
        if active_run is not None:
            self._records[active_run.request_id] = active_run

    def get_active_run(self) -> CommandRunRecord | None:
        return self._active_run

    def get_run(self, request_id: str) -> CommandRunRecord | None:
        return self._records.get(request_id)

    def admit_and_launch(self, request: CommandRequest) -> CommandRunRecord:
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
            request_id=f"stub-{len(self._records) + 1}",
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
        self._records[record.request_id] = record
        if admission_status == "admitted":
            self._active_run = record
        return record

    def cancel_run(self, request_id: str) -> CommandRunRecord:
        record = self._records.get(request_id)
        if record is None:
            raise KeyError(f"run not found: {request_id}")
        canceled = CommandRunRecord(
            request_id=record.request_id,
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
        self._records[request_id] = canceled
        if self._active_run and self._active_run.request_id == request_id:
            self._active_run = None
        return canceled


def _write_data_scope(root: Path, content: str) -> Path:
    config_path = root / CANONICAL_DATA_SCOPE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8", newline="\n")
    return config_path


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
            request_id="req-123",
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
            log_path="logs\\req-123.log",
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
        self.assertIn("req-123", html)
        self.assertIn("alice &amp; bob", html)
        self.assertIn("logs\\req-123.log", html)

    def test_runs_route_renders_form_and_active_run(self) -> None:
        active_run = CommandRunRecord(
            request_id="req-active",
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
            log_path="logs\\req-active.log",
            lifecycle_state="running",
            completed_at=None,
            exit_code=None,
        )
        app = create_app(runner=_StubRunner(active_run))
        runs_route = next((route for route in app.routes if getattr(route, "path", None) == "/runs"), None)

        self.assertIsNotNone(runs_route)
        response = runs_route.endpoint()
        html = response.body.decode("utf-8")

        self.assertIn("Submit Workflow Run", html)
        self.assertIn("Cancel active run", html)
        self.assertIn("req-active", html)
        self.assertIn("benchmark-load", html)

    def test_runs_submit_redirects_to_selected_run(self) -> None:
        runner = _StubRunner()
        app = create_app(runner=runner)
        submit_route = next((route for route in app.routes if getattr(route, "path", None) == "/runs/submit"), None)
        assert submit_route is not None

        request = _make_request(
            "/runs/submit",
            b"operator_id=alice&command=fetch&cycle=2026&tables=cm&tables=indiv&armed=on&confirmed=on",
        )
        response = asyncio.run(submit_route.endpoint(request))

        self.assertEqual(response.status_code, 303)
        self.assertIn("/runs?request_id=stub-1", response.headers["location"])
        saved = runner.get_run("stub-1")
        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertEqual(saved.command, "fetch")
        self.assertEqual(saved.lifecycle_state, "running")

    def test_runs_submit_invalid_cycle_renders_error(self) -> None:
        app = create_app(runner=_StubRunner())
        submit_route = next((route for route in app.routes if getattr(route, "path", None) == "/runs/submit"), None)
        assert submit_route is not None

        request = _make_request(
            "/runs/submit",
            b"operator_id=alice&command=fetch&cycle=not-a-year&armed=on&confirmed=on",
        )
        response = asyncio.run(submit_route.endpoint(request))
        html = response.body.decode("utf-8")

        self.assertEqual(response.status_code, 400)
        self.assertIn("cycle must be a whole year", html)

    def test_runs_submit_invalid_dbt_threads_renders_error(self) -> None:
        app = create_app(runner=_StubRunner())
        submit_route = next((route for route in app.routes if getattr(route, "path", None) == "/runs/submit"), None)
        assert submit_route is not None

        request = _make_request(
            "/runs/submit",
            b"operator_id=alice&command=load&cycle=2026&dbt_threads=abc&armed=on&confirmed=on",
        )
        response = asyncio.run(submit_route.endpoint(request))
        html = response.body.decode("utf-8")

        self.assertEqual(response.status_code, 400)
        self.assertIn("dbt threads must be a whole number", html)

    def test_runs_cancel_redirects_with_status(self) -> None:
        active_run = CommandRunRecord(
            request_id="req-active",
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
            log_path="logs\\req-active.log",
            lifecycle_state="running",
            completed_at=None,
            exit_code=None,
        )
        runner = _StubRunner(active_run)
        app = create_app(runner=runner)
        cancel_route = next(
            (route for route in app.routes if getattr(route, "path", None) == "/runs/{request_id}/cancel"),
            None,
        )
        assert cancel_route is not None

        response = cancel_route.endpoint("req-active")

        self.assertEqual(response.status_code, 303)
        self.assertIn("request_id=req-active", response.headers["location"])
        self.assertEqual(runner.get_run("req-active").lifecycle_state, "canceled")

    def test_expected_placeholder_routes_are_registered(self) -> None:
        app = create_app()
        registered_paths = {route.path for route in app.routes if hasattr(route, "path")}

        self.assertIn("/", registered_paths)
        self.assertIn("/api/runs/submit", registered_paths)
        self.assertIn("/api/runs/active", registered_paths)
        self.assertIn("/api/runs/{request_id}", registered_paths)
        self.assertIn("/api/runs/{request_id}/cancel", registered_paths)
        for path, _ in SCREEN_ROUTES:
            self.assertIn(path, registered_paths)


if __name__ == "__main__":
    unittest.main()
