#!/usr/bin/env bash
# Needs gcloud authenticated (workload identity in CI), GCP_PROJECT, and BENCH_IMAGE_GCP:
# Cloud Run pulls from Artifact Registry, so the workflow copies the GHCR digest there first.
set -euo pipefail
svc="cb-${BENCH_RUN_ID}"
region="asia-southeast1"
gcloud run deploy "$svc" --project "$GCP_PROJECT" --region "$region" \
  --image "$BENCH_IMAGE_GCP" --port 8080 --cpu 1 --memory 512Mi \
  --min-instances 0 --max-instances 1 --concurrency 80 --allow-unauthenticated \
  --set-env-vars "BENCH_TARGET=cloudrun,BENCH_REGION=${region},BENCH_COMMIT=${BENCH_COMMIT}" \
  --quiet >&2
gcloud run services describe "$svc" --project "$GCP_PROJECT" --region "$region" \
  --format 'value(status.url)'
