# How to Run — SEP Analyzer

Analyzes the Fed's Summary of Economic Projections (SEP) PDF and gives a bullish/bearish verdict with trading-desk commentary powered by Claude.

## Prerequisites

- Python 3
- An [Anthropic API key](https://console.anthropic.com/) for the AI synthesis step

## Setup

Install dependencies:

```bash
pip install pdfplumber anthropic
```

Set your API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

### 1. Analyze a PDF

```bash
python sep_analyzer.py path/to/sep.pdf
```

### 2. Analyze pasted text

```bash
python sep_analyzer.py --text "paste raw SEP text here"
```

### 3. Run the demo (no PDF needed)

```bash
python sep_analyzer.py --demo
```

### 4. Auto-poll for the March 2026 SEP (`run_sep.sh`)

The `run_sep.sh` script polls the Fed website every 30 seconds for the March 2026 SEP PDF. Once the PDF goes live, it automatically downloads it and runs `sep_analyzer.py` against it.

**Requirements:** `curl` (pre-installed on macOS/Linux), plus all the prerequisites above.

```bash
# 1. Make sure your API key is set
export ANTHROPIC_API_KEY=sk-ant-...

# 2. Make the script executable (one-time)
chmod +x run_sep.sh

# 3. Run it
./run_sep.sh
```

The script will print a status line every 30 seconds until the PDF is available. Once it detects a `200` response, it downloads the PDF to the project directory and pipes it into the analyzer.

Press `Ctrl+C` to stop polling.

## What It Does

1. Extracts text from the SEP PDF (or uses provided text)
2. Parses key projections (fed funds rate, GDP, Core PCE, unemployment)
3. Compares them to the December 2025 baseline
4. Scans for hawkish/dovish keywords
5. Computes a composite delta score
6. Sends everything to Claude for a rapid trader-desk analysis with verdict, confidence, and portfolio implications
