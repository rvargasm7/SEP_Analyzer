# Auto-discover next SEP release — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded March 2026 URL in `run_sep.sh` with runtime auto-discovery of the next SEP-producing FOMC meeting, and gate the polling loop on meeting day.

**Architecture:** Fetch the Fed's FOMC calendar page at run time, parse the next SEP-producing meeting date (Mar/Jun/Sep/Dec), and expose the result via a new `--discover` CLI flag on `sep_analyzer.py`. `run_sep.sh` calls `--discover`, parses a single-line response, and either exits with a "next date" message or enters the polling loop. On fetch or parse failure, fall back to a hardcoded list of known 2026–2027 meeting dates.

**Tech Stack:** Python 3 stdlib (`urllib.request`, `re`, `unittest`, `datetime`), bash.

**File Structure:**
- `sep_analyzer.py` — add discovery constants, parser, fetcher, public `fetch_next_sep()`, and `--discover` CLI branch.
- `run_sep.sh` — replace hardcoded URL/filename with a call to `--discover`, branch on `NOT_TODAY` / `POLL`.
- `tests/__init__.py` — marker for unittest discovery.
- `tests/test_discover.py` — unit tests for parser, fetcher, fallback, and CLI output.
- `tests/fixtures/fomccalendars.htm` — saved copy of the Fed FOMC calendar page for parser tests.

---

### Task 1: Create tests directory and download HTML fixture

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/fixtures/fomccalendars.htm` (downloaded)

- [ ] **Step 1: Create tests directory structure**

Run:
```bash
mkdir -p tests/fixtures
touch tests/__init__.py
```

- [ ] **Step 2: Download the Fed FOMC calendar page as a test fixture**

Run:
```bash
curl -sL "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm" \
  -o tests/fixtures/fomccalendars.htm
```

Verify the download worked:
```bash
wc -c tests/fixtures/fomccalendars.htm
grep -c "FOMC" tests/fixtures/fomccalendars.htm
```

Expected: file size is at least ~20 KB; grep count is at least 1.

- [ ] **Step 3: Commit the fixture**

```bash
git add tests/__init__.py tests/fixtures/fomccalendars.htm
git commit -m "Add Fed FOMC calendar HTML as test fixture"
```

---

### Task 2: Add SEP month constants and fallback list

**Files:**
- Modify: `sep_analyzer.py` (add constants after the existing CONFIG block)
- Create: `tests/test_discover.py`

- [ ] **Step 1: Write a failing test for the fallback list shape**

Create `tests/test_discover.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_discover -v`
Expected: ImportError ("cannot import name 'SEP_FALLBACK_DATES'").

- [ ] **Step 3: Update the datetime import in sep_analyzer.py**

Find the existing import near the top of `sep_analyzer.py`:

```python
from datetime import datetime
```

Replace it with:

```python
from datetime import datetime, date
```

- [ ] **Step 4: Add discovery constants to sep_analyzer.py**

Find the existing block:

```python
# ── CONFIG ────────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-20250514"
```

Add immediately after that line (before the BASELINE block):

```python
# ── SEP DISCOVERY ─────────────────────────────────────────────────────────────
# The Fed releases a Summary of Economic Projections at the March, June,
# September, and December FOMC meetings. These are two-day meetings; the
# SEP drops on the final day.
SEP_MONTHS = {3, 6, 9, 12}

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

# Hardcoded fallback — used only when the live calendar page can't be
# fetched or parsed. Update this list each time the Fed publishes a new
# year's FOMC schedule. Each date is the final day of a two-day SEP meeting.
SEP_FALLBACK_DATES = [
    date(2026, 3, 18),
    date(2026, 6, 17),
    date(2026, 9, 16),
    date(2026, 12, 9),
    date(2027, 3, 17),
    date(2027, 6, 16),
    date(2027, 9, 22),
    date(2027, 12, 15),
]

CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_discover -v`
Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add sep_analyzer.py tests/test_discover.py
git commit -m "Add SEP month constants and fallback date list"
```

---

### Task 3: Implement HTML parser

**Files:**
- Modify: `sep_analyzer.py` (add `_parse_next_sep_date`)
- Modify: `tests/test_discover.py` (add parser tests)

