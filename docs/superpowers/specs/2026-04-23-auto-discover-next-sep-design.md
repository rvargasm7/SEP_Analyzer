# Auto-discover next SEP release — Design

## Problem

`run_sep.sh` hardcodes the March 2026 FOMC projection URL
(`fomcprojtabl20260318.pdf`) and the local filename
(`sep_march2026.pdf`). SEPs are released four times per year
(Mar/Jun/Sep/Dec FOMC meetings), so the next release (June 2026) will
not be caught without a code change. Goal: automatically discover the
next SEP-producing FOMC meeting and only poll on meeting day.

## Approach

**Option A + smart gate.** Fetch the Fed's FOMC calendar page at run
time, parse the next SEP-producing meeting date, and only enter the
polling loop if that date is today. Between meetings, the script prints
the next expected date and exits cleanly. Parser failures fall back to
a small hardcoded list of known meeting dates so the script never dies
silently.

## Components

### 1. Discovery module — `fetch_next_sep()` in `sep_analyzer.py`

- **Input:** today's date (for testability; defaults to `datetime.date.today()`).
- **Action:**
  1. Fetch `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm`
     via `urllib.request` (avoids adding a new dependency).
  2. Parse meeting dates from the HTML. The Fed page uses a structured
     layout where each meeting is labeled with month and day range;
     SEP-producing meetings fall in Mar, Jun, Sep, Dec.
  3. Filter to meetings whose date is today-or-later AND whose month is
     Mar/Jun/Sep/Dec.
  4. Return the earliest such `datetime.date`.
- **Fallback:** if fetch or parse fails, return the earliest
  today-or-later date from a hardcoded list covering 2026–2027
  meeting dates. If that list is also exhausted, raise a
  `RuntimeError` with a message instructing the user to update the
  fallback list.
- **Network timeout:** 10 seconds; on timeout, use the fallback.

### 2. CLI entry point — `--discover` flag in `sep_analyzer.py`

New argparse flag. When set, the script:
- Calls `fetch_next_sep()`.
- Prints exactly one line to stdout and exits:
  - `NOT_TODAY <YYYY-MM-DD>` if the next SEP date is in the future.
  - `POLL <url> <filename>` if the next SEP date is today.
- URL format: `https://www.federalreserve.gov/monetarypolicy/files/fomcprojtabl<YYYYMMDD>.pdf`.
- Filename format: `sep_<YYYYMMDD>.pdf`.

All other CLI behavior (`--demo`, `--text`, PDF path, bare invocation)
is unchanged.

### 3. Smart gate in `run_sep.sh`

Replace the hardcoded `URL` and `PDF` variables with a call to
`python sep_analyzer.py --discover`. Parse the single-line output:

- If it starts with `NOT_TODAY`: print a friendly message with the next
  date and exit 0.
- If it starts with `POLL`: assign `URL` and `PDF` from the remaining
  fields and enter the existing polling loop.
- Any other output or non-zero exit: print an error and exit 1.

Polling interval (30 s), PDF download step, analyzer invocation, and
local-PDF-short-circuit all remain as they are today.

## Error handling

- **Calendar fetch fails:** fall back to hardcoded list. Discovery
  still succeeds. No user-visible error.
- **HTML parse fails:** same as above.
- **Fallback list exhausted:** fail loudly with a message pointing at
  the list location so the user knows how to extend it.
- **Malformed `--discover` output:** bash gate prints an error and
  exits 1 rather than entering a polling loop on a bad URL.

## Testing

- Unit test `fetch_next_sep()` by monkeypatching the HTTP fetcher to
  return a saved copy of the Fed calendar HTML. Verify:
  - Correct next date when multiple future SEP meetings exist.
  - Fallback to hardcoded list when fetch raises.
  - Fallback to hardcoded list when parse returns nothing.
  - `RuntimeError` when both parsed dates and fallback are exhausted.
- Unit test `--discover` output formatting:
  - `NOT_TODAY` branch with a mocked future date.
  - `POLL` branch with a mocked today date, verifying URL and
    filename use the correct `YYYYMMDD` format.

Save the Fed calendar HTML fixture under `tests/fixtures/`.

## Out of scope

- Changing polling interval or retry logic.
- Auto-detecting the Press Conference PDF or statement PDF.
- Fetching the SEP text via API instead of PDF download.
- Notifying the user via email / Slack when a new SEP drops.

## Files touched

- `sep_analyzer.py` — add `fetch_next_sep()`, add `--discover` flag.
- `run_sep.sh` — replace hardcoded URL/filename with discovery call.
- `tests/test_discover.py` — new file.
- `tests/fixtures/fomccalendars.htm` — new fixture.
