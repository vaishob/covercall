# Decision 0022: The "sim" Firestore database is named `covercall-sim`

- **Date:** 2026-10-18
- **PDF sections:** §4.5, §8.3 (the separate `sim` database)

## Context
The first real `gcloud firestore databases create --database=sim` failed:
`INVALID_ARGUMENT: database_id should be 4-63 characters, and valid characters are /[a-z][0-9]-/`.

## Decision
- The database the design calls `sim` has the ID **`covercall-sim`**. Docs keep calling it the
  "sim" database; only the ID changes.
- One constant per language: `SIM_DATABASE` in `services/common/store.py` (persona-sim, datagen
  seeding, scenario seeding) and `SIM_DB_ID` in `infra/env.sh` (database creation, the IAM
  condition that limits it to persona-sim). `infra/firebase.json` names it for the rules deploy.
- `tests/test_infra.py` checks that the ID is valid and the same in all three places, and that no
  code opens a database called `sim`.
