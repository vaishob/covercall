import {
  SCENARIO_MAP,
  type ScenarioKey,
  type ScenarioStateBundle,
} from '../mocks/state.ts';
import type {
  CoverCallEvalsReadModel,
  GapDoc,
  GapEventDoc,
  OutletDoc,
  PlanDoc,
  QuarantineDoc,
  StaffDoc,
} from './types.ts';

export type UnsubscribeFn = () => void;

export interface DataSource {
  readonly isMock: boolean;
  readonly sourceName: 'MockDataSource' | 'FirestoreDataSource';

  subscribeScenarioBundle(
    scenarioKey: Exclude<ScenarioKey, 'empty'>,
    onUpdate: (bundle: ScenarioStateBundle) => void
  ): UnsubscribeFn;

  subscribeGap(
    gapId: string,
    onUpdate: (gap: GapDoc | null) => void
  ): UnsubscribeFn;

  subscribeGapEvents(
    gapId: string,
    onUpdate: (events: GapEventDoc[], chainVerified: boolean | null) => void
  ): UnsubscribeFn;

  subscribePlan(
    planId: string,
    onUpdate: (plan: PlanDoc | null) => void
  ): UnsubscribeFn;

  subscribeQuarantine(
    gapId: string,
    onUpdate: (items: QuarantineDoc[]) => void
  ): UnsubscribeFn;

  getOutlets(): Promise<OutletDoc[]>;
  getStaff(outletId?: string): Promise<StaffDoc[]>;
  getEvalsReadModel(): Promise<CoverCallEvalsReadModel>;
}

const P0_METRICS_LIST = [
  'rule_violations',
  'solver_validator_disagreements',
  'unapproved_outbound',
  'injection_executed',
  'pii_leak',
  'outcome_missing',
  'escalation_late',
  'nondeterminism',
];

const P1_METRICS_LIST = [
  'overtime_saved_sgd',
  'cost_gap_vs_optimum',
  'time_to_fill_min',
  'parse_accuracy',
  'guard_precision_recall',
  'voice_slot_accuracy',
];

const P2_METRICS_LIST = ['message_quality', 'latency_p95'];

const LANGUAGE_SLICES = [
  'plain English',
  'Singlish',
  'Malay-mixed',
  'Mandarin- or Hokkien-mixed',
  'Tamil-mixed',
  'Gen Z',
  'ambiguous',
];

/**
 * MockDataSource returns the decoupled UI mocks with all values flagged `isMock: true`
 * and `/evals` returning `"No eval run yet"` (`value: null`) rather than invented metrics.
 */
export class MockDataSource implements DataSource {
  public readonly isMock = true;
  public readonly sourceName = 'MockDataSource' as const;

  subscribeScenarioBundle(
    scenarioKey: Exclude<ScenarioKey, 'empty'>,
    onUpdate: (bundle: ScenarioStateBundle) => void
  ): UnsubscribeFn {
    const bundle = SCENARIO_MAP[scenarioKey] ?? SCENARIO_MAP.s017;
    onUpdate({
      ...bundle,
      isMock: true,
      chainVerified: null,
    });
    return () => {};
  }

  subscribeGap(
    gapId: string,
    onUpdate: (gap: GapDoc | null) => void
  ): UnsubscribeFn {
    const match =
      Object.values(SCENARIO_MAP).find((b) => b.gap.id === gapId) ?? SCENARIO_MAP.s017;
    onUpdate({
      id: match.gap.id,
      outlet: match.gap.outlet,
      station: match.gap.station,
      start: match.gap.start,
      end: match.gap.end,
      absent_staff_id: match.gap.absent_staff_id,
      state: match.gap.state === 'EMPTY' ? 'REPORTED' : match.gap.state,
      version: match.gap.version,
      plan_id: match.gap.plan_id,
      outcome: match.gap.state === 'FILLED' ? 'filled' : null,
      cost_saved_sgd: match.gap.cost_saved_sgd,
      workflow_execution_id: match.gap.workflow_execution_id,
      must_fill_by: match.gap.must_fill_by,
      synthetic: true,
    });
    return () => {};
  }

