# CoverCall

**All data is synthetic.** CoverCall fills a sudden shift gap for a fictional three-outlet café chain in Singapore (Bugis, Tampines, Jurong East: real area names, synthetic business). It finds legal, low-cost cover, runs the outreach cascade, and proves every assignment against the Singapore Employment Act with a constraint solver and an independent validator. A language model never decides legality. No real employee data, proprietary code or confidential material is used anywhere in this repository.

Design doc: [`docs/CoverCall-Design-Doc.pdf`](docs/CoverCall-Design-Doc.pdf) (text export in `docs/design.md`). Build status and handoff notes: [`docs/HANDOFF.md`](docs/HANDOFF.md).

## Run it locally (Python 3.12)

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -r pyproject.toml --extra dev

python policy/lint_rules.py              # every rule has a full source and >= 2 tests
python -m datagen build --seed 42        # synthetic data + 60 golden / 40 held-out scenarios
pytest                                   # fixtures on both engines, property tests, determinism
python -m evals.compare --set golden     # CoverCall vs most-reliable-first baseline; exit 1 on any violation
```

## How legality is decided

| Piece | Path | What it does |
|---|---|---|
| Rule specs | `policy/rules/*.yaml` | One file per rule, each citing its public source (MOM, SFA) or `policy/company.yaml` for synthetic company rules |
| Semantics | `docs/decisions/0005-rule-semantics.md` | The single prose definition both engines implement |
| Solver | `policy/compile_cpsat.py` | OR-Tools CP-SAT: compiles the specs into constraints, ranks up to 3 plans (one person, or a split of two) |
| Validator | `policy/validate.py` | Independent plain Python (stdlib + yaml only). Re-checks every plan. Any disagreement is a P0 (`plan.disagreement`, gap held) |
| Baseline | `baseline/most_reliable_first.py` | Ask the most reliable free person first, with no cost or legality reasoning |

## Where each Google service is used

| Component | Path | Google Cloud service | Status |
|---|---|---|---|
| `coverage-cascade` | `workflows/coverage_cascade.yaml` | Cloud Workflows | See `docs/HANDOFF.md` |
| `api` | `services/api/` | Cloud Run (FastAPI) | See `docs/HANDOFF.md` |
| `solver` | `services/solver/` | Cloud Run (OR-Tools) | See `docs/HANDOFF.md` |
| `agent` | `services/agent/` | Cloud Run (ADK, Gemini Flash on Vertex AI) | Model ID `TODO-VERIFY`; deterministic stub parser locally |
| `guard` | `services/guard/` | Cloud Run (CPU) | Deterministic stub `stub-v0` until the Gemma guard (Slice 5); not a model |
| `persona-sim` | `services/persona_sim/` | Cloud Run (Gemini Flash) | Deterministic stub text locally |
| State and event log | `services/api/app/events.py` | Firestore (`(default)` and `sim`) | See `docs/HANDOFF.md` |
| Deploy scripts | `infra/` | gcloud | Written and syntax-checked, not run |

---
*All data is synthetic.*
