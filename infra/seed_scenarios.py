"""Seed scenario documents for the deployed demo (run by infra/60_seed.sh; not run in this build).

The planner-facing part (no personas) goes to ``(default)/scenarios``; the full scenario, including
persona overrides, goes to ``sim/scenarios`` where only persona-sim can read it.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def main() -> None:  # pragma: no cover - needs Firestore
    from services.common.store import SIM_DATABASE, FirestoreStore

    default, sim = FirestoreStore("(default)"), FirestoreStore(SIM_DATABASE)
    for path in sorted(Path("evals/datasets/golden").glob("*.yaml")):
        scen = yaml.safe_load(path.read_text(encoding="utf-8"))
        public = {k: scen[k] for k in ("id", "description", "now", "seed", "gap")}
        public["overrides"] = scen.get("overrides") or []
        default.set(f"scenarios/{scen['id']}", dict(public, synthetic=True))
        sim.set(f"scenarios/{scen['id']}", scen)
    travel = yaml.safe_load(Path("data/travel_cache.json").read_text(encoding="utf-8"))
    default.set("config/travel", travel)


if __name__ == "__main__":
    main()
