const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

/**
 * E2E Test: Full workflow from homepage to transcription
 * 
 * Flow:
 * 1. Navigate to precisepouchtrack.com
 * 2. Click "Other Products" → "Audio Duplication Detection"
 * 3. Sign in with credentials
 * 4. Create new project with current date/time
 * 5. Upload audio file (01_ImprobableScheme_Ch01_raw.wav)
 * 6. Wait for transcription to complete (can take 30+ minutes)
 * 7. Capture screenshots at every stage
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

// Helper to wait for network idle (useful after navigation)
async function waitForNetworkIdle(page, timeout = 5000) {
  await page.waitForLoadState('networkidle', { timeout });
}

test.describe('Audio Upload and Transcription Flow', () => {
  test('complete upload and transcription workflow', async ({ page: initialPage }) => {
    let page = initialPage;
    // Set longer timeout for the entire test (2 hours)
    test.setTimeout(2 * 60 * 60 * 1000);

    try {
      // ═══════════════════════════════════════════════════════════════
      // STEP 1: Navigate to Homepage
      // ═══════════════════════════════════════════════════════════════
      console.log('Step 1: Navigating to precisepouchtrack.com...');
      await page.goto('https://www.precisepouchtrack.com/');
      await waitForNetworkIdle(page);
      await captureStep(page, 1, 'homepage');

    // ═══════════════════════════════════════════════════════════════
    // STEP 2: Click "Other Products"
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 2: Clicking "Other Products"...');
    await page.click('text=Other Products');
    await page.waitForTimeout(1000); // Wait for dropdown
    await captureStep(page, 2, 'other-products-dropdown');

    // ═══════════════════════════════════════════════════════════════
    // STEP 3: Click "Audio Duplicate Detection" link
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 3: Clicking "Audio Duplicate Detection" link...');
    // Find the link
    const audioLink = page.locator('a:has-text("Audio Duplicate Detection")').first();
    await audioLink.waitFor({ state: 'visible', timeout: 5000 });
    
    // Get the href to check if it opens in new tab
    const href = await audioLink.getAttribute('href');
    console.log('Link href:', href);
    const target = await audioLink.getAttribute('target');
    console.log('Link target:', target);
    
    // If it opens in a new tab, handle that
    if (target === '_blank') {
      const [newPage] = await Promise.all([
        page.context().waitForEvent('page'),
        audioLink.click()
      ]);
      await newPage.waitForLoadState('domcontentloaded');
      page = newPage; // Switch to the new page
      console.log('Current URL after click (new tab):', page.url());
    } else {
      // Regular navigation
      await Promise.all([
        page.waitForLoadState('domcontentloaded'),
        audioLink.click()
      ]);
      console.log('Current URL after click:', page.url());
    }
    
    // Wait for page to be ready - look for the Sign In button in header
    await page.getByRole('button', { name: /sign in/i }).first().waitFor({ state: 'visible', timeout: 10000 });
    await captureStep(page, 3, 'audio-app-landing');

    // ═══════════════════════════════════════════════════════════════
    // STEP 4: Click "Sign In" button on landing page
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 4: Clicking "Sign In" button...');
    // The landing page has Sign In buttons - click the first one (in header or main content)
    const signInButton = page.getByRole('button', { name: /sign in/i }).first();
    await signInButton.waitFor({ state: 'visible', timeout: 5000 });
    await signInButton.click();
    
    // Wait for navigation to login page
    await page.waitForLoadState('networkidle');
    await captureStep(page, 4, 'login-page');

    // ═══════════════════════════════════════════════════════════════
    // STEP 5: Enter credentials and submit
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 5: Entering credentials...');
    await page.fill('input[name="username"]', process.env.TEST_USERNAME || 'admin');
    await page.fill('input[name="password"]', process.env.TEST_PASSWORD || 'audioadmin123');
    await captureStep(page, 5, 'credentials-entered');
    
    await page.click('button[type="submit"]');
    
    // Wait for successful login (should redirect to projects page)
    await page.waitForURL(/projects/i, { timeout: 10000 });
    await waitForNetworkIdle(page);
    await captureStep(page, 6, 'logged-in-projects-page');

    // ═══════════════════════════════════════════════════════════════
    // STEP 6: Click "Create New Project"
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 6: Clicking "Create New Project"...');
    const createButton = page.locator('text=Create New Project').or(page.locator('button:has-text("Create")'));
    await createButton.waitFor({ state: 'visible', timeout: 5000 });
    await createButton.click();
    
    // Wait for modal/dialog
    await page.waitForTimeout(1000);
    await captureStep(page, 7, 'create-project-dialog');

    // ═══════════════════════════════════════════════════════════════
    // STEP 7: Enter project name (current date/time)
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 7: Entering project name...');
    const now = new Date();
    const projectName = `Test-${now.toISOString().replace(/[:.]/g, '-')}`;
    console.log(`   Project name: ${projectName}`);
    
    // Find the input field - try multiple selectors
    const projectInput = page.getByPlaceholder(/enter project title/i)
      .or(page.locator('input[type="text"]').first())
      .or(page.locator('input[name="name"]'))
      .or(page.locator('input[name="title"]'));
    
    await projectInput.waitFor({ state: 'visible', timeout: 5000 });
    await projectInput.click(); // Focus the input
    await projectInput.fill(projectName);
    console.log(`   Input filled with: ${projectName}`);
    await captureStep(page, 8, 'project-name-entered');
    
    // Submit create project form - wait a moment for button to be enabled
    await page.waitForTimeout(500);
    const submitButton = page.locator('button:has-text("Create Project")').first();
    await submitButton.waitFor({ state: 'visible', timeout: 5000 });
    console.log('   Clicking Create Project button...');
    await submitButton.click();
    console.log('   Button clicked, waiting for navigation...');
    
    // Wait for navigation to project detail page
    await page.waitForURL(/project\/\d+/i, { timeout: 10000 });
    await waitForNetworkIdle(page);
    await captureStep(page, 9, 'project-created');

    // ═══════════════════════════════════════════════════════════════
    // STEP 8: Scroll down to "Select Files" button
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 8: Scrolling to "Select Files"...');
    const selectFilesButton = page.locator('button:has-text("Select Files")').or(page.locator('text=Select Files'));
    await selectFilesButton.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await captureStep(page, 10, 'scrolled-to-select-files');

    // ═══════════════════════════════════════════════════════════════
    // STEP 9: Click "Select Files" to open file picker
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 9: Opening file picker...');
    
    // Set up file chooser handler BEFORE clicking
    const fileChooserPromise = page.waitForEvent('filechooser', { timeout: 10000 });
    await selectFilesButton.click();
    
    const fileChooser = await fileChooserPromise;
    await page.waitForTimeout(500);
    
    // Take screenshot after file dialog opens (will show the page, not the OS dialog)
    await captureStep(page, 11, 'file-picker-opened');

    // ═══════════════════════════════════════════════════════════════
    // STEP 10: Select the audio file (01_ImprobableScheme_Ch01_raw.wav)
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 10: Selecting audio file...');
    
    // Path to the audio file in Downloads folder
    const downloadsPath = path.join(process.env.USERPROFILE || process.env.HOME, 'Downloads');
    const audioFilePath = path.join(downloadsPath, '01_ImprobableScheme_Ch01_raw.wav');
    
    // Check if file exists
    if (!fs.existsSync(audioFilePath)) {
      console.error(`❌ File not found: ${audioFilePath}`);
      console.log('   Available files in Downloads:');
      const files = fs.readdirSync(downloadsPath);
      files.filter(f => f.startsWith('01_')).forEach(f => console.log(`      - ${f}`));
      throw new Error(`Audio file not found: ${audioFilePath}`);
    }
    
    console.log(`   File found: ${audioFilePath}`);
    await fileChooser.setFiles(audioFilePath);
    
    // Wait for file to be selected and start uploading
    await page.waitForTimeout(2000);
    await captureStep(page, 12, 'file-selected-uploading');

    // ═══════════════════════════════════════════════════════════════
    // STEP 11: Wait for transcription to complete (up to 30 minutes)
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 11: Waiting for transcription to complete...');
    console.log('   Browser will stay open. Checking every 5 minutes for up to 30 minutes...');
    
    // Set up dialog listener for "Transcription Complete!" alert
    let transcriptionComplete = false;
    let dialogMessage = '';
    
    page.on('dialog', async dialog => {
      dialogMessage = dialog.message();
      console.log(`   🔔 Dialog detected: ${dialogMessage}`);
      
      if (dialogMessage.includes('Transcription Complete!')) {
        console.log('   ✅ Transcription Complete dialog appeared!');
        transcriptionComplete = true;
        // Accept dialog FIRST (click OK)
        await dialog.accept();
        console.log('   ✅ Dialog accepted (clicked OK)');
      } else {
        await dialog.accept(); // Accept any other dialogs too
        console.log(`   ℹ️  Other dialog accepted: ${dialogMessage}`);
      }
    });
    
    // Look for the transcription progress dialog/indicator
    await page.waitForTimeout(3000); // Give upload time to start
    const transcriptionIndicator = page.locator('text=Transcribing Audio').or(page.locator('text=Loading Processing Software'));
    const indicatorVisible = await transcriptionIndicator.isVisible().catch(() => false);
    
    if (indicatorVisible) {
      console.log('   ⏳ Transcription started...');
      await captureStep(page, 13, 'transcription-in-progress');
    }
    
    // Poll every 5 minutes for up to 30 minutes
    const checkIntervalMs = 5 * 60 * 1000; // 5 minutes
    const maxWaitMs = 30 * 60 * 1000; // 30 minutes
    const maxChecks = Math.floor(maxWaitMs / checkIntervalMs);
    let checkCount = 0;
    
    while (!transcriptionComplete && checkCount < maxChecks) {
      checkCount++;
      const elapsedMinutes = checkCount * 5;
      console.log(`   Check ${checkCount}/${maxChecks}: Waiting 5 minutes... (${elapsedMinutes} min elapsed)`);
      
      // Wait 5 minutes
      await page.waitForTimeout(checkIntervalMs);
      
      // Take screenshot of current state
      if (!transcriptionComplete) {
        await captureStep(page, 13 + checkCount, `transcription-check-${elapsedMinutes}min`);
        console.log(`   📸 Screenshot captured at ${elapsedMinutes} minutes`);
      }
    }
    
    if (!transcriptionComplete) {
      console.warn('   ⚠️  Transcription did not complete within 30 minutes');
      console.warn('   Checking for transcribed file in table...');
      
      // Check if file already transcribed (dialog might have been missed)
      const transcribedBadge = page.locator('text=TRANSCRIBED').first();
      const badgeVisible = await transcribedBadge.isVisible().catch(() => false);
      
      if (badgeVisible) {
        console.log('   ✅ Found TRANSCRIBED status badge - proceeding!');
        transcriptionComplete = true;
      }
    }
    
    // Wait a moment after dialog is dismissed for page to update
    if (transcriptionComplete) {
      console.log('   Waiting for dialog to be fully dismissed and page to update...');
      await page.waitForTimeout(3000);
      await captureStep(page, 49, 'after-transcription-dialog-dismissed');
      console.log('   ✅ Ready to proceed to PDF upload');
    }

    // ═══════════════════════════════════════════════════════════════
    // STEP 12: After transcription - Upload PDF
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 12: Looking for Upload PDF button...');
    await page.waitForTimeout(2000);

    // Scroll to the bottom of the page so the Audio Files table is visible
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(1000);
    await captureStep(page, 50, 'scrolled-to-bottom-looking-for-pdf-button');

    // Click Refresh to make sure the table is up to date
    const refreshButton = page.locator('button:has-text("Refresh")').first();
    if (await refreshButton.isVisible().catch(() => false)) {
      await refreshButton.click();
      console.log('   ✅ Clicked Refresh button');
      await page.waitForTimeout(2000);
    }

    // Try multiple selector strategies for the "📄+ Upload PDF" label in the table row
    // It is a <label> element (not a button!) with class "pdf-upload-button"
    const uploadPdfButton = page.locator('label.pdf-upload-button').first();

    // If not immediately visible, scroll through the page in increments looking for it
    let pdfButtonFound = await uploadPdfButton.isVisible().catch(() => false);
    if (!pdfButtonFound) {
      console.log('   Not visible at bottom, scrolling through page...');
      for (let scrollY = 0; scrollY <= 3000; scrollY += 200) {
        await page.evaluate((y) => window.scrollTo(0, y), scrollY);
        await page.waitForTimeout(300);
        pdfButtonFound = await uploadPdfButton.isVisible().catch(() => false);
        if (pdfButtonFound) {
          console.log(`   Found Upload PDF label at scroll position ${scrollY}`);
          break;
        }
      }
    }

    await uploadPdfButton.waitFor({ state: 'visible', timeout: 10000 });
    await uploadPdfButton.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    console.log('   ✅ Found Upload PDF button');
    await captureStep(page, 51, 'upload-pdf-button-visible');

    // Click the Upload PDF button
    const pdfFileChooserPromise = page.waitForEvent('filechooser', { timeout: 10000 });
    await uploadPdfButton.click();
    console.log('   Clicked Upload PDF button');
    
    const pdfFileChooser = await pdfFileChooserPromise;
    await page.waitForTimeout(500);
    await captureStep(page, 52, 'pdf-file-picker-opened');
    
    // ═══════════════════════════════════════════════════════════════
    // STEP 13: Select the PDF file (DS0518_ImprobableScheme...)
    // ═══════════════════════════════════════════════════════════════
    console.log('Step 13: Selecting PDF file...');
    
    const pdfFilePath = path.join(downloadsPath, 'DS0518_ImprobableScheme_Hussey_M_RECORDABLE_USE.pdf');
    
    // Check if file exists
    if (!fs.existsSync(pdfFilePath)) {
      console.error(`❌ PDF file not found: ${pdfFilePath}`);
      console.log('   Available PDF files in Downloads:');
      const files = fs.readdirSync(downloadsPath);
      files.filter(f => f.toLowerCase().endsWith('.pdf') && f.startsWith('DS')).forEach(f => console.log(`      - ${f}`));
      throw new Error(`PDF file not found: ${pdfFilePath}`);
    }
    
    console.log(`   PDF file found: ${pdfFilePath}`);
    await pdfFileChooser.setFiles(pdfFilePath);
    
    // Wait for PDF upload to complete
    await page.waitForTimeout(3000);
    await captureStep(page, 53, 'pdf-uploaded');
    
    console.log('✅ Test complete! Audio uploaded, transcribed, and PDF uploaded!');
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
