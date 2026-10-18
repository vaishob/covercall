"""Rule-spec linter (§3.4, §6.1, §10.3).

Fails with a nonzero exit if any spec in policy/rules/*.yaml is missing:
- id, title, kind, every source subfield (publisher, title, url, section,
  source_last_updated, retrieved), applies_when, params, message
- at least 2 tests with existing fixture files in policy/fixtures/
- or if any field in the YAML contains TODO-VERIFY.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

REQUIRED_TOP_FIELDS = (
    "id",
    "title",
    "kind",
    "source",
    "applies_when",
    "params",
    "message",
    "tests",
)

REQUIRED_SOURCE_FIELDS = (
    "publisher",
    "title",
    "url",
    "section",
    "source_last_updated",
    "retrieved",
)

ALLOWED_KINDS = {"hard", "cost", "soft", "applicability_gate", "data_gate"}


def _contains_todo_verify(obj: Any) -> bool:
    if isinstance(obj, str):
        return "TODO-VERIFY" in obj
    if isinstance(obj, dict):
        return any(_contains_todo_verify(k) or _contains_todo_verify(v) for k, v in obj.items())
    if isinstance(obj, list):
        return any(_contains_todo_verify(item) for item in obj)
    return False


def lint_rules_dir(
    rules_dir: Path = Path("policy/rules"),
    fixtures_dir: Path = Path("policy/fixtures"),
) -> list[str]:
    errors: list[str] = []
    if not rules_dir.exists():
        return [f"Rules directory not found: {rules_dir}"]

    rule_files = sorted(rules_dir.glob("*.yaml"))
    if not rule_files:
        return [f"No rule YAML files found in {rules_dir}"]

    for path in rule_files:
        try:
            spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{path}: invalid YAML ({exc})")
            continue

        if not isinstance(spec, dict):
            errors.append(f"{path}: top-level YAML must be a mapping")
            continue

        if _contains_todo_verify(spec):
            errors.append(f"{path}: contains TODO-VERIFY")

        for field in REQUIRED_TOP_FIELDS:
            if field not in spec or spec[field] is None or spec[field] == "":
                errors.append(f"{path}: missing required field '{field}'")

        if spec.get("id") and path.stem != spec.get("id"):
            errors.append(f"{path}: file stem '{path.stem}' does not match id '{spec.get('id')}'")

        if spec.get("kind") not in ALLOWED_KINDS:
            errors.append(f"{path}: invalid kind '{spec.get('kind')}'")

        source = spec.get("source")
        if not isinstance(source, dict):
            errors.append(f"{path}: 'source' must be a mapping")
        else:
            for sfield in REQUIRED_SOURCE_FIELDS:
                val = source.get(sfield)
                if val is None or str(val).strip() == "":
                    errors.append(f"{path}: missing required source subfield 'source.{sfield}'")

        tests = spec.get("tests")
        if not isinstance(tests, list) or len(tests) < 2:
            errors.append(f"{path}: must define at least 2 tests")
        else:
            for idx, test_case in enumerate(tests):
                if not isinstance(test_case, dict):
                    errors.append(f"{path}: test[{idx}] must be a mapping")
                    continue
                fix_name = test_case.get("fixture")
                expect = test_case.get("expect")
                if not fix_name:
                    errors.append(f"{path}: test[{idx}] missing 'fixture'")
                else:
                    fix_path = fixtures_dir / f"{fix_name}.yaml"
                    if not fix_path.exists():
                        errors.append(f"{path}: fixture file not found '{fix_path}'")
                if expect not in {"ok", "violation", "not_applicable"}:
                    errors.append(f"{path}: test[{idx}] invalid expect '{expect}'")

    return errors


def main() -> int:
    errors = lint_rules_dir()
    if errors:
        for err in errors:
            print(f"LINT ERROR: {err}", file=sys.stderr)
        return 1
    rule_count = len(list(Path("policy/rules").glob("*.yaml")))
    print(f"policy/lint_rules.py: OK ({rule_count} rules verified with complete sources and >=2 tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
