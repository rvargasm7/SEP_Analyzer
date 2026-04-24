#!/bin/bash
# Polls for the next FOMC SEP PDF and runs the analyzer when it drops.
# The next meeting date is discovered at run time from the Fed's FOMC
# calendar page. On non-meeting days, prints the next date and exits.

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Pick the first interpreter that has both required packages installed.
# Honors $PYTHON override; otherwise tries common candidates.
pick_python() {
    if [ -n "$PYTHON" ]; then
        echo "$PYTHON"
        return
    fi
    for cand in \
        "$DIR/.venv/bin/python" \
        "python3" \
        "/opt/anaconda3/bin/python3" \
        "/usr/bin/python3"
    do
        if command -v "$cand" >/dev/null 2>&1 && \
           "$cand" -c "import anthropic, pdfplumber" >/dev/null 2>&1; then
            echo "$cand"
            return
        fi
    done
    # Nothing works — fall back to python3 so user sees the clear error message.
    echo "python3"
}
PYTHON="$(pick_python)"

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

# --demo (and any trailing args like --tickers) skips discovery and runs
# the analyzer directly against mock SEP data.
if [ "$1" = "--demo" ]; then
    shift
    "$PYTHON" sep_analyzer.py --demo "$@"
    exit $?
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
# "$@" forwards any extra args (e.g. --tickers SPY,TLT,NVDA) to the analyzer.
if [ -f "$PDF" ]; then
    echo "Found $PDF locally. Running analyzer..."
    echo ""
    "$PYTHON" sep_analyzer.py "$PDF" "$@"
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
        "$PYTHON" sep_analyzer.py "$PDF" "$@"
        exit 0
    else
        echo "[$NOW] Not yet ($STATUS). Retrying in 30s..."
        sleep 30
    fi
done
