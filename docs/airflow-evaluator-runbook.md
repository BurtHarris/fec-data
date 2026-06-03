# Airflow Evaluator First Runbook

This runbook is for the Airflow-first evaluation branch and assumes a developer who is new to Airflow.

## Windows Note

Native Windows can run the lightweight in-process prototype checks such as `dag.test()` and the smoke test suite, but the full Airflow scheduler and webserver path is not reliable here. In this environment, the CLI webserver and scheduler commands fail before startup because Airflow's daemon path imports POSIX-only modules.

Use this split:

- Native Windows: validate prototype behavior with the smoke tests and `dag.test()`.
- WSL2 or Linux container: use the full Airflow UI and scheduler/webserver flow.

## What This Runbook Covers

- Start Airflow on localhost.
- Trigger one manual run of `upstream_metadata_scan_v1`.
- Verify task outcomes in Airflow UI.
- Optionally inspect SQL evidence in `db/fec-observations.sqlite`.
- Capture one `Single Evidence Note`.

## Branch Defaults

- DAG ID: `upstream_metadata_scan_v1`
- Scheduling: disabled (manual triggers only)
- Timezone: UTC
- Catchup: disabled
- Max active runs: 1
- Domain observation DB: `db/fec-observations.sqlite`
- Airflow runtime DB target: `db/airflow-runtime.sqlite`

## 1. Start Airflow (Localhost Only)

This section is intended for WSL2 or another Linux environment. Do not expect it to work on native Windows for this prototype.

From repo root in Linux/WSL:

```bash
bash scripts/airflow-setup.sh
```

This bootstraps a dedicated venv at `.venv-airflow`, installs Airflow with Linux constraints, configures `AIRFLOW_HOME`, and initializes `db/airflow-runtime.sqlite`.

Start scheduler and webserver in separate terminals:

```bash
bash scripts/airflow-run.sh scheduler
```

```bash
bash scripts/airflow-run.sh webserver
```

Open `http://127.0.0.1:8080`.

If you are staying on native Windows, skip the web UI steps and use the smoke tests plus `dag.test()` instead.

## 2. Trigger One Manual DAG Run

For native Windows prototype validation, use `dag.test()` rather than the web UI trigger path.

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

```bash
duckdb -c "ATTACH 'db/fec-observations.sqlite' AS obs (TYPE SQLITE); SELECT observed_at, cycle, table_name, fetch_status, http_status, change_detected, dag_run_id, map_index, try_number FROM obs.airflow_upstream_observation_history ORDER BY observation_id DESC LIMIT 20;"
```

```bash
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

## Schedule Mode

This branch currently runs in manual-trigger-only mode for evaluation:

- File: `dags/upstream_metadata_scan_v1.py`
- Setting: `MANUAL_TRIGGER_ONLY_SCHEDULE = None`

To re-enable periodic scheduling later, set that value to a timetable interval (for example `timedelta(hours=6)`).
