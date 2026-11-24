import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/auth', workers: 1, retries: 0, timeout: 45000,
  reporter: 'list', outputDir: 'test-results/auth',
  use: {baseURL: 'http://127.0.0.1:3102', viewport: {width: 1360, height: 960},
    channel: process.env.PLAYWRIGHT_CHROME_CHANNEL || undefined, trace: 'retain-on-failure'},
  webServer: [
    {command: 'node tests/fixtures/auth-server.mjs', url: 'http://127.0.0.1:54330/__test/metrics', timeout: 20000},
    {command: 'node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3102',
      url: 'http://127.0.0.1:3102/login', timeout: 120000,
      env: {NEXT_PUBLIC_USE_MOCK: 'false', NEXT_PUBLIC_API_BASE_URL: '/api', NEXT_TELEMETRY_DISABLED: '1',
        NEXT_PUBLIC_SUPABASE_URL: 'http://127.0.0.1:54330', NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'test-provider-public-key'}},
  ],
});
