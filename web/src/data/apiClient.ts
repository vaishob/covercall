import type { ApprovalDoc, GapDoc } from './types.ts';

export interface CreateGapPayload {
  outlet: string;
  shift_start: string;
  station: string;
  staff_name?: string;
  scenario_id?: string;
}

export interface SubmitApprovalPayload {
  gap_id: string;
  plan_id: string;
  decision: 'approved' | 'rejected';
  approval_nonce: string;
  transcript?: string;
  channel: 'voice' | 'tap';
}

export interface ChooseFallbackPayload {
  gap_id: string;
  option: string;
}

export interface LiveTokenResponse {
  ephemeral_token: string;
  expires_at: string;
  model_id: string;
  api_version: 'v1alpha';
}

export interface ApiStatusResponse {
  status: 'ok' | 'mock_mode' | 'degraded';
  guard_impl: string | null;
  live_model_id: string | null;
  mock_mode: boolean;
}

/**
 * ApiClient wraps the `api` Cloud Run service endpoints (§4.1, §7.2):
 * - POST /gaps
 * - POST /approvals
 * - POST /fallbacks
 * - POST /gaps/:gapId/cancel
 * - GET /gaps/:gapId
 * - GET /status
 * - POST /voice/token (ephemeral token minting for Gemini Live API v1alpha)
 *
 * When `VITE_API_BASE_URL` is unset, `isMockMode` is `true` and methods return honest mock-mode responses.
 */
export class ApiClient {
  public readonly baseUrl: string | null;
  public readonly isMockMode: boolean;

  constructor(baseUrl?: string | null) {
    const cleaned = baseUrl?.trim() || null;
    this.baseUrl = cleaned ? cleaned.replace(/\/$/, '') : null;
    this.isMockMode = !this.baseUrl;
  }

  async getStatus(): Promise<ApiStatusResponse> {
    if (!this.baseUrl) {
      return {
        status: 'mock_mode',
        guard_impl: null,
        live_model_id: null,
        mock_mode: true,
      };
    }

    const res = await fetch(`${this.baseUrl}/status`);
    if (!res.ok) {
      throw new Error(`GET /status failed with HTTP ${res.status}`);
    }
    return (await res.json()) as ApiStatusResponse;
  }

  async createGap(payload: CreateGapPayload): Promise<{ gap_id: string; mock: boolean; gap?: GapDoc }> {
    if (!this.baseUrl) {
      return {
        gap_id: `gap_mock_${Date.now()}`,
        mock: true,
      };
    }

    const res = await fetch(`${this.baseUrl}/gaps`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`POST /gaps failed with HTTP ${res.status}`);
    }
    return (await res.json()) as { gap_id: string; mock: boolean; gap?: GapDoc };
  }

  async submitApproval(
    payload: SubmitApprovalPayload
  ): Promise<{ approval_id: string; mock: boolean; approval?: ApprovalDoc }> {
    if (!payload.approval_nonce) {
      throw new Error('approve requires a server-issued approval_nonce (§7.2)');
    }
    if (!this.baseUrl) {
      return {
        approval_id: `appr_mock_${Date.now()}`,
        mock: true,
      };
    }

    const res = await fetch(`${this.baseUrl}/approvals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`POST /approvals failed with HTTP ${res.status}`);
    }
    return (await res.json()) as { approval_id: string; mock: boolean; approval?: ApprovalDoc };
  }

  async chooseFallback(payload: ChooseFallbackPayload): Promise<{ ok: boolean; mock: boolean }> {
    if (!this.baseUrl) {
      return { ok: true, mock: true };
    }
    const res = await fetch(`${this.baseUrl}/gaps/${encodeURIComponent(payload.gap_id)}/fallback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`POST /gaps/${payload.gap_id}/fallback failed with HTTP ${res.status}`);
    }
    return { ok: true, mock: false };
  }

  async getGapStatus(gapId: string): Promise<{ gap_id: string; state: string; mock: boolean }> {
    if (!this.baseUrl) {
      return { gap_id: gapId, state: 'SOLVED', mock: true };
    }
    const res = await fetch(`${this.baseUrl}/gaps/${encodeURIComponent(gapId)}`);
    if (!res.ok) {
      throw new Error(`GET /gaps/${gapId} failed with HTTP ${res.status}`);
    }
    return (await res.json()) as { gap_id: string; state: string; mock: boolean };
  }

  async cancelGap(gapId: string): Promise<{ gap_id: string; state: 'CANCELLED'; mock: boolean }> {
    if (!this.baseUrl) {
      return { gap_id: gapId, state: 'CANCELLED', mock: true };
    }
    const res = await fetch(`${this.baseUrl}/gaps/${encodeURIComponent(gapId)}/cancel`, {
      method: 'POST',
    });
    if (!res.ok) {
      throw new Error(`POST /gaps/${gapId}/cancel failed with HTTP ${res.status}`);
    }
    return (await res.json()) as { gap_id: string; state: 'CANCELLED'; mock: boolean };
  }

  /**
   * Mints a single-use ephemeral token for Gemini Live API (v1alpha) from `api` (§7.2).
   * Never uses a client-side API key. When `baseUrl` is unset, throws an error so the
   * VoiceProvider falls back cleanly to text mode without faking a voice session.
   */
  async mintLiveEphemeralToken(): Promise<LiveTokenResponse> {
    if (!this.baseUrl) {
      throw new Error(
        'Voice API unavailable in mock mode (VITE_API_BASE_URL is not configured). Falling back to text input.'
      );
    }

    const res = await fetch(`${this.baseUrl}/voice/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) {
      throw new Error(`POST /voice/token failed with HTTP ${res.status}`);
    }
    return (await res.json()) as LiveTokenResponse;
  }
}

export function createApiClientFromEnv(env?: Record<string, string | undefined>): ApiClient {
  const e =
    env ??
    ((typeof import.meta !== 'undefined' && (import.meta as unknown as { env?: Record<string, string | undefined> }).env) ||
      {});
  return new ApiClient(e.VITE_API_BASE_URL);
}
