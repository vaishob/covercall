web/ owner: Claude Code (since 2026-10-18T17:51:11+08:00)

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
- **Gemini model IDs: pinned 2026-10-18** (`chore/pin-models`, decisions 0019–0021) for voice, agent, persona_sim and eval_judge; `guard` stays TODO-VERIFY until Slice 5. Still open: ephemeral tokens are Preview; availability in `asia-southeast1` is unverified (model calls use `global`).
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
**Deployed 2026-10-18 to `covercall-demo-2026`** (see "Deployment" at the end of this file): web https://covercall-demo-2026.web.app, api https://covercall-api-584069229211.asia-southeast1.run.app, workflow `coverage-cascade`. Next: decide how production should handle scenario time (it runs on the real clock; see Deployment, still open).

---

## For the human: deploy steps (run 2026-10-18 against covercall-demo-2026; approve each)

Prerequisites: a Google Cloud project with billing; `gcloud` authenticated as an owner (`gcloud auth login`, `gcloud auth application-default login`); the Firebase CLI for security rules; Python 3.12 with the repo's venv (for seeding); Docker is not needed (Cloud Build builds the images).

**Required Secret Manager entry: `GEMINI_API_KEY`** (a Gemini Developer API key; only `api` reads it, to mint Live API ephemeral tokens, decision 0019). Create it by hand before step 3, reading the value from stdin so it never lands in the repo, a file or shell history. `infra/25_secrets.sh` stops the deploy if it is missing and grants `api` read access:
```bash
gcloud secrets create GEMINI_API_KEY --project "$PROJECT_ID" --replication-policy=automatic
read -rs KEY && printf '%s' "$KEY" | gcloud secrets versions add GEMINI_API_KEY --project "$PROJECT_ID" --data-file=- ; unset KEY
```
Telegram and Routes API secrets are Slice 7: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `ROUTES_API_KEY`.

```bash
export PROJECT_ID=<your-project-id>       # REGION defaults to asia-southeast1, TIME_SCALE to 10
bash infra/00_apis.sh                     # enable Run, Workflows, Firestore, Artifact Registry, Build, Secret Manager, Vertex AI, Gemini API, Trace, Logging, Monitoring, BigQuery
bash infra/10_firestore.sh                # Firestore Native (default) + covercall-sim in asia-southeast1; rules via firebase CLI
bash infra/20_iam.sh                      # cc-<service> accounts; workflows.invoker only for api + connectors; sim DB only for persona-sim
bash infra/25_secrets.sh                  # checks GEMINI_API_KEY exists; secretAccessor for api only
bash infra/30_images.sh                   # Artifact Registry repo + Cloud Build of 6 images (tag = git short SHA)
bash infra/40_deploy_services.sh          # Cloud Run: api public (min 1), others private; invoker bindings
bash infra/50_workflow.sh                 # deploy coverage-cascade under cc-workflow; run.invoker on api
PYTHON=.venv/Scripts/python.exe bash infra/60_seed.sh   # datagen --to-firestore + scenarios (PYTHON: the repo venv)
bash infra/70_hosting.sh                  # build web against the api URL; firebase deploy --only hosting
# smoke test: cd web && E2E_BASE_URL=https://$PROJECT_ID.web.app npx playwright test -c playwright.prod.config.ts
```

`bash infra/deploy_all.sh` runs all nine in order. Each was run once, one at a time, on 2026-10-18; `30_images.sh` and `40_deploy_services.sh` were re-run after fixes (idempotent in practice).

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

---

## Frontend import (branch `integrate/web`, 2026-10-18)

- **Source:** Argon (Google AI Studio) export of branch `gemini/slice-4-web` at commit `c2b071e`, from `../covercall-web-export.zip.zip` (the file has a double `.zip` extension). The export also holds stale backend files and `.aistudio/`. Only `web/` was extracted (to a temp folder outside the repo) and copied. Before the import, `main` was reset to `a80fdf5`: it had received an earlier copy of this frontend plus 16 `.aistudio/` files (2 copies of the design-doc PDF, 14 UI screenshots; scanned, no secrets, nothing from outside the project). The old tip is kept as the **local-only** tag `backup/main-before-reset` (`7c491b5`).
- **Files:** 32, all under `web/`. Nothing in the expected list is missing and there are no extras. `src/components/` has **12** files (the brief said 13, but its own total of 32 only works with 12): ApprovalCard, CandidateList, CaptionsPanel, CascadeTimeline, EvidenceModalViews, GapCard, MockDataBadge, MockModeBanner, RosterMiniGrid, RuleWarningCard, ScenarioLauncher, VoiceStateBar. No `node_modules/` or `dist/`.
- **Commits:** `bb61541` removes the AI Studio template, `f42c748` imports `web/` (only `web/` paths changed), and `dae875b` adds `.aistudio/` to the root `.gitignore`. `web/node_modules/` and `web/dist/` are ignored by `web/.gitignore` and by the root `node_modules/` and `dist/` patterns; neither is staged.
- **Secrets scan** (same patterns as the Step 1 audit) over `web/`: **clean**. `web/.env.example` has only empty placeholders (`VITE_API_BASE_URL`, `VITE_FIREBASE_*`, `VITE_FIRESTORE_DATABASE_ID`, `VITE_GEMINI_LIVE_MODEL_ID`).
- **Frontend checks** (Node 24.21.0, npm 11.19.0):
  - `npm ci`: OK without `--legacy-peer-deps`. npm held back `esbuild@0.25.12`'s postinstall script (not approved); test and build passed anyway.
  - `npm test`: `tests 15, pass 15, fail 0`.
  - `npm run build` (`tsc --noEmit && vite build`): OK, built in 1.54 s. One warning: `dist/assets/index-*.js` is 537.15 kB (gzip 164.76 kB), above Vite's 500 kB advisory.
