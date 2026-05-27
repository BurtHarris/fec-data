DROP TABLE IF EXISTS qa_metrics;
CREATE TEMP TABLE qa_metrics AS
{{NULL_METRICS_QUERY}};

DELETE FROM etl.qa_issue_log
WHERE run_id = {{RUN_ID}}
  AND cycle = {{CYCLE}}
  AND table_name = {{TABLE_NAME}}
  AND issue_type = 'null_rate';

DELETE FROM etl.qa_run_summary
WHERE run_id = {{RUN_ID}}
  AND cycle = {{CYCLE}}
  AND table_name = {{TABLE_NAME}}
  AND metric_name = 'null_rate';

INSERT INTO etl.qa_run_summary (
    run_id,
    cycle,
    table_name,
    metric_name,
    metric_value,
    status,
    computed_at
)
SELECT
    run_id,
    cycle,
    table_name,
    metric_name,
    metric_value,
    status,
    computed_at
FROM qa_metrics;

INSERT INTO etl.qa_issue_log (
    issue_id,
    run_id,
    cycle,
    table_name,
    issue_type,
    severity,
    issue_key,
    issue_count,
    issue_details,
    detected_at
)
SELECT
    COALESCE((SELECT MAX(issue_id) + 1 FROM etl.qa_issue_log), 1) AS issue_id,
    run_id,
    cycle,
    table_name,
    'null_rate' AS issue_type,
    'warn' AS severity,
    issue_key,
    issue_count,
    issue_details,
    computed_at
  FROM qa_metrics
WHERE issue_count > 0;

  DROP TABLE IF EXISTS qa_metrics;
