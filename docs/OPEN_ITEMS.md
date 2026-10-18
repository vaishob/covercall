# Open items to verify (§15.2)

All data in CoverCall is synthetic. This file mirrors §15.2 and adds items found during the build.
`TODO-VERIFY` = a fact I could not confirm; that thread is stopped until someone confirms it.

| Item | Status | Why it matters | Where to check / what was found |
|---|---|---|---|
| Submission deadline and current rules | TODO-VERIFY | The briefing cited 18 Oct 2026; the dashboard is authoritative | Participant dashboard |
| Innovation & Feasibility weight | TODO-VERIFY | Stated weights sum to 85% | Participant dashboard |
| Part 4 coverage details | VERIFIED 2026-10-18 | Drives `SG-EA4-COVERAGE` | MOM "Employment Act: who it covers" (updated 24 July 2025): workmen ≤ S$4,500, non-workmen ≤ S$2,600. The page says Part 4 "does not cover all managers or executives"; CoverCall treats every `manager_executive` as not covered (conservative for cost, out of the candidate pool as the lead) |
| Part-time employee equivalent salary for the Part 4 test | DESIGN CHOICE | Part-timers are paid hourly | `hourly × weekly_contract_hours × 52 / 12` (docs/decisions/0005). Not stated by MOM |
| Whether baristas count as food handlers | VERIFIED 2026-10-18 | `SG-SFA-FSC-L1` on the barista station | SFA FSC L1 page (updated 24 Aug 2026): a food handler "handles and prepares food and beverages". `enforce_fsc_on_barista: true` |
| Hours of work: do breaks count toward the 12 h day? | TODO-VERIFY | Engines count breaks as hours of work (stricter) | MOM page does not say; see docs/decisions/0005 |
| Public-holiday rules | OPEN (not encoded) | Not in this version | Demo dates (3–8 Nov 2026) avoid public holidays: TODO-VERIFY against MOM's 2026 public holiday list |
| Shift-worker 30-hour rest-day form | OPEN (not encoded) | `SG-EA4-REST-DAY` uses the weekly day-off check | MOM page "Rest day" section |
| Competitor facts (UKG, Deputy, Homebase, Shiftboard, Humanforce, Sling, Soon.works, Fountain) | TODO-VERIFY | Deck must use verified facts only | Each vendor's own site |
| Singapore F&B manpower and small-operator tooling | TODO-VERIFY | Deck slide 3 | MOM, SingStat or industry reports |
| Exact Gemini model IDs | VERIFIED 2026-10-18 | `config/models.yaml` | Pinned: `voice` `gemini-3.8-live` (Gemini Developer API, `v1beta`); `agent` and `persona_sim` `gemini-3.8-flash`, `eval_judge` `gemini-4-argon` (Enterprise Agent Platform, `global`). Sources: https://ai.google.dev/gemini-api/docs/models (updated 2026-10-13), the Enterprise Agent Platform locations page (updated 2026-10-15). Decisions 0019–0021 |
| Live API ephemeral tokens | OPEN (Preview) | Voice auth (§7.2) | https://ai.google.dev/gemini-api/docs/live-api/ephemeral-tokens (updated 2026-09-15): Preview, Live API only, `v1beta` only; the example locks a token to `gemini-3.8-live`. Re-check before Slice 4 (decision 0019) |
| Guard model checkpoint | OPEN (Slice 5) | `guard` stays `TODO-VERIFY`; `stub-v0` runs | Base checkpoint `google/gemma-3-270m`; the fine-tuned weights come in Slice 5 |
| Routes API transit coverage for Singapore | PLACEHOLDER | Travel times for borrows | `data/travel_cache.json` is `source: placeholder-not-routes-api` (no key used; no paid API calls in this run). Replace with a real matrix in Slice 7 |
| Outlet coordinates | TODO-VERIFY | Map display only | `datagen/__init__.py` uses approximate public area centroids for Bugis, Tampines and Jurong East; check against a public map |
| Persona reply review (§8.3) | NOT STARTED | Natural, respectful synthetic replies | `datagen/REVIEW.md` |
| Firestore emulator for Slice 2 | NOT USED | Local verification of transactions | Running it needs the `firebase` or `gcloud` CLI, which this unattended run may not invoke. An in-memory fake behind the same interface is used (docs/decisions/0010) |
| Cloud Workflows: can one callback endpoint receive several requests? | VERIFIED 2026-10-18 | Fan-out design (§4.4) | No, not reliably: "a single callback slot is available"; requests sent before `await_callback` are not all kept (docs.cloud.google.com/workflows/docs/creating-callback-endpoints, updated 2026-10-13). So the YAML uses one endpoint per offer in a `parallel` for-loop (docs/decisions/0011) |
| Gemini availability in `asia-southeast1` | TODO-VERIFY | §4.6, §13.3 | The locations page (updated 2026-10-15) lists Gemini models for "Asia Pacific" as a group, not per region. Model calls use the `global` endpoint meanwhile (decision 0021); check in the console |
| Workflows YAML accepted by the service (`next: continue` in a `parallel` for-loop, `map.get`, `sys.get_env("GOOGLE_CLOUD_WORKFLOW_EXECUTION_ID")`, OIDC `audience`) | TODO-VERIFY | `workflows/coverage_cascade.yaml` is checked statically and mirrored by the local driver, but has never been deployed | The first `gcloud workflows deploy` validates the syntax (infra/50_workflow.sh) |
| `FirestoreStore` transactions | TODO-VERIFY | Locally only `MemoryStore` runs | Run the tests against the Firestore emulator or a dev project |
| IAM condition on Firestore database name (`resource.name == "projects/P/databases/covercall-sim"`, decision 0022) | TODO-VERIFY | Least privilege: only persona-sim may use `sim` | infra/20_iam.sh; check the Firestore IAM conditions docs |
| Firebase CLI multi-database rules (`infra/firebase.json` array form) | TODO-VERIFY | Rules for `(default)` and `sim` | Firebase CLI docs |
| gitleaks image tag in `cloudbuild.yaml` (`zricethezav/gitleaks:v8.18.4`) | TODO-VERIFY | CI secret scan | Docker Hub |
| Escalation lead vs short-notice reports | FINDING | With the PDF defaults, reports under ~41 min before a shift escalate at once (docs/decisions/0009) | Product decision: keep, or lower `escalation_lead_min` |
| Adversarial scenario (J4) in the data | OPEN | §11.3 asks for an "Adversarial" Scenario button; `GET /scenarios` lists only scenarios that exist in `evals/datasets` | No adversarial scenario has been generated yet (Slice 5: guard and adversarial set). The button is omitted rather than faked (docs/decisions/0017) |
| Browser reads by polling | DESIGN CHOICE | The UI polls `api` every 2 s instead of Firestore listeners (docs/decisions/0015) | Revisit if read load matters during judging |
