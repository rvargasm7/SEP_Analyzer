#!/usr/bin/env python3
"""
SEP Analyzer — FOMC Summary of Economic Projections
Drop the Fed PDF in, get a bullish/bearish verdict in seconds.

Usage:
    python sep_analyzer.py path/to/sep.pdf
    python sep_analyzer.py --text "paste raw text here"
    python sep_analyzer.py --demo   (runs with mock SEP data to test)

Requires: ANTHROPIC_API_KEY environment variable
"""

import sys
import re
import os
import json
import argparse
import getpass
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

try:
    import pdfplumber
except ImportError:
    print("Run: pip install pdfplumber anthropic")
    sys.exit(1)

try:
    import anthropic
except ImportError:
    print("Run: pip install anthropic")
    sys.exit(1)


# ── CONFIG ────────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-20250514"

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
    date(2027, 6, 9),
    date(2027, 9, 15),
    date(2027, 12, 8),
]

CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"


def _parse_next_sep_date(html: str, today: date) -> Optional[date]:
    """
    Parse the Fed's FOMC calendar HTML and return the earliest SEP-producing
    meeting date that is on or after `today`.

    SEP-producing meetings happen in March, June, September, and December.
    The Fed renders each meeting as paired <div> elements: a month div
    (containing <strong>MonthName</strong>) followed by a date div (e.g.
    "17-18*"). The SEP drops on the final day of the two-day meeting.

    Returns None when html is empty or no future SEP date can be found.
    """
    if not html:
        return None

    # Locate every year heading and use its position to bound that year's
    # block. The HTML lists years in descending order (most recent first).
    year_heading = re.compile(
        r"(\d{4})\s*FOMC\s*Meetings", re.IGNORECASE
    )
    year_matches = list(year_heading.finditer(html))
    if not year_matches:
        return None

    # Match a month div directly followed (within the same fomc-meeting row)
    # by a date div whose text starts with "DD-DD" (allowing trailing chars
    # like "*" or footnote markers).
    pair_pattern = re.compile(
        r'fomc-meeting__month[^>]*>\s*<strong>([A-Za-z/]+)</strong>\s*</div>'
        r'(?:(?!fomc-meeting__month).)*?'
        r'fomc-meeting__date[^>]*>\s*(\d{1,2})\s*[-–]\s*(\d{1,2})',
        re.DOTALL | re.IGNORECASE,
    )

    candidates = []
    for i, ym in enumerate(year_matches):
        try:
            year = int(ym.group(1))
        except ValueError:
            continue
        block_start = ym.end()
        block_end = year_matches[i + 1].start() if i + 1 < len(year_matches) else len(html)
        block = html[block_start:block_end]

        for pm in pair_pattern.finditer(block):
            month_name = pm.group(1).strip().lower()
            month_num = MONTH_NAMES.get(month_name)
            if month_num is None or month_num not in SEP_MONTHS:
                continue
            try:
                day = int(pm.group(3))  # second day of two-day meeting
            except ValueError:
                continue
            try:
                meeting_date = date(year, month_num, day)
            except ValueError:
                continue
            if meeting_date >= today:
                candidates.append(meeting_date)

    if not candidates:
        return None
    return min(candidates)


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


# ── BASELINE (December 2025 SEP) ─────────────────────────────────────────────
# Update this section after each SEP release becomes the new baseline.
DECEMBER_BASELINE = {
    "fed_funds_median_2026": 3.4,     # actual Dec 2025 SEP median
    "fed_funds_median_2027": 3.1,
    "fed_funds_longer_run":  3.0,
    "gdp_2026":              2.3,
    "gdp_2027":              2.0,
    "core_pce_2026":         2.5,
    "core_pce_2027":         2.1,
    "unemployment_2026":     4.4,
    "unemployment_2027":     4.2,
    "cuts_implied_2026":     1,        # one 25bp cut projected for 2026
}

RUNS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")


