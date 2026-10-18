import { defineConfig } from '@playwright/test';

/**
 * Production smoke test against the deployed app. Creates real gaps (synthetic data) in the
 * project's Firestore and starts real Cloud Workflows executions. Run only when that is intended:
 *   E2E_BASE_URL=https://PROJECT_ID.web.app npx playwright test -c playwright.prod.config.ts
 */
const baseURL = process.env.E2E_BASE_URL;
if (!baseURL) throw new Error('Set E2E_BASE_URL to the Hosting URL');

export default defineConfig({
  testDir: './e2e-prod',
  timeout: 20 * 60_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: { baseURL, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
});