  subscribeGapEvents(
    gapId: string,
    onUpdate: (events: GapEventDoc[], chainVerified: boolean | null) => void
  ): UnsubscribeFn {
    const match =
      Object.values(SCENARIO_MAP).find((b) => b.gap.id === gapId) ?? SCENARIO_MAP.s017;
    const events: GapEventDoc[] = match.traceEvents.map((ev) => ({
      seq: ev.seq,
      type: ev.type,
      from_state: ev.from_state,
      to_state: ev.to_state,
      actor: ev.actor,
      model_ids: ev.model_ids,
      rule_ids: ev.rule_ids,
      trace_id: ev.trace_id,
      payload: { summary: ev.payload_summary, mock: true },
      prev_hash: ev.prev_hash,
      hash: ev.hash,
      ts: ev.ts,
      chain_verified: null,
    }));
    // Never compute chainVerified as true in mock mode (§Step 4)
    onUpdate(events, null);
    return () => {};
  }

  subscribePlan(
    planId: string,
    onUpdate: (plan: PlanDoc | null) => void
  ): UnsubscribeFn {
    const b = SCENARIO_MAP.s017;
    onUpdate({
      id: planId,
      gap_id: b.gap.id,
      candidates: b.candidates.map((c) => ({
        staff_id: c.staff_id,
        segments: c.segments.map((s) => ({ start: s.start, end: s.end })),
        cost_breakdown: {
          incremental_cost_sgd: c.incremental_cost_sgd,
          saves_vs_overtime_sgd: c.saves_vs_overtime_sgd,
        },
        travel_min: c.travel_min,
        arrival: c.arrival_iso,
        rules_checked: c.rules_checked.map((r) => r.ruleId),
        rejected_rules: [],
      })),
      solver_params: { seed: 17, mock: true },
      validator_version: 'mock-not-executed',
      synthetic: true,
    });
    return () => {};
  }

  subscribeQuarantine(
    gapId: string,
    onUpdate: (items: QuarantineDoc[]) => void
  ): UnsubscribeFn {
    if (gapId.includes('adversarial')) {
      const q = SCENARIO_MAP.adversarial.quarantinedMessage;
      if (q) {
        onUpdate([
          {
            id: q.id,
            gap_id: gapId,
            staff_id: q.staff_id,
            guard_labels: ['injection', 'pii'],
            guard_impl: null,
            redacted_text: q.redacted_text,
            synthetic: true,
          },
        ]);
        return () => {};
      }
    }
    onUpdate([]);
    return () => {};
  }

  async getOutlets(): Promise<OutletDoc[]> {
    return [
      {
        id: 'bugis',
        name: 'Bugis Espresso Bar',
        area: 'Bugis',
        lat: 1.3006,
        lng: 103.8555,
        opening_hours: { open: '07:00', close: '22:00' },
        stations: [{ station: 'barista', skill: 'barista', food_handling: true, min_count: 1 }],
        keyholders: ['stf_011', 'stf_014', 'stf_022'],
        synthetic: true,
      },
      {
        id: 'tampines',
        name: 'Tampines Hub Café',
        area: 'Tampines',
        lat: 1.3526,
        lng: 103.9446,
        opening_hours: { open: '07:00', close: '22:00' },
        stations: [{ station: 'barista', skill: 'barista', food_handling: true, min_count: 1 }],
        keyholders: ['stf_014'],
        synthetic: true,
      },
      {
        id: 'jurong_east',
        name: 'Jurong East Roastery',
        area: 'Jurong East',
        lat: 1.3329,
        lng: 103.7436,
        opening_hours: { open: '07:00', close: '22:00' },
        stations: [{ station: 'barista', skill: 'barista', food_handling: true, min_count: 1 }],
        keyholders: ['stf_019'],
        synthetic: true,
      },
    ];
  }

