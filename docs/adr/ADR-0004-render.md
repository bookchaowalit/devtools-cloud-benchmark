# ADR-0004: Render as a lab target

Template: `system-architecture-decision` (architecture-docs `templates/development-cycle/system-architecture-decision.md`).

## Document control

| Field | Value |
|---|---|
| Decision ID | ADR-0004 |
| Initiative/system | Cloud Benchmark Lab (`devtools-cloud-benchmark`), PRJ-CBL-01, target `render` |
| Decision owner | Owner (bookchaowalit) |
| Accountable approver | Owner (bookchaowalit). An AI cannot approve; this is gate G6 |
| Version/status/date | 1.0 / **proposed** (pending owner approval at G6) / 2026-10-18 |
| Related requirements | FR-03, FR-04, FR-12, NFR-01, NFR-02, NFR-04 in the architecture-docs workspace `operations/platform/cloud-benchmark-lab/06-requirements-engineering.md` |
| Related ADRs | ADR-0001 (deploy, measure, destroy), ADR-0002 (one image by digest) |
| Maker / AI reviewer | Claude Code / Codex (not run yet) |

## Decision

- **Context and constraints:**
  - Render runs web services from a Git repository or from an existing container image. The lab uses the image path so the bytes are the same as on Fly.io and Cloud Run (ADR-0002).
  - The Render REST API is the only control surface the lab uses. `targets/render/render_api.py` is stdlib-only Python. Its request body follows Render's public API reference and **has not been run against a real account**.
  - A Render API key is tied to a user and may reach every workspace that user belongs to. The lab therefore uses a dedicated lab account or workspace membership, never the owner's identity that also reaches a production workspace.
- **What Render is uniquely good at (as the provider documents it; the lab checks only part of this):**
  - Fixed, named instance types with predictable pricing, closest to classic "Heroku-style" PaaS.
  - Managed Postgres and Redis next to the service, Blueprints (`render.yaml`) for infrastructure as code, preview environments, and a complete REST API.
  - What the lab can show: the behaviour of one fixed-size instance and how fast it becomes ready from a public image. What it cannot show: managed databases, Blueprints, previews, team features.
- **Why it is in the lab, and why not another:** Render is the "fixed instance size, image-backed, always-on" reference. It gives the page a platform whose size is explicit and does not scale to zero, which makes the contrast with Fly.io and Cloud Run visible. Other fixed-size PaaS (for example DigitalOcean App Platform) are not in Phase 1; each can be added later, one at a time, with its own ADR and a real measured run.
- **Decision and rationale:** Include `render` as a Phase 1 target. Create one `web_service` named `cb-<run id>` from the GHCR digest, plan `starter` (0.5 CPU, 512 MB), region `singapore`, one instance, and delete it after the run through the API.
- **Options considered and rejected:**

  | Option | Why not |
  |---|---|
  | Render free instance type | It spins down when idle and has limits that would make results about the free tier, not the platform |
  | Blueprint (`render.yaml`) instead of the REST API | A Blueprint is a long-lived definition that syncs from Git; the lab needs create-and-delete per run |
  | Build from the Git repository on Render | Different builder and layers; ADR-0002 requires the same image bytes |
  | Private GHCR package with a registry credential | Adds a secret for a public image |
  | Use the owner's existing Render workspace | Violates the isolation rule |

- **System context and trust boundaries:**
  - The bench job holds `RENDER_API_KEY` (secret) and `RENDER_OWNER_ID` (variable). Render pulls the image from public GHCR; no credential is stored on Render.
  - The service URL comes from the create response (`serviceDetails.url`).
- **Interfaces, dependencies, and failure modes:**
  - `POST /v1/services` returns before the first deploy is live. `deploy.sh` prints the URL immediately and `run.py` waits on `/health`. Therefore **`deploy_s` for Render measures only the API call**, not time to live.
  - If the create response has no URL, `deploy` exits 1; the service may still exist, and `destroy` finds it by name and owner.
  - `destroy` lists services by name and owner (`limit=20`, no pagination), deletes the match, then polls the list up to ten times (3 s apart) until the service is gone. It exits 1 if the list or delete call fails, or if the service is still listed after the wait; a service that never existed exits 0.
  - If the API request body drifts from the documentation (field names, `runtime: image`, `image.imagePath` with a digest), the first real run fails at create. That is the point of the first run.
- **Data stores, ownership, retention, and residency:** None. Region: Singapore.
- **Authentication, authorization, secrets, and audit:** `RENDER_API_KEY` as a GitHub secret from a dedicated lab account; `RENDER_OWNER_ID` as a repository variable. Rotation: create a new key, replace the secret, delete the old key.
- **Availability, scale, cost, and operability:** One always-on instance; billed while it exists, so the delete in `destroy` is what keeps the cost near zero. The safety-net destroy pass repeats the delete by name.
- **Reversal/migration trigger:** Remove the target if the REST API can no longer create an image-backed service without a registry credential, or if the owner decides a dedicated lab account is not worth keeping.

## Exact configuration used

From `runner/targets.py`, `targets/render/` and `bench.yml`.

