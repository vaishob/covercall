# CoverCall handoff (`claude/slices-1-2`)

**All data is synthetic.**

Status: **Step 1 (audit) done.** Steps 2 to 5 are in progress. This file is updated after every step.

- Branch: `claude/slices-1-2` (forked from `main` at `3c5e56a docs: add design doc and kickstart prompt`).
- `main` is never committed to, merged, rebased or pushed from this branch.
- Sources of truth: `docs/CoverCall-Design-Doc.pdf` (§ numbers), then `docs/KICKSTART.txt`. Code is evidence only.

---

## Step 1: Audit (2026-10-18)

### What I found

- `git log --oneline` (before this branch): `a80fdf5 feat: initialize project structure`, `ed7d023 Initial commit`. AI Studio committed everything in one commit. The two docs were untracked and are now committed on `main` as `3c5e56a`.
- **Nothing has ever run.** Every Slice 2 file (`services/*/app/main.py`, `Dockerfile`, `requirements.txt`, `workflows/coverage_cascade.yaml`, `policy/timing.py`, `cloudbuild.yaml`) is a 0-byte file. `evals/runners/` and `infra/` do not exist.
- The scenario `expect` blocks and `data/*.json` were written by an agent that could not run Python. They were never produced by a solver run, so they count as hand-typed. `S-017` expects the manager `stf_001` to fill at S$0.00.

### Secrets scan

`gitleaks` and `trufflehog` are not installed, so I grepped the working tree, the full history (`git log --all -p`) and the PDF text. Patterns: `AIza…`, `-----BEGIN … PRIVATE KEY`, `"private_key"`, `ghp_`, `github_pat_`, `xox?-`, Telegram bot tokens (`\d{8,10}:AA…`), `sk-…`, `AKIA…`, `ya29.`, and generic `key|token|secret|password = <16+ chars>`.

**Result: clean.** The only hit is the placeholder `GEMINI_API_KEY="MY_GEMINI_API_KEY"` in `.env.example` (now `web/.env.example`). No hard stop.

### Layout fixes (Step 1)

- AI Studio React template files moved under `web/` with `git mv` (`docs/decisions/0003-frontend-template-moved-to-web.md`).
- `docs/CoverCall-Design-Doc.pdf.pdf` renamed to `docs/CoverCall-Design-Doc.pdf` (`docs/decisions/0004-design-doc-filename.md`).

### Rule sources checked against the live pages (2026-10-18)

| Page | URL | Last updated | Section headings confirmed |
|---|---|---|---|
| MOM: Hours of work, overtime and rest days | https://www.mom.gov.sg/employment-practices/hours-of-work-overtime-and-rest-days | 24 July 2025 | Break times; Normal hours of work; Overtime pay; Maximum hours of work; Maximum hours of overtime; Rest day; Calculate your pay for work on a rest day |
| MOM: Employment Act: who it covers | https://www.mom.gov.sg/employment-practices/employment-act/who-is-covered | 24 July 2025 | Who is covered under Part 4 |
| MOM: Overtime for part-time employees | https://www.mom.gov.sg/employment-practices/part-time-employment/overtime | 25 July 2025 | What is overtime; Calculating overtime pay |
| MOM: Who is a part-time employee | https://www.mom.gov.sg/employment-practices/part-time-employment/who-is-a-part-time-employee | 29 July 2024 | "under a contract of service to work less than 35 hours a week" |
| MOM: Monthly and daily salary | https://www.mom.gov.sg/employment-practices/salary/monthly-and-daily-salary | 8 December 2025 | Basic rate of pay, one day = (12 × monthly basic) / (52 × average days worked per week), used for rest-day pay |
| SFA: WSQ Food Safety Course (FSC) Level 1 | https://www.sfa.gov.sg/food-handler-hygiene-officer/training-courses/wsq-food-safety-course-level-1 | 24 Aug 2026 | Who must attain WSQ FSC Level 1 certification? (food handler = handles and prepares food **and beverages**; first refresher within 5 years) |

