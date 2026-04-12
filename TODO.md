# TODO List - Remaining Code Review Items

**Last Updated:** April 12, 2026  
**Completed:** Phase 1 (Basic Security) ✅ | Phase 2 (Architecture) ✅ | Phase 3 (Testing) 🟡 Partial  
**Critical:** Phase 1B (Advanced Security & GDPR) 🔴 Pre-Production Required  
**Remaining:** Phase 1B (11 items), Phase 3 (4 items), Phase 4-6 (22 items)

**Security Status:** ⭐⭐⭐⭐ 4/5 (Good) - Ready for production with HIGH priority tasks completed

---

## ✅ COMPLETED (15 items)

### Phase 1: Security Hardening ✅ DONE
- [x] Remove hardcoded SECRET_KEY, force environment variable
- [x] Change DEBUG default to False
- [x] Add DRF throttling to all views (UploadRateThrottle, TranscribeRateThrottle, ProcessRateThrottle)
- [x] Remove unnecessary @csrf_exempt decorators (20+ removed)
- [x] Create serializers for all models (serializers.py created)
- [x] Implement input validation (all endpoints validated)
- [x] Add environment variable validation (SECRET_KEY raises ImproperlyConfigured)

### Phase 2: Code Architecture ✅ DONE
- [x] Split views.py into domain modules (10 files: project, upload, transcription, processing, duplicate, pdf_matching, infrastructure, legacy)
- [x] Split tasks.py into domain modules (7 files: transcription, duplicate, pdf, audio_processing, utils)
- [x] Add database indexes to models (13 indexes added, migration applied)
- [x] Fix exception handling - specific exceptions (OSError, PermissionError, ValueError in delete method)
- [x] Write unit tests for models (test_models.py - 22 tests, 366 lines)
- [x] Write API tests for all endpoints (test_views.py - 17 tests, 267 lines)
- [x] Write task tests with mocks (test_tasks.py - 12 tests, 252 lines)

---

## 📋 REMAINING TASKS (37 items)

### Priority 1: Advanced Security & GDPR Compliance (11 items) 🔴 CRITICAL
**Estimated Time:** 1-2 weeks  
**Reference:** `docs/SECURITY_AUDIT.md`, `docs/SECURITY_PRODUCTION.md`, `docs/SECURITY_QUICK_START.md`  
**Overall Security Rating:** ⭐⭐⭐⭐ (4/5 - Good, needs production hardening)

#### 🔴 HIGH PRIORITY - Pre-Production (3 items)
**MUST complete before production launch**

1. [ ] **Add Production HTTPS Headers**
   - Location: `backend/myproject/settings.py`
   - Add when `DEBUG=False`:
     ```python
     SECURE_SSL_REDIRECT = True  # Force HTTPS
     SECURE_HSTS_SECONDS = 31536000  # 1 year HSTS
     SECURE_HSTS_INCLUDE_SUBDOMAINS = True
     SESSION_COOKIE_SECURE = True  # Cookies only over HTTPS
     CSRF_COOKIE_SECURE = True
     SECURE_BROWSER_XSS_FILTER = True
     SECURE_CONTENT_TYPE_NOSNIFF = True
     X_FRAME_OPTIONS = 'DENY'  # Prevent clickjacking
     ```
   - Verify: `curl -I https://audio.precisepouchtrack.com` (should show Strict-Transport-Security, X-Frame-Options)
   - Impact: Prevents downgrade attacks, cookie theft, clickjacking
   - Time: 30 minutes

2. [ ] **Review Application Logs for PII**
   - Files: All files using `logging` module
   - Search for: Email addresses, names, phone numbers in log statements
   - Redact: Replace with user IDs or hashed values
   - Example: `logger.info(f'User {user.id} logged in')` NOT `logger.info(f'User {user.email} logged in')`
   - Impact: GDPR compliance - logs must not expose personal data
   - Time: 2 hours

