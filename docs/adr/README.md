# Architecture decision records

Every provider in the lab must earn its place with an ADR that answers "why this provider, not
another" and says what it is uniquely good at. A target appears on the results page only after
its ADR exists **and** it has a real measured run that passed the contract.

Template: `system-architecture-decision` in the architecture-docs repository
(`templates/development-cycle/system-architecture-decision.md`). The full SDLC document set for this
initiative (requirements, risks, cost plan, runbook, go-live checklist, gates) lives in the
architecture-docs repository under `operations/platform/cloud-benchmark-lab/`.

| ADR | Decision | Status |
|---|---|---|
| [ADR-0001](ADR-0001-deploy-measure-destroy.md) | Deploy, measure, destroy: ephemeral runs, one client, one instance, contract first | proposed |
| [ADR-0002](ADR-0002-one-image-by-digest.md) | Build one image, deploy it by digest; Railway builds from source; Cloud Run uses an Artifact Registry copy | proposed |
| [ADR-0003](ADR-0003-railway.md) | Railway as a target | proposed |
| [ADR-0004](ADR-0004-render.md) | Render as a target | proposed |
| [ADR-0005](ADR-0005-fly.md) | Fly.io as a target | proposed |
| [ADR-0006](ADR-0006-cloud-run.md) | Google Cloud Run as a target | proposed |

Status values: `proposed` (written, waiting for the owner's approval at gate G6), `accepted`
(approved by the owner), `superseded`. An AI cannot approve an ADR.

## Honest status

None of the deploy scripts has run against a real account. Each provider ADR has a "First real run"
table that stays empty until the run happens. The ADR's "Cost" table is filled from the provider's
pricing page with the date it was checked; until then no cost figure is published.

## Adding a provider

1. Write the ADR first (copy the structure of ADR-0003 to ADR-0006): what it is uniquely good at,
   why it is in the lab and not another, exact configuration, fairness, setup, first real run, cost.
2. Add an entry to `runner/targets.py`, `targets/<id>/deploy.sh` and `destroy.sh`.
3. Run the bench for that target only; fill the "First real run" table.
4. Only then does it appear on the page.
