# Cloud Benchmark Lab

What exists today. Details and run steps are in [README.md](README.md).

## Purpose

Deploy one small service to several PaaS targets (Railway, Render, Fly.io, Cloud Run), check it
against a contract, measure it from one client the same way, then delete it. Every published
number is meant to keep its run record (commit, image digest, size, client, settings).

## Users

The owner, as evidence for platform choices and as a portfolio lab. No external users.

## What works

- `app/main.py`: the measured FastAPI service (no database, no outbound calls), built by the
  `Dockerfile`; CI builds the image and checks the contract against the container.
- `contract/check.py`: exact-value contract; a target that fails it gets failures, not numbers.
- `runner/`: `run.py` measures one URL (sequential latency, `oha` load, CPU load, optional
  idle probe); `orchestrate.py` runs deploy → measure → destroy per target with a second destroy
  pass; `build_site.py` rebuilds `site/data.json` from `results/`.
- `targets/<id>/deploy.sh` / `destroy.sh` for four providers, one ADR each (`docs/adr/`).
- Tests (`tests/`): contract against a real and a deliberately wrong local service, the
  orchestrator with fake targets, and the site builder. CI runs Ruff, mypy, pytest with a
  coverage gate, the container contract check and the shared security scans.

## Live

Results page: <https://cloud-benchmark-lab.vercel.app> (static `site/`, Vercel deploys on push to
`main`). On 2026-10-22 it answered HTTP 200 and `site/data.json` has **no runs**: the manual
`bench` workflow has never been dispatched, and no target has been deployed to a real account.

## Limits

- No published measurements yet; each target's first real run is its acceptance test.
- Running the bench creates paid resources for minutes; it is manual only (owner cost gate),
  and needs provider secrets/variables the owner sets in GitHub.
- The client is a GitHub-hosted runner with an uncontrolled location; sizes differ per provider;
  one instance per target, not a production setup.
- No Sentry: the only long-running code is the measured service, which lives for minutes and
  would be skewed by an SDK; the runner is a CLI inside GitHub Actions, where a failure already
  fails the run (and a failed destroy is reported as `failed: destroy`).

Sentry waiver: the only runtime is the measured service, which lives for minutes per bench run; an SDK would skew the measurements, and a runner failure already fails the GitHub Actions run.

## Disposition

Lab / showcase (product card verdict `showcase`). Keep; the next step is an owner-approved first
bench run.
