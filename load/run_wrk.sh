#!/usr/bin/env bash
# Deliverable 6 -- stress test with >2000 concurrent connections.
# Usage: ./load/run_wrk.sh http://EXTERNAL_IP
set -euo pipefail
URL="${1:?usage: run_wrk.sh http://EXTERNAL_IP}"
CONN="${CONN:-2100}"      # >2000 as required
THREADS="${THREADS:-4}"
DURATION="${DURATION:-60s}"
OUT="artifacts/wrk_report.txt"
mkdir -p artifacts

# wrk needs one file descriptor per connection.
ulimit -n 65535 || echo "WARN: could not raise ulimit -n; run with sudo if wrk errors"

echo "=== baseline warm-up ==="
wrk -t2 -c50 -d10s -s load/post.lua "$URL/predict" || true

echo "=== STRESS: ${THREADS} threads / ${CONN} connections / ${DURATION} ===" | tee "$OUT"
{
  date -u +"start_utc=%Y-%m-%dT%H:%M:%SZ"
  wrk -t"$THREADS" -c"$CONN" -d"$DURATION" --timeout 10s --latency \
      -s load/post.lua "$URL/predict"
  date -u +"end_utc=%Y-%m-%dT%H:%M:%SZ"
} 2>&1 | tee -a "$OUT"

echo
echo "--- pod / HPA state right after the run ---" | tee -a "$OUT"
kubectl get hpa heart-api 2>/dev/null | tee -a "$OUT" || true
kubectl top pods -l app=heart-api 2>/dev/null | tee -a "$OUT" || true
echo "report saved to $OUT"
