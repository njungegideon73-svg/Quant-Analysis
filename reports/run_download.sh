#!/bin/bash
# Re-runs the resumable download until every month is stored (failed months are retried each pass).
cd "$(dirname "$0")/.."
for pass in 1 2 3 4 5; do
  echo "=== pass $pass $(date -u +%FT%TZ)"
  .venv/bin/ta download-jforex  # public-feed fallback: ta download --workers 2 && { echo "ALL DONE $(date -u +%FT%TZ)"; exit 0; }
  sleep 60
done
echo "STOPPED with failures after 5 passes $(date -u +%FT%TZ)"
