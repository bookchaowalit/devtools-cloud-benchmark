"""Create or delete the Render bench service through the Render REST API.

    python3 targets/render/render_api.py deploy    # prints the service URL
    python3 targets/render/render_api.py destroy

Needs RENDER_API_KEY, RENDER_OWNER_ID, BENCH_RUN_ID, BENCH_COMMIT, BENCH_IMAGE.
RENDER_PLAN overrides the plan (default "starter", 0.5 CPU / 512 MB).
Stdlib only. The request body follows Render's public API reference; it has not
been run against a real account yet (see targets/README.md).
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.render.com/v1"
REGION = "singapore"


def call(method: str, path: str, body: dict | None = None) -> object:
    req = urllib.request.Request(  # noqa: S310 - fixed https API host
        f"{API}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {os.environ['RENDER_API_KEY']}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        raw = resp.read()
    return json.loads(raw) if raw else None


def service_name() -> str:
    return f"cb-{os.environ['BENCH_RUN_ID']}"


def find_service() -> dict | None:
    name = service_name()
    found = call("GET", f"/services?name={name}&ownerId={os.environ['RENDER_OWNER_ID']}&limit=20")
    for entry in found or []:
        service = entry.get("service", entry)
        if service.get("name") == name:
            return service
    return None


def deploy() -> int:
    owner = os.environ["RENDER_OWNER_ID"]
    body = {
        "type": "web_service",
        "name": service_name(),
        "ownerId": owner,
        "image": {"ownerId": owner, "imagePath": os.environ["BENCH_IMAGE"]},
        "envVars": [
            {"key": "BENCH_TARGET", "value": "render"},
            {"key": "BENCH_REGION", "value": REGION},
            {"key": "BENCH_COMMIT", "value": os.environ["BENCH_COMMIT"]},
        ],
        "serviceDetails": {
            "runtime": "image",
            "plan": os.environ.get("RENDER_PLAN", "starter"),
            "region": REGION,
            "healthCheckPath": "/health",
            "numInstances": 1,
        },
    }
    created = call("POST", "/services", body)
    service = created.get("service", created)
    url = service.get("serviceDetails", {}).get("url")
    if not url:
        print(f"render: no url in create response: {json.dumps(created)[:500]}", file=sys.stderr)
        return 1
    # Creation returns before the first deploy is live; run.py waits on /health.
    print(url)
    return 0


def destroy() -> int:
    try:
        service = find_service()
        if service:
            call("DELETE", f"/services/{service['id']}")
            print(f"render: deleted {service['id']}", file=sys.stderr)
        for _ in range(10):  # deletion can take a moment to show in the list
            if not find_service():
                break
            time.sleep(3)
        else:
            print("render: service still listed after delete", file=sys.stderr)
            return 1
    except (urllib.error.URLError, OSError, ValueError) as err:
        print(f"render: cleanup failed: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action not in {"deploy", "destroy"}:
        raise SystemExit(__doc__)
    raise SystemExit(deploy() if action == "deploy" else destroy())
