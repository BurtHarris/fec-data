import unittest

from pipeline.metadata_store import FetchHistoryRecord, InMemoryDownloadMetadataStore
from pipeline.web.upstream_changes import load_upstream_changes_report


class _FailingMetadataStore:
    source_label = "broken-store"

    @staticmethod
    def load_successful_fetch_history() -> tuple[FetchHistoryRecord, ...]:
        raise RuntimeError("metadata store is offline")


def _history_row(
    fetch_id: int,
    cycle: int,
    table_name: str,
    zip_name: str,
    source_url: str,
    fetch_status: str,
    http_status: int | None,
    content_length: int | None,
    response_date: str | None,
    last_modified: str | None,
    etag: str | None,
    local_file_size: int | None,
    fetched_at: str,
    error_text: str | None,
) -> FetchHistoryRecord:
    return FetchHistoryRecord(
        fetch_id=fetch_id,
        cycle=cycle,
        table_name=table_name,
        zip_name=zip_name,
        source_url=source_url,
        fetch_status=fetch_status,
        http_status=http_status,
        content_length=content_length,
        response_date=response_date,
        last_modified=last_modified,
        etag=etag,
        local_file_size=local_file_size,
        fetched_at=fetched_at,
        error_text=error_text,
    )


class UpstreamChangesAnalyticsTests(unittest.TestCase):
    def test_metadata_store_failure_returns_unavailable_report(self) -> None:
        report = load_upstream_changes_report(_FailingMetadataStore())

        self.assertEqual(report.status, "unavailable")
        self.assertIn("offline", report.message)

    def test_empty_history_returns_empty_report(self) -> None:
        report = load_upstream_changes_report(InMemoryDownloadMetadataStore())

        self.assertEqual(report.status, "empty")
        self.assertIn("No successful fetch history", report.message)

    def test_report_detects_changes_deterministically_and_computes_cadence(self) -> None:
        store = InMemoryDownloadMetadataStore(
            history=(
                _history_row(
                    1,
                    2024,
                    "indiv",
                    "indiv24.zip",
                    "https://example.test/indiv24.zip",
                    "success",
                    200,
                    100,
                    None,
                    "Mon, 01 Jan 2024 00:00:00 GMT",
                    "etag-a",
                    100,
                    "2024-01-01T00:00:00Z",
                    None,
                ),
                _history_row(
                    2,
                    2024,
                    "indiv",
                    "indiv24.zip",
                    "https://example.test/indiv24.zip",
                    "success",
                    200,
                    100,
                    None,
                    "Mon, 01 Jan 2024 00:00:00 GMT",
                    "etag-a",
                    100,
                    "2024-01-10T00:00:00Z",
                    None,
                ),
                _history_row(
                    3,
                    2024,
                    "indiv",
                    "indiv24.zip",
                    "https://example.test/indiv24.zip",
                    "success",
                    200,
                    110,
                    None,
                    "Mon, 01 Jan 2024 00:00:00 GMT",
                    "etag-a",
                    110,
                    "2024-02-01T00:00:00Z",
                    None,
                ),
                _history_row(
                    4,
                    2024,
                    "indiv",
                    "indiv24.zip",
                    "https://example.test/indiv24.zip",
                    "success",
                    200,
                    110,
                    None,
                    "Tue, 05 Mar 2024 00:00:00 GMT",
                    "etag-b",
                    110,
                    "2024-03-05T00:00:00Z",
                    None,
                ),
                _history_row(
                    5,
                    2024,
                    "indiv",
                    "indiv24.zip",
                    "https://example.test/indiv24.zip",
                    "success",
                    200,
                    110,
                    None,
                    "Tue, 05 Mar 2024 00:00:00 GMT",
                    "",
                    110,
                    "2024-03-10T00:00:00Z",
                    None,
                ),
                _history_row(
                    6,
                    2024,
                    "oth",
                    "oth24.zip",
                    "https://example.test/oth24.zip",
                    "success",
                    200,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "2024-01-01T00:00:00Z",
                    None,
                ),
                _history_row(
                    7,
                    2024,
                    "oth",
                    "oth24.zip",
                    "https://example.test/oth24.zip",
                    "success",
                    200,
                    200,
                    None,
                    None,
                    None,
                    200,
                    "2024-01-15T00:00:00Z",
                    None,
                ),
                _history_row(
                    8,
                    2024,
                    "oth",
                    "oth24.zip",
                    "https://example.test/oth24.zip",
                    "failed",
                    500,
                    300,
                    None,
                    None,
                    None,
                    300,
                    "2024-02-15T00:00:00Z",
                    "server error",
                ),
                _history_row(
                    9,
                    2024,
                    "cm",
                    "cm24.zip",
                    "https://example.test/cm24.zip",
                    "success",
                    200,
                    10,
                    None,
                    None,
                    None,
                    10,
                    "2024-01-20T00:00:00Z",
                    None,
                ),
                _history_row(
                    10,
                    2024,
                    "cm",
                    "cm24.zip",
                    "https://example.test/cm24.zip",
                    "success",
                    200,
                    20,
                    None,
                    None,
                    None,
                    20,
                    "2024-01-20T00:00:00Z",
                    None,
                ),
            )
        )

        report = load_upstream_changes_report(store)

        self.assertEqual(report.status, "ready")
        self.assertEqual(report.successful_fetch_count, 9)
        self.assertEqual(report.tracked_asset_count, 3)
        self.assertEqual(report.change_event_count, 4)
        self.assertEqual(report.latest_fetch_at, "2024-03-10T00:00:00Z")

        fetched_change_times = [event.fetched_at for event in report.recent_events]
        self.assertNotIn("2024-03-10T00:00:00Z", fetched_change_times)
        self.assertEqual(report.recent_events[0].fetched_at, "2024-03-05T00:00:00Z")
        self.assertEqual(report.recent_events[0].changed_fields, ("etag", "last_modified"))

        cadence_by_asset = {(summary.cycle, summary.table_name): summary for summary in report.cadence_summaries}
        self.assertEqual(cadence_by_asset[(2024, "indiv")].change_count, 2)
        self.assertEqual(cadence_by_asset[(2024, "indiv")].median_interval_days, 33.0)
        self.assertIsNone(cadence_by_asset[(2024, "oth")].median_interval_days)
        self.assertIsNone(cadence_by_asset[(2024, "cm")].median_interval_days)

        self.assertEqual(
            [(rollup.month_label, rollup.change_count, rollup.asset_count) for rollup in report.monthly_rollups],
            [("2024-03", 1, 1), ("2024-02", 1, 1), ("2024-01", 2, 2)],
        )
        self.assertEqual(report.table_summaries[0].table_name, "indiv")
        self.assertEqual(report.table_summaries[0].change_count, 2)


if __name__ == "__main__":
    unittest.main()