| Item | Value | Source |
|---|---|---|
| Target id | `render` | `runner/targets.py` |
| Region | `singapore` | `runner/targets.py`, `render_api.py` (`REGION`) |
| Size | `starter` plan: 0.5 CPU, 512 MB, 1 instance (`RENDER_PLAN` can override; the default is what is recorded) | `runner/targets.py`, `render_api.py` |
| Scale to zero | no | `runner/targets.py` |
| Artifact | `image`: the GHCR digest built by the workflow | `runner/targets.py` |
| Requires | secret `RENDER_API_KEY`; variable `RENDER_OWNER_ID` | `runner/targets.py`, `bench.yml` |
| Create | `POST /v1/services`: `type: web_service`, `name: cb-<run id>`, `ownerId`, `image: {ownerId, imagePath: $BENCH_IMAGE}`, `serviceDetails: {runtime: image, plan, region: singapore, healthCheckPath: /health, numInstances: 1}` | `render_api.py` |
| Env set at deploy | `BENCH_TARGET=render`, `BENCH_REGION=singapore`, `BENCH_COMMIT=<sha>` | `render_api.py` |
| Destroy | `GET /v1/services?name=…&ownerId=…&limit=20`, `DELETE /v1/services/{id}`, then poll the list until it is gone (10 × 3 s); exit 1 on API error or if still listed | `render_api.py` |
| Cleanup env | `RENDER_API_KEY`, `RENDER_OWNER_ID` | `runner/targets.py` (`cleanup_requires`) |
| Port | the image listens on `${PORT}` (default 8080); Render injects its own `PORT` | `Dockerfile` |

## How the comparison is unfair to or favours Render

| Effect | Direction | Note |
|---|---|---|
| Starter is 0.5 CPU, the smallest paid fixed size; Cloud Run gets 1 vCPU and Railway is uncapped | **Unfair to Render** on `load_cpu` and `load_items` | Read the size column; do not rank by rps across different sizes |
| `deploy_s` is only the API call | **Flatters Render** on `deploy_s` | Use `ready_s` (or `deploy_s + ready_s`) for time to live |
| Image pulled from public GHCR over the internet, not from a provider-local registry | Slightly unfair to Render's `ready_s` | Same for Fly.io; Cloud Run pulls from a regional registry |
| Always on, no scale-to-zero | Neutral | No cold-start probe applies |
| Free instance type deliberately not used | Neutral | Stated so readers do not assume the free tier was measured |

## Setup (one time; owner action, see the runbook in architecture-docs `11-deployment-go-live.md`)

1. Use a **lab-only** Render account or workspace (a separate identity from any production workspace). Add a payment method (needed for the starter plan).
2. Find the owner id: it is the workspace or user id used as `ownerId` (shown in the workspace settings, or from `GET /v1/owners` with the API key). Store it as the repository variable `RENDER_OWNER_ID`.
3. Account settings → API keys → create a key. Store it as the secret `RENDER_API_KEY`.
4. Make the GHCR package public (ADR-0002) and check an anonymous pull. Render needs no registry credential.
5. Configure billing notifications or the closest equivalent Render offers (confirm in the dashboard) and record it in the cost table.
6. Run the bench with `targets=render` and fill the table below.

## First real run (to fill)

| Date | Result (contract pass/fail, run record path) | deploy_s | ready_s | Issues and fixes |
|---|---|---|---|---|
| _pending_ | _not run yet_ | | | |

Acceptance for this target: the create call succeeds with the documented body; the contract passes; the service is gone from the workspace after the run (dashboard and `GET /v1/services`); the record is committed.

## Cost (to fill; do not publish numbers before this is filled)

| Item | Value | Source URL | Date checked |
|---|---|---|---|
| Workspace plan fee, if any | _to verify_ | provider pricing page (start from render.com/pricing) | _pending_ |
| Starter instance rate and billing granularity (per second or per hour, prorated or not) | _to verify_ | same | _pending_ |
| Minimum billed time per service, if any | _to verify_ | same | _pending_ |
| Bandwidth included | _to verify_ | same | _pending_ |
| Estimated live time per run | about 5 to 15 min (create + image pull + start + about 4 min of measurement). Estimate; replace with `ready_s + measurement` from the first record | first record | _pending_ |
| Estimated cost per run | _derive from the rates above after the first run_ | | _pending_ |
| Billing notification configured | _owner to record_ | dashboard | _pending_ |

## Consequences and verification

| Consequence or risk | Owner | Mitigation/evidence | Status |
|---|---|---|---|
| The REST body may not match the API at run time | Owner | First real run; pin the verified body in this ADR afterwards | open |
| API key reach is wider than the lab | Owner | Dedicated lab account; rotate after the first run if it was ever pasted anywhere | open |
| `limit=20` and no pagination in `find_service` | Owner | Acceptable for a lab workspace with few services; revisit if the sweep finds leftovers | accepted |
| Service stays billable if delete fails | Owner | Safety-net pass; sweep by `cb-` prefix; billing notification | open |
| Verification | Claude (maker), Codex (reviewer) | Script reviewed by reading only; not run against Render | not yet verified |

## Approval

| Role | Name/date | Decision |
|---|---|---|
| Technical owner | Owner (bookchaowalit) / pending | Approve / revise (G6) |
| Security/privacy reviewer | Codex (AI checker, advisory) / not run yet | Accept controls / escalate |
| Operations/data owner | Owner (bookchaowalit) / pending | Accept operability/data boundary |
