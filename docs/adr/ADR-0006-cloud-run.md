# ADR-0006: Google Cloud Run as a lab target

Template: `system-architecture-decision` (architecture-docs `templates/development-cycle/system-architecture-decision.md`).

## Document control

| Field | Value |
|---|---|
| Decision ID | ADR-0006 |
| Initiative/system | Cloud Benchmark Lab (`devtools-cloud-benchmark`), PRJ-CBL-01, target `cloudrun` |
| Decision owner | Owner (bookchaowalit) |
| Accountable approver | Owner (bookchaowalit). An AI cannot approve; this is gate G6 |
| Version/status/date | 1.0 / **proposed** (pending owner approval at G6) / 2026-10-18 |
| Related requirements | FR-03, FR-04, FR-08, FR-12, NFR-01, NFR-02, NFR-03, NFR-04 in the architecture-docs workspace `operations/platform/cloud-benchmark-lab/06-requirements-engineering.md` |
| Related ADRs | ADR-0001 (deploy, measure, destroy), ADR-0002 (one image by digest; Cloud Run needs an Artifact Registry copy) |
| Maker / AI reviewer | Claude Code / Codex (not run yet) |

## Decision

- **Context and constraints:**
  - Cloud Run runs containers as a serverless service: it scales by request, down to zero instances, and bills for the time requests are being served (with request-based billing) rather than for a standing instance.
  - Cloud Run pulls images from Google Artifact Registry, not from GHCR. The workflow copies the same image digest into Artifact Registry (ADR-0002).
  - CI authenticates with **workload identity federation** (GitHub OIDC). There is no service-account key file anywhere. The federation is restricted to this repository.
  - Cloud Run is the only hyperscaler in Phase 1. It brings IAM, billing accounts, budgets and APIs that the PaaS targets do not have; that is part of what the lab shows, and part of the setup cost.
  - Nothing in this target has run against a real account yet.
- **What Cloud Run is uniquely good at (as the provider documents it; the lab checks only part of this):**
  - Scale to zero with fine-grained billing, many concurrent requests per instance (the lab sets 80), and a deploy that is one command from an image.
  - The Google Cloud ecosystem around it: IAM, workload identity federation, VPC connectivity, Secret Manager, Artifact Registry and budgets, the surroundings an enterprise team expects.
  - What the lab can show: time to live from an image, cold start after idle, and a 1 vCPU instance under load. What it cannot show: IAM design depth, VPC, Secret Manager, multi-service architectures.
- **Why it is in the lab, and why not another:** Cloud Run is the "serverless containers on a hyperscaler" reference, and it is the one target whose setup (OIDC federation, least-privilege service account, budgets) is itself evidence of cloud engineering. Other hyperscaler container services (for example AWS App Runner or ECS on Fargate, or Azure Container Apps) are not in Phase 1; each can be added later, one at a time, with its own ADR and a real measured run.
- **Decision and rationale:** Include `cloudrun` as a Phase 1 target. Per run: deploy a service `cb-<run id>` in `asia-southeast1` from the Artifact Registry copy of the digest, `--min-instances 0 --max-instances 1`, measure, then delete the service.
- **Options considered and rejected:**

  | Option | Why not |
  |---|---|
  | Service-account JSON key in a GitHub secret | A long-lived key in a public repository's secrets; federation avoids it |
  | Deploy from source (`gcloud run deploy --source`) | Cloud Build with its own builder; ADR-0002 requires the same image bytes |
  | Cloud Run remote repository proxying GHCR | Extra feature to learn and pay for; a manifest copy is simpler |
  | Min instances above 0 | Breaks scale-to-zero and costs between requests |
  | Use an existing production or company GCP project | Violates the isolation rule |
  | Authenticated (private) service with an identity token on the client | More moving parts in the client; the service holds no data |

- **System context and trust boundaries:**
  - The bench job requests an OIDC token (`id-token: write`) and exchanges it through a workload identity pool and provider for a short-lived access token of the service account `GCP_SERVICE_ACCOUNT` in the lab project `GCP_PROJECT`. The provider's attribute condition must allow only `assertion.repository == 'bookchaowalit/devtools-cloud-benchmark'`.
  - The service account holds Cloud Run admin and Artifact Registry writer in the lab project only, plus whatever else a Cloud Run deploy needs (see the consequences table).
  - The Cloud Run service is public (`--allow-unauthenticated`) for the duration of the run.
