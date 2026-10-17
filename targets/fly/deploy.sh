#!/usr/bin/env bash
# Needs FLY_API_TOKEN and FLY_ORG. One machine (--ha=false), Singapore.
set -euo pipefail
app="cb-${BENCH_RUN_ID}"
flyctl apps create "$app" --org "$FLY_ORG" >&2
flyctl deploy --app "$app" --config targets/fly/fly.toml --image "$BENCH_IMAGE" \
  --ha=false --wait-timeout 10m \
  --env BENCH_TARGET=fly --env BENCH_REGION=sin --env "BENCH_COMMIT=${BENCH_COMMIT}" >&2
echo "https://${app}.fly.dev"
