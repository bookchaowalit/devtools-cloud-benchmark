# Cloud Benchmark Lab

One small service, deployed to several PaaS targets in Singapore, held to one instance, checked by
a contract, measured from one client, and then deleted. Every published number keeps its run
record (commit, image digest, target size, client, settings).

The point is not a leaderboard. It is evidence for one question per provider: *what is this
platform actually good at, and what does it cost to find out?* Each target has an ADR that answers
"why this one, not another".

Results page: `site/` (Vercel project, to be connected). Raw records: `results/`.

## Targets

| Target | Region | Size | Artifact | Scale to zero | ADR |
|---|---|---|---|---|---|
| `railway` | Singapore | usage-based, 1 replica | builds the Dockerfile itself | no | [ADR-0003](docs/adr/ADR-0003-railway.md) |
| `render` | Singapore | starter (0.5 CPU, 512 MB) | GHCR image by digest | no | [ADR-0004](docs/adr/ADR-0004-render.md) |
| `fly` | `sin` | shared-cpu-1x, 512 MB, 1 machine | GHCR image by digest | yes | [ADR-0005](docs/adr/ADR-0005-fly.md) |
| `cloudrun` | `asia-southeast1` | 1 vCPU, 512 MiB, max 1 | same digest copied to Artifact Registry | yes | [ADR-0006](docs/adr/ADR-0006-cloud-run.md) |

**Status:** the service, contract, runner and workflows are tested locally and in CI. No target
has been deployed to a real account yet; the first run of each is its acceptance test
([targets/README.md](targets/README.md)).

Adding a target: an entry in `runner/targets.py`, `targets/<id>/deploy.sh` + `destroy.sh`, an ADR,
and a passing contract on a real deploy before it appears on the page.

## What is measured

| Metric | How |
|---|---|
| `deploy_s` | wall time of `deploy.sh` (create + build/pull + start) |
| `ready_s` | after deploy returns, time until `/health` answers 200 |
| `latency_sequential` | 300 requests on one keep-alive connection, one at a time: p50/p95/p99/max |
| `load_items` | `oha`, 20 connections, 3 × 30 s over random `/items/{id}`: median rps, p50/p95/p99, error rate |
| `load_cpu` | `oha`, 4 connections, 20 s of `/work?n=20000` (SHA-256 rounds): CPU share under load |
| `first_request_after_idle_ms` | optional (`idle_seconds`): first request after the target was left idle |

The service (`app/main.py`) has no database and makes no outbound calls, so the platform is the
only variable. The contract (`contract/check.py`) checks exact values; a target that fails it
gets a record with its failures and no numbers.

## Run it locally

```bash
uv sync
uv run python -m pytest -q                           # contract, runner, orchestrator
uv run uvicorn app.main:app --port 8080 &
uv run python runner/run.py --target local --url http://127.0.0.1:8080 --quick --out .cache/local
```

`runner/run.py` downloads `oha` 1.16.0 into `.tools/` if it is not on `PATH`.

## Run the bench

`.github/workflows/bench.yml`, manual dispatch only. It builds and pushes the image once, then
runs `runner/orchestrate.py`: for each target, deploy → measure → destroy, one after another on
the same runner, with a second destroy pass as a safety net. A target whose secrets or variables
are missing is skipped. Results are committed back and `site/data.json` is rebuilt.

| Kind | Name |
|---|---|
| Secrets | `RAILWAY_TOKEN`, `RENDER_API_KEY`, `FLY_API_TOKEN` |
| Variables | `RAILWAY_SERVICE`, `RAILWAY_URL`, `RENDER_OWNER_ID`, `FLY_ORG`, `GCP_PROJECT`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT` |

Google auth is workload identity federation; there is no key file. One-time setup per provider:
the runbook in architecture-docs `operations/platform/cloud-benchmark-lab/`.

## Limits

- The client is a GitHub-hosted runner whose location is not controlled; latency includes that
  path. Compare targets within one run.
- Sizes are the nearest each provider offers, not equal. One instance isolates the platform, not
  the autoscaler, and is not a production setup.
- Railway's image is built by Railway from the same commit, so its digest differs.

## License

MIT