3. [ ] **Deploy Privacy & Security Page**
   - Files: `frontend/src/components/PrivacySecurityPage.jsx` (✅ created), `PrivacySecurityPage.css` (✅ created)
   - Integration:
     1. Add route: `<Route path="/privacy" element={<PrivacySecurityPage />} />` in App.js
     2. Add footer link: `<Link to="/privacy">Privacy & Security</Link>`
     3. Test 3 tabs: Privacy Policy, Security Measures, Your Data
   - Build: `npm run build`
   - Deploy: `scp -r build/* nickd@82.165.221.205:/opt/audioapp/frontend/build/`
   - Verify: https://audio.precisepouchtrack.com/privacy
   - Impact: User transparency about data handling (GDPR requirement)
   - Time: 30 minutes

#### 🟡 MEDIUM PRIORITY - Post-Launch (5 items)
**Complete within 2 weeks of production launch**

4. [ ] **Migrate Auth Tokens to httpOnly Cookies**
   - Issue: Tokens currently stored in `localStorage` (vulnerable to XSS attacks)
   - Solution: Use httpOnly cookies (not accessible via JavaScript)
   - Backend Changes (`accounts/views.py`):
     ```python
     class CustomAuthToken(ObtainAuthToken):
         def post(self, request, *args, **kwargs):
             # ... validation ...
             response = Response({...})
             response.set_cookie(
                 key='auth_token',
                 value=token.key,
                 httponly=True,  # XSS protection
                 secure=True,    # HTTPS only
                 samesite='Lax', # CSRF protection
                 max_age=30 * 24 * 60 * 60  # 30 days
             )
             return response
     ```
   - Backend Auth (`accounts/authentication.py`):
     ```python
     class CookieTokenAuthentication(TokenAuthentication):
         def authenticate(self, request):
             # Try header first, then cookie
             auth = super().authenticate(request)
             if auth: return auth
             token = request.COOKIES.get('auth_token')
             return self.authenticate_credentials(token) if token else None
     ```
   - Frontend Changes (`AuthContext.js`):
     - Remove all `localStorage.setItem('token', ...)` and `localStorage.getItem('token')`
     - Add `credentials: 'include'` to all fetch() calls
     - Token now sent automatically in cookie
   - Files to Update: `AuthContext.js`, `api.js`, `EditPage.js`, all components making API calls
   - Test: Check browser DevTools > Application > Cookies (should see `auth_token` with HttpOnly ✓)
   - Verify: `console.log(document.cookie)` should NOT show auth_token
   - Impact: Prevents token theft via XSS attacks
   - Time: 1-2 hours

5. [ ] **Implement GDPR Data Export Endpoint**
   - Requirement: GDPR Article 20 - Right to data portability
   - Backend (`accounts/views.py`):
     ```python
     @api_view(['POST'])
     @permission_classes([IsAuthenticated])
     def request_data_export(request):
         user = request.user
         data = {
             'account': {...},
             'subscription': {...},
             'projects': list(user.audioproject_set.values(...)),
             'audio_files': [...],
             'transcriptions': [...]
         }
         json_data = json.dumps(data, indent=2)
         send_export_email(user.email, data)
         return Response({'message': 'Data export will be emailed within 72 hours'})
     ```
   - Add URL: `path('data-export/', views.request_data_export)`
   - Frontend: Wire up "Request Data Export" button in PrivacySecurityPage.jsx
   - Email Setup: Configure SMTP in settings.py or use SendGrid/Mailgun
   - Test: Trigger export, verify email with JSON attachment
   - Impact: GDPR compliance for EU users
   - Time: 2-3 hours

6. [ ] **Add Security Audit Logging**
   - Purpose: Track security events for incident investigation
   - Configure Logging (`settings.py`):
     ```python
     LOGGING = {
         'loggers': {
             'security': {
                 'handlers': ['security_file'],
                 'level': 'INFO',
                 'propagate': False,
             },
         },
         'handlers': {
             'security_file': {
                 'class': 'logging.handlers.RotatingFileHandler',
                 'filename': 'logs/security.log',
                 'maxBytes': 10 * 1024 * 1024,  # 10MB
                 'backupCount': 5,
             },
         },
     }
     ```
   - Log Events (`accounts/views.py`):
     ```python
     import logging
     security_logger = logging.getLogger('security')
     
     # On successful login:
     security_logger.info(f'Login success: user_id={user.id}, ip={request.META.get("REMOTE_ADDR")}')
     
     # On failed login:
     security_logger.warning(f'Login failed: username={username}, ip={request.META.get("REMOTE_ADDR")}')
     
     # On data export:
     security_logger.info(f'Data export requested: user_id={user.id}')
     
     # On account deletion:
     security_logger.warning(f'Account deleted: user_id={user.id}')
     ```
   - Events to Log: Login (success/fail), logout, password change, data export, account deletion, subscription changes
   - Exclude: Passwords, tokens, personal data (only user IDs and IPs)
   - Impact: Enables security incident response and investigation
   - Time: 2 hours

