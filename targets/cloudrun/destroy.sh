#!/usr/bin/env bash
# Fails if the service list cannot be read, so a lookup error is never taken for "already gone".
set -euo pipefail
svc="cb-${BENCH_RUN_ID}"
region="asia-southeast1"
found=$(gcloud run services list --project "$GCP_PROJECT" --region "$region" \
  --filter "metadata.name=${svc}" --format 'value(metadata.name)')
if [[ -n "$found" ]]; then
  gcloud run services delete "$svc" --project "$GCP_PROJECT" --region "$region" --quiet >&2
fi
