#!/bin/bash
# Polls for the March 2026 SEP PDF and runs the analyzer when it drops.

URL="https://www.federalreserve.gov/monetarypolicy/files/fomcprojtabl20260318.pdf"
PDF="sep_march2026.pdf"
DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$DIR"

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

# If the PDF already exists locally, skip polling and analyze immediately
if [ -f "$PDF" ]; then
    echo "Found $PDF locally. Running analyzer..."
    echo ""
    /opt/anaconda3/bin/python3 sep_analyzer.py "$PDF"
    exit 0
fi

echo "Waiting for March 2026 SEP to drop..."
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
        /opt/anaconda3/bin/python3 sep_analyzer.py "$PDF"
        exit 0
    else
        echo "[$NOW] Not yet ($STATUS). Retrying in 30s..."
        sleep 30
    fi
done