### Audit table (Slice 1 and Slice 2 files)

| File | Verdict | Why |
|---|---|---|
| `pyproject.toml` | fix | `requires-python >=3.10` and mypy `python_version = "3.10"`; KICKSTART requires 3.12. |
| `.gitignore` | keep | Covers `.env*`, `*.key`, `*credentials*.json`, `data/*.local.*`. |
| `README.md` | fix | Synthetic statement is in paragraph 1 (good), but it documents `evals.runners.e2e_cascade`, which does not exist. |
| `config/models.yaml` | fix | Claims `gemini-2.5-flash` and `gemini-2.5-pro` are pinned and verified. Google's model page (updated 2026-10-13) lists the 2.5 family as limited to existing users, and lists `gemini-3.1-flash-live-preview` as a legacy preview. Neither is verified for this project, so they become `TODO-VERIFY`. |
| `policy/company.yaml` | fix | Every comment points to the model-ID decision file. It is missing parameters the engines need (break length, split granularity, tie-break). The weights decision is undocumented. |
| `policy/rules/SG-EA4-OT-CAP-72.yaml` | keep | Matches KICKSTART §3.2 verbatim, plus the `ot_cap_69_plus_3` edge test. |
| `policy/rules/SG-EA4-COVERAGE.yaml` | keep | URL, title, section and date match the live who-is-covered page. |
| `policy/rules/SG-EA4-{DAILY-MAX-12H,NORMAL-HOURS,BREAKS,OT-RATE,REST-DAY,REST-DAY-PAY}.yaml` | keep source, fix params | Sources match the MOM page and its section headings. Some params are not used by any engine (`shift_worker_continuous_rest_hours`). |
| `policy/rules/SG-PT-OT-RATE.yaml` | fix | URL is the part-time hub page. The exact page is `/part-time-employment/overtime` ("Overtime for part-time employees"). |
| `policy/rules/SG-SFA-FSC-L1.yaml` | keep | Source verified. The barista question in §15.2 is answered by SFA's definition ("food and beverages"). |
| `policy/rules/CO-*.yaml` | fix | Params copy values that belong in `policy/company.yaml` (11 h, 2 covers in 14 days), so changing the config would not change the rule. |
| `policy/fixtures/*.yaml` | rewrite | Fixtures hand-feed derived facts (`hours_since_prev_shift_end`, `days_since_last_rest_day`) instead of a roster, so the engines never derive those facts. |
| `policy/lint_rules.py` | keep | Meets §3.4: required fields, all source subfields, ≥2 tests, `TODO-VERIFY` fails, fixture files exist. |
| `policy/validate.py` | rewrite | Imports are clean (stdlib + `yaml`). But it hard-codes statutory numbers (`13.60`, `52 × 5.5` daily rate, which MOM does not publish) and invents facts when data is missing (age 18, 2 days since rest, S$12/h). Missing data then passes as legal. |
| `policy/compile_cpsat.py` | rewrite | Not a CP-SAT compilation. Rules are evaluated in Python and the variable is pinned to 0. Invented defaults: travel 18/28 min, salary S$2,400, S$12/h, "opening shift" means the start string begins with `07:`. Split points only come from a counter-offer. |
| `policy/timing.py` | rewrite | Empty. |
| `datagen/__init__.py` | rewrite | Expect blocks never computed. Roster assigns staff round-robin, ignoring skills and rest days. `days_since_last_rest_day` is stored by hand and disagrees with the roster. 14 h turnaround is hard-coded for every candidate. |
| `datagen/__main__.py` | keep | CLI shape matches `python -m datagen build --seed 42 [--to-firestore]`. |
| `datagen/REVIEW.md` | fix | Claims an audit happened ("templates audited… offensive or stereotyped patterns excluded"). No human review took place. |
| `data/*.json`, `evals/datasets/**` | rewrite | Regenerated by the new generator. |
| `baseline/most_reliable_first.py` | rewrite | Invented per-reply minutes (4.5 / 10 / 3.5) and a hard-coded shift context. |
| `evals/compare.py` | rewrite | CoverCall and the baseline use **different** invented minute constants for time to fill (1.2 vs 4.5 per decline). That makes the comparison misleading. Time to fill belongs to Slice 2. It also silently rebuilds the dataset. |
| `tests/test_policy.py` | rewrite | Tied to the old internals. The property test generates derived facts, not rosters. |
| `tests/test_datagen.py` | rewrite | Asserts the result it wants (`baseline violations > 0`, `total_saved_sgd > 0`). |
| `services/*/app/main.py`, `Dockerfile`, `requirements.txt` | rewrite | All empty. |
| `workflows/coverage_cascade.yaml`, `cloudbuild.yaml` | rewrite | Empty. |
| `docs/design.md` | fix | Partial export (6.5 KB). KICKSTART §2 says copy the PDF text. |
| `docs/OPEN_ITEMS.md` | fix | Claims model IDs are pinned. Refers to `infra/deploy.sh` and a local workflow harness that do not exist. |
| `docs/decisions/0001-supporting-files.md` | fix | References an AI Studio container path (`/app/applet`). |
| `docs/decisions/0002-model-ids-and-sources.md` | fix | Model IDs were not verified. The part-time source pointed to the hub page. |
| `docs/runbook.md` | keep | Generic gcloud runbook. It will be aligned with `infra/` service names. |

