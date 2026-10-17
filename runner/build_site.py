"""Collect published run records into site/data.json for the static page.

Quick (smoke) runs, and runs that failed the contract or the measurement, are never published.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def collect(results_dir: Path) -> list[dict]:
    records = []
    for path in results_dir.glob("*/record.json"):
        record = json.loads(path.read_text())
        failed = record["contract_failures"] or record.get("measurement_error")
        if record["settings"].get("quick") or failed:
            continue
        records.append({"id": path.parent.name, **record})
    return sorted(records, key=lambda r: r["started_at"])


def main() -> int:
    records = collect(ROOT / "results")
    out = ROOT / "site" / "data.json"
    out.write_text(
        json.dumps({"schema": "cloud-benchmark.site.v1", "runs": records}, indent=1) + "\n"
    )
    print(f"{out.relative_to(ROOT)}: {len(records)} record(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
