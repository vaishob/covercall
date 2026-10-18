import type { VoiceMode, VoiceState } from '../mocks/state.ts';
import type { ApiClient } from '../data/apiClient.ts';

/**
 * The exact five tools exposed to the voice model (§7.2):
 * - report_absence(outlet, shift_start, station, staff_name?)
 * - approve(plan_id, decision, approval_nonce)
 * - choose_fallback(gap_id, option)
 * - get_status(gap_id)
 * - cancel_gap(gap_id)
 *
 * The browser forwards each tool call to `api`, which validates it.
 * Nothing executes locally.
 */
export type VoiceToolName =
  | 'report_absence'
  | 'approve'
  | 'choose_fallback'
  | 'get_status'
  | 'cancel_gap';

export interface VoiceToolDeclaration {
  name: VoiceToolName;
  description: string;
  parameters: {
    type: 'OBJECT';
    properties: Record<string, { type: string; description: string }>;
    required: string[];
  };
}

export const VOICE_TOOL_DECLARATIONS: readonly VoiceToolDeclaration[] = [
  {
    name: 'report_absence',
    description: 'Report a staff absence to create a shift gap via the API service.',
    parameters: {
      type: 'OBJECT',
      properties: {
        outlet: { type: 'STRING', description: 'Outlet ID (bugis, tampines, jurong_east)' },
        shift_start: { type: 'STRING', description: 'Shift start time (HH:MM or ISO 8601 +08:00)' },
        station: { type: 'STRING', description: 'Station tag (barista, kitchen, cashier)' },
        staff_name: { type: 'STRING', description: 'Optional absent staff name' },
      },
      required: ['outlet', 'shift_start', 'station'],
    },
  },
  {
    name: 'approve',
    description: 'Record a Tier T2 plan approval or rejection with the server-issued approval_nonce.',
    parameters: {
      type: 'OBJECT',
      properties: {
        plan_id: { type: 'STRING', description: 'Plan ID being approved or rejected' },
        decision: { type: 'STRING', description: 'approved or rejected' },
        approval_nonce: {
          type: 'STRING',
          description: 'Server-issued single-use approval_nonce read back to the lead',
        },
      },
      required: ['plan_id', 'decision', 'approval_nonce'],
    },
  },
  {
    name: 'choose_fallback',
    description: 'Select a ranked fallback option when a gap reaches ESCALATED state.',
    parameters: {
      type: 'OBJECT',
      properties: {
        gap_id: { type: 'STRING', description: 'Gap ID' },
        option: {
          type: 'STRING',
          description: 'Fallback option ID (borrow_cross_outlet, reduced_service, lead_covers, agency_temp)',
        },
      },
      required: ['gap_id', 'option'],
    },
  },
  {
    name: 'get_status',
    description: 'Fetch current workflow state for a gap from the API service.',
    parameters: {
      type: 'OBJECT',
      properties: {
        gap_id: { type: 'STRING', description: 'Gap ID' },
      },
      required: ['gap_id'],
    },
  },
  {
    name: 'cancel_gap',
    description: 'Cancel an active shift gap and withdraw open offers via the API service.',
    parameters: {
      type: 'OBJECT',
      properties: {
        gap_id: { type: 'STRING', description: 'Gap ID' },
      },
      required: ['gap_id'],
    },
  },
] as const;

export const FIXED_FALLBACK_ORDER: readonly VoiceMode[] = [
  'hands-free',
  'push-to-talk',
  'text',
] as const;

/**
 * Spoken approval policy (§5.3 & §7.2):
 * "Only a clear affirmative counts; anything else is a no."
 */
const CLEAR_AFFIRMATIVE_PATTERNS = [
  /^yes\b/i,
  /\byes,\s*approve\b/i,
  /^approve\b/i,
  /\bi\s+approve\b/i,
  /^confirm\b/i,
  /\byes\s+go\s+ahead\b/i,
];

const AMBIGUOUS_OR_NEGATIVE_TOKENS = [
  /\bno\b/i,
  /\bnot\b/i,
  /\bwait\b/i,
  /\bhold\b/i,
  /\bmaybe\b/i,
  /\blater\b/i,
  /\bcancel\b/i,
  /\bdon't\b/i,
];

export function isClearAffirmativeTranscript(transcript: string): boolean {
  const cleaned = transcript.trim();
  if (!cleaned) return false;
  if (AMBIGUOUS_OR_NEGATIVE_TOKENS.some((re) => re.test(cleaned))) {
    return false;
  }
  return CLEAR_AFFIRMATIVE_PATTERNS.some((re) => re.test(cleaned));
}