- [ ] **Step 1: Add failing parser tests**

Open `tests/test_discover.py` and add these lines at the top (below the existing `from datetime import date` line):

```python
import os

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "fomccalendars.htm"
)
```

Then append a new test class after `TestFallbackList`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_discover -v`
Expected: 3 FAIL in TestParser ("cannot import name '_parse_next_sep_date'").

- [ ] **Step 3: Implement the parser**

In `sep_analyzer.py`, find the new `# ── SEP DISCOVERY` block added in Task 2. Immediately below the `CALENDAR_URL = ...` line, add:

```python
def _parse_next_sep_date(html: str, today: date):
    """
    Parse the Fed FOMC calendar HTML and return the next SEP-producing
    meeting date (today or later), or None if no such date is found.

    SEP-producing meetings occur in March, June, September, and December.
    The SEP is published on the final day of each two-day meeting, so
    this returns the higher day of each date range.
    """
    if not html:
        return None

    # Locate year sections. The Fed page groups meetings under headings
    # like "2026 FOMC Meetings". We use those to establish year context.
    year_heading = re.compile(r"(\d{4})\s*FOMC\s*Meetings", re.IGNORECASE)
    year_matches = list(year_heading.finditer(html))
    if not year_matches:
        return None

    candidates = []

    for i, match in enumerate(year_matches):
        year = int(match.group(1))
        section_start = match.end()
        section_end = (
            year_matches[i + 1].start()
            if i + 1 < len(year_matches)
            else len(html)
        )
        section = html[section_start:section_end]

        # Match "Month DD-DD" where the separator is "-" or en-dash "–".
        meeting_pattern = re.compile(
            r"(january|february|march|april|may|june|july|august|"
            r"september|october|november|december)\s+"
            r"(\d{1,2})\s*[-–]\s*(\d{1,2})",
            re.IGNORECASE,
        )
        for mm in meeting_pattern.finditer(section):
            month = MONTH_NAMES.get(mm.group(1).lower())
            if month not in SEP_MONTHS:
                continue
            day_second = int(mm.group(3))
            try:
                meeting_date = date(year, month, day_second)
            except ValueError:
                continue
            if meeting_date >= today:
                candidates.append(meeting_date)

    return min(candidates) if candidates else None
```