7. [ ] **Add Content Security Policy (CSP)**
   - Purpose: Prevent XSS attacks by restricting resource sources
   - Install: `pip install django-csp`
   - Configure (`settings.py`):
     ```python
     MIDDLEWARE = [
         'csp.middleware.CSPMiddleware',
         # ... other middleware
     ]
     
     CSP_DEFAULT_SRC = ("'self'",)
     CSP_SCRIPT_SRC = ("'self'", "https://js.stripe.com")
     CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")  # For styled-components
     CSP_CONNECT_SRC = ("'self'", "https://api.stripe.com", "https://api.anthropic.com")
     CSP_IMG_SRC = ("'self'", "data:", "https:")
     CSP_FONT_SRC = ("'self'", "data:")
     CSP_FRAME_SRC = ("https://js.stripe.com",)  # For Stripe checkout
     ```
   - Test: Check browser console for CSP violations
   - Adjust: Add sources as needed for third-party services
   - Impact: Defense-in-depth against XSS attacks
   - Time: 1 hour

8. [ ] **Enhanced Rate Limiting for Production**
   - Current: Good baseline limits
   - Production Adjustment (`settings.py`):
     ```python
     REST_FRAMEWORK = {
         'DEFAULT_THROTTLE_RATES': {
             'anon': '50/hour',      # Reduced from 100
             'user': '500/hour',     # Reduced from 1000
             'upload': '30/hour',    # Reduced from 50
             'transcribe': '5/hour', # Reduced from 10
             'process': '10/hour',   # Reduced from 20
             'login': '3/hour',      # Reduced from 10 (brute-force protection)
         }
     }
     ```
   - Add IP-based blocking for repeated violations
   - Consider: django-defender for automatic IP blocking
   - Monitor: Track rate limit violations in logs
   - Impact: Stronger protection against abuse and DDoS
   - Time: 30 minutes

#### 🟢 LOW PRIORITY - Future Enhancement (3 items)
**Complete within 1-3 months**

9. [ ] **Implement File Encryption at Rest**
   - Issue: Audio files stored unencrypted on disk
   - Solutions:
     - Option A: AWS S3 with server-side encryption (SSE-S3)
     - Option B: Encrypt files before writing using `cryptography` library
   - Example (Option B):
     ```python
     from cryptography.fernet import Fernet
     
     # Generate key once, store in environment
     ENCRYPTION_KEY = os.getenv('FILE_ENCRYPTION_KEY')
     cipher = Fernet(ENCRYPTION_KEY)
     
     # Encrypt on upload
     encrypted_data = cipher.encrypt(file.read())
     
     # Decrypt on download
     decrypted_data = cipher.decrypt(encrypted_file.read())
     ```
   - Impact: Protects user files if server is compromised
   - Time: 4-6 hours

10. [ ] **Data Anonymization for Analytics**
    - Issue: Usage analytics may contain identifiable information
    - Solution: Hash user IDs before logging
    - Example:
      ```python
      import hashlib
      
      def anonymize_user_id(user_id):
          salt = settings.ANALYTICS_SALT  # Store in env
          return hashlib.sha256(f"{user_id}{salt}".encode()).hexdigest()[:16]
      
      # Use in analytics
      analytics_logger.info(f'upload: user={anonymize_user_id(user.id)}')
      ```
    - Impact: Privacy-friendly analytics
    - Time: 2-3 hours

11. [ ] **Security Monitoring Dashboard**
    - Purpose: Real-time security event visualization
    - Tools: Grafana + Prometheus or Sentry dashboards
    - Metrics:
      - Login attempts (successful/failed) per hour
      - API rate limit violations
      - Data export requests
      - File upload volume
      - Token expiry events
    - Alerts: Spike in failed logins, unusual API activity
    - Impact: Proactive security incident detection
    - Time: 4-6 hours

