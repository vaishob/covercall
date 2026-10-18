import { defineConfig } from '@playwright/test';

/**
 * Voice checks against a deployed preview (fake microphone). Spends one Live token per session.
 *   E2E_BASE_URL=https://PROJECT--voice-xxxx.web.app npx playwright test -c playwright.voice.config.ts
 */
const baseURL = process.env.E2E_BASE_URL;
if (!baseURL) throw new Error('Set E2E_BASE_URL to the preview channel URL');

export default defineConfig({
  testDir: './e2e-voice',
  timeout: 3 * 60_000,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    permissions: ['microphone'],
    launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] },
  },
});
