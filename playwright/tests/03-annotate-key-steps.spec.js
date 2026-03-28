const { test, expect } = require('@playwright/test');
const { captureStepWithAnnotation } = require('./helpers/screenshot-annotator');

/**
 * Re-capture critical UI steps with visual annotations
 * This test will replace existing screenshots with annotated versions
 * highlighting key buttons, tabs, and controls
 */

test.describe('Re-capture Screenshots with Annotations', () => {
  test('annotate critical UI interaction steps', async ({ page }) => {
    test.setTimeout(30 * 60 * 1000); // 30 minutes

    try {
      console.log('🎯 Starting annotation test - will re-capture key screenshots with visual highlights...');

      // ═══════════════════════════════════════════════════════════════
      // SETUP: Navigate to the app and login
      // ═══════════════════════════════════════════════════════════════
      console.log('Setup: Navigating to audio app and logging in...');
      await page.goto('https://audio.precisepouchtrack.com/');
      await page.waitForLoadState('networkidle');

      // Login
      await page.fill('input[name="username"]', 'admin');
      await page.fill('input[name="password"]', 'audioadmin123');
      await page.click('button[type="submit"]');
      
      // Wait for redirect to projects page
      await page.waitForURL(/projects/i, { timeout: 10000 });
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      console.log('✓ Logged in successfully');

      // ═══════════════════════════════════════════════════════════════
      // Navigate to existing project
      // ═══════════════════════════════════════════════════════════════
      console.log('Opening existing project...');
      
      // Wait for project cards to load
      const firstProject = page.locator('div.project-card').first();
      await firstProject.waitFor({ state: 'visible', timeout: 10000 });
      
      // Log which project we're opening
      const projectTitle = await firstProject.locator('h3').first().innerText().catch(() => 'unknown');
      console.log(`   Opening project: "${projectTitle}"`);

      // Click the first project card
      await firstProject.click();
      await page.waitForURL(/project\/\d+/i, { timeout: 10000 });
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      console.log('✓ Project opened');

      // ═══════════════════════════════════════════════════════════════
      // Select audio file (needed for duplicate detection)
      // ═══════════════════════════════════════════════════════════════
      console.log('Selecting audio file...');
      
      // Wait for the file table to load
      await page.waitForSelector('table, .file-list, tbody', { timeout: 10000 });
      await page.waitForTimeout(1000);

      // Find and click the first audio file row
      const audioFileRow = page.locator('tr[data-file-id], tbody tr').first();
      const rowCount = await audioFileRow.count();
      
      if (rowCount > 0) {
        await audioFileRow.click();
        await page.waitForTimeout(1000);
        console.log('✓ Audio file selected');
      } else {
        console.log('⚠️  No audio files found - continuing anyway');
      }

      // ═══════════════════════════════════════════════════════════════
      // ANNOTATED STEP 55: Duplicates Tab (with highlight)
      // ═══════════════════════════════════════════════════════════════
      console.log('📸 Step 55: Capturing Duplicates tab with annotation...');
      
      // Scroll to top to make tabs visible
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(500);

      await captureStepWithAnnotation(page, 55, 'duplicates-tab-visible', {
        selector: '[data-tab="duplicates"], button:has-text("Duplicates")',
        options: {
          type: 'box',
          color: '#ef4444',
          thickness: 4,
          pulse: true,
        }
      });

      // ═══════════════════════════════════════════════════════════════
      // Click Duplicates Tab
      // ═══════════════════════════════════════════════════════════════
      console.log('Clicking Duplicates tab...');
      const duplicatesTab = page.locator('[data-tab="duplicates"], button:has-text("Duplicates")').first();
      await duplicatesTab.waitFor({ state: 'visible', timeout: 10000 });
      await duplicatesTab.click();
      await page.waitForTimeout(2000);

      // ═══════════════════════════════════════════════════════════════
      // ANNOTATED STEP 56: After Duplicates Clicked
      // ═══════════════════════════════════════════════════════════════
      console.log('📸 Step 56: After duplicates clicked...');
      await captureStepWithAnnotation(page, 56, 'after-duplicates-clicked', null);

      // ═══════════════════════════════════════════════════════════════
      // Scroll down to controls
      // ═══════════════════════════════════════════════════════════════
      await page.evaluate(() => window.scrollBy(0, 400));
      await page.waitForTimeout(500);

      await captureStepWithAnnotation(page, 57, 'scrolled-down', null);

      // ═══════════════════════════════════════════════════════════════
      // ANNOTATED STEP 58: Algorithm Dropdown (with highlight)
      // ═══════════════════════════════════════════════════════════════
      console.log('📸 Step 58: Capturing algorithm dropdown with annotation...');
      
      await captureStepWithAnnotation(page, 58, 'dropdown-before-selection', {
        selector: 'select[id*="algorithm"], select.algorithm-select, select:has(option:has-text("Multi-pass"))',
        options: {
          type: 'box',
          color: '#ef4444',
          thickness: 4,
          pulse: true,
        }
      });

      // ═══════════════════════════════════════════════════════════════
      // Select Multi-pass algorithm
      // ═══════════════════════════════════════════════════════════════
      console.log('Selecting Multi-pass algorithm...');
      const algorithmSelect = page.locator('select').first();
      await algorithmSelect.selectOption({ label: /multi.*pass/i });
      await page.waitForTimeout(1000);

      await captureStepWithAnnotation(page, 59, 'multi-pass-selected', null);

      // ═══════════════════════════════════════════════════════════════
      // ANNOTATED STEP 60: Start Detection Button (with highlight + arrow)
      // ═══════════════════════════════════════════════════════════════
      console.log('📸 Step 60: Capturing Start Detection button with annotation...');
      
      await captureStepWithAnnotation(page, 60, 'before-start-detection', {
        selector: 'button:has-text("Start Detection"), button:has-text("Detect Duplicates")',
        options: {
          type: 'box',
          color: '#ef4444',
          thickness: 5,
          pulse: true,
          arrow: { from: 'left', length: 60 }
        }
      });

      // ═══════════════════════════════════════════════════════════════
      // Click Start Detection (if not already run)
      // ═══════════════════════════════════════════════════════════════
      const startDetectionBtn = page.locator('button:has-text("Start Detection"), button:has-text("Detect Duplicates")').first();
      
      // Check if detection already complete
      const clearButton = page.locator('button:has-text("Clear Results"), button:has-text("Clear")');
      const isDetectionComplete = await clearButton.count() > 0;

      if (!isDetectionComplete) {
        console.log('Starting detection...');
        await startDetectionBtn.click();
        
        // Handle confirmation dialog if it appears
        page.on('dialog', async dialog => {
          console.log('Confirming dialog:', dialog.message());
          await dialog.accept();
        });

        await page.waitForTimeout(2000);
        
        // Wait for detection to complete (look for Clear button or results)
        console.log('Waiting for detection to complete...');
        await page.waitForSelector('button:has-text("Clear Results"), button:has-text("Clear"), button:has-text("Align")', {
          timeout: 10 * 60 * 1000 // 10 minutes
        });
        
        console.log('✓ Detection complete');
      } else {
        console.log('✓ Detection already complete');
      }

      await page.waitForTimeout(1000);
      await captureStepWithAnnotation(page, 62, 'clear-results-button-visible-detection-complete', null);

      // ═══════════════════════════════════════════════════════════════
      // ANNOTATED STEP 63: Align to Silence Button (with highlight)
      // ═══════════════════════════════════════════════════════════════
      console.log('📸 Step 63: Capturing Align to Silence button with annotation...');
      
      await captureStepWithAnnotation(page, 63, 'align-to-silence-button-visible', {
        selector: 'button:has-text("Align to Silence"), button:has-text("Align")',
        options: {
          type: 'box',
          color: '#10b981',
          thickness: 5,
          pulse: true,
          arrow: { from: 'left', length: 60 }
        }
      });

      // Click Align to Silence
      const alignBtn = page.locator('button:has-text("Align to Silence"), button:has-text("Align")').first();
      if (await alignBtn.count() > 0) {
        console.log('Clicking Align to Silence...');
        await alignBtn.click();
        await page.waitForTimeout(2000);
        
        // Wait for alignment to complete
        console.log('Waiting for alignment to complete...');
        await page.waitForTimeout(15000); // Alignment usually takes 10-30 seconds
        
        // Handle completion dialog
        page.on('dialog', async dialog => {
          console.log('Alignment complete dialog:', dialog.message());
          await dialog.accept();
        });

        await page.waitForTimeout(2000);
        console.log('✓ Alignment complete');
      }

      await captureStepWithAnnotation(page, 65, 'after-alignment-complete', null);

      // ═══════════════════════════════════════════════════════════════
      // ANNOTATED STEP 66: Select All Button (with highlight)
      // ═══════════════════════════════════════════════════════════════
      console.log('📸 Step 66: Capturing Select All button with annotation...');
      
      await captureStepWithAnnotation(page, 66, 'select-all-button-visible', {
        selector: 'button:has-text("Select All")',
        options: {
          type: 'box',
          color: '#8b5cf6',
          thickness: 4,
          pulse: true,
        }
      });

      // Click Select All
      const selectAllBtn = page.locator('button:has-text("Select All")').first();
      if (await selectAllBtn.count() > 0) {
        await selectAllBtn.click();
        await page.waitForTimeout(1000);
        console.log('✓ Selected all duplicates');
      }

      await captureStepWithAnnotation(page, 67, 'after-select-all', null);

      // ═══════════════════════════════════════════════════════════════
      // ANNOTATED STEP 68: Assemble Button (with highlight + arrow)
      // ═══════════════════════════════════════════════════════════════
      console.log('📸 Step 68: Capturing Assemble button with annotation...');
      
      await captureStepWithAnnotation(page, 68, 'before-assemble', {
        selector: 'button:has-text("Assemble"), button:has-text("Confirm Deletions")',
        options: {
          type: 'box',
          color: '#f59e0b',
          thickness: 5,
          pulse: true,
          arrow: { from: 'bottom', length: 50 }
        }
      });

      console.log('✅ All annotated screenshots captured successfully!');
      console.log('📁 Screenshots saved to: playwright/user-manual-screenshots/');

    } catch (error) {
      console.error('❌ Error during annotation test:', error);
      throw error;
    }
  });
});
