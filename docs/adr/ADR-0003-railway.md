# ADR-0003: Railway as a lab target

Template: `system-architecture-decision` (architecture-docs `templates/development-cycle/system-architecture-decision.md`).

## Document control

| Field | Value |
|---|---|
| Decision ID | ADR-0003 |
| Initiative/system | Cloud Benchmark Lab (`devtools-cloud-benchmark`), PRJ-CBL-01, target `railway` |
| Decision owner | Owner (bookchaowalit) |
| Accountable approver | Owner (bookchaowalit). An AI cannot approve; this is gate G6 |
| Version/status/date | 1.0 / **proposed** (pending owner approval at G6) / 2026-10-18 |
| Related requirements | FR-03, FR-04, FR-12, NFR-01, NFR-02, NFR-04 in the architecture-docs workspace `operations/platform/cloud-benchmark-lab/06-requirements-engineering.md` |
| Related ADRs | ADR-0001 (deploy, measure, destroy), ADR-0002 (one image by digest; Railway builds from source) |
| Maker / AI reviewer | Claude Code / Codex (not run yet) |

## Decision

- **Context and constraints:**
  - Railway already hosts the owner's production backend and workers. The lab uses a **separate** Railway workspace and project, with its own budget, so a lab mistake cannot reach production.
  - Railway deploys from source: the CLI uploads the build context and Railway builds the `Dockerfile` itself. This is how the owner normally uses it, so the lab keeps that path instead of forcing an image.
  - Nothing in this target has run against a real account yet.
- **What Railway is uniquely good at (as the provider documents it; the lab checks only part of this):**
  - The shortest path from a repository or a directory to a running, publicly reachable service: `railway up`, a generated domain, no cluster or registry to set up.
  - Usage-based billing of resources in use, with databases, private networking and environments in the same project model.
  - What the lab can show: time to live from source (build included), the behaviour of an uncapped single replica, and how little configuration the service needs. What it cannot show: developer experience, databases, private networking, team features.
- **Why it is in the lab, and why not another:** The owner runs production on Railway, so the lab should show how it compares with the alternatives the owner might choose for a new product. It is the "source build, usage-based" reference point. Other source-build PaaS (for example Heroku-style or Koyeb-style platforms) are not in Phase 1; each can be added later, one at a time, with its own ADR and a real measured run.
- **Decision and rationale:** Include `railway` as a Phase 1 target, deployed by `railway up` from source into one lab service, one replica, Singapore, and removed after each run with `railway down`. Rationale: it is the owner's real platform and the cheapest to set up.
- **Options considered and rejected:**

  | Option | Why not |
  |---|---|
  | Deploy the GHCR image to Railway | Not Railway's normal path; ADR-0002 keeps source build and labels it |
  | Create and delete a whole Railway project per run | Needs a workspace-level token (broader blast radius). One service with a project token scoped to the `bench` environment is smaller |
  | Connect the service to the GitHub repository | A push would deploy and bill; deploys must happen only from `bench.yml` |
  | Use the production Railway workspace | Violates the isolation rule (lab accounts and budgets are separate) |

- **System context and trust boundaries:**
  - The bench job holds `RAILWAY_TOKEN`, a Railway **project token** for the lab project's `bench` environment. The token can only act inside that environment.
  - The service's generated public domain is stored once as the repository variable `RAILWAY_URL` and is the URL measured.
- **Interfaces, dependencies, and failure modes:**
  - Railway CLI is installed in the job with `npm install --global @railway/cli@5.70.0` (pinned).
  - `railway up --ci` returns when the build finishes. It may not wait for the health check to pass; `run.py` waits for `/health` (up to 600 s). Confirm at the first run what `--ci` waits for and record it.
  - `destroy.sh` runs `targets/railway/railway_cleanup.py`. `railway down` only removes the latest successful deployment, so a deployment still queued or building when a run is interrupted would survive it. The script lists up to 50 recent deployments of the service (`railway deployment list --service … --json`), cancels those in flight and removes those running (`deploymentCancel` / `deploymentRemove` through `railway api`), then lists again and **exits non-zero if anything is still live** (a deployment that is only `REMOVING` is accepted). A failed list also exits non-zero. These subcommands and status names are unverified against a real account; the first run is the test. The go-live checklist still verifies the dashboard after a run.
  - Changes to CLI flags, the GraphQL schema behind `railway api`, or the project-token behaviour would break the scripts (R-05 provider API drift).
- **Data stores, ownership, retention, and residency:** None. Build logs and deployment history stay in the lab Railway project. Region: Singapore.
- **Authentication, authorization, secrets, and audit:** `RAILWAY_TOKEN` is a GitHub secret. `RAILWAY_SERVICE` and `RAILWAY_URL` are repository variables (not secret). Rotation: create a new project token, replace the secret, delete the old token.
- **Availability, scale, cost, and operability:** One replica, no scale-to-zero setting, no CPU/RAM cap set. Between runs there is no deployment (`railway down`), but the service shell and its variables remain. Cost is whatever Railway bills for the run's build and run time; see the cost section.
- **Reversal/migration trigger:** Remove the target if Railway's CLI can no longer create a deployment from a project token, or if the isolation rule cannot be kept (no way to separate lab from production).

## Exact configuration used

From `runner/targets.py`, `targets/railway/`, `.railwayignore` and `bench.yml`.

