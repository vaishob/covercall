/**
 * The one mapping layer between the backend contract (backendTypes.ts) and what the lead screen
 * renders. Display only: it formats and selects server values, and never computes legality,
 * cost, deadlines or ranking (ground rule: no business logic in the browser).
 */
import type {
  ApprovalDto,
  EventsViewDto,
  GapState,
  GapViewDto,
  OfferStatus,
  QuarantineDto,
  RuleKind,
  SegmentDto,
} from './backendTypes.ts';
import { TERMINAL_STATES } from './backendTypes.ts';

export type DataSourceKind = 'live' | 'replay';

export const KIND_LABELS: Record<RuleKind, string> = {
  hard: 'Hard rule',
  data_gate: 'Data gate',
  soft: 'Soft rule (penalty only)',
  cost: 'Cost rule',
  applicability_gate: 'Applicability gate',
};

/** Labels for the backend's fallback option IDs (gaps/{id}.fallbacks, §5.1 / J3). */
export const FALLBACK_LABELS: Record<string, string> = {
  borrow: 'Borrow from another outlet',
  reduced_service: 'Reduced service (close a station)',
  lead_covers: 'Lead covers',
  agency: 'Agency',
  unfilled: 'Leave unfilled',
};

export const OFFER_STATUS_LABELS: Record<OfferStatus, string> = {
  open: 'Awaiting reply',
  accepted: 'Accepted',
  decline: 'Declined',
  countered: 'Counter-offer',
  timeout: 'No reply (window timed out)',
  withdrawn: 'Withdrawn (covered by someone else)',
  late: 'Late reply (courtesy sent)',
  flagged: 'Flagged by guard (quarantined)',
};

export interface BreakView {
  start: string;
  durationMin: number;
}

export interface SegmentView {
  staffId: string;
  name: string;
  homeOutlet: string;
  start: string;
  end: string;
  breaks: BreakView[];
  travelMin: number;
  arrival: string;
}

export interface RuleCheckView {
  ruleId: string;
  title: string;
  kind: RuleKind;
  kindLabel: string;
  status: 'ok' | 'violation' | 'not_applicable';
  message: string;
  sourceUrl: string;
  staffName: string;
}

export interface PlanOptionView {
  rank: number;
  segments: SegmentView[];
  isSplit: boolean;
  isBorrow: boolean;
  totalCents: number;
  overtimeCents: number;
  savesVsNaiveCents: number | null;
  travelMin: number;
  arrival: string;
  /** Applicable hard and data-gate checks that passed (the green checks, J1 step 3). */
  passedChecks: RuleCheckView[];
}

export interface RejectedView {
  key: string;
  staffId: string;
  name: string;
  homeOutlet: string | null;
  ruleId: string;
  title: string;
  kind: RuleKind;
  kindLabel: string;
  message: string;
  sourceUrl: string;
  publisher: string;
  section: string;
}

export interface OfferView {
  offerId: string;
  seq: number;
  staffId: string;
  staffName: string;
  start: string;
  end: string;
  sentAt: string;
  windowS: number;
  status: OfferStatus;
  statusLabel: string;
  round: string | null;
  lateReply: boolean;
}

export interface QuarantineView {
  id: string;
  staffName: string;
  guardLabels: string[];
  guardImpl: string | null;
  redactedText: string;
}

export interface RosterCell {
  hour: string;
  staffName: string | null;
}

export interface FallbackView {
  id: string;
  label: string;
}

export interface GapView {
  gapId: string;
  scenarioId: string | null;
  outlet: string;
  outletName: string;
  station: string;
  start: string;
  end: string;
  reportedAt: string;
  absentName: string;
  state: GapState;
  version: number;
  outcome: string | null;
  outcomeLabel: string | null;
  summary: string | null;
  escalationAt: string | null;
  secondsToEscalation: number | null;
  costSavedCents: number | null;
  workflowExecutionId: string | null;
  approvalPending: boolean;
  fallbacks: FallbackView[];
  isTerminal: boolean;
  timeScale: number;
}

