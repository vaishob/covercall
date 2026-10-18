# CoverCall handoff (`claude/slices-1-2`)

**All data is synthetic.**

## Final report (2026-10-18)

**Stopped at HARD STOP 2:** both exit checks pass. Slice 1 passes in full. Slice 2 passes in its local form; nothing is deployed.

| Slice | Status | Tag | Proof |
|---|---|---|---|
| 1. Engine and evidence | **Done** | `slice-1` | ruff clean; mypy clean; `lint_rules` 15/15; pytest green; `evals.compare --set golden` exit 0, CoverCall violations 0 |
| 2. Cascade foundation | **Done locally, not deployed** | `slice-2-local` | pytest 149 passed; `evals.runners.local_cascade` J2 PASS, J3 PASS (`verify_chain` OK, 0 violations, every P0 counter 0); `evals.compare` exit 0 on golden and held-out with `time_to_fill_min` |

The original Slice 2 exit check (J2/J3 **on Cloud Run** in `asia-southeast1`) is **not met**. This run may not touch Google Cloud. The deploy scripts are written and checked with `bash -n` and ShellCheck 0.11.0, but have never run.

### Commands run on the final commit and their output

```
$ ruff check .                                  All checks passed!
$ mypy                                          Success: no issues found in 54 source files
$ python policy/lint_rules.py                   OK (15 rules verified with complete sources and >=2 tests)
$ pytest                                        149 passed in 25.51s
$ bash -n infra/*.sh ; shellcheck -x infra/*.sh all OK, shellcheck exit 0
$ python -m evals.runners.local_cascade         (exit 0)
J2 (S-017): state=FILLED outcome=filled time_to_fill_min=15.47 verify_chain=OK events=9 violations=0
  p0={'unapproved_outbound': 0, 'pii_leak': 0, 'escalation_late': 0, 'outcome_missing': 0,
      'solver_validator_disagreements': 0, 'rule_violations': 0}
  events: gap.reported -> input.guarded -> plan.solved -> plan.approved -> reply.decline -> reply.counter
          -> offer.timeout -> reply.accept -> commit.ok
  offers: stf_019 07:00-15:00 decline; stf_022 07:00-15:00 countered (09:00-15:00);
          stf_008 07:00-15:00 timeout; stf_028 07:00-09:00 accepted  => filled by stf_028 07-09 + stf_022 09-15
  PASS
J3 (S-002): state=RESOLVED outcome=borrow verify_chain=OK events=10 violations=0 p0=all 0
  events: gap.reported -> input.guarded -> plan.solved -> plan.approved -> offer.timeout x4
          -> escalation.due -> fallback.chosen
  offers: stf_016 timeout [single:1]; stf_026, stf_031, stf_029 timeout [fanout:2]
  PASS
```

### Compare tables (real runs only; synthetic SGD; simulated minutes)

`python -m evals.compare --set golden` (exit 0):

| Metric | CoverCall | Baseline (most reliable first) |
|---|---|---|
| Gaps filled | 50/60 | 59/60 |
| Median overtime cost per gap | S$0.00 | S$0.00 |
| Total overtime cost | S$75.52 | S$3,434.68 |
| Total incremental labour cost | S$1,746.52 | S$6,322.68 |
| Rule violations (hard rules) | **0** | 19 |
| Scenarios with a violation | 0 | 18 |
| Solver/validator disagreements | 0 | n/a |
| Median time to fill (simulated min) | 1.82 | 1.78 |
| Fills arriving after shift start | 0 | 2 |

CoverCall: 10 gaps escalated and resolved by a fallback, 0 held; P0 counters all 0; 0 chains failing `verify_chain`; 0 results differing from `expect`.

`python -m evals.compare --set heldout` (exit 0):

| Metric | CoverCall | Baseline |
|---|---|---|
| Gaps filled | 36/40 | 40/40 |
| Median overtime cost per gap | S$0.00 | S$0.00 |
| Total overtime cost | S$0.00 | S$2,422.67 |
| Total incremental labour cost | S$1,005.00 | S$4,142.67 |
| Rule violations (hard rules) | **0** | 15 |
| Scenarios with a violation | 0 | 14 |
| Median time to fill (simulated min) | 1.06 | 3.05 |
| Fills arriving after shift start | 0 | 2 |

