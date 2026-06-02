import sqlite3
import tempfile
import unittest
import os
from datetime import datetime, timezone
from importlib import import_module, reload
from pathlib import Path
from unittest.mock import patch

from pipeline.airflow_observation_store import (
    EXPECTED_SCHEMA_VERSION,
    MAX_ERROR_MESSAGE_LEN,
    ObservationRecord,
    ensure_domain_schema,
    insert_observation,
    upsert_snapshot_from_run,
)
from pipeline.airflow_scan_config import validate_manual_overrides


class DomainObservationStoreSmokeTests(unittest.TestCase):
    def test_bootstrap_and_first_successful_observation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "fec-observations.sqlite"
            ensure_domain_schema(db_path)

            result = insert_observation(
                db_path,
                ObservationRecord(
                    cycle=2026,
                    table_name="cm",
                    zip_name="cm26.zip",
                    source_url="https://www.fec.gov/files/bulk-downloads/2026/cm26.zip",
                    fetch_status="succeeded",
                    http_status=200,
                    response_date="Mon, 02 Jun 2026 00:00:00 GMT",
                    last_modified="Mon, 02 Jun 2026 00:00:00 GMT",
                    etag="etag-1",
                    content_length=101,
                    error_class=None,
                    error_message=None,
                    dag_id="upstream_metadata_scan_v1",
                    dag_run_id="manual__1",
                    task_id="observe_artifact",
                    map_index=0,
                    try_number=1,
                ),
            )

            conn = sqlite3.connect(db_path)
            try:
                schema_version = conn.execute("SELECT version FROM airflow_domain_schema_version").fetchone()[0]
                row_count = conn.execute("SELECT COUNT(*) FROM airflow_upstream_observation_history").fetchone()[0]
            finally:
                conn.close()

        self.assertEqual(schema_version, EXPECTED_SCHEMA_VERSION)
        self.assertEqual(row_count, 1)
        self.assertFalse(result.change_detected)

    def test_change_detection_and_snapshot_upsert(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "fec-observations.sqlite"
            ensure_domain_schema(db_path)

            first = insert_observation(
                db_path,
                ObservationRecord(
                    cycle=2026,
                    table_name="cn",
                    zip_name="cn26.zip",
                    source_url="https://www.fec.gov/files/bulk-downloads/2026/cn26.zip",
                    fetch_status="succeeded",
                    http_status=200,
                    response_date="Mon, 02 Jun 2026 00:00:00 GMT",
                    last_modified="Mon, 02 Jun 2026 00:00:00 GMT",
                    etag="etag-1",
                    content_length=201,
                    error_class=None,
                    error_message=None,
                    dag_id="upstream_metadata_scan_v1",
                    dag_run_id="manual__1",
                    task_id="observe_artifact",
                    map_index=0,
                    try_number=1,
                ),
            )
            second = insert_observation(
                db_path,
                ObservationRecord(
                    cycle=2026,
                    table_name="cn",
                    zip_name="cn26.zip",
                    source_url="https://www.fec.gov/files/bulk-downloads/2026/cn26.zip",
                    fetch_status="succeeded",
                    http_status=200,
                    response_date="Mon, 02 Jun 2026 06:00:00 GMT",
                    last_modified="Mon, 02 Jun 2026 06:00:00 GMT",
                    etag="etag-2",
                    content_length=202,
                    error_class=None,
                    error_message=None,
                    dag_id="upstream_metadata_scan_v1",
                    dag_run_id="manual__2",
                    task_id="observe_artifact",
                    map_index=0,
                    try_number=1,
                ),
            )

            updated = upsert_snapshot_from_run(db_path, dag_id="upstream_metadata_scan_v1", dag_run_id="manual__2")

            conn = sqlite3.connect(db_path)
            try:
                snapshot = conn.execute(
                    "SELECT etag, content_length, change_detected, dag_run_id FROM airflow_upstream_snapshot WHERE cycle=2026 AND table_name='cn'"
                ).fetchone()
            finally:
                conn.close()

        self.assertFalse(first.change_detected)
        self.assertTrue(second.change_detected)
        self.assertEqual(updated, 1)
        self.assertEqual(snapshot, ("etag-2", 202, 1, "manual__2"))

    def test_failed_observation_records_unknown_change_and_compact_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "fec-observations.sqlite"
            ensure_domain_schema(db_path)

            long_message = "x" * (MAX_ERROR_MESSAGE_LEN + 80)
            result = insert_observation(
                db_path,
                ObservationRecord(
                    cycle=2026,
                    table_name="weball",
                    zip_name="weball26.zip",
                    source_url="https://www.fec.gov/files/bulk-downloads/2026/weball26.zip",
                    fetch_status="failed",
                    http_status=503,
                    response_date=None,
                    last_modified=None,
                    etag=None,
                    content_length=None,
                    error_class="HTTPError",
                    error_message=long_message,
                    dag_id="upstream_metadata_scan_v1",
                    dag_run_id="manual__3",
                    task_id="observe_artifact",
                    map_index=1,
                    try_number=2,
                ),
            )

            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "SELECT change_detected, LENGTH(error_message) FROM airflow_upstream_observation_history ORDER BY observation_id DESC LIMIT 1"
                ).fetchone()
            finally:
                conn.close()

        self.assertIsNone(result.change_detected)
        self.assertEqual(row[0], None)
        self.assertEqual(row[1], MAX_ERROR_MESSAGE_LEN)


