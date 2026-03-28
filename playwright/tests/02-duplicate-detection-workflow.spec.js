const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

/**
 * E2E Test: Duplicate Detection Workflow After PDF Upload
 * 
 * Prerequisites:
 * - Project created
 * - Audio file uploaded and transcribed
 * - PDF uploaded
 * 
 * Flow:
 * 1. Scroll up and click "Duplicates" button
 * 2. Scroll down
 * 3. Click dropdown (showing "Retry-aware + PDF")
 * 4. Select "Multi-pass highest"
 * 5. Click "Start Detection"
 * 6. Click OK on alert
 * 7. Wait for "Clear" button to appear
 * 8. Scroll down and click "Align to silence" button
 * 9. Wait
 * 10. Click OK on alert
 * 11. Scroll down and click "Select all" then "Assemble" buttons
 */

// Helper to create screenshot folder
const screenshotDir = path.join(__dirname, '..', 'user-manual-screenshots');
if (!fs.existsSync(screenshotDir)) {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

// Helper to save screenshot with step number
async function captureStep(page, stepNumber, stepName) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `step-${stepNumber.toString().padStart(2, '0')}-${stepName}-${timestamp}.png`;
  const filepath = path.join(screenshotDir, filename);
  await page.screenshot({ path: filepath, fullPage: true });
  console.log(`📸 Screenshot saved: ${filename}`);
  return filepath;
}

