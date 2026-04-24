# SEP Analyzer

FOMC Summary of Economic Projections scanner. Point it at the Fed's SEP PDF (or let it auto-discover the next release date) and get a bullish/bearish verdict with trader-desk commentary powered by Claude.

## Requirements

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/) (only needed for AI synthesis; parsing and scoring work without it)

## Quick Start

```bash
pip install -r requirements.txt
```

Create a `.env` file with your Anthropic API key (just the raw key, no variable name):

```
sk-ant-your-key-here
```

Then run it:

```bash
./run_sep.sh
```

The script auto-discovers the next FOMC meeting date from the Fed's calendar page:
- On a non-meeting day: prints the next SEP release date and exits.
- On release day: polls the Fed site every 30s until the PDF drops, then downloads and analyzes it.

## What It Does

1. Extracts text from the SEP PDF (via `pdfplumber`)
2. Parses key projections: fed funds rate, GDP, Core PCE, unemployment
3. Compares them to the **previous SEP baseline** (auto-loaded from your last run)
4. Scans for hawkish/dovish/hike keywords
5. Computes a composite delta score
6. Sends everything to Claude for a rapid trader-desk analysis with verdict, confidence, and portfolio implications

## Usage

### Normal run (auto-discover + poll)

```bash
./run_sep.sh
```

### Demo mode (no network, no PDF, no real API call needed for parsing)

Useful for showing the pipeline end-to-end against mock SEP text:

```bash
./run_sep.sh --demo
```

### Custom portfolio tickers

Threaded through to the AI synthesis prompt so portfolio implications are tailored to your positions. Works with demo mode and with real runs:

```bash
./run_sep.sh --demo --tickers SPY,TLT,NVDA
./run_sep.sh --tickers SPY,TLT,NVDA         # applied once the PDF is downloaded
```

### Analyze a specific PDF directly

```bash
python sep_analyzer.py path/to/sep.pdf
```

### Analyze pasted text

```bash
python sep_analyzer.py --text "paste raw SEP text here"
```

### Just discover the next release date (no download, no analysis)

```bash
python sep_analyzer.py --discover
```

Prints `NOT_TODAY <date>` or `POLL <url> <filename>`.

## Auto-Baseline (`runs/`)

Each run saves its output to a local `runs/` folder (e.g. `runs/2026-03-18_170934/output.json`). The next run loads the most recent prior output as the comparison baseline — no manual editing needed.

- First run: uses the hardcoded December 2025 SEP as baseline
- Every run after: uses your most recent prior run
- Full history accumulates in `runs/` so you can track how projections shift over time

`runs/` is gitignored (local to your machine).

## API Key

The key is loaded in this order:

1. `.env` file in the project directory (raw key only)
2. `ANTHROPIC_API_KEY` environment variable
3. Interactive prompt at runtime (input is hidden)

If no key is provided, parsing and scoring still run — only the AI synthesis step is skipped or reports the error inline.

## Output

```
COMPOSITE SCORE: -2.0
SIGNAL:          NEUTRAL

TRADER DESK ANALYSIS
1. VERDICT: NEUTRAL
2. CONFIDENCE: 85%
3. TOP 3 SIGNALS: ...
4. IMMEDIATE IMPACT: ...
5. PORTFOLIO IMPLICATIONS: ...
6. WATCH LIST: ...
```

## Tests

```bash
python -m pytest tests/ -q
```

Covers the parser (table + prose extraction), scoring (baseline handling, delta direction, keyword math), and the FOMC calendar discovery flow.

## Configuration

The Claude model is set at the top of `sep_analyzer.py`:

```python
CLAUDE_MODEL = "claude-sonnet-4-20250514"
```

Update this when a newer model is available.

## Security

- API key is **never hardcoded** — loaded from `.env`, env var, or interactive prompt
- `.env`, PDFs, local run data, and `.claude/` settings are all gitignored
- The key only lives in memory for the duration of the session

## License

MIT — see [LICENSE](LICENSE).