def load_baseline() -> dict:
    """
    Load the most recent run as the baseline.
    Falls back to DECEMBER_BASELINE if no prior runs exist.
    """
    if not os.path.isdir(RUNS_DIR):
        return DECEMBER_BASELINE

    run_dirs = sorted(
        [d for d in os.listdir(RUNS_DIR)
         if os.path.isfile(os.path.join(RUNS_DIR, d, "output.json"))],
    )
    if not run_dirs:
        return DECEMBER_BASELINE

    latest = os.path.join(RUNS_DIR, run_dirs[-1], "output.json")
    with open(latest) as f:
        data = json.load(f)

    baseline = data.get("baseline_snapshot", {})
    if not baseline:
        return DECEMBER_BASELINE

    print(f"  Using prior run as baseline: runs/{run_dirs[-1]}/")
    return baseline


def save_run(reading, scores: dict, analysis_text: str, source_label: str) -> str:
    """
    Save current run output to runs/YYYY-MM-DD_HHMMSS/.
    Returns the path to the saved directory.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_dir = os.path.join(RUNS_DIR, timestamp)
    os.makedirs(run_dir, exist_ok=True)

    # Snapshot of extracted numbers — this becomes the next run's baseline
    baseline_snapshot = {}
    for key in [
        "fed_funds_median_2026", "fed_funds_median_2027", "fed_funds_longer_run",
        "gdp_2026", "gdp_2027", "core_pce_2026", "core_pce_2027",
        "unemployment_2026", "unemployment_2027",
    ]:
        val = getattr(reading, key, None)
        if val is not None:
            baseline_snapshot[key] = val

    output = {
        "timestamp": timestamp,
        "source": source_label,
        "baseline_snapshot": baseline_snapshot,
        "scores": {k: v for k, v in scores.items() if k != "TOTAL"},
        "total_score": scores["TOTAL"],
        "keyword_hits": {
            "hawkish": reading.hawkish_hits,
            "dovish": reading.dovish_hits,
            "hike": reading.hike_hits,
        },
        "ai_analysis": analysis_text,
    }

    out_path = os.path.join(run_dir, "output.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Run saved to: runs/{timestamp}/output.json")
    return run_dir


# ── KEYWORD DICTIONARIES ──────────────────────────────────────────────────────
HAWKISH_PHRASES = [
    "inflation risks remain tilted to the upside",
    "upside risks to inflation",
    "inflation has not returned",
    "remain attentive to inflation",
    "prepared to adjust",
    "policy sufficiently restrictive",
    "not yet confident",
    "further progress needed",
    "energy prices could broaden",
    "second-round effects",
    "wage pressures remain",
    "services inflation persistent",
    "tightening bias",
    "rate hike",
    "additional firming",
    "higher for longer",
    "elevated uncertainty",
    "geopolitical risks to inflation",
]

DOVISH_PHRASES = [
    "inflation has eased substantially",
    "making progress toward",
    "confident inflation moving",
    "labor market has cooled",
    "risks to our goals are roughly in balance",
    "proceed carefully",
    "appropriate to reduce",
    "transitory impact",
    "energy prices tend to be transitory",
    "look through",
    "supply-side normalization",
    "below-trend growth",
    "downside risks to employment",
    "easing financial conditions",
    "disinflation process",
    "gradual recalibration",
]

HIKE_SIGNALS = [
    "prepared to increase",
    "would not hesitate to raise",
    "tighten further",
    "rate increase",
    "additional tightening",
]


# ── DATA CLASS ────────────────────────────────────────────────────────────────
@dataclass
class SEPReading:
    # Extracted numbers (None = not found in document)
    fed_funds_median_2026: Optional[float] = None
    fed_funds_median_2027: Optional[float] = None
    fed_funds_longer_run:  Optional[float] = None
    gdp_2026:              Optional[float] = None
    gdp_2027:              Optional[float] = None
    core_pce_2026:         Optional[float] = None
    core_pce_2027:         Optional[float] = None
    unemployment_2026:     Optional[float] = None
    unemployment_2027:     Optional[float] = None
    dots_no_cuts_count:    Optional[int]   = None   # members projecting 0 cuts
    dots_hike_count:       Optional[int]   = None   # members projecting hike

    # Keyword hits
    hawkish_hits: list = field(default_factory=list)
    dovish_hits:  list = field(default_factory=list)
    hike_hits:    list = field(default_factory=list)

    # Raw text
    raw_text: str = ""


# ── PDF EXTRACTION ────────────────────────────────────────────────────────────
def extract_pdf_text(path: str) -> str:
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


# ── NUMBER PARSER ─────────────────────────────────────────────────────────────
def parse_sep_numbers(text: str) -> dict:
    """
    Extract key SEP numbers using regex patterns.
    Handles both table formats and prose mentions.
    """
    results = {}
    text_lower = text.lower()

    # ── Table-format parser (Fed PDF: concatenated labels + columns) ────
    # The official SEP PDF renders as e.g.:
    #   ChangeinrealGDP 2.4 2.3 2.1 2.0 ...
    #   CorePCEinflation4 2.7 2.2 2.0 ...
    #   Federalfundsrate 3.4 3.1 3.1 3.1 ...
    # Columns are: 2026  2027  2028  Longer run (medians), then ranges.
    table_rows = {
        # label regex -> (2026_key, 2027_key, longer_run_key)
        r"changeinrealgdp\s+([\d.]+)\s+([\d.]+)\s+[\d.]+\s+([\d.]+)":
            ("gdp_2026", "gdp_2027", None),
        r"unemploymentrate\s+([\d.]+)\s+([\d.]+)\s+[\d.]+\s+([\d.]+)":
            ("unemployment_2026", "unemployment_2027", None),
        r"corepce\s*inflation\d?\s+([\d.]+)\s+([\d.]+)":
            ("core_pce_2026", "core_pce_2027", None),
        r"federal\s*funds\s*rate\s+([\d.]+)\s+([\d.]+)\s+[\d.]+\s+([\d.]+)":
            ("fed_funds_median_2026", None, "fed_funds_longer_run"),
    }

    for pat, keys in table_rows.items():
        match = re.search(pat, text_lower)
        if match:
            for i, key in enumerate(keys):
                if key and match.group(i + 1):
                    results.setdefault(key, float(match.group(i + 1)))

    # Also try fed_funds_median_2027 from the funds rate row
    ff_match = re.search(
        r"federal\s*funds\s*rate\s+([\d.]+)\s+([\d.]+)", text_lower
    )
    if ff_match:
        results.setdefault("fed_funds_median_2027", float(ff_match.group(2)))

    # ── Prose-format fallback patterns ───────────────────────────────────
    patterns = {
        "fed_funds_median_2026": [
            r"(?:median|midpoint).*?2026.*?(\d\.\d{1,3})\s*%",
            r"2026.*?(?:median|midpoint).*?(\d\.\d{1,3})\s*%",
            r"federal funds rate.*?2026[^\d]*(\d\.\d{1,3})",
        ],
        "fed_funds_longer_run": [
            r"longer.?run.*?(\d\.\d{1,3})\s*%",
            r"neutral.*?rate.*?(\d\.\d{1,3})",
            r"(\d\.\d{1,3})\s*%.*?longer.?run",
        ],
        "gdp_2026": [
            r"(?:real\s+)?gdp.*?2026[^\d]*([+-]?\d\.\d)\s*%",
            r"(?:economic\s+)?growth.*?2026[^\d]*([+-]?\d\.\d)\s*%",
            r"2026[^\d]*(?:real\s+)?gdp[^\d]*([+-]?\d\.\d)",
        ],
        "core_pce_2026": [
            r"core\s+pce.*?2026[^\d]*(\d\.\d)\s*%",
            r"pce\s+(?:ex|excluding|core).*?2026[^\d]*(\d\.\d)",
            r"2026.*?core\s+pce[^\d]*(\d\.\d)",
        ],
        "unemployment_2026": [
            r"unemployment.*?2026[^\d]*(\d\.\d)\s*%",
            r"2026.*?unemployment[^\d]*(\d\.\d)",
        ],
        "gdp_2027": [
            r"(?:real\s+)?gdp.*?2027[^\d]*([+-]?\d\.\d)\s*%",
            r"2027[^\d]*(?:real\s+)?gdp[^\d]*([+-]?\d\.\d)",
        ],
        "core_pce_2027": [
            r"core\s+pce.*?2027[^\d]*(\d\.\d)\s*%",
            r"2027.*?core\s+pce[^\d]*(\d\.\d)",
        ],
        "unemployment_2027": [
            r"unemployment.*?2027[^\d]*(\d\.\d)\s*%",
            r"2027.*?unemployment[^\d]*(\d\.\d)",
        ],
    }

    for key, pats in patterns.items():
        if key in results:
            continue  # already found via table parser
        for pat in pats:
            match = re.search(pat, text_lower)
            if match:
                try:
                    results[key] = float(match.group(1))
                    break
                except ValueError:
                    continue

    # ── Hike signal from Table 1 range data ────────────────────────────
    # The official PDF dot plot (Figure 2) is a visual chart — individual
    # dot values don't appear in extracted text.  Instead, use the range
    # column from Table 1 (highest participant projection for 2026 fed
    # funds rate).  If the range high exceeds the current target midpoint
    # (3.625 = midpoint of 3.50–3.75), some members project hikes.
    current_rate_midpoint = 3.625
    range_match = re.search(
        r"federal\s*funds\s*rate.*?(\d\.\d)[\u2013–-](\d\.\d)\s+"
        r"(\d\.\d)[\u2013–-](\d\.\d)\s+(\d\.\d)[\u2013–-](\d\.\d)",
        text_lower,
    )
    if range_match:
        range_high_2026 = float(range_match.group(2))
        results["dots_hike_count"] = 1 if range_high_2026 > current_rate_midpoint else 0
    else:
        results["dots_hike_count"] = 0
    results["dots_no_cuts_count"] = 0

    return results


# ── KEYWORD SCANNER ───────────────────────────────────────────────────────────
def scan_keywords(text: str) -> dict:
    text_lower = text.lower()
    hawkish_hits = [p for p in HAWKISH_PHRASES if p in text_lower]
    dovish_hits  = [p for p in DOVISH_PHRASES  if p in text_lower]
    hike_hits    = [p for p in HIKE_SIGNALS    if p in text_lower]
    return {
        "hawkish_hits": hawkish_hits,
        "dovish_hits":  dovish_hits,
        "hike_hits":    hike_hits,
    }


# ── DELTA SCORER ─────────────────────────────────────────────────────────────
def score_deltas(reading: SEPReading, baseline: dict) -> dict:
    """
    Compare each extracted metric to the previous baseline.
    Returns a score dict with individual component signals.
    Positive score = bullish (market-friendly), negative = bearish.
    """
    scores = {}
    b = baseline

    def safe_delta(new_val, baseline_key, direction="lower_is_bullish"):
        if new_val is None:
            return 0, "not found"
        delta = new_val - b[baseline_key]
        if direction == "lower_is_bullish":
            score = -delta * 10  # negative delta = bullish
        else:
            score = delta * 10
        return round(score, 2), f"{'+' if delta>0 else ''}{delta:.2f} vs prev baseline"

    # Fed funds rate: lower = bullish (more cuts expected)
    s, note = safe_delta(reading.fed_funds_median_2026, "fed_funds_median_2026", "lower_is_bullish")
    scores["dot_plot_2026"] = {"score": s, "note": note, "value": reading.fed_funds_median_2026}

    # Longer run rate: lower = bullish (lower neutral rate)
    s, note = safe_delta(reading.fed_funds_longer_run, "fed_funds_longer_run", "lower_is_bullish")
    scores["longer_run_rate"] = {"score": s, "note": note, "value": reading.fed_funds_longer_run}

    # GDP: higher = bullish (stronger growth)
    s, note = safe_delta(reading.gdp_2026, "gdp_2026", "higher_is_bullish")
    scores["gdp_2026"] = {"score": s, "note": note, "value": reading.gdp_2026}

    # Core PCE: lower = bullish (inflation cooling)
    s, note = safe_delta(reading.core_pce_2026, "core_pce_2026", "lower_is_bullish")
    scores["core_pce_2026"] = {"score": s, "note": note, "value": reading.core_pce_2026}

    # Unemployment: lower = bullish (labor market strong)
    s, note = safe_delta(reading.unemployment_2026, "unemployment_2026", "lower_is_bullish")
    scores["unemployment_2026"] = {"score": s, "note": note, "value": reading.unemployment_2026}

    # Hike signal: any participant projecting above current rate = bearish
    if reading.dots_hike_count and reading.dots_hike_count > 0:
        scores["hike_dots"] = {"score": -15, "note": "range high suggests hike projection(s)", "value": reading.dots_hike_count}
    else:
        scores["hike_dots"] = {"score": 0, "note": "no hike dots detected", "value": 0}

    # Keywords
    keyword_score = (len(reading.dovish_hits) * 3) - (len(reading.hawkish_hits) * 3) - (len(reading.hike_hits) * 10)
    scores["keywords"] = {
        "score": keyword_score,
        "note": f"{len(reading.dovish_hits)} dovish / {len(reading.hawkish_hits)} hawkish / {len(reading.hike_hits)} hike signals",
        "value": keyword_score
    }

    total = sum(v["score"] for v in scores.values())
    scores["TOTAL"] = total
    return scores


# ── CLAUDE SYNTHESIS ──────────────────────────────────────────────────────────
def synthesize_with_claude(reading: SEPReading, scores: dict, raw_text: str, baseline: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "[Set ANTHROPIC_API_KEY env variable for AI synthesis]"

    client = anthropic.Anthropic(api_key=api_key)
# One thing to note. In line 439 Portfolio Implications: (Switch to your ticker list if you want them analyzed)
    context = f"""
