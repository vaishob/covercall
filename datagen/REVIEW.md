# Synthetic reply review (§8.3)

**All data is synthetic.**

## Status: NOT STARTED

§8.3 asks two or three Singaporean reviewers to mark a sample of about 50 generated replies as
natural, fake or offensive, and to remove the flagged patterns. **No human review has taken place.**
(An earlier version of this file said the templates were "audited". That was not true and is withdrawn.)

The reply corpus (2,000 replies) and the adversarial set (400) are Slice 5 work. Slices 1–2 generate
no surface text with a model. `persona-sim` uses fixed stub templates labelled `stub-v0`.

## What is already enforced in code
- Each reply's intent is fixed first (`datagen/personas.py: decide_reply`), and the label is ground truth.
- Persona style is sampled with its own seeded RNG and never reads the name.
  `tests/test_datagen.py::test_persona_style_never_reads_the_name` checks this by parsing the source
  and by renaming a person and comparing the personas.
- No naming pool maps to a language or dialect: `datagen/__init__.py` has one flat name list.

## Review log
| Date | Reviewers | Sample | Natural | Fake | Offensive | Patterns removed |
|---|---|---|---|---|---|---|
| (none yet) | | | | | | |
