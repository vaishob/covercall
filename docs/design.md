# CoverCall — Design Doc (Google Cloud AI Builder Cup)
Oct 18, 2026 · @Vaishob

## 0. How to use this document
This is the single source of truth for building CoverCall, a solo entry in the Google Cloud AI Builder Cup. An engineer or coding agent (Google AI Studio, Codex, Claude Code) with no prior context MUST be able to build, test, deploy and present the product from this document alone.

**What CoverCall is, in one paragraph.** A shift lead at a small three-outlet café chain in Singapore gets a sick call at 6:02am. They tell CoverCall by voice. CoverCall finds legal, low-cost replacements, including staff from another outlet. After the lead approves by voice, it messages candidates one at a time, reads their replies, re-plans when someone declines or counter-offers, and escalates when time runs out. Every assignment is checked against the Singapore Employment Act by a constraint solver and an independent validator, never by a language model. Every step is checkpointed, traced and evaluated.

### Conventions
- MUST, SHOULD and MAY follow RFC 2119. A MUST that fails is release-blocking (P0).
- Names in `code` font are canonical. Use them as written for services, collections, fields, rule IDs and routes.
- "Design default" marks a tunable number chosen for this design, not a fact from a source. Defaults live in config, never hard-coded.
- All code, comments, docs, UI copy, deck and video MUST be in English.

### Ground rules (non-negotiable)
- Never invent metrics, legal rules, features, test results or capabilities. If a fact is missing, add it to §15 Open items and stop that thread.
- Every legal rule in code MUST cite its public source and section.
- All data is synthetic and MUST be labelled synthetic in the UI footer, repo and deck.
- Use public sources and synthetic data only. Use no proprietary, employer-derived or confidential code, data or designs.
- Never commit secrets. Use Secret Manager.
- The live app, video, deck and repo MUST describe the same version and the same capabilities.

## 1. Competition context and rubric tracker
CoverCall targets the **Future of Work & Enterprise Productivity** theme, with Retail & Commerce as the secondary fit. Technical Merit is 40% of the score, so verifiable engineering comes first.

- Technical Merit & GenAI Implementation (40%): Cloud Workflows state machine with durable callbacks; OR-Tools solver plus independent validator; Gemini Live, Flash and Pro; fine-tuned Gemma guard; Firestore event log; Cloud Trace; Cloud Build eval gate.
- Problem Alignment & Impact (25%): Café lead at 6:02am; small operators with no workforce software; Singapore Employment Act compliance; overtime cost avoided against a stated baseline.
- UX / Solution Design (10%): No sign-in; one-tap Scenario button; hands-free voice with captions; one-handed mobile layout; P0-first evals page.
- Innovation & Creativity (25%): Voice plus provable compliance plus autonomous cascade; `RosterProvider` adapter for Deputy- or UKG-style systems; clinics shown as a second sector.

## 2. Product summary
CoverCall fills a sudden shift gap for a small multi-outlet operator in minutes, hands-free. It proves every assignment complies with the Singapore Employment Act and shows the overtime cost it avoided.

- **Primary user:** shift lead or owner of a three-outlet café chain in Singapore (`bugis`, `tampines`, `jurong_east`).
- **Staff:** about 30 people. Full-timers plus student part-timers aged 17 and over from polytechnic, ITE and university.
- **Impact metric:** overtime cost avoided per decision, measured against `baseline/most_reliable_first.py`, alongside `rule_violations` (CoverCall MUST be 0) and `time_to_fill_min`.

## 3. Core user journeys
- **J1 — The 6:02am absence (the hook):** Lead reports Ali sick for Bugis morning shift; roster re-solves; top 3 legal candidates shown with cost, travel time, and rule checks; greyed-out candidates show plain-English rule warnings with source links; lead approves with read-back.
- **J2 — The cascade:** Sends offers one at a time with reply window countdown; handles declines, counter-offers ("09:00–15:00"), and timeouts; commits roster on acceptance.
- **J3 — Escalation:** Fans out when slack runs low; escalates at `t_esc` with ranked fallbacks (borrow, reduced service, lead covers, agency, unfilled).
- **J4 — Adversarial:** Refuses illegal double shift citing `SG-EA4-DAILY-MAX-12H`; quarantines prompt-injected staff reply via `guard`.
- **J5 — The judge's evidence path:** `/evals` and `/trace/:gapId` replay with hash-chain verification.
- **J6 — Real connectors:** Telegram opt-in and Google Maps Routes API transit times.

## 4. System architecture
Components: `web`, `api`, `coverage-cascade` (Cloud Workflows), `solver`, `validator`, `agent`, `guard`, `persona-sim`, `connectors`, `Firestore` (`(default)` and `sim`), `BigQuery` (`covercall_evals`), `Cloud Storage`, `Cloud Build`, `Observability`, `Secret Manager`.

## 5. Coverage workflow (`coverage-cascade`)
States: `REPORTED`, `GUARDED`, `SOLVED`, `OUTREACH`, `COMMITTING`, `FILLED`, `ESCALATED`, `RESOLVED`, `HELD`, `CANCELLED`.
Formulas (§5.2):
- `mustFillBy(c) = shiftStart - travel(c) - buffer`
- `slack(t) = max_c mustFillBy(c) - t`
- `replyWindow(t) = min(w_max, max(w_min, slack(t) / k))`
- `t_esc = max_c mustFillBy(c) - escalationLead`

## 6. Policy engine
Every rule is a declarative YAML spec in `policy/rules/*.yaml` with a cited public source and section, compiled into OR-Tools CP-SAT (`policy/compile_cpsat.py`) and re-implemented independently in plain Python (`policy/validate.py`).

## 7. AI components
Pinned in `config/models.yaml`. Prompts in `prompts/*.md`.

## 8. Data model and synthetic data
Seeded generator `python -m datagen build --seed 42`. All records carry `synthetic: true`.

## 9. Connectors and adapters
Telegram bot webhook, Google Maps Routes API transit matrix, and `RosterProvider` protocol (`FirestoreRosterProvider` + `ExternalWfmRosterProvider` stub).

## 10. Evaluation and the release gate
P0 metrics (`rule_violations`, `solver_validator_disagreements`, `unapproved_outbound`, `injection_executed`, `pii_leak`, `outcome_missing`, `escalation_late`, `nondeterminism`) MUST all equal 0.

## 11–15. Frontend, Security, Build Order, Video/Deck, Pre-submission Gate
See `docs/OPEN_ITEMS.md` and `docs/decisions/` for tracked items and architectural decisions.
