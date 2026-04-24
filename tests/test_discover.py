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

    def test_returns_none_when_no_year_headings(self):
        from sep_analyzer import _parse_next_sep_date
        self.assertIsNone(_parse_next_sep_date("<html>nothing</html>", date(2026, 1, 1)))

    def test_returns_none_when_no_future_sep(self):
        from sep_analyzer import _parse_next_sep_date
        self.assertIsNone(_parse_next_sep_date(self.html, date(2030, 1, 1)))

    def test_returns_first_future_sep_from_april(self):
        from sep_analyzer import _parse_next_sep_date
        result = _parse_next_sep_date(self.html, date(2026, 4, 1))
        self.assertEqual(result, date(2026, 6, 17))

    def test_advances_after_a_meeting_passes(self):
        from sep_analyzer import _parse_next_sep_date
        result = _parse_next_sep_date(self.html, date(2026, 6, 18))
        self.assertEqual(result, date(2026, 9, 16))

    def test_meeting_day_itself_qualifies(self):
        # >= today, not > today: today == meeting day should return that day.
        from sep_analyzer import _parse_next_sep_date
        result = _parse_next_sep_date(self.html, date(2026, 6, 17))
        self.assertEqual(result, date(2026, 6, 17))


if __name__ == "__main__":
    unittest.main()
