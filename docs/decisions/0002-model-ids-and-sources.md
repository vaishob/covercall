# Decision 0002: Statutory Rule Sources, Objective Weights, and Model Pinning

- **Date:** 2026-10-18
- **PDF Section:** §1.3, §3.1, §6.2, §7.1, §15.2

## Context
1. **Statutory URLs (§6.2):** The PDF explicitly gives `https://www.mom.gov.sg/employment-practices/hours-of-work-overtime-and-rest-days` (last updated 2025-07-24) and references three additional public pages in §6.2 and §15.3: MOM's "Who is covered by the Employment Act" page, MOM's "Overtime for part-time employees" page, and SFA's "Requirements for food handlers / WSQ Food Safety Course Level 1" page.
2. **Barista Food Handler Rule (§15.2):** §15.2 notes checking whether SFA's definition covers beverages before enforcing `SG-SFA-FSC-L1` on the barista station.
3. **Solver Objective Weights (§6.4):** `policy/company.yaml` requires tunable design-default weights `objective_weights: {cost, fairness, disruption}` operating on integer cents.
4. **Model IDs (§7.1):** `config/models.yaml` requires pinned model IDs or `TODO-VERIFY` for unverified models.

## Decision
1. **Verified Official Sources:** All four official Singapore statutory pages were retrieved and verified live on 2026-10-18 with HTTP 200:
   - MOM Hours/OT/Rest Day: `https://www.mom.gov.sg/employment-practices/hours-of-work-overtime-and-rest-days` (`source_last_updated: 2025-07-24`)
   - MOM Coverage: `https://www.mom.gov.sg/employment-practices/employment-act/who-is-covered` (`title: "Employment Act: who it covers"`, `section: "Who is covered under Part 4"`, `source_last_updated: 2025-07-24`)
   - MOM Part-Time Overtime: `https://www.mom.gov.sg/employment-practices/part-time-employment` (`title: "Part-time employment"`, `section: "Overtime"`, `source_last_updated: 2025-07-25`)
   - SFA Food Safety Course Level 1: `https://www.sfa.gov.sg/food-handler-hygiene-officer/training-courses/wsq-food-safety-course-level-1` (`title: "WSQ Food Safety Course (FSC) Level 1"`, `section: "Who must attain WSQ FSC Level 1 certification?"`, `source_last_updated: 2026-08-24`)
2. **Baristas as Food Handlers (`enforce_fsc_on_barista: true`):** The retrieved SFA page explicitly states: *"A Food Handler is defined as any person who handles and prepares food and beverages within food establishments licensed by SFA."* Therefore `enforce_fsc_on_barista: true` is set in `policy/company.yaml` and enforced in `SG-SFA-FSC-L1`.
3. **Objective Weights (`policy/company.yaml`):** Set `objective_weights: {cost: 1, fairness: 500, disruption: 300}` in integer cents (`cost: 1` = 1× incremental wage cost in cents; `fairness: 500` = S$5.00 equivalent soft penalty per cover beyond `max_covers: 2` in 14 days; `disruption: 300` = S$3.00 penalty for split segments or cross-outlet borrow travel friction).
4. **Model Pinning (`config/models.yaml`):**
   - `voice`: `gemini-3.1-flash-live-preview` (`v1alpha`), verified in Google's Live API documentation.
   - `agent`: `gemini-2.5-flash` (`v1`), pinned for structured output (`parse_reply`, `explain_plan`, `draft_offer`).
   - `persona_sim`: `gemini-2.5-flash` (`v1`), pinned with temperature `0.8` and scenario seed.
   - `guard`: `TODO-VERIFY` in `config/models.yaml` until Slice 5 Gemma 3 270M fine-tuning completes; in Slices 1–2 `services/guard` runs the deterministic fail-closed stub (`guard_impl: "stub-v0"`).
   - `eval_judge`: `gemini-2.5-pro` (`v1`), Cloud Build only.

## Alternatives Considered
- Leaving `SG-EA4-COVERAGE`, `SG-PT-OT-RATE`, or `SG-SFA-FSC-L1` with `TODO-VERIFY` URLs: rejected because retrieving the live MOM and SFA URLs directly allowed all 15 rules in §6.2 to be verified and active in Slice 1.
