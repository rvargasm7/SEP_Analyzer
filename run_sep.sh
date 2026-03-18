#!/bin/bash
# Polls for the March 2026 SEP PDF and runs the analyzer when it drops.

URL="https://www.federalreserve.gov/monetarypolicy/files/fomcprojtabl20260318.pdf"
PDF="sep_march2026.pdf"
DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$DIR"

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: Set your API key first:"
    echo "  export ANTHROPIC_API_KEY=sk-ant-..."
    exit 1
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
        python3 sep_analyzer.py "$PDF"
        exit 0
    else
        echo "[$NOW] Not yet ($STATUS). Retrying in 30s..."
        sleep 30
    fi
done