export interface LeadView {
  source: DataSourceKind;
  now: string;
  gap: GapView;
  plans: PlanOptionView[];
  naive: { name: string; overtimeCents: number; blockingRuleIds: string[] } | null;
  rejected: RejectedView[];
  offers: OfferView[];
  committed: { segments: SegmentView[]; totalCents: number; overtimeCents: number } | null;
  approval: { nonce: string; readback: string; planId: string } | null;
  quarantine: QuarantineView[];
  roster: { label: string; cells: RosterCell[] };
}

export function isTerminal(state: GapState): boolean {
  return TERMINAL_STATES.includes(state);
}

export function centsToSgd(cents: number): string {
  const sign = cents < 0 ? '-' : '';
  const abs = Math.abs(cents);
  return `${sign}S$${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`;
}

function segment(dto: SegmentDto): SegmentView {
  return {
    staffId: dto.staff_id,
    name: dto.display_name,
    homeOutlet: dto.home_outlet,
    start: dto.start,
    end: dto.end,
    breaks: dto.breaks.map((b) => ({ start: b.start, durationMin: b.duration_min })),
    travelMin: dto.travel_min,
    arrival: dto.arrival,
  };
}

/** Hour labels between two ISO times, from the strings themselves (display only). */
function hourMarks(startIso: string, endIso: string): string[] {
  const h0 = Number(startIso.slice(11, 13));
  const h1 = Number(endIso.slice(11, 13));
  const out: string[] = [];
  for (let h = h0; h < h1; h += 1) out.push(`${String(h).padStart(2, '0')}:00`);
  return out;
}

function roster(gap: GapView, segments: SegmentView[]): LeadView['roster'] {
  const cells = hourMarks(gap.start, gap.end).map((hour) => {
    const seg = segments.find((s) => s.start.slice(11, 16) <= hour && hour < s.end.slice(11, 16));
    return { hour, staffName: seg ? seg.name : null };
  });
  return { label: `${gap.outletName} · ${gap.station}`, cells };
}

