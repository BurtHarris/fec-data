"""Allowlisted command runner for operations web app requests."""

from __future__ import annotations

import json
import sqlite3
import subprocess
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

    run_number: int | None
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
            if self._command_run_log_needs_migration(conn):
                self._migrate_legacy_schema(conn)
            self._create_tables(conn)
            self._ensure_column(conn, "command_run_log", "lifecycle_state", "TEXT NOT NULL DEFAULT 'rejected'")
            self._ensure_column(conn, "command_run_log", "completed_at", "TEXT")
            self._ensure_column(conn, "command_run_log", "exit_code", "INTEGER")
            conn.commit()

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS command_run_log (
                run_number INTEGER PRIMARY KEY AUTOINCREMENT,
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
                run_number INTEGER NOT NULL,
                acquired_at TEXT NOT NULL
            )
            """
        )

    def _command_run_log_needs_migration(self, conn: sqlite3.Connection) -> bool:
        rows = conn.execute("PRAGMA table_info(command_run_log)").fetchall()
        if not rows:
            return False
        names = {row[1] for row in rows}
        return "run_number" not in names or "request_id" in names

    def _migrate_legacy_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE command_run_log RENAME TO command_run_log_legacy")
        conn.execute("DROP TABLE IF EXISTS run_lock")
        self._create_tables(conn)
        conn.execute(
            """
            INSERT INTO command_run_log (
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
            )
            SELECT
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
            FROM command_run_log_legacy
            ORDER BY rowid
            """
        )
        conn.execute("DROP TABLE command_run_log_legacy")

    def _ensure_column(self, conn: sqlite3.Connection, table_name: str, column_name: str, ddl: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        names = {row[1] for row in rows}
        if column_name in names:
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")

    def insert_record(self, record: CommandRunRecord) -> int:
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                INSERT INTO command_run_log (
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
            return int(cursor.lastrowid)

    def update_launch_outcome(
        self,
        run_number: int,
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
                WHERE run_number = ?
                """,
                (launch_status, launch_error, launched_at, pid, command_line, log_path, run_number),
            )
            conn.commit()

    def update_rejection(self, run_number: int, rejection_reason: str, completed_at: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                UPDATE command_run_log
                SET admission_status = 'rejected',
                    rejection_reason = ?,
                    launch_status = 'not_started',
                    lifecycle_state = 'rejected',
                    completed_at = ?
                WHERE run_number = ?
                """,
                (rejection_reason, completed_at, run_number),
            )
            conn.commit()

    def update_lifecycle(
        self,
        run_number: int,
        lifecycle_state: str,
        completed_at: str | None,
        exit_code: int | None,
    ) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                UPDATE command_run_log
                SET lifecycle_state = ?, completed_at = ?, exit_code = ?
                WHERE run_number = ?
                """,
                (lifecycle_state, completed_at, exit_code, run_number),
            )
            conn.commit()

    def try_acquire_run_lock(self, run_number: int, acquired_at: str) -> bool:
        with closing(self._connect()) as conn:
            try:
                conn.execute(
                    "INSERT INTO run_lock (lock_name, run_number, acquired_at) VALUES ('active_run', ?, ?)",
                    (run_number, acquired_at),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def release_run_lock(self, run_number: int) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "DELETE FROM run_lock WHERE lock_name = 'active_run' AND run_number = ?",
                (run_number,),
            )
            conn.commit()

    def get_active_run_number(self) -> int | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT run_number FROM run_lock WHERE lock_name = 'active_run'"
            ).fetchone()
        if row is None:
            return None
        return int(row[0])

    def get_record(self, run_number: int) -> CommandRunRecord | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT
                    run_number,
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
                WHERE run_number = ?
                """,
                (run_number,),
            ).fetchone()
        if not row:
            return None
        return CommandRunRecord(*row)

    def list_recent_records(self, limit: int = 25) -> list[CommandRunRecord]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT
                    run_number,
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
                ORDER BY run_number DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [CommandRunRecord(*row) for row in rows]


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
        self._active_processes: dict[int, subprocess.Popen[str]] = {}

    def admit_and_launch(self, request: CommandRequest) -> CommandRunRecord:
        self.reconcile_running_processes()
        requested_at = utc_now_iso()
        payload_json = self._serialize_payload(request)

        rejected_reason = self._rejection_reason(request)
        record = CommandRunRecord(
            run_number=None,
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
        run_number = self._store.insert_record(record)

        if rejected_reason:
            updated = self._store.get_record(run_number)
            if updated is None:
                raise RuntimeError("Failed to read back rejected run record")
            return updated

        lock_ok = self._store.try_acquire_run_lock(run_number=run_number, acquired_at=requested_at)
        if not lock_ok:
            active = self._store.get_active_run_number()
            rejection_reason = f"run request rejected: another workflow run is active ({active})"
            self._store.update_rejection(run_number, rejection_reason, requested_at)
            updated = self._store.get_record(run_number)
            if updated is None:
                raise RuntimeError("Failed to read back lock-rejected run record")
            return updated

        command = self._build_command(request)
        log_path = self._logs_dir / f"{requested_at.replace(':', '').replace('-', '')}_run-{run_number}.log"
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
                run_number=run_number,
                launch_status="launch_failed",
                launch_error=str(exc),
                launched_at=None,
                pid=None,
                command_line=command_line,
                log_path=log_path.as_posix(),
            )
            self._store.update_lifecycle(
                run_number=run_number,
                lifecycle_state="failed",
                completed_at=utc_now_iso(),
                exit_code=None,
            )
            self._store.release_run_lock(run_number)
            updated = self._store.get_record(run_number)
            if updated is None:
                raise RuntimeError("Failed to persist launch failure record")
            return updated

        self._active_processes[run_number] = process
        launched_at = utc_now_iso()
        self._store.update_launch_outcome(
            run_number=run_number,
            launch_status="launched",
            launch_error=None,
            launched_at=launched_at,
            pid=process.pid,
            command_line=command_line,
            log_path=log_path.as_posix(),
        )
        updated = self._store.get_record(run_number)
        if updated is None:
            raise RuntimeError("Failed to read back launch record")
        return updated

    def reconcile_running_processes(self) -> None:
        """Advance lifecycle state for processes that have exited."""

        finished: list[tuple[int, int]] = []
        for run_number, process in list(self._active_processes.items()):
            exit_code = process.poll()
            if exit_code is None:
                continue
            finished.append((run_number, exit_code))

        for run_number, exit_code in finished:
            lifecycle_state = "completed" if exit_code == 0 else "failed"
            self._store.update_lifecycle(
                run_number=run_number,
                lifecycle_state=lifecycle_state,
                completed_at=utc_now_iso(),
                exit_code=exit_code,
            )
            self._store.release_run_lock(run_number)
            del self._active_processes[run_number]

    def cancel_run(self, run_number: int) -> CommandRunRecord:
        """Cancel the active run and persist lifecycle updates."""

        self.reconcile_running_processes()
        process = self._active_processes.get(run_number)
        if process is None:
            record = self._store.get_record(run_number)
            if record is None:
                raise KeyError(f"run not found: {run_number}")
            return record

        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

        exit_code = process.poll()
        self._store.update_lifecycle(
            run_number=run_number,
            lifecycle_state="canceled",
            completed_at=utc_now_iso(),
            exit_code=exit_code,
        )
        self._store.release_run_lock(run_number)
        del self._active_processes[run_number]
        updated = self._store.get_record(run_number)
        if updated is None:
            raise RuntimeError("Failed to read canceled run record")
        return updated

    def get_run(self, run_number: int) -> CommandRunRecord | None:
        self.reconcile_running_processes()
        return self._store.get_record(run_number)

    def get_active_run(self) -> CommandRunRecord | None:
        self.reconcile_running_processes()
        active_run_number = self._store.get_active_run_number()
        if active_run_number is None:
            return None
        return self._store.get_record(active_run_number)

    def list_recent_runs(self, limit: int = 25) -> list[CommandRunRecord]:
        self.reconcile_running_processes()
        return self._store.list_recent_records(limit=limit)

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