- **Backend unaffected:** `ruff check .` All checks passed; `mypy` no issues in 54 files; `lint_rules` OK (15 rules); `pytest` 149 passed; `evals.runners.local_cascade` J2 PASS, J3 PASS, exit 0.
- **Frontend handoff:** see `web/HANDOFF-WEB.md` (contract the UI expects in §3, remaining mocks in §5, known gaps in §8).

## Frontend ↔ backend contract gaps (documented only; nothing fixed)

Compared `web/src/data/{apiClient,types,dataSource}.ts` (and `voiceProvider.ts`, `mocks/state.ts` where they set contract values) with `services/api/app/main.py` and `core.py`, the documents the backend writes, and `infra/firestore.rules`. The UI currently runs in mock mode, so none of these break it today. All of them break it once `VITE_API_BASE_URL` is set.

**Transport**
1. **No CORS on `api`.** A browser on Firebase Hosting calling the Cloud Run `api` cross-origin will be blocked; there is no `CORSMiddleware`.
2. **`FirestoreDataSource` does not use Firestore.** It sends HTTP `fetch` calls to `api` (the Firebase SDK is not installed). §11.1 says the web app reads Firestore directly through read-only listeners. On API errors it quietly falls back to mock scenario data.

**Endpoints: the UI calls routes the backend does not have**

| UI call | Backend has | Gap |
|---|---|---|
| `GET /status` → `{status, guard_impl, live_model_id, mock_mode}` | only `GET /healthz` → `{status}` | missing route |
| `POST /voice/token` → `{ephemeral_token, expires_at, model_id, api_version: "v1alpha"}` | `POST /live/token` → HTTP 501 | path differs; response shape undefined (Slice 4 stub) |
| `POST /gaps/{id}/fallback` | `POST /fallbacks` with `{gap_id, option}` | path differs |
| `GET /scenarios/{key}` (a composite "scenario bundle") | none; scenarios start via `POST /gaps {scenario_id}` | missing route; no backend view assembles the bundle |
| `GET /quarantine?gap_id=` | none | missing route |
| `GET /evals` (BigQuery read model) | none; compare results exist only as CLI and JSON output | missing route (Slice 6) |
| `GET /gaps/{id}/events` expects `{events: [...], chain_verified}` | returns a bare list; verification is a separate `GET /gaps/{id}/verify` → `{ok, events, errors}` | shape differs |

**Request payloads**

3. `POST /gaps`: the UI (voice `report_absence`) sends `{outlet, shift_start, station, staff_name?}`. The backend needs `scenario_id`, or else `{outlet, station, start, end, absent_staff_id}`, so the UI request returns **422** (no `end`, a name instead of `absent_staff_id`). The response is `{gap_id, workflow_execution_id}` with no `mock` and no `gap`.
4. `POST /approvals`: the UI sends `approval_nonce` and `decision: "approved" | "rejected"`. The backend reads `nonce` (so it returns **409**, "no pending approval with that nonce"), and accepts only `decision == "approve"`. **"approved" would be recorded as a reject.** The UI also sends `plan_id`, which the backend ignores (it takes the plan from the pending approval). The backend's response is the full approval document (`approval_id`, `decision: approve|reject`, …).
5. `POST /gaps/{id}/cancel`: the UI expects `{gap_id, state: "CANCELLED"}`. The backend returns `{status: "cancel requested", waits_signalled}`, because the cancel goes through the workflow, so the state is not CANCELLED yet.
6. Fallback option IDs: the UI uses `borrow_cross_outlet, reduced_service, lead_covers, agency_temp`. The backend uses `borrow, reduced_service, lead_covers, agency, unfilled` (listed in `gaps/{id}.fallbacks`).

**Field names and types (`types.ts` vs the documents the backend writes)**

