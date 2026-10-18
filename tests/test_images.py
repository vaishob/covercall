"""Each Cloud Run image contains every repo module its service imports (first deploy: api crashed
with ModuleNotFoundError: services.persona_sim, which local tests cannot see)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SERVICES = ["api", "solver", "agent", "guard", "persona_sim", "connectors"]
LOCAL_ROOTS = {"services", "policy", "datagen", "baseline", "evals", "infra", "config"}


def _module_file(name: str) -> Path | None:
    parts = name.split(".")
    if parts[0] not in LOCAL_ROOTS:
        return None
    for candidate in (Path(*parts).with_suffix(".py"), Path(*parts) / "__init__.py"):
        if candidate.exists():
            return candidate
    return None


def _imports(path: Path) -> set[str]:
    """Every import in the file, including lazy ones inside functions."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


def _closure(entry: Path) -> set[Path]:
    seen: set[Path] = set()
    todo = [entry]
    while todo:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        for name in _imports(path):
            found = _module_file(name)
            if found is not None:
                todo.append(found)
    return seen


def _copied(service: str) -> list[str]:
    text = Path(f"services/{service}/Dockerfile").read_text(encoding="utf-8")
    return [m.group(1) for m in re.finditer(r"^COPY (\S+) \S+$", text, re.M) if "requirements" not in m.group(1)]


@pytest.mark.parametrize("service", SERVICES)
def test_image_contains_every_imported_module(service: str) -> None:
    copied = _copied(service)
    for path in _closure(Path(f"services/{service}/app/main.py")):
        rel = path.as_posix()
        assert any(rel == c or rel.startswith(c.rstrip("/") + "/") for c in copied), (
            f"{service} image is missing {rel}")
