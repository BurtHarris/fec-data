"""Cleaner failure report for Airflow upstream metadata scans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


DEFAULT_DAG_ID = "upstream_metadata_scan_v1"


@dataclass(frozen=True)
class AirflowFailureEvent:
    observed_at: str
    dag_run_id: str
    cycle: int
    table_name: str
    zip_name: str
    source_url: str
    fetch_status: str
    http_status: int | None
    error_class: str | None
    error_message: str | None
    map_index: int
    try_number: int


@dataclass(frozen=True)
class AirflowFailureClassSummary:
    error_class: str
    failure_count: int


@dataclass(frozen=True)
class AirflowFailureReport:
    source_label: str
    dag_id: str
    status: str
    message: str
    latest_failed_run_id: str | None = None
    latest_failed_at: str | None = None
    total_attempt_count: int = 0
    failed_attempt_count: int = 0
    failed_asset_count: int = 0
    error_class_summaries: tuple[AirflowFailureClassSummary, ...] = ()
    failed_events: tuple[AirflowFailureEvent, ...] = ()


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def load_airflow_failure_report(db_path: Path, dag_id: str = DEFAULT_DAG_ID) -> AirflowFailureReport:
    source_label = str(db_path)
    if not db_path.exists():
        return AirflowFailureReport(
            source_label=source_label,
            dag_id=dag_id,
            status="unavailable",
            message=f"Failure history database not found: {db_path}",
        )

    conn = _connect(db_path)
    try:
        latest_failed_run = conn.execute(
            """
            SELECT dag_run_id,
                   MAX(observed_at) AS latest_failed_at,
                   COUNT(*) AS failed_attempt_count,
                   COUNT(DISTINCT cycle || ':' || table_name) AS failed_asset_count
            FROM airflow_upstream_observation_history
            WHERE dag_id = ?
              AND fetch_status != 'succeeded'
            GROUP BY dag_run_id
            ORDER BY latest_failed_at DESC, dag_run_id DESC
            LIMIT 1
            """,
            (dag_id,),
        ).fetchone()

        if latest_failed_run is None:
            return AirflowFailureReport(
                source_label=source_label,
                dag_id=dag_id,
                status="clean",
                message="No failed upstream observations are recorded for this DAG.",
            )

        dag_run_id = str(latest_failed_run["dag_run_id"])
        failed_events = conn.execute(
            """
            SELECT observed_at,
                   dag_run_id,
                   cycle,
                   table_name,
                   zip_name,
                   source_url,
                   fetch_status,
                   http_status,
                   error_class,
                   error_message,
                   map_index,
                   try_number
            FROM airflow_upstream_observation_history
            WHERE dag_id = ?
              AND dag_run_id = ?
              AND fetch_status != 'succeeded'
            ORDER BY map_index, try_number, observation_id
            """,
            (dag_id, dag_run_id),
        ).fetchall()

        total_attempt_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM airflow_upstream_observation_history
            WHERE dag_id = ?
              AND dag_run_id = ?
            """,
            (dag_id, dag_run_id),
        ).fetchone()[0]

        error_class_summaries = conn.execute(
            """
            SELECT COALESCE(error_class, 'unknown') AS error_class,
                   COUNT(*) AS failure_count
            FROM airflow_upstream_observation_history
            WHERE dag_id = ?
              AND dag_run_id = ?
              AND fetch_status != 'succeeded'
            GROUP BY COALESCE(error_class, 'unknown')
            ORDER BY failure_count DESC, error_class ASC
            """,
            (dag_id, dag_run_id),
        ).fetchall()

        return AirflowFailureReport(
            source_label=source_label,
            dag_id=dag_id,
            status="ready",
            message="Latest failed observation batch with grouped errors and source URLs.",
            latest_failed_run_id=dag_run_id,
            latest_failed_at=str(latest_failed_run["latest_failed_at"]),
            total_attempt_count=int(total_attempt_count),
            failed_attempt_count=int(latest_failed_run["failed_attempt_count"]),
            failed_asset_count=int(latest_failed_run["failed_asset_count"]),
            error_class_summaries=tuple(
                AirflowFailureClassSummary(
                    error_class=str(row["error_class"]),
                    failure_count=int(row["failure_count"]),
                )
                for row in error_class_summaries
            ),
            failed_events=tuple(
                AirflowFailureEvent(
                    observed_at=str(row["observed_at"]),
                    dag_run_id=str(row["dag_run_id"]),
                    cycle=int(row["cycle"]),
                    table_name=str(row["table_name"]),
                    zip_name=str(row["zip_name"]),
                    source_url=str(row["source_url"]),
                    fetch_status=str(row["fetch_status"]),
                    http_status=int(row["http_status"]) if row["http_status"] is not None else None,
                    error_class=str(row["error_class"]) if row["error_class"] is not None else None,
                    error_message=str(row["error_message"]) if row["error_message"] is not None else None,
                    map_index=int(row["map_index"]),
                    try_number=int(row["try_number"]),
                )
                for row in failed_events
            ),
        )
    finally:
        conn.close()
