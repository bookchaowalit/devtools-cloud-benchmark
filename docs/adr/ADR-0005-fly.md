# ADR-0005: Fly.io as a lab target

Template: `system-architecture-decision` (architecture-docs `templates/development-cycle/system-architecture-decision.md`).

## Document control

| Field | Value |
|---|---|
| Decision ID | ADR-0005 |
| Initiative/system | Cloud Benchmark Lab (`devtools-cloud-benchmark`), PRJ-CBL-01, target `fly` |
| Decision owner | Owner (bookchaowalit) |
| Accountable approver | Owner (bookchaowalit). An AI cannot approve; this is gate G6 |
| Version/status/date | 1.0 / **proposed** (pending owner approval at G6) / 2026-10-18 |
| Related requirements | FR-03, FR-04, FR-12, NFR-01, NFR-02, NFR-04 in the architecture-docs workspace `operations/platform/cloud-benchmark-lab/06-requirements-engineering.md` |
| Related ADRs | ADR-0001 (deploy, measure, destroy), ADR-0002 (one image by digest) |
| Maker / AI reviewer | Claude Code / Codex (not run yet) |

## Decision

- **Context and constraints:**
  - Fly.io runs containers as lightweight virtual machines ("Machines") that it places in a chosen region and can stop and start on demand.
  - The lab deploys the GHCR digest with `flyctl deploy --image`, so the bytes are the same as on Render and Cloud Run (ADR-0002).
  - A Fly app belongs to an organization. An org-scoped token can only act inside that organization, so a dedicated **lab organization** keeps the blast radius away from any production app.
  - Nothing in this target has run against a real account yet.
- **What Fly.io is uniquely good at (as the provider documents it; the lab checks only part of this):**
  - Placing small VMs close to users in many regions with an anycast edge, controlled from a CLI and a Machines API.
  - Fast start and stop of Machines, so an app can scale to zero (`auto_stop_machines`) and wake on the first request.
  - What the lab can show: time to live from an image, the first request after idle for a stopped Machine, and the behaviour of one shared-CPU Machine. What it cannot show: multi-region placement, volumes, private networking (WireGuard), the Machines API itself.