7. IDs: the UI uses `id` everywhere. The backend uses `gap_id`, `plan_id`, `offer_id`, `approval_id`, `staff_id`, `outlet_id`, `shift_id` and `ledger_id`. Quarantine documents have no ID field.
8. **`GapDoc.must_fill_by` does not exist.** The backend stores `t_esc` (the latest computed) and `t_esc_locked` (locked at approval, decision 0009); must-fill-by is per candidate and is not stored. The UI's must-fill-by countdown has no backing field. Other gap fields the UI does not model: `pending_approval {nonce, readback_text, plan_id}`, which is where the nonce and read-back actually live; `fallbacks`; `summary`; `excluded`; `windows`; `accepted`; `approval_id`; `approved_plan_id`; `current_plan_id`; `reported_at`; `filled_at`; `time_scale`.
9. **Plan shape.** Backend `plans/{id}.candidates[]` are ranked *plans*: `{rank, staff_ids[], segments[{staff_id, display_name, home_outlet, start, end, breaks, travel_min, arrival, cost_breakdown, fairness_penalty_units, rules_checked}], cost_breakdown, overtime_cost_cents, travel_min, arrival, is_cross_outlet_borrow, objective, solver_status}`. The UI expects one `staff_id` per candidate and segments of only `{start, end}`. A two-person split (as in J2) has no UI representation.
10. **Cost breakdown.** The backend uses integer **cents**: `{base_cents, overtime_cents, rest_day_cents, total_cents}` plus `overtime_cost_cents`. The UI expects SGD floats `{incremental_cost_sgd, saves_vs_overtime_sgd, basis?}`. The backend computes no per-candidate "saves vs overtime"; only `gaps/{id}.cost_saved_sgd`, at commit, against the naive first pick (decision 0014).
11. **`rules_checked`.** Backend: objects `{rule_id, status, kind, message, source_url}`. UI: `string[]`.
12. **`rejected_rules` location.** Backend: at plan level, `plans/{id}.rejected_candidates[] = {staff_id, display_name, rejected_rules[{rule_id, message, source_url, params}]}`. UI: inside each `candidates[]` entry.
13. **`rejected_rules` severity and source.** The UI requires `severity: "P0"|"P1"|"P2"`, `source_publisher` and `source_section`. The backend has no severity on rules (P0/P1/P2 are eval-metric severities, §10.1; rules have `kind: hard|cost|soft|applicability_gate|data_gate`) and does not copy the publisher or section into the plan (they are in `policy/rules/*.yaml`).
14. `ApprovalDoc.decision`: UI `approved|rejected|pending`, backend `approve|reject`. The backend also stores `plan_id` and `exclude_staff_ids`.
15. `OfferDoc.status`: UI `sent|accepted|declined|counter|timeout|withdrawn`, backend `open|accepted|decline|countered|timeout|withdrawn|late|flagged`. The backend offer also has `start`, `end`, `plan_id`, `rank`, `approval_id`, `fanout_group`, `attempt`, and a server-only `callback_url`.
16. `ShiftDoc.breaks`: UI `{start, end}`, backend `{start, duration_min}`. UI status `covered` does not exist; the backend writes a new cover shift (`source: "cover:<gapId>"`) and marks the original `absent`.
17. `LedgerDoc.month`: UI comment says `YYYYMM`, backend writes `"2026-11"` (the ID suffix is `YYYYMM`).
18. `GapEventDoc.from_state` is `string` in the UI, but is `null` for `gap.reported`. The UI reads `payload.summary`; the backend payloads have no `summary` key. Mock events use actors such as `system:guard_stub` and `system:mock_state`, which the backend's append guard rejects (allowed: `lead | system | staff:<id> | model:<id>`).
19. Mock-only values that differ from the generated data: outlet names ("Bugis Espresso Bar", closing 22:00) vs `name: "Bugis"` closing 21:00; full-timer `weekly_contract_hours` 44 vs 40 (decision 0007).

**Read paths and `infra/firestore.rules`**

20. Rules let clients read only `gaps`, `gaps/{id}/events`, `plans`, `outlets` and `shifts`. The UI also reads **`staff`** (`getStaff`, currently always mock) and **`quarantine`** (`subscribeQuarantine`). Both are denied to clients under the current rules, so either the rules or the UI must change.
21. `gaps/{id}` is client-readable and holds `pending_approval.nonce`. The UI needs the nonce for `approve`, so this works, but it is a deliberate exposure to note in the security review.
22. The UI has no read path for **offers** (the cascade timeline is mock-only). `offers` is server-only by design (it holds callback URLs), so the timeline needs a redacted view (events already carry offer outcomes) or a new route.

**Voice**

23. Token route mismatch (`/voice/token` vs `/live/token`). The backend route returns 501, so the UI falls back to text, which is correct for today. The voice model ID is `TODO-VERIFY` in `config/models.yaml` and `VITE_GEMINI_LIVE_MODEL_ID` is empty, so neither side has a pinned Live model.

---

## Contract alignment (branch `feat/web-contract`, 2026-10-18)

The frontend now talks to the real backend. Decisions: 0015 (reads only through `api`, client-safe
projections, Firestore deny-all), 0016 (backend shapes are canonical; one mapping layer; contract
fixtures), 0017 (recorded replay replaces invented mock data), 0018 (local dev server).

### Checks run on the final commit

```
$ ruff check .                              All checks passed!
$ mypy                                      Success: no issues found in 59 source files
$ python policy/lint_rules.py               OK (15 rules verified with complete sources and >=2 tests)
$ pytest                                    164 passed
$ python -m evals.runners.local_cascade     J2 (S-017) FILLED, PASS; J3 (S-002) RESOLVED (borrow), PASS; exit 0
$ (web) npm test                            tests 27, pass 27, fail 0
$ (web) npm run build                       built in 1.63s (warning: the two lazily loaded replay chunks are >500 kB raw, 25-35 kB gzip)
$ (web) npx playwright test                 2 passed: S-017 to FILLED by tap; Nobody replies to ESCALATED then RESOLVED
```

The Playwright run starts `python -m evals.runners.dev_server` (memory store, `ALLOWED_ORIGINS=http://localhost:3000`)
and the Vite dev server with `VITE_API_BASE_URL=http://127.0.0.1:8080`. It asserts: candidates, the Priya
`SG-EA4-OT-CAP-72` warning with its MOM source link, the approval read-back and the timeline (decline,
counter-offer, no reply) appear; no replay badge or banner; no console errors; axe-core reports no
serious or critical issue on `/`, `/trace/:gapId` and `/evals`. (axe found one real issue on the first
run, a keyboard-unreachable scrolling region in the roster strip; it was fixed.)

