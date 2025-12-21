# TODO List - Remaining Code Review Items

**Last Updated:** December 14, 2025  
**Completed:** Phase 1 (Security) ✅ | Phase 2 (Architecture) ✅ | Phase 3 (Testing) 🟡 Partial  
**Remaining:** Phase 3 (Frontend Testing), Phase 4 (Production), Phase 5 (CI/CD)

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

## 📋 REMAINING TASKS (26 items)

### Priority 1: Testing Completion (4 items)
**Estimated Time:** 2-3 days

1. [ ] **Run full test suite and fix any failures**
   - Location: `backend/audioDiagnostic/tests/`
   - Command: `python manage.py test audioDiagnostic.tests`
   - Expected: All 51 tests pass
   - Notes: Fixed DoesNotExist exception handling, should pass now

2. [ ] **Security scan with bandit**
   - Install: `pip install bandit`
   - Run: `bandit -r backend/`
   - Fix: Any HIGH or MEDIUM severity issues

3. [ ] **Add query optimization (select_related/prefetch_related)**
   - Files: All view files that access related models
   - Example: `AudioProject.objects.select_related('user').prefetch_related('audio_files')`
   - Impact: Reduces N+1 query problems

4. [ ] **Verify test coverage**
   - Install: `pip install coverage`
   - Run: `coverage run --source='.' manage.py test audioDiagnostic.tests`
   - Report: `coverage report`
   - Goal: 80%+ coverage

---

### Priority 2: Frontend Testing & Quality (4 items)
**Estimated Time:** 3-5 days

5. [ ] **Add frontend component tests**
   - Framework: Jest + React Testing Library
   - Files: `frontend/audio-waveform-visualizer/src/**/*.test.js`
   - Coverage: Main components, API utilities, hooks
   - Setup: `npm install --save-dev @testing-library/react @testing-library/jest-dom`

6. [ ] **Set up frontend coverage reporting**
   - Tool: Jest coverage
   - Command: `npm test -- --coverage`
   - Goal: 70%+ coverage

7. [ ] **Refactor large React component**
   - File: `frontend/audio-waveform-visualizer/src/App.jsx` (3,224 lines)
   - Split into: ProjectList, ProjectDetail, AudioUpload, TranscriptionView, DuplicateReview
   - Max file size: 500 lines
   - Use: React Context for state management

8. [ ] **Set up linting**
   - Backend: `pip install flake8 black`
   - Frontend: `npm install --save-dev eslint prettier`
   - Add: Pre-commit hooks with `husky`
   - Config: .flake8, .prettierrc

---

### Priority 3: Performance & Production Readiness (9 items)
**Estimated Time:** 1-2 weeks

9. [ ] **Migrate to PostgreSQL**
   - Install: `pip install psycopg2-binary`
   - Update: settings.py DATABASES config
   - Migrate: `python manage.py migrate`
   - Backup: Create migration plan for existing data

10. [ ] **Implement Whisper model caching**
    - Issue: Model loads on every transcription task
    - Solution: Load once at worker startup
    - File: `tasks/transcription_tasks.py`
    - Pattern: Module-level model instance

11. [ ] **Add structured logging**
    - Install: `pip install python-json-logger`
    - Configure: JSON formatter in settings.py
    - Update: Replace print statements with logger.info()
    - Add: Request ID tracking

12. [ ] **Set up Sentry error tracking**
    - Install: `pip install sentry-sdk`
    - Sign up: sentry.io
    - Configure: settings.py with DSN
    - Test: Trigger test error

13. [ ] **Add Prometheus metrics**
    - Install: `pip install django-prometheus`
    - Add: Middleware for request metrics
    - Endpoint: /metrics
    - Track: Request count, latency, task queue size

14. [ ] **Fix FFmpeg path (cross-platform)**
    - File: `tasks/transcription_tasks.py`
    - Change: `r"C:\ffmpeg\..."` to environment variable
    - Add: `FFMPEG_PATH = os.getenv('FFMPEG_PATH', 'ffmpeg')`
    - Update: .env.template

15. [ ] **Fix frontend API URLs (env-based)**
    - File: `frontend/audio-waveform-visualizer/src/api.js`
    - Change: `http://localhost:8000` to `process.env.REACT_APP_API_URL`
    - Add: .env files for dev/staging/prod
    - Default: `REACT_APP_API_URL=http://localhost:8000`

