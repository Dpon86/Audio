# Security & Code Review Report
**Project:** Audio Duplicate Detection  
**Reviewer:** GitHub Copilot (Senior Developer Analysis)  
**Date:** March 28, 2026  
**Scope:** Full codebase — backend (Django/Celery), frontend (React), Playwright tests, infrastructure (Docker/deployment)

---

## Executive Summary

The application has solid core functionality but contains **6 critical security vulnerabilities** that are exploitable today with no further access required. The most urgent is a live secret key committed to the repository and a production environment file that is not gitignored. These must be addressed before the next `git push`.

Total issues found: **28**  
- 🔴 Critical: 6 — ✅ All resolved (2026-03-28)
- 🟠 High: 6 — ✅ All resolved (2026-03-28)
- 🟡 Medium: 9 — ✅ All resolved (2026-03-28)
- 🔵 Low: 7 — ✅ 5 resolved (2026-03-28), 2 require manual steps (L1, L6)

---

## 🔴 CRITICAL — ✅ All Resolved (2026-03-28)

---

### ✅ C1. Live OpenAI API Key Committed to Repository
**File:** `backend/.env`  
**Risk:** Financial — anyone with repo access can use this key and bill charges to the account.

The `.env` file contains a live `sk-proj-...` OpenAI API key. While `.env` itself may be gitignored, `.env.production` (see C2) is not, meaning the key could be exposed at any time.

**Action:**
1. Rotate the key immediately at https://platform.openai.com/api-keys
2. Add `*.env*` (except `*.env.example`) to `.gitignore`
3. Audit git history for any previous commits of `.env` using `git log --all -- backend/.env`
4. If found in history, use `git filter-repo` to scrub it

---

### ✅ C2. `.env.production` Not Gitignored
**File:** `backend/.env.production`, `.gitignore`  
**Risk:** Full server compromise — file contains the production Django `SECRET_KEY`, Postgres password (`AudioDB_Prod_2026_SecurePass123!`), and production server IP.

The `.gitignore` only excludes `.env`, not `.env.production`. On the next `git add -A` this file will be staged and pushed.

**Action:**
1. Add to `.gitignore`:
   ```
   .env.production
   .env.local
   .env.staging
   ```
2. Rotate the Postgres password and Django `SECRET_KEY` immediately
3. Check git status now: `git status backend/.env.production`

---

### ✅ C3. `CORS_ALLOW_ALL_ORIGINS = True` in Production Settings
**File:** `backend/myproject/settings.py`  
**Risk:** Cross-site request forgery — any website can make authenticated API requests on behalf of logged-in users.

`CORS_ALLOW_ALL_ORIGINS = True` appears 3 lines *below* the `CORS_ALLOWED_ORIGINS` whitelist, silently overriding it. The whitelist has no effect.

**Action:**
```python
# Change to:
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Only open in development
```

---

### ✅ C4. Hardcoded Superuser Password in Multiple Files
**Files:** `backend/docker-entrypoint.sh`, `playwright/tests/01-upload-and-transcribe.spec.js`, `playwright/tests/02-duplicate-detection-workflow.spec.js`, `COMMANDS.txt`, `TROUBLESHOOTING_LOGIN_ISSUE.md`  
**Risk:** Immediate account takeover if any of these files are seen by an unauthorized party.

The password `audioadmin123` is the production admin account password, hardcoded in at least 5 files.

**Action:**
1. Change the production admin password immediately
2. In `docker-entrypoint.sh`, read from environment variable:
   ```bash
   ADMIN_PASSWORD=${DJANGO_ADMIN_PASSWORD:-changeme}
   ```
3. In Playwright tests, use:
   ```js
   password: process.env.TEST_PASSWORD || 'audioadmin123'
   ```
4. Remove password from all `.md` documentation files

---

### ✅ C5. Database Password Hardcoded in Docker Compose
**File:** `docker-compose.production.yml`  
**Risk:** Database compromise if the compose file is ever exposed.

`POSTGRES_PASSWORD: AudioDB_Prod_2026_SecurePass123!` is inline in the compose file rather than read from the environment.

**Action:**
```yaml
# Change to:
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
```
And set the value in the (gitignored) `.env.production`.

---

### ✅ C6. Unauthenticated Path Traversal in `download_audio`
**File:** `backend/audioDiagnostic/views/legacy_views.py`  
**Risk:** An unauthenticated attacker can read any file accessible to the Django process, including `settings.py`, private keys, and log files.

`download_audio(request, filename)` accepts a user-supplied filename with no authentication check and no path sanitisation. A request for `../../myproject/settings.py` would return the Django settings file.

**Action:**
```python
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def download_audio(request, filename):
    safe_name = os.path.basename(filename)  # Strip directory components
    full_path = os.path.join(AUDIO_DIR, safe_name)
    if not full_path.startswith(os.path.realpath(AUDIO_DIR)):
        return HttpResponse(status=403)
```

---

## 🟠 HIGH — Fix Within This Sprint

---