How to read these honestly:
- **CoverCall fills fewer gaps than the baseline.** Most CoverCall escalations are reports less than ~41 minutes before the shift. With the PDF defaults (10-minute buffer, 15-minute escalation lead) and 16-minute travel, the slack is already below the lead, so CoverCall calls the lead at once (decision 0009). The baseline ignores travel and deadlines: 2 of its fills per set arrive after the shift starts, and its fills break hard rules 19 and 15 times.
- Medians are S$0 for both arms. Most gaps can be covered by someone with spare contract hours. The difference is in totals and violations.
- Staff outside Part 4 cost S$0 (no statutory overtime; contractual pay not modelled). Travel times are placeholders, not Routes API data. The guard and the reply parser are deterministic stubs (`stub-v0`), not models.

### Every TODO-VERIFY and open item
From `docs/OPEN_ITEMS.md`:
- **Gemini model IDs (all five roles): TODO-VERIFY.** `config/models.yaml` pins nothing. Services that need a model refuse to start.
- Submission deadline and rules; the Innovation & Feasibility weight; competitor facts; Singapore F&B evidence.
- Whether breaks count toward the 12-hour day (engines count them; stricter).
- Public-holiday dates for the demo week; outlet coordinates.
- Workflows YAML on the real service (`next: continue` in a parallel for-loop, `map.get`, `sys.get_env`, OIDC `audience`).
- `FirestoreStore` transactions; IAM condition on the Firestore database name; Firebase multi-database rules config; the gitleaks image tag.
- Gemini availability in `asia-southeast1`.
- Not encoded: public holidays, the shift-worker 30-hour rest form. Placeholder: Routes API travel. Not started: the §8.3 human reply review.
- Finding: the escalation lead escalates short-notice gaps at once (product decision).

### Decisions made (docs/decisions/)
- 0001 supporting files (updated); 0002 model IDs and sources (partly superseded)
- 0003 React template moved to `web/`; 0004 design-doc file name
- 0005 rule semantics shared by both engines; 0006 CP-SAT formulation, weights, determinism
- 0007 synthetic data shape; 0008 baseline behaviour and comparison
- 0009 `t_esc` locked at approval, windows clamped (fixed a real `escalation_late` P0)
- 0010 local verification (memory store + local driver; no emulator); 0011 fan-out with one callback per offer
- 0012 persona delivery and time compression; 0013 raw text out of the workflow, api proxies guard/parse
- 0014 commit re-check, cancel via callbacks, approvals, `cost_saved_sgd`

