// @ts-check
const { defineConfig, devices } = require('@playwright/test');

/**
 * @see https://playwright.dev/docs/test-configuration
 */
module.exports = defineConfig({
  testDir: './tests',
  
  // Maximum time one test can run (2 hours for long transcription/processing)
  timeout: 2 * 60 * 60 * 1000,
  
  // Maximum time for each assertion/action
  expect: {
    timeout: 30000
  },
  
  // Run tests in files in parallel
  fullyParallel: false,
  
  // Fail the build on CI if you accidentally left test.only
  forbidOnly: !!process.env.CI,
  
  // Retry on CI only
  retries: process.env.CI ? 2 : 0,
  
  // Reporter to use
  reporter: [
    ['html'],
    ['list']
  ],
  
  // Shared settings for all the projects below
  use: {
    // Base URL
    baseURL: 'https://www.precisepouchtrack.com',
    
    // Take screenshot on failure
    screenshot: 'only-on-failure',
    
    // Record trace on first retry
    trace: 'on-first-retry',
    
    // Record video on failure
    video: 'retain-on-failure',
    
    // Browser context options
    viewport: { width: 1920, height: 1080 },
    
    // Ignore HTTPS errors (if self-signed certs)
    ignoreHTTPSErrors: true,
  },

  // Configure projects for major browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Folder for test artifacts such as screenshots, videos, traces, etc.
  outputDir: 'test-results/',
  
  // Folder for test screenshots
  snapshotDir: 'screenshots/',
});
