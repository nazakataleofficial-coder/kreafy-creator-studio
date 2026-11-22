#!/bin/sh
# Kreafy Creator Studio — one-click launcher (Linux / Mac).
# Double-click ya terminal se: ./start-studio.sh
# Backend + frontend start honge aur dashboard browser me khul jayega.
# Band karne ke liye Ctrl+C dabayen.
cd "$(dirname "$0")"
exec python3 studio/launcher.py "$@"
