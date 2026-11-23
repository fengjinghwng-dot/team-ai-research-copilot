import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/browser', fullyParallel: false, workers: 1, retries: 0,
  timeout: 45000, reporter: 'list', outputDir: 'test-results',
  use: {baseURL: 'http://127.0.0.1:3101', viewport: {width: 1360, height: 960},
    channel: process.env.PLAYWRIGHT_CHROME_CHANNEL || undefined, trace: 'retain-on-failure'},
  webServer: {
    command: 'node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3101',
    url: 'http://127.0.0.1:3101/login', timeout: 120000, reuseExistingServer: false,
    env: {NEXT_PUBLIC_USE_MOCK: 'true', NEXT_PUBLIC_API_BASE_URL: '/api',
      NEXT_PUBLIC_SUPABASE_URL: 'https://example.supabase.co',
      NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'browser-test-placeholder', NEXT_TELEMETRY_DISABLED: '1'},
  },
});
