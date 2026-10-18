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
| Exact Gemini model IDs, Live API route, region availability | **TODO-VERIFY** | Services refuse to start on `TODO-VERIFY` | Found 2026-10-18 on https://ai.google.dev/gemini-api/docs/models (updated 2026-10-13): `gemini-3.1-flash-live-preview` is listed as a legacy preview (the page recommends `gemini-3.8-live`); the `gemini-2.5` family is limited to earlier users; current Flash IDs include `gemini-3.6-flash` and `gemini-3.8-flash`. Not confirmed on Vertex AI for `asia-southeast1`, and not confirmed that ephemeral tokens work with `gemini-3.8-live`. Pin in `config/models.yaml` after checking the console |
| Routes API transit coverage for Singapore | PLACEHOLDER | Travel times for borrows | `data/travel_cache.json` is `source: placeholder-not-routes-api` (no key used; no paid API calls in this run). Replace with a real matrix in Slice 7 |
| Outlet coordinates | TODO-VERIFY | Map display only | `datagen/__init__.py` uses approximate public area centroids for Bugis, Tampines and Jurong East; check against a public map |
| Persona reply review (§8.3) | NOT STARTED | Natural, respectful synthetic replies | `datagen/REVIEW.md` |
| Firestore emulator for Slice 2 | NOT USED | Local verification of transactions | Running it needs the `firebase` or `gcloud` CLI, which this unattended run may not invoke. An in-memory fake behind the same interface is used (docs/decisions/0010) |
| Cloud Workflows: can one callback endpoint receive several requests? | TODO-VERIFY | Fan-out design (§4.4) | Not verified against the Workflows callbacks docs. The YAML uses one endpoint per offer inside a `parallel` block, which is the fallback KICKSTART names (docs/decisions/0011) |
| Gemini availability in `asia-southeast1` | TODO-VERIFY | §4.6, §13.3 | Check in the console before deploy |
