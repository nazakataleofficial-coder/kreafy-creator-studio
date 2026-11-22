#!/bin/sh
# Kreafy Creator Studio — safe update (Linux / Mac).
# Usage: ./update-studio.sh <naya-version-folder-ya-zip>
# Pehle backup banta hai, phir code badalta hai, phir verify hota hai.
# Verify fail ho to backup wapas lag jata hai.
cd "$(dirname "$0")"
if [ -z "$1" ]; then
  echo "Usage: ./update-studio.sh <naya-version-folder-ya-zip>"
  echo "Example: ./update-studio.sh ~/Downloads/kreafy-creator-studio-test-main.zip"
  exit 1
fi
exec python3 scripts/update.py --source "$1"