### Contract gaps: outcome of each item

| Gap | Outcome |
|---|---|
| 1. No CORS on `api` | **Fixed.** `ALLOWED_ORIGINS` (default `http://localhost:3000`); a wildcard is refused at start-up. Tested. |
| 2. `FirestoreDataSource` used HTTP and fell back to mock data silently | **Fixed by decision 0015.** No Firestore SDK path; one `LiveSource` over the `api` routes; errors are shown as errors. |
| Table: `GET /status` missing | **Fixed.** Returns `guard_impl`, `parser_impl`, model IDs from `config/models.yaml` as-is (pinned since `chore/pin-models`; `guard` still `TODO-VERIFY`), time scale. |
| Table: `/voice/token` vs `/live/token` | **Fixed** (UI calls `POST /live/token`). **Voice itself stays open:** the route answers 501 with an explanation; the UI falls back hands-free → push-to-talk → text. |
| Table: `/gaps/{id}/fallback` vs `/fallbacks` | **Fixed.** UI calls `POST /fallbacks`. |
| Table: `GET /scenarios/{key}` bundle | **Fixed differently.** `GET /scenarios` lists the playable scenarios (S-017, S-002) from the data; `POST /gaps {scenario_id}` starts one; `GET /gaps/{id}` is the single view model. |
| Table: `GET /quarantine?gap_id=` | **Fixed** as `GET /gaps/{id}/quarantine` (redacted text only). |
| Table: `GET /evals` | **Fixed:** returns `no_eval_run` and no numbers. **Open:** real results need BigQuery (Slice 6). |
| Table: events shape | **Fixed.** `GET /gaps/{id}/events` returns `{events, chain}` with the server's `verify_chain` result. |
| 3. `POST /gaps` from voice `report_absence` | **Fixed.** The server resolves the staff name and the end time from the roster; unknown, ambiguous or unrostered → a clarifying question, never a guess, and no gap is created. |
| 4. `/approvals` payload | **Fixed.** UI sends `nonce` and `approve`/`reject`. |
| 5. Cancel response | **Fixed in the UI.** Cancel shows "cancel requested"; polling then shows CANCELLED once the workflow appends `gap.cancelled`. |
| 6. Fallback option IDs | **Fixed.** UI uses the backend's `borrow, reduced_service, lead_covers, agency, unfilled`, labelled in the mapping layer. |
| 7. `id` vs `gap_id`/`plan_id`/… | **Fixed** in `viewModel.ts`. |
| 8. `must_fill_by` | **Fixed.** The countdown target is `t_esc_locked`; seconds remaining come from the server (`clock.seconds_to_escalation`). `pending_approval` is gone from the gap document. |
| 9. Plan shape, two-person splits | **Fixed.** Every segment shows its own person, times, breaks, travel and arrival. |
| 10. Cents vs SGD; per-candidate saving | **Fixed.** Cents end to end; the backend adds `saves_vs_naive_cents` per plan (decision 0014 comparator), shown as "less/more overtime than the usual first pick (Priya)", with a synthetic-wages note. |
| 11. `rules_checked` objects | **Fixed.** |
| 12. `rejected_rules` location | **Fixed.** Mapping reads `plan.rejected`. |
| 13. Severity and source | **Fixed.** UI shows the rule **kind** (Hard rule, Data gate), not P0/P1/P2; publisher and section come from the rule spec through the projection. SFA and part-time rules link to their own pages (tested). |
| 14. Approval decision values | **Fixed** (`approve`/`reject`). |
| 15. Offer status values | **Fixed.** Backend statuses with display labels. |
| 16. Breaks; `covered` shift status | **Fixed.** Breaks are start plus duration. The UI no longer reads shifts, so `covered` is moot. |
| 17. Ledger `month` | **Obsolete.** The UI no longer reads ledgers. |
| 18. Event `from_state` null, `payload.summary`, mock actors | **Fixed.** Trace view maps null to "(none)" and summarises scalar payload fields; mock events are gone. |
| 19. Mock-only values (outlet names, 44 h) | **Fixed.** Mock data removed; replay shows recorded real responses (decision 0017). |
| 20. Client reads of `staff`, `quarantine` | **Fixed by decision 0015.** No client Firestore reads; names come in projections; quarantine has its own route. |
| 21. Nonce in a readable document | **Fixed.** Server-only `server/{gapId}`; only `GET /gaps/{id}/approval` returns it, only while pending. Leak test over every read route. |
| 22. No read path for offers | **Fixed.** Offers are in the gap view, without callback URLs. |
| 23. Voice token and model | Route **fixed**; voice **open** (Slice 4). Model pinned later (`gemini-3.8-live`, `v1beta`; decision 0019), and the web client now expects `v1beta` tokens. |

### Still open
- Voice (Slice 4), BigQuery evals (Slice 6), the guard model and an adversarial scenario (Slice 5; the J4 button is omitted, see OPEN_ITEMS).
- Typed text: with an approval pending, it is sent as a voice-channel transcript (the server decides yes or no). Typed absence reports are not parsed in the browser; they need the voice tools.
- Nothing is deployed. On Cloud Run, set `ALLOWED_ORIGINS` to the Firebase Hosting origin, and point the web build's `VITE_API_BASE_URL` at the `api` URL.
- The dev server keeps one shared roster per session (decision 0018).

