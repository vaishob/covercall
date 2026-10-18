# Decision 0010: Verifying Slice 2 locally (no Cloud, no emulator)

- **Date:** 2026-10-18
- **PDF sections:** §4, §5, §13.2; handoff "UNATTENDED MODE"

## Context
This build may not run `gcloud`, `firebase` or `terraform`, or create or bill any Google Cloud resource.
The Firestore emulator is started with `firebase emulators:start` or `gcloud emulators firestore start`,
so it is out. Cloud Workflows has no local emulator.

## Decision
- **Store:** `services/common/store.py` defines one interface. `MemoryStore` (in-memory fake with the
  transaction semantics the code relies on: atomic write sets, `create` fails if the document exists,
  reads see the transaction's own writes) is used locally. `FirestoreStore` implements the same interface
  with `google-cloud-firestore` transactions and is **untested**.
- **Workflow:** `workflows/coverage_cascade.yaml` is checked statically (`tests/test_workflow.py`: every
  event type is in `TRANSITIONS`, guard has no retry, every call uses OIDC with the api audience, retry is
  3 attempts with backoff, waits use callbacks with `TimeoutError` handling). `evals/runners/local_cascade.py`
  executes the same steps by name (a test checks every YAML step is mirrored) through the real FastAPI routes
  with `TestClient`, a simulated clock and in-process stand-ins for callbacks, persona-sim, guard and agent.
- **Models:** none. Guard and parser are deterministic stubs labelled `stub-v0` in every payload.

## What this does not prove
That the YAML deploys and runs on Cloud Workflows, that Firestore transactions behave like the fake under
contention, that IAM and OIDC are configured right, or that Cloud Run cold starts are acceptable. These need
the deploy steps in `docs/HANDOFF.md`.
