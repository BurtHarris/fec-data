import sqlite3
import tempfile
import unittest
from pathlib import Path

from pipeline.web.upstream_changes import load_upstream_changes_report


def _write_metadata_history(metadata_db_path: Path, rows: list[tuple[object, ...]], create_table: bool = True) -> Path:
    metadata_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(metadata_db_path)
    try:
        if create_table:
            conn.execute(
                """
                CREATE TABLE etl_fetch_history (
                    fetch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle INTEGER NOT NULL,
                    table_name TEXT NOT NULL,
                    zip_name TEXT,
                    source_url TEXT,
                    fetch_status TEXT NOT NULL,
                    http_status INTEGER,
                    content_length INTEGER,
                    response_date TEXT,
                    last_modified TEXT,
                    etag TEXT,
                    local_file_size INTEGER,
                    fetched_at TEXT NOT NULL,
                    error_text TEXT
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO etl_fetch_history (
                    fetch_id,
                    cycle,
                    table_name,
                    zip_name,
                    source_url,
                    fetch_status,
                    http_status,
                    content_length,
                    response_date,
                    last_modified,
                    etag,
                    local_file_size,
                    fetched_at,
                    error_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        conn.commit()
    finally:
        conn.close()
    return metadata_db_path


class UpstreamChangesAnalyticsTests(unittest.TestCase):
    def test_missing_db_returns_unavailable_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_db_path = Path(temp_dir) / "db" / "fec-metadata.sqlite"

            report = load_upstream_changes_report(metadata_db_path)

        self.assertEqual(report.status, "unavailable")
        self.assertIn("not found", report.message)

    def test_missing_history_table_returns_unavailable_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_db_path = _write_metadata_history(
                Path(temp_dir) / "db" / "fec-metadata.sqlite",
                rows=[],
                create_table=False,
            )

            report = load_upstream_changes_report(metadata_db_path)

        self.assertEqual(report.status, "unavailable")
        self.assertIn("etl_fetch_history", report.message)

    def test_report_detects_changes_deterministically_and_computes_cadence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_db_path = _write_metadata_history(
                Path(temp_dir) / "db" / "fec-metadata.sqlite",
                [
                    (
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
                    (
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
                    (
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
                    (
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
                    (
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
                    (
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
                    (
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
                    (
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
                    (
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
                    (
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
                ],
            )

            report = load_upstream_changes_report(metadata_db_path)

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