  async getStaff(): Promise<StaffDoc[]> {
    return SCENARIO_MAP.s017.candidates.map((c) => ({
      id: c.staff_id,
      display_name: c.display_name,
      age: 22,
      is_student: c.contract_type === 'part_time',
      home_area: c.home_outlet,
      home_outlet: c.home_outlet.toLowerCase().replace(' ', '_'),
      contract_type: c.contract_type,
      employee_class: c.employee_class,
      weekly_contract_hours: c.contract_type === 'full_time' ? 44 : 20,
      normal_daily_hours: 8,
      skills: ['barista'],
      fsc_l1_passed_on: '2024-03-12',
      keyholder: true,
      channel: c.channel,
      synthetic: true,
    }));
  }

  async getEvalsReadModel(): Promise<CoverCallEvalsReadModel> {
    // In mock mode every number shows null -> rendered as "No eval run yet" rather than invented values (§Step 4)
    return {
      isMock: true,
      latestRun: null,
      buildHistory: [],
      p0Metrics: P0_METRICS_LIST.map((m) => ({
        run_id: 'mock',
        metric: m,
        severity: 'P0',
        slice: 'all',
        value: null,
        threshold: 0,
        passed: null,
      })),
      p1Metrics: P1_METRICS_LIST.map((m) => ({
        run_id: 'mock',
        metric: m,
        severity: 'P1',
        slice: 'all',
        value: null,
        threshold: null,
        change_since_last: null,
        passed: null,
      })),
      p2Metrics: P2_METRICS_LIST.map((m) => ({
        run_id: 'mock',
        metric: m,
        severity: 'P2',
        slice: 'all',
        value: null,
        threshold: null,
        passed: null,
      })),
      sliceTables: {
        parseAccuracyBySlice: LANGUAGE_SLICES.map((s) => ({
          run_id: 'mock',
          metric: 'parse_accuracy',
          severity: 'P1',
          slice: s,
          value: null,
          threshold: null,
          passed: null,
        })),
        guardComparisonBySlice: LANGUAGE_SLICES.map((s) => ({
          slice: s,
          label: 'injection',
          gemmaPrecision: null,
          gemmaRecall: null,
          geminiBaselinePrecision: null,
          geminiBaselineRecall: null,
        })),
      },
      headlineVsBaseline: {
        overtimeSavedMedianSgd: null,
        overtimeSavedTotalSgd: null,
        coverCallViolations: null,
        baselineViolations: null,
        coverCallTimeToFillMin: null,
        baselineTimeToFillMin: null,
      },
      cases: [],
    };
  }
}

export interface FirestoreEnvConfig {
  projectId: string;
  apiKey?: string;
  appId?: string;
  databaseId?: string;
  apiBaseUrl?: string;
}

/**
 * FirestoreDataSource connects read-only listeners to the §8.1 Firestore collections
 * configured via `import.meta.env.VITE_FIREBASE_*` (no secrets committed).
 */
export class FirestoreDataSource implements DataSource {
  public readonly isMock = false;
  public readonly sourceName = 'FirestoreDataSource' as const;
  private readonly config: FirestoreEnvConfig;
  private readonly fallbackMock = new MockDataSource();

  constructor(config: FirestoreEnvConfig) {
    this.config = config;
  }

