#!/bin/bash
set -e

URL="http://localhost:8000"
OUTPUT="docs/screenshots"

mkdir -p "$OUTPUT"

echo "📸 Capture des pages SymlinkRepair..."

pages=(
  "$URL:dashboard"
  "$URL/scan:scan"
  "$URL/results:results"
  "$URL/reports:reports"
  "$URL/config:config"
)

export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser

for page in "${pages[@]}"; do
  url="${page%%:*}"
  name="${page##*:}"
  echo "  → $name..."
  pageres "$url" 1280x800 --filename="$OUTPUT/$name" 2>/dev/null
  if [ $? -ne 0 ]; then
    echo "  ⚠️  Échec pour $name"
  fi
done

echo "✅ Captures terminées : $OUTPUT/"
ls -lh "$OUTPUT"
