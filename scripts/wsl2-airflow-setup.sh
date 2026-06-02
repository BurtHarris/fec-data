#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=scripts/wsl2-airflow-env.sh
source "${SCRIPT_DIR}/wsl2-airflow-env.sh"

AIRFLOW_VENV="${AIRFLOW_VENV:-${REPO_ROOT}/.venv-airflow-wsl}"
AIRFLOW_VERSION="${AIRFLOW_VERSION:-2.10.3}"
AIRFLOW_ADMIN_USER="${AIRFLOW_ADMIN_USER:-admin}"
AIRFLOW_ADMIN_PASSWORD="${AIRFLOW_ADMIN_PASSWORD:-admin}"
AIRFLOW_ADMIN_FIRSTNAME="${AIRFLOW_ADMIN_FIRSTNAME:-Local}"
AIRFLOW_ADMIN_LASTNAME="${AIRFLOW_ADMIN_LASTNAME:-Admin}"
AIRFLOW_ADMIN_EMAIL="${AIRFLOW_ADMIN_EMAIL:-local@example.com}"

if [[ ! -d "${AIRFLOW_VENV}" ]]; then
  python3 -m venv "${AIRFLOW_VENV}"
fi

# shellcheck disable=SC1090
source "${AIRFLOW_VENV}/bin/activate"

python -m pip install --upgrade pip

PYTHON_VERSION="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

python -m pip install --constraint "${CONSTRAINT_URL}" "apache-airflow==${AIRFLOW_VERSION}"
python -m pip install -e "${REPO_ROOT}"

airflow db migrate

if airflow users list | grep -q "${AIRFLOW_ADMIN_USER}"; then
  echo "Airflow user '${AIRFLOW_ADMIN_USER}' already exists; skipping creation."
else
  airflow users create \
    --username "${AIRFLOW_ADMIN_USER}" \
    --firstname "${AIRFLOW_ADMIN_FIRSTNAME}" \
    --lastname "${AIRFLOW_ADMIN_LASTNAME}" \
    --role Admin \
    --email "${AIRFLOW_ADMIN_EMAIL}" \
    --password "${AIRFLOW_ADMIN_PASSWORD}"
fi

echo "WSL2 Airflow setup complete."
echo "Activate with: source ${AIRFLOW_VENV}/bin/activate"
echo "Run scheduler: bash scripts/wsl2-airflow-run.sh scheduler"
echo "Run webserver: bash scripts/wsl2-airflow-run.sh webserver"