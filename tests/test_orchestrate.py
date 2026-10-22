"""The orchestrator always destroys what it deployed, and skips unconfigured targets."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from runner import orchestrate  # noqa: E402
from tests.test_contract import Server  # noqa: E402


def fake_targets(tmp: Path, url: str) -> Path:
    """A fly target whose deploy prints a local URL and whose destroy leaves a marker."""
    target = tmp / "targets" / "fly"
    target.mkdir(parents=True)
    (target / "deploy.sh").write_text(f"#!/bin/sh\necho 'log line' >&2\necho {url}\n")
    (target / "destroy.sh").write_text(f"#!/bin/sh\ntouch {tmp / 'destroyed'}\n")
    for script in target.iterdir():
        script.chmod(0o755)
    return tmp / "targets"


FLY_ENV = {"FLY_API_TOKEN": "test", "FLY_ORG": "test", "BENCH_RUN_ID": "test"}


class OrchestrateTest(unittest.TestCase):
    def run_fly(self, server_target: str) -> tuple[int, bool]:
        with (
            tempfile.TemporaryDirectory() as raw,
            Server("app.main:app", ROOT, {"BENCH_TARGET": server_target}) as srv,
        ):
            tmp = Path(raw)
            targets_dir = fake_targets(tmp, srv.url)
            with mock.patch.dict(os.environ, FLY_ENV):
                code = orchestrate.main(
                    [
                        "--targets",
                        "fly",
                        "--quick",
                        "--targets-dir",
                        str(targets_dir),
                        "--out",
                        str(tmp / "out"),
                    ]
                )
            return code, (tmp / "destroyed").exists()

    def test_measures_then_destroys(self):
        code, destroyed = self.run_fly("fly")
        self.assertEqual(code, 0)
        self.assertTrue(destroyed)

    def test_destroys_even_when_contract_fails(self):
        code, destroyed = self.run_fly("render")
        self.assertEqual(code, 1)
        self.assertTrue(destroyed)

    def test_skips_target_without_its_environment(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("RENDER_")}
        with mock.patch.dict(os.environ, env, clear=True):
            code = orchestrate.main(["--targets", "render", "--targets-dir", "/nonexistent"])
        self.assertEqual(code, 0)


class CleanupTest(unittest.TestCase):
    def make_targets(self, tmp: Path, destroy_body: str) -> Path:
        for name in ("fly", "render"):
            target = tmp / "targets" / name
            target.mkdir(parents=True)
            (target / "deploy.sh").write_text("#!/bin/sh\nexit 1\n")
            (target / "destroy.sh").write_text(f"#!/bin/sh\n{destroy_body}\ntouch {tmp}/{name}\n")
            for script in target.iterdir():
                script.chmod(0o755)
        return tmp / "targets"

    def test_failed_destroy_fails_the_run(self):
        with tempfile.TemporaryDirectory() as raw, mock.patch.dict(os.environ, FLY_ENV):
            targets_dir = self.make_targets(Path(raw), "exit 3")
            code = orchestrate.main(["--targets", "fly", "--targets-dir", str(targets_dir)])
        self.assertEqual(code, 1)

    def test_destroy_only_continues_after_a_failure(self):
        env = {**FLY_ENV, "RENDER_API_KEY": "test", "RENDER_OWNER_ID": "test"}
        with tempfile.TemporaryDirectory() as raw, mock.patch.dict(os.environ, env):
            tmp = Path(raw)
            targets_dir = self.make_targets(
                tmp, f'[ "$0" = "{tmp}/targets/fly/destroy.sh" ] && exit 3'
            )
            code = orchestrate.main(
                ["--destroy-only", "--targets", "fly,render", "--targets-dir", str(targets_dir)]
            )
            self.assertTrue((tmp / "render").exists())
        self.assertEqual(code, 1)

    def test_cloudrun_cleanup_needs_no_image(self):
        env = {k: v for k, v in os.environ.items() if k != "BENCH_IMAGE_GCP"}
        with (
            tempfile.TemporaryDirectory() as raw,
            mock.patch.dict(
                os.environ, {**env, "GCP_PROJECT": "test", "BENCH_RUN_ID": "test"}, clear=True
            ),
        ):
            target = Path(raw) / "targets" / "cloudrun"
            target.mkdir(parents=True)
            (target / "destroy.sh").write_text(f"#!/bin/sh\ntouch {raw}/ran\n")
            (target / "destroy.sh").chmod(0o755)
            code = orchestrate.main(
                [
                    "--destroy-only",
                    "--targets",
                    "cloudrun",
                    "--targets-dir",
                    str(Path(raw) / "targets"),
                ]
            )
            self.assertTrue((Path(raw) / "ran").exists())
        self.assertEqual(code, 0)

    def test_idle_seconds_is_bounded(self):
        with self.assertRaises(SystemExit):
            orchestrate.main(["--targets", "fly", "--idle-seconds", "999999"])


class TimeoutTest(unittest.TestCase):
    def test_deploy_timeout_kills_the_whole_process_group(self):
        with tempfile.TemporaryDirectory() as raw, mock.patch.dict(os.environ, FLY_ENV):
            tmp = Path(raw)
            target = tmp / "targets" / "fly"
            target.mkdir(parents=True)
            # The "provider CLI" is a grandchild that would outlive a plain kill of the script.
            (target / "deploy.sh").write_text(
                f"#!/bin/sh\nsleep 300 &\necho $! > {tmp}/child\nwait\n"
            )
            (target / "destroy.sh").write_text("#!/bin/sh\nexit 0\n")
            for script in target.iterdir():
                script.chmod(0o755)
            with mock.patch.object(orchestrate, "DEPLOY_TIMEOUT_S", 1):
                code = orchestrate.main(["--targets", "fly", "--targets-dir", str(tmp / "targets")])
            child = int((tmp / "child").read_text())
        self.assertEqual(code, 1)
        time.sleep(0.2)
        with self.assertRaises(ProcessLookupError):
            os.kill(child, 0)


if __name__ == "__main__":
    unittest.main()
