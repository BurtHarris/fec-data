#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=scripts/airflow-env.sh
source "${SCRIPT_DIR}/airflow-env.sh"

AIRFLOW_VENV="${AIRFLOW_VENV:-${REPO_ROOT}/.venv-airflow}"
AIRFLOW_PORT="${AIRFLOW_PORT:-8080}"
AIRFLOW_ADMIN_USER="${AIRFLOW_ADMIN_USER:-admin}"
AIRFLOW_ADMIN_PASSWORD="${AIRFLOW_ADMIN_PASSWORD:-admin}"
AIRFLOW_ADMIN_FIRSTNAME="${AIRFLOW_ADMIN_FIRSTNAME:-Local}"
AIRFLOW_ADMIN_LASTNAME="${AIRFLOW_ADMIN_LASTNAME:-Admin}"
AIRFLOW_ADMIN_EMAIL="${AIRFLOW_ADMIN_EMAIL:-local@example.com}"

if [[ ! -f "${AIRFLOW_VENV}/bin/activate" ]]; then
  echo "Missing ${AIRFLOW_VENV}. Run bash scripts/airflow-setup.sh first."
  exit 1
fi

# shellcheck disable=SC1090
source "${AIRFLOW_VENV}/bin/activate"

command_name="${1:-help}"

case "${command_name}" in
  init)
    airflow db migrate
    ;;
  create-admin)
    airflow users create \
      --username "${AIRFLOW_ADMIN_USER}" \
      --firstname "${AIRFLOW_ADMIN_FIRSTNAME}" \
      --lastname "${AIRFLOW_ADMIN_LASTNAME}" \
      --role Admin \
      --email "${AIRFLOW_ADMIN_EMAIL}" \
      --password "${AIRFLOW_ADMIN_PASSWORD}"
    ;;
  scheduler)
    exec airflow scheduler
    ;;
  webserver)
    exec airflow webserver --port "${AIRFLOW_PORT}"
    ;;
  users)
    airflow users list
    ;;
  shell)
    exec bash
    ;;
  *)
    cat <<'USAGE'
Usage: bash scripts/airflow-run.sh <command>

Commands:
  init          Run airflow db migrate
  create-admin  Create admin user from AIRFLOW_ADMIN_* env vars
  scheduler     Start airflow scheduler
  webserver     Start airflow webserver on AIRFLOW_PORT (default 8080)
  users         List Airflow users
  shell         Open a shell with Airflow env loaded
USAGE
    exit 1
    ;;
esac