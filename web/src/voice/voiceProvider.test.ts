import test from 'node:test';
import assert from 'node:assert/strict';
import { ApiClient } from '../data/apiClient.ts';
import {
  FIXED_FALLBACK_ORDER,
  forwardVoiceToolCallToApi,
  getNextFallbackMode,
  isClearAffirmativeTranscript,
  LiveVoiceProvider,
  PushToTalkProvider,
  VOICE_TOOL_DECLARATIONS,
} from './voiceProvider.ts';

function recordingClient(status = 200, body: unknown = {}) {
  const calls: Array<{ url: string; method: string; body: unknown }> = [];
  const client = new ApiClient('http://api.test', async (url, init) => {
    calls.push({ url, method: init?.method ?? 'GET', body: init?.body ? JSON.parse(String(init.body)) : undefined });
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  });
  return { client, calls };
}

const quiet = { onStateChange: () => {}, onModeFallback: () => {}, onCaption: () => {} };

test('VOICE_TOOL_DECLARATIONS exposes the exact 5 tools from §7.2', () => {
  assert.deepEqual(
    VOICE_TOOL_DECLARATIONS.map((t) => t.name),
    ['report_absence', 'approve', 'choose_fallback', 'get_status', 'cancel_gap']
  );
});

test('FIXED_FALLBACK_ORDER enforces hands-free -> push-to-talk -> text (§7.2)', () => {
  assert.deepEqual(FIXED_FALLBACK_ORDER, ['hands-free', 'push-to-talk', 'text']);
  assert.equal(getNextFallbackMode('hands-free'), 'push-to-talk');
  assert.equal(getNextFallbackMode('push-to-talk'), 'text');
  assert.equal(getNextFallbackMode('text'), 'text');
});

test('isClearAffirmativeTranscript accepts only a clear yes (§5.3, §7.2)', () => {
  assert.equal(isClearAffirmativeTranscript('Yes, approve'), true);
  assert.equal(isClearAffirmativeTranscript('yes'), true);
  assert.equal(isClearAffirmativeTranscript('Approve plan'), true);
  assert.equal(isClearAffirmativeTranscript('maybe yes'), false);
  assert.equal(isClearAffirmativeTranscript('yes but wait'), false);
  assert.equal(isClearAffirmativeTranscript('no'), false);
});

test('Live and push-to-talk fall back to text in recorded replay (no API)', async () => {
  let fallback = '';
  await new LiveVoiceProvider(null, { ...quiet, onModeFallback: (m) => (fallback = m) }).connect();
  assert.equal(fallback, 'text');
  fallback = '';
  await new PushToTalkProvider(null, { ...quiet, onModeFallback: (m) => (fallback = m) }).connect();
  assert.equal(fallback, 'text');
});

test('hands-free falls back to push-to-talk when POST /live/token answers 501', async () => {
  const { client, calls } = recordingClient(501, { error: 'not_implemented', message: 'Voice is Slice 4.' });
  let fallback = '';
  let reason = '';
  await new LiveVoiceProvider(client, { ...quiet, onModeFallback: (m, r) => ((fallback = m), (reason = r)) }).connect();
  assert.equal(calls[0].url, 'http://api.test/live/token');
  assert.equal(calls[0].method, 'POST');
  assert.equal(fallback, 'push-to-talk');
  assert.match(reason, /Hands-free unavailable/);
});

test('a 429 from POST /live/token skips push-to-talk (same token route) and falls back to text', async () => {
  const { client, calls } = recordingClient(429, { error: 'rate_limited', message: 'per-IP token limit reached' });
  let fallback = '';
  let reason = '';
  await new LiveVoiceProvider(client, { ...quiet, onModeFallback: (m, r) => ((fallback = m), (reason = r)) }).connect();
  assert.equal(calls.length, 1);
  assert.equal(fallback, 'text');
  assert.match(reason, /per-IP token limit reached/);
  assert.doesNotMatch(reason, /push-to-talk/i);
});

