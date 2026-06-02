# MoneyTrail Data Operations Context

This context defines the shared language for operating the internal MoneyTrail data engineering workflow. It exists to keep planning, UI language, and runbook decisions consistent.

## Language

**Data Scope**:
The configured set of election cycles and table groups that determine what data is eligible for fetch and load.
_Avoid_: coverage file, table toggle list

**Data Scope Config**:
The canonical YAML document that stores Data Scope and is edited by operators through the app.
_Avoid_: legacy coverage yaml, random config

**Canonical Config Path**:
The single authoritative location for Data Scope Config at `config/data_scope.yml`, with no legacy fallback paths.
_Avoid_: dual config sources, transition aliasing

**Config Snapshot**:
The immutable copy of Data Scope Config captured when a Workflow Run starts and used for that run end-to-end.
_Avoid_: live mutable config, mid-run toggle

**Workflow Run**:
A single execution of an ETL operation initiated by an operator, such as fetch or load, with status and logs.
_Avoid_: job click, script fire

**Airflow-First Evaluation Branch**:
The branch mode for prototype evaluation where Airflow-native terminology and orchestration behavior are the primary reference model.
_Avoid_: PowerShell-first compatibility mode, dual-control vocabulary

**DAG Run**:
The canonical run term in the Airflow-First Evaluation Branch for one scheduled or manually triggered execution of a DAG.
_Avoid_: workflow run alias in this branch, script run

**Mapped Artifact Check Task**:
An Airflow task instance created per cycle and table artifact so each upstream check has isolated retry, state, and logs in the DAG Run.
_Avoid_: monolithic loop task, hidden per-artifact state

**Observation-First Write Path**:
The persistence model where each Mapped Artifact Check Task appends its own Upstream Observation History row directly.
_Avoid_: reducer-only history write, delayed per-artifact persistence

**Snapshot Reducer Task**:
The fan-in task that updates Upstream Snapshot state from completed observation rows after mapped checks finish.
_Avoid_: per-task snapshot overwrite, distributed latest-state writes

**Partial-Progress Reducer Policy**:
The policy that runs the Snapshot Reducer Task to persist successful observation outcomes even when some mapped checks fail.
_Avoid_: all-or-nothing reduce, discard-on-partial-failure

**Failing-Visible DAG Outcome**:
The policy that marks the overall DAG Run as failed when any mapped artifact check remains failed after retries, even if partial progress was persisted.
_Avoid_: silent partial success, green DAG with hidden failures

**Per-Attempt Observation Grain**:
The history-grain rule that records one Upstream Observation History row for each mapped task attempt, including retries.
_Avoid_: per-run collapse, retry-overwrite history

**Airflow Attempt Identity**:
The required identity tuple (`dag_id`, `dag_run_id`, `task_id`, `map_index`, `try_number`) persisted on each observation row to trace SQL evidence back to an exact Airflow task attempt.
_Avoid_: opaque task provenance, inferred run linkage

**Command Runner**:
The backend component that executes allowlisted workflow commands and streams logs/status to the Operations Dashboard.
_Avoid_: shell passthrough, arbitrary command exec

**Run Lock**:
The rule that only one Workflow Run may be active at a time, while internal command-level parallelism (such as dbt threads and parallel fetch workers) is still allowed inside that run.
_Avoid_: unlimited concurrent runs, fully serialized dbt

**Run History**:
The ordered record of completed and failed workflow runs used for audit and troubleshooting.
_Avoid_: console scrollback, ad hoc notes

**Upstream Change**:
A detectable update in FEC-hosted bulk artifacts, observed through metadata shifts like timestamp, tag, or size.
_Avoid_: random refresh, file drift

**Upstream Change Pattern**:
The derived cadence and burst behavior of Upstream Changes over time, computed from fetch metadata history per cycle and table.
_Avoid_: one-off update guess, ad hoc eyeballing

**Operations Dashboard**:
The internal web interface for monitoring scope, starting runs, and reviewing health and history.
_Avoid_: website, portal page

**Operations Web App**:
The active localhost application implemented in `src/pipeline/web` and launched through a pipeline CLI entrypoint.
_Avoid_: separate frontend repo, static-only artifact

**Local-Trusted Mode**:
The v1 access model where the app runs on localhost for trusted operators and uses confirmations before command execution.
_Avoid_: internet-exposed admin, unauthenticated remote access