### Violation checklist

| Check | Result |
|---|---|
| `policy/validate.py` imports `ortools`, `compile_cpsat` or shared rule logic | **No.** Clean. |
| Rule YAML with missing or invented source fields, URLs or sections | **No invented URLs.** All six pages verified live. One rule (`SG-PT-OT-RATE`) cites the less specific hub page. |
| Hard-coded design defaults that belong in `policy/company.yaml` | **Yes:** `validate.py`, `compile_cpsat.py`, `baseline`, `compare`, and the `CO-*` rule params. |
| Hand-typed `expect` blocks in scenarios | **Yes, in effect.** All 100 were written without a solver run. |
| Missing `synthetic: true` | No. Records carry it. |
| A language model deciding legality or changing state | **No.** There is no model call anywhere. |

### Remaining work, ordered and mapped to exit checks

| # | Work | Exit check served |
|---|---|---|
| 1 | Python 3.12 venv, `pyproject.toml` fixed, honest ruff, mypy and pytest baseline | Slice 1: ruff, mypy, pytest |
| 2 | Fix rule sources and params; move design defaults to `company.yaml`; models to `TODO-VERIFY` | Slice 1: `lint_rules.py` |
| 3 | Rewrite `validate.py`: facts derived from roster dicts, stdlib + yaml only | Slice 1: pytest (fixtures, AST test) |
| 4 | Rewrite `compile_cpsat.py`: real CP-SAT model, splits, top-k no-good cuts, integer money, `PlanDisagreement` | Slice 1: pytest (fixtures, property, determinism) |
| 5 | Rewrite fixtures (roster-level) and tests | Slice 1: pytest |
| 6 | Rewrite datagen: roster, ledgers, personas, travel placeholder, scenarios with computed `expect` | Slice 1: compare |
| 7 | Rewrite baseline and `evals.compare` (cost + violations only) | Slice 1: `python -m evals.compare --set golden`, violations = 0 |
| 8 | `api/events.py`: `TRANSITIONS`, hash chain, `verify_chain`, redaction, dedup, Firestore-or-fake store | Slice 2: pytest |
| 9 | `policy/timing.py` | Slice 2: pytest |
| 10 | `api`, `solver`, `guard` stub, `agent` stub parser, `persona_sim` services | Slice 2: pytest |
| 11 | `workflows/coverage_cascade.yaml` + validator against the §5.1 table | Slice 2: pytest |
| 12 | `evals/runners/local_cascade.py` (J2 = S-017, J3 = nobody replies) + `time_to_fill_min` in compare | Slice 2: local exit check |
| 13 | `infra/` scripts (syntax-checked only), `cloudbuild.yaml` | Deploy steps for the human |
