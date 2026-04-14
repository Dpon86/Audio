# Master TODO â€” Audio App

**Last Updated:** April 14, 2026
**Canonical source of truth** â€” all other TODO files are superseded by this one.

**Overall Completion:** ~55% (29 of ~53 tracked items done)
**Production Status:** â­â­â­â­ 4/5 â€” Running in production, security hardened

---

## âœ… COMPLETED

### Security Hardening (Phase 1)
- [x] Remove hardcoded SECRET_KEY, force env variable (`ImproperlyConfigured` if missing)
- [x] Change DEBUG default to False
- [x] Add DRF throttling to all views (`UploadRateThrottle`, `TranscribeRateThrottle`, `ProcessRateThrottle`)
- [x] Remove unnecessary `@csrf_exempt` decorators (20+ removed)
- [x] Create serializers for all models (`serializers.py`)
- [x] Implement input validation (all endpoints validated)
- [x] Add environment variable validation
- [x] Add Production HTTPS Headers (all 8: HSTS, SSL redirect, XSS filter, nosniff, X-Frame-Options, session/CSRF cookie secure, proxy SSL header) â€” in `settings.py` behind `if not DEBUG`
- [x] Migrate auth tokens from localStorage to httpOnly cookies
  - `CookieTokenAuthentication` checks `auth_token` cookie first, falls back to Authorization header
  - `ExpiringTokenAuthentication` aliased to `CookieTokenAuthentication` â€” all views updated transparently
  - Login + register set httpOnly, SameSite=Lax cookie; `POST /api/accounts/logout/` clears it
  - All 11 frontend files: removed `localStorage.getItem('token')` + Authorization headers; use `credentials: 'include'` / `xhr.withCredentials = true`
- [x] CORS configured with `CORS_ALLOW_CREDENTIALS = True`

### Code Architecture (Phase 2)
- [x] Split `views.py` (2,369 lines) â†’ 10 domain modules
- [x] Split `tasks.py` (2,644 lines) â†’ 7 domain modules
- [x] Add database indexes to models (13 indexes, migration applied)
- [x] Fix exception handling (specific: `OSError`, `PermissionError`, `ValueError`)
- [x] Write unit tests for models (`test_models.py` â€” 22 tests, 366 lines)
- [x] Write API tests for all endpoints (`test_views.py` â€” 17 tests, 267 lines)
- [x] Write task tests with mocks (`test_tasks.py` â€” 12 tests, 252 lines)

### Infrastructure / Configuration
- [x] Frontend API URLs env-based (`REACT_APP_API_URL` via `.env` files)
- [x] FFmpeg path uses env variable (`FFMPEG_PATH` with `os.getenv`, cross-platform fallback)
- [x] Database engine env-based (`DATABASE_ENGINE` defaults to sqlite3; postgres-ready)
- [x] Basic logging configured (debug.log + error.log via `FileHandler` in settings.py)

### Client-Side Processing
- [x] Client-side transcription with `@xenova/transformers` (39MB model, browser-cached)
- [x] Default to client-side processing (server-side toggle hidden)
- [x] IndexedDB storage for audio File objects
- [x] Server persistence for transcription metadata (`ClientTranscription` model + API endpoints)
- [x] Server persistence for duplicate analysis (`DuplicateAnalysis` model + API endpoints)
- [x] Cross-device sync: auto-save to server after transcription/analysis, auto-load on mount
- [x] Sync status badges in UI ("â˜ï¸ Synced" / "ðŸ“± Local" / "â˜ï¸ðŸ”„ Server")

### AI Duplicate Detection (Partial)
- [x] AI database models created (`AIDuplicateDetectionResult`, `AIPDFComparisonResult`, `AIProcessingLog`)
- [x] AI service layer created (`services/ai/`: `anthropic_client.py`, `duplicate_detector.py`, `prompt_templates.py`, `cost_calculator.py`)
- [x] Privacy & Security Page created (`PrivacySecurityPage.jsx` + CSS) and routed at `/privacy`

