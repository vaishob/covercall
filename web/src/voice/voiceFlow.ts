import type { VoiceMode, VoiceState } from './types.ts';

/**
 * Pure voice state rules (no browser APIs), shared by the providers and App.
 * Never show "Listening" without a live session whose audio is running.
 */

export const TAP_TO_ENABLE_AUDIO = 'Tap to enable audio';

/**
 * Where to go after a voice mode fails. Push-to-talk needs a token from the same route and the same
 * microphone, so after a 429 or a microphone denial it would fail too: go straight to text.
 */
export function fallbackModeFor(failure: { status?: number; micDenied?: boolean }, next: VoiceMode): VoiceMode {
  if (failure.status === 429 || failure.micDenied) return 'text';
  return next;
}

/** State once the Live socket is open. Suspended audio (iOS outside a tap) needs one more tap. */
export function liveReadyState(pushToTalk: boolean, audioRunning: boolean): { state: VoiceState; needsTap: boolean } {
  if (!audioRunning) return { state: 'Muted', needsTap: true };
  return { state: pushToTalk ? 'Muted' : 'Listening', needsTap: false };
}

/** State for a "Hold to talk" press or release; null leaves the state alone (no live session). */
export function talkState(open: boolean, hasLiveSession: boolean): VoiceState | null {
  if (!hasLiveSession) return null;
  return open ? 'Listening' : 'Muted';
}

/** Re-tapping the mode that is already connected (or connecting) must not mint another token. */
export function isSameModeActive(requested: VoiceMode, current: VoiceMode, state: VoiceState, hasProvider: boolean): boolean {
  return requested === current && hasProvider && state !== 'Offline';
}