| Item | Value | Source |
|---|---|---|
| Target id | `railway` | `runner/targets.py` |
| Region | `asia-southeast1-eqsg3a` (label "Singapore") | `runner/targets.py` |
| Size | usage-based; 1 replica; **no CPU/RAM cap set** | `runner/targets.py` |
| Scale to zero | no | `runner/targets.py` |
| Artifact | `source`: Railway builds the same `Dockerfile` at the same commit | `runner/targets.py` |
| Requires | secret `RAILWAY_TOKEN`; variables `RAILWAY_SERVICE`, `RAILWAY_URL` | `runner/targets.py`, `bench.yml` |
| Builder | `DOCKERFILE`, `dockerfilePath = "Dockerfile"` | `targets/railway/railway.toml` |
| Health check | `/health`, timeout 300 s | `targets/railway/railway.toml` |
| Restart policy | `ON_FAILURE` | `targets/railway/railway.toml` |
| Upload scope | only `Dockerfile` and `app/` | `.railwayignore` |
| Env set at deploy | `BENCH_TARGET=railway`, `BENCH_REGION=asia-southeast1`, `BENCH_COMMIT=<sha>` via `railway variables --skip-deploys` | `targets/railway/deploy.sh` |
| Deploy | `railway up --service "$RAILWAY_SERVICE" --ci`, then prints `$RAILWAY_URL` | `targets/railway/deploy.sh` |
| Destroy | `targets/railway/railway_cleanup.py`: cancel in-flight and remove running deployments of the service, then verify none is live (exit 1 otherwise) | `targets/railway/destroy.sh` |
| Cleanup env | `RAILWAY_TOKEN`, `RAILWAY_SERVICE` (the `cleanup` job does not need `RAILWAY_URL`) | `runner/targets.py` (`cleanup_requires`) |
| CLI version | `@railway/cli@5.70.0` | `bench.yml` |
| Region and replicas | service settings, set once in the dashboard (not in `railway.toml`) | runbook |

## How the comparison is unfair to or favours Railway

| Effect | Direction | Note |
|---|---|---|
| No CPU/RAM cap is set, so the replica can use more than the fixed sizes elsewhere | **Favours Railway** on `load_cpu` and `load_items` | The size column says "usage-based"; do not read its rps next to a 0.5 CPU instance as like-for-like |
| `deploy_s` includes the build from source; the others only pull an image | **Unfair to Railway** on `deploy_s` | Compare `ready_s` and request metrics; treat `deploy_s` as "time to live from source" |
| Its image digest differs (`image` is empty or different in the record) | Neutral but must be disclosed | Same Dockerfile and commit |
| Railway region id differs from the label `Singapore` used elsewhere | Neutral | `BENCH_REGION` is declared by the script and is not verified by the contract; check the region in the dashboard at the first run |
| Single replica with no overlap between deployments | Neutral for the bench | Zero-downtime deploys and multi-replica behaviour are not measured at all |
| No scale-to-zero, so no cold-start probe applies | Neutral | `first_request_after_idle_ms` measures an always-on service |

## Setup (one time; owner action, see the runbook in architecture-docs `11-deployment-go-live.md`)

1. In a **lab** Railway workspace (not the production one), create the project `cloud-benchmark-lab` with an environment `bench`.
2. Add an empty service (for example `bench`). **Do not connect a GitHub repository** to it.
3. Settings → Config-as-code path = `targets/railway/railway.toml`. Region = Singapore. Replicas = 1. Leave resource limits unset (as recorded above).
4. Networking → generate a public domain. Store the full URL **with scheme** (`https://…`) as the repository variable `RAILWAY_URL`. Store the service name or id as `RAILWAY_SERVICE`.
5. Create a project token for the `bench` environment. Store it as the secret `RAILWAY_TOKEN`.
6. Set a usage limit or alert on the lab workspace (exact feature to confirm in the dashboard) and record it in the cost table.
7. Run the bench with `targets=railway` and fill the table below.

## First real run (to fill)

| Date | Result (contract pass/fail, run record path) | deploy_s | ready_s | Issues and fixes |
|---|---|---|---|---|
| _pending_ | _not run yet_ | | | |

Acceptance for this target: the contract passes; `destroy.sh` leaves no running deployment (checked in the dashboard); the region shown in the dashboard is Singapore; the record is committed.

## Cost (to fill; do not publish numbers before this is filled)

| Item | Value | Source URL | Date checked |
|---|---|---|---|
| Plan or subscription fee, if any | _to verify_ | provider pricing page (start from railway.com/pricing) | _pending_ |
| CPU, memory and network rates | _to verify_ | same | _pending_ |
| Build time cost, if any | _to verify_ | same | _pending_ |
| Estimated live time per run | about 5 to 15 min (build + start + about 4 min of measurement). Estimate; replace with `deploy_s + ready_s + measurement` from the first record | first record | _pending_ |
| Estimated cost per run | _derive from the rates above after the first run_ | | _pending_ |
| Usage limit or alert configured | _owner to record_ | dashboard | _pending_ |

## Consequences and verification

| Consequence or risk | Owner | Mitigation/evidence | Status |
|---|---|---|---|
| The cleanup script relies on `railway deployment list --json`, `railway api` and an assumed set of status names | Owner | First real run; adjust the script and record the working commands here | open |
| Unclear what `railway up --ci` waits for | Owner | Observe at the first run; document here | open |
| Unknown whether a project token can run `railway variables --set` and `railway up` together | Owner | First real run is the test | open |
| Service shell and variables persist between runs | Owner | No deployment runs, so no usage; confirm no idle charge from the shell | open |
| Verification | Claude (maker), Codex (reviewer) | Scripts reviewed by reading only; not run against Railway. The orchestrator's handling of a failing `destroy.sh` is unit-tested with stand-in scripts | not yet verified against Railway |

## Approval

| Role | Name/date | Decision |
|---|---|---|
| Technical owner | Owner (bookchaowalit) / pending | Approve / revise (G6) |
| Security/privacy reviewer | Codex (AI checker, advisory) / not run yet | Accept controls / escalate |
| Operations/data owner | Owner (bookchaowalit) / pending | Accept operability/data boundary |
