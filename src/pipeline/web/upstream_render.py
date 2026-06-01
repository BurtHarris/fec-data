"""Server-rendered HTML for the Upstream Changes operations screen."""

from __future__ import annotations

from html import escape

from pipeline.web.upstream_changes import UpstreamChangesReport


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


def _render_upstream_metric_cards(report: UpstreamChangesReport) -> str:
    busiest_month = report.monthly_rollups[0] if report.monthly_rollups else None
    cards = [
        ("Successful fetches", str(report.successful_fetch_count)),
        ("Tracked assets", str(report.tracked_asset_count)),
        ("Detected shifts", str(report.change_event_count)),
        (
            "Busiest month",
            f"{busiest_month.month_label} ({busiest_month.change_count})" if busiest_month else "n/a",
        ),
    ]
    return "".join(
        f"<div class='metric-card'><span class='muted'>{escape(label)}</span><strong>{escape(value)}</strong></div>"
        for label, value in cards
    )


def render_upstream_changes(report: UpstreamChangesReport) -> str:
    source_rows = [
        ("Status", report.status),
        ("Source DB", report.source_label),
        ("Latest fetch", report.latest_fetch_at or "n/a"),
        ("Summary", report.message),
    ]

    if report.status != "ready":
        return """
<div class='stack'>
  <section class='subpanel'>
    <h3>Metadata history status</h3>
    <p class='muted'>This screen reads historical fetch metadata from the configured metadata store and derives upstream ZIP change events when that history exists.</p>
    {detail_rows}
  </section>
</div>
""".format(detail_rows=_render_detail_rows(source_rows))

    recent_change_rows = [
        [
            escape(event.fetched_at),
            escape(str(event.cycle)),
            escape(event.table_name),
            escape(", ".join(event.changed_fields)),
            escape(event.previous_fetched_at),
            escape(event.current_etag or "n/a"),
            escape(event.current_last_modified or "n/a"),
            escape(str(event.current_content_length) if event.current_content_length is not None else "n/a"),
        ]
        for event in report.recent_events
    ]
    cadence_rows = [
        [
            escape(str(summary.cycle)),
            escape(summary.table_name),
            escape(str(summary.change_count)),
            escape(f"{summary.median_interval_days:.1f}" if summary.median_interval_days is not None else "no cadence data"),
            escape(summary.latest_change_at),
        ]
        for summary in report.cadence_summaries
    ]
    rollup_rows = [
        [
            escape(rollup.month_label),
            escape(str(rollup.change_count)),
            escape(str(rollup.asset_count)),
        ]
        for rollup in report.monthly_rollups
    ]
    table_summary_rows = [
        [
            escape(summary.table_name),
            escape(str(summary.change_count)),
            escape(str(summary.cycle_count)),
            escape(summary.latest_change_at),
        ]
        for summary in report.table_summaries
    ]

    return """
<div class='stack'>
  <section class='subpanel'>
    <h3>Upstream metadata shifts</h3>
    <p class='muted'>Change events are derived from successful fetch history when ETag, Last-Modified, or Content-Length moves forward for a cycle and table pair.</p>
    {detail_rows}
  </section>
  <section class='metric-grid'>
    {metric_cards}
  </section>
  <div class='dashboard-grid'>
    <section class='subpanel'>
      <h3>Recent change events</h3>
      <p class='muted'>Newest detected upstream ZIP shifts first.</p>
      {recent_table}
    </section>
    <section class='subpanel'>
      <h3>Cadence by asset</h3>
      <p class='muted'>Median interval is only shown when at least two change events exist for the same cycle and table.</p>
      {cadence_table}
    </section>
  </div>
  <div class='dashboard-grid'>
    <section class='subpanel'>
      <h3>Monthly burst windows</h3>
      <p class='muted'>Simple monthly rollup of detected upstream changes in UTC calendar months.</p>
      {rollup_table}
    </section>
    <section class='subpanel'>
      <h3>Table summary</h3>
      <p class='muted'>Tables with the highest number of detected upstream metadata shifts.</p>
      {summary_table}
    </section>
  </div>
</div>
""".format(
        detail_rows=_render_detail_rows(source_rows),
        metric_cards=_render_upstream_metric_cards(report),
        recent_table=_render_table(
            ["Fetched", "Cycle", "Table", "Changed fields", "Previous fetch", "ETag", "Last-Modified", "Content-Length"],
            recent_change_rows,
        ),
        cadence_table=_render_table(["Cycle", "Table", "Changes", "Median days", "Latest"], cadence_rows),
        rollup_table=_render_table(["Month", "Change events", "Assets changed"], rollup_rows),
        summary_table=_render_table(["Table", "Changes", "Cycles", "Latest"], table_summary_rows),
    )