16. [ ] **Use CPU-only PyTorch**
    - File: `requirements.txt`
    - Change: `torch==2.7.0` to `torch==2.7.0+cpu`
    - URL: `--extra-index-url https://download.pytorch.org/whl/cpu`
    - Savings: ~600MB disk space

17. [ ] **Pin all dependencies**
    - Run: `pip freeze > requirements.txt`
    - Check: No version ranges (==, not >=)
    - Update: package.json with exact versions
    - Test: Fresh install verifies compatibility

---

### Priority 4: CI/CD & Monitoring (9 items)
**Estimated Time:** 1-2 weeks

18. [ ] **Set up GitHub Actions CI**
    - File: `.github/workflows/ci.yml`
    - Stages: Lint → Test → Build → Security Scan
    - Triggers: On PR and push to main
    - Cache: Dependencies for speed

19. [ ] **Add automated testing in CI**
    - Backend: `python manage.py test`
    - Frontend: `npm test`
    - Coverage: Upload to codecov.io
    - Gate: Block merge if tests fail

20. [ ] **Add security scanning in CI**
    - Tools: bandit (Python), npm audit (Node)
    - Run: On every PR
    - Fail: On HIGH severity issues
    - Report: Summary in PR comment

21. [ ] **Set up staging environment**
    - Platform: Heroku/DigitalOcean/AWS
    - Database: PostgreSQL (managed)
    - Redis: Managed Redis instance
    - Celery: Separate worker dyno
    - Deploy: Auto-deploy from main branch

22. [ ] **Configure deployment pipeline**
    - Strategy: Blue-green or rolling
    - Steps: Test → Build → Deploy staging → Manual approve → Deploy prod
    - Rollback: One-click rollback capability
    - Smoke tests: Post-deployment health checks

23. [ ] **Add health check endpoints**
    - Endpoint: `/health/` (basic check)
    - Endpoint: `/health/db/` (database connectivity)
    - Endpoint: `/health/redis/` (Redis connectivity)
    - Endpoint: `/health/celery/` (worker status)
    - Response: JSON with status + latency

24. [ ] **Set up log aggregation**
    - Service: Papertrail/Loggly/ELK
    - Forward: All application logs
    - Index: Searchable by request ID
    - Retention: 30 days minimum

25. [ ] **Configure alerts**
    - Tool: Sentry + PagerDuty/Opsgenie
    - Alerts: Error rate spike, API latency >1s, Worker queue >100
    - Channels: Email, Slack, SMS for critical
    - On-call: Rotation schedule

26. [ ] **Add API documentation**
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
| Phase 1: Security | 7 | 7 | 0 | ✅ DONE |
| Phase 2: Architecture | 8 | 8 | 0 | ✅ DONE |
| Phase 3: Testing | 7 | 3 | 4 | 🟡 IN PROGRESS |
| Phase 4: Production | 9 | 0 | 9 | ⏳ NOT STARTED |
| Phase 5: CI/CD | 8 | 0 | 8 | ⏳ NOT STARTED |
| **TOTAL** | **39** | **18** | **21** | **46% Complete** |

---

## 🎯 Next Actions (Recommended Order)

### This Week
1. Run and verify all tests pass
2. Run security scan (bandit)
3. Add query optimization where needed
4. Fix FFmpeg path to use environment variable
5. Fix frontend API URL to use environment variable

### Next Week
6. Set up coverage reporting
7. Add frontend component tests
8. Refactor large React component
9. Set up linting (black, flake8, eslint)
10. Pin all dependencies

### Following Weeks
11. Migrate to PostgreSQL
12. Implement Whisper model caching
13. Add structured logging
14. Set up Sentry
15. Begin CI/CD setup

---

## 📝 Notes

- **Test Suite:** 51 tests created (811 lines across 3 test files)
- **Refactoring:** views.py (2,369 lines) → 10 modules | tasks.py (2,644 lines) → 7 modules
- **Security:** All critical vulnerabilities fixed
- **Database:** 13 indexes added and migrated
- **Backups:** Original files saved as views_old.py and tasks_old.py

---

## 🔗 References

- Code Review Report: `docs/CODE_REVIEW_REPORT.md`
- Refactoring Summary: `docs/REFACTORING_SUMMARY.md`
- New Architecture: `docs/ARCHITECTURE_NEW.md`
- Test Files: `backend/audioDiagnostic/tests/`
- View Modules: `backend/audioDiagnostic/views/`
- Task Modules: `backend/audioDiagnostic/tasks/`