Note: `re` is already imported at the top of `sep_analyzer.py` — do not re-import it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_discover -v`
Expected: 6 tests PASS.

If TestParser tests fail with `AssertionError: None is not an instance...`, the regex did not match anything in the fixture. Open `tests/fixtures/fomccalendars.htm` and locate a 2026 or 2027 meeting entry to see the exact format. Adjust the `year_heading` regex (the actual heading phrasing) or the `meeting_pattern` regex (the separator or whitespace between month and days) and re-run. The parser must tolerate the real page structure, not an idealized one.

- [ ] **Step 5: Commit**

```bash
git add sep_analyzer.py tests/test_discover.py
git commit -m "Implement Fed calendar HTML parser for next SEP date"
```

---

### Task 4: Implement fetch_next_sep() with fallback

**Files:**
- Modify: `sep_analyzer.py` (add `_fetch_calendar_html`, `fetch_next_sep`)
- Modify: `tests/test_discover.py` (add tests with mocked fetch)

- [ ] **Step 1: Add failing tests for fetch_next_sep**

Open `tests/test_discover.py`. Add this import near the top of the file (after `import os`):

```python
from unittest.mock import patch
```

Append this new test class after `TestParser`:

```python
class TestFetchNextSep(unittest.TestCase):
    def test_uses_parsed_date_when_fetch_succeeds(self):
        from sep_analyzer import fetch_next_sep
        fake_html = (
            "<html><body>"
            "<h3>2026 FOMC Meetings</h3>"
            "<div>June 16-17</div>"
            "<div>September 15-16</div>"
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_discover -v`
Expected: 4 FAIL in TestFetchNextSep ("cannot import name 'fetch_next_sep'").

- [ ] **Step 3: Implement the fetch wrapper and public function**

In `sep_analyzer.py`, add `urllib.request` to the imports at the top of the file. Find:

```python
import argparse
import getpass
```

Add immediately below:

```python
import urllib.request
```

Then, at the end of the `# ── SEP DISCOVERY` block (below `_parse_next_sep_date`), add:

```python
def _fetch_calendar_html(url: str = CALENDAR_URL, timeout: float = 10.0) -> str:
    """Fetch the Fed FOMC calendar page. Raises OSError on network error."""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_next_sep(today=None):
    """
    Return the next SEP-producing FOMC meeting date (today or later).

    Tries the live Fed calendar first. On fetch failure, parse failure,
    or an empty parse result, falls back to SEP_FALLBACK_DATES. If the
    fallback is also exhausted, raises RuntimeError.
    """
    if today is None:
        today = date.today()

    try:
        html = _fetch_calendar_html()
        parsed = _parse_next_sep_date(html, today)
        if parsed is not None:
            return parsed
    except (OSError, ValueError):
        pass

    for d in SEP_FALLBACK_DATES:
        if d >= today:
            return d

    raise RuntimeError(
        "No future SEP meeting found. Update SEP_FALLBACK_DATES in "
        "sep_analyzer.py with the next year's FOMC schedule."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_discover -v`
Expected: 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sep_analyzer.py tests/test_discover.py
git commit -m "Add fetch_next_sep() with calendar fetch and fallback list"
```

---

### Task 5: Add --discover CLI flag

**Files:**
- Modify: `sep_analyzer.py` (add `--discover` flag and `_discover_command`)
- Modify: `tests/test_discover.py` (add subprocess tests)

- [ ] **Step 1: Add failing tests for the CLI flag**

Open `tests/test_discover.py`. Add these imports near the top of the file:

```python
import subprocess
import sys
```

Append this test class after `TestFetchNextSep`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_discover -v`
Expected: TestDiscoverCLI FAILS (argparse rejects `--discover`, non-zero exit).

- [ ] **Step 3: Implement the --discover flag**

In `sep_analyzer.py`, find the `main()` function's argparse setup:

```python
def main():
    parser = argparse.ArgumentParser(description="SEP Analyzer — FOMC Projections Scanner")
    parser.add_argument("pdf", nargs="?", help="Path to SEP PDF file")
    parser.add_argument("--text", help="Raw text instead of PDF")
    parser.add_argument("--demo", action="store_true", help="Run with demo data")
    args = parser.parse_args()

    ensure_api_key()
```

Replace with:

```python
def main():
    parser = argparse.ArgumentParser(description="SEP Analyzer — FOMC Projections Scanner")
    parser.add_argument("pdf", nargs="?", help="Path to SEP PDF file")
    parser.add_argument("--text", help="Raw text instead of PDF")
    parser.add_argument("--demo", action="store_true", help="Run with demo data")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Print next SEP date (NOT_TODAY <date>) or poll URL (POLL <url> <filename>) and exit",
    )
    args = parser.parse_args()

    if args.discover:
        _discover_command()
        return

    ensure_api_key()
```

Then add this helper function immediately above `if __name__ == "__main__":`:

```python
def _discover_command() -> None:
    """Print a single-line directive for run_sep.sh and exit."""
    next_date = fetch_next_sep()
    today = date.today()
    if next_date == today:
        yyyymmdd = next_date.strftime("%Y%m%d")
        url = (
            "https://www.federalreserve.gov/monetarypolicy/files/"
            f"fomcprojtabl{yyyymmdd}.pdf"
        )
        filename = f"sep_{yyyymmdd}.pdf"
        print(f"POLL {url} {filename}")
    else:
        print(f"NOT_TODAY {next_date.isoformat()}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_discover -v`
Expected: 13 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sep_analyzer.py tests/test_discover.py
git commit -m "Add --discover CLI flag to sep_analyzer.py"
```

---

### Task 6: Update run_sep.sh to use --discover

**Files:**
- Modify: `run_sep.sh` (replace hardcoded URL/filename with dynamic discovery)

- [ ] **Step 1: Rewrite run_sep.sh**

Replace the entire contents of `run_sep.sh` with:

```bash
#!/bin/bash
# Polls for the next FOMC SEP PDF and runs the analyzer when it drops.
# The next meeting date is discovered at run time from the Fed's FOMC
# calendar page. On non-meeting days, prints the next date and exits.

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

PYTHON="/opt/anaconda3/bin/python3"

# Load API key: .env file → environment → interactive prompt
if [ -z "$ANTHROPIC_API_KEY" ] && [ -f .env ]; then
    export ANTHROPIC_API_KEY="$(cat .env | tr -d '[:space:]')"
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "─── API KEY REQUIRED ────────────────────────────────────"
    echo "  Enter your Anthropic API key (will not be displayed)."
    echo "  It will NOT be stored — only used for this session."
    echo ""
    read -s -p "  ANTHROPIC_API_KEY: " ANTHROPIC_API_KEY
    echo ""
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        echo "  No key provided. Exiting."
        exit 1
    fi
    export ANTHROPIC_API_KEY
    echo "  Key set for this session."
    echo ""
fi

# Discover the next SEP-producing FOMC meeting.
# sep_analyzer.py --discover prints exactly one of:
#   NOT_TODAY 2026-06-17
#   POLL <url> <filename>
DISCOVERY="$("$PYTHON" sep_analyzer.py --discover)"
DISCOVERY_STATUS=$?
if [ $DISCOVERY_STATUS -ne 0 ] || [ -z "$DISCOVERY" ]; then
    echo "Discovery failed (exit $DISCOVERY_STATUS). Check your network."
    echo "Output: $DISCOVERY"
    exit 1
fi

read -r VERB ARG1 ARG2 <<< "$DISCOVERY"

case "$VERB" in
    NOT_TODAY)
        echo "Next SEP release: $ARG1"
        echo "Run this script again on that day to download and analyze."
        exit 0
        ;;
    POLL)
        URL="$ARG1"
        PDF="$ARG2"
        ;;
    *)
        echo "Unexpected discovery output: $DISCOVERY"
        exit 1
        ;;
