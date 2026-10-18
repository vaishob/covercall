"""Deploy config consistency: Firestore database IDs (decision 0022)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from services.common.store import SIM_DATABASE

# Firestore: "database_id should be 4-63 characters, and valid characters are /[a-z][0-9]-/".
DB_ID = re.compile(r"^[a-z][a-z0-9-]{2,61}[a-z0-9]$")


def test_sim_database_id_is_valid_and_consistent() -> None:
    assert DB_ID.match(SIM_DATABASE), SIM_DATABASE
    env = Path("infra/env.sh").read_text(encoding="utf-8")
    assert f'export SIM_DB_ID="{SIM_DATABASE}"' in env
    rules = json.loads(Path("infra/firebase.json").read_text(encoding="utf-8"))["firestore"]
    assert {r["database"] for r in rules} == {"(default)", SIM_DATABASE}


def test_no_code_opens_a_database_by_the_old_id() -> None:
    for path in [*Path("services").rglob("*.py"), *Path("datagen").rglob("*.py"), *Path("infra").glob("*")]:
        if path.is_file() and path.suffix in {".py", ".sh", ".json"}:
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"""(FirestoreStore|Client)\([^)]*["']sim["']|databases/sim\b|"database": "sim\"""", text), path
