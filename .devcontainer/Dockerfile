# Fastest base for Airflow-heavy dev
FROM quay.io/astronomer/astro-runtime:10.0.0

USER root

# System packages you likely need
RUN apt-get update && apt-get install -y \
    sqlite3 \
    jq \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python packages: dbt + duckdb + sqlite utils
RUN pip install --no-cache-dir \
    dbt-duckdb \
    duckdb \
    sqlite-utils

# Create workspace dirs (volumes will mount over these)
RUN mkdir -p /workspaces/fec-data/data \
    && mkdir -p /workspaces/fec-data/db \
    && chown -R astro:astro /workspaces

USER astro
WORKDIR /workspaces/fec-data
