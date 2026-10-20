import type { VoiceMode, VoiceState } from './types.ts';
import { ApiError, type ApiClient } from '../data/apiClient.ts';

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
    description: "Record the lead's answer to the read-back. The browser sends the server nonce; the server checks for a clear yes.",
    parameters: {
      type: 'OBJECT',
      properties: {
        decision: { type: 'STRING', description: 'approve (only after a clear spoken yes) or reject' },
      },
      required: ['decision'],
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
  /** Called when report_absence creates a gap, so the lead view follows it. */
  onGap?: (gapId: string) => void;
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

/**
 * Forwards a voice tool call to `api`. Never executes state changes locally (§7.2): the server
 * resolves names and shifts, issues the read-back and nonce, and applies the clear-yes check.
 */
export async function forwardVoiceToolCallToApi(
  apiClient: ApiClient | null,
  toolName: VoiceToolName,
  args: Record<string, string>,
  context: ToolContext,
  transcript?: string,
  waitForReadback: (gapId: string) => Promise<{ readback_text: string } | null> = (id) => pollApproval(apiClient, id)
): Promise<unknown> {
  if (!apiClient) {
    throw new Error('Recorded replay: voice tools need a live API (set VITE_API_BASE_URL).');
  }
  switch (toolName) {
    case 'report_absence': {
      const created = await apiClient.reportAbsence({
        outlet: args.outlet,
        shift_start: args.shift_start,
        station: args.station,
        staff_name: args.staff_name,
        text: transcript,
      });
      if (created.status !== 'created' || !created.gap_id) return created; // a clarifying question
      context.gapId = created.gap_id;
      context.onGap?.(created.gap_id);
      const approval = await waitForReadback(created.gap_id);
      return approval
        ? { gap_id: created.gap_id, readback_text: approval.readback_text }
        : { gap_id: created.gap_id, status: 'no plan to approve yet; use get_status' };
    }

    case 'approve': {
      if (!context.gapId) throw new Error('approve needs an active gap.');
      const pending = await apiClient.getApproval(context.gapId);
      if (!pending) throw new Error('No approval is pending for this gap.');
      // Anything other than a clear yes counts as a no (§5.3, §7.2); the server checks again.
      const isYes = args.decision === 'approve' && transcript !== undefined && isClearAffirmativeTranscript(transcript);
      return apiClient.submitApproval({
        gap_id: context.gapId,
        nonce: pending.nonce,
        decision: isYes ? 'approve' : 'reject',
        transcript: transcript ?? '',
        channel: 'voice',
      });
    }

    case 'choose_fallback':
      return apiClient.chooseFallback(args.gap_id || context.gapId || '', args.option);

    case 'get_status':
      return apiClient.getGap(args.gap_id || context.gapId || '');

    case 'cancel_gap':
      return apiClient.cancelGap(args.gap_id || context.gapId || '');
  }
}

/** Waits (up to ~90 s) for the server's read-back sentence after a gap is created. */
async function pollApproval(apiClient: ApiClient | null, gapId: string): Promise<{ readback_text: string } | null> {
  for (let i = 0; i < 45 && apiClient; i++) {
    const pending = await apiClient.getApproval(gapId);
    if (pending) return pending;
    await new Promise((r) => setTimeout(r, 2000));
  }
  return null;
}

abstract class TokenVoiceProvider implements VoiceProvider {
  abstract readonly mode: VoiceMode;
  readonly modelId: string | null;
  protected readonly apiClient: ApiClient | null;
  protected readonly callbacks: VoiceProviderCallbacks;
  protected readonly context: ToolContext;
  protected live: { setGate(open: boolean): void; close(reason?: string): void; lastUserTranscript: string } | null = null;

  constructor(apiClient: ApiClient | null, callbacks: VoiceProviderCallbacks, configuredModelId?: string | null,
              context?: ToolContext) {
    this.apiClient = apiClient;
    this.callbacks = callbacks;
    this.modelId = configuredModelId?.trim() || null;
    this.context = context ?? { gapId: null };
  }

  abstract connect(): Promise<void>;

  disconnect(): void {
    this.live?.close();
    this.live = null;
  }

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

  /** Mints a token, then opens one Live session. Falls back on mic denial, token error or socket error. */
  protected async openLive(next: VoiceMode, pushToTalk: boolean): Promise<void> {
    const label = pushToTalk ? 'Push-to-talk' : 'Hands-free';
    if (!this.apiClient) {
      const reason = `${label} needs a live API (recorded replay). Fell back to text input.`;
      this.callbacks.onStateChange('Offline', reason);
      this.callbacks.onModeFallback('text', reason);
      return;
    }
    try {
      this.callbacks.onStateChange('Thinking', 'Requesting a v1beta ephemeral token from api…');
      const tokenResp = await this.apiClient.mintLiveToken();
      if (tokenResp.api_version !== 'v1beta' || !tokenResp.token) {
        throw new Error('Ephemeral token requires Live API v1beta.');
      }
      const model = this.modelId || tokenResp.model_id;
      if (!model) throw new Error('No Live model ID is configured.');
      const { LiveSession } = await import('./liveSession.ts');
      const session: InstanceType<typeof LiveSession> = new LiveSession({
        onUserTranscript: (t) => this.callbacks.onCaption('Lead', t),
        onModelTranscript: (t) => this.callbacks.onCaption('CoverCall', t),
        onSpeaking: (s) =>
          this.callbacks.onStateChange(s ? 'Speaking' : pushToTalk ? 'Muted' : 'Listening'),
        onToolCall: (name, args): Promise<unknown> => {
          this.callbacks.onStateChange('Thinking', `Asking the server (${name})…`);
          return this.forwardToolCall(name as VoiceToolName, args, this.context, session.lastUserTranscript);
        },
        onClosed: (reason) => {
          if (this.live !== session) return; // closed by us
          this.live = null;
          this.callbacks.onStateChange('Offline', reason);
          this.callbacks.onModeFallback(next, `${reason} Falling back to ${next}.`);
        },
      });
      this.live = session;
      await session.open(tokenResp.token, model, tokenResp.api_version);
      session.setGate(!pushToTalk);
      this.callbacks.onStateChange(
        pushToTalk ? 'Muted' : 'Listening',
        `Live session active (${model}, v1beta ephemeral token)${pushToTalk ? '. Hold the button to talk.' : ''}`
      );
    } catch (err) {
      this.live?.close();
      this.live = null;
      const msg = err instanceof Error ? err.message : 'Live session failed';
      const denied = err instanceof Error && err.name === 'NotAllowedError';
      // Push-to-talk mints from the same route, so after a 429 it would fail too: go straight to text.
      const limited = err instanceof ApiError && err.status === 429;
      const fallback = limited ? 'text' : next;
      const reason = limited
        ? `${label} unavailable: ${msg}. Voice is paused for a few minutes; falling back to text.`
        : `${label} unavailable: ${denied ? 'microphone permission denied.' : msg} Falling back to ${fallback}.`;
      this.callbacks.onStateChange('Offline', reason);
      this.callbacks.onModeFallback(fallback, reason);
    }
  }

  /** Push-to-talk gate (held button). */
  setTalking(open: boolean): void {
    this.live?.setGate(open);
    this.callbacks.onStateChange(open ? 'Listening' : 'Muted');
  }
}

/**
 * 1. LiveVoiceProvider (hands-free): Gemini Live (`v1beta`, decision 0019) authenticated ONLY with an
 * ephemeral token from `api` (`POST /live/token`). Never holds a client API key.
 */
export class LiveVoiceProvider extends TokenVoiceProvider {
  readonly mode: VoiceMode = 'hands-free';

  async connect(): Promise<void> {
    await this.openLive('push-to-talk', false);
  }
}

/** 2. PushToTalkProvider: the same Live session with the mic gated by a held button. */
export class PushToTalkProvider extends TokenVoiceProvider {
  readonly mode: VoiceMode = 'push-to-talk';

  async connect(): Promise<void> {
    await this.openLive('text', true);
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
