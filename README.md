# CoverCall

**All data is synthetic.** CoverCall is a hands-free, provably legal shift absence coverage engine and autonomous outreach cascade built for a fictional three-outlet café chain in Singapore (Bugis, Tampines, Jurong East) as a solo entry in the Google Cloud AI Builder Cup. No real employee data, proprietary code, or confidential records exist anywhere in this repository.

## What CoverCall Does

When a shift lead gets a sudden sick call at 6:02am before a 7:00am opening shift, CoverCall:
1. **Proves legality deterministically**: Compiles declarative statutory and company rules (`policy/rules/*.yaml`) twice—into an OR-Tools CP-SAT constraint solver (`policy/compile_cpsat.py`) and an independent plain-Python validator (`policy/validate.py`). A language model never decides legality. Any disagreement between the solver and the validator raises a release-blocking P0 (`plan.disagreement -> HELD`).
2. **Closes the outreach loop**: Executes a deterministic state machine (`coverage-cascade` on Cloud Workflows) with durable callback endpoints, dynamic reply windows (`policy/timing.py`), automatic fan-out when slack falls below threshold, re-solving on counter-offers, and timely escalation (`t_esc`).
3. **Verifies every transition**: Writes an append-only SHA-256 tamper-evident event hash chain (`gaps/{gapId}/events/{seq}`) with deterministic PII redaction before persistence and fail-closed safety guarding.

## Google Cloud Architecture Map

| Component | Path | Google Cloud Service | Responsibility |
|---|---|---|---|
| `coverage-cascade` | `workflows/coverage_cascade.yaml` | Cloud Workflows | Deterministic state machine (`REPORTED -> GUARDED -> SOLVED -> OUTREACH -> COMMITTING -> FILLED` / `ESCALATED -> RESOLVED` / `HELD` / `CANCELLED`); durable callback waits |
| `api` | `services/api/` | Cloud Run (FastAPI) | Public HTTP entry (`/gaps`, `/approvals`, `/replies`, `/test`), internal workflow transitions (`/internal/*`), tamper-evident event chain |
| `solver` | `services/solver/` | Cloud Run (OR-Tools CP-SAT) | Deterministic top-k candidate ranking and independent validator check (`policy/compile_cpsat.py` + `policy/validate.py`) |
| `agent` | `services/agent/` | Cloud Run (ADK + Gemini Flash) | Structured reply parsing (`parse_reply`), verified plan explanation (`explain_plan`), and under-300-char offer drafting (`draft_offer`) |
| `guard` | `services/guard/` | Cloud Run (CPU-only) | Fail-closed safety guard (`stub-v0` in Slices 1–2; Gemma 3 270M in Slice 5) performing deterministic PII redaction and prompt-injection quarantine |
| `persona-sim` | `services/persona_sim/` | Cloud Run (Gemini Flash) | Simulated staff responder reading only the `sim` Firestore database (`personas/{staffId}`) |
| `connectors` | `services/connectors/` | Cloud Run | Telegram webhook adapter and Google Maps Routes API transit client |
| `Firestore` | `infra/` | Cloud Firestore (Native) | Operational state in `(default)` database and isolated persona profiles in `sim` database |

## Quickstart (Slices 1 & 2)

```bash
# 1. Lint rule specs (verifies every rule has a complete source and >=2 tests)
python3 policy/lint_rules.py

# 2. Generate seeded synthetic dataset, 60 golden scenarios, and 40 held-out scenarios
python3 -m datagen build --seed 42

# 3. Run unit, fixture, AST-isolation, and Hypothesis property tests
pytest

# 4. Compare CoverCall vs. most-reliable-first baseline on the golden set
python3 -m evals.compare --set golden

# 5. Run end-to-end J2 (cascade) and J3 (escalation) verification
python3 -m evals.runners.e2e_cascade
```

---
*All data is synthetic.*