---

### Priority 2: Testing Completion (4 items)
**Estimated Time:** 2-3 days

12. [ ] **Run full test suite and fix any failures**
   - Location: `backend/audioDiagnostic/tests/`
   - Command: `python manage.py test audioDiagnostic.tests`
   - Expected: All 51 tests pass
   - Notes: Fixed DoesNotExist exception handling, should pass now

13. [ ] **Security scan with bandit**
   - Install: `pip install bandit`
   - Run: `bandit -r backend/`
   - Fix: Any HIGH or MEDIUM severity issues

14. [ ] **Add query optimization (select_related/prefetch_related)**
   - Files: All view files that access related models
   - Example: `AudioProject.objects.select_related('user').prefetch_related('audio_files')`
   - Impact: Reduces N+1 query problems

15. [ ] **Verify test coverage**
   - Install: `pip install coverage`
   - Run: `coverage run --source='.' manage.py test audioDiagnostic.tests`
   - Report: `coverage report`
   - Goal: 80%+ coverage

---

### Priority 3: Frontend Testing & Quality (4 items)
**Estimated Time:** 3-5 days

16. [ ] **Add frontend component tests**
   - Framework: Jest + React Testing Library
   - Files: `frontend/audio-waveform-visualizer/src/**/*.test.js`
   - Coverage: Main components, API utilities, hooks
   - Setup: `npm install --save-dev @testing-library/react @testing-library/jest-dom`

17. [ ] **Set up frontend coverage reporting**
   - Tool: Jest coverage
   - Command: `npm test -- --coverage`
   - Goal: 70%+ coverage

18. [ ] **Refactor large React component**
   - File: `frontend/audio-waveform-visualizer/src/App.jsx` (3,224 lines)
   - Split into: ProjectList, ProjectDetail, AudioUpload, TranscriptionView, DuplicateReview
   - Max file size: 500 lines
   - Use: React Context for state management

19. [ ] **Set up linting**
   - Backend: `pip install flake8 black`
   - Frontend: `npm install --save-dev eslint prettier`
   - Add: Pre-commit hooks with `husky`
   - Config: .flake8, .prettierrc

---

### Priority 4: Performance & Production Readiness (9 items)
**Estimated Time:** 1-2 weeks

20. [ ] **Migrate to PostgreSQL**
   - Install: `pip install psycopg2-binary`
   - Update: settings.py DATABASES config
   - Migrate: `python manage.py migrate`
   - Backup: Create migration plan for existing data

21. [ ] **Implement Whisper model caching**
    - Issue: Model loads on every transcription task
    - Solution: Load once at worker startup
    - File: `tasks/transcription_tasks.py`
    - Pattern: Module-level model instance

22. [ ] **Add structured logging**
    - Install: `pip install python-json-logger`
    - Configure: JSON formatter in settings.py
    - Update: Replace print statements with logger.info()
    - Add: Request ID tracking

23. [ ] **Set up Sentry error tracking**
    - Install: `pip install sentry-sdk`
    - Sign up: sentry.io
    - Configure: settings.py with DSN
    - Test: Trigger test error

24. [ ] **Add Prometheus metrics**
    - Install: `pip install django-prometheus`
    - Add: Middleware for request metrics
    - Endpoint: /metrics
    - Track: Request count, latency, task queue size

25. [ ] **Fix FFmpeg path (cross-platform)**
    - File: `tasks/transcription_tasks.py`
    - Change: `r"C:\ffmpeg\..."` to environment variable
    - Add: `FFMPEG_PATH = os.getenv('FFMPEG_PATH', 'ffmpeg')`
    - Update: .env.template

26. [ ] **Fix frontend API URLs (env-based)**
    - File: `frontend/audio-waveform-visualizer/src/api.js`
    - Change: `http://localhost:8000` to `process.env.REACT_APP_API_URL`
    - Add: .env files for dev/staging/prod
    - Default: `REACT_APP_API_URL=http://localhost:8000`