### How to run locally
```
python -m evals.runners.dev_server --port 8080                     # repo root; ALLOWED_ORIGINS defaults to http://localhost:3000
cd web && VITE_API_BASE_URL=http://127.0.0.1:8080 npm run dev      # then open http://localhost:3000
cd web && npx playwright test                                      # starts both servers itself
python -m evals.runners.capture_fixtures                           # after an intended backend shape change
```

---

## Deployment (branch `chore/deploy-fixes`, 2026-10-18)

Project `covercall-demo-2026` (number 584069229211), region `asia-southeast1`. Every step was run
one at a time with the author's approval. `GEMINI_API_KEY` was created by the author in their own
terminal; its value was never seen, printed or stored by the agent.

### What is live
| Thing | Where |
|---|---|
| Web app (Firebase Hosting) | https://covercall-demo-2026.web.app |
| api (public) | https://covercall-api-584069229211.asia-southeast1.run.app (`/status`, `/test`) |
| Private services | `covercall-{solver,guard,agent,persona-sim,connectors}-584069229211.asia-southeast1.run.app` (403 without an ID token) |
| Workflow | `coverage-cascade` (revision `000001-3e7`, service account `cc-workflow`) |
| Firestore | `(default)` and `covercall-sim`, Native, deny-all client rules |
| Images | `asia-southeast1-docker.pkg.dev/covercall-demo-2026/covercall/*:a195d43` |
| Secret | `GEMINI_API_KEY` v1, readable only by `cc-api` |

`ALLOWED_ORIGINS` on api is `https://covercall-demo-2026.web.app,https://covercall-demo-2026.firebaseapp.com`
(checked: CORS header present for the Hosting origin, absent for others). `/status` reports
`environment: cloud`, the pinned models and `time_scale: 10`.

### Production smoke test (tap only, Playwright against the Hosting URL)
| Journey | Result | Evidence |
|---|---|---|
| S-017 to FILLED | **PASS** (2.2 min, after the fix below) | `gap-0004`: "Filled: Fiona 07:00-09:00 + Lucas 09:00-15:00", `cost_saved_cents` 15105 (same as the local run). Offers: decline, counter, timeout, accept. Execution `0e0807b3…` SUCCEEDED with argument `gap_id: gap-0004`. `verify_chain` OK, 9 events. axe: no serious or critical issues on `/`, `/trace/gap-0004`, `/evals`. No console errors. |
| Nobody replies to ESCALATED, then RESOLVED | **PASS** (12.8 min) | `gap-0003`: 12 offer timeouts, `escalation.due`, `fallback.chosen` (borrow). Execution `c8a685e0…` SUCCEEDED with argument `gap_id: gap-0003`. `verify_chain` OK, 18 events. No console errors. |

No ERROR log entries and no 5xx responses on any service after the final redeploy.

### What failed on the way, and the fixes (all in this branch)
1. **Firestore database ID `sim` rejected** (IDs need 4–63 characters) → renamed `covercall-sim` (decision 0022, `tests/test_infra.py`).
2. **`60_seed.sh` used the system Python** → `PYTHON=` override.
3. **`40_deploy_services.sh` could not have worked:** gcloud refuses `--set-env-vars` with `--update-env-vars`, and api crashes at start-up without `GUARD_URL`/`SOLVER_URL`/`PERSONA_SIM_URL` → each service deploys once, using deterministic Cloud Run URLs.
4. **api image missing `services/persona_sim`** (ModuleNotFoundError at start-up) → added; `tests/test_images.py` checks every image against its service's imports.
5. **S-017 failed in production:** `/internal/accept` returned 500, `ReadAfterWriteError` (Firestore needs every read in a transaction before the first write; `accept` and `commit` broke this). Fixed; `MemoryStore` now enforces the rule. The failed execution left `gap-0001` stranded in OUTREACH (see open items).
6. A service-account creation quota (per minute) stopped `20_iam.sh` once; re-running after 60 s finished it.
7. `/healthz` returns Google's 404 on Cloud Run (the path is reserved by the platform); use `/status`.

### Still open
- **Real clock in production:** scenario gaps are dated 3–4 Nov 2026, so deadlines are ~2 weeks away. Offers go one at a time (no fan-out), the countdown shows ~15 days, and "Nobody replies" takes ~13 minutes. Fan-out (a `parallel` loop with several branches) has not run in production yet. Needs a product decision (OPEN_ITEMS).
- **A failed execution strands its gap** (no top-level error handler in the YAML; no alert on FAILED executions).
- **Leftover gaps:** `gap-0001` (S-017, OUTREACH, execution FAILED, before the fix) and `gap-0002` (S-017, SOLVED, waiting for an approval; created from another browser session at 14:28Z, not by the smoke test; its execution times out after 12 h). Left as they are.
- The roster in `(default)` now holds `gap-0004`'s cover shifts; a second S-017 run sees them. Reseed (`60_seed.sh`) for a clean demo.
- Cost: api, guard, agent and persona-sim keep one warm instance each (persona-sim with CPU always on).
- Voice (Slice 4), BigQuery evals (Slice 6), the guard model (Slice 5), and the IAM deny side of the database conditions remain as before.

