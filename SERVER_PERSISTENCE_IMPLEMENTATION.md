# Server Persistence Implementation - TODO Tracker

**Project:** Audio App - Client-Side Transcription Persistence  
**Date Created:** March 10, 2026  
**Status:** Planning Phase  
**Priority:** HIGH

---

## 📋 Overview

Implement backend API to persist client-side transcription results, enabling:
- Save/retrieve transcriptions processed in browser
- Duplicate detection across sessions
- User-specific transcription history
- Segment-level duplicate analysis

---

## ✅ Phase 1: Database Models

### 1.1 Create ClientTranscription Model
**File:** `/opt/audioapp/backend/audioDiagnostic/models.py`

**Status:** ⏳ NOT STARTED  
**Fields Required:**
- [ ] `id` (AutoField, primary key)
- [ ] `user` (ForeignKey to User, indexed)
- [ ] `original_file_name` (CharField, max_length=500)
- [ ] `file_hash` (CharField, max_length=64, indexed for duplicate detection)
- [ ] `duration_seconds` (FloatField)
- [ ] `transcription_data` (JSONField - stores segments array)
- [ ] `processing_metadata` (JSONField - model info, browser, etc.)
- [ ] `created_at` (DateTimeField, auto_now_add, indexed)
- [ ] `updated_at` (DateTimeField, auto_now)

**Indexes:**
- [ ] Composite index on (user, created_at)
- [ ] Index on file_hash for duplicate detection
- [ ] Index on user for filtering

**Meta:**
- [ ] ordering = ['-created_at']
- [ ] verbose_name = 'Client Transcription'

---

### 1.2 Create DuplicateAnalysis Model
**File:** `/opt/audioapp/backend/audioDiagnostic/models.py`

**Status:** ⏳ NOT STARTED  
**Fields Required:**
- [ ] `id` (AutoField, primary key)
- [ ] `transcription` (ForeignKey to ClientTranscription, CASCADE)
- [ ] `segment_index` (IntegerField)
- [ ] `segment_text` (TextField)
- [ ] `duplicate_count` (IntegerField, default=1)
- [ ] `duplicate_indices` (JSONField - list of other indices)
- [ ] `analyzed_at` (DateTimeField, auto_now_add)

**Indexes:**
- [ ] Composite index on (transcription, segment_index)

---

## ✅ Phase 2: Database Migration

### 2.1 Create Initial Migration
**Status:** ⏳ NOT STARTED

**Tasks:**
- [ ] Run: `python manage.py makemigrations audioDiagnostic`
- [ ] Review migration file
- [ ] Run: `python manage.py migrate audioDiagnostic`
- [ ] Verify tables created in database

---

## ✅ Phase 3: Serializers

### 3.1 Create ClientTranscriptionSerializer
**File:** `/opt/audioapp/backend/audioDiagnostic/serializers.py`

**Status:** ⏳ NOT STARTED  
**Requirements:**
- [ ] Include all model fields
- [ ] Read-only: id, created_at, updated_at
- [ ] Validate file_hash (SHA-256 format)
- [ ] Validate transcription_data structure
- [ ] Add user from request.user automatically

---

### 3.2 Create DuplicateAnalysisSerializer
**File:** `/opt/audioapp/backend/audioDiagnostic/serializers.py`

**Status:** ⏳ NOT STARTED  
**Requirements:**
- [ ] Include all model fields
- [ ] Nested segment details
- [ ] Duplicate percentage calculation

---

## ✅ Phase 4: API Views

### 4.1 ClientTranscriptionListCreateView
**File:** `/opt/audioapp/backend/audioDiagnostic/views/client_storage.py`

**Status:** ⏳ NOT STARTED  
**Endpoint:** `POST /api/client-transcriptions/`

**Requirements:**
- [ ] Authentication required
- [ ] Create new transcription record
- [ ] Check for duplicates by file_hash
- [ ] Return 201 Created with transcription data
- [ ] Handle validation errors

---

### 4.2 ClientTranscriptionDetailView
**File:** `/opt/audioapp/backend/audioDiagnostic/views/client_storage.py`

**Status:** ⏳ NOT STARTED  
**Endpoint:** `GET /api/client-transcriptions/<id>/`

**Requirements:**
- [ ] Authentication required
- [ ] Retrieve specific transcription
- [ ] User can only access their own transcriptions
- [ ] Return 404 if not found or not authorized

---

### 4.3 ClientTranscriptionListView
**File:** `/opt/audioapp/backend/audioDiagnostic/views/client_storage.py`

