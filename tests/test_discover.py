"""Tests for fetch_next_sep() and --discover CLI flag."""
import unittest
from datetime import date

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


if __name__ == "__main__":
    unittest.main()
