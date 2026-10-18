import { defineConfig } from '@playwright/test';

/**
 * Local end-to-end run: the real `api` app (memory store, local workflow driver, simulated personas)
 * plus the Vite dev server pointed at it. No Google Cloud resource is used. All data is synthetic.
 */
// Relative to the repo root (the dev server runs with cwd ..).
const python =
  process.env.PYTHON ?? (process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');

// Ports can be moved when 8080/3000 are busy: E2E_API_PORT, E2E_WEB_PORT.
const apiPort = process.env.E2E_API_PORT ?? '8080';
const webPort = process.env.E2E_WEB_PORT ?? '3000';

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: `http://localhost:${webPort}`, trace: 'retain-on-failure' },
  webServer: [
    {
      command: `"${python}" -m evals.runners.dev_server --port ${apiPort} --pace 0.4`,
      cwd: '..',
      url: `http://127.0.0.1:${apiPort}/status`,
      env: { ALLOWED_ORIGINS: `http://localhost:${webPort}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npx vite --port ${webPort} --host 0.0.0.0`,
      url: `http://localhost:${webPort}`,
      env: { VITE_API_BASE_URL: `http://127.0.0.1:${apiPort}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
