# Decision 0012: Delayed persona replies and demo time compression

- **Date:** 2026-10-18
- **PDF sections:** §4.5 (KICKSTART: "pick the smallest durable mechanism using existing components"), §8.1, §8.3

## Decision
- **Delivery:** `persona-sim` writes each scheduled reply to `sim/outbox/{message_id}` with `deliver_at`.
  On Cloud Run a background loop (warm instance, min instances 1, CPU not throttled) delivers due items every
  5 s to the api's `POST /replies`; `POST /deliver` does the same on demand. The outbox is durable
  (Firestore), and redelivery after a restart is harmless because the api drops duplicate `message_id`s.
  No new Google Cloud product is added (no Cloud Tasks or Scheduler).
- **Intent first:** the reply's intent comes from `datagen.personas.decide_reply` (scenario `will` wins,
  then hidden availability, then seeded tendencies). The label stays in the `sim` outbox; the api only sees text.
- **Surface text:** fixed templates (`text_impl: stub-v0`), not a model, until the `persona_sim` model is pinned.
- **Time compression:** `TIME_SCALE` (default 10 on Cloud Run) divides reply windows and reply delays in real
  seconds. The `/test` page states the factor in a visible banner. Locally the driver uses a simulated
  clock, so nothing is compressed: reported times are simulated minutes.
