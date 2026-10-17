"""Measure one deployed target and write its run record.

    python runner/run.py --target fly --url https://cb-123.fly.dev \
        --deploy-seconds 84.2 --image ghcr.io/...@sha256:...

The target must already be deployed (targets/<id>/deploy.sh). This script waits
for it to be ready, runs the contract, and only then measures. A target that
fails the contract gets a record with its failures and no numbers.
"""

import argparse
import hashlib
import http.client
import json
import math
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from contract.check import check  # noqa: E402
from runner.targets import TARGETS  # noqa: E402

OHA_VERSION = "1.16.0"
# sha256 of oha-linux-amd64 v1.16.0, as published in the GitHub release asset digest.
OHA_SHA256 = "620bb9e16fb53eabc9a3fc45f88bdb41fefa3fee5c05e75892011ce320391716"
SCHEMA = "cloud-benchmark.record.v1"

SETTINGS = {
    "ready_timeout_s": 600,
    "latency_requests": 300,
    "load_warmup_s": 10,
    "load_seconds": 30,
    "load_repeats": 3,
    "load_concurrency": 20,
    "work_rounds": 20_000,
    "work_seconds": 20,
    "work_concurrency": 4,
}
QUICK = {
    **SETTINGS,
    "ready_timeout_s": 60,
    "latency_requests": 30,
    "load_warmup_s": 1,
    "load_seconds": 3,
    "load_repeats": 1,
    "work_seconds": 3,
}


def oha_path() -> str:
    found = shutil.which("oha")
    if found:
        return found
    local = ROOT / ".tools" / "oha"
    if not local.exists():
        local.parent.mkdir(exist_ok=True)
        url = f"https://github.com/hatoo/oha/releases/download/v{OHA_VERSION}/oha-linux-amd64"
        partial = local.with_suffix(".part")
        urllib.request.urlretrieve(url, partial)
        digest = hashlib.sha256(partial.read_bytes()).hexdigest()
        if digest != OHA_SHA256:
            partial.unlink()
            raise RuntimeError(f"oha download checksum mismatch: {digest}")
        partial.chmod(0o755)
        partial.rename(local)
    return str(local)


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile; values must be non-empty."""
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def wait_ready(base: str, timeout_s: float) -> float:
    """Seconds until /health first returns 200. Raises TimeoutError."""
    start = time.monotonic()
    while True:
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=10) as resp:
                if resp.status == 200:
                    return time.monotonic() - start
        except (OSError, http.client.HTTPException):  # URLError is an OSError
            pass
        if time.monotonic() - start > timeout_s:
            raise TimeoutError(f"{base}/health not ready after {timeout_s}s")
        time.sleep(2)


def first_request_ms(base: str) -> float:
    start = time.perf_counter()
    with urllib.request.urlopen(f"{base}/items/1", timeout=120) as resp:
        resp.read()
    return (time.perf_counter() - start) * 1000


def sequential_latency(base: str, count: int) -> dict:
    """One keep-alive connection, one request at a time: the latency a single user sees."""
    parsed = urllib.parse.urlsplit(base)
    https = parsed.scheme == "https"
    conn_cls = http.client.HTTPSConnection if https else http.client.HTTPConnection
    conn = conn_cls(parsed.netloc, timeout=30)
    rng = random.Random(7)  # noqa: S311 - load pattern, not security
    samples, errors = [], 0
    try:
        for _ in range(count):
            path = f"{parsed.path.rstrip('/')}/items/{rng.randint(1, 9999)}"
            start = time.perf_counter()
            try:
                conn.request("GET", path)
                resp = conn.getresponse()
                resp.read()
                if resp.status != 200:
                    errors += 1
                    continue
            except (OSError, http.client.HTTPException):
                errors += 1
                conn.close()
                continue
            samples.append((time.perf_counter() - start) * 1000)
    finally:
        conn.close()
    if not samples:
        return {"requests": count, "errors": errors}
    return {
        "requests": count,
        "errors": errors,
        "p50_ms": round(percentile(samples, 50), 2),
        "p95_ms": round(percentile(samples, 95), 2),
        "p99_ms": round(percentile(samples, 99), 2),
        "max_ms": round(max(samples), 2),
    }


MAX_IDLE_S = 1800
REQUEST_TIMEOUT_S = 10


def idle_seconds(value: str) -> int:
    """argparse type: idle wait is bounded so it cannot eat the job's cleanup time."""
    seconds = int(value)
    if not 0 <= seconds <= MAX_IDLE_S:
        raise argparse.ArgumentTypeError(f"must be between 0 and {MAX_IDLE_S}")
    return seconds


def oha(url: str, seconds: int, concurrency: int, regex: bool) -> dict:
    cmd = [
        oha_path(),
        "-z",
        f"{seconds}s",
        "-c",
        str(concurrency),
        "--no-tui",
        "--output-format",
        "json",
        "-w",
        "-t",
        f"{REQUEST_TIMEOUT_S}s",
    ]
    if regex:
        cmd.append("--rand-regex-url")
    # -w lets in-flight requests finish; -t bounds each one; the subprocess timeout bounds all.
    out = subprocess.run(
        [*cmd, url],
        capture_output=True,
        text=True,
        check=True,
        timeout=seconds + REQUEST_TIMEOUT_S + 30,
    )
    return json.loads(out.stdout)


