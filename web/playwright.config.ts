import { defineConfig } from '@playwright/test';

/**
 * Local end-to-end run: the real `api` app (memory store, local workflow driver, simulated personas)
 * plus the Vite dev server pointed at it. No Google Cloud resource is used. All data is synthetic.
 */
// Relative to the repo root (the dev server runs with cwd ..).
const python =
  process.env.PYTHON ?? (process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: 'http://localhost:3000', trace: 'retain-on-failure' },
  webServer: [
    {
      command: `"${python}" -m evals.runners.dev_server --port 8080 --pace 0.4`,
      cwd: '..',
      url: 'http://127.0.0.1:8080/status',
      env: { ALLOWED_ORIGINS: 'http://localhost:3000' },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:3000',
      env: { VITE_API_BASE_URL: 'http://127.0.0.1:8080' },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
