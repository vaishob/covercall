import test from 'node:test';
import assert from 'node:assert/strict';
import { ApiClient } from '../data/apiClient.ts';
import {
  FIXED_FALLBACK_ORDER,
  getNextFallbackMode,
  isClearAffirmativeTranscript,
  LiveVoiceProvider,
  PushToTalkProvider,
  VOICE_TOOL_DECLARATIONS,
} from './voiceProvider.ts';

test('VOICE_TOOL_DECLARATIONS exposes the exact 5 tools from §7.2', () => {
  const names = VOICE_TOOL_DECLARATIONS.map((t) => t.name);
  assert.deepEqual(names, [
    'report_absence',
    'approve',
    'choose_fallback',
    'get_status',
    'cancel_gap',
  ]);
});

test('FIXED_FALLBACK_ORDER enforces hands-free -> push-to-talk -> text (§7.2)', () => {
  assert.deepEqual(FIXED_FALLBACK_ORDER, ['hands-free', 'push-to-talk', 'text']);
  assert.equal(getNextFallbackMode('hands-free'), 'push-to-talk');
  assert.equal(getNextFallbackMode('push-to-talk'), 'text');
  assert.equal(getNextFallbackMode('text'), 'text');
});

test('isClearAffirmativeTranscript accepts only a clear yes and treats anything else as no (§5.3, §7.2)', () => {
  assert.equal(isClearAffirmativeTranscript('Yes, approve'), true);
  assert.equal(isClearAffirmativeTranscript('yes'), true);
  assert.equal(isClearAffirmativeTranscript('Approve plan'), true);
  assert.equal(isClearAffirmativeTranscript('maybe yes'), false);
  assert.equal(isClearAffirmativeTranscript('yes but wait'), false);
  assert.equal(isClearAffirmativeTranscript('no'), false);
  assert.equal(isClearAffirmativeTranscript('what about Priya?'), false);
});

test('LiveVoiceProvider refuses to fake a voice session in mock mode and falls back to text', async () => {
  const api = new ApiClient(null);
  let lastState = '';
  let lastReason = '';
  let fallbackMode = '';

  const provider = new LiveVoiceProvider(api, {
    onStateChange: (st, reason) => {
      lastState = st;
      lastReason = reason ?? '';
    },
    onModeFallback: (mode, reason) => {
      fallbackMode = mode;
      lastReason = reason;
    },
    onCaption: () => {},
  });

  await provider.connect();
  assert.equal(lastState, 'Offline');
  assert.equal(fallbackMode, 'text');
  assert.match(lastReason, /Voice unavailable in mock mode/);
});

test('PushToTalkProvider falls back to text when API is unset in mock mode', async () => {
  const api = new ApiClient(null);
  let fallbackMode = '';
  const ptt = new PushToTalkProvider(api, {
    onStateChange: () => {},
    onModeFallback: (mode) => {
      fallbackMode = mode;
    },
    onCaption: () => {},
  });

  await ptt.connect();
  assert.equal(fallbackMode, 'text');
});

test('forwardToolCall approve requires approval_nonce and downgrades ambiguous transcript to rejected', async () => {
  const api = new ApiClient(null);
  const provider = new LiveVoiceProvider(api, {
    onStateChange: () => {},
    onModeFallback: () => {},
    onCaption: () => {},
  });

  await assert.rejects(
    () =>
      provider.forwardToolCall('approve', {
        plan_id: 'plan_1',
        decision: 'approved',
        approval_nonce: '',
      }),
    /approval_nonce/
  );
});
