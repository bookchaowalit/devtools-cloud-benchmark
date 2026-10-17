# Targets

Each directory holds two scripts the bench workflow calls from the repository root:

| Script | Does | Output |
|---|---|---|
| `deploy.sh` | Creates a fresh deployment named `cb-$BENCH_RUN_ID` | the public base URL, as the only line on stdout (logs go to stderr) |
| `destroy.sh` | Removes what `deploy.sh` created | nothing; safe to run twice, and after a failed deploy |

Environment every script gets: `BENCH_RUN_ID`, `BENCH_COMMIT`, `BENCH_IMAGE` (GHCR reference with
digest) and the target's own secrets listed in `runner/targets.py`.

**Status:** none of these scripts has run against a real account yet. The first real run of each
target is the test; record its result in that target's ADR before publishing numbers.
