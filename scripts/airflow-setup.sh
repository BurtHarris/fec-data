#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=scripts/airflow-env.sh
source "${SCRIPT_DIR}/airflow-env.sh"

AIRFLOW_VENV="${AIRFLOW_VENV:-${REPO_ROOT}/.venv-airflow}"
AIRFLOW_VERSION="${AIRFLOW_VERSION:-2.10.3}"
AIRFLOW_ADMIN_USER="${AIRFLOW_ADMIN_USER:-admin}"
AIRFLOW_ADMIN_PASSWORD="${AIRFLOW_ADMIN_PASSWORD:-admin}"
AIRFLOW_ADMIN_FIRSTNAME="${AIRFLOW_ADMIN_FIRSTNAME:-Local}"
AIRFLOW_ADMIN_LASTNAME="${AIRFLOW_ADMIN_LASTNAME:-Admin}"
AIRFLOW_ADMIN_EMAIL="${AIRFLOW_ADMIN_EMAIL:-local@example.com}"

supports_airflow_constraints() {
  local python_bin="$1"
  local python_mm
  local python_major
  local python_minor
  local constraint_url

  python_mm="$("${python_bin}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)" || return 1
  python_major="${python_mm%%.*}"
  python_minor="${python_mm#*.}"

  # Keep setup aligned with project baseline in pyproject.toml (>=3.11).
  if (( python_major < 3 || (python_major == 3 && python_minor < 11) )); then
    return 1
  fi

  constraint_url="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${python_mm}.txt"

  if command -v curl >/dev/null 2>&1; then
    if ! curl -fsI "${constraint_url}" >/dev/null; then
      return 1
    fi
  else
    if ! "${python_bin}" - "${constraint_url}" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

url = sys.argv[1]
with urllib.request.urlopen(url):
    pass
PY
    then
      return 1
    fi
  fi

  return 0
}

if [[ -n "${AIRFLOW_PYTHON:-}" ]]; then
  PYTHON_BIN="${AIRFLOW_PYTHON}"
  if ! supports_airflow_constraints "${PYTHON_BIN}"; then
    PYTHON_MM="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "unknown")"
    echo "AIRFLOW_PYTHON points to Python ${PYTHON_MM}, but Airflow ${AIRFLOW_VERSION} constraints are unavailable for that interpreter."
    echo "Use a compatible interpreter (for example python3.12) or unset AIRFLOW_PYTHON to auto-select the newest supported version."
    exit 1
  fi
else
  PYTHON_BIN=""
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "${candidate}" >/dev/null 2>&1 && supports_airflow_constraints "${candidate}"; then
      PYTHON_BIN="${candidate}"
      break
    fi
  done

  if [[ -z "${PYTHON_BIN}" && -d "${HOME}/.pyenv/versions" ]]; then
    mapfile -t PYENV_PYTHONS < <(
      find "${HOME}/.pyenv/versions" -maxdepth 3 -type f \
        \( -name 'python3.13' -o -name 'python3.12' -o -name 'python3.11' \) \
        | sort -r
    )

    for candidate in "${PYENV_PYTHONS[@]}"; do
      if supports_airflow_constraints "${candidate}"; then
        PYTHON_BIN="${candidate}"
        break
      fi
    done
  fi

  if [[ -z "${PYTHON_BIN}" ]]; then
    echo "No compatible Python interpreter found for Airflow ${AIRFLOW_VERSION} constraints."
    echo "Install a recent Python 3 release (for example python3.12) and rerun setup."
    exit 1
  fi
fi

PYTHON_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

echo "Selected ${PYTHON_BIN} (Python ${PYTHON_VERSION}) for Airflow ${AIRFLOW_VERSION} setup"

if [[ -x "${AIRFLOW_VENV}/bin/python" ]]; then
  VENV_PYTHON_VERSION="$("${AIRFLOW_VENV}/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if [[ "${VENV_PYTHON_VERSION}" != "${PYTHON_VERSION}" ]]; then
    echo "Recreating ${AIRFLOW_VENV} because it was built with Python ${VENV_PYTHON_VERSION}"
    rm -rf "${AIRFLOW_VENV}"
  fi
fi

if [[ ! -d "${AIRFLOW_VENV}" ]]; then
  "${PYTHON_BIN}" -m venv "${AIRFLOW_VENV}"
fi

# shellcheck disable=SC1090
source "${AIRFLOW_VENV}/bin/activate"

python -m pip install --upgrade pip

echo "Installing Apache Airflow ${AIRFLOW_VERSION} with constraints for Python ${PYTHON_VERSION}"
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

echo "Airflow setup complete."
echo "Activate with: source ${AIRFLOW_VENV}/bin/activate"
echo "Run scheduler: bash scripts/airflow-run.sh scheduler"
echo "Run webserver: bash scripts/airflow-run.sh webserver"