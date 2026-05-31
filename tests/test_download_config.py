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


if __name__ == "__main__":
    unittest.main()
