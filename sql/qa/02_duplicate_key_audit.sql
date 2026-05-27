DROP TABLE IF EXISTS qa_duplicate_groups;
CREATE TEMP TABLE qa_duplicate_groups AS
SELECT
    {{KEY_EXPR}} AS issue_key,
    COUNT(*) AS issue_count
FROM {{TARGET_TABLE}}
GROUP BY 1
HAVING COUNT(*) > 1;

DELETE FROM etl.qa_issue_log
WHERE run_id = {{RUN_ID}}
  AND cycle = {{CYCLE}}
  AND table_name = {{TABLE_NAME}}
  AND issue_type = 'duplicate_key';

DELETE FROM etl.qa_run_summary
WHERE run_id = {{RUN_ID}}
  AND cycle = {{CYCLE}}
  AND table_name = {{TABLE_NAME}}
  AND metric_name = 'duplicate_key';

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
    {{RUN_ID}} AS run_id,
    {{CYCLE}} AS cycle,
    {{TABLE_NAME}} AS table_name,
    'duplicate_key' AS metric_name,
    CAST(COALESCE(SUM(issue_count), 0) AS DOUBLE) AS metric_value,
    CASE WHEN COUNT(*) > 0 THEN 'warn' ELSE 'pass' END AS status,
    NOW() AS computed_at
FROM qa_duplicate_groups;

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
    {{RUN_ID}} AS run_id,
    {{CYCLE}} AS cycle,
    {{TABLE_NAME}} AS table_name,
    'duplicate_key' AS issue_type,
    'warn' AS severity,
    issue_key,
    issue_count,
    'duplicate_rows=' || CAST(issue_count AS VARCHAR) AS issue_details,
    NOW() AS detected_at
FROM qa_duplicate_groups;

DROP TABLE IF EXISTS qa_duplicate_groups;