27. [ ] **Use CPU-only PyTorch**
    - File: `requirements.txt`
    - Change: `torch==2.7.0` to `torch==2.7.0+cpu`
    - URL: `--extra-index-url https://download.pytorch.org/whl/cpu`
    - Savings: ~600MB disk space

28. [ ] **Pin all dependencies**
    - Run: `pip freeze > requirements.txt`
    - Check: No version ranges (==, not >=)
    - Update: package.json with exact versions
    - Test: Fresh install verifies compatibility

---

### Priority 5: CI/CD & Monitoring (9 items)
**Estimated Time:** 1-2 weeks

29. [ ] **Set up GitHub Actions CI**
    - File: `.github/workflows/ci.yml`
    - Stages: Lint → Test → Build → Security Scan
    - Triggers: On PR and push to main
    - Cache: Dependencies for speed

30. [ ] **Add automated testing in CI**
    - Backend: `python manage.py test`
    - Frontend: `npm test`
    - Coverage: Upload to codecov.io
    - Gate: Block merge if tests fail

20. [ ] **Add security scanning in CI**
    - Tools: bandit (Python), npm audit (Node)
    - Run: On every PR
    - Fail: On HIGH severity issues
    - Report: Summary in PR comment

32. [ ] **Set up staging environment**
    - Platform: Heroku/DigitalOcean/AWS
    - Database: PostgreSQL (managed)
    - Redis: Managed Redis instance
    - Celery: Separate worker dyno
    - Deploy: Auto-deploy from main branch

33. [ ] **Configure deployment pipeline**
    - Strategy: Blue-green or rolling
    - Steps: Test → Build → Deploy staging → Manual approve → Deploy prod
    - Rollback: One-click rollback capability
    - Smoke tests: Post-deployment health checks

34. [ ] **Add health check endpoints**
    - Endpoint: `/health/` (basic check)
    - Endpoint: `/health/db/` (database connectivity)
    - Endpoint: `/health/redis/` (Redis connectivity)
    - Endpoint: `/health/celery/` (worker status)
    - Response: JSON with status + latency

35. [ ] **Set up log aggregation**
    - Service: Papertrail/Loggly/ELK
    - Forward: All application logs
    - Index: Searchable by request ID
    - Retention: 30 days minimum

36. [ ] **Configure alerts**
    - Tool: Sentry + PagerDuty/Opsgenie
    - Alerts: Error rate spike, API latency >1s, Worker queue >100
    - Channels: Email, Slack, SMS for critical
    - On-call: Rotation schedule

37. [ ] **Add API documentation**
    - Install: `pip install drf-spectacular`
    - Configure: settings.py schema generation
    - Endpoint: `/api/docs/` (Swagger UI)
    - Auto-generate: From serializers + docstrings

---

## 🔧 TECHNICAL DEBT (Not Blocking)

### Code Quality
- [ ] Extract Stripe logic to service layer (currently in models.py)
- [ ] Add type hints to Python code
- [ ] Improve error messages (user-friendly)
- [ ] Add request/response examples to API docs

### Frontend
- [ ] Extract API utilities to separate module
- [ ] Add loading states for all async operations
- [ ] Implement proper error boundaries
- [ ] Add accessibility (ARIA labels, keyboard nav)

### Infrastructure
- [ ] Add backup/disaster recovery strategy
- [ ] Document runbook for common issues
- [ ] Create development setup script
- [ ] Add Docker Compose for local development

### Performance
- [ ] Add Redis caching for frequently accessed data
- [ ] Implement pagination for large lists
- [ ] Add database query logging in dev
- [ ] Profile and optimize slow endpoints

---

## 📊 Progress Summary

| Phase | Tasks | Completed | Remaining | Status |
|-------|-------|-----------|-----------|--------|
| Phase 1: Security (Basic) | 7 | 7 | 0 | ✅ DONE |
| Phase 1B: Security (Advanced) | 11 | 0 | 11 | 🔴 CRITICAL - Pre-Production |
| Phase 2: Architecture | 8 | 8 | 0 | ✅ DONE |
| Phase 3: Testing | 7 | 3 | 4 | 🟡 IN PROGRESS |
| Phase 4: Frontend Testing | 4 | 0 | 4 | ⏳ NOT STARTED |
| Phase 5: Production Readiness | 9 | 0 | 9 | ⏳ NOT STARTED |
| Phase 6: CI/CD | 9 | 0 | 9 | ⏳ NOT STARTED |
| **TOTAL** | **55** | **18** | **37** | **33% Complete** |