### ✅ H1. `BasicAuthentication` Enabled on All API Views
**Files:** All files under `backend/audioDiagnostic/views/`  
**Risk:** Password transmitted in HTTP headers on every API request. If the connection is ever unencrypted, passwords are exposed in plaintext.

Every view explicitly declares `BasicAuthentication` alongside `TokenAuthentication`.

**Action:** Remove `BasicAuthentication` from all `authentication_classes` declarations. Token authentication is sufficient and more secure.

---

### ✅ H2. `window.fetch` Globally Monkey-Patched
**File:** `frontend/audio-waveform-visualizer/src/services/clientSideTranscription.js`  
**Risk:** Silent breakage of all subsequent fetch calls; internal API URLs leaked to browser console in production.

`window.fetch = function(...)` permanently overrides the browser's native `fetch` on every `initialize()` call and is never restored. If called twice, the wrapper wraps itself.

**Action:** Gate the override behind a flag:
```js
if (process.env.NODE_ENV === 'development') {
  const originalFetch = window.fetch;
  window.fetch = function(...args) { /* debug logging */ return originalFetch(...args); };
}
```

---

### ✅ H3. Hardcoded Windows Absolute Path in Production View
**File:** `backend/audioDiagnostic/views/legacy_views.py`  
**Risk:** Server crash — `C:\Users\user\Documents\...` does not exist on the Linux production server.

`N8NTranscribeView` has `FOLDER_TO_WATCH = r"C:\Users\user\Documents\GitHub\n8n\Files"` and is also unauthenticated.

**Action:** Either remove this view entirely (if unused) or move the path to a settings variable and add authentication.

---

### ✅ H4. No File-Size Check Before Loading Audio Into RAM
**File:** `backend/audioDiagnostic/tasks/duplicate_tasks.py`  
**Risk:** Out-of-memory crash on the 3 GB production server. A single large WAV file can kill the Celery worker.

`pydub.AudioSegment.from_file(path)` loads the entire audio file into memory with no size check beforehand.

**Action:**
```python
MAX_AUDIO_SIZE_BYTES = 400 * 1024 * 1024  # 400 MB
if os.path.getsize(audio_path) > MAX_AUDIO_SIZE_BYTES:
    raise ValueError(f"Audio file too large for processing: {os.path.getsize(audio_path)} bytes")
```

---

### ✅ H5. Auth Token Stored in `localStorage` (XSS Theft Risk)
**File:** `frontend/audio-waveform-visualizer/src/contexts/AuthContext.js`  
**Risk:** Any successful XSS attack can steal the auth token and impersonate the user indefinitely.

The auth token, user data, and subscription info are all stored in `localStorage` where they are readable by any JavaScript on the page.

**Action (preferred):** Switch to `httpOnly` session cookies managed server-side.  
**Action (minimal):** Add token expiry on the server — `ExpiringToken` from `django-rest-framework-expiring-authtoken`, or implement a custom `created` timestamp check.

---

### ✅ H6. Stripe Secret Key Not Validated Before Use
**File:** `backend/accounts/webhooks.py`  
**Risk:** If `STRIPE_SECRET_KEY` is unset, webhook signature verification silently fails or always passes — enabling billing fraud.

`stripe.api_key = settings.STRIPE_SECRET_KEY` sets the key to `None` if the env var is missing, causing all Stripe calls to behave unpredictably.

**Action:**
```python
# In settings.py
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
if not STRIPE_SECRET_KEY and not DEBUG:
    raise ImproperlyConfigured("STRIPE_SECRET_KEY must be set in production")
```

---

## 🟡 MEDIUM — ✅ All Resolved (2026-03-28)

---

### ✅ M1. File Type Validation by Extension Only
**File:** `backend/audioDiagnostic/views/upload_views.py`  
A file named `malicious.php.mp3` passes the extension check. Added MIME type or magic-byte validation should be applied using `python-magic`.

---

### ✅ M2. Playwright Tests Use Live Production Credentials
**Files:** `playwright/tests/01-upload-and-transcribe.spec.js`, `playwright/tests/02-duplicate-detection-workflow.spec.js`  
Tests run against `https://audio.precisepouchtrack.com` with hardcoded `admin`/`audioadmin123`. This creates unwanted data in production on every test run. Use a dedicated test account with credentials from environment variables:
```js
username: process.env.TEST_USERNAME || 'testuser',
password: process.env.TEST_PASSWORD
```

---

### ✅ M3. `CORS_ALLOWED_ORIGINS` Environment Variable Never Read
**File:** `backend/myproject/settings.py`  
The `CORS_ALLOWED_ORIGINS` setting in `.env.production` has no effect because `settings.py` never reads it via `os.environ`. This means CORS is controlled entirely by the hardcoded list in settings.

---

### ✅ M4. Whisper Model Loaded Per Celery Task
**File:** `backend/audioDiagnostic/tasks/transcription_tasks.py`  
`whisper.load_model("base")` is called inside the task function, downloading ~145 MB and allocating significant RAM on every transcription job. Load once at worker startup:
```python
# At module level, outside the task:
_whisper_model = None
def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model("base")
    return _whisper_model
```

