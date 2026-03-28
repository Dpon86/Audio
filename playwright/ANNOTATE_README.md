# Screenshot Annotation Test

This test re-captures critical UI screenshots with visual annotations (red circles, arrows, and highlights) to help users identify key buttons and controls.

## What Gets Annotated

The following steps will be re-captured with visual highlights:

- **Step 55**: Duplicates tab (red box highlight)
- **Step 58**: Algorithm dropdown (red box highlight)  
- **Step 60**: Start Detection button (red box + arrow)
- **Step 63**: Align to Silence button (green box + arrow)
- **Step 66**: Select All button (purple box highlight)
- **Step 68**: Assemble button (orange box + arrow)

## Prerequisites

1. You must have an **existing project** with:
   - Audio file uploaded and transcribed
   - PDF script uploaded (optional but recommended)

2. The test will use these credentials (update in the test file if needed):
   - Username: `nickd`
   - Password: `Kermit1998`

## How to Run

### Option 1: Run with headed browser (see what's happening)

```powershell
cd playwright
npm run test:headed -- tests/03-annotate-key-steps.spec.js
```

### Option 2: Run headless (faster)

```powershell
cd playwright
npx playwright test tests/03-annotate-key-steps.spec.js
```

## What Happens

1. The test logs into the app
2. Opens the first available project
3. Selects the first audio file
4. Navigates through the duplicate detection workflow
5. At each critical step, it:
   - Adds a visual annotation (red circle/box around the UI element)
   - Waits 300ms for the animation to render
   - Takes the screenshot
   - Removes the annotation
6. New screenshots **replace** the old ones in `playwright/user-manual-screenshots/`

## Duration

- Full run: **5-15 minutes** (depends on whether detection needs to run)
- If detection is already complete on the project: **2-3 minutes**

## After Running

1. The new annotated screenshots will be in `playwright/user-manual-screenshots/`
2. Copy them to the frontend:
   ```powershell
   Copy-Item "user-manual-screenshots\step-5*.png" "..\frontend\audio-waveform-visualizer\public\user-manual-screenshots\" -Force
   Copy-Item "user-manual-screenshots\step-6*.png" "..\frontend\audio-waveform-visualizer\public\user-manual-screenshots\" -Force
   ```

3. Open [playwright/user-manual.html](../user-manual.html) in a browser to see the updated manual with annotated screenshots

## Customizing Annotations

Edit `tests/03-annotate-key-steps.spec.js` and modify the `captureStepWithAnnotation()` calls:

```javascript
await captureStepWithAnnotation(page, 60, 'before-start-detection', {
  selector: 'button:has-text("Start Detection")',
  options: {
    type: 'box',        // 'box' or 'circle'
    color: '#ef4444',   // Hex color
    thickness: 5,       // Border thickness in px
    pulse: true,        // Pulsing animation
    arrow: {            // Optional arrow
      from: 'left',     // 'top', 'bottom', 'left', 'right'
      length: 60        // Arrow length in px
    }
  }
});
```

## Troubleshooting

### "Element not found" warnings
The selector might be incorrect. Inspect the page and update the selector in the test.

### Screenshots look the same
Check the console output - if annotations aren't being added, the selector might not match any element.

### Test times out
Increase the timeout in the test file:
```javascript
test.setTimeout(60 * 60 * 1000); // 60 minutes
```