def load(url: str, s: dict, seconds: int, concurrency: int, repeats: int, regex: bool) -> dict:
    oha(url, s["load_warmup_s"], concurrency, regex)
    rps, p50, p95, p99, errors, total = [], [], [], [], 0, 0
    for _ in range(repeats):
        r = oha(url, seconds, concurrency, regex)
        codes = r.get("statusCodeDistribution", {})
        failed = sum(r.get("errorDistribution", {}).values())
        total += sum(codes.values()) + failed
        errors += failed + sum(n for code, n in codes.items() if not str(code).startswith("2"))
        rps.append(r["summary"]["requestsPerSec"])
        pct = r["latencyPercentiles"]
        if pct.get("p50") is None:  # oha reports no percentiles when nothing succeeded
            continue
        p50.append(pct["p50"] * 1000)
        p95.append(pct["p95"] * 1000)
        p99.append(pct["p99"] * 1000)

    def median_ms(values: list[float]) -> float | None:
        return round(statistics.median(values), 2) if values else None

    return {
        "concurrency": concurrency,
        "seconds": seconds,
        "repeats": repeats,
        "rps_median": round(statistics.median(rps), 1),
        "p50_ms": median_ms(p50),
        "p95_ms": median_ms(p95),
        "p99_ms": median_ms(p99),
        "error_rate": round(errors / total, 5) if total else None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--target", required=True, choices=sorted(TARGETS) + ["local"])
    ap.add_argument("--url", required=True)
    ap.add_argument("--image", default=None, help="image reference deployed, with digest")
    ap.add_argument("--deploy-seconds", type=float, default=None)
    ap.add_argument(
        "--idle-seconds",
        type=idle_seconds,
        default=0,
        help="wait this long after warm-up, then time the first request",
    )
    ap.add_argument("--quick", action="store_true", help="smoke settings; never published")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    s = QUICK if args.quick else SETTINGS
    base = args.url.rstrip("/")
    started = datetime.now(UTC)
    target = TARGETS.get(args.target)
    out = args.out or ROOT / "results" / f"{started:%Y%m%dT%H%M%SZ}-{args.target}"
    out.mkdir(parents=True, exist_ok=True)

    record = {
        "schema": SCHEMA,
        "target": args.target,
        "target_spec": (
            {k: v for k, v in asdict(target).items() if k not in {"requires", "cleanup_requires"}}
            if target
            else None
        ),
        "url_host": urllib.parse.urlsplit(base).netloc,
        "started_at": started.isoformat(),
        "commit": git_commit(),
        "image": args.image,
        "settings": {**s, "quick": args.quick, "idle_seconds": args.idle_seconds},
        "client": {
            "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
            "runner": os.environ.get("RUNNER_NAME"),
            "location": os.environ.get("BENCH_CLIENT_LOCATION", "not controlled"),
            "python": platform.python_version(),
        },
        "load_generator": f"oha {OHA_VERSION}",
        "metrics": {},
        "contract_failures": [],
    }

    def save() -> None:
        (out / "record.json").write_text(json.dumps(record, indent=2) + "\n")

    try:
        record["metrics"]["deploy_s"] = args.deploy_seconds
        record["metrics"]["ready_s"] = round(wait_ready(base, s["ready_timeout_s"]), 2)
        contract = check(base, expected_target=None if args.target == "local" else args.target)
    except (OSError, ValueError, http.client.HTTPException) as err:  # TimeoutError is an OSError
        record["contract_failures"] = [f"{type(err).__name__}: {err}"]
        save()
        print(f"{args.target}: not ready or contract unreachable: {err}", file=sys.stderr)
        return 1
    if not contract.ok:
        record["contract_failures"] = contract.failures
        save()
        print(
            f"{args.target}: contract failed:\n  " + "\n  ".join(contract.failures), file=sys.stderr
        )
        return 1

    try:
        m = record["metrics"]
        m["latency_sequential"] = sequential_latency(base, s["latency_requests"])
        # oha's --rand-regex-url treats "." as a literal, so the host needs no escaping.
        m["load_items"] = load(
            f"{base}/items/[1-9][0-9]{{0,3}}",
            s,
            s["load_seconds"],
            s["load_concurrency"],
            s["load_repeats"],
            regex=True,
        )
        m["load_cpu"] = load(
            f"{base}/work?n={s['work_rounds']}",
            s,
            s["work_seconds"],
            s["work_concurrency"],
            1,
            regex=False,
        )
        if args.idle_seconds:
            time.sleep(args.idle_seconds)
            m["first_request_after_idle_ms"] = round(first_request_ms(base), 1)
    except (
        OSError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
        http.client.HTTPException,
    ) as err:
        # A failed measurement still leaves a record, and is not published (see build_site).
        record["measurement_error"] = f"{type(err).__name__}: {err}"
        record["finished_at"] = datetime.now(UTC).isoformat()
        save()
        print(f"{args.target}: measurement failed: {record['measurement_error']}", file=sys.stderr)
        return 1
    record["finished_at"] = datetime.now(UTC).isoformat()
    save()
    print(f"{args.target}: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
