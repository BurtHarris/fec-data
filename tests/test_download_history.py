import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from pipeline.download import build_plan, download_one
from pipeline.metadata_store import DownloadStatusRecord, InMemoryDownloadMetadataStore


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


class DownloadHistoryTests(unittest.TestCase):
    def test_downloaded_fetch_persists_history_and_current_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = InMemoryDownloadMetadataStore()
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
                result = download_one(plan, force=False, progress_interval=999.0, metadata_store=store)

            history = store.load_successful_fetch_history()
            statuses = store.list_download_statuses()
            has_json_sidecar = any(path.suffix == ".json" for path in plan.zip_path.parent.iterdir())

        self.assertIn("downloaded indiv24.zip", result)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].cycle, 2024)
        self.assertEqual(history[0].table_name, "indiv")
        self.assertEqual(history[0].fetch_status, "downloaded")
        self.assertEqual(history[0].http_status, 200)
        self.assertEqual(history[0].content_length, 6)
        self.assertEqual(history[0].last_modified, "Mon, 01 Jan 2024 00:00:00 GMT")
        self.assertEqual(history[0].etag, "etag-1")
        self.assertEqual(history[0].local_file_size, 6)
        self.assertIsNone(history[0].error_text)
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0].fetch_status, "downloaded")
        self.assertEqual(statuses[0].bytes_downloaded, 6)
        self.assertEqual(statuses[0].progress_pct, 100.0)
        self.assertFalse(has_json_sidecar)

    def test_not_modified_fetch_uses_cached_sqlite_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = InMemoryDownloadMetadataStore(
                statuses=(
                    DownloadStatusRecord(
                        cycle=2024,
                        table_name="indiv",
                        zip_name="indiv24.zip",
                        source_url="https://example.test/indiv24.zip",
                        fetch_status="downloaded",
                        http_status=200,
                        content_length=10,
                        response_date="Mon, 01 Jan 2024 00:00:01 GMT",
                        last_modified="Mon, 01 Jan 2024 00:00:00 GMT",
                        etag="etag-1",
                        local_file_size=10,
                        bytes_downloaded=10,
                        progress_pct=100.0,
                        download_started_at="2024-01-01T00:00:00Z",
                        download_completed_at="2024-01-01T00:00:01Z",
                        last_attempt_at="2024-01-01T00:00:01Z",
                        updated_at="2024-01-01T00:00:01Z",
                    ),
                )
            )
            plan = build_plan(2024, "indiv", root)
            plan.zip_path.parent.mkdir(parents=True, exist_ok=True)
            plan.zip_path.write_bytes(b"cached-zip")
            error = HTTPError(plan.url, 304, "Not Modified", {}, None)

            with patch("pipeline.download.urlopen", side_effect=error):
                result = download_one(plan, force=False, progress_interval=999.0, metadata_store=store)

            history = store.load_successful_fetch_history()
            statuses = store.list_download_statuses()

        self.assertEqual(result, "skipped indiv24.zip (not modified)")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].fetch_status, "not_modified")
        self.assertEqual(history[0].http_status, 304)
        self.assertEqual(history[0].content_length, 10)
        self.assertEqual(history[0].local_file_size, len(b"cached-zip"))
        self.assertEqual(statuses[0].fetch_status, "not_modified")
        self.assertEqual(statuses[0].progress_pct, 100.0)
        self.assertEqual(statuses[0].etag, "etag-1")

    def test_failed_fetch_persists_history_row_before_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = InMemoryDownloadMetadataStore()
            plan = build_plan(2024, "indiv", root)
            error = HTTPError(plan.url, 500, "Server Error", {"Date": "Mon, 01 Jan 2024 00:00:01 GMT"}, None)

            with patch("pipeline.download.urlopen", side_effect=error):
                with self.assertRaises(RuntimeError) as raised:
                    download_one(plan, force=False, progress_interval=999.0, metadata_store=store)

            history = store.load_successful_fetch_history()
            statuses = store.list_download_statuses()

        self.assertEqual(str(raised.exception), "failed indiv24.zip: HTTP 500")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].fetch_status, "failed")
        self.assertEqual(history[0].http_status, 500)
        self.assertIsNone(history[0].local_file_size)
        self.assertEqual(history[0].error_text, "HTTP Error 500: Server Error")
        self.assertEqual(statuses[0].fetch_status, "failed")
        self.assertEqual(statuses[0].http_status, 500)


if __name__ == "__main__":
    unittest.main()
