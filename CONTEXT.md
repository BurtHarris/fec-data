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
