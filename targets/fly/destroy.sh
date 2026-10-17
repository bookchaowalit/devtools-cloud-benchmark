#!/usr/bin/env bash
# Fails if the app list cannot be read, so a lookup error is never taken for "already gone".
set -euo pipefail
app="cb-${BENCH_RUN_ID}"
apps=$(flyctl apps list --org "$FLY_ORG" --json)
if APP="$app" python3 -c 'import json,os,sys; sys.exit(0 if any(a.get("Name")==os.environ["APP"] for a in json.load(sys.stdin)) else 1)' <<<"$apps"; then
  flyctl apps destroy "$app" --yes >&2
fi