esac

# If the PDF already exists locally, skip polling and analyze immediately.
if [ -f "$PDF" ]; then
    echo "Found $PDF locally. Running analyzer..."
    echo ""
    "$PYTHON" sep_analyzer.py "$PDF"
    exit 0
fi

echo "Waiting for SEP to drop..."
echo "URL: $URL"
echo "Checking every 30 seconds. Press Ctrl+C to stop."
echo ""

while true; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL")
    NOW=$(date "+%H:%M:%S")
    if [ "$STATUS" = "200" ]; then
        echo "[$NOW] PDF is live! Downloading..."
        curl -sL "$URL" -o "$PDF"
        echo "Saved to $PDF"
        echo ""
        "$PYTHON" sep_analyzer.py "$PDF"
        exit 0
    else
        echo "[$NOW] Not yet ($STATUS). Retrying in 30s..."
        sleep 30
    fi
done
```

- [ ] **Step 2: Manual smoke test (NOT_TODAY path)**

Since today is 2026-04-23 and the next SEP is June 17, 2026, the script should exit immediately with a "Next SEP release" message.

Run:
```bash
./run_sep.sh; echo "exit: $?"
```

Expected output includes a line like `Next SEP release: 2026-06-17` followed by `exit: 0`. The script must NOT enter a polling loop.

- [ ] **Step 3: Commit**

```bash
git add run_sep.sh
git commit -m "Wire run_sep.sh to use --discover for dynamic URL"
```

---

### Task 7: Verify fallback behavior and full test suite

**Files:** (none — verification only)

- [ ] **Step 1: Simulate fetch failure and confirm fallback**

Run:
```bash
python3 -c "
from unittest.mock import patch
from sep_analyzer import fetch_next_sep
with patch('sep_analyzer._fetch_calendar_html', side_effect=OSError('simulated')):
    print(fetch_next_sep())
"
```

Expected: prints the earliest date from `SEP_FALLBACK_DATES` that is today-or-later (e.g., `2026-06-17`).

- [ ] **Step 2: Run the full test suite**

Run: `python3 -m unittest discover tests -v`
Expected: all 13 tests PASS.

- [ ] **Step 3: No commit needed**

This task is verification only — nothing to commit.
