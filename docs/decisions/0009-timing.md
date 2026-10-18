# Decision 0009: Locking t_esc at approval, and clamping reply windows to it

- **Date:** 2026-10-18
- **PDF sections:** §5.1 (plan.approved: "escalation strategy locked"), §5.2, §10.1 (`escalation_late` P0)

## Context
The first local run of the golden set found `escalation_late = 6`. `t_esc = max_c mustFillBy(c) − escalationLead`
was recomputed every round. When the person with the latest deadline declined, the max dropped and the new `t_esc`
could already be in the past, so an escalation that fired at the earliest possible moment still counted as late.

## Decision
- `t_esc` is computed once, when `api` records `plan.approved`, from every legal candidate still in play.
  It is stored as `gaps/{id}.t_esc_locked` and in the event payload. If it is already past at approval,
  it is locked at the approval time (escalate at once). Re-approval after a material counter-offer locks it again.
- The window used for an offer is `min(replyWindow(t), t_esc_locked − t)`, so no wait outlives `t_esc`.
- `escalation.due` carries `t_esc` in its payload; the metric counts events with `ts > t_esc`.
- Slack, viability and fan-out still use the current candidates at each round (§5.2 formulas unchanged).

Result: `escalation_late = 0` on all 100 scenarios.

## Consequence (stated plainly)
With the PDF defaults (buffer 10, escalationLead 15) and 16-minute local travel, a gap reported less than about
41 minutes before the shift has slack under 15 minutes, so CoverCall escalates to the lead at once rather than
sending offers. This is most of the golden-set escalations. Lowering `escalation_lead_min` is a config change.
