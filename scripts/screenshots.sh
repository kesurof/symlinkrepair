#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
URL="http://localhost:8005"
OUTPUT="$SCRIPT_DIR/docs/screenshots"

mkdir -p "$OUTPUT"

echo "📸 Capture des pages SymlinkRepair..."

pages=(
  "$URL/?dark=1:dashboard"
  "$URL/scan?dark=1:scan"
  "$URL/results?dark=1:results"
  "$URL/reports?dark=1:reports"
  "$URL/config?dark=1:config"
)

export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser

for page in "${pages[@]}"; do
  url="${page%:*}"
  name="${page##*:}"
  echo "  → $name"
  cd "$OUTPUT"
  timeout 120 pageres "$url" 1280x800 --filename="$name" 2>&1
  if [ $? -ne 0 ]; then
    echo "  ⚠️  Échec pour $name"
  fi
done

echo "✅ Captures terminées : $OUTPUT/"
ls -lh "$OUTPUT"
