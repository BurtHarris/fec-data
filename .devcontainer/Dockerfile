# Fastest base for Airflow-heavy dev
FROM quay.io/astronomer/astro-runtime:10.0.0

USER root

RUN echo 'astro ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/astro && chmod 0440 /etc/sudoers.d/astro

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --root-user-action=ignore \
    --default-timeout=120 \
    --retries 10 \
    dbt-duckdb \
    duckdb \
    sqlite-utils

# Create workspace dirs (volumes will mount over these)
RUN mkdir -p /workspaces/fec-data/data \
    && mkdir -p /workspaces/fec-data/db \
    && chown -R astro:astro /workspaces

USER astro
WORKDIR /workspaces/fec-data
