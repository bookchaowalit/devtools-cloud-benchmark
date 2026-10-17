"""Only full, passing runs reach the results page."""

import json
import tempfile
import unittest
from pathlib import Path

from runner.build_site import collect


def write(results: Path, name: str, **overrides) -> None:
    record = {
        "target": "fly",
        "started_at": overrides.pop("started_at", "2026-10-18T00:00:00+00:00"),
        "settings": {"quick": False},
        "contract_failures": [],
        "metrics": {},
        **overrides,
    }
    (results / name).mkdir()
    (results / name / "record.json").write_text(json.dumps(record))


class BuildSiteTest(unittest.TestCase):
    def test_publishes_only_full_passing_runs_in_time_order(self):
        with tempfile.TemporaryDirectory() as raw:
            results = Path(raw)
            write(results, "b-ok", started_at="2026-10-18T02:00:00+00:00")
            write(results, "a-ok", started_at="2026-10-18T01:00:00+00:00")
            write(results, "quick", settings={"quick": True})
            write(results, "contract", contract_failures=["/health -> 500"])
            write(results, "measure", measurement_error="TimeoutExpired: oha")
            ids = [r["id"] for r in collect(results)]
        self.assertEqual(ids, ["a-ok", "b-ok"])


if __name__ == "__main__":
    unittest.main()
