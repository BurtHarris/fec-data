"""Server-rendered HTML for the Airflow failure report screen."""

from __future__ import annotations

from html import escape

from pipeline.web.airflow_failures import AirflowFailureReport


def _render_detail_rows(rows: list[tuple[str, str]]) -> str:
    items = [
        f"<div class='detail-row'><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>"
        for label, value in rows
    ]
    return f"<dl class='detail-list'>{''.join(items)}</dl>"


def _render_table(headers: list[str], rows: list[list[str]]) -> str:
    head_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return (
        "<div style='overflow-x:auto'>"
        f"<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"
        "</div>"
    )


def _render_metric_cards(report: AirflowFailureReport) -> str:
    cards = [
        ("Failed attempts", str(report.failed_attempt_count)),
        ("Failed assets", str(report.failed_asset_count)),
        ("Total attempts", str(report.total_attempt_count)),
        ("Latest failed run", report.latest_failed_run_id or "n/a"),
    ]
    return "".join(
        f"<div class='metric-card'><span class='muted'>{escape(label)}</span><strong>{escape(value)}</strong></div>"
        for label, value in cards
    )


def render_airflow_failures(report: AirflowFailureReport) -> str:
    source_rows = [
        ("Status", report.status),
        ("Source DB", report.source_label),
        ("Latest failed run", report.latest_failed_run_id or "n/a"),
        ("Latest failed at", report.latest_failed_at or "n/a"),
        ("Summary", report.message),
    ]

    if report.status != "ready":
        return """
<div class='stack'>
  <section class='subpanel'>
    <h3>Airflow failure status</h3>
    <p class='muted'>This screen reads the latest failed upstream metadata scan from the local observation database and groups the failed attempts by error class.</p>
    {detail_rows}
  </section>
</div>
""".format(detail_rows=_render_detail_rows(source_rows))

    error_rows = [
        [escape(summary.error_class), escape(str(summary.failure_count))]
        for summary in report.error_class_summaries
    ]
    failure_rows = [
        [
            escape(event.observed_at),
            escape(str(event.cycle)),
            escape(event.table_name),
            escape(event.zip_name),
            escape(event.fetch_status),
            escape(str(event.http_status) if event.http_status is not None else "n/a"),
            escape(event.error_class or "unknown"),
            escape(event.error_message or "n/a"),
            escape(str(event.map_index)),
            escape(str(event.try_number)),
        ]
        for event in report.failed_events
    ]

    return """
<div class='stack'>
  <section class='subpanel'>
    <h3>Latest Airflow failure batch</h3>
    <p class='muted'>The newest failed run is summarized below with grouped error classes and the exact failed source URLs preserved in the loader output.</p>
    {detail_rows}
  </section>
  <section class='metric-grid'>
    {metric_cards}
  </section>
  <div class='dashboard-grid'>
    <section class='subpanel'>
      <h3>Failure classes</h3>
      <p class='muted'>Counts are grouped by the recorded error class for the latest failed run.</p>
      {class_table}
    </section>
    <section class='subpanel'>
      <h3>Failed attempts</h3>
      <p class='muted'>Attempts are ordered by map index and try number so the retry sequence is readable.</p>
      {failure_table}
    </section>
  </div>
</div>
""".format(
        detail_rows=_render_detail_rows(source_rows),
        metric_cards=_render_metric_cards(report),
        class_table=_render_table(["Error class", "Failures"], error_rows),
        failure_table=_render_table(
            ["Observed", "Cycle", "Table", "Zip", "Status", "HTTP", "Error class", "Error message", "Map index", "Try"],
            failure_rows,
        ),
    )
