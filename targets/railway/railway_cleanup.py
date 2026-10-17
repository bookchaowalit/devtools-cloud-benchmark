"""Cancel or remove every live deployment of the Railway lab service, then verify.

`railway down` only removes the latest SUCCESS deployment, so a deployment that is
still queued or building when a run is interrupted would survive it. This lists
all recent deployments and acts on each one that is not already finished.
Exits non-zero if the list fails or anything is still live afterwards.
"""

import json
import os
import subprocess
import sys

IN_FLIGHT = {"QUEUED", "WAITING", "INITIALIZING", "BUILDING", "DEPLOYING", "NEEDS_APPROVAL"}
RUNNING = {"SUCCESS", "SLEEPING", "CRASHED"}


def railway(*args: str) -> str:
    out = subprocess.run(
        ["railway", *args],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return out.stdout


def live_deployments(service: str) -> list[dict]:
    raw = json.loads(railway("deployment", "list", "--service", service, "--limit", "50", "--json"))
    items = raw.get("deployments", raw) if isinstance(raw, dict) else raw
    return [d for d in items if str(d.get("status", "")).upper() in IN_FLIGHT | RUNNING]


def main() -> int:
    service = os.environ["RAILWAY_SERVICE"]
    try:
        for dep in live_deployments(service):
            status = str(dep["status"]).upper()
            mutation = "deploymentCancel" if status in IN_FLIGHT else "deploymentRemove"
            railway(
                "api",
                f"mutation($id: String!) {{ {mutation}(id: $id) }}",
                "--raw-var",
                f"id={dep['id']}",
            )
            print(f"railway: {mutation} {dep['id']} ({status})", file=sys.stderr)
        remaining = live_deployments(service)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError) as err:
        print(f"railway: cleanup failed: {err}", file=sys.stderr)
        return 1
    # Removal is asynchronous; REMOVING is fine, anything still running is not.
    if remaining:
        ids = ", ".join(f"{d['id']} ({d['status']})" for d in remaining)
        print(f"railway: still live after cleanup: {ids}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