---

## ðŸ”´ HIGH PRIORITY â€” Do Next

### Security & GDPR

**S1 â€” Review Application Logs for PII** *(~2 hours)*
- Scan all `logger.*` calls for email addresses, names, phone numbers
- Replace with user IDs: `logger.info(f'Login: user_id={user.id}')` not `user.email`
- Key files: `accounts/views.py`, all `audioDiagnostic/views/` files
- Impact: GDPR compliance

**S2 â€” Add Security Audit Logging** *(~2 hours)*
- Add dedicated `security` logger with `RotatingFileHandler` (10MB, 5 backups) in `settings.py`
- Log in `accounts/views.py`: login success/fail (user_id + IP), logout, password change
- Events: login, logout, password change, data export, account deletion, subscription change
- Never log tokens, passwords, or PII â€” only user_id + IP
- Impact: Enables incident investigation

**S3 â€” Add Privacy Page Footer Link** *(~15 min)*
- Route `/privacy` already exists and works
- Add `<Link to="/privacy">Privacy & Security</Link>` in app footer/nav
- Impact: GDPR user transparency

**S4 â€” Implement GDPR Data Export Endpoint** *(~2â€“3 hours)*
- `POST /api/accounts/data-export/` â†’ returns JSON of all user data
- Bundle: account info, subscription, projects, audio files, transcriptions
- Wire up "Request Data Export" button in `PrivacySecurityPage.jsx`
- Configure SMTP or transactional email (SendGrid/Mailgun)
- Impact: GDPR Article 20 â€” right to data portability

---

## ðŸŸ¡ MEDIUM PRIORITY â€” Complete Within 2 Weeks

### Security Enhancements

**S5 â€” Add Content Security Policy (CSP)** *(~1 hour)*
- `pip install django-csp`, add `csp.middleware.CSPMiddleware` to `MIDDLEWARE`
- Allow: `'self'`, Stripe JS, Anthropic API
- Impact: Defense-in-depth against XSS

**S6 â€” Tighten Rate Limits for Production** *(~30 min)*
- Add login-specific throttle class: `3/hour` (brute-force protection)
- Consider `django-defender` for automatic IP blocking
- Current limits are good baseline; login endpoint needs hardening

### Testing

**T1 â€” Run Full Test Suite and Fix Failures** *(~1 day)*
- `docker exec audioapp_backend python manage.py test audioDiagnostic.tests`
- Expected: 51 tests pass (22 model + 17 API + 12 task tests)

**T2 â€” Run Security Scan (Bandit)** *(~1 hour)*
- `pip install bandit` â†’ `bandit -r backend/`
- Fix any HIGH or MEDIUM severity findings

**T3 â€” Add Query Optimisation** *(~2 hours)*
- Add `select_related` / `prefetch_related` to views accessing related models
- Example: `AudioProject.objects.select_related('user').prefetch_related('audio_files')`
- Impact: Eliminates N+1 queries

**T4 â€” Verify Test Coverage** *(~1 hour)*
- `coverage run --source='.' manage.py test audioDiagnostic.tests` â†’ `coverage report`
- Goal: 80%+ backend coverage

### AI Duplicate Detection (Remaining Setup)

**AI1 â€” Complete AI Service Integration** *(~1â€“2 days)*
- AI DB models exist; AI service layer exists (`anthropic_client.py` etc.)
- Wire up endpoints: AI duplicate detection, PDF comparison views
- Add API keys to server `.env` (`ANTHROPIC_API_KEY`)
- Test end-to-end: trigger AI analysis, verify `AIProcessingLog` rows created
- Frontend: surface AI analysis results in Tab3/Tab4 UI

---

## ðŸŸ¢ LOW PRIORITY â€” Future (1â€“3 Months)

### Performance & Production Hardening

**P1 â€” Migrate to PostgreSQL** *(~half day)*
- `DATABASE_ENGINE` env var is already wired up â€” just set it and run `migrate`
- Create migration plan for existing SQLite data
- Managed Postgres (render.com, Supabase, etc.) for production

