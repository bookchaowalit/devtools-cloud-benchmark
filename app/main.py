"""The one service every target runs.

It has no database and no outbound calls, so a difference between targets is a
difference in the platform (network, CPU share, scheduling, cold start), not in
some dependency the targets happen to share.
"""

import hashlib
import os
import time

from fastapi import FastAPI, HTTPException, Query

STARTED_AT = time.time()
ITEM_COUNT = 9999
MAX_WORK_ROUNDS = 100_000

app = FastAPI(title="cloud-benchmark", docs_url=None, redoc_url=None, openapi_url=None)


def make_item(item_id: int) -> dict:
    """Deterministic item, so the contract can check exact values on any target."""
    digest = hashlib.sha256(f"item-{item_id}".encode()).hexdigest()
    return {
        "id": item_id,
        "name": f"item-{item_id:04d}",
        "price_cents": item_id * 7 % 10_000,
        "tags": [digest[:8], digest[8:16]],
    }


def hash_rounds(rounds: int) -> str:
    value = b"cloud-benchmark"
    for _ in range(rounds):
        value = hashlib.sha256(value).digest()
    return value.hex()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/info")
def info() -> dict:
    return {
        "target": os.environ.get("BENCH_TARGET", "local"),
        "region": os.environ.get("BENCH_REGION", "unknown"),
        "commit": os.environ.get("BENCH_COMMIT", "unknown"),
        "uptime_s": round(time.time() - STARTED_AT, 3),
    }


@app.get("/items/{item_id}")
def item(item_id: int) -> dict:
    if not 1 <= item_id <= ITEM_COUNT:
        raise HTTPException(status_code=404, detail="item not found")
    return make_item(item_id)


@app.get("/work")
def work(n: int = Query(1000, ge=1, le=MAX_WORK_ROUNDS)) -> dict:
    return {"rounds": n, "digest": hash_rounds(n)}
