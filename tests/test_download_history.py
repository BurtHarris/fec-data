import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from pipeline.download import build_plan, download_one


class _FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str], status: int = 200) -> None:
        self._body = body
        self._offset = 0
        self.headers = headers
        self.status = status

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self, size: int) -> bytes:
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


def _history_rows(metadata_db_path: Path) -> list[tuple[object, ...]]:
    conn = sqlite3.connect(metadata_db_path)
    try:
        return conn.execute(
            """
            SELECT
                cycle,
                table_name,
                zip_name,
                fetch_status,
                http_status,
                content_length,
                last_modified,
                etag,
                local_file_size,
                error_text
            FROM etl_fetch_history
            ORDER BY rowid
            """
        ).fetchall()
    finally:
        conn.close()


class DownloadHistoryTests(unittest.TestCase):
    def test_downloaded_fetch_persists_history_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = build_plan(2024, "indiv", root)
            body = b"abcdef"
            response = _FakeResponse(
                body,
                {
                    "Content-Length": str(len(body)),
                    "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
                    "ETag": "etag-1",
                    "Date": "Mon, 01 Jan 2024 00:00:01 GMT",
                },
            )

            with patch("pipeline.download.urlopen", return_value=response):
                result = download_one(plan, force=False, progress_interval=999.0)

            rows = _history_rows(plan.metadata_db_path)

        self.assertIn("downloaded indiv24.zip", result)
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0],
            (
                2024,
                "indiv",
                "indiv24.zip",
                "downloaded",
                200,
                6,
                "Mon, 01 Jan 2024 00:00:00 GMT",
                "etag-1",
                6,
                None,
            ),
        )

    def test_not_modified_fetch_persists_history_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = build_plan(2024, "indiv", root)
            plan.zip_path.parent.mkdir(parents=True, exist_ok=True)
            plan.zip_path.write_bytes(b"cached-zip")
            plan.meta_path.write_text(
                '{\n  "url": "https://example.test/indiv24.zip",\n  "etag": "etag-1",\n  "last_modified": "Mon, 01 Jan 2024 00:00:00 GMT",\n  "content_length": "10"\n}\n',
                encoding="utf-8",
            )
            error = HTTPError(plan.url, 304, "Not Modified", {}, None)

            with patch("pipeline.download.urlopen", side_effect=error):
                result = download_one(plan, force=False, progress_interval=999.0)

            rows = _history_rows(plan.metadata_db_path)

        self.assertEqual(result, "skipped indiv24.zip (not modified)")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][3], "not_modified")
        self.assertEqual(rows[0][4], 304)
        self.assertEqual(rows[0][5], 10)
        self.assertEqual(rows[0][8], len(b"cached-zip"))

    def test_failed_fetch_persists_history_row_before_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = build_plan(2024, "indiv", root)
            error = HTTPError(plan.url, 500, "Server Error", {"Date": "Mon, 01 Jan 2024 00:00:01 GMT"}, None)

            with patch("pipeline.download.urlopen", side_effect=error):
                with self.assertRaises(RuntimeError) as raised:
                    download_one(plan, force=False, progress_interval=999.0)

            rows = _history_rows(plan.metadata_db_path)

        self.assertEqual(str(raised.exception), "failed indiv24.zip: HTTP 500")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][3], "failed")
        self.assertEqual(rows[0][4], 500)
        self.assertIsNone(rows[0][8])
        self.assertEqual(rows[0][9], "HTTP Error 500: Server Error")


if __name__ == "__main__":
    unittest.main()