You are a macro trader reading the Fed's Summary of Economic Projections (SEP) the moment it drops.

PREVIOUS SEP BASELINE:
{json.dumps(baseline, indent=2)}

EXTRACTED FROM TODAY'S SEP:
Dot plot median 2026: {reading.fed_funds_median_2026}
Longer run rate: {reading.fed_funds_longer_run}
GDP 2026: {reading.gdp_2026}%
Core PCE 2026: {reading.core_pce_2026}%
Unemployment 2026: {reading.unemployment_2026}%
Potential hike dots: {reading.dots_hike_count}

KEYWORD SIGNALS:
Hawkish phrases found: {reading.hawkish_hits}
Dovish phrases found: {reading.dovish_hits}
Hike signal phrases: {reading.hike_hits}

DELTA SCORE BREAKDOWN:
{json.dumps({k: v for k, v in scores.items() if k != 'TOTAL'}, indent=2)}
Total score: {scores['TOTAL']} (positive = bullish, negative = bearish)

EXCERPT FROM SEP TEXT (first 3000 chars):
{raw_text[:3000]}

Provide a rapid trading-desk analysis:
1. VERDICT: BULLISH / BEARISH / NEUTRAL (one word)
2. CONFIDENCE: percentage
3. TOP 3 SIGNALS: the three most market-moving things in this SEP
4. IMMEDIATE IMPACT: what happens to S&P, 10Y yield, dollar, and gold in the next 60 minutes
5. PORTFOLIO IMPLICATIONS: specific to a speculative portfolio with positions in USAR, TGT, SPY, TLT, UPS, XOM, NVDA, META
6. WATCH LIST: one sentence on what to monitor in Powell's press conference