**Airflow Orchestration Layer**:
The scheduling and dependency control layer that triggers pipeline work while delegating domain execution to existing MoneyTrail modules.
_Avoid_: replacement pipeline engine, direct domain rewrite

**Domain Metadata Store**:
The SQLite tables that capture fetch status and history for Upstream Change analysis and dashboard visibility.
_Avoid_: Airflow metadata DB, scheduler internals

**Metadata Scan Run**:
A scheduled observation pass that issues HEAD requests to source artifacts and records source metadata without downloading ZIP bytes.
_Avoid_: fetch run, download run

**Fetch Run**:
A transfer pass that performs conditional GET requests and writes ZIP artifacts to local storage.
_Avoid_: metadata-only scan, HEAD-only check

**Scan-Fetch Split**:
The operating model where Metadata Scan Runs and Fetch Runs are separate workflows that share the same Domain Metadata Store.
_Avoid_: single blended run, implicit download-on-scan

**Upstream Snapshot**:
The current-state table that stores the latest observed source metadata per cycle and table.
_Avoid_: raw history log, latest guess

**Upstream Observation History**:
The append-only table that stores one row per metadata scan attempt for longitudinal analysis.
_Avoid_: mutable status row, overwritten timeline

**Change Detection Rule**:
The rule that flags an Upstream Change by comparing each successful metadata observation to the prior successful observation for the same cycle and table across ETag, Last-Modified, and Content-Length.
_Avoid_: download-trigger heuristic, status-only guess

**Unknown Change State**:
The null change state used for failed or non-success observations where upstream drift cannot be determined.
_Avoid_: forced no-change, synthetic change on failure

**Scan Cadence**:
The fixed interval schedule for Metadata Scan Runs used to repeatedly observe upstream artifact state.
_Avoid_: ad hoc trigger-only scan, business-hours-only assumption

**Configurable Default Cadence**:
The branch rule that defaults scan cadence to 6 hours while keeping the interval easy to change through explicit configuration.
_Avoid_: hard-coded immutable interval, hidden schedule constant

**DAG-Owned Cadence Setting**:
The scheduling ownership rule that defines and changes scan cadence only in Airflow DAG configuration, not in data scope configuration.
_Avoid_: split cadence authority, data-scope-driven scheduler interval

**Single-Step Cadence Edit**:
The runbook requirement that shows one explicit setting location in the DAG file for changing cadence quickly during evaluation.
_Avoid_: multi-file cadence edits, implicit schedule discovery

**UTC Schedule Timezone**:
The default timezone policy for DAG scheduling and observation timestamps during evaluation.
_Avoid_: local-time scheduling default, daylight-saving-dependent timing

**Fixed UTC DAG Start Date**:
The scheduling policy that pins DAG start_date to a specific recent UTC datetime in code rather than computing it dynamically.
_Avoid_: now-based start_date, implicit moving scheduler baseline

**Canonical Evaluation DAG ID**:
The standard DAG identifier upstream_metadata_scan_v1 used for evaluator discovery and consistent documentation references.
_Avoid_: ad hoc DAG naming, ambiguous scan job label

**No-Catchup Scan Policy**:
The scheduler policy that runs only future scan intervals and does not backfill missed historical intervals automatically.
_Avoid_: automatic backlog replay, retroactive scan flood

**Single-Active Scan Run**:
The policy that allows only one active Metadata Scan Run at a time to preserve deterministic observation ordering.
_Avoid_: overlapping scan runs, parallel cadence overlap

**Canonical Scan Config Source**:
The rule that Metadata Scan Runs resolve scope and metadata storage settings from config/data_scope.yml as the default configuration authority.
_Avoid_: Airflow-only config fork, scheduler-local config drift

**Dual-Proof Evaluation**:
The prototype acceptance rule that requires both Airflow UI evidence of DAG/task execution and SQL-verifiable updates in the Domain Metadata Store.
_Avoid_: UI-only demo, table-only verification

**Partial-Success Scan Outcome**:
The run outcome where successful observations are persisted for reachable artifacts even when some artifact checks fail in the same scan interval.
_Avoid_: fail-all-on-first-error, hidden per-artifact failure

