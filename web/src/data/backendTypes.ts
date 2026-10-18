/**
 * The backend contract: response shapes of the `api` read routes, exactly as
 * services/api/app/views.py builds them. Field names are the backend's (§8.1, snake_case).
 * Money is integer cents. Do not edit by hand to "fix" the UI; change the backend and re-capture
 * the fixtures (python -m evals.runners.capture_fixtures) instead.
 */

export type GapState =
  | 'REPORTED'
  | 'GUARDED'
  | 'SOLVED'
  | 'OUTREACH'
  | 'COMMITTING'
  | 'FILLED'
  | 'ESCALATED'
  | 'RESOLVED'
  | 'HELD'
  | 'CANCELLED';

export type RuleKind = 'hard' | 'cost' | 'soft' | 'applicability_gate' | 'data_gate';

export interface CostBreakdownCents {
  base_cents: number;
  overtime_cents: number;
  rest_day_cents: number;
  total_cents: number;
}

export interface RuleCheckDto {
  rule_id: string;
  status: 'ok' | 'violation' | 'not_applicable';
  kind: RuleKind;
  title: string;
  message: string;
  source_url: string;
}

export interface BreakDto {
  start: string;
  duration_min: number;
}

export interface SegmentDto {
  staff_id: string;
  display_name: string;
  home_outlet: string;
  start: string;
  end: string;
  breaks: BreakDto[];
  travel_min: number;
  arrival: string;
  cost_breakdown: CostBreakdownCents;
  rules_checked: RuleCheckDto[];
}

export interface PlanOptionDto {
  rank: number;
  staff_ids: string[];
  segments: SegmentDto[];
  cost_breakdown: CostBreakdownCents;
  overtime_cost_cents: number;
  saves_vs_naive_cents: number | null;
  travel_min: number;
  arrival: string;
  is_cross_outlet_borrow: boolean;
}

export interface RejectedRuleDto {
  rule_id: string;
  kind: RuleKind;
  title: string;
  message: string;
  source_url: string;
  publisher: string;
  section: string;
}

export interface RejectedCandidateDto {
  staff_id: string;
  display_name: string;
  home_outlet: string | null;
  rules: RejectedRuleDto[];
}

export interface NaiveFirstPickDto {
  staff_id: string;
  display_name: string;
  overtime_cents: number;
  blocking_rule_ids: string[];
}

export interface PlanDto {
  plan_id: string;
  created_at: string;
  naive_first_pick: NaiveFirstPickDto | null;
  options: PlanOptionDto[];
  rejected: RejectedCandidateDto[];
}

export type OfferStatus =
  | 'open'
  | 'accepted'
  | 'decline'
  | 'countered'
  | 'timeout'
  | 'withdrawn'
  | 'late'
  | 'flagged';

export interface OfferDto {
  offer_id: string;
  staff_id: string;
  display_name: string | null;
  start: string;
  end: string;
  sent_at: string;
  window_s: number;
  status: OfferStatus;
  fanout_group: string | null;
  rank: number;
  late_reply: boolean;
}

export interface GapDto {
  gap_id: string;
  scenario_id: string | null;
  outlet: string;
  outlet_name: string;
  station: string;
  start: string;
  end: string;
  absent_staff_id: string;
  absent_staff_name: string | null;
  state: GapState;
  version: number;
  outcome: string | null;
  summary: string | null;
  cost_saved_cents: number | null;
  reported_at: string;
  filled_at: string | null;
  t_esc_locked: string | null;
  workflow_execution_id: string | null;
  approval_pending: boolean;
  fallbacks: string[] | null;
  time_scale: number;
}

export interface GapViewDto {
  gap: GapDto;
  clock: { now: string; seconds_to_escalation: number | null };
  plan: PlanDto | null;
  committed: {
    plan_id: string;
    rank: number;
    segments: Array<{ staff_id: string; display_name: string; start: string; end: string }>;
    cost_breakdown: CostBreakdownCents;
  } | null;
  offers: OfferDto[];
  synthetic: true;
}

export interface ApprovalDto {
  gap_id: string;
  pending: true;
  nonce: string;
  readback_text: string;
  plan_id: string;
  tier: 'T2';
  synthetic: true;
}

export interface QuarantineDto {
  quarantine_id: string;
  gap_id: string;
  offer_id: string | null;
  staff_id: string;
  display_name: string | null;
  guard_labels: string[];
  guard_impl: string | null;
  redacted_text: string;
  synthetic: true;
}

export interface EventDto {
  seq: number;
  type: string;
  from_state: string | null;
  to_state: string;
  actor: string;
  model_ids: string[];
  rule_ids: string[];
  trace_id: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
  ts: string;
  synthetic: true;
}

export interface EventsViewDto {
  gap_id: string;
  events: EventDto[];
  chain: { gap_id: string; ok: boolean; events: number; errors: string[] };
  synthetic: true;
}

export interface ScenarioDto {
  scenario_id: string;
  label: string;
  journey: string;
  description: string;
  now: string;
  gap: { outlet: string; station: string; start: string; end: string };
  synthetic: true;
}

export interface StatusDto {
  status: 'ok';
  environment: string;
  guard_impl: string;
  parser_impl: string;
  persona_text_impl: string;
  models: Record<string, { model_id: string; api_version: string; provider: string }>;
  time_scale: number;
  synthetic: true;
}

export interface EvalsDto {
  status: 'no_eval_run' | string;
  message: string;
  latest_run: null | Record<string, unknown>;
  metrics: unknown[];
  synthetic: true;
}

export type CreateGapResponse =
  | { status: 'created'; gap_id: string; workflow_execution_id: string }
  | {
      status: 'clarify';
      question: string;
      candidates: Array<{ staff_id: string; display_name: string; home_outlet: string }>;
    };

export const TERMINAL_STATES: readonly GapState[] = ['FILLED', 'RESOLVED', 'CANCELLED', 'HELD'];
