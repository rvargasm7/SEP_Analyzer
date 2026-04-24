"""Tests for parse_sep_numbers() — table and prose extraction."""
import unittest

from sep_analyzer import parse_sep_numbers, DEMO_SEP_TEXT


class TestEmptyInput(unittest.TestCase):
    def test_empty_text_returns_only_hike_dot_defaults(self):
        result = parse_sep_numbers("")
        self.assertEqual(result, {"dots_hike_count": 0, "dots_no_cuts_count": 0})

    def test_garbage_text_does_not_raise(self):
        parse_sep_numbers("no economic projections here")


class TestTableFormat(unittest.TestCase):
    """
    Simulates the real Fed SEP PDF extraction format — concatenated labels
    followed by numeric columns (2026, 2027, 2028, Longer run).
    """

    TABLE_TEXT = (
        "ChangeinrealGDP 2.4 2.3 2.1 2.0\n"
        "Unemploymentrate 4.4 4.3 4.1 4.1\n"
        "CorePCEinflation4 2.7 2.2 2.0\n"
        "Federalfundsrate 3.4 3.1 3.1 3.1\n"
    )

    def test_extracts_gdp(self):
        result = parse_sep_numbers(self.TABLE_TEXT)
        self.assertEqual(result["gdp_2026"], 2.4)
        self.assertEqual(result["gdp_2027"], 2.3)

    def test_extracts_unemployment(self):
        result = parse_sep_numbers(self.TABLE_TEXT)
        self.assertEqual(result["unemployment_2026"], 4.4)
        self.assertEqual(result["unemployment_2027"], 4.3)

    def test_extracts_core_pce(self):
        result = parse_sep_numbers(self.TABLE_TEXT)
        self.assertEqual(result["core_pce_2026"], 2.7)
        self.assertEqual(result["core_pce_2027"], 2.2)

    def test_extracts_fed_funds(self):
        result = parse_sep_numbers(self.TABLE_TEXT)
        self.assertEqual(result["fed_funds_median_2026"], 3.4)
        self.assertEqual(result["fed_funds_median_2027"], 3.1)
        self.assertEqual(result["fed_funds_longer_run"], 3.1)


class TestHikeDotDetection(unittest.TestCase):
    def test_range_high_above_midpoint_signals_hike(self):
        # Current rate midpoint = 3.625. Range high 4.1 > 3.625 → hike expected.
        text = "Federal funds rate 3.4-4.1 3.1-3.9 3.0-3.5"
        result = parse_sep_numbers(text)
        self.assertEqual(result["dots_hike_count"], 1)

    def test_range_high_at_or_below_midpoint_no_hike(self):
        # Range high 3.6 <= 3.625 midpoint → no hike expected.
        text = "Federal funds rate 3.3-3.6 3.0-3.5 2.8-3.2"
        result = parse_sep_numbers(text)
        self.assertEqual(result["dots_hike_count"], 0)

    def test_no_range_data_defaults_to_zero(self):
        result = parse_sep_numbers("no range data present")
        self.assertEqual(result["dots_hike_count"], 0)


class TestProseFallback(unittest.TestCase):
    """
    When the table regex doesn't match (e.g. pasted text has spaces in labels),
    prose patterns should still extract key numbers.
    """

    def test_demo_text_extracts_fed_funds_median_2026(self):
        # The demo prose includes "rates at 3.875 for 2026" and a median mention.
        result = parse_sep_numbers(DEMO_SEP_TEXT)
        self.assertIn("fed_funds_median_2026", result)
        self.assertIsNotNone(result["fed_funds_median_2026"])

    def test_demo_text_extracts_longer_run(self):
        result = parse_sep_numbers(DEMO_SEP_TEXT)
        self.assertEqual(result["fed_funds_longer_run"], 3.0)

    def test_demo_text_extracts_gdp_2026(self):
        result = parse_sep_numbers(DEMO_SEP_TEXT)
        self.assertIn("gdp_2026", result)
        self.assertIsNotNone(result["gdp_2026"])

    def test_demo_text_populates_defaults(self):
        result = parse_sep_numbers(DEMO_SEP_TEXT)
        self.assertIn("dots_hike_count", result)
        self.assertIn("dots_no_cuts_count", result)


if __name__ == "__main__":
    unittest.main()
