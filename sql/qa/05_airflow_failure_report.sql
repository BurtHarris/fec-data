WITH failed_rows AS (
    SELECT
        observed_at,
        dag_run_id,
        cycle,
        table_name,
        zip_name,
        source_url,
        fetch_status,
        http_status,
        error_class,
        error_message,
        map_index,
        try_number,
        ROW_NUMBER() OVER (
            PARTITION BY dag_run_id
            ORDER BY observed_at DESC, map_index DESC, try_number DESC, observation_id DESC
        ) AS run_rank
    FROM airflow_upstream_observation_history
    WHERE dag_id = 'upstream_metadata_scan_v1'
      AND fetch_status != 'succeeded'
),
latest_failed_run AS (
    SELECT *
    FROM failed_rows
    QUALIFY run_rank = 1
    ORDER BY observed_at DESC, dag_run_id DESC
    LIMIT 1
)
SELECT
    observed_at,
    dag_run_id,
    cycle,
    table_name,
    zip_name,
    source_url,
    fetch_status,
    http_status,
    COALESCE(error_class, 'unknown') AS error_class,
    COALESCE(error_message, 'n/a') AS error_message,
    map_index,
    try_number
FROM latest_failed_run
ORDER BY map_index, try_number;
