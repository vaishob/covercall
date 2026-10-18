# Decision 0023: Scenario gaps use a per-gap overlay; Gemini Flash parses replies and writes persona text

- **Date:** 2026-10-18
- **PDF sections:** §7.1, §7.3, §8.3

## Scenario overlay
- A scenario gap's commit writes its cover shifts and the absence to `overlays/{gapId}`, never to the
  shared `shifts` roster. Its planner context is the seeded roster (every `cover:` shift ignored) plus
  only its own overlay, so every run of a scenario starts from the same roster. Lead-reported gaps
  still write to the roster. `tests/test_dev_server.py` runs S-017 twice and checks identical plans.

## Gemini on (production)
- `PARSER_IMPL=gemini` on api: `parse_reply` calls `gemini-3.8-flash` (Enterprise Agent Platform,
  `global`) with structured output, validated against the §7.3 schema. Staff text sits between
  `<staff_reply>` delimiters as data. One retry on invalid output, then `unclear`; confidence below
  `parse_confidence_min` (0.7), any error or a timeout (8 s) also give `unclear`, never an accept.
  The guard still runs first. Locally the deterministic stub stays the default.
- `PERSONA_TEXT_IMPL=gemini` on persona-sim: the seeded intent is unchanged; Gemini writes only the
  words (temperature 0.8, seeded). The text must parse back (stub parser) to the same intent and
  window, otherwise the template is used.
- Outcome events carry `parser_impl`, `prompt_sha256`, `text_impl` and `text_prompt_sha256`
  (`parses/{offerId}`, merged by api). `cc-api` has `roles/aiplatform.user`.
