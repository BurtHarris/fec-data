#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

export DEBIAN_FRONTEND="${DEBIAN_FRONTEND:-noninteractive}"

APT_PACKAGES=(
  build-essential
  ca-certificates
  curl
  fd-find
  fzf
  git
  gh
  jq
  libbz2-dev
  libffi-dev
  liblzma-dev
  libncursesw5-dev
  libreadline-dev
  libsqlite3-dev
  libssl-dev
  libxml2-dev
  libxmlsec1-dev
  make
  p7zip-full
  pkg-config
  python3
  python3-venv
  ripgrep
  sqlite3
  tk-dev
  unzip
  xz-utils
  zlib1g-dev
  bat
)

require_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "Required command missing: ${command_name}" >&2
    exit 1
  fi
}

ensure_symlink() {
  local target="$1"
  local link_name="$2"

  if [[ -e "${link_name}" || -L "${link_name}" ]]; then
    return 0
  fi

  sudo ln -s "${target}" "${link_name}"
}

install_pyenv() {
  if [[ ! -d "${HOME}/.pyenv" ]]; then
    git clone https://github.com/pyenv/pyenv.git "${HOME}/.pyenv"
  fi

  export PYENV_ROOT="${HOME}/.pyenv"
  export PATH="${PYENV_ROOT}/bin:${PATH}"
  # shellcheck disable=SC1090
  eval "$(pyenv init - bash)"

  pyenv install -s 3.12.10
  pyenv local 3.12.10 >/dev/null 2>&1 || true
}

install_uv() {
  if command -v uv >/dev/null 2>&1; then
    return 0
  fi

  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
}

install_duckdb_cli() {
  if command -v duckdb >/dev/null 2>&1; then
    return 0
  fi

  local arch asset_name download_url tmp_dir
  case "$(uname -m)" in
    x86_64) arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
    *)
      echo "Unsupported architecture for DuckDB CLI: $(uname -m)" >&2
      exit 1
      ;;
  esac

  asset_name="duckdb_cli-linux-${arch}.zip"
  download_url="$(python3 - <<PY
import json
import sys
import urllib.request

asset_name = ${asset_name@Q}
with urllib.request.urlopen('https://api.github.com/repos/duckdb/duckdb/releases/latest') as response:
    release = json.load(response)

for asset in release.get('assets', []):
    if asset.get('name') == asset_name:
        print(asset['browser_download_url'])
        break
else:
    raise SystemExit(f'could not find DuckDB asset {asset_name!r}')
PY
)"

  tmp_dir="$(mktemp -d)"
  curl -fL "${download_url}" -o "${tmp_dir}/duckdb.zip"
  unzip -q "${tmp_dir}/duckdb.zip" -d "${tmp_dir}"
  sudo install -m 0755 "${tmp_dir}/duckdb" /usr/local/bin/duckdb
  rm -rf "${tmp_dir}"
}

sudo apt-get update
sudo apt-get install -y "${APT_PACKAGES[@]}"

ensure_symlink /usr/bin/fdfind /usr/local/bin/fd
ensure_symlink /usr/bin/batcat /usr/local/bin/bat

install_pyenv
install_uv
install_duckdb_cli

if ! grep -q 'PYENV_ROOT="$HOME/.pyenv"' "${HOME}/.bashrc"; then
  {
    echo ''
    echo '# pyenv initialization'
    echo 'export PYENV_ROOT="$HOME/.pyenv"'
    echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"'
    echo 'eval "$(pyenv init - bash)"'
  } >> "${HOME}/.bashrc"
fi

echo "WSL tool bootstrap complete."
echo "Python: $(pyenv version-name)"
echo "uv: $(uv --version)"
echo "duckdb: $(duckdb --version)"
echo "fd: $(fd --version 2>/dev/null || fd -v 2>/dev/null || true)"
echo "bat: $(bat --version 2>/dev/null || batcat --version 2>/dev/null || true)"
