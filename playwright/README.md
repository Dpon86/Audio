# Playwright E2E Tests for Audio Duplication Detection

Automated end-to-end tests for the PrecisePouchTrack Audio application with screenshot capture for user manual creation.

## Setup

### 1. Install Dependencies

```bash
cd playwright
npm install
npx playwright install chromium
```

### 2. Prepare Test Data

Ensure the test audio file exists in your Downloads folder:
- `C:\Users\YourName\Downloads\01_ImprobableScheme_Ch01_raw.wav`

(The test will automatically look for this file)

## Running Tests

### Run in headless mode (default)
```bash
npm test
```

### Run with browser visible (watch the test)
```bash
npm run test:headed
```

### Run in debug mode (step through test)
```bash
npm run test:debug
```

### Run with Playwright UI (interactive)
```bash
npm run test:ui
```

## Test Structure

```
playwright/
├── package.json                       # Dependencies
├── playwright.config.js               # Playwright configuration
├── tests/
│   └── 01-upload-and-transcribe.spec.js   # Main test file
├── user-manual-screenshots/           # Auto-generated screenshots
│   ├── step-01-homepage-*.png
│   ├── step-02-other-products-dropdown-*.png
│   ├── step-03-audio-app-landing-*.png
│   └── ... (all workflow steps)
└── test-results/                      # Test artifacts (videos, traces)
```

## What the Tests Do

### Test: `01-upload-and-transcribe.spec.js`

Full workflow from homepage to transcription completion:

1. ✅ Navigate to https://www.precisepouchtrack.com/
2. ✅ Click "Other Products" dropdown
3. ✅ Click "Audio Duplication Detection"
4. ✅ Click "Sign In"
5. ✅ Enter credentials (admin / <your-admin-password>)
6. ✅ Click "Create New Project"
7. ✅ Enter project name (current date/time)
8. ✅ Scroll to "Select Files" button
9. ✅ Open file picker
10. ✅ Select `01_ImprobableScheme_Ch01_raw.wav`
11. ✅ Wait for transcription dialog
12. ✅ Monitor progress (check every 5 minutes for up to 2 hours)
13. ✅ Capture final state

**Screenshot capture**: Every step is automatically saved to `user-manual-screenshots/` with timestamped filenames.

## Screenshots for User Manual

All screenshots are saved with the naming pattern:
```
step-{number}-{action}-{timestamp}.png
```

Example:
- `step-01-homepage-2026-03-23T14-30-15-123Z.png`
- `step-05-credentials-entered-2026-03-23T14-31-42-456Z.png`
- `step-13-transcription-progress-15min-2026-03-23T14-46-42-789Z.png`

Screenshots are full-page captures showing the entire browser window.

## Configuration

### Timeouts

The test is configured for long-running operations:

- **Test timeout**: 2 hours (for transcription)
- **Action timeout**: 30 seconds (clicks, fills, etc.)
- **Check interval**: 5 minutes (transcription progress)

### Browser

- Default: Chromium (Chrome)
- Viewport: 1920×1080
- HTTPS errors: Ignored (for self-signed certs)

## Viewing Test Results

After a test run:

```bash
npm run report
```

This opens the HTML test report with:
- Test status (passed/failed)
- Screenshots
- Videos (on failure)
- Network logs
- Console output

## Troubleshooting

### File not found error

If the test fails with "Audio file not found":
1. Check the Downloads folder path
2. Ensure the file is named exactly `01_ImprobableScheme_Ch01_raw.wav`
3. Update the path in the test if your Downloads folder is elsewhere

### Timeout errors

If transcription takes longer than 2 hours:
1. Increase `timeout` in `playwright.config.js`
2. Increase `maxChecks` in the test file

### Login issues

If login fails:
1. Verify credentials are still `admin` / `<your-admin-password>`
2. Check if the login page structure has changed
3. Run in debug mode: `npm run test:debug`

## Next Steps

To add more test scenarios:

1. Create `02-detect-duplicates.spec.js` — Test duplicate detection algorithms
2. Create `03-process-audio.spec.js` — Test audio processing and download
3. Create `04-pdf-comparison.spec.js` — Test PDF comparison flow

Each test will automatically capture screenshots for the user manual.
