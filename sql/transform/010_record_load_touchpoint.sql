-- Lightweight transform touchpoint to verify ordered SQL execution.

INSERT INTO etl_run_log (run_id, run_started_at, phase, status, details)
SELECT
    CAST(epoch_ms(now()) AS BIGINT) AS run_id,
    now() AS run_started_at,
    'load' AS phase,
    'ok' AS status,
    'schema+transform batches executed' AS details;