---

### ✅ M5. `apiFetch` Always Sets `Content-Type: application/json`
**File:** `frontend/audio-waveform-visualizer/src/config/api.js`  
When called with a `FormData` body, the browser must set `Content-Type` itself (with the multipart boundary). The hardcoded JSON header overrides this and will silently break any new file upload route added via `apiFetch`.

---

### ✅ M6. No Per-Tab Error Boundary in Project Detail Page
**File:** `frontend/audio-waveform-visualizer/src/screens/ProjectDetailPageNew.js`  
A JavaScript error in `Tab3Duplicates` (detection/waveform) causes the entire project page to unmount, losing the file list. Each tab should have its own `<ErrorBoundary>`.

---

### ✅ M7. `PyPDF2` is Deprecated
**File:** `backend/requirements.txt`  
`PyPDF2==3.0.1` is unmaintained. `PyMuPDF` (fitz) is already in `requirements.txt` and provides more reliable text extraction. Remove `PyPDF2` and migrate the 1–2 call sites to `fitz`.

---

### ✅ M8. No Brute-Force Throttle on Login Endpoint
**File:** `backend/accounts/views.py`  
The login endpoint uses the global anonymous throttle of 100 requests/hour per IP — not per username. An attacker can attempt 100 passwords against any account per hour from a single IP. Add a dedicated tighter throttle:
```python
class LoginRateThrottle(AnonRateThrottle):
    rate = '10/hour'
```

---

### ✅ M9. `const page` Variable Reassignment in Playwright
**File:** `playwright/tests/01-upload-and-transcribe.spec.js` line 84  
`page = newPage` attempts to reassign a function parameter. In strict mode this throws. Change to `let page` or restructure the new-tab logic using Playwright's context-level page event.

---

## 🔵 LOW

| # | Issue | File | Status |
|---|-------|------|--------|
| L1 | Dead-code files: `tasks_old.py`, `views_old.py`, `split_tasks.py`, `split_views.py` — delete or archive | `backend/audioDiagnostic/` | ⚠️ Manual — delete the 4 files in Explorer or `git rm` |
| L2 | ✅ Logs moved from `MEDIA_ROOT/logs/` to `BASE_DIR/logs/` — no longer publicly accessible via `/media/` URL | `backend/myproject/settings.py` | ✅ 2026-03-28 |
| L3 | ✅ Legacy routes `/AudioUpload`, `/EditPage`, `/PDFAnalysis` wrapped in `<ProtectedRoute>` | `frontend/.../App.js` | ✅ 2026-03-28 |
| L4 | ✅ Temp files now cleaned up on exception in `cut_audio` — unlinks moved to `finally` block | `backend/audioDiagnostic/views/legacy_views.py` | ✅ 2026-03-28 |
| L5 | ✅ Wrong reverse accessor fixed: `audiofile_set.count()` → `audio_files.count()` | `backend/audioDiagnostic/serializers.py` | ✅ 2026-03-28 |
| L6 | Docker images not digest-pinned — run on server once: `docker inspect postgres:15-alpine --format='{{index .RepoDigests 0}}'` then pin in compose as `postgres@sha256:<hash>` | `docker-compose.production.yml` | ⚠️ Manual — run on server |
| L7 | ✅ Duplicate `throttle_classes = [ProcessRateThrottle]` line removed | `backend/audioDiagnostic/views/processing_views.py` | ✅ 2026-03-28 |

---

## Recommended Fix Order

### Week 1 — Do Today
1. ~~Rotate OpenAI API key (C1)~~ ✅
2. ~~Add `.env.production` to `.gitignore` + rotate DB password and `SECRET_KEY` (C2)~~ ✅
3. ~~Set `CORS_ALLOW_ALL_ORIGINS = False` (C3)~~ ✅
4. ~~Fix path traversal in `download_audio` (C6)~~ ✅

### Week 1 — Do This Week
5. ~~Change production admin password; read from env var in entrypoint (C4)~~ ✅
6. ~~Remove DB password from compose file (C5)~~ ✅
7. ~~Remove `BasicAuthentication` from all views (H1)~~ ✅
8. ~~Fix `window.fetch` monkey-patch (H2)~~ ✅
9. ~~Remove hardcoded Windows path / N8NTranscribeView (H3)~~ ✅
10. ~~Add file-size check before audio RAM load (H4)~~ ✅

### Week 2
11. ~~Add token expiry or move to httpOnly cookies (H5)~~ ✅
12. ~~Validate Stripe key on startup (H6)~~ ✅

### Ongoing
- ~~Address all Medium items during normal sprint work~~ ✅
- ~~Address Low items L2–L5, L7~~ ✅ (2026-03-28)
- L1: Delete 4 dead-code files manually (`tasks_old.py`, `views_old.py`, `split_tasks.py`, `split_views.py`)
- L6: Pin Docker image digests on server — run `docker inspect postgres:15-alpine --format='{{index .RepoDigests 0}}'` and `docker inspect redis:7-alpine --format='{{index .RepoDigests 0}}'`, then update `docker-compose.production.yml`
