#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

export MONEYTRAIL_REPO_ROOT="${REPO_ROOT}"
export AIRFLOW_HOME="${AIRFLOW_HOME:-${REPO_ROOT}/tmp/airflow-home}"
export AIRFLOW__CORE__DAGS_FOLDER="${AIRFLOW__CORE__DAGS_FOLDER:-${REPO_ROOT}/dags}"
export AIRFLOW__CORE__LOAD_EXAMPLES="${AIRFLOW__CORE__LOAD_EXAMPLES:-False}"
export AIRFLOW__CORE__EXECUTOR="${AIRFLOW__CORE__EXECUTOR:-SequentialExecutor}"
export AIRFLOW__WEBSERVER__WEB_SERVER_HOST="${AIRFLOW__WEBSERVER__WEB_SERVER_HOST:-127.0.0.1}"
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN:-sqlite:///${REPO_ROOT}/db/airflow-runtime.sqlite}"

# Ensure Airflow and project-local paths exist before CLI calls.
mkdir -p "${AIRFLOW_HOME}" "${REPO_ROOT}/db" "${REPO_ROOT}/logs"

if [[ -d "${REPO_ROOT}/src" ]]; then
  export PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
fi