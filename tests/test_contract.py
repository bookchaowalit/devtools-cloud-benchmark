"""The contract passes on the real service and fails on a wrong one.

Each test starts a real uvicorn process, so this is what a deployed target sees.
"""

import json
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from contract.check import check  # noqa: E402
from runner import run  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, app: str, cwd: Path, env: dict | None = None):
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            app,
            "--port",
            str(self.port),
            "--no-access-log",
            "--log-level",
            "warning",
        ]
        self.cwd, self.env = cwd, env

    def __enter__(self):
        import os

        self.proc = subprocess.Popen(self.cmd, cwd=self.cwd, env={**os.environ, **(self.env or {})})
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(f"{self.url}/health", timeout=1).close()
                return self
            except OSError:
                time.sleep(0.1)
        self.proc.kill()
        raise RuntimeError("server did not start")

    def __exit__(self, *exc):
        self.proc.terminate()
        self.proc.wait(timeout=10)


WRONG_APP = textwrap.dedent(
    """
    from app.main import app as real
    from fastapi import FastAPI
    app = FastAPI()

    @app.get("/items/{item_id}")
    def item(item_id: int):
        return {"id": item_id, "name": "wrong"}

    app.mount("/", real)
    """
)


class ContractTest(unittest.TestCase):
    def test_real_service_passes(self):
        with Server("app.main:app", ROOT, {"BENCH_TARGET": "fly"}) as srv:
            result = check(srv.url, expected_target="fly")
        self.assertEqual(result.failures, [])

    def test_wrong_target_name_fails(self):
        with Server("app.main:app", ROOT, {"BENCH_TARGET": "render"}) as srv:
            result = check(srv.url, expected_target="fly")
        self.assertTrue(any("target" in f for f in result.failures), result.failures)

    def test_wrong_service_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "wrong.py").write_text(WRONG_APP)
            env = {"PYTHONPATH": str(ROOT)}
            with Server("wrong:app", Path(tmp), env) as srv:
                result = check(srv.url)
        self.assertTrue(any("/items/" in f for f in result.failures), result.failures)


class RunnerTest(unittest.TestCase):
    def test_percentile_nearest_rank(self):
        values = [float(v) for v in range(1, 101)]
        self.assertEqual(run.percentile(values, 50), 50.0)
        self.assertEqual(run.percentile(values, 99), 99.0)
        self.assertEqual(run.percentile([3.0], 95), 3.0)
        # nearest rank is ceil(p * n): p95 of 1..30 is the 29th value
        self.assertEqual(run.percentile([float(v) for v in range(1, 31)], 95), 29.0)

    def test_quick_run_writes_a_record(self):
        with Server("app.main:app", ROOT) as srv, tempfile.TemporaryDirectory() as tmp:
            code = run.main(["--target", "local", "--url", srv.url, "--quick", "--out", tmp])
            record = json.loads((Path(tmp) / "record.json").read_text())
        self.assertEqual(code, 0)
        self.assertEqual(record["contract_failures"], [])
        self.assertTrue(record["settings"]["quick"])
        for key in ("ready_s", "latency_sequential", "load_items", "load_cpu"):
            self.assertIn(key, record["metrics"])
        self.assertEqual(record["metrics"]["load_items"]["error_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
