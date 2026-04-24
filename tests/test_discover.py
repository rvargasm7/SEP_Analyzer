"""Tests for fetch_next_sep() and --discover CLI flag."""
import unittest
from datetime import date
import os

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "fomccalendars.htm"
)

from sep_analyzer import SEP_FALLBACK_DATES


class TestFallbackList(unittest.TestCase):
    def test_fallback_list_is_sorted(self):
        self.assertEqual(SEP_FALLBACK_DATES, sorted(SEP_FALLBACK_DATES))

    def test_fallback_contains_sep_months_only(self):
        for d in SEP_FALLBACK_DATES:
            self.assertIn(d.month, {3, 6, 9, 12})

    def test_fallback_covers_at_least_2026_and_2027(self):
        years = {d.year for d in SEP_FALLBACK_DATES}
        self.assertIn(2026, years)
        self.assertIn(2027, years)


class TestParser(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE_PATH) as f:
            self.html = f.read()

    def test_returns_none_for_empty_html(self):
        from sep_analyzer import _parse_next_sep_date
        self.assertIsNone(_parse_next_sep_date("", date(2026, 1, 1)))

    def test_returns_sep_month_only(self):
        from sep_analyzer import _parse_next_sep_date
        result = _parse_next_sep_date(self.html, date(2026, 1, 1))
        self.assertIsNotNone(result)
        self.assertIn(result.month, {3, 6, 9, 12})

    def test_returns_date_on_or_after_today(self):
        from sep_analyzer import _parse_next_sep_date
        today = date(2026, 4, 1)
        result = _parse_next_sep_date(self.html, today)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result, today)


if __name__ == "__main__":
    unittest.main()
