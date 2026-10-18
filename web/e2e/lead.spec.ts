import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

/** Tap-only journeys against the local api (memory store, local workflow driver). */

function watchConsole(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', (err) => errors.push(err.message));
  return errors;
}

async function expectNoSeriousA11y(page: Page, where: string): Promise<void> {
  const results = await new AxeBuilder({ page }).analyze();
  const bad = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
  expect(bad.map((v) => `${where}: ${v.id} (${v.impact}) ${v.nodes.length} node(s)`)).toEqual([]);
}

async function approve(page: Page): Promise<void> {
  await expect(page.getByTestId('readback')).toBeVisible({ timeout: 60_000 });
  await page.getByRole('button', { name: 'Approve plan' }).click();
}

test('S-017 runs to FILLED by tap, with real candidates, a rule warning and the timeline', async ({ page }) => {
  const errors = watchConsole(page);
  await page.goto('/');
  await expect(page.getByTestId('replay-banner')).toHaveCount(0);
  await page.getByRole('button', { name: /6:02am sick call/ }).click();

  await expect(page.getByTestId('plan-option').first()).toBeVisible({ timeout: 60_000 });
  const priya = page.getByTestId('rule-warning').filter({ hasText: 'SG-EA4-OT-CAP-72' });
  await expect(priya).toContainText('Priya: 70 of 72 overtime hours used this month.');
  await expect(priya.getByRole('link', { name: /SG-EA4-OT-CAP-72 source/ })).toHaveAttribute(
    'href',
    'https://www.mom.gov.sg/employment-practices/hours-of-work-overtime-and-rest-days'
  );
  await expect(page.getByTestId('replay-badge')).toHaveCount(0);
  await approve(page);

  await expect(page.getByTestId('gap-state')).toContainText('FILLED', { timeout: 90_000 });
  const offers = page.getByTestId('offer');
  await expect(offers.nth(0)).toContainText('Declined');
  await expect(offers.nth(1)).toContainText('Counter-offer');
  await expect(offers.nth(2)).toContainText('No reply');
  await expect(page.getByRole('region', { name: 'Shift gap at Bugis' }).getByText(/^Filled: /)).toBeVisible();
  await expect(page.getByTestId('replay-badge')).toHaveCount(0);
  await expectNoSeriousA11y(page, '/');

  await page.getByRole('button', { name: 'Trace replay', exact: true }).click();
  await expect(page).toHaveURL(/\/trace\/gap-\d+$/);
  await expect(page.getByTestId('chain-verification-status')).toContainText('Hash chain verified by the server');
  await expectNoSeriousA11y(page, '/trace/:gapId');

  await page.getByRole('button', { name: /How we know it/ }).click();
  await expect(page.getByTestId('release-gate-badge')).toContainText('No eval run yet');
  await expectNoSeriousA11y(page, '/evals');

  expect(errors).toEqual([]);
});

test('Nobody replies runs to ESCALATED, then RESOLVED after choosing a fallback', async ({ page }) => {
  const errors = watchConsole(page);
  await page.goto('/');
  await page.getByRole('button', { name: /Nobody replies/ }).click();
  await approve(page);
  await expect(page.getByTestId('gap-state')).toContainText('ESCALATED', { timeout: 90_000 });
  const first = page.getByRole('button', { name: /^1\. / });
  await expect(first).toBeVisible({ timeout: 30_000 });
  const label = (await first.textContent())?.replace(/^1\.\s*/, '') ?? '';
  await first.click();
  await expect(page.getByTestId('gap-state')).toContainText('RESOLVED', { timeout: 60_000 });
  await expect(page.getByTestId('gap-state')).toContainText(label);
  await expect(page.getByTestId('replay-badge')).toHaveCount(0);
  expect(errors).toEqual([]);
});
