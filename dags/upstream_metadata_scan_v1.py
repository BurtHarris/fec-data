"""Airflow-first DAG for scanning upstream FEC artifact metadata via HEAD requests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException
from airflow.operators.python import get_current_context
from airflow.utils.trigger_rule import TriggerRule

from pipeline.airflow_observation_store import (
    DomainSchemaVersionError,
    ObservationRecord,
    ensure_domain_schema,
    insert_observation,
    upsert_snapshot_from_run,
)
from pipeline.airflow_scan_config import resolve_scan_targets, validate_manual_overrides
from pipeline.data_scope import CANONICAL_DATA_SCOPE_PATH


DAG_ID = "upstream_metadata_scan_v1"
DEFAULT_DATA_SCOPE_CONFIG = CANONICAL_DATA_SCOPE_PATH
DOMAIN_OBSERVATION_DB = Path("db") / "fec-observations.sqlite"
MANUAL_TRIGGER_ONLY_SCHEDULE = None
DEFAULT_RETRIES = 2
DEFAULT_RETRY_DELAY = timedelta(minutes=2)
DEFAULT_USER_AGENT = "moneytrail-airflow-scan/0.1"
FIXED_START_DATE_UTC = datetime(2026, 6, 1, tzinfo=timezone.utc)


def repo_root() -> Path:
    return REPO_ROOT


def _head_request(url: str) -> tuple[int, dict[str, str]]:
    request = Request(url=url, headers={"User-Agent": DEFAULT_USER_AGENT}, method="HEAD")
    with urlopen(request, timeout=60) as response:
        status = int(getattr(response, "status", 200))
        headers = {str(k): str(v) for k, v in response.headers.items()}
        return status, headers


@dag(
    dag_id=DAG_ID,
    schedule=MANUAL_TRIGGER_ONLY_SCHEDULE,
    start_date=FIXED_START_DATE_UTC,
    catchup=False,
    max_active_runs=1,
    tags=["airflow-first", "upstream", "metadata-scan"],
    default_args={"retries": DEFAULT_RETRIES, "retry_delay": DEFAULT_RETRY_DELAY},
)
def upstream_metadata_scan_v1() -> None:
    @task
    def build_scan_targets() -> list[dict[str, object]]:
        dag_run = get_current_context()["dag_run"]
        conf = dag_run.conf or {}

        cycles_override = conf.get("cycles")
        tables_override = conf.get("tables")
        try:
            validated_cycles, validated_tables = validate_manual_overrides(cycles_override, tables_override)
        except ValueError as exc:
            raise AirflowFailException(str(exc)) from exc

        config_path = repo_root() / DEFAULT_DATA_SCOPE_CONFIG
        targets = resolve_scan_targets(
            config_path,
            repo_root=repo_root(),
            cycles_override=validated_cycles,
            tables_override=validated_tables,
        )
        if not targets:
            raise AirflowFailException("No scan targets resolved from configuration")
        return targets

    @task
    def schema_gate() -> str:
        db_path = repo_root() / DOMAIN_OBSERVATION_DB
        try:
            ensure_domain_schema(db_path)
        except DomainSchemaVersionError as exc:
            raise AirflowFailException(str(exc)) from exc
        return str(db_path)

    @task
    def observe_artifact(target: dict[str, object], domain_db_path: str) -> dict[str, object]:
        context = get_current_context()
        task_instance = context["ti"]

        cycle = int(target["cycle"])
        table_name = str(target["table_name"])
        zip_name = str(target["zip_name"])
        source_url = str(target["source_url"])

        fetch_status = "succeeded"
        http_status: int | None = None
        response_date: str | None = None
        last_modified: str | None = None
        etag: str | None = None
        content_length: int | None = None
        error_class: str | None = None
        error_message: str | None = None

        try:
            http_status, headers = _head_request(source_url)
            response_date = headers.get("Date")
            last_modified = headers.get("Last-Modified")
            etag = headers.get("ETag")
            content_length_raw = headers.get("Content-Length")
            content_length = int(content_length_raw) if content_length_raw and content_length_raw.isdigit() else None
        except HTTPError as exc:
            fetch_status = "failed"
            http_status = int(exc.code)
            error_class = type(exc).__name__
            error_message = str(exc)
        except URLError as exc:
            fetch_status = "failed"
            error_class = type(exc).__name__
            error_message = str(exc.reason)
        except OSError as exc:
            fetch_status = "failed"
            error_class = type(exc).__name__
            error_message = str(exc)

        result = insert_observation(
            Path(domain_db_path),
            ObservationRecord(
                cycle=cycle,
                table_name=table_name,
                zip_name=zip_name,
                source_url=source_url,
                fetch_status=fetch_status,
                http_status=http_status,
                response_date=response_date,
                last_modified=last_modified,
                etag=etag,
                content_length=content_length,
                error_class=error_class,
                error_message=error_message,
                dag_id=context["dag"].dag_id,
                dag_run_id=context["dag_run"].run_id,
                task_id=task_instance.task_id,
                map_index=int(task_instance.map_index),
                try_number=int(task_instance.try_number),
            ),
        )

        payload = {
            "cycle": cycle,
            "table_name": table_name,
            "observation_id": result.observation_id,
            "change_detected": result.change_detected,
            "fetch_status": fetch_status,
            "http_status": http_status,
        }

        if fetch_status != "succeeded":
            raise AirflowFailException(
                f"HEAD check failed for cycle={cycle} table={table_name} url={source_url} "
                f"status={http_status} error={error_class}: {error_message}"
            )

        return payload

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def update_snapshot(domain_db_path: str) -> int:
        context = get_current_context()
        return upsert_snapshot_from_run(
            Path(domain_db_path),
            dag_id=context["dag"].dag_id,
            dag_run_id=context["dag_run"].run_id,
        )

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def enforce_run_outcome() -> None:
        context = get_current_context()
        dag_run = context["dag_run"]
        task_instances = dag_run.get_task_instances()
        failed_mapped = [
            ti
            for ti in task_instances
            if ti.task_id == "observe_artifact" and ti.state in {"failed", "upstream_failed"}
        ]
        if failed_mapped:
            sample = failed_mapped[0]
            raise AirflowFailException(
                "One or more mapped artifact checks failed after retries. "
                f"sample_map_index={sample.map_index}"
            )

    targets = build_scan_targets()
    db_path = schema_gate()
    mapped = observe_artifact.partial(domain_db_path=db_path).expand(target=targets)
    snapshot = update_snapshot(db_path)
    mapped >> snapshot
    snapshot >> enforce_run_outcome()


upstream_metadata_scan_v1()
