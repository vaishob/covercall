/**
 * Where the lead screen's data comes from (docs/decisions/0015, 0016):
 * - LiveSource: the `api` read routes, polled every 2 s while a gap is active, stopping once the
 *   gap reaches a terminal state. Errors go to the caller (shown as errors, no mock fallback).
 * - ReplaySource: used only when VITE_API_BASE_URL is unset. It plays back real responses that
 *   were recorded from the local cascade (web/src/data/__fixtures__, captured by
 *   evals/runners/capture_fixtures.py). Always badged "Recorded replay"; taps are disabled.
 */
import type {
  ApprovalDto,
  EvalsDto,
  EventsViewDto,
  GapViewDto,
  QuarantineDto,
  ScenarioDto,
  StatusDto,
} from './backendTypes.ts';
import { ApiClient } from './apiClient.ts';
import type { DataSourceKind, LeadView, TraceView } from './viewModel.ts';
import { toLeadView, toTraceView } from './viewModel.ts';

export type Unsubscribe = () => void;

export interface LeadSource {
  readonly kind: DataSourceKind;
  readonly canAct: boolean;
  listScenarios(): Promise<ScenarioDto[]>;
  start(scenarioId: string): Promise<string>;
  watch(handle: string, onView: (v: LeadView) => void, onError: (e: Error) => void): Unsubscribe;
  approve(handle: string, nonce: string, decision: 'approve' | 'reject', transcript?: string): Promise<void>;
  chooseFallback(handle: string, option: string): Promise<void>;
  cancel(handle: string): Promise<void>;
  trace(handle: string): Promise<TraceView>;
  evals(): Promise<EvalsDto>;
  status(): Promise<StatusDto>;
}

export class LiveSource implements LeadSource {
  readonly kind = 'live' as const;
  readonly canAct = true;
  readonly api: ApiClient;
  private readonly intervalMs: number;

  constructor(api: ApiClient, intervalMs = 2000) {
    this.api = api;
    this.intervalMs = intervalMs;
  }

  listScenarios(): Promise<ScenarioDto[]> {
    return this.api.listScenarios();
  }

  async start(scenarioId: string): Promise<string> {
    const res = await this.api.startScenario(scenarioId);
    if (res.status !== 'created') throw new Error(res.question);
    return res.gap_id;
  }

  /** Fetch one consistent snapshot of the lead view. */
  async snapshot(gapId: string): Promise<LeadView> {
    const dto = await this.api.getGap(gapId);
    const [approval, quarantine] = await Promise.all([
      dto.gap.approval_pending ? this.api.getApproval(gapId) : Promise.resolve(null),
      this.api.getQuarantine(gapId),
    ]);
    return toLeadView(dto, approval, quarantine, 'live');
  }

  watch(gapId: string, onView: (v: LeadView) => void, onError: (e: Error) => void): Unsubscribe {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const tick = async (): Promise<void> => {
      if (!active) return;
      try {
        const view = await this.snapshot(gapId);
        if (!active) return;
        onView(view);
        if (view.gap.isTerminal) return; // stop polling on terminal states
      } catch (err) {
        if (active) onError(err as Error);
      }
      if (active) timer = setTimeout(() => void tick(), this.intervalMs);
    };
    void tick();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }

  async approve(gapId: string, nonce: string, decision: 'approve' | 'reject', transcript?: string): Promise<void> {
    await this.api.submitApproval({
      gap_id: gapId,
      nonce,
      decision,
      channel: transcript === undefined ? 'tap' : 'voice',
      transcript: transcript ?? '',
    });
  }

  async chooseFallback(gapId: string, option: string): Promise<void> {
    await this.api.chooseFallback(gapId, option);
  }

  async cancel(gapId: string): Promise<void> {
    await this.api.cancelGap(gapId);
  }

  async trace(gapId: string): Promise<TraceView> {
    return toTraceView(await this.api.getEvents(gapId));
  }

  evals(): Promise<EvalsDto> {
    return this.api.getEvals();
  }

  status(): Promise<StatusDto> {
    return this.api.getStatus();
  }
}

export interface ReplayFixture {
  scenario_id: string;
  outcome: string;
  status: StatusDto;
  scenarios: ScenarioDto[];
  evals: EvalsDto;
  snapshots: Array<{ after_step: string; gap: GapViewDto; approval: ApprovalDto | null; quarantine: QuarantineDto[] }>;
  events: EventsViewDto;
}

export type FixtureLoader = () => Promise<ReplayFixture[]>;

/** Loads the recorded fixtures lazily (their own chunk), so the live bundle stays small. */
export const loadRecordedFixtures: FixtureLoader = async () => {
  const [a, b] = await Promise.all([import('./__fixtures__/s017.json'), import('./__fixtures__/s002.json')]);
  return [a.default as unknown as ReplayFixture, b.default as unknown as ReplayFixture];
};

export class ReplaySource implements LeadSource {
  readonly kind = 'replay' as const;
  readonly canAct = false;
  private readonly loader: FixtureLoader;
  private readonly stepMs: number;
  private fixtures: Promise<ReplayFixture[]> | null = null;

  constructor(loader: FixtureLoader = loadRecordedFixtures, stepMs = 1200) {
    this.loader = loader;
    this.stepMs = stepMs;
  }

  private all(): Promise<ReplayFixture[]> {
    this.fixtures ??= this.loader();
    return this.fixtures;
  }

  private async fixture(handle: string): Promise<ReplayFixture> {
    const found = (await this.all()).find((f) => `replay:${f.scenario_id}` === handle);
    if (!found) throw new Error(`No recorded replay for ${handle}`);
    return found;
  }

  async listScenarios(): Promise<ScenarioDto[]> {
    return (await this.all()).flatMap((f) => f.scenarios);
  }

  async start(scenarioId: string): Promise<string> {
    await this.fixture(`replay:${scenarioId}`);
    return `replay:${scenarioId}`;
  }

  watch(handle: string, onView: (v: LeadView) => void, onError: (e: Error) => void): Unsubscribe {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    void this.fixture(handle)
      .then((fx) => {
        let i = 0;
        const next = (): void => {
          if (!active) return;
          const s = fx.snapshots[i];
          onView(toLeadView(s.gap, s.approval, s.quarantine, 'replay'));
          i += 1;
          if (i < fx.snapshots.length) timer = setTimeout(next, this.stepMs);
        };
        next();
      })
      .catch((err: Error) => onError(err));
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }

  private refuse(): Promise<void> {
    return Promise.reject(new Error('Recorded replay: actions are disabled. Set VITE_API_BASE_URL to run live.'));
  }

  approve(): Promise<void> {
    return this.refuse();
  }

  chooseFallback(): Promise<void> {
    return this.refuse();
  }

  cancel(): Promise<void> {
    return this.refuse();
  }

  async trace(handle: string): Promise<TraceView> {
    return toTraceView((await this.fixture(handle)).events);
  }

  async evals(): Promise<EvalsDto> {
    return (await this.all())[0].evals;
  }

  async status(): Promise<StatusDto> {
    return (await this.all())[0].status;
  }
}

export function createSource(baseUrl: string | null): LeadSource {
  return baseUrl ? new LiveSource(new ApiClient(baseUrl)) : new ReplaySource();
}
