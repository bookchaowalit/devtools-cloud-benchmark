"""Deploy, measure and destroy each target in turn, from one client.

    python runner/orchestrate.py --targets railway,render,fly,cloudrun
    python runner/orchestrate.py --destroy-only --targets railway,render,fly,cloudrun

Targets run one after another in the same job, so every target is measured from
the same machine. A target whose required environment is missing is skipped,
not failed. destroy.sh runs after every deploy attempt, whatever happened.
"""

import argparse
import contextlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from runner import run  # noqa: E402
from runner.targets import TARGETS  # noqa: E402

DEPLOY_TIMEOUT_S = 20 * 60
# Four targets x 5 min stays inside the cleanup job's 30 min budget.
DESTROY_TIMEOUT_S = 5 * 60


def run_script(script: Path, env: dict, timeout: float, capture: bool) -> tuple[int, str]:
    """Run a target script in its own process group; on timeout kill the whole group,
    so a provider CLI the script started cannot outlive it and race the cleanup."""
    proc = subprocess.Popen(
        [str(script)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE if capture else None,
        text=True,
        start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, sig)
            try:
                proc.wait(timeout=10)
                break
            except subprocess.TimeoutExpired:
                continue
        raise
    return proc.returncode, out or ""


def destroy(targets_dir: Path, target: str, env: dict) -> bool:
    """True only if destroy.sh ran and reported success; never raises."""
    try:
        code, _ = run_script(targets_dir / target / "destroy.sh", env, DESTROY_TIMEOUT_S, False)
    except (subprocess.TimeoutExpired, OSError) as err:
        print(f"{target}: destroy.sh did not finish: {err}", file=sys.stderr)
        return False
    return code == 0


def bench_one(target: str, args: argparse.Namespace, env: dict) -> str:
    outcome = "failed: unexpected error"
    try:
        outcome = deploy_and_measure(target, args, env)
    except Exception as err:  # noqa: BLE001 - one target must never stop the others
        outcome = f"failed: {type(err).__name__}: {err}"
    finally:
        if not destroy(args.targets_dir, target, env):
            outcome = f"failed: destroy did not succeed (after: {outcome}); check the provider"
    return outcome


def deploy_and_measure(target: str, args: argparse.Namespace, env: dict) -> str:
    script = args.targets_dir / target / "deploy.sh"
    start = time.monotonic()
    try:
        returncode, stdout = run_script(script, env, DEPLOY_TIMEOUT_S, True)
        deploy_s = round(time.monotonic() - start, 1)
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        if returncode != 0 or not lines:
            return f"failed: deploy exited {returncode}"
        url = lines[-1]
        run_args = ["--target", target, "--url", url, "--deploy-seconds", str(deploy_s)]
        if env.get("BENCH_IMAGE"):
            run_args += ["--image", env["BENCH_IMAGE"]]
        if args.idle_seconds:
            run_args += ["--idle-seconds", str(args.idle_seconds)]
        if args.quick:
            run_args.append("--quick")
        if args.out:
            run_args += ["--out", str(args.out / target)]
        code = run.main(run_args)
        return "measured" if code == 0 else "failed: contract or readiness"
    except subprocess.TimeoutExpired:
        return f"failed: deploy timed out after {DEPLOY_TIMEOUT_S}s"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--targets", default=",".join(TARGETS))
    ap.add_argument("--idle-seconds", type=run.idle_seconds, default=0)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--destroy-only", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--targets-dir", type=Path, default=ROOT / "targets")
    args = ap.parse_args(argv)

    wanted = [t.strip() for t in args.targets.split(",") if t.strip()]
    unknown = [t for t in wanted if t not in TARGETS]
    if unknown:
        ap.error(f"unknown targets: {', '.join(unknown)}")

    env = {**os.environ}
    env.setdefault("BENCH_RUN_ID", str(int(time.time())))
    env.setdefault("BENCH_COMMIT", run.git_commit())

    outcomes: dict[str, str] = {}
    for target in wanted:
        spec = TARGETS[target]
        needed = spec.cleanup_requires if args.destroy_only else spec.requires
        missing = [name for name in needed if not env.get(name)]
        if missing:
            outcomes[target] = f"skipped: missing {', '.join(missing)}"
        elif args.destroy_only:
            ok = destroy(args.targets_dir, target, env)
            outcomes[target] = "destroyed" if ok else "failed: destroy"
        else:
            outcomes[target] = bench_one(target, args, env)
        print(f"{target}: {outcomes[target]}", flush=True)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("| Target | Outcome |\n|---|---|\n")
            fh.writelines(f"| {t} | {o} |\n" for t, o in outcomes.items())
    return 1 if any(o.startswith("failed") for o in outcomes.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
