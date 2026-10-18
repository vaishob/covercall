import type {
  ApprovalDto,
  CreateGapResponse,
  EvalsDto,
  EventsViewDto,
  GapViewDto,
  QuarantineDto,
  ScenarioDto,
  StatusDto,
} from './backendTypes.ts';

export class ApiError extends Error {
  readonly status: number;
  readonly path: string;

  constructor(path: string, status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.path = path;
  }
}

export interface ReportAbsencePayload {
  outlet: string;
  station: string;
  shift_start: string;
  staff_name?: string;
  text?: string;
}

export interface SubmitApprovalPayload {
  gap_id: string;
  nonce: string;
  decision: 'approve' | 'reject';
  channel: 'voice' | 'tap';
  transcript?: string;
}

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

/**
 * Thin client for the `api` routes (services/api/app/main.py). Paths and payloads match the
 * backend exactly. Every non-2xx answer becomes an ApiError carrying the server's message:
 * errors are shown as errors, never replaced by mock data.
 */
export class ApiClient {
  readonly baseUrl: string;
  private readonly fetchImpl: FetchLike;

  constructor(baseUrl: string, fetchImpl?: FetchLike) {
    const cleaned = baseUrl.trim().replace(/\/$/, '');
    if (!cleaned) throw new Error('ApiClient needs a base URL');
    this.baseUrl = cleaned;
    this.fetchImpl = fetchImpl ?? ((input, init) => fetch(input, init));
  }

  private async request<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
    const init: RequestInit = { method };
    if (body !== undefined) {
      init.headers = { 'Content-Type': 'application/json' };
      init.body = JSON.stringify(body);
    }
    let res: Response;
    try {
      res = await this.fetchImpl(`${this.baseUrl}${path}`, init);
    } catch (err) {
      throw new ApiError(path, 0, `Cannot reach the CoverCall API (${(err as Error).message}).`);
    }
    if (!res.ok) {
      let message = `${method} ${path} failed with HTTP ${res.status}`;
      try {
        const data = (await res.json()) as { error?: string; message?: string; detail?: string };
        message = data.message ?? data.error ?? data.detail ?? message;
      } catch {
        // keep the generic message
      }
      throw new ApiError(path, res.status, message);
    }
    return (await res.json()) as T;
  }

  getStatus(): Promise<StatusDto> {
    return this.request('GET', '/status');
  }

  listScenarios(): Promise<ScenarioDto[]> {
    return this.request('GET', '/scenarios');
  }

  startScenario(scenarioId: string): Promise<CreateGapResponse> {
    return this.request('POST', '/gaps', { scenario_id: scenarioId });
  }

  /** Voice `report_absence`: the server resolves the name and end time, or asks a question. */
  reportAbsence(payload: ReportAbsencePayload): Promise<CreateGapResponse> {
    return this.request('POST', '/gaps', payload);
  }

  getGap(gapId: string): Promise<GapViewDto> {
    return this.request('GET', `/gaps/${encodeURIComponent(gapId)}`);
  }

  getEvents(gapId: string): Promise<EventsViewDto> {
    return this.request('GET', `/gaps/${encodeURIComponent(gapId)}/events`);
  }

  getQuarantine(gapId: string): Promise<QuarantineDto[]> {
    return this.request('GET', `/gaps/${encodeURIComponent(gapId)}/quarantine`);
  }

  /** The pending read-back and nonce, or null when no approval is pending ({pending: false}). */
  async getApproval(gapId: string): Promise<ApprovalDto | null> {
    const data = await this.request<ApprovalDto | { gap_id: string; pending: false }>(
      'GET',
      `/gaps/${encodeURIComponent(gapId)}/approval`
    );
    return data.pending ? data : null;
  }

  submitApproval(payload: SubmitApprovalPayload): Promise<{ approval_id: string; decision: string }> {
    if (!payload.nonce) {
      return Promise.reject(new Error('approve requires the server-issued nonce (§7.2)'));
    }
    return this.request('POST', '/approvals', payload);
  }

  chooseFallback(gapId: string, option: string): Promise<{ status: string }> {
    return this.request('POST', '/fallbacks', { gap_id: gapId, option });
  }

  cancelGap(gapId: string): Promise<{ status: string; waits_signalled: number }> {
    return this.request('POST', `/gaps/${encodeURIComponent(gapId)}/cancel`);
  }

  getEvals(): Promise<EvalsDto> {
    return this.request('GET', '/evals');
  }

  /** Slice 4. The backend answers 501 with an explanation until voice exists. */
  mintLiveToken(): Promise<{ token: string; expires_at: string; model_id: string; api_version: 'v1beta' }> {
    return this.request('POST', '/live/token');
  }
}

export function apiBaseUrlFromEnv(env?: Record<string, string | undefined>): string | null {
  const e =
    env ??
    ((typeof import.meta !== 'undefined' &&
      (import.meta as unknown as { env?: Record<string, string | undefined> }).env) ||
      {});
  const url = e.VITE_API_BASE_URL?.trim();
  return url ? url : null;
}
