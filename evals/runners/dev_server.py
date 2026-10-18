"""Local dev server: the real ``api`` app on a memory store, with the workflow running locally.

    ALLOWED_ORIGINS=http://localhost:3000 python -m evals.runners.dev_server --port 8080

Each ``POST /gaps`` starts ``coverage-cascade`` for that gap in a background thread, using the local
driver with an *external* lead: the workflow waits for the browser's approval and fallback taps,
exactly as Cloud Workflows waits on callbacks. Simulated time jumps to the next reply or timeout,
paced by ``--pace`` real seconds per step so a viewer can follow it. No Google Cloud resource is
used. Internal routes are open on this server, so it binds to 127.0.0.1 only. All data is synthetic.
"""

from __future__ import annotations

import argparse
import threading
import traceback
from pathlib import Path

import uvicorn
import yaml
from fastapi.testclient import TestClient

from datagen.loader import load_data
from evals.runners.local_cascade import LocalRun
from policy.compile_cpsat import load_company_config, load_rules
from services.api.app.main import allowed_origins_from_env


class ThreadLauncher:
    """``Launcher`` for the dev server: one background workflow execution per gap."""

    def __init__(self, run: LocalRun, pace_s: float, lead_timeout_s: float):
        self.run, self.pace_s, self.lead_timeout_s = run, pace_s, lead_timeout_s
        self.errors: dict[str, str] = {}

    def start(self, gap_id: str) -> str:
        def work() -> None:
            try:
                self.run.execute(gap_id, client=TestClient(self.run.app), lead="external",
                                 pace_s=self.pace_s, lead_timeout_s=self.lead_timeout_s)
            except Exception:  # surface in the server log; the gap stays where it stopped
                self.errors[gap_id] = traceback.format_exc()
                print(f"[dev_server] workflow for {gap_id} failed:\n{self.errors[gap_id]}", flush=True)

        threading.Thread(target=work, name=f"workflow-{gap_id}", daemon=True).start()
        return f"local-dev-execution-{gap_id}"


def build(pace_s: float = 1.0, lead_timeout_s: float = 1800.0,
          origins: list[str] | None = None) -> LocalRun:
    scenarios = [yaml.safe_load(p.read_text(encoding="utf-8"))
                 for p in sorted(Path("evals/datasets/golden").glob("*.yaml"))]
    run = LocalRun(None, load_data(), load_company_config(), load_rules(), scenarios=scenarios,
                   allowed_origins=origins or allowed_origins_from_env())
    run.api.launcher = ThreadLauncher(run, pace_s, lead_timeout_s)
    return run


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--pace", type=float, default=1.0, help="real seconds per simulated step")
    args = parser.parse_args(argv)
    run = build(pace_s=args.pace)
    print(f"[dev_server] CORS origins: {allowed_origins_from_env()}  (all data is synthetic)", flush=True)
    uvicorn.run(run.app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