---

## Final engineering (branch `feat/final`, 2026-10-18/19). Frozen after this.

### What is live (production frozen at 00:05 SGT, 2026-10-19)
| Thing | Value |
|---|---|
| Images | tag `a6507f5` on all six services (revisions `*-00004-*`); previous working revisions `*-00003-*` (tag `a195d43`) kept for rollback |
| Time scale | `TIME_SCALE=60` on api and persona-sim; `/status` reports `time_scale: 60` (the UI label reads it) |
| Reply parser | `gemini-3.8-flash` on the Enterprise Agent Platform, `global` (`PARSER_IMPL=gemini`, decision 0023). Fails closed to `unclear`. The guard (`stub-v0`) runs first |
| Persona text | `gemini-3.8-flash`, temperature 0.8, seeded intent kept; template fallback when the text does not parse back to the intent (`PERSONA_TEXT_IMPL=gemini`) |
| Scenario gaps | commit to `overlays/{gapId}`; the seeded roster is never changed (decision 0023). Production reseeded at ~23:40 SGT |
| Web | https://covercall-demo-2026.web.app (`/about` labels each implementation from `/status`) |
| IAM change | `cc-api` has `roles/aiplatform.user` (parse runs in api) |

### Production runs after the redeploy (tap only, Playwright against Hosting)
| Run | Elapsed | Outcome | verify_chain | Execution | Gemini evidence |
|---|---|---|---|---|---|
| S-017 #1 `gap-0005` | 1.1 min | FILLED: Fiona 07:00-09:00 + Lucas 09:00-15:00, saved 15105 cents | OK, 9 events | `1cede986-21b6-4d26-a298-04031b4d13d0` | events: `parser_impl gemini-3.8-flash`, `prompt_sha256 002a6891…`; `text_impl gemini-3.8-flash`, `text_prompt_sha256 bd95d271…` (one reply fell back to `stub-v0` text) |
| S-017 #2 `gap-0006` | 1.1 min | identical to #1 (same plan, same saving, same offers) | OK, 9 events | `ab592ab3-b4a8-46bb-97c8-c19d5a684cc8` | same as #1 |
| Nobody replies `gap-0007` | 2.6 min | ESCALATED then RESOLVED (borrow) | OK, 18 events | `1d27d76a-725a-41f9-b6f2-6574a660926e` | no replies, so no parse (by design) |

Outcomes match the local cascade (J2 FILLED with the same plan and saving; J3 RESOLVED). Local
checks on the final commit: ruff, mypy, lint_rules, pytest 185 passed, local_cascade exit 0,
npm test 28/28, build, local Playwright 2/2. One live Gemini call was also made locally: "wah 7am
ah... only after 9 can, got lecture" → counter 09:00–15:00, reason school, confidence 0.95, 4.7 s.

### Clean-up (item 4)
- `gap-0002`: **CANCELLED** through `POST /gaps/gap-0002/cancel` (1 wait signalled; the workflow appended `gap.cancelled`).
- `gap-0001`: **not cancelled.** `POST /gaps/gap-0001/cancel` returns 500: its execution already FAILED, so its open offer's callback no longer exists. Left in OUTREACH; not edited by hand.

### Still open
- Production still runs on the real clock (scenario dates 3–4 Nov): offers go one at a time and the countdown shows ~15 days. `TIME_SCALE=60` makes the waits short; it does not change the dates.
- A failed execution strands its gap (`gap-0001`); the cancel route cannot reach it. Needs a top-level error handler in the YAML and a cancel path that works without a live execution.
- Persona text: when Gemini's wording does not parse back to the seeded intent, the template is used (seen once per S-017 run).
- Voice (Slice 4), BigQuery evals (Slice 6), the guard model (Slice 5).

---

## Voice live (branch `feat/voice`, promoted 2026-10-19 ~00:55 SGT). Frozen after this.

### What is live
| Thing | Value |
|---|---|
| api | revision `covercall-api-00006-bip` (image `api:voice-b9fc16d`), 100% of traffic. `VOICE_ENABLED=1`, `DEMO_ISOLATION=1`, `ALLOWED_ORIGINS` = the two production Hosting origins |
| Other services | unchanged: `*-00004-*` (tag `a6507f5`) |
| Voice | `POST /live/token`: single-use `v1beta` ephemeral tokens for `gemini-3.8-live` (1 min to start, 30 min session), the model, audio, both transcriptions, session resumption, system instruction and five tools locked server-side (global lock). Rate limit 5 per IP and 60 overall per 10 minutes (429). The key is never logged or returned. `/status` reports `voice: live` |
| Web | https://covercall-demo-2026.web.app: hands-free, push-to-talk and text, with a hint under the voice controls; `/about` reads voice and model status from `/status`. `@google/genai` 2.27.0 |
| Demo isolation | lead-reported gaps (voice, text) commit to their own overlay, so the same absence always gets the same plan (decision 0024) |
| Data | production reseeded at ~01:03 SGT |

