import { expect, test, type Page } from '@playwright/test';

/** Preview checks: a Live session opens with a fake mic; the text fallback works; no console errors. */

function watchConsole(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', (err) => errors.push(err.message));
  return errors;
}

test('hands-free opens a Gemini Live session from an ephemeral token', async ({ page }) => {
  const errors = watchConsole(page);
  const token = page.waitForResponse((r) => r.url().endsWith('/live/token'));
  await page.goto('/');
  await page.getByRole('button', { name: 'Hands-free' }).click();
  const resp = await token;
  expect(resp.status()).toBe(200);
  const body = await resp.json();
  expect(body.model_id).toBe('gemini-3.8-live');
  expect(body.api_version).toBe('v1beta');
  expect(Object.keys(body).sort()).toEqual(['api_version', 'expires_at', 'model_id', 'new_session_expires_at', 'token']);
  await expect(page.getByText(/Live session active \(gemini-3\.8-live, v1beta ephemeral token\)/)).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(5_000); // keep the socket open: no error or close in the first seconds
  await expect(page.getByText(/Live session active/)).toBeVisible();
  await page.getByRole('button', { name: 'Text', exact: true }).click();
  expect(errors).toEqual([]);
});

test('text mode works without a voice session', async ({ browser }) => {
  const context = await browser.newContext({ permissions: [] });
  const page = await context.newPage();
  const errors = watchConsole(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Text', exact: true }).click();
  const input = page.getByPlaceholder(/Type command/);
  await input.fill('hello');
  await input.press('Enter');
  await expect(page.getByText(/Typed absence reports are not parsed in the browser/)).toBeVisible();
  expect(errors).toEqual([]);
  await context.close();
});
