#!/usr/bin/env bash
# Railway builds the same Dockerfile at the same commit itself (artifact "source", ADR-0003).
# Needs RAILWAY_TOKEN (a project token for the lab project's bench environment),
# RAILWAY_SERVICE, and RAILWAY_URL (the service's generated domain, set once).
set -euo pipefail
railway variables --service "$RAILWAY_SERVICE" --skip-deploys \
  --set BENCH_TARGET=railway --set BENCH_REGION=asia-southeast1 \
  --set "BENCH_COMMIT=${BENCH_COMMIT}" >&2
railway up --service "$RAILWAY_SERVICE" --ci >&2
echo "$RAILWAY_URL"
