#!/bin/bash
set -e

export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser
node "$(dirname "$0")/screenshots-dark.mjs"
