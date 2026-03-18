# SEP Analyzer

FOMC Summary of Economic Projections scanner. Drop a Fed SEP PDF in, get a bullish/bearish verdict with trader-desk commentary powered by Claude.

## What It Does

1. Extracts text from the SEP PDF
2. Parses key projections: fed funds rate, GDP, Core PCE, unemployment
3. Compares them to the **previous SEP baseline** (auto-loaded from your last run)
4. Scans for hawkish/dovish/hike keywords
5. Computes a composite delta score
6. Sends everything to Claude for a rapid trader-desk analysis with verdict, confidence, and portfolio implications

## Auto-Baseline (runs/)

Each run saves its output to a local `runs/` folder (e.g. `runs/2026-03-18_170018/output.json`). The next time you run the analyzer, it automatically loads the most recent run as the comparison baseline — no manual editing needed.

- First run: uses the hardcoded December 2025 SEP as baseline
- Every run after: uses your most recent prior run
- Full history accumulates in `runs/` so you can track how projections shift over time

The `runs/` folder is gitignored (local to your machine).

## Setup

```bash
pip install -r requirements.txt
```

Set your API key (required for the AI synthesis step):

```bash
export ANTHROPIC_API_KEY=your-key-here
```

## Usage

### Analyze a PDF

```bash
python sep_analyzer.py path/to/sep.pdf
```

### Analyze pasted text

```bash
python sep_analyzer.py --text "paste raw SEP text here"
```

### Demo mode (no PDF needed)

```bash
python sep_analyzer.py --demo
```

### Auto-poll for the next SEP

`run_sep.sh` polls the Fed website every 30 seconds. Once the PDF goes live, it downloads and analyzes it automatically.

```bash
export ANTHROPIC_API_KEY=your-key-here
chmod +x run_sep.sh
./run_sep.sh
```

## Output

```
COMPOSITE SCORE: -16.8
SIGNAL:          BEARISH

TRADER DESK ANALYSIS
1. VERDICT: BEARISH
2. CONFIDENCE: 78%
3. TOP 3 SIGNALS: ...
4. IMMEDIATE IMPACT: ...
5. PORTFOLIO IMPLICATIONS: ...
6. WATCH LIST: ...
```

## Security

- API key is **never hardcoded** — loaded from the `ANTHROPIC_API_KEY` environment variable only
- `.env` files, PDFs, and local run data are all gitignored
