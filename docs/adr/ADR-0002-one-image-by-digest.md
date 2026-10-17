# ADR-0002: Build one image, deploy it by digest. Railway is the exception; Cloud Run needs a copy

Template: `system-architecture-decision` (architecture-docs `templates/development-cycle/system-architecture-decision.md`).

## Document control

| Field | Value |
|---|---|
| Decision ID | ADR-0002 |
| Initiative/system | Cloud Benchmark Lab (`devtools-cloud-benchmark`), PRJ-CBL-01 |
| Decision owner | Owner (bookchaowalit) |
| Accountable approver | Owner (bookchaowalit). An AI cannot approve; this is gate G6 |
| Version/status/date | 1.0 / **proposed** (pending owner approval at G6) / 2026-10-18 |
| Related requirements | FR-08, NFR-03, NFR-06 in the architecture-docs workspace `operations/platform/cloud-benchmark-lab/06-requirements-engineering.md` |
| Maker / AI reviewer | Claude Code / Codex (not run yet) |

## Decision

- **Context and constraints:**
  - A fair comparison needs the same code on every target. For container platforms the strongest form of "same" is the same image bytes, identified by digest, not by a tag that can move.
  - The `Dockerfile` pins its base image by digest (`python:3.12-slim@sha256:…`) and installs `app/requirements.txt`, which `uv.lock` exports with exact versions. The container runs as uid 10001, one uvicorn worker, and listens on `${PORT}` (default 8080).
  - Railway deploys from source: `railway up` uploads the build context (limited by `.railwayignore`) and Railway builds the same `Dockerfile` itself. Render and Fly.io can run an existing image from a registry. Cloud Run only pulls from Google Artifact Registry (or Docker Hub remote repositories), not from GHCR directly.
  - Images in GHCR are private by default. Render and Fly.io pull the image without a registry credential in this design, so the package has to be public.
- **Decision and rationale:**
  1. `bench.yml` builds the image **once per run** (`docker/build-push-action`, tag `ghcr.io/<repo>:<commit sha>`) and records its **digest**. All image targets receive `BENCH_IMAGE=ghcr.io/<repo>@sha256:<digest>`. Rationale: identical bytes; the digest is stored in each run record (`image`).
  2. **Railway is the exception.** It builds the same `Dockerfile` at the same commit from the uploaded source, so its digest is different. The record's `target_spec.artifact` is `source` and the page says so. Rationale: building from source is how Railway is normally used and part of what the lab shows; forcing an image would test a path the owner does not use there.
  3. **Cloud Run gets a copy of the same digest.** After auth, the workflow runs `docker buildx imagetools create --tag <AR>:<sha> <GHCR digest ref>` into `asia-southeast1-docker.pkg.dev/<project>/cloud-benchmark/app` and exports `BENCH_IMAGE_GCP=<AR>@<same digest>`. `docker buildx imagetools create` copies the manifest unchanged, so the copy has exactly the same digest as the source; that is why the workflow deliberately reuses the GHCR digest value for `BENCH_IMAGE_GCP` instead of reading the copy's digest back (this is a design choice, not a gap). Rationale: Cloud Run must pull from Artifact Registry; copying the manifest avoids a second build that could differ. The first real run reads the Artifact Registry digest and compares (see consequences).
  4. The GHCR package is made **public** once, after the first push (one-time setup in the runbook). The `bench` job then **checks it on every run**: it requests an anonymous pull token and the manifest of `BENCH_IMAGE`, and stops with `GHCR package … is not public` before any target is deployed. The first dispatch is therefore expected to push the image and then stop at this check; make the package public and dispatch again.
  5. The base image is bumped deliberately (a PR changes the digest in the `Dockerfile`), never by a floating tag.
