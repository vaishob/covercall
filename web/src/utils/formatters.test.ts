import test from 'node:test';
import assert from 'node:assert/strict';
import {
  formatTime12h,
  formatCurrencySGD,
  formatRuleWarningText,
  getThrottledAriaCountdown,
} from './formatters.ts';

test('formatTime12h converts ISO 8601 +08:00 and 24h strings to 12h format (§11.6)', () => {
  assert.equal(formatTime12h('2026-11-03T07:00:00+08:00'), '7:00am');
  assert.equal(formatTime12h('2026-11-03T15:00:00+08:00'), '3:00pm');
  assert.equal(formatTime12h('2026-11-03T06:02:00+08:00'), '6:02am');
  assert.equal(formatTime12h('06:52'), '6:52am');
  assert.equal(formatTime12h('12:30'), '12:30pm');
});

test('formatCurrencySGD formats SGD amounts with currency symbol (§11.6)', () => {
  assert.equal(formatCurrencySGD(40.8), 'S$40.80');
  assert.equal(formatCurrencySGD(68), 'S$68.00');
});

test('formatRuleWarningText produces canonical S-017 Priya warning from server-supplied fields (§11.4)', () => {
  const formatted = formatRuleWarningText({
    staffName: 'Priya',
    messageBody:
      '70 of 72 overtime hours used this month. This shift adds 3. Breaches the EA Part 4 monthly cap.',
    ruleId: 'SG-EA4-OT-CAP-72',
    sourcePublisher: 'MOM',
  });
  assert.equal(
    formatted,
    'Priya: 70 of 72 overtime hours used this month. This shift adds 3. Breaches the EA Part 4 monthly cap. SG-EA4-OT-CAP-72 · MOM source.'
  );
});

test('getThrottledAriaCountdown buckets screen reader updates to avoid flooding (§11.7)', () => {
  assert.equal(
    getThrottledAriaCountdown(19 * 60),
    'Approximately 20 minutes remaining until CoverCall escalates to you.'
  );
  assert.equal(
    getThrottledAriaCountdown(16 * 60),
    'Approximately 20 minutes remaining until CoverCall escalates to you.'
  );
  assert.equal(
    getThrottledAriaCountdown(4 * 60),
    '4 minutes remaining until CoverCall escalates to you.'
  );
});
