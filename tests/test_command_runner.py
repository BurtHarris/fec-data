import tempfile
import unittest
from pathlib import Path

from pipeline.web.command_runner import CommandAuditStore, CommandRequest, CommandRunner


class _FakeProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15

    def wait(self, timeout: int) -> int:
        del timeout
        if self.returncode is None:
            self.returncode = -15
        return self.returncode

    def kill(self) -> None:
        self.returncode = -9


class CommandRunnerTests(unittest.TestCase):
    def test_rejected_request_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = CommandAuditStore(root / "db" / "ops_web.sqlite")
            runner = CommandRunner(repo_root=root, store=store)

            record = runner.admit_and_launch(
                CommandRequest(
                    command="fetch",
                    operator_id="alice",
                    armed=False,
                    confirmed=True,
                    cycle=2026,
                )
            )

            self.assertEqual(record.admission_status, "rejected")
            self.assertEqual(record.launch_status, "not_started")
            self.assertEqual(record.lifecycle_state, "rejected")
            self.assertIn("not armed", record.rejection_reason or "")
            self.assertEqual(record.run_number, 1)

            persisted = store.get_record(record.run_number or 0)
            self.assertIsNotNone(persisted)
            self.assertEqual(persisted.admission_status, "rejected")

    def test_admitted_request_launches_and_persists_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = CommandAuditStore(root / "db" / "ops_web.sqlite")

            calls: list[list[str]] = []

            def launcher(*args, **kwargs):
                del kwargs
                calls.append(list(args[0]))
                return _FakeProcess(pid=4242)

            runner = CommandRunner(repo_root=root, store=store, process_launcher=launcher)
            record = runner.admit_and_launch(
                CommandRequest(
                    command="fetch",
                    operator_id="alice",
                    armed=True,
                    confirmed=True,
                    cycle=2026,
                    tables=("cm",),
                    force=True,
                )
            )

            self.assertEqual(record.admission_status, "admitted")
            self.assertEqual(record.launch_status, "launched")
            self.assertEqual(record.lifecycle_state, "running")
            self.assertEqual(record.pid, 4242)
            self.assertEqual(record.run_number, 1)
            self.assertIn("uv run download", record.command_line or "")
            self.assertTrue(record.log_path)
            self.assertTrue(Path(record.log_path or "").exists())
            self.assertIn("run-1", record.log_path or "")
            self.assertTrue(calls)
            self.assertEqual(calls[0][:3], ["uv", "run", "download"])

    def test_launch_failure_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = CommandAuditStore(root / "db" / "ops_web.sqlite")

            def launcher(*args, **kwargs):
                del args
                del kwargs
                raise OSError("mock launch failure")

            runner = CommandRunner(repo_root=root, store=store, process_launcher=launcher)
            record = runner.admit_and_launch(
                CommandRequest(
                    command="load",
                    operator_id="alice",
                    armed=True,
                    confirmed=True,
                    cycle=2026,
                )
            )

            self.assertEqual(record.admission_status, "admitted")
            self.assertEqual(record.launch_status, "launch_failed")
            self.assertEqual(record.lifecycle_state, "failed")
            self.assertIn("mock launch failure", record.launch_error or "")

    def test_second_run_is_rejected_while_lock_is_active(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = CommandAuditStore(root / "db" / "ops_web.sqlite")
            first_process = _FakeProcess(pid=111)
            second_process = _FakeProcess(pid=222)
            process_queue = [first_process, second_process]

            def launcher(*args, **kwargs):
                del args
                del kwargs
                return process_queue.pop(0)

            runner = CommandRunner(repo_root=root, store=store, process_launcher=launcher)
            first = runner.admit_and_launch(
                CommandRequest(
                    command="fetch",
                    operator_id="alice",
                    armed=True,
                    confirmed=True,
                    cycle=2026,
                )
            )
            second = runner.admit_and_launch(
                CommandRequest(
                    command="load",
                    operator_id="bob",
                    armed=True,
                    confirmed=True,
                    cycle=2026,
                )
            )

            self.assertEqual(first.lifecycle_state, "running")
            self.assertEqual(second.admission_status, "rejected")
            self.assertEqual(second.lifecycle_state, "rejected")
            self.assertIn(f"another workflow run is active ({first.run_number})", second.rejection_reason or "")

    def test_run_moves_to_completed_when_process_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = CommandAuditStore(root / "db" / "ops_web.sqlite")
            process = _FakeProcess(pid=333)

            def launcher(*args, **kwargs):
                del args
                del kwargs
                return process

            runner = CommandRunner(repo_root=root, store=store, process_launcher=launcher)
            record = runner.admit_and_launch(
                CommandRequest(
                    command="fetch",
                    operator_id="alice",
                    armed=True,
                    confirmed=True,
                    cycle=2026,
                )
            )

            process.returncode = 0
            updated = runner.get_run(record.run_number or 0)

            self.assertIsNotNone(updated)
            self.assertEqual(updated.lifecycle_state, "completed")
            self.assertEqual(updated.exit_code, 0)

    def test_cancel_marks_run_canceled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = CommandAuditStore(root / "db" / "ops_web.sqlite")
            process = _FakeProcess(pid=444)

            def launcher(*args, **kwargs):
                del args
                del kwargs
                return process

            runner = CommandRunner(repo_root=root, store=store, process_launcher=launcher)
            launched = runner.admit_and_launch(
                CommandRequest(
                    command="load",
                    operator_id="alice",
                    armed=True,
                    confirmed=True,
                    cycle=2026,
                )
            )

            canceled = runner.cancel_run(launched.run_number or 0)

            self.assertEqual(canceled.lifecycle_state, "canceled")
            self.assertIsNotNone(canceled.exit_code)

    def test_list_recent_runs_returns_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = CommandAuditStore(root / "db" / "ops_web.sqlite")

            first_process = _FakeProcess(pid=101)
            second_process = _FakeProcess(pid=202)
            process_queue = [first_process, second_process]

            def launcher(*args, **kwargs):
                del args
                del kwargs
                return process_queue.pop(0)

            runner = CommandRunner(repo_root=root, store=store, process_launcher=launcher)
            first = runner.admit_and_launch(
                CommandRequest(
                    command="fetch",
                    operator_id="alice",
                    armed=True,
                    confirmed=True,
                    cycle=2026,
                )
            )
            first_process.returncode = 0
            runner.get_run(first.run_number or 0)

            second = runner.admit_and_launch(
                CommandRequest(
                    command="load",
                    operator_id="bob",
                    armed=True,
                    confirmed=True,
                    cycle=2026,
                )
            )

            records = runner.list_recent_runs(limit=10)

            self.assertEqual([record.run_number for record in records[:2]], [second.run_number, first.run_number])


if __name__ == "__main__":
    unittest.main()
