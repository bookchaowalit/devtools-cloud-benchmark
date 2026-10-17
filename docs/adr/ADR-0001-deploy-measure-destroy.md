# ADR-0001: Deploy, measure, destroy. Ephemeral runs, one client, one instance, contract first

Template: `system-architecture-decision` (architecture-docs `templates/development-cycle/system-architecture-decision.md`).

## Document control

| Field | Value |
|---|---|
| Decision ID | ADR-0001 |
| Initiative/system | Cloud Benchmark Lab (`devtools-cloud-benchmark`), PRJ-CBL-01 |
| Decision owner | Owner (bookchaowalit) |
| Accountable approver | Owner (bookchaowalit). An AI cannot approve; this is gate G6 |
| Version/status/date | 1.0 / **proposed** (pending owner approval at G6) / 2026-10-18 |
| Related requirements | FR-05, FR-06, FR-07, FR-09, NFR-01, NFR-02, NFR-05, NFR-06, NFR-07 in the architecture-docs workspace `operations/platform/cloud-benchmark-lab/06-requirements-engineering.md` |
| Maker / AI reviewer | Claude Code / Codex (not run yet; see the workspace `reviews/README.md`) |

## Decision

- **Context and constraints:**
  - The owner wants verifiable evidence of real multi-cloud / PaaS experience, not logos. A number is only evidence if a reader can see how it was produced.
  - A solo owner cannot afford always-on resources on four or more providers just to keep a showcase alive. Cost between runs has to be close to zero.
  - Production stays on Vercel, Railway, Cloudflare and Neon. The lab must not touch production or company systems, so it uses separate accounts, budgets and a separate public repository.
  - Platforms differ in sizes, autoscalers, edge networks and billing. A like-for-like comparison is impossible. The honest goal is a comparison with its limits written next to it.
  - None of the deploy scripts has run against a real account yet. The first real run of each target is its acceptance test.
- **Decision and rationale:**
  1. **Ephemeral runs.** Every run creates a fresh deployment named `cb-<BENCH_RUN_ID>` (Railway: a fresh deployment of the one lab service), measures it, and deletes it. Nothing keeps running or billing between runs. Rationale: near-zero cost; no state to drift; every run starts from the same clean state.
  2. **One small stateless service** (`app/main.py`: `/health`, `/info`, `/items/{id}`, `/work`), no database and no outbound calls. Rationale: the only variable is the platform (network, CPU share, scheduling, cold start), not a dependency the targets share.
  3. **Contract first.** `contract/check.py` checks exact values (item contents, SHA-256 digest of `/work`, 404 and 422 behaviour, `/info.target`). A target that fails the contract gets a run record with its failures and no numbers. Rationale: a fast wrong answer must never look like a good number.
  4. **One client.** All targets are measured one after another from the same GitHub-hosted job. The client location is not controlled and is recorded as such. Rationale: one client keeps the targets comparable inside a run; the page tells readers to compare within a run, not across runs.
  5. **One instance, Singapore.** Every target is held to one instance in Singapore (`asia-southeast1` / `sin` / `singapore`). Rationale: throughput then compares one instance with one instance, not one provider's autoscaler with another's. The exact size of each target is recorded; sizes are the nearest each provider offers, not equal.
  6. **Destroy always, and a failed destroy fails the run.** `runner/orchestrate.py` runs `destroy.sh` after every deploy attempt (in a `finally`), whatever happened, with a 5 minute limit; a script that hangs is killed together with the provider CLI it started (own process group). If `destroy.sh` exits non-zero or times out, the target's outcome becomes `failed: destroy did not succeed …` and the run exits non-zero. A second pass runs in a **separate `cleanup` job** (`needs: bench`, `if: always()`, `orchestrate.py --destroy-only`), so it still runs when the `bench` job hit its timeout or was cancelled. `destroy.sh` must be safe to run twice, safe after a failed deploy, and must fail when it cannot tell whether the resource is gone (a failed lookup is never read as "already gone").
  7. **Manual trigger only.** `bench.yml` is `workflow_dispatch` only. Any schedule is a separate owner cost decision.
  8. **Records are the product.** Each run writes `results/<timestamp>-<target>/record.json` (schema `cloud-benchmark.record.v1`) with commit, image reference, target spec, settings, client and load generator. `runner/build_site.py` publishes only records that are not `quick`, have no contract failures and no `measurement_error`. The `bench` job uploads `results/` as an artifact (`bench-results-<run id>`); a separate `publish` job (the only one with `contents: write`, and with no provider credentials) copies the records onto the branch tip, rebuilds `site/data.json` and pushes, retrying up to three times.
- **Options considered and rejected:**

  | Option | Why not |
  |---|---|
  | Keep one deployment per provider running and sample continuously | Standing cost on every provider, and it measures noise over time, not the platform. Reversal path below |
  | Measure from several client regions | Needs clients in several places (cost and operations) and the first version should be explainable in one sentence. A Singapore client is a follow-up |
  | Compare autoscaling | Different autoscalers are not comparable without a long, costly test. Out of scope |
  | A realistic app with a database | Adds a shared dependency and shared network path; hides the platform. The lab measures the platform |
  | Run everything on the owner's machine | Not reproducible, and the CI hosting policy forbids using the local machine as a runner |
  | Publish vendor marketing or third-party benchmark numbers | Not verifiable by the owner; no run record |
  | Scheduled weekly runs from day one | Cost decision not made; no real run has happened yet |