- **Interfaces, dependencies, and failure modes:**
  - Needs these APIs enabled in the lab project: Cloud Run, Artifact Registry, IAM Credentials, Security Token Service.
  - `--allow-unauthenticated` requires permission to set the invoker policy, and an organization policy that restricts public principals would block it. A standalone lab project avoids this; the first run confirms it.
  - Deploying a Cloud Run service acts as the runtime service account (the default Compute Engine service account unless set). The deploying account therefore needs permission to act as it: grant `roles/iam.serviceAccountUser` to `cb-bench` on the runtime service account (the default Compute Engine service account, `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com`), not on the whole project. This is part of the setup; the first run confirms it, and the exact minimum roles are recorded in this ADR afterwards.
  - `destroy.sh` lists services with `--filter metadata.name=cb-<run id>` and deletes the match, so it is safe to run twice. If the list fails the script fails, so a lookup error is never taken for "already gone". The `cleanup` job authenticates through workload identity federation itself and needs only `GCP_PROJECT` (it does not need the image).
  - If `GCP_WORKLOAD_IDENTITY_PROVIDER` is not set, the auth and copy steps are skipped; the target then lacks `BENCH_IMAGE_GCP` and is skipped, not failed.
- **Data stores, ownership, retention, and residency:** Image copies in Artifact Registry `asia-southeast1` (repository `cloud-benchmark`, image `app`); service logs in Cloud Logging (retention per default). Region: `asia-southeast1` (Singapore).
- **Authentication, authorization, secrets, and audit:** No secret for Google at all. Audit: Cloud Audit Logs in the lab project plus the workflow run.
- **Availability, scale, cost, and operability:** `--min-instances 0 --max-instances 1 --concurrency 80`, 1 vCPU, 512 MiB, request-based billing. After the run the service is deleted; Artifact Registry storage remains and is small. A budget with alerts is set on the billing account of the lab project.
- **Reversal/migration trigger:** Remove the target if keyless federation cannot be kept restricted to this repository, or if the lab project cannot be kept free of production resources.

## Exact configuration used

From `runner/targets.py`, `targets/cloudrun/` and `bench.yml`.

| Item | Value | Source |
|---|---|---|
| Target id | `cloudrun` | `runner/targets.py` |
| Region | `asia-southeast1` (label "Singapore") | `runner/targets.py`, `deploy.sh` |
| Size | 1 vCPU, 512 MiB, max 1 instance, request-based billing | `runner/targets.py`, `deploy.sh` |
| Scale to zero | yes (`--min-instances 0`) | `deploy.sh` |
| Artifact | `image`: the same digest, copied to Artifact Registry as `BENCH_IMAGE_GCP` | `runner/targets.py`, `bench.yml` |
| Requires | variable `GCP_PROJECT`; `BENCH_IMAGE_GCP` (set by the workflow); variables `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT` for the auth step | `runner/targets.py`, `bench.yml` |
| Deploy | `gcloud run deploy cb-<run id> --project $GCP_PROJECT --region asia-southeast1 --image $BENCH_IMAGE_GCP --port 8080 --cpu 1 --memory 512Mi --min-instances 0 --max-instances 1 --concurrency 80 --allow-unauthenticated --set-env-vars BENCH_TARGET=cloudrun,BENCH_REGION=asia-southeast1,BENCH_COMMIT=<sha> --quiet`; prints `status.url` from `gcloud run services describe` | `deploy.sh` |
| Destroy | `gcloud run services list --filter metadata.name=cb-<run id>`; `gcloud run services delete cb-<run id> --quiet` if listed; fails if the list fails | `destroy.sh` |
| Cleanup env | `GCP_PROJECT` | `runner/targets.py` (`cleanup_requires`) |
| Registry copy | `docker buildx imagetools create --tag asia-southeast1-docker.pkg.dev/$GCP_PROJECT/cloud-benchmark/app:$GITHUB_SHA $BENCH_IMAGE`; `BENCH_IMAGE_GCP` is `<repo>@<the GHCR digest>` (the digest of the copy is not read back) | `bench.yml` |
| Auth action | `google-github-actions/auth` v3.0.0 and `setup-gcloud` v3.0.1, pinned by SHA | `bench.yml` |
| Workflow permission | `id-token: write` on the `bench` and `cleanup` jobs only (workflow-level is `contents: read`) | `bench.yml` |

## How the comparison is unfair to or favours Cloud Run

