# Fastest base for Airflow-heavy dev
FROM quay.io/astronomer/astro-runtime:10.0.0

SHELL ["/bin/bash", "-lc"]

USER root

RUN echo 'astro ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/astro && chmod 0440 /etc/sudoers.d/astro

ENV DEBIAN_FRONTEND=noninteractive

# Container bootstrap requirements are installed directly in this image build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    fd-find \
    fzf \
    git \
    gh \
    jq \
    libbz2-dev \
    libffi-dev \
    liblzma-dev \
    libncursesw5-dev \
    libreadline-dev \
    libsqlite3-dev \
    libssl-dev \
    libxml2-dev \
    libxmlsec1-dev \
    make \
    p7zip-full \
    pkg-config \
    python3 \
    python3-venv \
    ripgrep \
    sqlite3 \
    tk-dev \
    unzip \
    xz-utils \
    zlib1g-dev \
    bat \
    sudo \
    && if [ ! -e /usr/local/bin/fd ]; then ln -s /usr/bin/fdfind /usr/local/bin/fd; fi \
    && if [ ! -e /usr/local/bin/bat ]; then ln -s /usr/bin/batcat /usr/local/bin/bat; fi \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --root-user-action=ignore \
    --default-timeout=120 \
    --retries 10 \
    apache-airflow-providers-http==4.8.0 \
    apache-airflow-providers-sqlite==3.6.0 \
    airflow-provider-duckdb==0.2.0 \
    dbt-duckdb \
    duckdb \
    sqlite-utils

RUN set -euo pipefail; \
        case "$(uname -m)" in \
            x86_64) arch="amd64" ;; \
            aarch64|arm64) arch="arm64" ;; \
            *) echo "Unsupported architecture for DuckDB CLI: $(uname -m)" >&2; exit 1 ;; \
        esac; \
        asset_name="duckdb_cli-linux-${arch}.zip"; \
    download_url="$(DUCKDB_ASSET_NAME="${asset_name}" python3 - <<'PY'
import json
import os
import urllib.request

asset_name = os.environ['DUCKDB_ASSET_NAME']
with urllib.request.urlopen('https://api.github.com/repos/duckdb/duckdb/releases/latest') as response:
        release = json.load(response)

for asset in release.get('assets', []):
        if asset.get('name') == asset_name:
                print(asset['browser_download_url'])
                break
else:
        raise SystemExit(f'could not find DuckDB asset {asset_name!r}')
PY
)"; \
        tmp_dir="$(mktemp -d)"; \
        curl -fL "${download_url}" -o "${tmp_dir}/duckdb.zip"; \
        unzip -q "${tmp_dir}/duckdb.zip" -d "${tmp_dir}"; \
        install -m 0755 "${tmp_dir}/duckdb" /usr/local/bin/duckdb; \
        rm -rf "${tmp_dir}"

# Create workspace dirs (volumes will mount over these)
RUN mkdir -p /workspaces/fec-data/data \
    && mkdir -p /workspaces/fec-data/db \
    && chown -R astro:astro /workspaces

USER astro
WORKDIR /workspaces/fec-data

ENV PYENV_ROOT=/home/astro/.pyenv
ENV PATH=/home/astro/.local/bin:/home/astro/.pyenv/bin:/home/astro/.pyenv/shims:${PATH}

RUN set -euo pipefail; \
        if [[ ! -d "${HOME}/.pyenv" ]]; then \
            git clone https://github.com/pyenv/pyenv.git "${HOME}/.pyenv"; \
        fi; \
        export PYENV_ROOT="${HOME}/.pyenv"; \
        export PATH="${PYENV_ROOT}/bin:${PATH}"; \
        eval "$(pyenv init - bash)"; \
        pyenv install -s 3.12.10; \
        pyenv global 3.12.10

RUN set -euo pipefail; \
        if ! command -v uv >/dev/null 2>&1; then \
            curl -LsSf https://astral.sh/uv/install.sh | sh; \
        fi

RUN if ! grep -q '\.local/bin' "${HOME}/.bashrc"; then \
            { \
                echo ''; \
                echo '# user-local binaries (uv, etc.)'; \
                echo 'export PATH="$HOME/.local/bin:$PATH"'; \
            } >> "${HOME}/.bashrc"; \
        fi

RUN if ! grep -q 'PYENV_ROOT="$HOME/.pyenv"' "${HOME}/.bashrc"; then \
            { \
                echo ''; \
                echo '# pyenv initialization'; \
                echo 'export PYENV_ROOT="$HOME/.pyenv"'; \
                echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"'; \
                echo 'eval "$(pyenv init - bash)"'; \
            } >> "${HOME}/.bashrc"; \
        fi
