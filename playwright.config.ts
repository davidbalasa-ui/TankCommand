import { defineConfig } from '@playwright/test';

const chromiumPath = process.env.PW_CHROMIUM_PATH;
const BASE_URL = 'http://127.0.0.1:4173';

export default defineConfig({
  testDir: './tests/e2e',
  // CI runners draw 1080p frames in software on two cores; the desktop project needs the headroom.
  timeout: process.env.CI ? 60_000 : 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    launchOptions: chromiumPath ? { executablePath: chromiumPath } : {},
  },
  webServer: {
    command: 'VITE_TEST_HOOK=1 npm run build && npm run preview -- --host 127.0.0.1',
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: 'phone',
      use: {
        browserName: 'chromium',
        viewport: { width: 915, height: 412 },
        hasTouch: true,
        isMobile: true,
      },
    },
    {
      name: 'tablet',
      use: {
        browserName: 'chromium',
        viewport: { width: 1280, height: 800 },
        hasTouch: true,
      },
    },
    {
      name: 'desktop',
      // Even at the low setting a 1080p software frame is the slowest in the suite, and GitHub's
      // runners vary by about 2x in speed: give desktop tests twice the default budget.
      timeout: process.env.CI ? 120_000 : 60_000,
      use: {
        browserName: 'chromium',
        viewport: { width: 1920, height: 1080 },
        // CI draws every frame in software. 1080p is five times the phone's pixels, and on the
        // slower runners a single frame took seconds, starving the page so that every in-match
        // desktop test timed out. Desktop runs at the player-selectable "low" graphics setting
        // (half render scale, no shadows); phone and tablet keep "auto", so the full-quality path
        // and the automatic quality drop stay covered there.
        storageState: {
          cookies: [],
          origins: [
            {
              origin: BASE_URL,
              localStorage: [{ name: 'setting.gameSettings', value: JSON.stringify({ graphicsQuality: 'low' }) }],
            },
          ],
        },
      },
    },
  ],
});
