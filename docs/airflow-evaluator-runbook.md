# Airflow Evaluator First Runbook

This runbook is for the Airflow-first evaluation branch and assumes a developer who is new to Airflow.

## What This Runbook Covers

- Start Airflow on localhost.
- Trigger one manual run of `upstream_metadata_scan_v1`.
- Verify task outcomes in Airflow UI.
- Optionally inspect SQL evidence in `db/fec-observations.sqlite`.
- Capture one `Single Evidence Note`.

## Branch Defaults

- DAG ID: `upstream_metadata_scan_v1`
- Default cadence: every 6 hours
- Timezone: UTC
- Catchup: disabled
- Max active runs: 1
- Domain observation DB: `db/fec-observations.sqlite`
- Airflow runtime DB target: `db/airflow-runtime.sqlite`

## 1. Start Airflow (Localhost Only)

From repo root:

```powershell
$env:AIRFLOW_HOME = (Resolve-Path .).Path + "\\tmp\\airflow-home"
$env:AIRFLOW__CORE__DAGS_FOLDER = (Resolve-Path .\\dags).Path
$env:AIRFLOW__DATABASE__SQL_ALCHEMY_CONN = "sqlite:///" + ((Resolve-Path .\\db).Path -replace "\\","/") + "/airflow-runtime.sqlite"
$env:AIRFLOW__WEBSERVER__WEB_SERVER_HOST = "127.0.0.1"

airflow db migrate
airflow users create --username admin --firstname Local --lastname Admin --role Admin --email local@example.com --password admin
```

Start scheduler and webserver in separate terminals:

```powershell
airflow scheduler
```

```powershell
airflow webserver --port 8080
```

Open `http://127.0.0.1:8080`.

## 2. Trigger One Manual DAG Run

In Airflow UI, open DAG `upstream_metadata_scan_v1` and trigger with config.

Suggested small-scope config:

```json
{
  "cycles": [2026],
  "tables": ["cm", "cn"]
}
```

Allowed manual overrides are limited to `cycles` and `tables`.

## 3. Verify Airflow UI Outcomes

- Confirm mapped `observe_artifact` task instances were created.
- Confirm `update_snapshot` ran (trigger rule: all_done).
- Confirm final DAG state reflects failures if any mapped checks exhausted retries.

## 4. Optional SQL Verification

Inspect data in the domain observation DB:

```powershell
duckdb -c "ATTACH 'db/fec-observations.sqlite' AS obs (TYPE SQLITE); SELECT observed_at, cycle, table_name, fetch_status, http_status, change_detected, dag_run_id, map_index, try_number FROM obs.airflow_upstream_observation_history ORDER BY observation_id DESC LIMIT 20;"
```

```powershell
duckdb -c "ATTACH 'db/fec-observations.sqlite' AS obs (TYPE SQLITE); SELECT cycle, table_name, fetch_status, last_observed_at, updated_at, dag_run_id FROM obs.airflow_upstream_snapshot ORDER BY cycle DESC, table_name ASC;"
```

## 5. Record a Single Evidence Note

Capture one short note for the run:

- One Airflow UI observation.
- One matching SQL observation.
- One sentence linking them.

Example template:

```text
Airflow UI: map index 1 retried once then succeeded.
SQL: observation history shows try_number=2 for cycle=2026, table=cn and snapshot updated in same dag_run_id.
Conclusion: mapped retries and snapshot reducer behaved as expected for partial transient failure.
```

## Single-Step Cadence Edit

To change cadence quickly, edit one setting in the DAG file:

- File: `dags/upstream_metadata_scan_v1.py`
- Setting: `DEFAULT_SCAN_INTERVAL = timedelta(hours=6)`

No other file is required for cadence changes in this branch.