### Verification after PROMOTE (all against the production URLs)
| Check | Result |
|---|---|
| Author's voice test on the preview | passed (reported by the author) |
| S-017 by tap | FILLED in 1.9 min (`gap-0011`, but see the finding below); after the reseed FILLED in 1.3 min (`gap-0013`): Fiona 07:00-09:00 + Lucas 09:00-15:00, saved 15105 cents, `verify_chain` OK (9 events), execution `c592b95a-fa9c-4b9e-ac67-56e174f26632` |
| Nobody replies by tap | ESCALATED then RESOLVED (borrow) in 2.8 min (`gap-0012`), `verify_chain` OK (18 events), execution `b18202c3-4522-4a00-9e27-ffff22a9248c` |
| Fake-mic voice check | Live session opened from a production token (`gemini-3.8-live`, v1beta); text mode works |
| Console errors | none in any run |

Local checks on `b9fc16d`: ruff, mypy, lint_rules, pytest 190 passed, local_cascade exit 0, npm test 34/34,
build, local Playwright 2/2.

### Finding: Gemini parsing makes S-017 less repeatable
In `gap-0011`, Lucas's seeded counter-offer was written by the template (Gemini's wording did not
parse back to the intent), and the Gemini parser read that template text as `unclear`. The server
fails closed (`unclear` is a decline, never an accept), so the plan moved on and Shreya filled the
whole shift: legal, FILLED, recorded honestly, but not the usual Fiona + Lucas split. The next run
(`gap-0013`) gave the usual split. This predates voice (the parser has been on since `feat/final`).

