/**
 * Contract tests: real backend responses (captured by evals/runners/capture_fixtures.py) run through
 * the mapping layer. A backend shape change breaks these tests (and the backend's own drift test).
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import type { ReplayFixture } from './source.ts';
import { centsToSgd, toLeadView, toTraceView } from './viewModel.ts';

function fixture(name: string): ReplayFixture {
  return JSON.parse(readFileSync(new URL(`./__fixtures__/${name}.json`, import.meta.url), 'utf-8')) as ReplayFixture;
}

const s017 = fixture('s017');
const s002 = fixture('s002');
const map = (fx: ReplayFixture, i: number) => {
  const s = fx.snapshots[i < 0 ? fx.snapshots.length + i : i];
  return toLeadView(s.gap, s.approval, s.quarantine, 'live');
};

test('centsToSgd formats integer cents without float drift', () => {
  assert.equal(centsToSgd(15105), 'S$151.05');
  assert.equal(centsToSgd(0), 'S$0.00');
  assert.equal(centsToSgd(-505), '-S$5.05');
});

test('S-017 final snapshot maps to a filled lead view with a two-person split', () => {
  const v = map(s017, -1);
  assert.equal(v.gap.state, 'FILLED');
  assert.equal(v.gap.isTerminal, true);
  assert.equal(v.gap.absentName, 'Ali');
  assert.equal(v.gap.outletName, 'Bugis');
  assert.ok(v.gap.escalationAt, 't_esc_locked is the countdown target');
  assert.equal(v.committed?.segments.length, 2);
  assert.deepEqual(
    v.committed?.segments.map((s) => [s.name, s.start.slice(11, 16), s.end.slice(11, 16)]),
    [['Fiona', '07:00', '09:00'], ['Lucas', '09:00', '15:00']]
  );
  assert.ok(v.plans.some((p) => p.isSplit && p.segments.length === 2));
  assert.equal(v.gap.costSavedCents, 15105);
  assert.equal(v.naive?.name, 'Priya');
  assert.deepEqual(v.naive?.blockingRuleIds, ['SG-EA4-OT-CAP-72']);
});

test('saving vs the usual first pick comes from the server, not the browser', () => {
  const s = s017.snapshots.at(-1)!;
  const v = map(s017, -1);
  v.plans.forEach((p, i) => assert.equal(p.savesVsNaiveCents, s.gap.plan!.options[i].saves_vs_naive_cents));
});

test('rejected candidates carry the rule ID, kind label (not P0/P1/P2), message and source from the data', () => {
  const v = map(s017, -1);
  const priya = v.rejected.find((r) => r.staffId === 'stf_004');
  assert.ok(priya);
  assert.equal(priya.ruleId, 'SG-EA4-OT-CAP-72');
  assert.equal(priya.kindLabel, 'Hard rule');
  assert.match(priya.message, /^Priya: 70 of 72 overtime hours used this month\./);
  assert.equal(priya.sourceUrl, 'https://www.mom.gov.sg/employment-practices/hours-of-work-overtime-and-rest-days');
  assert.equal(priya.section, 'Maximum hours of overtime');
  for (const r of v.rejected) {
    assert.ok(!/^P[0-2]/.test(r.kindLabel));
    if (r.ruleId === 'SG-SFA-FSC-L1') assert.match(r.sourceUrl, /^https:\/\/www\.sfa\.gov\.sg\//);
    if (r.ruleId === 'SG-PT-OT-RATE') assert.match(r.sourceUrl, /part-time-employment\/overtime$/);
  }
});

test('rule checks are objects mapped with kind and source; breaks are start plus duration', () => {
  const v = map(s017, -1);
  const top = v.plans[0];
  assert.ok(top.passedChecks.length > 0);
  for (const c of top.passedChecks) {
    assert.ok(c.kind === 'hard' || c.kind === 'data_gate');
    assert.equal(c.status, 'ok');
    assert.ok(c.sourceUrl.length > 0);
  }
  const allSegments = s017.snapshots.flatMap((_, i) => map(s017, i).plans.flatMap((p) => p.segments));
  const withBreak = allSegments.find((s) => s.breaks.length > 0);
  assert.ok(withBreak);
  assert.equal(typeof withBreak.breaks[0].durationMin, 'number');
});

test('S-017 cascade timeline reads the real offers: decline, counter, silence, accept', () => {
  const v = map(s017, -1);
  assert.deepEqual(
    v.offers.map((o) => [o.staffName, o.status]),
    [['Aisha', 'decline'], ['Lucas', 'countered'], ['Nadia', 'timeout'], ['Fiona', 'accepted']]
  );
  assert.equal(v.offers[0].statusLabel, 'Declined');
});

test('approval snapshot maps the server read-back and nonce; other snapshots have none', () => {
  const idx = s017.snapshots.findIndex((s) => s.approval);
  assert.ok(idx >= 0);
  const v = map(s017, idx);
  assert.equal(v.gap.state, 'SOLVED');
  assert.ok(v.approval?.nonce);
  assert.match(v.approval!.readback, /^Offer the bugis barista shift/);
  assert.equal(map(s017, -1).approval, null);
});

test('roster strip names who covers each hour of the committed plan', () => {
  const cells = map(s017, -1).roster.cells;
  assert.deepEqual(cells.map((c) => c.staffName), ['Fiona', 'Fiona', 'Lucas', 'Lucas', 'Lucas', 'Lucas', 'Lucas', 'Lucas']);
});

test('S-002 escalates with the backend fallback names, then resolves', () => {
  const esc = s002.snapshots.findIndex((s) => s.gap.gap.state === 'ESCALATED' && (s.gap.gap.fallbacks ?? []).length > 0);
  assert.ok(esc >= 0);
  const v = map(s002, esc);
  assert.deepEqual(v.gap.fallbacks.map((f) => f.id), s002.snapshots[esc].gap.gap.fallbacks);
  assert.equal(v.gap.fallbacks[0].label, 'Borrow from another outlet');
  assert.ok(v.offers.some((o) => o.round?.startsWith('fanout')));
  const last = map(s002, -1);
  assert.equal(last.gap.state, 'RESOLVED');
  assert.equal(last.gap.outcomeLabel, 'Borrow from another outlet');
});

test('trace view keeps the server chain verdict', () => {
  const t = toTraceView(s017.events);
  assert.equal(t.chainOk, true);
  assert.equal(t.events[0].type, 'gap.reported');
  assert.equal(t.events[0].from, '(none)');
  assert.equal(t.events.at(-1)?.type, 'commit.ok');
});

test('fixtures hold no nonce outside approval snapshots and no callback URLs', () => {
  for (const fx of [s017, s002]) {
    const nonces = fx.snapshots.flatMap((s) => (s.approval ? [s.approval.nonce] : []));
    for (const s of fx.snapshots) {
      const gapJson = JSON.stringify(s.gap) + JSON.stringify(s.quarantine);
      for (const n of nonces) assert.ok(!gapJson.includes(n));
      assert.ok(!gapJson.includes('callback'));
    }
  }
});
