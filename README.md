# SEP Analyzer

FOMC Summary of Economic Projections scanner. Drop a Fed SEP PDF in, get a bullish/bearish verdict with trader-desk commentary powered by Claude.

## Quick Start

```bash
pip install -r requirements.txt
```

Create a `.env` file with your Anthropic API key:

```
sk-ant-your-key-here
```

Run it:

```bash
./run_sep.sh
```

That's it. One command. The script loads your key from `.env`, detects the PDF locally (or polls the Fed website until it drops), parses the SEP, and delivers the full analysis.

## What It Does

1. Extracts text from the SEP PDF
2. Parses key projections: fed funds rate, GDP, Core PCE, unemployment
3. Compares them to the **previous SEP baseline** (auto-loaded from your last run)
4. Scans for hawkish/dovish/hike keywords
5. Computes a composite delta score
6. Sends everything to Claude for a rapid trader-desk analysis with verdict, confidence, and portfolio implications

## Auto-Baseline (runs/)

Each run saves its output to a local `runs/` folder (e.g. `runs/2026-03-18_170934/output.json`). The next time you run the analyzer, it automatically loads the most recent run as the comparison baseline — no manual editing needed.

- First run: uses the hardcoded December 2025 SEP as baseline
- Every run after: uses your most recent prior run
- Full history accumulates in `runs/` so you can track how projections shift over time

The `runs/` folder is gitignored (local to your machine).

## Usage

### One command (recommended)

```bash
./run_sep.sh
```

If the PDF already exists locally, it skips polling and runs the analysis immediately. If not, it polls the Fed website every 30 seconds until the PDF drops, then downloads and analyzes it automatically.

### Analyze a specific PDF

```bash
python sep_analyzer.py path/to/sep.pdf
```

### Analyze pasted text

```bash
python sep_analyzer.py --text "paste raw SEP text here"
```

### Demo mode (no PDF or API key needed)

```bash
python sep_analyzer.py --demo
```

## API Key

The key is loaded in this order:

1. `.env` file in the project directory (just the raw key, no `export` or variable name)
2. `ANTHROPIC_API_KEY` environment variable
3. Interactive prompt at runtime (input is hidden)

If no key is provided, the analysis still runs — only the AI synthesis step is skipped.

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

## Configuration

The Claude model is set at the top of `sep_analyzer.py`:

```python
CLAUDE_MODEL = "claude-sonnet-4-20250514"
```

Update this when a newer model is available.

## Security

- API key is **never hardcoded** — loaded from `.env` file, environment variable, or interactive prompt
- `.env` files, PDFs, local run data, and `.claude/` settings are all gitignored
- The key only lives in memory for the duration of the session
