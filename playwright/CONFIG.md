# Test Configuration

## Update Your Credentials

Before running the annotation test, update the credentials in `tests/03-annotate-key-steps.spec.js`:

```javascript
// Login
await page.fill('input[name="username"]', 'YOUR_USERNAME_HERE');
await page.fill('input[name="password"]', 'YOUR_PASSWORD_HERE');

```

Replace:
- `YOUR_USERNAME_HERE` with your actual username
- `YOUR_PASSWORD_HERE` with your actual password

## Quick Setup

Edit line 25-26 of `tests/03-annotate-key-steps.spec.js` with your credentials, then run:

```powershell
cd playwright
npx playwright test tests/03-annotate-key-steps.spec.js --headed
```

## What The Test Does

1. Logs into audio.precisepouchtrack.com
2. Opens your first project
3. Navigates to Duplicates tab
4. Captures screenshots with visual annotations:
   - Red boxes around buttons
   - Arrows pointing to critical controls
   - Pulsing animations
5. Saves annotated screenshots to `user-manual-screenshots/`

## Duration: 5-15 minutes