Be direct, rapid, and specific. No hedging. Trader language.
"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": context}]
    )
    return response.content[0].text


# ── DEMO DATA ─────────────────────────────────────────────────────────────────
DEMO_SEP_TEXT = """
SUMMARY OF ECONOMIC PROJECTIONS
March 18, 2026

The Federal Open Market Committee (FOMC) participants submitted projections
for economic growth, inflation, unemployment, and the appropriate path of
monetary policy.

ECONOMIC PROJECTIONS TABLE

                        2026        2027        Longer Run
Real GDP Growth         1.7%        2.0%        1.8%
Unemployment Rate       4.5%        4.3%        4.1%
PCE Inflation           3.1%        2.4%        2.0%
Core PCE Inflation      2.9%        2.3%        —
Federal Funds Rate      3.625       3.375       3.0

The Committee noted that inflation risks remain tilted to the upside
given persistent services inflation and the ongoing impact of energy
price shocks from the Middle East conflict.

Participants agreed that they are not yet confident that inflation
is moving sustainably toward the 2% target. The Committee remains
attentive to the risks to both sides of its dual mandate.

Several participants noted that further progress on inflation is
needed before additional rate reductions would be appropriate.
The median participant projects 3.625% federal funds rate at end of 2026,
unchanged from December, though the balance of risks has shifted.

Three participants project rates at 3.875 for 2026, up from zero in December.
The longer-run neutral rate projection held at 3.0%.

GDP growth for 2026 was revised down to 1.7% from 2.3% in December,
reflecting the drag from elevated energy costs and tighter financial conditions.

Unemployment is projected at 4.5% for 2026, slightly above the December
projection of 4.4%, reflecting some cooling in the labor market.

Core PCE inflation was revised up to 2.9% for 2026, from 2.5% in December,
driven by energy passthrough effects and continued stickiness in services prices.
"""


