import type { VoiceMode, VoiceState } from './types.ts';
import type { ApiClient } from '../data/apiClient.ts';

/**
 * The exact five tools exposed to the voice model (§7.2):
 * - report_absence(outlet, shift_start, station, staff_name?)
 * - approve(plan_id, decision, approval_nonce)
 * - choose_fallback(gap_id, option)
 * - get_status(gap_id)
 * - cancel_gap(gap_id)
 *
 * The browser forwards each tool call to `api`, which validates it. Nothing executes locally.
 * Voice itself (Gemini Live with ephemeral tokens) is Slice 4: `POST /live/token` answers 501
 * until then, and the providers fall back hands-free -> push-to-talk -> text.
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
    description: 'Report a staff absence. The server resolves the name and shift, or asks a question.',
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
    description: 'Record a Tier T2 approval or rejection with the server-issued approval_nonce.',
    parameters: {
      type: 'OBJECT',
      properties: {
        plan_id: { type: 'STRING', description: 'Plan ID being approved or rejected' },
        decision: { type: 'STRING', description: 'approve or reject' },
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
          description: 'Fallback option ID (borrow, reduced_service, lead_covers, agency, unfilled)',
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
    description: 'Ask the workflow to cancel an active gap (open offers are withdrawn).',
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
 * Spoken approval policy (§5.3 & §7.2): "Only a clear affirmative counts; anything else is a no."
 * The server applies the same rule to the transcript; this copy only decides what to send.
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

export interface ToolContext {
  /** The gap the lead is looking at; approve() is about this gap. */
  gapId: string | null;
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
    context: ToolContext,
    transcript?: string
  ): Promise<unknown>;
}

/** Forwards a voice tool call to `api`. Never executes state changes locally (§7.2). */
export async function forwardVoiceToolCallToApi(
  apiClient: ApiClient | null,
  toolName: VoiceToolName,
  args: Record<string, string>,
  context: ToolContext,
  transcript?: string
): Promise<unknown> {
  if (!apiClient) {
    throw new Error('Recorded replay: voice tools need a live API (set VITE_API_BASE_URL).');
  }
  switch (toolName) {
    case 'report_absence':
      return apiClient.reportAbsence({
        outlet: args.outlet,
        shift_start: args.shift_start,
        station: args.station,
        staff_name: args.staff_name,
        text: transcript,
      });

    case 'approve': {
      const nonce = args.approval_nonce?.trim();
      if (!nonce) {
        throw new Error('approve requires the server-issued approval_nonce (§7.2).');
      }
      if (!context.gapId) {
        throw new Error('approve needs an active gap.');
      }
      // Anything other than a clear yes counts as a no (§5.3, §7.2).
      const isYes =
        args.decision === 'approve' &&
        (transcript === undefined || isClearAffirmativeTranscript(transcript));
      return apiClient.submitApproval({
        gap_id: context.gapId,
        nonce,
        decision: isYes ? 'approve' : 'reject',
        transcript: transcript ?? '',
        channel: 'voice',
      });
    }

    case 'choose_fallback':
      return apiClient.chooseFallback(args.gap_id, args.option);

    case 'get_status':
      return apiClient.getGap(args.gap_id);

    case 'cancel_gap':
      return apiClient.cancelGap(args.gap_id);
  }
}

abstract class TokenVoiceProvider implements VoiceProvider {
  abstract readonly mode: VoiceMode;
  readonly modelId: string | null;
  protected readonly apiClient: ApiClient | null;
  protected readonly callbacks: VoiceProviderCallbacks;

  constructor(apiClient: ApiClient | null, callbacks: VoiceProviderCallbacks, configuredModelId?: string | null) {
    this.apiClient = apiClient;
    this.callbacks = callbacks;
    this.modelId = configuredModelId?.trim() || null;
  }

  abstract connect(): Promise<void>;
  abstract disconnect(): void;

