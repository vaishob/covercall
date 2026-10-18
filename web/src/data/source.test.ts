import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ApiClient, ApiError } from './apiClient.ts';
import { LiveSource, ReplaySource, type ReplayFixture } from './source.ts';

const s017 = JSON.parse(readFileSync(new URL('./__fixtures__/s017.json', import.meta.url), 'utf-8')) as ReplayFixture;

function client(routes: Record<string, (body: unknown) => [number, unknown]>) {
  const calls: Array<{ method: string; path: string; body: unknown }> = [];
  const api = new ApiClient('http://api.test/', async (url, init) => {
    const path = url.replace('http://api.test', '');
    const method = init?.method ?? 'GET';
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path, body });
    const handler = routes[`${method} ${path}`];
    const [status, data] = handler ? handler(body) : [404, { error: `no route ${path}` }];
    return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
  });
  return { api, calls };
}

test('ApiClient uses the backend routes and payloads exactly', async () => {
  const { api, calls } = client({
    'POST /gaps': () => [200, { status: 'created', gap_id: 'g1', workflow_execution_id: 'x' }],
    'POST /approvals': () => [200, { approval_id: 'a', decision: 'approve' }],
    'POST /fallbacks': () => [200, { status: 'relayed' }],
    'POST /gaps/g1/cancel': () => [200, { status: 'cancel requested', waits_signalled: 1 }],
    'GET /gaps/g1/approval': () => [200, { gap_id: 'g1', pending: false, synthetic: true }],
  });
  assert.equal(api.baseUrl, 'http://api.test');
  await api.startScenario('S-017');
  await api.submitApproval({ gap_id: 'g1', nonce: 'n', decision: 'approve', channel: 'tap' });
  await api.chooseFallback('g1', 'borrow');
  await api.cancelGap('g1');
  assert.equal(await api.getApproval('g1'), null);
  assert.deepEqual(calls.map((c) => `${c.method} ${c.path}`), [
    'POST /gaps', 'POST /approvals', 'POST /fallbacks', 'POST /gaps/g1/cancel', 'GET /gaps/g1/approval',
  ]);
  assert.deepEqual(calls[0].body, { scenario_id: 'S-017' });
  assert.deepEqual(calls[1].body, { gap_id: 'g1', nonce: 'n', decision: 'approve', channel: 'tap' });
  assert.deepEqual(calls[2].body, { gap_id: 'g1', option: 'borrow' });
  await assert.rejects(() => api.submitApproval({ gap_id: 'g1', nonce: '', decision: 'approve', channel: 'tap' }), /nonce/);
});

test('ApiClient surfaces the server message as an ApiError', async () => {
  const { api } = client({ 'POST /live/token': () => [501, { error: 'not_implemented', message: 'Voice is Slice 4.' }] });
  await assert.rejects(() => api.mintLiveToken(), (e: unknown) => e instanceof ApiError && e.status === 501 && /Slice 4/.test(e.message));
});

test('LiveSource polls until a terminal state, then stops', async () => {
  const snaps = s017.snapshots;
  let i = 0;
  const { api, calls } = client({
    'GET /gaps/gap-0001': () => [200, snaps[Math.min(i++, snaps.length - 1)].gap],
    'GET /gaps/gap-0001/quarantine': () => [200, []],
    'GET /gaps/gap-0001/approval': () => [200, snaps.find((s) => s.approval)!.approval],
  });
  const states: string[] = [];
  await new Promise<void>((resolve) => {
    new LiveSource(api, 1).watch('gap-0001', (v) => {
      states.push(v.gap.state);
      if (v.gap.isTerminal) setTimeout(resolve, 30);
    }, (e) => assert.fail(e.message));
  });
  assert.equal(states.at(-1), 'FILLED');
  const polls = calls.filter((c) => c.path === '/gaps/gap-0001').length;
  assert.equal(polls, snaps.length, 'no further polling after FILLED');
  assert.ok(calls.some((c) => c.path.endsWith('/approval')), 'approval fetched while pending');
});

test('LiveSource reports errors instead of falling back to recorded data', async () => {
  const { api } = client({ 'GET /gaps/g9': () => [500, { error: 'boom' }] });
  const message = await new Promise<string>((resolve) => {
    const stop = new LiveSource(api, 1).watch('g9', () => assert.fail('no view expected'), (e) => {
      stop();
      resolve(e.message);
    });
  });
  assert.equal(message, 'boom');
});

test('ReplaySource plays the recorded snapshots and refuses actions', async () => {
  const replay = new ReplaySource(async () => [s017], 0);
  assert.deepEqual((await replay.listScenarios()).map((s) => s.scenario_id), ['S-017']);
  const handle = await replay.start('S-017');
  const seen: string[] = [];
  await new Promise<void>((resolve) => {
    replay.watch(handle, (v) => {
      assert.equal(v.source, 'replay');
      seen.push(v.gap.state);
      if (seen.length === s017.snapshots.length) resolve();
    }, (e) => assert.fail(e.message));
  });
  assert.equal(seen.at(-1), 'FILLED');
  assert.equal(replay.canAct, false);
  await assert.rejects(() => replay.approve(), /Recorded replay/);
  assert.equal((await replay.evals()).status, 'no_eval_run');
});