class AirflowDagSmokeTests(unittest.TestCase):
    def test_manual_override_validation_rejects_bad_cycles(self) -> None:
        with self.assertRaisesRegex(ValueError, "even integer years"):
            validate_manual_overrides([2025], None)

    def test_manual_override_validation_rejects_bad_tables(self) -> None:
        with self.assertRaisesRegex(ValueError, "entries must be strings"):
            validate_manual_overrides([2026], ["cm", 1])

    def test_dag_loads_with_expected_defaults(self) -> None:
        try:
            from dags import upstream_metadata_scan_v1 as dag_module
        except ModuleNotFoundError as exc:
            self.skipTest(f"Airflow not installed in this environment: {exc}")

        dag = dag_module.upstream_metadata_scan_v1()

        self.assertEqual(dag.dag_id, "upstream_metadata_scan_v1")
        self.assertFalse(dag.catchup)
        self.assertEqual(dag.max_active_runs, 1)

        task_ids = set(dag.task_ids)
        self.assertEqual(
            task_ids,
            {"build_scan_targets", "schema_gate", "observe_artifact", "update_snapshot", "enforce_run_outcome"},
        )

    def test_dag_test_executes_tiny_scope_and_persists_observation(self) -> None:
        try:
            from airflow.utils.db import initdb
        except ModuleNotFoundError as exc:
            self.skipTest(f"Airflow not installed in this environment: {exc}")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            airflow_home = temp_root / "airflow-home"
            airflow_home.mkdir(parents=True, exist_ok=True)
            runtime_db = temp_root / "airflow-runtime.sqlite"
            observation_db = temp_root / "fec-observations.sqlite"

            env_updates = {
                "AIRFLOW_HOME": str(airflow_home),
                "AIRFLOW__CORE__DAGS_FOLDER": str(Path(__file__).resolve().parents[1] / "dags"),
                "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN": f"sqlite:///{runtime_db.as_posix()}",
                "AIRFLOW__CORE__LOAD_EXAMPLES": "False",
                "AIRFLOW__CORE__EXECUTOR": "SequentialExecutor",
                "AIRFLOW__CORE__UNIT_TEST_MODE": "True",
            }

            with patch.dict(os.environ, env_updates, clear=False):
                dag_module = reload(import_module("dags.upstream_metadata_scan_v1"))
                initdb()

                with patch.object(
                    dag_module,
                    "DOMAIN_OBSERVATION_DB",
                    observation_db,
                ), patch.object(
                    dag_module,
                    "_head_request",
                    return_value=(
                        200,
                        {
                            "Date": "Mon, 02 Jun 2026 00:00:00 GMT",
                            "Last-Modified": "Mon, 02 Jun 2026 00:00:00 GMT",
                            "ETag": "etag-smoke",
                            "Content-Length": "321",
                        },
                    ),
                ):
                    dag = dag_module.upstream_metadata_scan_v1()
                    dag.test(
                        execution_date=datetime(2026, 6, 2, tzinfo=timezone.utc),
                        run_conf={"cycles": [2026], "tables": ["cm"]},
                    )

            conn = sqlite3.connect(observation_db)
            try:
                row = conn.execute(
                    "SELECT cycle, table_name, fetch_status, etag FROM airflow_upstream_observation_history"
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(row, (2026, "cm", "succeeded", "etag-smoke"))


if __name__ == "__main__":
    unittest.main()