test('hands-free accepts only a v1beta ephemeral token (decision 0019)', async () => {
  const token = { token: 'auth_tokens/tok', expires_at: '2026-11-03T06:30:00+08:00', model_id: 'gemini-3.8-live' };
  // v1beta passes the token check and reaches the mic (none in node, so it falls back for that reason).
  let reason = '';
  await new LiveVoiceProvider(recordingClient(200, { ...token, api_version: 'v1beta' }).client, {
    ...quiet,
    onModeFallback: (_m, r) => (reason = r),
  }).connect();
  assert.doesNotMatch(reason, /requires Live API v1beta/);
  let fallback = '';
  await new LiveVoiceProvider(recordingClient(200, { ...token, api_version: 'v1alpha' }).client, {
    ...quiet,
    onModeFallback: (m, r) => ((fallback = m), (reason = r)),
  }).connect();
  assert.equal(fallback, 'push-to-talk');
  assert.match(reason, /requires Live API v1beta/);
});

test('approve tool fetches the server nonce, sends the transcript, and downgrades an unclear yes', async () => {
  const { client, calls } = recordingClient(200, { pending: true, nonce: 'n1', readback_text: 'r', approval_id: 'a1', decision: 'reject' });
  await assert.rejects(() => forwardVoiceToolCallToApi(client, 'approve', { decision: 'approve' }, { gapId: null }), /active gap/);
  await forwardVoiceToolCallToApi(client, 'approve', { decision: 'approve' }, { gapId: 'g1' }, 'hmm maybe');
  assert.equal(calls.at(-2)?.url, 'http://api.test/gaps/g1/approval');
  assert.deepEqual(calls.at(-1), {
    url: 'http://api.test/approvals',
    method: 'POST',
    body: { gap_id: 'g1', nonce: 'n1', decision: 'reject', transcript: 'hmm maybe', channel: 'voice' },
  });
  await forwardVoiceToolCallToApi(client, 'approve', { decision: 'approve' }, { gapId: 'g1' }, 'yes, approve');
  assert.equal((calls.at(-1)?.body as { decision: string }).decision, 'approve');
});

test('report_absence and choose_fallback hit the real routes', async () => {
  const { client, calls } = recordingClient(200, { status: 'clarify', question: 'Who is absent?', candidates: [] });
  await forwardVoiceToolCallToApi(client, 'report_absence', { outlet: 'bugis', shift_start: '07:00', station: 'barista', staff_name: 'Ali' }, { gapId: null });
  assert.equal(calls[0].url, 'http://api.test/gaps');
  assert.deepEqual(calls[0].body, { outlet: 'bugis', station: 'barista', shift_start: '07:00', staff_name: 'Ali' });
  await forwardVoiceToolCallToApi(client, 'choose_fallback', { gap_id: 'g1', option: 'borrow' }, { gapId: 'g1' });
  assert.deepEqual(calls[1], { url: 'http://api.test/fallbacks', method: 'POST', body: { gap_id: 'g1', option: 'borrow' } });
});

test('report_absence returns the server read-back once the gap is created, and follows the gap', async () => {
  const { client } = recordingClient(200, { status: 'created', gap_id: 'gap-0042', workflow_execution_id: 'e' });
  let followed = '';
  const context = { gapId: null as string | null, onGap: (id: string) => (followed = id) };
  const out = await forwardVoiceToolCallToApi(client, 'report_absence', { outlet: 'bugis', shift_start: '07:00', station: 'barista' },
    context, 'Ali is sick', async () => ({ readback_text: 'Approve Fiona 07:00-09:00 ...' }));
  assert.deepEqual(out, { gap_id: 'gap-0042', readback_text: 'Approve Fiona 07:00-09:00 ...' });
  assert.equal(context.gapId, 'gap-0042');
  assert.equal(followed, 'gap-0042');
});
