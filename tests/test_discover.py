"""Tests for fetch_next_sep() and --discover CLI flag."""
import unittest
from datetime import date
import os
import subprocess
import sys
from unittest.mock import patch

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


class TestFetchNextSep(unittest.TestCase):
    def test_uses_parsed_date_when_fetch_succeeds(self):
        from sep_analyzer import fetch_next_sep
        fake_html = (
            "<html><body>"
            "<h3>2026 FOMC Meetings</h3>"
            "<div class='fomc-meeting__month'><strong>June</strong></div>"
            "<div class='fomc-meeting__date'>16-17</div>"
            "<div class='fomc-meeting__month'><strong>September</strong></div>"
            "<div class='fomc-meeting__date'>15-16</div>"
            "</body></html>"
        )
        with patch("sep_analyzer._fetch_calendar_html", return_value=fake_html):
            result = fetch_next_sep(today=date(2026, 4, 23))
        self.assertEqual(result, date(2026, 6, 17))

    def test_uses_fallback_when_fetch_raises(self):
        from sep_analyzer import fetch_next_sep
        with patch("sep_analyzer._fetch_calendar_html",
                   side_effect=OSError("network down")):
            result = fetch_next_sep(today=date(2026, 4, 23))
        self.assertEqual(result, date(2026, 6, 17))

    def test_uses_fallback_when_parse_returns_none(self):
        from sep_analyzer import fetch_next_sep
        with patch("sep_analyzer._fetch_calendar_html",
                   return_value="<html></html>"):
            result = fetch_next_sep(today=date(2026, 4, 23))
        self.assertEqual(result, date(2026, 6, 17))

    def test_raises_when_fallback_exhausted(self):
        from sep_analyzer import fetch_next_sep
        far_future = date(2100, 1, 1)
        with patch("sep_analyzer._fetch_calendar_html",
                   side_effect=OSError("boom")):
            with self.assertRaises(RuntimeError):
                fetch_next_sep(today=far_future)


class TestDiscoverCLI(unittest.TestCase):
    def _run(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return subprocess.run(
            [sys.executable, "sep_analyzer.py", "--discover"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_discover_exits_zero(self):
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_discover_emits_single_line(self):
        result = self._run()
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1, f"expected one line, got: {lines}")

    def test_discover_line_has_expected_prefix(self):
        result = self._run()
        line = result.stdout.strip().splitlines()[-1]
        self.assertTrue(
            line.startswith("NOT_TODAY ") or line.startswith("POLL "),
            f"unexpected prefix: {line!r}",
        )


if __name__ == "__main__":
    unittest.main()
