export interface RuleWarningInput {
  staffName: string;
  messageBody: string;
  ruleId: string;
  sourcePublisher: string;
}

/**
 * Formats an ISO 8601 timestamp (with +08:00) or HH:MM string into "7:00am" style
 * per §11.6 of the CoverCall Design Doc.
 * Display-only formatter; never computes deadlines or policy rules.
 */
export function formatTime12h(input: string): string {
  const timeMatch = input.match(/T(\d{2}):(\d{2})/) || input.match(/^(\d{1,2}):(\d{2})$/);
  if (!timeMatch) {
    return input;
  }
  const hours24 = parseInt(timeMatch[1], 10);
  const minutes = timeMatch[2];
  const period = hours24 >= 12 ? 'pm' : 'am';
  const hours12 = hours24 % 12 === 0 ? 12 : hours24 % 12;
  return `${hours12}:${minutes}${period}`;
}

/**
 * Formats a number in Singapore Dollars (SGD) with currency shown per §11.6.
 * Display-only formatter; never computes labour costs or overtime rates.
 */
export function formatCurrencySGD(amount: number): string {
  const sign = amount < 0 ? '-' : '';
  const abs = Math.abs(amount);
  return `${sign}S$${abs.toFixed(2)}`;
}

/**
 * Formats a RuleWarning summary line from server-supplied parameters per §11.4:
 * "Priya: 70 of 72 overtime hours used this month. This shift adds 3. Breaches the EA Part 4 monthly cap. SG-EA4-OT-CAP-72 · MOM source."
 */
export function formatRuleWarningText(input: RuleWarningInput): string {
  return `${input.staffName}: ${input.messageBody} ${input.ruleId} · ${input.sourcePublisher} source.`;
}

/**
 * Throttles countdown announcements for screen readers (§11.7) so polite live regions
 * do not flood assistive technology on every second tick.
 */
export function getThrottledAriaCountdown(totalSecondsRemaining: number): string {
  const minutesCeiling = Math.ceil(totalSecondsRemaining / 60);
  if (totalSecondsRemaining <= 0) {
    return 'Must-fill-by deadline reached.';
  }
  if (minutesCeiling <= 5) {
    return `${minutesCeiling} minute${minutesCeiling === 1 ? '' : 's'} remaining until must-fill-by deadline.`;
  }
  const bucket5 = Math.ceil(minutesCeiling / 5) * 5;
  return `Approximately ${bucket5} minutes remaining until must-fill-by deadline.`;
}