### Rollback (exact commands)
```bash
# api: back to the pre-voice revision
gcloud run services update-traffic covercall-api --project covercall-demo-2026 --region asia-southeast1 \
  --to-revisions covercall-api-00004-mlt=100
# Hosting: back to the pre-voice live release (saved as channel "prevlive" before the deploy)
firebase hosting:clone covercall-demo-2026:prevlive covercall-demo-2026:live --project covercall-demo-2026
```
The preview channel `voice` (https://covercall-demo-2026--voice-m6a66s8s.web.app, expires 26 Oct) and
the tagged revisions `voice` (`00005-bux`) and `live-voice` (`00006-bip`) remain; they carry no traffic of their own.

### Still open
- Gemini parser and persona-text variation can change which legal plan fills (above).
- Production still runs on the real clock (dates 3–4 Nov); voice reports must name the date.
- `gap-0001` stays stranded (failed execution, cancel route cannot reach it).
- Ephemeral tokens are a Preview feature; rate limits are per instance (in memory).

---

## Voice fix (branch `fix/voice-ratelimit`, promoted 2026-10-20 ~22:50 SGT). Frozen after this.

### What happened
20 Oct ~22:07 SGT, iPhone on https://covercall-demo-2026.web.app: "Hands-free unavailable: per-IP token limit
reached". Request logs: one phone (`222.164.40.95`, one instance) minted 5 tokens in 57 s (22:03:36-22:04:33),
then got 429 seven times. The limiter worked as built; 5 per IP per 10 min was too tight when every mode tap
mints, and the iPhone sessions never got working audio (no tool call followed any token), so the lead kept
retrying. Two more defects: the limiter keyed on the left-most `X-Forwarded-For` entry (client-supplied, so the
per-IP limit could be bypassed), and the hands-free -> push-to-talk fallback only switched the mode, leaving a
dead "Hold to talk" button.

### What changed
| Thing | Value |
|---|---|
| api | `client_ip()` = right-most `X-Forwarded-For` entry (the one Cloud Run appends). Limits **20 per IP and 120 overall per 10 min** (429 beyond). One `live_token limiter_key=<ip> outcome=...` log line per request. Counters still in memory per instance |
| Web | Mode tap creates/reuses the input and output `AudioContext`s and calls `resume()` before any `await` (iOS); Hold to talk resumes again. If audio is not running once the socket opens: "Tap to enable audio", never "Listening". Hands-free -> push-to-talk fallback really connects; a **429 (or mic denial) goes straight to text**. Re-tapping a connected or connecting mode does not mint again. Pure rules in `web/src/voice/voiceFlow.ts` |
| Commits | `7cb16dc` (api), `7cd5bf3` (web) |
| api | revision **`covercall-api-00010-qoy`** (tag `final`, image `api:fix-7cb16dc`), 100% of traffic. Same env and secrets as `00006-bip` |
| Web | live release built from `7cd5bf3` against the production api (`index-HqNEQ3kc.js`) |

### Verification
| Check | Result |
|---|---|
| Limiter key, tagged revision, two networks (one call each with a spoofed `X-Forwarded-For: 10.9.9.9`) | key = request `remoteIp` every time (`222.164.40.95`, hotspot `119.234.32.32`); never `10.9.9.9` |
| Author's iPhone test on preview `voicefix` (Safari and Chrome) | audio heard, read-back, "yes, approve", FILLED; push-to-talk answered |
| After the api + Hosting promote (`00008-xam`) | S-017 FILLED in 2.1 min (`gap-0019`); Nobody replies ESCALATED then RESOLVED in 2.8 min (`gap-0020`); fake-mic voice check 5/5; 385 api requests, all 200 |
| After the preview origin was removed (`00010-qoy`) | preview origin CORS 400, `web.app` 200; fake-mic voice check 2/2; S-017 FILLED in 1.4 min (`gap-0021`) |
| Checks on `7cd5bf3` | pytest 192 passed, ruff, mypy; npm test 41/41, tsc, build, local Playwright 2/2 (web checks ran in Cloud Build: Windows Application Control on the author's laptop now blocks rollup's native binary) |

One fake-mic run on the preview failed (1 of 5) before the promote; its trace was overwritten, cause unknown.
Every run since (10) passed.

### Rollback (exact commands)
```bash
gcloud run services update-traffic covercall-api --project covercall-demo-2026 --region asia-southeast1 \
  --to-revisions covercall-api-00006-bip=100
firebase hosting:clone covercall-demo-2026:prevlive2 covercall-demo-2026:live --project covercall-demo-2026
```
`prevlive2` (expires 27 Oct) holds the pre-fix live release. Tags `fix` (`00008-xam`, with the preview origin)
and `final` remain; preview channel `voicefix` expires 27 Oct.

### Still open
- Rate-limit counters are per instance (in memory); no evidence yet that Firestore-backed counters are needed.
- The limiter assumes Cloud Run's front end is the only proxy. A load balancer in front would add an entry
  and must be revisited.
- Gemini parser variation, the real clock and `gap-0001` (above) are unchanged.

---

## Demo clock fix (branch `fix/demo-clock`, promoted 2026-10-21 21:12 SGT). Frozen after this.

### What happened
The demo shifts are fixed on 3-8 Nov 2026 and production runs on the real clock. Locally reproduced: from
3 Nov 06:19 SGT the S-017 tap and the voice report for "Tuesday, 3 November" escalate on approval and never
fill; from 4 Nov 06:19 "Nobody replies" escalates without sending an offer. Judging runs to 6 Nov.

### What changed
| Thing | Value |
|---|---|
| api | `DEMO_CLOCK_OFFSET_DAYS=7`: deadlines (solver arrival, t_esc lock, next offers, countdown) are judged on a clock 7 days behind; event timestamps stay real (decision 0025). Commit `d042863`. Works until 10 Nov 06:19 SGT |
| api | revision **`covercall-api-00013-xiz`** (tag `democlockfinal`, image `api:clock-d042863`), 100% of traffic. Env as `00010-qoy` plus `DEMO_CLOCK_OFFSET_DAYS=7` |
| solver | revision **`covercall-solver-00005-lmf`**, `--min-instances 1` (was 0; first solve after idle took 7.5-13.6 s). Commit `7a779fb`. Roughly US$0.30-0.45 a day |
| Unchanged | web, Hosting, persona-sim, guard, agent, workflow definition |

### Verification
| Check | Result |
|---|---|
| Local sweep, judge times 21 Oct 19:00 to 6 Nov 23:59 (8 times x voice, S-017, Nobody replies) | all 24 match the 20-21 Oct runs (same outcome, offers, people); no fan-out; countdown 3.3-20.5 days |
| Checks on `d042863` | pytest 198 passed, ruff, mypy; npm test 41/41, tsc |
| Tag `democlock` (`00012-dol`, `API_URL` = tag URL so the workflow ran the new code) | offset 7.00; Nobody replies RESOLVED with 12 single timeouts; voice FILLED; 199 requests all 200 |
| Control: S-017 x4 alternating PROD (offset 0) / TAG (offset 7), 21 Oct 20:48-20:58 SGT | identical: all ESCALATED -> RESOLVED, same 9 single offers; 6-7 "unclear" parses per run lining up with Vertex 504/429/500 on both revisions |
| After the shift (`gap-0035..37`) | offset 7.00; Nobody replies RESOLVED (3.1 min); voice FILLED (0.6 min); S-017 escalated in the control pattern (7 unclear vs 6 Vertex errors); 315 requests all 200, no tracebacks |
| Solver after 20 min idle (`gap-0038`, 21:39 SGT) | no new instance started; solver `/solve` 0.84 s, api `/internal/solve` 3.4 s, read-back 5.7 s after the report (cold before: `/internal/solve` 7.5-13.6 s). The voice run itself escalated: 8 "unclear" parses vs 7 Vertex errors (control pattern) |

### Finding: Vertex errors make S-017 escalate (open)
gemini-3.8-flash on Vertex `global` failed about 75-90% of calls on 21 Oct (504 DEADLINE_EXCEEDED, 429, 500;
18-39% on 18 and 20 Oct). A failed parse is "unclear", which fails closed to decline, so S-017 escalates on
any revision. The SDK sends `X-Server-Timeout: 8` and the server stops about 3.4 s earlier: the 504s and the
4.6-4.7 s latency spike are that deadline. No status-page incident; no project quota (dynamic shared quota).
Not available on Vertex asia-southeast1 or us-central1 (404). The Gemini Developer API parsed 12/12 in the
same window. Fix in progress on `fix/parse-reliability` (not deployed).

### Rollback (exact commands)
```bash
gcloud run services update-traffic covercall-api --project covercall-demo-2026 --region asia-southeast1 \
  --to-revisions covercall-api-00010-qoy=100
gcloud run services update-traffic covercall-solver --project covercall-demo-2026 --region asia-southeast1 \
  --to-revisions covercall-solver-00004-kls=100
```
`00010-qoy` keeps tag `final`. Tag `democlock` was removed after confirming no execution started through it
was running. Gaps created on `00013-xiz` carry `clock_offset_s`, which older code ignores.

### Still open
- Vertex reliability (above). `gap-0022` (started 21 Oct 17:16 SGT, not ours) is still waiting in its workflow.
- `prevlive2` and `voicefix` preview channels expire 27 Oct; Hosting is unchanged by this fix.
