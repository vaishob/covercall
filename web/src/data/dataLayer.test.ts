import test from 'node:test';
import assert from 'node:assert/strict';
import { createDataSourceFromEnv, MockDataSource } from './dataSource.ts';
import { ApiClient, createApiClientFromEnv } from './apiClient.ts';
import {
  MOM_HOURS_OVERTIME_REST_URL,
  SCENARIO_DESCRIPTORS,
  SCENARIO_MAP,
} from '../mocks/state.ts';

test('createDataSourceFromEnv defaults to MockDataSource when env is unset', async () => {
  const ds = createDataSourceFromEnv({});
  assert.equal(ds.isMock, true);
  assert.equal(ds.sourceName, 'MockDataSource');

  const evals = await ds.getEvalsReadModel();
  assert.equal(evals.isMock, true);
  assert.equal(evals.latestRun, null);
  assert.equal(evals.p0Metrics.length, 8);
  assert.equal(evals.p1Metrics.length, 6);
  assert.equal(evals.p2Metrics.length, 2);
  assert.equal(evals.sliceTables.guardComparisonBySlice.length, 7);

  for (const m of evals.p0Metrics) {
    assert.equal(m.value, null);
  }
  for (const m of evals.p1Metrics) {
    assert.equal(m.value, null);
  }
  for (const m of evals.p2Metrics) {
    assert.equal(m.value, null);
  }
});

test('MockDataSource.subscribeGapEvents never reports chainVerified as true in mock mode', () => {
  const ds = new MockDataSource();
  let receivedVerified: boolean | null = true;
  let eventCount = 0;
  ds.subscribeGapEvents('gap_20261103_bugis_0700', (events, verified) => {
    eventCount = events.length;
    receivedVerified = verified;
  });
  assert.ok(eventCount > 0);
  assert.equal(receivedVerified, null);
});

test('Honesty checks: only S-017 scenario ID exists, guardImpl is null in mock mode, and rule URLs cite MOM URL', () => {
  const codes = SCENARIO_DESCRIPTORS.map((d) => d.scenarioCode);
  assert.ok(codes.includes('S-017'));
  assert.ok(!codes.includes('S-042'));
  assert.ok(!codes.includes('S-058'));

  for (const bundle of Object.values(SCENARIO_MAP)) {
    assert.equal(bundle.isMock, true);
    assert.equal(bundle.guardImpl, null);
    for (const rej of bundle.rejectedCandidates) {
      assert.equal(rej.source.url, MOM_HOURS_OVERTIME_REST_URL);
    }
  }
});

test('ApiClient enters mock mode when VITE_API_BASE_URL is unset and refuses to fake Live tokens', async () => {
  const api = createApiClientFromEnv({});
  assert.equal(api.isMockMode, true);

  const status = await api.getStatus();
  assert.equal(status.mock_mode, true);
  assert.equal(status.guard_impl, null);

  await assert.rejects(
    () => api.mintLiveEphemeralToken(),
    /Voice API unavailable in mock mode/
  );
});

test('ApiClient.submitApproval requires a non-empty approval_nonce', async () => {
  const api = new ApiClient(null);
  await assert.rejects(
    () =>
      api.submitApproval({
        gap_id: 'gap_1',
        plan_id: 'plan_1',
        decision: 'approved',
        approval_nonce: '',
        channel: 'tap',
      }),
    /approval_nonce/
  );
});
