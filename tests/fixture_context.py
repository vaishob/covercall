"""Build plain-dict engine contexts from policy/fixtures/*.yaml (test helper only)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

FIXTURES = Path("policy/fixtures")


def load_fixture(name: str, company: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(assignment, context)`` for a fixture merged over ``_base.yaml``."""
    base = yaml.safe_load((FIXTURES / "_base.yaml").read_text(encoding="utf-8"))
    over = yaml.safe_load((FIXTURES / f"{name}.yaml").read_text(encoding="utf-8"))
    doc = copy.deepcopy(base)
    for key in ("employee", "ledger", "gap", "assignment"):
        doc[key].update(over.get(key) or {})
        if key == "assignment" and "assignment" in over:
            doc[key] = dict(over["assignment"])
    for key in ("shifts", "other_shifts", "other_staff", "extra_ledgers", "now", "outlets"):
        if key in over:
            doc[key] = over[key]

    employee = doc["employee"]
    sid = employee["staff_id"]
    month = doc["assignment"]["start"][:7].replace("-", "")
    ledger = {"ledger_id": f"{sid}_{month}", "staff_id": sid, "month": doc["assignment"]["start"][:7],
              "synthetic": True, **doc["ledger"]}
    ledgers = [ledger] + list(doc.get("extra_ledgers") or [])
    for other in doc["other_staff"]:
        ledgers.append({"ledger_id": f"{other['staff_id']}_{month}", "staff_id": other["staff_id"],
                        "ot_hours_used": 0, "rest_days": [], "cover_requests_14d": 0,
                        "synthetic": True})
    staff = [employee] + list(doc["other_staff"])
    context = {
        "now": doc["now"],
        "gap": doc["gap"],
        "staff": {s["staff_id"]: s for s in staff},
        "shifts": list(doc["shifts"]) + list(doc["other_shifts"]),
        "ledgers": {led["ledger_id"]: led for led in ledgers},
        "outlets": {o["outlet_id"]: o for o in doc["outlets"]},
        "travel": {s["staff_id"]: {o["outlet_id"]: 15 for o in doc["outlets"]} for s in staff},
        "company": company,
    }
    return dict(doc["assignment"]), context
