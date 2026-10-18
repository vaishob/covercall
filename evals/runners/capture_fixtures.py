"""Capture real read-route responses as frontend contract fixtures.

    python -m evals.runners.capture_fixtures          # writes web/src/data/__fixtures__/*.json

Runs S-017 and S-002 through the local driver and records ``GET /gaps/{id}`` (plus ``/approval``
while pending and ``/quarantine``) after every workflow step, keeping each distinct response once,
and the final ``/events``. Also records ``/status``, ``/scenarios`` and ``/evals``. The frontend
tests map these through ``web/src/data/viewModel.ts``; ``tests/test_contract_fixtures.py`` checks
that the backend still produces exactly these responses. Regenerate after any intended change.
All data is synthetic.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from datagen.loader import load_data
from evals.runners.local_cascade import LocalRun, load_scenario
from policy.compile_cpsat import load_company_config, load_rules

FIXTURE_DIR = Path("web/src/data/__fixtures__")
SCENARIOS = {"s017": "S-017", "s002": "S-002"}


def capture(sid: str, data: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[tuple[str, Any]]]:
    """Return (fixture, every raw (path, response) read during the run)."""
    run = LocalRun(load_scenario(sid), data or load_data(), load_company_config(), load_rules())
    responses: list[tuple[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    seen: set[str] = set()

    def read(path: str) -> Any:
        resp = run.client.get(path)
        body = resp.json() if resp.status_code == 200 else None
        responses.append((path, body))
        return body

    def observe(gap_id: str, step: str) -> None:
        if not gap_id:
            return
        gap = read(f"/gaps/{gap_id}")
        approval = read(f"/gaps/{gap_id}/approval") if gap["gap"]["approval_pending"] else None
        if approval is not None and not approval.get("pending"):
            approval = None
        quarantine = read(f"/gaps/{gap_id}/quarantine")
        snap = {"gap": gap, "approval": approval, "quarantine": quarantine}
        key = json.dumps(snap, sort_keys=True)
        if key not in seen:
            seen.add(key)
            snapshots.append(dict(snap, after_step=step))

    run.observer = observe
    result = run.run()
    observe(run.gap_id, "finished")
    fixture = {
        "scenario_id": sid,
        "outcome": result["outcome"],
        "status": read("/status"),
        "scenarios": read("/scenarios"),
        "evals": read("/evals"),
        "snapshots": snapshots,
        "events": read(f"/gaps/{run.gap_id}/events"),
        "note": "Real responses from the local cascade (evals/runners/capture_fixtures.py). All data is synthetic.",
    }
    return fixture, responses


def render(fixture: dict[str, Any]) -> str:
    """Stable JSON: one compact line per top-level key and per snapshot (readable diffs, small files)."""
    def compact(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    lines = []
    for key in sorted(fixture):
        if key == "snapshots":
            body = ",\n  ".join(compact(s) for s in fixture[key])
            lines.append(f'"{key}":[\n  {body}\n]')
        else:
            lines.append(f'"{key}":{compact(fixture[key])}')
    return "{\n" + ",\n".join(lines) + "\n}\n"


def main() -> int:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    data = load_data()
    for name, sid in SCENARIOS.items():
        fixture, _ = capture(sid, data)
        path = FIXTURE_DIR / f"{name}.json"
        path.write_text(render(fixture), encoding="utf-8", newline="\n")
        print(f"{path}: {len(fixture['snapshots'])} snapshots, outcome {fixture['outcome']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