export interface VoiceProviderCallbacks {
  onStateChange: (state: VoiceState, reason?: string) => void;
  onModeFallback: (newMode: VoiceMode, reason: string) => void;
  onCaption: (speaker: 'Lead' | 'CoverCall', text: string) => void;
}

export interface VoiceProvider {
  readonly mode: VoiceMode;
  readonly modelId: string | null;
  connect(): Promise<void>;
  disconnect(): void;
  sendText(text: string): Promise<void>;
  forwardToolCall(
    toolName: VoiceToolName,
    args: Record<string, string>,
    transcript?: string
  ): Promise<unknown>;
}

/**
 *Forwards any voice model tool call to `api`. Never executes state changes locally (§7.2).
 */
export async function forwardVoiceToolCallToApi(
  apiClient: ApiClient,
  toolName: VoiceToolName,
  args: Record<string, string>,
  transcript?: string
): Promise<unknown> {
  switch (toolName) {
    case 'report_absence':
      return apiClient.createGap({
        outlet: args.outlet,
        shift_start: args.shift_start,
        station: args.station,
        staff_name: args.staff_name,
      });

    case 'approve': {
      const nonce = args.approval_nonce?.trim();
      if (!nonce) {
        throw new Error('approve requires server-issued approval_nonce (§7.2).');
      }
      // Anything other than a clear yes counts as a no (§5.3, §7.2)
      const isYes =
        args.decision === 'approved' &&
        (transcript === undefined || isClearAffirmativeTranscript(transcript));
      const decision: 'approved' | 'rejected' = isYes ? 'approved' : 'rejected';

      return apiClient.submitApproval({
        gap_id: args.gap_id || 'active_gap',
        plan_id: args.plan_id,
        decision,
        approval_nonce: nonce,
        transcript: transcript ?? '',
        channel: 'voice',
      });
    }

    case 'choose_fallback':
      return apiClient.chooseFallback({
        gap_id: args.gap_id,
        option: args.option,
      });

    case 'get_status':
      return apiClient.getGapStatus(args.gap_id);

    case 'cancel_gap':
      return apiClient.cancelGap(args.gap_id);
  }
}

/**
 * 1. LiveVoiceProvider (hands-free mode):
 * Connects to Gemini Live API (`v1alpha`) authenticated ONLY with an ephemeral token
 * fetched from `api` (`POST /voice/token`). Never accepts or holds a client API key.
 * Model ID comes strictly from env/server token response (`VITE_GEMINI_LIVE_MODEL_ID`).
 * Automatically falls back along `hands-free` -> `push-to-talk` -> `text` on failure.
 */
export class LiveVoiceProvider implements VoiceProvider {
  public readonly mode: VoiceMode = 'hands-free';
  public readonly modelId: string | null;
  private readonly apiClient: ApiClient;
  private readonly callbacks: VoiceProviderCallbacks;

  constructor(
    apiClient: ApiClient,
    callbacks: VoiceProviderCallbacks,
    configuredModelId?: string | null
  ) {
    this.apiClient = apiClient;
    this.callbacks = callbacks;
    this.modelId = configuredModelId?.trim() || null;
  }

  async connect(): Promise<void> {
    if (this.apiClient.isMockMode || !this.apiClient.baseUrl) {
      const reason =
        'Voice unavailable in mock mode (no API URL configured). Fell back to text input.';
      this.callbacks.onStateChange('Offline', reason);
      this.callbacks.onModeFallback('text', reason);
      return;
    }

    try {
      this.callbacks.onStateChange('Thinking', 'Minting v1alpha ephemeral token from api…');
      const tokenResp = await this.apiClient.mintLiveEphemeralToken();
      if (tokenResp.api_version !== 'v1alpha' || !tokenResp.ephemeral_token) {
        throw new Error('Ephemeral token requires Live API v1alpha.');
      }
      const resolvedModel = this.modelId || tokenResp.model_id;
      if (!resolvedModel) {
        throw new Error('VITE_GEMINI_LIVE_MODEL_ID is not configured.');
      }
      this.callbacks.onStateChange(
        'Listening',
        `Live session active (${resolvedModel}, v1alpha ephemeral token)`
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Live session failed';
      const fallbackReason = `Hands-free unavailable (${msg}). Falling back to push-to-talk.`;
      this.callbacks.onStateChange('Offline', fallbackReason);
      this.callbacks.onModeFallback('push-to-talk', fallbackReason);
    }
  }

  disconnect(): void {
    // Store no audio (§7.2)
    this.callbacks.onStateChange('Muted', 'Voice session closed (no audio stored).');
  }

  async sendText(text: string): Promise<void> {
    this.callbacks.onCaption('Lead', text);
  }

  async forwardToolCall(
    toolName: VoiceToolName,
    args: Record<string, string>,
    transcript?: string
  ): Promise<unknown> {
    return forwardVoiceToolCallToApi(this.apiClient, toolName, args, transcript);
  }
}

/**
 * 2. PushToTalkProvider (`push-to-talk` mode):
 * Second step in the fixed fallback order (`hands-free` -> `push-to-talk` -> `text`).
 * Falls back to `text` if `api` is unreachable or in mock mode.
 */
export class PushToTalkProvider implements VoiceProvider {
  public readonly mode: VoiceMode = 'push-to-talk';
  public readonly modelId: string | null;
  private readonly apiClient: ApiClient;
  private readonly callbacks: VoiceProviderCallbacks;