- **System context and trust boundaries:**
  - GitHub Actions (public repo, GitHub-hosted `ubuntu-24.04`) is the only place that holds provider credentials. It talks to four provider control planes, pulls from GHCR, and measures the public URLs of the deployed targets. Results go back to the repository by commit; the page is static.
  - Provider accounts are lab-only and separate from production. A leaked lab token must not reach production data.
- **Interfaces, dependencies, and failure modes:**
  - Script contract: `deploy.sh` prints the public base URL as the only stdout line (logs go to stderr); `destroy.sh` prints nothing that matters and is idempotent. See `targets/README.md`.
  - Deploy fails or times out (20 min) → outcome `failed`, `destroy.sh` still runs. Contract fails or the target is unreachable → record with failures, no numbers, `destroy.sh` still runs. A measurement error → record with `measurement_error`, not published. Destroy fails or times out (5 min) → outcome `failed: destroy did not succeed`, the run is red, and the `cleanup` job tries again. If the runner itself dies, the `cleanup` job (a different runner) still runs; resources can still be orphaned if both fail, and the operations runbook has a sweep by the `cb-` name prefix.
  - A target with missing credentials is skipped, not failed.
- **Data stores, ownership, retention, and residency:** No database. Run records are JSON files committed to `results/`; they are public and kept forever in git. Records contain no secrets (`requires` is excluded from `target_spec`) and only the host part of the deployment URL.
- **Authentication, authorization, secrets, and audit:** Provider tokens are GitHub secrets (`RAILWAY_TOKEN`, `RENDER_API_KEY`, `FLY_API_TOKEN`); non-secret identifiers are repository variables; Google uses workload identity federation (OIDC) with no key file. The workflow-level permission is `contents: read`; `packages: write` and `id-token: write` exist only on the `bench` job, `id-token: write` on the `cleanup` job, and `contents: write` only on the `publish` job. Provider credentials are in the environment of the `bench` and `cleanup` jobs only, not `publish`. Workflow inputs reach shell scripts only through environment variables (`BENCH_TARGETS`, `BENCH_IDLE_SECONDS`), and `idle_seconds` is bounded to 1800. Audit trail: workflow runs plus committed records.
- **Availability, scale, cost, and operability:** Cost per run is the live time of each target (deploy + ready + about 4 minutes of measurement) times that provider's rate. The estimate and the date it was checked are kept in each provider ADR. GitHub-hosted minutes are free for public repositories.
- **Reversal/migration trigger:** Move to scheduled or continuous measurement only when the owner makes a cost decision for it and a Singapore client exists. Add a second client region when a published conclusion depends on client distance.

## Consequences and verification

| Consequence or risk | Owner | Mitigation/evidence | Status |
|---|---|---|---|
| Cold runs only: no long-term trend, noisy-neighbour effects are sampled once per run | Owner | Page says so; repeat runs before drawing a conclusion; `first_request_after_idle_ms` probe covers scale-to-zero separately | accepted |
| Client location is not controlled, so latency includes an unknown path | Owner | Recorded as `BENCH_CLIENT_LOCATION`; page says compare within a run only | accepted |
| `deploy_s` is not the same event on every provider (Railway builds from source; Render returns before the first deploy is live) | Owner | `ready_s` is recorded separately; each provider ADR states what its `deploy_s` includes | accepted |
| Orphaned resources if destroy fails or the runner dies | Owner | Failed destroy fails the run; separate `cleanup` job; process-group kill on timeout; idempotent scripts that fail when the lookup fails; `cb-` prefix; sweep runbook; budget alerts on every account | mitigated in code; open until each target's first real run verifies a clean account |
| Region is declared by the script (`BENCH_REGION`), not measured | Owner | Check the region in each provider's dashboard at the first real run and record it in the provider ADR | open |
| Scripts have never run against a real account | Owner | First run per target is the acceptance test (provider ADR table). No number is published before that | open |
| Verification | Claude (maker), Codex (reviewer) | `pytest`: 14 passed (contract passes on the real service and fails on a wrong one; `build_site` publishes only full passing records; orchestrator destroys even when the contract fails, skips targets without credentials, fails the run when destroy fails, continues destroy-only after a failure, bounds idle time, and kills a timed-out deploy's whole process group); `ruff check`: clean (2026-10-18, local). Codex review not run yet | partly done |

## Approval

| Role | Name/date | Decision |
|---|---|---|
| Technical owner | Owner (bookchaowalit) / pending | Approve / revise (G6) |
| Security/privacy reviewer | Codex (AI checker, advisory) / not run yet | Accept controls / escalate |
| Operations/data owner | Owner (bookchaowalit) / pending | Accept operability/data boundary |
