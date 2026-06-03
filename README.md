# FEC Data ELT (Pre-Release)

This repository is an early-stage data engineering project for ingesting and analyzing Federal Election Commission (FEC) bulk campaign finance data. The current architecture is ELT: source files are landed as immutable raw artifacts, then loaded and transformed inside DuckDB into analysis-ready models.

The project is still pre-release. Expect active iteration in schemas, transform sequencing, and orchestration while data quality and performance are tuned.

## Documentation

- [Developer Setup](docs/developer_setup.md): Dev Container workflow, host prerequisites, and split-storage guidance (repo source in workspace, runtime data on Linux-native mounts).
- [Project Context](CONTEXT.md): domain and working context for this repository.
- [Architecture Decisions](docs/adr): decision records tracked during project evolution.

## Project Goals

- Build a reproducible local ELT workflow for FEC bulk data.
- Preserve source-of-truth raw files and make downstream transforms deterministic.
- Produce trustworthy analytic tables with clear, SQL-first quality checks.
- Keep orchestration lightweight and observable during early evaluation.

## ELT Scope

- Extract: download official FEC bulk ZIP artifacts.
- Load: ingest source data into DuckDB with stable schema conventions.
- Transform: apply SQL/dbt modeling and validation checks for analyst use.

## Current Status

- Stage: pre-release / active development
- Primary datastore: DuckDB
- Modeling approach: SQL/dbt-based transforms
- Reliability posture: improving through audits, smoke tests, and iterative hardening

## Repository Structure (High Level)

- config: data scope and source-coverage configuration
- models: raw FEC dbt models
- sql/schema and sql/transform: schema creation and ELT SQL
- sql/qa: quality, audit, and anomaly checks
- dags: Airflow-first evaluation workflows
- src/pipeline: Python pipeline utilities
- tests: smoke tests and validation checks
- artifacts: analysis, diagrams, reviews, and exploration output

## Early Adopter Notes

- Backward compatibility is not guaranteed yet.
- Data model names and load sequencing may be refined.
- Performance characteristics will continue to improve as datasets scale.

## Runtime Storage Model

- Repository source files remain in the normal workspace checkout for Git/editor workflows.
- Runtime-heavy artifacts (`data/` and `db/`) are mounted to Linux-native host paths by the Dev Container configuration.
- Use the `Export: db snapshot` task when host-side tools need a copied DB snapshot.

For setup and environment instructions, see [Developer Setup](docs/developer_setup.md).