  async sendText(text: string): Promise<void> {
    this.callbacks.onCaption('Lead', text);
  }

  async forwardToolCall(
    toolName: VoiceToolName,
    args: Record<string, string>,
    context: ToolContext,
    transcript?: string
  ): Promise<unknown> {
    return forwardVoiceToolCallToApi(this.apiClient, toolName, args, context, transcript);
  }
}

/**
 * 1. LiveVoiceProvider (hands-free): Gemini Live (`v1alpha`) authenticated ONLY with an ephemeral
 * token from `api` (`POST /live/token`). Never holds a client API key.
 */
export class LiveVoiceProvider extends TokenVoiceProvider {
  readonly mode: VoiceMode = 'hands-free';

  async connect(): Promise<void> {
    if (!this.apiClient) {
      const reason = 'Voice needs a live API (recorded replay). Fell back to text input.';
      this.callbacks.onStateChange('Offline', reason);
      this.callbacks.onModeFallback('text', reason);
      return;
    }
    try {
      this.callbacks.onStateChange('Thinking', 'Requesting a v1alpha ephemeral token from api…');
      const tokenResp = await this.apiClient.mintLiveToken();
      if (tokenResp.api_version !== 'v1alpha' || !tokenResp.ephemeral_token) {
        throw new Error('Ephemeral token requires Live API v1alpha.');
      }
      const resolvedModel = this.modelId || tokenResp.model_id;
      if (!resolvedModel) throw new Error('No Live model ID is configured.');
      this.callbacks.onStateChange('Listening', `Live session active (${resolvedModel}, v1alpha ephemeral token)`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Live session failed';
      const fallbackReason = `Hands-free unavailable: ${msg} Falling back to push-to-talk.`;
      this.callbacks.onStateChange('Offline', fallbackReason);
      this.callbacks.onModeFallback('push-to-talk', fallbackReason);
    }
  }

  disconnect(): void {
    this.callbacks.onStateChange('Muted', 'Voice session closed (no audio stored).');
  }
}

/** 2. PushToTalkProvider: second step of the fixed fallback order. */
export class PushToTalkProvider extends TokenVoiceProvider {
  readonly mode: VoiceMode = 'push-to-talk';

  async connect(): Promise<void> {
    if (!this.apiClient) {
      const reason = 'Push-to-talk needs a live API (recorded replay). Fell back to text input.';
      this.callbacks.onStateChange('Offline', reason);
      this.callbacks.onModeFallback('text', reason);
      return;
    }
    try {
      const tokenResp = await this.apiClient.mintLiveToken();
      if (!tokenResp.ephemeral_token) throw new Error('Missing ephemeral token.');
      this.callbacks.onStateChange('Muted', 'Push-to-talk ready (hold button to speak).');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'PTT token error';
      const fallbackReason = `Push-to-talk unavailable: ${msg} Falling back to text input.`;
      this.callbacks.onStateChange('Offline', fallbackReason);
      this.callbacks.onModeFallback('text', fallbackReason);
    }
  }

  disconnect(): void {
    this.callbacks.onStateChange('Muted', 'Push-to-talk disconnected (no audio stored).');
  }
}

/** 3. TextProvider: terminal fallback. Works live and in recorded replay. */
export class TextProvider extends TokenVoiceProvider {
  readonly mode: VoiceMode = 'text';

  async connect(): Promise<void> {
    const reason = this.apiClient ? 'Text mode active.' : 'Recorded replay: text input is display-only.';
    this.callbacks.onStateChange(this.apiClient ? 'Muted' : 'Offline', reason);
  }

  disconnect(): void {
    // No-op
  }
}

export function getNextFallbackMode(current: VoiceMode): VoiceMode {
  const idx = FIXED_FALLBACK_ORDER.indexOf(current);
  if (idx === -1 || idx >= FIXED_FALLBACK_ORDER.length - 1) {
    return 'text';
  }
  return FIXED_FALLBACK_ORDER[idx + 1];
}
