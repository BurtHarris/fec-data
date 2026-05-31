import unittest

from pipeline.download import resolve_cycle_tables


class ResolveCycleTablesValidationTests(unittest.TestCase):
    def test_invalid_coverage_year_range_raises_system_exit(self) -> None:
        config = {
            "coverage": "20x0",
            "facts": "2026",
            "table_groups": {
                "dimensions": ["ccl", "cm", "cn", "weball"],
                "facts": ["indiv", "oppexp", "oth", "pas2"],
            },
        }

        with self.assertRaisesRegex(SystemExit, "coverage must be a year or year range string"):
            resolve_cycle_tables(2026, config)

    def test_boolean_coverage_value_raises_system_exit(self) -> None:
        config = {
            "coverage": True,
            "facts": "2026",
            "table_groups": {
                "dimensions": ["ccl", "cm", "cn", "weball"],
                "facts": ["indiv", "oppexp", "oth", "pas2"],
            },
        }

        with self.assertRaisesRegex(SystemExit, "coverage must be a year or year range string"):
            resolve_cycle_tables(2026, config)

    def test_invalid_facts_year_raises_system_exit(self) -> None:
        config = {
            "coverage": "2026",
            "facts": "20x6",
            "table_groups": {
                "dimensions": ["ccl", "cm", "cn", "weball"],
                "facts": ["indiv", "oppexp", "oth", "pas2"],
            },
        }

        with self.assertRaisesRegex(SystemExit, "facts must be a year or year range string"):
            resolve_cycle_tables(2026, config)

    def test_reversed_facts_range_raises_system_exit(self) -> None:
        config = {
            "coverage": "2026",
            "facts": "2028-2026",
            "table_groups": {
                "dimensions": ["ccl", "cm", "cn", "weball"],
                "facts": ["indiv", "oppexp", "oth", "pas2"],
            },
        }

        with self.assertRaisesRegex(SystemExit, "facts start year must not be greater than end year"):
            resolve_cycle_tables(2026, config)

    def test_cycle_2026_resolves_normalized_deduplicated_tables_in_order(self) -> None:
        config = {
            "coverage": "2026",
            "facts": "2026",
            "table_groups": {
                "dimensions": ["CM", "ccl", "weball"],
                "facts": ["indiv", "CM", "pas2"],
            },
        }

        resolved = resolve_cycle_tables(2026, config)

        self.assertEqual(resolved, ["cm", "ccl", "weball", "indiv", "pas2"])

    def test_cycle_outside_coverage_returns_empty_list(self) -> None:
        config = {
            "coverage": "2024",
            "facts": "2024",
            "table_groups": {
                "dimensions": ["ccl", "cm", "cn", "weball"],
                "facts": ["indiv", "oppexp", "oth", "pas2"],
            },
        }

        resolved = resolve_cycle_tables(2026, config)

        self.assertEqual(resolved, [])

    def test_cycle_2026_uses_dimensions_only_when_facts_excluded(self) -> None:
        config = {
            "coverage": "2024-2026",
            "facts": "2024",
            "table_groups": {
                "dimensions": ["ccl", "CM", "weball"],
                "facts": ["indiv", "oppexp"],
            },
        }

        resolved = resolve_cycle_tables(2026, config)

        self.assertEqual(resolved, ["ccl", "cm", "weball"])

    def test_non_string_table_group_entry_raises_system_exit(self) -> None:
        config = {
            "coverage": "2026",
            "facts": "2026",
            "table_groups": {
                "dimensions": ["ccl", 42, "weball"],
                "facts": ["indiv", "oppexp"],
            },
        }

        with self.assertRaisesRegex(SystemExit, "table_groups.dimensions entries must be strings"):
            resolve_cycle_tables(2026, config)


if __name__ == "__main__":
    unittest.main()