export function toLeadView(
  dto: GapViewDto,
  approval: ApprovalDto | null,
  quarantine: QuarantineDto[],
  source: DataSourceKind
): LeadView {
  const g = dto.gap;
  const gap: GapView = {
    gapId: g.gap_id,
    scenarioId: g.scenario_id,
    outlet: g.outlet,
    outletName: g.outlet_name,
    station: g.station,
    start: g.start,
    end: g.end,
    reportedAt: g.reported_at,
    absentName: g.absent_staff_name ?? g.absent_staff_id,
    state: g.state,
    version: g.version,
    outcome: g.outcome,
    outcomeLabel: g.outcome ? FALLBACK_LABELS[g.outcome] ?? g.outcome : null,
    summary: g.summary,
    escalationAt: g.t_esc_locked,
    secondsToEscalation: dto.clock.seconds_to_escalation,
    costSavedCents: g.cost_saved_cents,
    workflowExecutionId: g.workflow_execution_id,
    approvalPending: g.approval_pending,
    fallbacks: (g.fallbacks ?? []).map((id) => ({ id, label: FALLBACK_LABELS[id] ?? id })),
    isTerminal: isTerminal(g.state),
    timeScale: g.time_scale,
  };
  const plan = dto.plan;
  const plans: PlanOptionView[] = (plan?.options ?? []).map((o) => ({
    rank: o.rank,
    segments: o.segments.map(segment),
    isSplit: o.segments.length > 1,
    isBorrow: o.is_cross_outlet_borrow,
    totalCents: o.cost_breakdown.total_cents,
    overtimeCents: o.overtime_cost_cents,
    savesVsNaiveCents: o.saves_vs_naive_cents,
    travelMin: o.travel_min,
    arrival: o.arrival,
    passedChecks: o.segments.flatMap((s) =>
      s.rules_checked
        .filter((r) => r.status === 'ok' && (r.kind === 'hard' || r.kind === 'data_gate'))
        .map((r) => ({
          ruleId: r.rule_id,
          title: r.title,
          kind: r.kind,
          kindLabel: KIND_LABELS[r.kind],
          status: r.status,
          message: r.message,
          sourceUrl: r.source_url,
          staffName: s.display_name,
        }))
    ),
  }));
  const rejected: RejectedView[] = (plan?.rejected ?? []).flatMap((r) =>
    r.rules.map((rule) => ({
      key: `${r.staff_id}:${rule.rule_id}`,
      staffId: r.staff_id,
      name: r.display_name,
      homeOutlet: r.home_outlet,
      ruleId: rule.rule_id,
      title: rule.title,
      kind: rule.kind,
      kindLabel: KIND_LABELS[rule.kind],
      message: rule.message,
      sourceUrl: rule.source_url,
      publisher: rule.publisher,
      section: rule.section,
    }))
  );
  const committed = dto.committed
    ? {
        segments: dto.committed.segments.map((s) => {
          const fromPlan = plans.flatMap((p) => p.segments).find(
            (x) => x.staffId === s.staff_id && x.start === s.start && x.end === s.end
          );
          return (
            fromPlan ?? {
              staffId: s.staff_id,
              name: s.display_name,
              homeOutlet: '',
              start: s.start,
              end: s.end,
              breaks: [],
              travelMin: 0,
              arrival: '',
            }
          );
        }),
        totalCents: dto.committed.cost_breakdown.total_cents,
        overtimeCents:
          dto.committed.cost_breakdown.overtime_cents + dto.committed.cost_breakdown.rest_day_cents,
      }
    : null;
  const offers: OfferView[] = dto.offers.map((o, i) => ({
    offerId: o.offer_id,
    seq: i + 1,
    staffId: o.staff_id,
    staffName: o.display_name ?? o.staff_id,
    start: o.start,
    end: o.end,
    sentAt: o.sent_at,
    windowS: o.window_s,
    status: o.status,
    statusLabel: OFFER_STATUS_LABELS[o.status] ?? o.status,
    round: o.fanout_group,
    lateReply: o.late_reply,
  }));
  const shown = committed?.segments ?? plans[0]?.segments ?? [];
  return {
    source,
    now: dto.clock.now,
    gap,
    plans,
    naive: plan?.naive_first_pick
      ? {
          name: plan.naive_first_pick.display_name,
          overtimeCents: plan.naive_first_pick.overtime_cents,
          blockingRuleIds: plan.naive_first_pick.blocking_rule_ids,
        }
      : null,
    rejected,
    offers,
    committed,
    approval: approval
      ? { nonce: approval.nonce, readback: approval.readback_text, planId: approval.plan_id }
      : null,
    quarantine: quarantine.map((q) => ({
      id: q.quarantine_id,
      staffName: q.display_name ?? q.staff_id,
      guardLabels: q.guard_labels,
      guardImpl: q.guard_impl,
      redactedText: q.redacted_text,
    })),
    roster: roster(gap, shown),
  };
}

export interface TraceView {
  chainOk: boolean;
  chainErrors: string[];
  events: Array<{
    seq: number;
    type: string;
    from: string;
    to: string;
    actor: string;
    ts: string;
    ruleIds: string[];
    modelIds: string[];
    hash: string;
    prevHash: string;
    payloadSummary: string;
  }>;
}

export function toTraceView(dto: EventsViewDto): TraceView {
  return {
    chainOk: dto.chain.ok,
    chainErrors: dto.chain.errors,
    events: dto.events.map((e) => ({
      seq: e.seq,
      type: e.type,
      from: e.from_state ?? '(none)',
      to: e.to_state,
      actor: e.actor,
      ts: e.ts,
      ruleIds: e.rule_ids,
      modelIds: e.model_ids,
      hash: e.hash,
      prevHash: e.prev_hash,
      payloadSummary: Object.entries(e.payload)
        .filter(([, v]) => typeof v !== 'object' || v === null)
        .map(([k, v]) => `${k}: ${String(v)}`)
        .join(' · '),
    })),
  };
}