# ── MAIN ──────────────────────────────────────────────────────────────────────
def analyze(text: str, source_label: str = "SEP", save: bool = True) -> None:
    print(f"\n{'='*60}")
    print(f"  SEP ANALYZER — {source_label}")
    print(f"{'='*60}\n")

    # Load baseline (most recent prior run, or December 2025 fallback)
    print("► Loading baseline...")
    baseline = load_baseline()

    # Parse numbers
    print("► Parsing structured data...")
    numbers = parse_sep_numbers(text)

    # Keyword scan
    print("► Scanning keywords...")
    keywords = scan_keywords(text)

    # Build reading
    reading = SEPReading(
        raw_text=text,
        **{k: numbers.get(k) for k in [
            "fed_funds_median_2026", "fed_funds_longer_run",
            "gdp_2026", "gdp_2027", "core_pce_2026", "core_pce_2027",
            "unemployment_2026", "unemployment_2027",
            "dots_no_cuts_count", "dots_hike_count"
        ]},
        hawkish_hits=keywords["hawkish_hits"],
        dovish_hits=keywords["dovish_hits"],
        hike_hits=keywords["hike_hits"],
    )

    # Score
    print("► Scoring deltas vs previous baseline...")
    scores = score_deltas(reading, baseline)

    # Print extracted numbers
    print("\n─── EXTRACTED NUMBERS ───────────────────────────────────")
    fields = [
        ("Fed funds median 2026", reading.fed_funds_median_2026, f"Prev: {baseline.get('fed_funds_median_2026', '?')}"),
        ("Longer run rate",       reading.fed_funds_longer_run,  f"Prev: {baseline.get('fed_funds_longer_run', '?')}"),
        ("GDP 2026",              reading.gdp_2026,               f"Prev: {baseline.get('gdp_2026', '?')}"),
        ("Core PCE 2026",         reading.core_pce_2026,          f"Prev: {baseline.get('core_pce_2026', '?')}"),
        ("Unemployment 2026",     reading.unemployment_2026,      f"Prev: {baseline.get('unemployment_2026', '?')}"),
        ("Hike dots detected",    reading.dots_hike_count,        "Prev: 0"),
    ]
    for label, val, prev in fields:
        val_str = f"{val}%" if val is not None else "NOT FOUND"
        print(f"  {label:<28} {val_str:<12} ({prev})")

    # Print keyword hits
    print("\n─── KEYWORD SIGNALS ─────────────────────────────────────")
    print(f"  Hawkish ({len(reading.hawkish_hits)}): {', '.join(reading.hawkish_hits[:3]) or 'none'}")
    print(f"  Dovish  ({len(reading.dovish_hits)}):  {', '.join(reading.dovish_hits[:3]) or 'none'}")
    print(f"  Hike    ({len(reading.hike_hits)}):  {', '.join(reading.hike_hits) or 'none'}")

    # Print scores
    print("\n─── DELTA SCORES vs PREVIOUS BASELINE ──────────────────")
    for key, val in scores.items():
        if key == "TOTAL":
            continue
        if isinstance(val, dict):
            bar = "▲" if val["score"] > 0 else ("▼" if val["score"] < 0 else "─")
            print(f"  {bar} {key:<22} {val['score']:>+6.1f}  {val['note']}")

    total = scores["TOTAL"]
    verdict = "BULLISH" if total > 10 else ("BEARISH" if total < -10 else "NEUTRAL")
    verdict_color = {"BULLISH": "✅", "BEARISH": "🔴", "NEUTRAL": "⚠️"}[verdict]

    print(f"\n{'─'*55}")
    print(f"  COMPOSITE SCORE: {total:+.1f}")
    print(f"  SIGNAL:          {verdict_color} {verdict}")
    print(f"{'─'*55}\n")

    # Claude synthesis
    print("► Running AI synthesis...\n")
    analysis = synthesize_with_claude(reading, scores, text, baseline)
    print("─── TRADER DESK ANALYSIS ────────────────────────────────")
    print(analysis)
    print(f"\n{'='*60}\n")

    # Save run
    if save:
        save_run(reading, scores, analysis, source_label)