### The single next action for you
Confirm and pin the Gemini model IDs in `config/models.yaml` (see OPEN_ITEMS for what Google's page showed on 2026-10-13). Then run the deploy steps below in a dev project. The first `gcloud workflows deploy` is the only validation the workflow YAML has not yet had.

---

## For the human: deploy steps (not run; run them in order and approve each)

Prerequisites: a Google Cloud project with billing; `gcloud` authenticated as an owner (`gcloud auth login`, `gcloud auth application-default login`); the Firebase CLI for security rules; Python 3.12 with the repo's venv (for seeding); Docker is not needed (Cloud Build builds the images). No Secret Manager entries are needed for Slices 1–2 (Telegram and Routes API secrets are Slice 7: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `ROUTES_API_KEY`).

```bash
export PROJECT_ID=<your-project-id>       # REGION defaults to asia-southeast1, TIME_SCALE to 10
bash infra/00_apis.sh                     # enable Run, Workflows, Firestore, Artifact Registry, Build, Secret Manager, Vertex AI, Trace, Logging, Monitoring, BigQuery
bash infra/10_firestore.sh                # Firestore Native (default) + sim in asia-southeast1; rules via firebase CLI
bash infra/20_iam.sh                      # cc-<service> accounts; workflows.invoker only for api + connectors; sim DB only for persona-sim
bash infra/30_images.sh                   # Artifact Registry repo + Cloud Build of 6 images (tag = git short SHA)
bash infra/40_deploy_services.sh          # Cloud Run: api public (min 1), others private; invoker bindings
bash infra/50_workflow.sh                 # deploy coverage-cascade under cc-workflow; run.invoker on api
bash infra/60_seed.sh                     # datagen --to-firestore + scenarios + travel config
# then open  <api-url>/test  and tap "Scenario: 6:02am sick call" (J2) and "Nobody replies" (J3)
```

`bash infra/deploy_all.sh` runs all seven in order. Every script is meant to be idempotent, but none has run.

## For the next agent
- **Branch:** `claude/slices-1-2`. Tags: `slice-1`, `slice-2-local`. Do not commit to `main` from here. Merge via a PR when the human approves.
- **Do not overwrite:** `policy/rules/*.yaml` (sources verified live on 2026-10-18), `docs/decisions/0005-rule-semantics.md` (the contract both engines implement), and `data/` plus `evals/datasets/` (regenerate only with `python -m datagen build --seed 42`; a test checks `data/` matches the generator byte for byte).
- **Keep the invariants:** `policy/validate.py` imports only the standard library and `yaml` (AST test); every hard rule change goes in the YAML, both engines and the fixtures together (property tests compare rule IDs and cost lines exactly); state changes only through `events.append_in_txn` and `TRANSITIONS`; nothing staff-facing without `_outbound` (approval check).
- **Frontend (`web/`):** untouched except the Step 1 move. The AI Studio template there is empty boilerplate. Read-only Firestore collections for the web app are listed in `infra/firestore.rules`.
- **Merge notes:** `main` holds only the two docs commits plus AI Studio's initial commit. This branch deletes `evals/cascade_sim.py` (it existed only inside this branch), renames the PDF, and moves the root React files to `web/`. If the frontend agent edits files on `main` at the old root paths, rebase their changes onto `web/`.
- **Next slices:** Slice 3 (lead view with Scenario buttons) can read `gaps`, `gaps/{id}/events` and `plans` directly. `plans/{id}.rejected_candidates[].rejected_rules[]` already carries the message, rule ID and source URL for the greyed-out cards.

---

## Step 1: Audit (2026-10-18)

### What I found

- `git log --oneline` (before this branch): `a80fdf5 feat: initialize project structure`, `ed7d023 Initial commit`. AI Studio committed everything in one commit. The two docs were untracked and are now committed on `main` as `3c5e56a`.
- **No Slice 2 code exists.** Every Slice 2 file (`services/*/app/main.py`, `Dockerfile`, `requirements.txt`, `workflows/coverage_cascade.yaml`, `policy/timing.py`, `cloudbuild.yaml`) is a 0-byte file. `evals/runners/` and `infra/` do not exist.
- **Correction (Step 2):** I first assumed the scenario `expect` blocks were hand-typed. That was wrong. Running `build_synthetic_dataset(seed=42)` reproduces `data/*.json` and all 100 scenario files byte for byte, so they are generator output. The generator's logic is the problem. `S-017` expects the manager `stf_001` to fill at S$0.00, and CoverCall shows S$0.00 overtime in all 60 golden scenarios, because staff outside Part 4 (including the manager) cost nothing in its model.

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
| `datagen/__init__.py` | rewrite | Its cost model makes staff outside Part 4 (including the manager) free, so `S-017` "fills" with the manager at S$0. Roster assigns staff round-robin, ignoring skills and rest days. `days_since_last_rest_day` is stored by hand and disagrees with the roster. 14 h turnaround is hard-coded for every candidate. |
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
| Hand-typed `expect` blocks in scenarios | **No** (corrected in Step 2: they reproduce from the generator). The generator's cost model is wrong, so they are still regenerated. |
| Missing `synthetic: true` | No. Records carry it. |
| A language model deciding legality or changing state | **No.** There is no model call anywhere. |

## Step 2: Runnable baseline (2026-10-18)

- Only Python 3.14 was installed. I installed `uv` (user site) and CPython 3.12.15, created `.venv` (Python 3.12), and installed every dependency from `pyproject.toml` plus the dev extras (`ortools 9.15.6755`).
- `pyproject.toml`: `requires-python = ">=3.12,<3.13"`, mypy `python_version = "3.12"`, added `types-PyYAML`. `pip install -e .` fails on setuptools flat-layout discovery, so dependencies are installed with `uv pip install -r pyproject.toml --extra dev` and code runs from the repo root (`pythonpath = ["."]`).

Baseline on the **unmodified AI Studio code**:

| Command | Result |
|---|---|
| `ruff check .` | `All checks passed!` |
| `mypy` | **Fails:** `Found 1 error in 1 file (errors prevented further checking)`. Six services each have a top-level package named `app`. |
| `python policy/lint_rules.py` | `OK (15 rules verified with complete sources and >=2 tests)` |
| `pytest` | **`1 failed, 38 passed`**. `test_datagen_builds_all_synthetic_records_and_scenarios`: `assert 17 == 18` (the full-timer count is off by one, because the `stf_010` pin overrides the 60/40 split). |
| `python -m evals.compare --set golden` | Exit 0. CoverCall S$0.00 median / S$0.00 total overtime, 0 violations; baseline S$151.05 / S$9,063.00, 80 violations. **Not credible:** CoverCall's S$0 comes from picking staff outside Part 4 at zero modelled cost, and time to fill uses invented constants (1.10 vs 3.50 min). |

## Step 3: Slice 1 (engine and evidence) — DONE, tag `slice-1`

Every AI Studio engine file was rewritten (see the audit table for why). What exists now:

- `policy/rules/*.yaml`: 15 specs. Sources re-verified live. `applies_when` is a real expression both engines evaluate. Company values are referenced as `company:<key>`, not copied.
- `docs/decisions/0005-rule-semantics.md`: the one prose definition of every fact and rule. Both engines implement it separately.
- `policy/validate.py`: stdlib + `yaml` only (AST test). Derives every fact from roster dicts. Missing data fails closed. Breach templates are shown only for breaches.
- `policy/compile_cpsat.py`: real CP-SAT model. Booleans per (person, option); full gap or a two-person split on a 30-minute grid; each hard rule is a named linear constraint; integer-cent objective; top-k cuts over sets of people; `num_search_workers = 1`, fixed seed. `solve` cross-checks legality **and cost** with the validator and raises `PlanDisagreement`.
- `policy/fixtures/`: 41 roster-level fixtures over a shared `_base.yaml`. Every rule has ≥ 2.
- `datagen/`: 33 staff, 497 shifts (19 Oct to 15 Nov), 66 ledgers, 33 `sim` personas (hidden timetables and exam weeks), placeholder travel, and 60 golden + 40 held-out scenarios with `expect` computed by the solver.
- `baseline/most_reliable_first.py`, `evals/cascade_sim.py`, `evals/compare.py`.

Exit check, run on 2026-10-18:

```
$ ruff check .                      -> All checks passed!
$ mypy                              -> Success: no issues found in 38 source files
$ python policy/lint_rules.py       -> policy/lint_rules.py: OK (15 rules verified with complete sources and >=2 tests)
$ pytest                            -> 71 passed in 14.90s
$ python -m evals.compare --set golden   (exit 0)
CoverCall vs most-reliable-first baseline: golden set, n=60 (all data is synthetic; costs in synthetic SGD)
Metric                         |      CoverCall |       Baseline
------------------------------------------------------------------
Gaps filled                    |          57/60 |          59/60
Median overtime cost per gap   |         S$0.00 |         S$0.00
Total overtime cost            |        S$77.10 |     S$3,434.68
Total incremental labour cost  |     S$1,907.10 |     S$6,322.68
Rule violations (hard rules)   |              0 |             19
Scenarios with a violation     |              0 |             18
Solver/validator disagreements |              0 |            n/a
------------------------------------------------------------------
CoverCall escalated: 3, held: 0; baseline unfilled: 1
Results differing from scenario expect blocks: 0
```

Held-out (`python -m evals.compare --set heldout`, exit 0): CoverCall 40/40 filled, total overtime S$37.76, total incremental S$1,291.76, 0 violations, 0 disagreements, 0 expect mismatches. Baseline: 40/40 filled, S$2,422.67 overtime, S$4,142.67 total, 15 violations in 14 scenarios.

These Step 3 numbers come from the untimed Slice 1 cascade at tag `slice-1`. The final numbers from the timed state machine (Slice 2) are in the final report at the top, and they replace these.

How to read these numbers honestly:
- CoverCall escalates 3 golden gaps. S-002 is "nobody replies" by design. In **S-013 and S-038** the baseline "fills", but the person it picks cannot arrive with the 10-minute buffer (S-013), or the pick breaks the 11-hour rest rule (S-038). The baseline ignores travel and reply time.
- Medians are S$0.00 for both arms because most gaps can be covered by someone with spare contract hours. The difference is in the totals and violations.
- Staff outside Part 4 cost S$0 (no statutory overtime). Their contractual pay is not modelled (decision 0008).
- Travel times are placeholders, not Routes API data.

### Work list from the audit (status at the end of the run: all 13 done)

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

## Step 4: Slice 2 (cascade foundation, local) — DONE, tag `slice-2-local`

What was built (all new; the AI Studio files were empty):
- `services/api/app/events.py`: the `TRANSITIONS` table (the §5.1 table, `gap.cancelled` from every non-terminal state and HELD); one-transaction append with version guard; SHA-256 chain exactly as KICKSTART §4.1 specifies; `verify_chain`; PII redaction before every write (`services/common/pii.py`); message dedup.
- `services/common/store.py`: `Store` interface, `MemoryStore` (used), `FirestoreStore` (written, untested).
- `policy/timing.py`: §5.2 as pure functions, plus `t_esc` locked at approval and windows clamped to it (decision 0009).
- `services/api/app/{core,main,deps,page}.py`: public `POST /gaps`, `/approvals`, `/replies`, `/fallbacks`, `/gaps/{id}/cancel`, `GET /test` (text-only page with the "All data is synthetic" footer and a visible time-compression banner), and the internal routes the workflow calls (decision 0013). The live-token route returns 501 (Slice 4).
- `workflows/coverage_cascade.yaml`: the §5 state machine, with fan-out in a `parallel` loop (decision 0011).
- `services/guard` (`stub-v0`, fails closed), `services/agent` (`stub-v0` parser, explanation check, offer draft; refuses to start without an explicit implementation), `services/persona_sim` (outbox delivery, decision 0012), `services/solver`, `services/connectors` (refuses until Slice 7).
- `evals/runners/local_cascade.py`: the local driver. `evals/compare.py` now runs the timed state machine and reports `time_to_fill_min`. Scenario labels are recomputed by the same driver. The untimed Slice 1 simulator (`evals/cascade_sim.py`) was removed, so there is one cascade semantics.
- `infra/`: `env.sh`, `00_apis.sh` to `60_seed.sh`, `deploy_all.sh`, `build-images.yaml`, Firestore rules for `(default)` (read-only, demo collections only) and `sim` (no client access), `seed_scenarios.py`. Dockerfiles and requirements for all six services. `cloudbuild.yaml` gate for steps 1–5, the local cascade and a secret scan.

Problems found and fixed during Slice 2 (real defects, found by running):
1. `escalation_late = 6` across the golden set. `t_esc` moved after declines. Fixed by locking it at approval (decision 0009).
2. `pii_leak` false positives: the phone and card patterns matched digit runs inside SHA-256 hashes. Fixed with word-boundary patterns; tests pin both sides.
3. The stub parser read §8.3's own example "wah 7am ah... 8 can?" as an accept, and "sorry can't make it" as unclear. Fixed; the §8.3 examples are now tests.
4. `evals.compare` exited 0 despite a non-zero P0 counter (an edit had not applied). Fixed; it now fails on any P0 counter or chain failure.

Tests added: `tests/test_events.py` (every table transition accepted; **every** (state, event) pair outside the table rejected; clean, tampered, deleted, reordered and truncated chains; redaction; dedup), `tests/test_timing.py`, `tests/test_cascade.py` (J2, J3, no offer without approval, voice approval needs a clear yes, duplicate reply dropped, late yes gets a courtesy reply, guard failure → HELD, injection quarantined and never in the event log, lead cancel through the workflow, material-change rule), `tests/test_workflow.py` (YAML vs table, retry and OIDC policy, local driver mirrors every step), `tests/test_services.py`.

Not covered end to end: the re-approval path after a material counter-offer (`reply.counter` → SOLVED). The rule is unit-tested, and the YAML and driver contain the path, but no scenario exercises it.