| Effect | Direction | Note |
|---|---|---|
| A full 1 vCPU, versus 0.5 CPU on Render and a burstable share on Fly.io | **Favours Cloud Run** on `load_cpu` and `load_items` | Read the size column; do not rank by rps across different sizes |
| Request-based billing throttles CPU outside requests; a probe after idle starts a new instance | Real trade-off, visible only with `idle_seconds` | The default run has `idle_seconds=0` |
| Concurrency 80 on one instance, max 1 instance | Neutral | The 20-connection load stays on one instance; autoscaling is deliberately not measured |
| Google's front end sits in front of every request | Cannot be removed | Part of the platform; same idea as Fly's edge |
| Image pulled from a regional Artifact Registry in the same region | **Favours Cloud Run** on `ready_s` against Render and Fly.io, which pull from GHCR | Disclosed on the page |
| `deploy_s` includes the image pull and the revision becoming ready | Comparable with Fly.io; not with Render (API call only) or Railway (build included) | Use `ready_s` and request metrics for comparison |

## Setup (one time; owner action, see the runbook in architecture-docs `11-deployment-go-live.md`)

1. Create a **dedicated GCP project** for the lab (not a production or company project), link a billing account, and create a **budget with alert thresholds** on it. Record the project id as the repository variable `GCP_PROJECT`.
2. Enable the Cloud Run, Artifact Registry, IAM Credentials and Security Token Service APIs.
3. Create the Artifact Registry Docker repository `cloud-benchmark` in `asia-southeast1`. Add a cleanup policy so old copies do not accumulate.
4. Create a workload identity pool and an OIDC provider for `https://token.actions.githubusercontent.com`, with an attribute condition limiting it to the repository `bookchaowalit/devtools-cloud-benchmark`. Store the provider's full resource name as `GCP_WORKLOAD_IDENTITY_PROVIDER`.
5. Create a service account (for example `cb-bench`) with Cloud Run admin and Artifact Registry writer in the project, allow the federated identity of this repository to impersonate it (Workload Identity User), and store its email as `GCP_SERVICE_ACCOUNT`. Also grant it `roles/iam.serviceAccountUser` on the runtime service account (the default Compute Engine service account unless the deploy script sets another), so Cloud Run can deploy acting as it.
6. Run the bench with `targets=cloudrun` and fill the table below. Run again with `idle_seconds` set to record the cold-start probe.

## First real run (to fill)

| Date | Result (contract pass/fail, run record path) | deploy_s | ready_s | Issues and fixes |
|---|---|---|---|---|
| _pending_ | _not run yet_ | | | |

Acceptance for this target: the keyless auth step succeeds in both the `bench` and `cleanup` jobs; the digest of the Artifact Registry copy, read back, equals the GHCR digest (record both); the deploy works with the documented roles (record the exact minimum set); the contract passes; `gcloud run services list` shows no `cb-` service afterwards; the record is committed.

## Cost (to fill; do not publish numbers before this is filled)

| Item | Value | Source URL | Date checked |
|---|---|---|---|
| Free tier and what counts against it | _to verify_ | provider pricing page (start from cloud.google.com/run/pricing) | _pending_ |
| CPU, memory and request rates for request-based billing, in `asia-southeast1` | _to verify_ | same | _pending_ |
| Artifact Registry storage rate and free allowance | _to verify_ | cloud.google.com/artifact-registry/pricing | _pending_ |
| Network egress | _to verify_ | provider pricing page | _pending_ |
| Estimated live time per run | about 3 to 10 min (deploy + start + about 4 min of measurement). Estimate; replace with real values from the first record | first record | _pending_ |
| Estimated cost per run | _derive from the rates above after the first run_ | | _pending_ |
| Budget and alert thresholds | _owner to record amounts_ | Billing console | _pending_ |

## Consequences and verification

| Consequence or risk | Owner | Mitigation/evidence | Status |
|---|---|---|---|
| Federation misconfigured too broadly would let other repositories impersonate the service account | Owner | Attribute condition on the repository; verify with a negative test if practical | open |
| Minimum IAM roles are not yet proven | Owner | First real run; record the exact roles here | open |
| Manifest copy keeps the digest (assumed; the workflow does not read it back) | Owner | Read the Artifact Registry digest and compare with GHCR at the first run | open |
| Artifact Registry storage grows | Owner | Cleanup policy; review in the monthly run | open |
| Cloud Run needs a billing account, which is the largest cost-control surface in the lab | Owner | Budget alerts on the billing account; dedicated project | open |
| Verification | Claude (maker), Codex (reviewer) | Scripts and workflow steps reviewed by reading only; not run against Google Cloud | not yet verified |

## Approval

| Role | Name/date | Decision |
|---|---|---|
| Technical owner | Owner (bookchaowalit) / pending | Approve / revise (G6) |
| Security/privacy reviewer | Codex (AI checker, advisory) / not run yet | Accept controls / escalate |
| Operations/data owner | Owner (bookchaowalit) / pending | Accept operability/data boundary |
