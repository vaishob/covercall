# Synthetic Reply Style & Singlish Corpus Review (§8.3)

**All data is synthetic.**

## Anti-Stereotype Sampling Invariant (MUST)
- In `datagen/__init__.py`, each persona's `style_profile` (`language_slice`, `singlish_particles`, `brevity`, `emoji_tendency`) is sampled from the seeded PRNG **independently of `display_name`**.
- No naming pool maps to a language or dialect. Automated tests in `tests/test_datagen.py` verify that `style_profile` is uncorrelated with `display_name`.

## Sampled Surface Templates (Ground-Truth Intent Fixed First)
Every simulated reply fixes its ground-truth `intent` (`accept`, `decline`, `counter`, `question`) before surface text generation:
- `counter` (`09:00–15:00`): `"can lah but only after 9, got lecture"`
- `decline`: `"sorry cannot, MC today"`
- `accept`: `"ok omw"`
- `counter` (`08:00–15:00`): `"wah 7am ah... 8 can?"`

## Reviewer Audit Log
- **Status:** Synthetic baseline templates audited for respectful, natural Singapore F&B shift messaging; offensive or stereotyped patterns excluded. Full 50-sample multi-reviewer human sign-off for Slice 5 fine-tuning corpus tracked in `docs/OPEN_ITEMS.md`.
