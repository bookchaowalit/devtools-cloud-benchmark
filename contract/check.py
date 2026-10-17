"""Contract every deployed target must pass before it is measured.

Stdlib only, so the bench workflow can run it without installing the app.
"""

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

TIMEOUT_S = 15


@dataclass
class ContractResult:
    base_url: str
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def expected_item(item_id: int) -> dict:
    digest = hashlib.sha256(f"item-{item_id}".encode()).hexdigest()
    return {
        "id": item_id,
        "name": f"item-{item_id:04d}",
        "price_cents": item_id * 7 % 10_000,
        "tags": [digest[:8], digest[8:16]],
    }


def expected_digest(rounds: int) -> str:
    value = b"cloud-benchmark"
    for _ in range(rounds):
        value = hashlib.sha256(value).digest()
    return value.hex()


def _get(url: str) -> tuple[int, object]:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, None


def check(base_url: str, expected_target: str | None = None) -> ContractResult:
    base = base_url.rstrip("/")
    result = ContractResult(base)

    def expect(cond: bool, message: str) -> None:
        if not cond:
            result.failures.append(message)

    status, body = _get(f"{base}/health")
    expect(status == 200 and body == {"status": "ok"}, f"/health -> {status} {body!r}")

    status, body = _get(f"{base}/info")
    keys = {"target", "region", "commit", "uptime_s"}
    expect(status == 200 and isinstance(body, dict) and keys <= body.keys(), f"/info -> {status}")
    if expected_target and isinstance(body, dict):
        expect(body.get("target") == expected_target, f"/info target {body.get('target')!r}")

    for item_id in (1, 42, 9999):
        status, body = _get(f"{base}/items/{item_id}")
        expect(status == 200 and body == expected_item(item_id), f"/items/{item_id} -> {status}")
    status, _ = _get(f"{base}/items/0")
    expect(status == 404, f"/items/0 -> {status}, want 404")

    status, body = _get(f"{base}/work?n=1000")
    want = {"rounds": 1000, "digest": expected_digest(1000)}
    expect(status == 200 and body == want, f"/work?n=1000 -> {status}")
    status, _ = _get(f"{base}/work?n=100001")
    expect(status == 422, f"/work over the cap -> {status}, want 422")

    return result