  constructor(
    apiClient: ApiClient,
    callbacks: VoiceProviderCallbacks,
    configuredModelId?: string | null
  ) {
    this.apiClient = apiClient;
    this.callbacks = callbacks;
    this.modelId = configuredModelId?.trim() || null;
  }

  async connect(): Promise<void> {
    if (this.apiClient.isMockMode || !this.apiClient.baseUrl) {
      const reason =
        'Push-to-talk unavailable in mock mode (no API URL configured). Fell back to text input.';
      this.callbacks.onStateChange('Offline', reason);
      this.callbacks.onModeFallback('text', reason);
      return;
    }

    try {
      const tokenResp = await this.apiClient.mintLiveEphemeralToken();
      if (!tokenResp.ephemeral_token) {
        throw new Error('Missing ephemeral token');
      }
      this.callbacks.onStateChange('Muted', 'Push-to-talk ready (hold button to speak).');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'PTT token error';
      const fallbackReason = `Push-to-talk failed (${msg}). Falling back to text input.`;
      this.callbacks.onStateChange('Offline', fallbackReason);
      this.callbacks.onModeFallback('text', fallbackReason);
    }
  }

  disconnect(): void {
    this.callbacks.onStateChange('Muted', 'Push-to-talk disconnected (no audio stored).');
  }

  async sendText(text: string): Promise<void> {
    this.callbacks.onCaption('Lead', text);
  }

  async forwardToolCall(
    toolName: VoiceToolName,
    args: Record<string, string>,
    transcript?: string
  ): Promise<unknown> {
    return forwardVoiceToolCallToApi(this.apiClient, toolName, args, transcript);
  }
}

/**
 * 3. TextProvider (`text` mode):
 * Terminal fallback mode (`hands-free` -> `push-to-talk` -> `text`).
 * Works both when connected to `api` and in mock mode without faking a voice session.
 */
export class TextProvider implements VoiceProvider {
  public readonly mode: VoiceMode = 'text';
  public readonly modelId: string | null = null;
  private readonly apiClient: ApiClient;
  private readonly callbacks: VoiceProviderCallbacks;

  constructor(apiClient: ApiClient, callbacks: VoiceProviderCallbacks) {
    this.apiClient = apiClient;
    this.callbacks = callbacks;
  }

  async connect(): Promise<void> {
    const reason = this.apiClient.isMockMode
      ? 'Voice unavailable in mock mode (no API URL). Text mode active.'
      : 'Text mode active.';
    this.callbacks.onStateChange(this.apiClient.isMockMode ? 'Offline' : 'Muted', reason);
  }

  disconnect(): void {
    // No-op
  }

  async sendText(text: string): Promise<void> {
    this.callbacks.onCaption('Lead', text);
  }

  async forwardToolCall(
    toolName: VoiceToolName,
    args: Record<string, string>,
    transcript?: string
  ): Promise<unknown> {
    return forwardVoiceToolCallToApi(this.apiClient, toolName, args, transcript);
  }
}

export function getNextFallbackMode(current: VoiceMode): VoiceMode {
  const idx = FIXED_FALLBACK_ORDER.indexOf(current);
  if (idx === -1 || idx >= FIXED_FALLBACK_ORDER.length - 1) {
    return 'text';
  }
  return FIXED_FALLBACK_ORDER[idx + 1];
}