---

## 🔴 CRITICAL PRE-PRODUCTION TASKS

**MUST complete before going live:**
1. ✅ Add production HTTPS headers (Task #1)
2. ✅ Review logs for PII (Task #2)
3. ✅ Deploy privacy page (Task #3)
4. ✅ Run full test suite (Task #12)
5. ✅ Security scan with bandit (Task #13)

**Estimated Time: 1 day**

---
---

## 🎯 Next Actions (Recommended Order)

### This Week (CRITICAL - Pre-Production)
1. **Add production HTTPS headers** (Task #1) - 30 minutes
2. **Review logs for PII** (Task #2) - 2 hours  
3. **Deploy privacy page** (Task #3) - 30 minutes
4. **Run full test suite** (Task #12) - 1 hour
5. **Security scan with bandit** (Task #13) - 1 hour

**Total Time: ~5 hours to be production-ready**

### Next Week (Post-Launch Security)
6. **Migrate to httpOnly cookies** (Task #4) - 1-2 hours
7. **Implement GDPR data export** (Task #5) - 2-3 hours
8. **Add security audit logging** (Task #6) - 2 hours
9. **Add Content Security Policy** (Task #7) - 1 hour
10. **Enhanced rate limiting** (Task #8) - 30 minutes

### Following Weeks
11. Query optimization (Task #14)
12. Frontend component tests (Task #16)
13. Refactor large React component (Task #18)
14. Set up linting (Task #19)
15. Begin PostgreSQL migration (Task #20)

---
---

## 📝 Notes

- **Test Suite:** 51 tests created (811 lines across 3 test files)
- **Refactoring:** views.py (2,369 lines) → 10 modules | tasks.py (2,644 lines) → 7 modules
- **Security (Basic):** All critical vulnerabilities fixed ✅
- **Security (Advanced):** Comprehensive audit completed - 4/5 stars (Good) ⭐⭐⭐⭐
- **Privacy Page:** React component created with 3 tabs (Privacy Policy, Security Measures, Your Data)
- **Database:** 13 indexes added and migrated
- **Backups:** Original files saved as views_old.py and tasks_old.py

---

## 🔗 References

### Code Review & Architecture
- Code Review Report: `docs/CODE_REVIEW_REPORT.md`
- Refactoring Summary: `docs/REFACTORING_SUMMARY.md`
- New Architecture: `docs/ARCHITECTURE_NEW.md`
- Test Files: `backend/audioDiagnostic/tests/`
- View Modules: `backend/audioDiagnostic/views/`
- Task Modules: `backend/audioDiagnostic/tasks/`

### Security Documentation
- **Security Audit:** `docs/SECURITY_AUDIT.md` (comprehensive 25,000+ char analysis)
- **Production Hardening:** `docs/SECURITY_PRODUCTION.md` (deployment guide with code examples)
- **Implementation Summary:** `docs/SECURITY_IMPLEMENTATION_SUMMARY.md` (executive overview)
- **Quick Start Guide:** `docs/SECURITY_QUICK_START.md` (copy/paste commands for deployment)
- **Privacy Page (Frontend):** `frontend/src/components/PrivacySecurityPage.jsx` + `.css`

### Key Security Findings
- ✅ **Strengths:** Environment-based secrets, strong password hashing (PBKDF2-SHA256, 600k iterations), comprehensive rate limiting, PCI-compliant payments (Stripe)
- ⚠️ **High Priority:** Production HTTPS headers, log PII review
- ⚠️ **Medium Priority:** httpOnly cookies (migrate from localStorage), GDPR data export, security logging
- ⚠️ **Low Priority:** File encryption at rest, analytics anonymization

---

## 🚨 Security Alert

**Overall Security Rating: ⭐⭐⭐⭐ (4/5 - Good)**  
**Status: Safe for production with HIGH priority tasks completed**

See `docs/SECURITY_AUDIT.md` for full details.
