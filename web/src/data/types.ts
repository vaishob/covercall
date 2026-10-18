/**
 * Canonical TypeScript types mirroring §8.1 (Firestore schema) and §10.4 (BigQuery covercall_evals)
 * of the CoverCall Design Doc.
 *
 * Canonical field names are preserved in snake_case to match the backend & Firestore documents.
 */

export interface OutletStationSpec {
  station: 'barista' | 'kitchen' | 'cashier' | string;
  skill: string;
  food_handling: boolean;
  min_count: number;
}

/** Collection: outlets/{outletId} (§8.1) */
export interface OutletDoc {
  id: string;
  name: string;
  area: 'Bugis' | 'Tampines' | 'Jurong East' | string;
  lat: number;
  lng: number;
  opening_hours: { open: string; close: string };
  stations: OutletStationSpec[];
  keyholders: string[];
  synthetic: true;
}

/** Collection: staff/{staffId} display fields (§8.1) */
export interface StaffDoc {
  id: string;
  display_name: string;
  age: number; // 17 or over
  is_student: boolean;
  home_area: string;
  home_outlet: string;
  contract_type: 'full_time' | 'part_time';
  employee_class: 'workman' | 'non_workman' | 'manager_executive';
  monthly_basic_sgd?: number;
  hourly_basic_sgd?: number;
  weekly_contract_hours: number;
  normal_daily_hours: number;
  skills: string[];
  fsc_l1_passed_on: string | null;
  keyholder: boolean;
  channel: 'sim' | 'telegram';
  synthetic: true;
}

/** Collection: shifts/{shiftId} (§8.1) */
export interface ShiftDoc {
  id: string;
  outlet: string;
  station: string;
  staff_id: string;
  start: string; // ISO 8601 +08:00
  end: string; // ISO 8601 +08:00
  breaks: Array<{ start: string; end: string }>;
  status: 'scheduled' | 'absent' | 'covered' | 'cancelled';
  synthetic: true;
}

/** Collection: ledgers/{staffId_YYYYMM} (§8.1) */
export interface LedgerDoc {
  id: string;
  staff_id: string;
  month: string; // YYYYMM
  ot_hours_used: number;
  rest_days: string[];
  cover_requests_14d: number;
  synthetic: true;
}

export type GapState =
  | 'REPORTED'
  | 'GUARDED'
  | 'HELD'
  | 'SOLVED'
  | 'OUTREACH'
  | 'COMMITTING'
  | 'FILLED'
  | 'ESCALATED'
  | 'RESOLVED'
  | 'CANCELLED';

/** Collection: gaps/{gapId} (§8.1) */
export interface GapDoc {
  id: string;
  outlet: string;
  station: string;
  start: string; // ISO 8601 +08:00
  end: string; // ISO 8601 +08:00
  absent_staff_id: string;
  state: GapState;
  version: number;
  plan_id: string | null;
  outcome: string | null;
  cost_saved_sgd: number | null;
  workflow_execution_id: string | null;
  must_fill_by?: string; // Supplied by backend solver/timing
  synthetic: true;
}

/** Subcollection: gaps/{gapId}/events/{seq} (§8.1 & §5.4) */
export interface GapEventDoc {
  seq: number;
  type: string;
  from_state: string;
  to_state: string;
  actor: string; // 'lead' | 'system' | 'staff:<id>' | 'model:<id>'
  model_ids: string[];
  rule_ids: string[];
  trace_id: string;
  payload: Record<string, unknown>; // Redacted
  prev_hash: string;
  hash: string;
  ts: string; // ISO 8601 +08:00
  chain_verified?: boolean | null; // Supplied by trace verification endpoint, never assumed true in mock mode
}

export interface PlanCandidateEntry {
  staff_id: string;
  segments: Array<{ start: string; end: string }>;
  cost_breakdown: {
    incremental_cost_sgd: number;
    saves_vs_overtime_sgd: number;
    basis?: string;
  };
  travel_min: number;
  arrival: string; // ISO 8601 +08:00
  rules_checked: string[];
  rejected_rules: Array<{
    rule_id: string;
    severity: 'P0' | 'P1' | 'P2';
    message: string;
    source_url: string;
    source_publisher: string;
    source_section: string;
  }>;
}

/** Collection: plans/{planId} (§8.1) */
export interface PlanDoc {
  id: string;
  gap_id: string;
  candidates: PlanCandidateEntry[];
  solver_params: Record<string, unknown>;
  validator_version: string;
  synthetic: true;
}

/** Collection: offers/{offerId} (§8.1) */
export interface OfferDoc {
  id: string;
  gap_id: string;
  staff_id: string;
  sent_at: string; // ISO 8601 +08:00
  window_s: number;
  status: 'sent' | 'accepted' | 'declined' | 'counter' | 'timeout' | 'withdrawn';
  synthetic: true;
}

/** Collection: approvals/{approvalId} (§8.1) */
export interface ApprovalDoc {
  id: string;
  gap_id: string;
  tier: 'T0' | 'T1' | 'T2' | 'T3';
  nonce: string;
  readback_text: string;
  transcript: string;
  decision: 'approved' | 'rejected' | 'pending';
  channel: 'voice' | 'tap';
  ts: string;
  synthetic: true;
}

/** Collection: quarantine/{id} (§8.1) */
export interface QuarantineDoc {
  id: string;
  gap_id: string;
  staff_id: string;
  guard_labels: Array<'injection' | 'pii' | 'abuse' | 'ok'>;
  guard_impl?: string | null;
  redacted_text: string;
  synthetic: true;
}

/** BigQuery Dataset: covercall_evals (§10.4 & §11.5) */
export interface EvalRunRow {
  run_id: string;
  build_id: string;
  git_sha: string;
  started_at: string;
  models: Record<string, { model_id: string; prompt_hash?: string }>;
  tolerance: Record<string, number>;
  status: 'PASSED' | 'BLOCKED';
}

export interface EvalMetricRow {
  run_id: string;
  metric: string;
  severity: 'P0' | 'P1' | 'P2';
  slice: string;
  value: number | null;
  threshold: number | null;
  change_since_last?: number | null;
  passed: boolean | null;
}

export interface EvalCaseRow {
  run_id: string;
  dataset: 'golden' | 'heldout' | 'reply_test' | 'adversarial';
  case_id: string;
  metric: string;
  passed: boolean;
  trace_id: string;
  details: Record<string, unknown>;
}

export interface CoverCallEvalsReadModel {
  isMock: boolean;
  latestRun: EvalRunRow | null;
  buildHistory: EvalRunRow[];
  p0Metrics: EvalMetricRow[];
  p1Metrics: EvalMetricRow[];
  p2Metrics: EvalMetricRow[];
  sliceTables: {
    parseAccuracyBySlice: EvalMetricRow[];
    guardComparisonBySlice: Array<{
      slice: string;
      label: string;
      gemmaPrecision: number | null;
      gemmaRecall: number | null;
      geminiBaselinePrecision: number | null;
      geminiBaselineRecall: number | null;
    }>;
  };
  headlineVsBaseline: {
    overtimeSavedMedianSgd: number | null;
    overtimeSavedTotalSgd: number | null;
    coverCallViolations: number | null;
    baselineViolations: number | null;
    coverCallTimeToFillMin: number | null;
    baselineTimeToFillMin: number | null;
  };
  cases: EvalCaseRow[];
}
