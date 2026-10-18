# Open Items to Verify (§15.2)

All data in CoverCall is synthetic. This file mirrors §15.2 of the CoverCall Design Doc and tracks items requiring external verification or later-slice completion.

| Item | Status | Why it matters | Where to check / Resolution |
|---|---|---|---|
| Submission deadline and current rules | `TODO-VERIFY` | The briefing cited 18 Oct 2026; the participant dashboard is authoritative | Participant dashboard |
| Innovation & Feasibility weight | `TODO-VERIFY` | Stated rubric weights sum to 85%; remaining 15% presumed Innovation & Feasibility | Participant dashboard |
| Part 4 coverage details | `VERIFIED (2026-10-18)` | Drives `SG-EA4-COVERAGE` (workmen <= $4,500, non-workmen <= $2,600, managers/executives excluded) | Verified at `https://www.mom.gov.sg/employment-practices/employment-act/who-is-covered` (Last Updated 24 July 2025) |
| Whether baristas count as food handlers | `VERIFIED (2026-10-18)` | SFA's definition covers anyone who handles and prepares food and beverages in SFA-licensed premises; `enforce_fsc_on_barista: true` in `policy/company.yaml` | Verified at `https://www.sfa.gov.sg/food-handler-hygiene-officer/training-courses/wsq-food-safety-course-level-1` (Last Updated 24 Aug 2026) |
| Public-holiday rules | `OPEN (Out of scope v1)` | Not encoded in this version; demo scenarios avoid public holidays (`2026-11-03` is a normal Tuesday) | MOM public holiday page |
| Competitor facts (UKG, Deputy, Homebase, Shiftboard, Humanforce, Sling, Soon.works, Fountain) | `TODO-VERIFY` | Came from market scan; Slice 8 deck must use verified facts only | Each vendor's own site before Slice 8 deck export |
| Singapore F&B manpower and small-operator tooling | `TODO-VERIFY` | Deck slide 3 needs cited public evidence; "small operators roster on chat groups and spreadsheets" remains a hypothesis | Public MOM, SingStat or industry reports |
| Exact Gemini model IDs, Live API access route, region availability in `asia-southeast1` | `PARTIAL / TODO-VERIFY` | `gemini-3.1-flash-live-preview` (`v1alpha`), `gemini-2.5-flash` (`v1`), and `gemini-2.5-pro` (`v1`) pinned in `config/models.yaml`; fine-tuned Gemma 3 270M checkpoint is `TODO-VERIFY` until Slice 5 (`guard` uses `guard_impl: "stub-v0"` in Slices 1–2); Vertex AI regional endpoint quota in `asia-southeast1` pending live GCP project deployment | Google model documentation & GCP console |
| Routes API transit coverage in the route matrix for Singapore | `PLACEHOLDER (Slice 1–2)` | No `ROUTES_API_KEY` secret is provisioned in local/CI container; `data/travel_cache.json` uses `"source": "placeholder-not-routes-api"` per §3.8 step 7 until Slice 7 real connector key is configured in Secret Manager | Google Maps Routes API documentation |
| Cloud Run / Workflows live GCP deployment in `asia-southeast1` | `TODO-VERIFY (Environment)` | Container environment has no `gcloud` CLI or attached GCP billing credentials; idempotent deployment scripts are provided in `infra/deploy.sh` and `workflows/coverage_cascade.yaml`, while `e2e_cascade.py` runs against the local/container FastAPI + workflow engine harness | Run `infra/deploy.sh` with authenticated `gcloud` in target GCP project |