def ensure_api_key():
    """Load API key from .env file, environment, or interactive prompt."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.isfile(env_path):
            with open(env_path) as f:
                key = f.read().strip()
            if key:
                os.environ["ANTHROPIC_API_KEY"] = key
                return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("─── API KEY REQUIRED ────────────────────────────────────")
        print("  The AI synthesis step needs your Anthropic API key.")
        print("  Tip: put your key in a .env file to skip this prompt.\n")
        key = getpass.getpass("  Enter your ANTHROPIC_API_KEY: ")
        if not key.strip():
            print("\n  No key provided. AI synthesis will be skipped.")
        else:
            os.environ["ANTHROPIC_API_KEY"] = key.strip()
            print("  Key set for this session.\n")


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

    if args.demo:
        analyze(DEMO_SEP_TEXT, "DEMO — March 2026 Mock SEP")

    elif args.text:
        analyze(args.text, "PASTED TEXT")

    elif args.pdf:
        if not os.path.exists(args.pdf):
            print(f"File not found: {args.pdf}")
            sys.exit(1)
        print(f"Extracting text from {args.pdf}...")
        text = extract_pdf_text(args.pdf)
        if not text.strip():
            print("Could not extract text from PDF. Try --text with copy-pasted content.")
            sys.exit(1)
        analyze(text, args.pdf)

    else:
        print(__doc__)
        print("\nRunning demo mode...\n")
        analyze(DEMO_SEP_TEXT, "DEMO — March 2026 Mock SEP")


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


if __name__ == "__main__":
    main()