**Observation Explainability**:
The requirement that each observation stores enough metadata to justify true, false, or null change detection results.
_Avoid_: opaque change flag, unverifiable drift decision

**Storage Isolation Boundary**:
The branch rule that keeps Airflow runtime metadata and domain observation metadata in separate SQLite database files.
_Avoid_: shared runtime-domain database, mixed ownership tables

**Airflow Runtime Database**:
The SQLite database that stores Airflow internal scheduler, DAG Run, and task instance metadata only.
_Avoid_: domain snapshot store, upstream observation analytics database

**Domain Observation Database**:
The SQLite database that stores Upstream Snapshot and Upstream Observation History for analysis and verification.
_Avoid_: scheduler state store, Airflow internals database

**Retained Domain Evidence Path**:
The policy that places the Domain Observation Database under db/ as durable prototype evidence across DAG Runs.
_Avoid_: disposable tmp-only evidence store, scheduler-owned runtime path

**Co-Located DB Directory Policy**:
The branch policy that stores both Airflow Runtime Database and Domain Observation Database files under db/ while preserving strict file-level ownership boundaries.
_Avoid_: mixed-table ownership in one file, runtime-domain path scattering

**Airflow Runtime DB File**:
The canonical Airflow runtime metadata file at db/airflow-runtime.sqlite.
_Avoid_: inferred airflow.db default path, unnamed scheduler metadata file

**Domain Observation DB File**:
The canonical domain metadata evidence file at db/fec-observations.sqlite.
_Avoid_: shared runtime file, ambiguous metadata filename

**Dual Trigger Mode**:
The evaluation policy that supports both scheduled cadence DAG Runs and manual Airflow UI triggered DAG Runs.
_Avoid_: schedule-only operation, manual-only demo mode

**Constrained Manual Override Policy**:
The rule that manual DAG Run overrides are limited to cycle range and table subset while database paths and schema contracts remain fixed by branch defaults.
_Avoid_: ad hoc storage path override, runtime schema mutation from trigger config

**Prototype Full-History Retention**:
The evaluation-phase policy that retains all Upstream Observation History rows without TTL cleanup so scan behavior and retry patterns remain fully inspectable.
_Avoid_: early retention pruning, auto-expire prototype evidence

**Domain Schema Version Marker**:
The lightweight schema-version record in the Domain Observation Database used to validate compatibility before DAG tasks write observations.
_Avoid_: implicit schema assumption, silent format drift

**Fail-Fast Schema Gate**:
The policy that aborts a DAG Run when the Domain Observation Database schema version is incompatible, instead of applying in-task automatic migrations.
_Avoid_: silent auto-migration, best-effort schema coercion

**Create-If-Missing Bootstrap**:
The first-run policy that allows DAG tasks to create missing Domain Observation tables and version marker records, while still failing on incompatible existing versions.
_Avoid_: mandatory pre-seed script, auto-repair of incompatible schema

**Manual Promotion Authority**:
The branch lifecycle rule that promotion from Airflow-first evaluation to broader adoption is decided explicitly by the project owner rather than automatic gate criteria.
_Avoid_: fixed auto-promotion checklist, time-based forced convergence

**Evaluator First-Run Runbook**:
The single end-to-end guide for a developer new to Airflow that covers startup, one manual DAG Run, task-state checks, and SQL verification in the Domain Observation Database.
_Avoid_: fragmented setup notes, multi-document onboarding maze

**Non-Mandatory Verification Checklist**:
The evaluation policy that provides recommended SQL verification checks without requiring a fixed mandatory minimum set on every run.
_Avoid_: rigid pass-fail SQL gate, forced checklist completion

**Single Evidence Note**:
The evaluation record pattern that captures one explicit Airflow UI observation, one matching SQL observation, and one linking conclusion sentence per run.
_Avoid_: no-evidence signoff, heavyweight mandatory report template

**Localhost-Only Airflow Access**:
The branch policy that keeps the Airflow web interface bound to localhost during evaluation.
_Avoid_: remote-exposed evaluation UI, premature multi-user deployment

**Compact Failure Diagnostics**:
The observation logging policy that stores concise failure fields (error class, HTTP status when available, and truncated message) in the Domain Observation Database while full traces remain in Airflow task logs.
_Avoid_: raw stack trace blobs in SQL rows, opaque failure summary
