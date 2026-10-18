"""CLI entrypoint for `python -m datagen build --seed 42` (§3.8, §8.2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from datagen import build_synthetic_dataset


def _seed_firestore(data_dir: Path) -> None:
    from google.cloud import firestore  # type: ignore[import-untyped]

    from services.common.store import SIM_DATABASE

    default_db = firestore.Client(database="(default)")
    sim_db = firestore.Client(database=SIM_DATABASE)

    outlets = json.loads((data_dir / "outlets.json").read_text(encoding="utf-8"))
    for o in outlets:
        default_db.collection("outlets").document(o["outlet_id"]).set(o)

    staff = json.loads((data_dir / "staff.json").read_text(encoding="utf-8"))
    for s in staff:
        default_db.collection("staff").document(s["staff_id"]).set(s)

    ledgers = json.loads((data_dir / "ledgers.json").read_text(encoding="utf-8"))
    for lid, ldoc in ledgers.items():
        default_db.collection("ledgers").document(lid).set(ldoc)

    shifts = json.loads((data_dir / "shifts.json").read_text(encoding="utf-8"))
    for sh in shifts:
        default_db.collection("shifts").document(sh["shift_id"]).set(sh)

    personas = json.loads((data_dir / "sim_personas.json").read_text(encoding="utf-8"))
    for pid, pdoc in personas.items():
        sim_db.collection("personas").document(pid).set(pdoc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CoverCall synthetic data generator")
    sub = parser.add_subparsers(dest="cmd")

    build_p = sub.add_parser("build", help="Build synthetic dataset and scenarios")
    build_p.add_argument("--seed", type=int, default=42, help="Deterministic RNG seed")
    build_p.add_argument(
        "--to-firestore",
        action="store_true",
        help="Also write generated collections to Firestore (default) and sim databases",
    )

    args = parser.parse_args(argv)
    if args.cmd != "build":
        parser.print_help()
        return 1

    summary = build_synthetic_dataset(seed=args.seed)
    if args.to_firestore:
        _seed_firestore(Path("data"))

    print(
        f"datagen build complete (seed={args.seed}, synthetic=True): "
        f"{summary['outlets']} outlets, {summary['staff']} staff, "
        f"{summary['golden_scenarios']} golden scenarios, "
        f"{summary['heldout_scenarios']} held-out scenarios "
        f"(travel_source={summary['travel_source']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