- **Why it is in the lab, and why not another:** Fly.io is the "small VM, global edge, scale to zero, CLI-first" reference. It sits between Render (always-on fixed size) and Cloud Run (serverless containers) and gives the page a scale-to-zero platform that is not a hyperscaler. Other edge or microVM-style platforms (for example Koyeb or Cloudflare's container offering) are not in Phase 1; each can be added later, one at a time, with its own ADR and a real measured run.
- **Decision and rationale:** Include `fly` as a Phase 1 target. Per run: create the app `cb-<run id>` in the lab org, deploy the digest as one Machine in `sin` (`--ha=false`), measure, then `flyctl apps destroy`.
- **Options considered and rejected:**

  | Option | Why not |
  |---|---|
  | `flyctl deploy` from source (remote builder) | Different builder and layers; ADR-0002 requires the same image bytes |
  | Keep one app and only deploy/destroy Machines | Leaves an app (and possibly IPs) behind between runs; per-run apps are cleaner to sweep by prefix |
  | Run two Machines (default HA) | Breaks the one-instance rule |
  | Use the owner's personal Fly organization | Violates the isolation rule |
  | Multi-region placement | The lab holds every target to one instance in Singapore |

- **System context and trust boundaries:**
  - The bench job holds `FLY_API_TOKEN` (secret, org-scoped) and `FLY_ORG` (variable, the organization slug). `flyctl` is installed by `superfly/flyctl-actions/setup-flyctl` (pinned by SHA, with the flyctl version pinned to 0.4.118 through the action's `version` input).
  - The app is public at `https://cb-<run id>.fly.dev`.
- **Interfaces, dependencies, and failure modes:**
  - `flyctl deploy --wait-timeout 10m` waits for the Machine to pass its health check (`/health`, grace 10 s, interval 10 s, timeout 5 s).
  - `destroy.sh` lists the organization's apps (`flyctl apps list --org … --json`) and destroys `cb-<run id>` only if it is in the list, so it is safe to run twice and after a failed create. If the list cannot be read it fails, so a lookup error is never taken for "already gone".
  - A new app may get IP addresses allocated on first deploy. A dedicated IPv4 address would be billed separately. Check at the first run that none was allocated, and that `apps destroy` released everything.
  - flyctl flag changes would break the script (R-05 provider API drift). flyctl is pinned to 0.4.118; bump it deliberately and re-run the first-run checks.
- **Data stores, ownership, retention, and residency:** None. Region: `sin` (Singapore).
- **Authentication, authorization, secrets, and audit:** `FLY_API_TOKEN` as a GitHub secret (org-scoped deploy/org token from the lab organization); `FLY_ORG` as a variable. Rotation: create a new token, replace the secret, revoke the old one.
- **Availability, scale, cost, and operability:** One Machine, `auto_stop_machines = "stop"`, `auto_start_machines = true`, `min_machines_running = 0`. During a run the Machine is up; after the run the app is destroyed.
- **Reversal/migration trigger:** Remove the target if `flyctl` can no longer create an app and deploy an external image non-interactively, or if the lab organization cannot be kept separate.

## Exact configuration used

From `runner/targets.py`, `targets/fly/` and `bench.yml`.

| Item | Value | Source |
|---|---|---|
| Target id | `fly` | `runner/targets.py` |
| Region | `sin` (label "Singapore"); `primary_region = "sin"` | `runner/targets.py`, `fly.toml` |
| Size | `shared-cpu-1x`, 512 MB, 1 Machine | `runner/targets.py`, `fly.toml` (`[[vm]]`) |
| Scale to zero | yes (`auto_stop_machines = "stop"`, `min_machines_running = 0`, `auto_start_machines = true`) | `fly.toml` |
| Artifact | `image`: the GHCR digest built by the workflow | `runner/targets.py` |
| Requires | secret `FLY_API_TOKEN`; variable `FLY_ORG` | `runner/targets.py`, `bench.yml` |
| HTTP | `internal_port = 8080`, `force_https = true` | `fly.toml` |
| Health check | `GET /health`, interval 10 s, timeout 5 s, grace period 10 s | `fly.toml` |
| Create | `flyctl apps create cb-<run id> --org $FLY_ORG` | `deploy.sh` |
| Deploy | `flyctl deploy --app cb-<run id> --config targets/fly/fly.toml --image $BENCH_IMAGE --ha=false --wait-timeout 10m --env BENCH_TARGET=fly --env BENCH_REGION=sin --env BENCH_COMMIT=<sha>`; prints `https://cb-<run id>.fly.dev` | `deploy.sh` |
| Destroy | `flyctl apps list --org $FLY_ORG --json`; `flyctl apps destroy cb-<run id> --yes` if the app is listed; fails if the list fails | `destroy.sh` |
| Cleanup env | `FLY_API_TOKEN`, `FLY_ORG` | `runner/targets.py` (`cleanup_requires`) |
| flyctl installer | `superfly/flyctl-actions/setup-flyctl` pinned by SHA; flyctl `version: 0.4.118` | `bench.yml` |

## How the comparison is unfair to or favours Fly.io

| Effect | Direction | Note |
|---|---|---|
| `shared-cpu-1x` is a shared CPU; the provider documents a burst and a baseline, so a sustained load can be throttled | Can be **unfair to Fly.io** on a long `load_cpu` | The 20 s CPU test may or may not reach the throttle; record the result and do not extrapolate |
| Fly's anycast edge terminates the client connection at an edge near the client and carries it over Fly's network | Can **favour Fly.io** on latency from a client far from Singapore | The client is a GitHub-hosted runner whose location is not controlled; compare within a run only. Confirm the edge behaviour at the first run |
| Scale to zero is on, so the first request after idle includes a Machine start | Shows a real trade-off, but only if `idle_seconds` is set | The default run has `idle_seconds=0`, so the cold-start number appears only in a run that asks for it |
| `deploy_s` includes the image pull and the health check (`--wait-timeout 10m`) | Fair to Fly; comparable with Cloud Run, not with Render (API call only) or Railway (build included) | Use `ready_s` and the request metrics for comparison |
| Image pulled from public GHCR | Slightly unfair to `ready_s` (same as Render) | Cloud Run pulls from a regional registry |

## Setup (one time; owner action, see the runbook in architecture-docs `11-deployment-go-live.md`)

1. Create a **lab organization** on Fly.io (a separate organization from any production app) and add a payment method.
2. Store the organization slug as the repository variable `FLY_ORG`.
3. Create an organization-scoped token for that organization (`fly tokens create org`, or the dashboard equivalent) and store it as the secret `FLY_API_TOKEN`. Confirm at the first run that an org-scoped token is enough to create and destroy apps; if not, record the minimum token type here.
4. Make the GHCR package public (ADR-0002) and check an anonymous pull.
5. Configure billing alerts or the closest equivalent Fly.io offers (confirm in the dashboard) and record it in the cost table.
6. Run the bench with `targets=fly` and fill the table below. Run once more with `idle_seconds` set (for example 300) to record the cold-start probe.

## First real run (to fill)

| Date | Result (contract pass/fail, run record path) | deploy_s | ready_s | Issues and fixes |
|---|---|---|---|---|
| _pending_ | _not run yet_ | | | |

Acceptance for this target: `flyctl apps create` and `deploy --image` work non-interactively with the org token; one Machine in `sin`; the contract passes; `flyctl apps list --org <org>` shows no `cb-` app afterwards, and no IP addresses remain; the record is committed.

## Cost (to fill; do not publish numbers before this is filled)

| Item | Value | Source URL | Date checked |
|---|---|---|---|
| Plan or minimum spend, if any | _to verify_ | provider pricing page (start from fly.io/docs/about/pricing) | _pending_ |
| `shared-cpu-1x` 512 MB rate and billing granularity | _to verify_ | same | _pending_ |
| IP address charges (shared vs dedicated IPv4) | _to verify_ | same | _pending_ |
| Bandwidth included | _to verify_ | same | _pending_ |
| Estimated live time per run | about 5 to 15 min (create + pull + start + about 4 min of measurement). Estimate; replace with real values from the first record | first record | _pending_ |
| Estimated cost per run | _derive from the rates above after the first run_ | | _pending_ |
| Billing alert configured | _owner to record_ | dashboard | _pending_ |

## Consequences and verification

| Consequence or risk | Owner | Mitigation/evidence | Status |
|---|---|---|---|
| flyctl is pinned to 0.4.118, so a bump is a deliberate change | Owner | Re-verify the first-run checks after any bump (R-05) | mitigated |
| Dedicated IP allocation on first deploy could create a separate charge | Owner | Check IPs after the run and after `apps destroy` | open |
| Org token scope may not be enough for `apps create` | Owner | First real run is the test; record the working token type | open |
| App name collision (`cb-<run id>` is global) | Owner | The run id is unique per workflow run; a clash fails the create loudly | accepted |
| Verification | Claude (maker), Codex (reviewer) | Script reviewed by reading only; not run against Fly.io | not yet verified |

## Approval

| Role | Name/date | Decision |
|---|---|---|
| Technical owner | Owner (bookchaowalit) / pending | Approve / revise (G6) |
| Security/privacy reviewer | Codex (AI checker, advisory) / not run yet | Accept controls / escalate |
| Operations/data owner | Owner (bookchaowalit) / pending | Accept operability/data boundary |
