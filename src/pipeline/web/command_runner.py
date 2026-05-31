"""Allowlisted command runner for operations web app requests."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from pipeline.cli_common import validate_even_cycle
from pipeline.data_scope import DEFAULT_TABLES


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class CommandRequest:
    """Operator request to run one allowlisted workflow command."""

    command: str
    operator_id: str
    armed: bool
    confirmed: bool
    cycle: int
    tables: tuple[str, ...] = ()
    force: bool = False
    dbt_threads: int | None = None


@dataclass(frozen=True)
class CommandRunRecord:
    """Persisted audit record for one command admission and launch attempt."""

    request_id: str
    requested_at: str
    operator_id: str
    command: str
    payload_json: str
    admission_status: str
    rejection_reason: str | None
    launch_status: str
    launch_error: str | None
    launched_at: str | None
    pid: int | None
    command_line: str | None
    log_path: str | None
    lifecycle_state: str
    completed_at: str | None
    exit_code: int | None


class CommandAuditStore:
    """SQLite persistence for command admission and launch outcomes."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS command_run_log (
                    request_id TEXT PRIMARY KEY,
                    requested_at TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    command_name TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    admission_status TEXT NOT NULL,
                    rejection_reason TEXT,
                    launch_status TEXT NOT NULL,
                    launch_error TEXT,
                    launched_at TEXT,
                    pid INTEGER,
                    command_line TEXT,
                    log_path TEXT,
                    lifecycle_state TEXT NOT NULL DEFAULT 'rejected',
                    completed_at TEXT,
                    exit_code INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_lock (
                    lock_name TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    acquired_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "command_run_log", "lifecycle_state", "TEXT NOT NULL DEFAULT 'rejected'")
            self._ensure_column(conn, "command_run_log", "completed_at", "TEXT")
            self._ensure_column(conn, "command_run_log", "exit_code", "INTEGER")
            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table_name: str, column_name: str, ddl: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        names = {row[1] for row in rows}
        if column_name in names:
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")

    def insert_record(self, record: CommandRunRecord) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO command_run_log (
                    request_id,
                    requested_at,
                    operator_id,
                    command_name,
                    payload_json,
                    admission_status,
                    rejection_reason,
                    launch_status,
                    launch_error,
                    launched_at,
                    pid,
                    command_line,
                    log_path,
                    lifecycle_state,
                    completed_at,
                    exit_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.request_id,
                    record.requested_at,
                    record.operator_id,
                    record.command,
                    record.payload_json,
                    record.admission_status,
                    record.rejection_reason,
                    record.launch_status,
                    record.launch_error,
                    record.launched_at,
                    record.pid,
                    record.command_line,
                    record.log_path,
                    record.lifecycle_state,
                    record.completed_at,
                    record.exit_code,
                ),
            )
            conn.commit()

    def update_launch_outcome(
        self,
        request_id: str,
        launch_status: str,
        launch_error: str | None,
        launched_at: str | None,
        pid: int | None,
        command_line: str | None,
        log_path: str | None,
    ) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                UPDATE command_run_log
                SET launch_status = ?, launch_error = ?, launched_at = ?, pid = ?, command_line = ?, log_path = ?
                WHERE request_id = ?
                """,
                (launch_status, launch_error, launched_at, pid, command_line, log_path, request_id),
            )
            conn.commit()

    def update_lifecycle(
        self,
        request_id: str,
        lifecycle_state: str,
        completed_at: str | None,
        exit_code: int | None,
    ) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                UPDATE command_run_log
                SET lifecycle_state = ?, completed_at = ?, exit_code = ?
                WHERE request_id = ?
                """,
                (lifecycle_state, completed_at, exit_code, request_id),
            )
            conn.commit()

    def try_acquire_run_lock(self, request_id: str, acquired_at: str) -> bool:
        with closing(self._connect()) as conn:
            try:
                conn.execute(
                    "INSERT INTO run_lock (lock_name, request_id, acquired_at) VALUES ('active_run', ?, ?)",
                    (request_id, acquired_at),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def release_run_lock(self, request_id: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "DELETE FROM run_lock WHERE lock_name = 'active_run' AND request_id = ?",
                (request_id,),
            )
            conn.commit()

    def get_active_run_id(self) -> str | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT request_id FROM run_lock WHERE lock_name = 'active_run'"
            ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def get_record(self, request_id: str) -> CommandRunRecord | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT
                    request_id,
                    requested_at,
                    operator_id,
                    command_name,
                    payload_json,
                    admission_status,
                    rejection_reason,
                    launch_status,
                    launch_error,
                    launched_at,
                    pid,
                    command_line,
                    log_path,
                    lifecycle_state,
                    completed_at,
                    exit_code
                FROM command_run_log
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
        if not row:
            return None
        return CommandRunRecord(*row)


class CommandRunner:
    """Admission and launch orchestration for allowlisted workflow commands."""

    ALLOWLIST = {"fetch", "load", "benchmark-load"}

    def __init__(
        self,
        repo_root: Path,
        store: CommandAuditStore,
        process_launcher: Callable[..., subprocess.Popen[str]] | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._store = store
        self._logs_dir = repo_root / "logs" / "ops-web"
        self._logs_dir.mkdir(parents=True, exist_ok=True)
        self._process_launcher = process_launcher or subprocess.Popen
        self._active_processes: dict[str, subprocess.Popen[str]] = {}

    def admit_and_launch(self, request: CommandRequest) -> CommandRunRecord:
        self.reconcile_running_processes()
        request_id = str(uuid.uuid4())
        requested_at = utc_now_iso()
        payload_json = self._serialize_payload(request)

        rejected_reason = self._rejection_reason(request)
        if rejected_reason is None:
            lock_ok = self._store.try_acquire_run_lock(request_id=request_id, acquired_at=requested_at)
            if not lock_ok:
                active = self._store.get_active_run_id()
                rejected_reason = f"run request rejected: another workflow run is active ({active})"

        record = CommandRunRecord(
            request_id=request_id,
            requested_at=requested_at,
            operator_id=request.operator_id,
            command=request.command,
            payload_json=payload_json,
            admission_status="rejected" if rejected_reason else "admitted",
            rejection_reason=rejected_reason,
            launch_status="not_started",
            launch_error=None,
            launched_at=None,
            pid=None,
            command_line=None,
            log_path=None,
            lifecycle_state="rejected" if rejected_reason else "running",
            completed_at=requested_at if rejected_reason else None,
            exit_code=None,
        )
        self._store.insert_record(record)

        if rejected_reason:
            return record

        command = self._build_command(request)
        log_path = self._logs_dir / f"{requested_at.replace(':', '').replace('-', '')}_{request_id}.log"
        command_line = " ".join(command)

        try:
            with log_path.open("w", encoding="utf-8") as handle:
                process = self._process_launcher(
                    command,
                    cwd=str(self._repo_root),
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
        except OSError as exc:
            self._store.update_launch_outcome(
                request_id=request_id,
                launch_status="launch_failed",
                launch_error=str(exc),
                launched_at=None,
                pid=None,
                command_line=command_line,
                log_path=log_path.as_posix(),
            )
            self._store.update_lifecycle(
                request_id=request_id,
                lifecycle_state="failed",
                completed_at=utc_now_iso(),
                exit_code=None,
            )
            self._store.release_run_lock(request_id)
            updated = self._store.get_record(request_id)
            if updated is None:
                raise RuntimeError("Failed to persist launch failure record")
            return updated

        self._active_processes[request_id] = process
        launched_at = utc_now_iso()
        self._store.update_launch_outcome(
            request_id=request_id,
            launch_status="launched",
            launch_error=None,
            launched_at=launched_at,
            pid=process.pid,
            command_line=command_line,
            log_path=log_path.as_posix(),
        )
        updated = self._store.get_record(request_id)
        if updated is None:
            raise RuntimeError("Failed to read back launch record")
        return updated

    def reconcile_running_processes(self) -> None:
        """Advance lifecycle state for processes that have exited."""

        finished: list[tuple[str, int]] = []
        for request_id, process in list(self._active_processes.items()):
            exit_code = process.poll()
            if exit_code is None:
                continue
            finished.append((request_id, exit_code))

        for request_id, exit_code in finished:
            lifecycle_state = "completed" if exit_code == 0 else "failed"
            self._store.update_lifecycle(
                request_id=request_id,
                lifecycle_state=lifecycle_state,
                completed_at=utc_now_iso(),
                exit_code=exit_code,
            )
            self._store.release_run_lock(request_id)
            del self._active_processes[request_id]

    def cancel_run(self, request_id: str) -> CommandRunRecord:
        """Cancel the active run and persist lifecycle updates."""

        self.reconcile_running_processes()
        process = self._active_processes.get(request_id)
        if process is None:
            record = self._store.get_record(request_id)
            if record is None:
                raise KeyError(f"run not found: {request_id}")
            return record

        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

        exit_code = process.poll()
        self._store.update_lifecycle(
            request_id=request_id,
            lifecycle_state="canceled",
            completed_at=utc_now_iso(),
            exit_code=exit_code,
        )
        self._store.release_run_lock(request_id)
        del self._active_processes[request_id]
        updated = self._store.get_record(request_id)
        if updated is None:
            raise RuntimeError("Failed to read canceled run record")
        return updated

    def get_run(self, request_id: str) -> CommandRunRecord | None:
        self.reconcile_running_processes()
        return self._store.get_record(request_id)

    def get_active_run(self) -> CommandRunRecord | None:
        self.reconcile_running_processes()
        active_request_id = self._store.get_active_run_id()
        if active_request_id is None:
            return None
        return self._store.get_record(active_request_id)

    def _serialize_payload(self, request: CommandRequest) -> str:
        payload = {
            "command": request.command,
            "operator_id": request.operator_id,
            "armed": request.armed,
            "confirmed": request.confirmed,
            "cycle": request.cycle,
            "tables": list(request.tables),
            "force": request.force,
            "dbt_threads": request.dbt_threads,
        }
        return json.dumps(payload, sort_keys=True)

    def _rejection_reason(self, request: CommandRequest) -> str | None:
        if request.command not in self.ALLOWLIST:
            allowed = ", ".join(sorted(self.ALLOWLIST))
            return f"command is not allowlisted; allowed commands: {allowed}"
        if not request.armed:
            return "run request rejected: app is not armed"
        if not request.confirmed:
            return "run request rejected: confirmation is required"
        if not request.operator_id.strip():
            return "run request rejected: operator_id is required"
        try:
            validate_even_cycle(request.cycle, "cycle")
        except SystemExit as exc:
            return str(exc)
        if request.dbt_threads is not None and request.dbt_threads < 1:
            return f"dbt_threads must be at least 1: {request.dbt_threads}"

        invalid = sorted(set(request.tables) - set(DEFAULT_TABLES))
        if invalid:
            valid = ", ".join(DEFAULT_TABLES)
            return f"Unknown table(s): {', '.join(invalid)}. Valid tables: {valid}"
        return None

    def _build_command(self, request: CommandRequest) -> list[str]:
        if request.command == "fetch":
            command = ["uv", "run", "download", "--cycles", str(request.cycle)]
            if request.tables:
                command.extend(["--tables", *request.tables])
            if request.force:
                command.append("--force")
            return command

        if request.command == "load":
            command = ["uv", "run", "load", "--cycle", str(request.cycle)]
            if request.tables:
                command.extend(["--tables", *request.tables])
            if request.dbt_threads is not None:
                command.extend(["--dbt-threads", str(request.dbt_threads)])
            return command

        command = ["uv", "run", "benchmark-load", "--cycle", str(request.cycle)]
        if request.tables:
            command.extend(["--tables", *request.tables])
        if request.dbt_threads is not None:
            command.extend(["--dbt-threads", str(request.dbt_threads)])
        return command