**P2 â€” Implement Whisper Model Caching** *(~2 hours)*
- Currently loads model per task invocation
- Load once at Celery worker startup (module-level singleton)
- File: `tasks/transcription_tasks.py`

**P3 â€” Structured JSON Logging** *(~1 hour)*
- `pip install python-json-logger`; configure JSON formatter in `settings.py`
- Add request ID tracking for log correlation

**P4 â€” Sentry Error Tracking** *(~30 min)*
- `pip install sentry-sdk`; configure DSN in `settings.py`

**P5 â€” Health Check Endpoints** *(~1 hour)*
- `/health/` basic; `/health/db/` DB ping; `/health/redis/` Redis ping; `/health/celery/` worker queue

**P6 â€” File Encryption at Rest** *(~4â€“6 hours)*
- Audio files currently unencrypted on disk
- Option A: S3 + SSE; Option B: `cryptography.fernet` encrypt on write, decrypt on read
- Requires `FILE_ENCRYPTION_KEY` env var

**P7 â€” Pin All Dependencies** *(~1 hour)*
- `pip freeze > requirements.txt`; `npm shrinkwrap` or lock package versions

### Frontend Quality

**F1 â€” Refactor App.jsx** *(~3â€“5 days)*
- Currently 3,224 lines â€” split into: `ProjectList`, `ProjectDetail`, `AudioUpload`, `TranscriptionView`, `DuplicateReview`
- Max 500 lines per file; use React Context for shared state

**F2 â€” Add Frontend Component Tests** *(~3â€“5 days)*
- Jest + React Testing Library for main components, API utilities, hooks
- Goal: 70%+ coverage

**F3 â€” Set Up Linting** *(~1 hour)*
- Backend: `flake8` + `black`; Frontend: `eslint` + `prettier`
- Pre-commit hooks with `husky`

### CI/CD & Monitoring

**C1 â€” GitHub Actions CI Pipeline** *(~1 day)*
- Stages: Lint â†’ Test â†’ Security Scan â†’ Build
- Triggers: PRs and pushes to master
- Block merge on test failures or HIGH severity bandit findings

**C2 â€” Prometheus Metrics** *(~2 hours)*
- `pip install django-prometheus`; expose `/metrics`
- Track: request count/latency, task queue size, upload volume

**C3 â€” Log Aggregation** *(~2 hours)*
- Forward logs to Papertrail, Loggly, or self-hosted ELK
- Searchable by request ID; 30-day minimum retention

**C4 â€” API Documentation** *(~1 hour)*
- `pip install drf-spectacular`; expose `/api/docs/` (Swagger UI)

---

## ðŸ“Š Summary

| Area | Done | Remaining |
|------|------|-----------|
| Security (Phase 1 + 1B) | 10 | 6 |
| Architecture (Phase 2) | 7 | 0 |
| Testing | 3 | 4 |
| Client-side / Server Persistence | 9 | 0 |
| AI Duplicate Detection | 2 | 1 |
| Privacy page | 1 | 1 (footer link) |
| Performance / Infra | 3 | 7 |
| Frontend Quality | 0 | 3 |
| CI/CD & Monitoring | 0 | 4 |
| **TOTAL** | **~35** | **~26** |

---

## ðŸŽ¯ Recommended Next Actions

1. **S1** â€” Review logs for PII *(quick win, GDPR compliance)*
2. **S2** â€” Add security audit logging *(quick win, incident response)*
3. **S3** â€” Add privacy page footer link *(15 min)*
4. **T1** â€” Run full test suite *(validate production stability)*
5. **T2** â€” Bandit security scan *(may catch remaining issues)*
6. **S4** â€” GDPR data export endpoint *(legal requirement for EU users)*
7. **AI1** â€” Complete AI duplicate detection wiring
8. **P1** â€” PostgreSQL migration *(production database hardening)*


---