- **Options considered and rejected:**

  | Option | Why not |
  |---|---|
  | Each provider builds from source | Different builders and base layers; "same code" would be a claim, not a fact |
  | One image tag (`latest`) | Tags move; the record would not prove what ran |
  | Push the image to every provider's own registry | More setup, more accounts, more credentials to hold, with no extra information |
  | Private GHCR package with registry credentials on each provider | Four more secrets in the lab for a public demo image that holds no secrets |
  | Force Railway to run an image | Railway's normal path is source build; the lab should show that path and label it |
  | Cloud Run remote repository (proxy of GHCR) | Extra Artifact Registry feature to learn and pay for; a plain manifest copy is simpler and verifiable |

- **System context and trust boundaries:**
  - GitHub Actions builds and pushes with `GITHUB_TOKEN` (`packages: write`). GHCR serves a public, anonymous read. Google access is workload identity federation; the job requests an OIDC token (`id-token: write`).
  - The image contains only the app, its pinned dependencies and no secrets. Provider-specific values (`BENCH_TARGET`, `BENCH_REGION`, `BENCH_COMMIT`) are injected as environment variables at deploy time, not baked in.
- **Interfaces, dependencies, and failure modes:**
  - GHCR still private → the workflow's anonymous-pull check fails the `bench` job before any deploy, with a message that says how to fix it. (If that check were bypassed, Render and Fly.io would fail to pull and the record would show a deploy or readiness failure.)
  - Artifact Registry copy fails (permissions, API not enabled) → the Cloud Run target fails with a missing `BENCH_IMAGE_GCP` (skipped) or a deploy error; other targets are not affected.
  - Digest mismatch between GHCR and AR → the run record would show different digests. The first real Cloud Run run compares them and records the result in ADR-0006.
- **Data stores, ownership, retention, and residency:** Image layers are stored in GHCR (public, free for public packages at the time of writing, to be re-verified) and in Artifact Registry in `asia-southeast1` (storage cost, small). Old tags accumulate; a cleanup policy is a follow-up.
- **Authentication, authorization, secrets, and audit:** No registry credentials on Render or Fly.io. The Google service account has only Cloud Run admin and Artifact Registry writer in the lab project (plus the service-account-user permission Cloud Run deploys need; verified at the first run).
- **Availability, scale, cost, and operability:** One build per run on a free GitHub-hosted runner for a public repository. The registry copy is a manifest copy and moves little data.
- **Reversal/migration trigger:** Move Railway to an image deploy only if Railway's source build proves to be a different artifact in a way that changes a published conclusion. Move to a private package with credentials only if the image ever contains anything non-public.

## Consequences and verification

| Consequence or risk | Owner | Mitigation/evidence | Status |
|---|---|---|---|
| Railway's digest differs, so "same image" is not literally true for Railway | Owner | `artifact: source` in the record and on the page; Dockerfile and commit are identical | accepted |
| `deploy_s` for Railway includes the build, for the others only an image pull | Owner | Stated in ADR-0003; compare `ready_s` and request metrics, treat `deploy_s` as "time to live" | accepted |
| GHCR visibility is a manual step and easy to forget | Owner | Runbook step; the workflow now fails early with a clear message when the package is not public | mitigated in code; first run proves it |
| Digest equality of the Artifact Registry copy follows from the manifest copy | Owner | As a one-time confirmation at the first Cloud Run run, read the Artifact Registry digest and record both digests in ADR-0006 | accepted by design; confirm once |
| Old images accumulate in GHCR and Artifact Registry | Owner | Cleanup policy on the AR repo; GHCR retention reviewed in the monthly run | open |
| Verification | Claude (maker), Codex (reviewer) | `ci.yml` builds the image without pushing and runs the contract against the container. Not yet run on GitHub (repository not created yet). Codex review not run | not yet verified in CI |

## Approval

| Role | Name/date | Decision |
|---|---|---|
| Technical owner | Owner (bookchaowalit) / pending | Approve / revise (G6) |
| Security/privacy reviewer | Codex (AI checker, advisory) / not run yet | Accept controls / escalate |
| Operations/data owner | Owner (bookchaowalit) / pending | Accept operability/data boundary |