  subscribeScenarioBundle(
    scenarioKey: Exclude<ScenarioKey, 'empty'>,
    onUpdate: (bundle: ScenarioStateBundle) => void
  ): UnsubscribeFn {
    let active = true;
    const baseUrl = this.config.apiBaseUrl;
    if (baseUrl) {
      fetch(`${baseUrl.replace(/\/$/, '')}/scenarios/${scenarioKey}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (active && data) {
            onUpdate({ ...data, isMock: false });
          }
        })
        .catch(() => {
          if (active) {
            this.fallbackMock.subscribeScenarioBundle(scenarioKey, onUpdate);
          }
        });
    } else {
      this.fallbackMock.subscribeScenarioBundle(scenarioKey, onUpdate);
    }
    return () => {
      active = false;
    };
  }

  subscribeGap(
    gapId: string,
    onUpdate: (gap: GapDoc | null) => void
  ): UnsubscribeFn {
    let active = true;
    const baseUrl = this.config.apiBaseUrl;
    if (baseUrl) {
      fetch(`${baseUrl.replace(/\/$/, '')}/gaps/${encodeURIComponent(gapId)}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data: GapDoc | null) => {
          if (active) onUpdate(data);
        })
        .catch(() => {
          if (active) onUpdate(null);
        });
    }
    return () => {
      active = false;
    };
  }

  subscribeGapEvents(
    gapId: string,
    onUpdate: (events: GapEventDoc[], chainVerified: boolean | null) => void
  ): UnsubscribeFn {
    let active = true;
    const baseUrl = this.config.apiBaseUrl;
    if (baseUrl) {
      fetch(`${baseUrl.replace(/\/$/, '')}/gaps/${encodeURIComponent(gapId)}/events`)
        .then((res) => (res.ok ? res.json() : null))
        .then(
          (
            data: { events: GapEventDoc[]; chain_verified: boolean | null } | null
          ) => {
            if (active && data) {
              onUpdate(data.events ?? [], data.chain_verified ?? null);
            }
          }
        )
        .catch(() => {
          if (active) onUpdate([], null);
        });
    }
    return () => {
      active = false;
    };
  }

  subscribePlan(
    planId: string,
    onUpdate: (plan: PlanDoc | null) => void
  ): UnsubscribeFn {
    let active = true;
    const baseUrl = this.config.apiBaseUrl;
    if (baseUrl) {
      fetch(`${baseUrl.replace(/\/$/, '')}/plans/${encodeURIComponent(planId)}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data: PlanDoc | null) => {
          if (active) onUpdate(data);
        })
        .catch(() => {
          if (active) onUpdate(null);
        });
    }
    return () => {
      active = false;
    };
  }

  subscribeQuarantine(
    gapId: string,
    onUpdate: (items: QuarantineDoc[]) => void
  ): UnsubscribeFn {
    let active = true;
    const baseUrl = this.config.apiBaseUrl;
    if (baseUrl) {
      fetch(`${baseUrl.replace(/\/$/, '')}/quarantine?gap_id=${encodeURIComponent(gapId)}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data: QuarantineDoc[] | null) => {
          if (active && Array.isArray(data)) onUpdate(data);
        })
        .catch(() => {
          if (active) onUpdate([]);
        });
    }
    return () => {
      active = false;
    };
  }

  async getOutlets(): Promise<OutletDoc[]> {
    return this.fallbackMock.getOutlets();
  }

  async getStaff(): Promise<StaffDoc[]> {
    return this.fallbackMock.getStaff();
  }

  async getEvalsReadModel(): Promise<CoverCallEvalsReadModel> {
    const baseUrl = this.config.apiBaseUrl;
    if (baseUrl) {
      try {
        const res = await fetch(`${baseUrl.replace(/\/$/, '')}/evals`);
        if (res.ok) {
          const data = (await res.json()) as CoverCallEvalsReadModel;
          return { ...data, isMock: false };
        }
      } catch {
        // Fall through to no-eval-run model
      }
    }
    return this.fallbackMock.getEvalsReadModel();
  }
}

export function createDataSourceFromEnv(env?: Record<string, string | undefined>): DataSource {
  const e =
    env ??
    ((typeof import.meta !== 'undefined' && (import.meta as unknown as { env?: Record<string, string | undefined> }).env) ||
      {});
  const apiBaseUrl = e.VITE_API_BASE_URL?.trim();
  const projectId = e.VITE_FIREBASE_PROJECT_ID?.trim();

  if (apiBaseUrl && projectId) {
    return new FirestoreDataSource({
      projectId,
      apiKey: e.VITE_FIREBASE_API_KEY,
      appId: e.VITE_FIREBASE_APP_ID,
      databaseId: e.VITE_FIRESTORE_DATABASE_ID || '(default)',
      apiBaseUrl,
    });
  }

  return new MockDataSource();
}
