#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  YouTube Transcript Accessibility Tool
#  Double-click this file in Finder to launch the web app.
#  A browser window will open automatically at http://localhost:5050
#  Close this Terminal window (or press Ctrl+C) to stop the server.
# ─────────────────────────────────────────────────────────────────

# Move to the folder containing this script
cd "$(dirname "$0")"

echo ""
echo "  YouTube Transcript Accessibility Tool"
echo "  ──────────────────────────────────────"

# ── Install / update dependencies quietly ──────────────────────
echo "  Checking dependencies…"
python3 -m pip install --quiet --break-system-packages \
    flask youtube-transcript-api yt-dlp 2>/dev/null \
  || pip3 install --quiet flask youtube-transcript-api yt-dlp 2>/dev/null
echo "  Dependencies OK."
echo ""

# ── Launch ─────────────────────────────────────────────────────
python3 yt_transcript_tool.py
