import tempfile
import unittest
from pathlib import Path

from pipeline.data_scope import (
    load_data_scope_config,
    normalize_data_scope_config,
    save_data_scope_config,
    snapshot_data_scope,
)


class DataScopeConfigServiceTests(unittest.TestCase):
    def test_normalize_rejects_facts_outside_coverage(self) -> None:
        raw = {
            "coverage": "2022-2024",
            "facts": "2020-2024",
            "table_groups": {
                "dimensions": ["cm", "cn", "ccl", "weball"],
                "facts": ["indiv", "oppexp", "oth", "pas2"],
            },
        }

        with self.assertRaisesRegex(SystemExit, "facts range must be fully contained within coverage range"):
            normalize_data_scope_config(raw)

    def test_save_and_load_roundtrip_normalizes_case_and_deduplicates(self) -> None:
        raw = {
            "coverage": "2022-2026",
            "facts": "2024-2026",
            "table_groups": {
                "dimensions": ["CM", "cn", "CM", "weball"],
                "facts": ["INDIV", "pas2", "pas2"],
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "data_scope.yml"
            save_data_scope_config(target, raw)
            loaded = load_data_scope_config(target)

        self.assertEqual(loaded["coverage"], "2022-2026")
        self.assertEqual(loaded["facts"], "2024-2026")
        self.assertEqual(loaded["table_groups"]["dimensions"], ["cm", "cn", "weball"])
        self.assertEqual(loaded["table_groups"]["facts"], ["indiv", "pas2"])

    def test_snapshot_is_immutable_copy_of_normalized_config(self) -> None:
        raw = {
            "coverage": "2026",
            "facts": "2026",
            "table_groups": {
                "dimensions": ["cm"],
                "facts": ["indiv"],
            },
        }

        snap = snapshot_data_scope(raw)
        snap["table_groups"]["dimensions"].append("cn")

        self.assertEqual(raw["table_groups"]["dimensions"], ["cm"])


if __name__ == "__main__":
    unittest.main()