**Status:** ⏳ NOT STARTED  
**Endpoint:** `GET /api/client-transcriptions/`

**Requirements:**
- [ ] Authentication required
- [ ] List user's transcriptions
- [ ] Pagination support
- [ ] Filter by date range
- [ ] Search by filename
- [ ] Order by created_at DESC

---

### 4.4 DuplicateAnalysisView
**File:** `/opt/audioapp/backend/audioDiagnostic/views/client_storage.py`

**Status:** ⏳ NOT STARTED  
**Endpoint:** `POST /api/client-transcriptions/<id>/analyze-duplicates/`

**Requirements:**
- [ ] Authentication required
- [ ] Analyze transcription for duplicate segments
- [ ] Create DuplicateAnalysis records
- [ ] Return analysis summary
- [ ] Handle edge cases (empty transcription, etc.)

---

## ✅ Phase 5: URL Configuration

### 5.1 Add API Routes
**File:** `/opt/audioapp/backend/audioDiagnostic/urls.py`

**Status:** ⏳ NOT STARTED  
**Routes to Add:**
- [ ] `POST /api/client-transcriptions/` → ClientTranscriptionListCreateView
- [ ] `GET /api/client-transcriptions/` → ClientTranscriptionListView
- [ ] `GET /api/client-transcriptions/<id>/` → ClientTranscriptionDetailView
- [ ] `POST /api/client-transcriptions/<id>/analyze-duplicates/` → DuplicateAnalysisView

---

## ✅ Phase 6: Permissions & Security

### 6.1 Authentication Setup
**Status:** ⏳ NOT STARTED

**Tasks:**
- [ ] Verify authentication middleware active
- [ ] Add IsAuthenticated permission to all views
- [ ] Add user ownership check (users only see their data)
- [ ] Test with authenticated and unauthenticated requests

---

### 6.2 CORS Configuration
**Status:** ⏳ NOT STARTED

**Tasks:**
- [ ] Verify CORS allows frontend domain
- [ ] Test cross-origin requests
- [ ] Configure allowed methods (GET, POST)

---

## ✅ Phase 7: Testing

### 7.1 Backend API Testing
**Status:** ⏳ NOT STARTED

**Tasks:**
- [ ] Test POST create transcription
- [ ] Test GET list transcriptions
- [ ] Test GET single transcription
- [ ] Test duplicate analysis
- [ ] Test authentication enforcement
- [ ] Test user isolation (can't see other users' data)
- [ ] Test validation errors
- [ ] Test pagination

---

### 7.2 Frontend Integration
**Status:** ⏳ NOT STARTED

**Tasks:**
- [ ] Update frontend to call save API after transcription
- [ ] Add UI to view saved transcriptions
- [ ] Add duplicate analysis visualization
- [ ] Test error handling
- [ ] Test loading states

---

## ✅ Phase 8: Deployment

### 8.1 Database Migration on Production
**Status:** ⏳ NOT STARTED

**Tasks:**
- [ ] Backup production database
- [ ] Run migrations on production
- [ ] Verify tables created
- [ ] Test API endpoints on production

---

### 8.2 Docker Container Update
**Status:** ⏳ NOT STARTED

**Tasks:**
- [ ] Update backend container with new code
- [ ] Restart backend service
- [ ] Verify no errors in logs
- [ ] Test API endpoints

---

## 📊 Progress Summary

**Total Tasks:** 60+  
**Completed:** 0  
**In Progress:** 0  
**Not Started:** 60+  

**Current Phase:** Phase 1 - Database Models  
**Next Step:** Create ClientTranscription and DuplicateAnalysis models

---

## 🔧 Prerequisites

**Before Starting:**
- [ ] Verify Django project structure
- [ ] Check database connection
- [ ] Confirm audioDiagnostic app exists
- [ ] Review existing models.py structure
- [ ] Backup current database

---

## 📝 Notes

- All changes should be made in `/opt/audioapp/backend/`
- Test each phase before moving to next
- Keep migrations reversible
- Document any deviations from plan
- Update this file as tasks complete

---

## 🚀 Quick Start Commands

```bash
# Navigate to backend
cd /opt/audioapp/backend

# Activate virtual environment (if needed)
source venv/bin/activate

# Create migrations
python manage.py makemigrations audioDiagnostic

# Apply migrations
python manage.py migrate

# Test API
python manage.py test audioDiagnostic

# Run development server
python manage.py runserver
```

---

**Last Updated:** March 10, 2026  
**Updated By:** Copilot  
**Status:** Ready to begin implementation
