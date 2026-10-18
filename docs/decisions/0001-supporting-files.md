# Decision 0001: Supporting Files and Repository Root Layout

- **Date:** 2026-10-18
- **PDF Section:** §13.1 (Repository layout), §6 (Policy engine), §10 (Evaluation and the release gate), §15.2 (Open items to verify)

## Context
Section 13.1 defines the top-level directory structure of `covercall/`. To implement automated rule linting, independent fixture storage, pure deadline calculations, CLI baseline comparisons, open-item tracking, and automated unit/property tests in Slices 1 and 2, several supporting paths are needed alongside the canonical layout. Additionally, the workspace container mounts the project root at `/app/applet` alongside the web preview harness.

## Decision
1. Add the following supporting paths recorded here per §2:
   - `policy/fixtures/` — YAML test fixtures referenced by `policy/rules/*.yaml`.
   - `policy/lint_rules.py` — CI linter enforcing complete rule metadata, source fields, `>=2` tests, and zero `TODO-VERIFY` strings.
   - `policy/timing.py` — Pure deadline, slack, reply-window, fan-out, and escalation functions (§5.2).
   - `evals/compare.py` — CLI runner comparing CoverCall against `baseline/most_reliable_first.py` on `golden` and `heldout` sets (§10.2, §13.2).
   - `docs/OPEN_ITEMS.md` — Tracked verification items mirroring §15.2.
   - `tests/` — Pytest and Hypothesis test suites for dual compilation, AST isolation, timing, and hash-chain verification.
2. Keep the repository rooted at `/app/applet` so `python -m datagen build --seed 42`, `python -m evals.compare --set golden`, and `pytest` execute directly from the repo root.

## Alternatives Considered
- Embedding fixtures inline in rule YAML files: rejected because §6.1 specifies `fixture: <name>` references.
- Keeping timing formulas inline inside the FastAPI router: rejected because decoupling pure math in `policy/timing.py` enables deterministic unit testing.

## Update (2026-10-18, claude/slices-1-2)
The `/app/applet` path above was the AI Studio container and does not apply to this repo. Other
supporting files added since: `tests/fixture_context.py` (fixture merge helper),
`policy/fixtures/_base.yaml` (shared fixture defaults), `datagen/loader.py`, `datagen/personas.py`,
`datagen/scenarios.py`, `evals/cascade_sim.py`, and `docs/HANDOFF.md`.