test.describe('Duplicate Detection and Assembly Workflow', () => {
  test('PDF uploaded to final assembly', async ({ page }) => {
    // Set longer timeout (1 hour for detection + alignment)
    test.setTimeout(60 * 60 * 1000);

    try {
      // ═══════════════════════════════════════════════════════════════
      // SETUP 1: Navigate to audio app
      // ═══════════════════════════════════════════════════════════════
      console.log('Setup 1: Navigating to audio app...');
      await page.goto('https://audio.precisepouchtrack.com/');
      await page.waitForLoadState('networkidle');
      await captureStep(page, 1, 'audio-app-landing');

      // ═══════════════════════════════════════════════════════════════
      // SETUP 2: Sign in
      // ═══════════════════════════════════════════════════════════════
      console.log('Setup 2: Signing in...');
      const signInButton = page.getByRole('button', { name: /sign in/i }).first();
      await signInButton.waitFor({ state: 'visible', timeout: 10000 });
      await signInButton.click();

      await page.waitForLoadState('networkidle');
      await captureStep(page, 2, 'login-page');

      await page.fill('input[name="username"]', process.env.TEST_USERNAME || 'admin');
      await page.fill('input[name="password"]', process.env.TEST_PASSWORD || 'audioadmin123');
      await page.click('button[type="submit"]');

      await page.waitForURL(/projects/i, { timeout: 10000 });
      await page.waitForLoadState('networkidle');
      console.log('   ✅ Signed in');
      await captureStep(page, 3, 'projects-page');

      // ═══════════════════════════════════════════════════════════════
      // SETUP 3: Open the most recent project (first card in the list)
      // ═══════════════════════════════════════════════════════════════
      console.log('Setup 3: Opening most recent project...');

      // Wait for project cards to load
      const firstProject = page.locator('div.project-card').first();
      await firstProject.waitFor({ state: 'visible', timeout: 10000 });

      // Log the project title so we know which one was opened
      const projectTitle = await firstProject.locator('h3').first().innerText().catch(() => 'unknown');
      console.log(`   Opening project: "${projectTitle}"`);

      await firstProject.click();
      await page.waitForURL(/project\/\d+/i, { timeout: 10000 });
      await page.waitForLoadState('networkidle');
      console.log('   ✅ Project opened:', page.url());
      await captureStep(page, 4, 'project-page-opened');

      // ═══════════════════════════════════════════════════════════════
      // SETUP 4: Scroll down and click the audio file row to select it
      // ═══════════════════════════════════════════════════════════════
      console.log('Setup 4: Selecting the audio file...');

      // Scroll down to the Audio Files table
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(1000);

      // Click the file row - it has title="Click to select this file for use in other tabs"
      const audioFileRow = page.locator('tr[title="Click to select this file for use in other tabs"]').first();
      await audioFileRow.waitFor({ state: 'visible', timeout: 10000 });
      await audioFileRow.scrollIntoViewIfNeeded();
      await page.waitForTimeout(500);
      await captureStep(page, 5, 'audio-file-row-visible');

      await audioFileRow.click();
      console.log('   ✅ Clicked audio file row to select it');
      await page.waitForTimeout(1000);
      await captureStep(page, 6, 'audio-file-selected');

      // Scroll back to top so the navigation tabs are visible
      console.log('   Scrolling back to top to see tabs...');
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(500);
      await captureStep(page, 7, 'scrolled-back-to-top-tabs-visible');

      // ═══════════════════════════════════════════════════════════════
      // STEP 1: Scroll up and click "Duplicates" tab
      // ═══════════════════════════════════════════════════════════════
      console.log('Step 1: Scrolling up and clicking Duplicates tab...');
    
    // Scroll to top first
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(500);
    
    // Look for Duplicates tab - it's a navigation tab, not a button
    const duplicatesTab = page.locator('text=Duplicates').first();
    
    await duplicatesTab.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await captureStep(page, 55, 'duplicates-tab-visible');
    
    await duplicatesTab.click();
    console.log('   ✅ Clicked Duplicates tab');
    
    // Wait for page to update after clicking
    await page.waitForTimeout(2000);
    await captureStep(page, 56, 'after-duplicates-clicked');

    // ═══════════════════════════════════════════════════════════════
    // STEP 2: Scroll down
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 2: Scrolling down...');
    await page.evaluate(() => window.scrollBy(0, 400));
    await page.waitForTimeout(500);
    await captureStep(page, 57, 'scrolled-down');

    // ═══════════════════════════════════════════════════════════════
    // STEP 3 & 4: Click dropdown and select "Multi-Pass Best (Highest Recall)"
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 3: Clicking detection mode dropdown...');
    
    // The select has no id/name but sits inside the algorithm controls row
    // It is a plain <select> with option values like 'windowed_retry_pdf', 'multi_pass_best', etc.
    const detectionDropdown = page.locator('select').filter({ hasText: /Retry-Aware|Multi-Pass/ }).first();
    
    await detectionDropdown.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await captureStep(page, 58, 'dropdown-before-selection');
    
    // ═══════════════════════════════════════════════════════════════
    // STEP 4: Select "Multi-Pass Best (Highest Recall)"
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 4: Selecting "Multi-Pass Best (Highest Recall)"...');
    
    // Select by option value (most reliable - exact value from source code)
    await detectionDropdown.selectOption({ value: 'multi_pass_best' });
    
    console.log('   ✅ Selected Multi-Pass Best (Highest Recall)');
    
    await page.waitForTimeout(500);
    await captureStep(page, 59, 'multi-pass-selected');

    // ═══════════════════════════════════════════════════════════════
    // STEP 5: Click "▶ Start Detection" button
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 5: Clicking Start Detection button...');
    
    // Green button with "▶ Start Detection" or just "Start Detection"
    const startDetectionButton = page.locator('button:has-text("Start Detection")').first();
    
    await startDetectionButton.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await captureStep(page, 60, 'before-start-detection');
    
    await startDetectionButton.click();
    console.log('   ✅ Clicked Start Detection');

    // ═══════════════════════════════════════════════════════════════
    // STEP 6: Click OK on alert box
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 6: Waiting for alert and clicking OK...');
    
    let alertHandled = false;
    
    page.once('dialog', async dialog => {
      console.log(`   🔔 Alert detected: ${dialog.message()}`);
      await dialog.accept();
      console.log('   ✅ Alert accepted (clicked OK)');
      alertHandled = true;
    });
    
    // Wait for alert to appear and be handled
    await page.waitForTimeout(2000);
    
    if (alertHandled) {
      console.log('   Alert was handled successfully');
    } else {
      console.log('   ⚠️  No alert appeared (may have been auto-dismissed)');
    }
    
    await captureStep(page, 61, 'after-detection-started');

    // ═══════════════════════════════════════════════════════════════
    // STEP 7: Wait for "🗑 Clear Results" button to appear (but don't press)
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 7: Waiting for Clear Results button to appear...');
    console.log('   (Detection is processing, this may take several minutes)');
    
    // Red button with "🗑 Clear Results" or just "Clear Results"
    const clearButton = page.locator('button:has-text("Clear Results")').first();
    
    // Poll for Clear Results button with timeout (e.g., 15 minutes max)
    await clearButton.waitFor({ state: 'visible', timeout: 15 * 60 * 1000 });
    
    console.log('   ✅ Clear Results button appeared - detection complete!');
    await captureStep(page, 62, 'clear-results-button-visible-detection-complete');

    // ═══════════════════════════════════════════════════════════════
    // STEP 8: Scroll down and click "Align to silence" button
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 8: Scrolling down to Align to silence button...');
    
    const alignButton = page.locator('button:has-text("Align to silence")')
      .or(page.locator('button:has-text("Align to Silence")'))
      .or(page.locator('[data-testid="align-to-silence-button"]'))
      .first();
    
    await alignButton.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await captureStep(page, 63, 'align-to-silence-button-visible');
    
    await alignButton.click();
    console.log('   ✅ Clicked Align to silence button');

    // ═══════════════════════════════════════════════════════════════
    // STEP 9: Wait for processing
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 9: Waiting for alignment to process...');
    await page.waitForTimeout(2000);
    await captureStep(page, 64, 'alignment-processing');

    // ═══════════════════════════════════════════════════════════════
    // STEP 10: Click OK on "Alignment Complete!" alert box
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 10: Waiting for "Alignment Complete!" alert and clicking OK...');
    
    let alignmentAlertHandled = false;
    
    page.once('dialog', async dialog => {
      const message = dialog.message();
      console.log(`   🔔 Alert detected: ${message}`);
      
      if (message.includes('Alignment Complete!')) {
        console.log('   ✅ Alignment Complete! alert detected');
      }
      
      await dialog.accept();
      console.log('   ✅ Alert accepted (clicked OK)');
      alignmentAlertHandled = true;
    });
    
    // Wait for alert to appear (with generous timeout - alignment can take time)
    await page.waitForTimeout(10000);
    
    if (alignmentAlertHandled) {
      console.log('   ✅ Alignment completion alert handled');
    } else {
      console.log('   ⚠️  No alert appeared yet (alignment may still be processing)');
      // Wait a bit more and check for dialog
      await page.waitForTimeout(5000);
    }
    
    await captureStep(page, 65, 'after-alignment-complete');

    // ═══════════════════════════════════════════════════════════════
    // STEP 11: Scroll down and click "Select all" button
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 11: Looking for Select all button...');
    
    const selectAllButton = page.locator('button:has-text("Select all")')
      .or(page.locator('button:has-text("Select All")'))
      .or(page.locator('[data-testid="select-all-button"]'))
      .first();
    
    // Try to find the button, scroll down if not visible
    const selectAllVisible = await selectAllButton.isVisible().catch(() => false);
    
    if (!selectAllVisible) {
      console.log('   Select all button not visible, scrolling down...');
      await page.evaluate(() => window.scrollBy(0, 400));
      await page.waitForTimeout(500);
    }
    
    await selectAllButton.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await captureStep(page, 66, 'select-all-button-visible');
    
    await selectAllButton.click();
    console.log('   ✅ Clicked Select all button');
    
    await page.waitForTimeout(1000);
    await captureStep(page, 67, 'after-select-all');

    // ═══════════════════════════════════════════════════════════════
    // STEP 12: Click "Assemble" button
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 12: Looking for Assemble button...');
    
    const assembleButton = page.locator('button:has-text("Assemble")')
      .or(page.locator('[data-testid="assemble-button"]'))
      .first();
    
    // Try to find the button, scroll down if not visible
    const assembleVisible = await assembleButton.isVisible().catch(() => false);
    
    if (!assembleVisible) {
      console.log('   Assemble button not visible, scrolling down...');
      await page.evaluate(() => window.scrollBy(0, 200));
      await page.waitForTimeout(500);
    }
    
    await assembleButton.waitFor({ state: 'visible', timeout: 5000 });
    await captureStep(page, 68, 'before-assemble');

    // Handle the "Server-Side Assembly... Continue?" confirm dialog BEFORE clicking
    page.once('dialog', async dialog => {
      console.log(`   🔔 Confirm dialog: ${dialog.message().split('\n')[0]}`);
      await dialog.accept(); // Click OK
      console.log('   ✅ Confirmed assembly (clicked OK)');
    });

    await assembleButton.click();
    console.log('   ✅ Clicked Assemble button');

    // Wait for assembly to start (Assembling Audio... spinner appears)
    await page.waitForTimeout(3000);
    await captureStep(page, 69, 'assembling-audio-in-progress');
    console.log('   ⏳ Assembly in progress, waiting for completion...');

    // ═══════════════════════════════════════════════════════════════
    // STEP 13: Wait for assembly completion alert and click OK
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 13: Waiting for assembly completion alert...');

    let assemblyComplete = false;

    page.once('dialog', async dialog => {
      const message = dialog.message();
      console.log(`   🔔 Alert detected: ${message.split('\n')[0]}`);
      if (message.includes('assembly complete') || message.includes('Assembly Complete') || message.includes('Assembly is still running')) {
        console.log('   ✅ Assembly completion alert detected');
      }
      await dialog.accept();
      console.log('   ✅ Alert accepted (clicked OK)');
      assemblyComplete = true;
    });

    // Wait up to 10 minutes for server assembly to complete
    const maxWaitMs = 10 * 60 * 1000;
    const pollInterval = 5000;
    let elapsed = 0;

    while (!assemblyComplete && elapsed < maxWaitMs) {
      await page.waitForTimeout(pollInterval);
      elapsed += pollInterval;
      if (!assemblyComplete) {
        console.log(`   ⏳ Still assembling... (${Math.round(elapsed / 1000)}s elapsed)`);
        await captureStep(page, 70, `assembly-wait-${Math.round(elapsed / 1000)}s`);
      }
    }

    if (!assemblyComplete) {
      console.warn('   ⚠️  Assembly alert not detected within timeout - checking Results tab...');
    }

    await page.waitForTimeout(2000);
    await captureStep(page, 71, 'after-assembly-complete');

    // ═══════════════════════════════════════════════════════════════
    // STEP 14: Confirm Results tab is now active
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 14: Confirming Results tab is active...');

    // App should auto-switch to Results tab after assembly
    const resultsTab = page.locator('text=Results').first();
    await resultsTab.waitFor({ state: 'visible', timeout: 10000 });
    console.log('   ✅ Results tab is visible');

    await page.waitForTimeout(2000);
    await captureStep(page, 72, 'results-tab-active');
    
    console.log('✅ Workflow complete! All steps executed successfully!');
    console.log(`📸 All screenshots saved to: ${screenshotDir}`);
    
    } catch (error) {
      // ═══════════════════════════════════════════════════════════════
      // ERROR HANDLING: Capture screenshot before test fails
      // ═══════════════════════════════════════════════════════════════
      console.error('❌ Test failed with error:', error.message);
      
      // Capture failure screenshot
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const errorFilename = `ERROR-${timestamp}.png`;
      const errorPath = path.join(screenshotDir, errorFilename);
      
      try {
        await page.screenshot({ path: errorPath, fullPage: true });
        console.log(`📸 Error screenshot saved: ${errorFilename}`);
        console.log(`   Full path: ${errorPath}`);
      } catch (screenshotError) {
        console.error('   Failed to capture error screenshot:', screenshotError.message);
      }
      
      // Re-throw the error so the test still fails
      throw error;
    }
  });
});
