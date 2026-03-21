# Phase 2: AI Detection API - Deployment Guide

**Date:** March 21, 2026  
**Phase:** 2 - Celery Tasks & API Endpoints  
**Status:** ✅ Complete, Ready for Deployment

---

## What Was Built

Phase 2 adds the **backend API infrastructure** for AI-powered duplicate detection:

### 1. **Celery Tasks** (`ai_tasks.py` - 610 lines)
- **ai_detect_duplicates_task()** - Main AI detection with paragraph expansion
- **ai_compare_pdf_task()** - PDF comparison and verification
- **estimate_ai_cost_task()** - Cost estimation without API call

**Features:**
- Redis progress tracking (0-100%)
- Cost enforcement ($50/month per user limit)
- Error logging in `AIProcessingLog` database
- Status updates in JSON format
- Paragraph expansion (optional)

### 2. **Serializers** (`serializers.py` - +150 lines)
- **Request Serializers:** Input validation for API calls
  * `AIDetectionRequestSerializer` - Validates detection parameters
  * `AIPDFComparisonRequestSerializer` - Validates PDF comparison
  * `AICostEstimateRequestSerializer` - Validates cost estimates
  
- **Response Serializers:** Format database results for API responses
  * `AIDuplicateDetectionResultSerializer`
  * `AIPDFComparisonResultSerializer`
  * `AIProcessingLogSerializer`

**Validation:**
- Input ranges: `min_words` (1-20), `similarity_threshold` (0.5-1.0)
- Audio file existence checks
- Transcription verification
- User permissions

### 3. **API Views** (`ai_detection_views.py` - 380 lines)
Six new REST API endpoints:

1. **POST /api/ai-detection/detect/**  
   Trigger AI duplicate detection
   ```json
   {
     "audio_file_id": 123,
     "min_words": 3,
     "similarity_threshold": 0.85,
     "keep_occurrence": "last",
     "enable_paragraph_expansion": false
   }
   ```

2. **GET /api/ai-detection/status/{task_id}/**  
   Get task progress and status (0-100%)

3. **POST /api/ai-detection/compare-pdf/**  
   Trigger AI PDF comparison
   ```json
   {
     "audio_file_id": 123
   }
   ```

4. **POST /api/ai-detection/estimate-cost/**  
   Get cost estimate (no API call)
   ```json
   {
     "audio_duration_seconds": 3600,
     "task_type": "duplicate_detection"
   }
   ```

5. **GET /api/ai-detection/results/{audio_file_id}/**  
   Get all AI detection results for an audio file

6. **GET /api/ai-detection/user-cost/**  
   Get user's monthly AI cost usage

### 4. **URL Routing** (`urls.py`)
Added routes for all new endpoints

---

## Prerequisites

**Before deploying Phase 2, Phase 1 must be deployed:**
- ✅ AI service layer (4 Python modules)
- ✅ Database models (3 new models)
- ✅ Django settings with AI configuration
- ✅ `anthropic==0.39.0` package installed
- ✅ Database migrations run
- ✅ API key in `.env` file

**If Phase 1 is not deployed, see:** `docs/AI-models/PHASE1_DEPLOYMENT.md`

---

## Deployment Steps

### Option 1: Automated (Recommended)

Already included in Phase 1 deployment script. If Phase 1 is deployed, Phase 2 is just a git pull:

```bash
ssh nickd@82.165.221.205
cd /opt/audioapp
sudo git pull origin master
sudo docker-compose restart audioapp audioapp_celery_worker
```

### Option 2: Manual

```bash
# 1. SSH to server
ssh nickd@82.165.221.205

# 2. Navigate to app directory
cd /opt/audioapp

# 3. Pull latest code
sudo git pull origin master

# 4. Restart services (no migrations needed - Phase 2 is code only)
sudo docker-compose restart audioapp
sudo docker-compose restart audioapp_celery_worker

# 5. Verify Celery can import new tasks
sudo docker-compose exec audioapp_celery_worker celery -A myproject inspect registered | grep ai_detect_duplicates_task
```

**Expected Output:**
```
  * audioDiagnostic.tasks.ai_tasks.ai_detect_duplicates_task
  * audioDiagnostic.tasks.ai_tasks.ai_compare_pdf_task
  * audioDiagnostic.tasks.ai_tasks.estimate_ai_cost_task
```

---

## Testing

### 1. Test Cost Estimation (No API Call, Free)

```bash
curl -X POST http://82.165.221.205:8000/api/ai-detection/estimate-cost/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "audio_duration_seconds": 3600,
    "task_type": "duplicate_detection"
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "estimate": {
    "estimated_input_tokens": 27000,
    "estimated_output_tokens": 5400,
    "estimated_cost_usd": 0.162,
    "task_type": "duplicate_detection",
    "audio_duration_seconds": 3600
  }
}
```

### 2. Test User Cost Endpoint

```bash
curl -X GET http://82.165.221.205:8000/api/ai-detection/user-cost/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected Response:**
```json
{
  "success": true,
  "current_month_cost": 0.0,
  "limit": 50.0,
  "usage_percentage": 0.0,
  "remaining": 50.0,
  "month": "March 2026",
  "recent_transactions": []
}
```

### 3. Test AI Detection (Real API Call - ~$0.06 cost)

**⚠️ This makes a real Anthropic API call and costs money**

```bash
# First, upload an audio file and transcribe it (or use existing audio_file_id)

# Then trigger AI detection:
curl -X POST http://82.165.221.205:8000/api/ai-detection/detect/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "audio_file_id": YOUR_AUDIO_FILE_ID,
    "min_words": 3,
    "similarity_threshold": 0.85,
    "keep_occurrence": "last",
    "enable_paragraph_expansion": false
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "task_id": "abc123-def456-...",
  "message": "AI duplicate detection started",
  "audio_file_id": 123,
  "estimated_cost": {...},
  "status_url": "/api/ai-detection/status/abc123-def456-.../"
}
```

### 4. Check Task Status

```bash
# Poll for progress (every 5 seconds)
curl -X GET http://82.165.221.205:8000/api/ai-detection/status/TASK_ID/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected Responses:**

**Processing (0-100%):**
```json
{
  "success": true,
  "task_id": "abc123...",
  "state": "STARTED",
  "progress": 45,
  "status": "processing",
  "message": "Calling AI service..."
}
```

**Complete:**
```json
{
  "success": true,
  "task_id": "abc123...",
  "state": "SUCCESS",
  "progress": 100,
  "status": "completed",
  "message": "AI detection complete",
  "result": {
    "success": true,
    "result_id": 456,
    "duplicate_count": 12,
    "cost_usd": 0.0623
  },
  "detection_result": {
    "id": 456,
    "duplicate_groups": [...],
    "api_cost_usd": "0.0623",
    "average_confidence": 0.92,
    ...
  }
}
```

### 5. Get Results

```bash
curl -X GET http://82.165.221.205:8000/api/ai-detection/results/AUDIO_FILE_ID/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected Response:**
```json
{
  "success": true,
  "count": 1,
  "results": [
    {
      "id": 456,
      "audio_file": 123,
      "audio_file_title": "Chapter 1.mp3",
      "user_username": "nickd",
      "ai_provider": "anthropic",
      "ai_model": "claude-3-5-sonnet-20241022",
      "processing_date": "2026-03-21T10:30:00Z",
      "processing_time_seconds": 8.5,
      "input_tokens": 27134,
      "output_tokens": 5423,
      "total_tokens": 32557,
      "api_cost_usd": "0.0623",
      "duplicate_groups": [
        {
          "group_id": 1,
          "duplicate_text": "Welcome to chapter one",
          "occurrences": [
            {
              "occurrence_id": 1,
              "segment_ids": [5, 6],
              "start_time": 12.5,
              "end_time": 14.8,
              "text": "Welcome to chapter one",
              "confidence_score": 0.95,
              "action": "keep"
            },
            {
              "occurrence_id": 2,
              "segment_ids": [234, 235],
              "start_time": 456.2,
              "end_time": 458.5,
              "text": "Welcome to chapter one",
              "confidence_score": 0.94,
              "action": "delete"
            }
          ]
        }
      ],
      "duplicate_count": 12,
      "average_confidence": 0.92,
      "user_confirmed": false,
      "user_modified": false
    }
  ]
}
```

---

## Troubleshooting

### Error: "Monthly AI cost limit exceeded"

**Cause:** User has spent $50+ this month  
**Solution:**
```python
# SSH to server and check/reset limit:
sudo docker-compose exec audioapp python manage.py shell

from django.core.cache import cache
from datetime import datetime

user_id = 1
month_key = f"ai_cost_{user_id}_{datetime.now().strftime('%Y_%m')}"

# Check current usage
print(f"Current usage: ${cache.get(month_key, 0.0)}")

# Reset (for testing):
cache.delete(month_key)

# Or increase limit in settings:
# AI_COST_LIMIT_PER_USER_PER_MONTH=100.00
```

### Error: "Audio file must be transcribed first"

**Cause:** Audio file has no transcription  
**Solution:** Transcribe the file first via Tab 2 API

### Error: "Permission denied"

**Cause:** User doesn't own the audio file's project  
**Solution:** Check authentication token and audio file ownership

### Error: "Celery task not found"

**Cause:** Celery worker not restarted after deployment  
**Solution:**
```bash
sudo docker-compose restart audioapp_celery_worker
```

### Task Stuck in "PENDING" State

**Cause:** Celery worker crashed or not processing  
**Solution:**
```bash
# Check worker logs
sudo docker-compose logs --tail=50 audioapp_celery_worker

# Restart worker
sudo docker-compose restart audioapp_celery_worker
```

---

## File Changes Summary

**Phase 2 added/modified 4 files:**

1. **NEW:** `backend/audioDiagnostic/tasks/ai_tasks.py` (610 lines)
   - 3 Celery tasks with full error handling

2. **NEW:** `backend/audioDiagnostic/views/ai_detection_views.py` (380 lines)
   - 6 API endpoints with permissions/validation

3. **MODIFIED:** `backend/audioDiagnostic/serializers.py` (+150 lines)
   - 6 new serializers for request/response

4. **MODIFIED:** `backend/audioDiagnostic/urls.py` (+7 lines)
   - URL routing for AI endpoints

**Total Lines Added:** ~1,150 lines

---

## What's Next?

**Phase 3: Frontend Integration** (Weeks 4-5)
- React components for AI detection toggle
- Progress indicator during AI processing
- Confidence score display
- Waveform markers for AI results
- PDF discrepancy viewer

**Phase 4: Testing** (Week 5)
- Unit tests for AI services
- Integration tests for Celery tasks
- E2E tests for full workflow

**Phase 5: Production Deployment** (Week 6)
- User acceptance testing
- Performance optimization
- Production monitoring

**Phase 6: Monitoring** (Week 7-8)
- Cost tracking dashboard
- Error monitoring
- User analytics

---

## Cost Monitoring

**Real-time monitoring:**
```bash
# Check user's current month cost
curl http://82.165.221.205:8000/api/ai-detection/user-cost/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# View all processing logs
sudo docker-compose exec audioapp python manage.py shell
>>> from audioDiagnostic.models import AIProcessingLog
>>> logs = AIProcessingLog.objects.filter(status='success').order_by('-timestamp')[:10]
>>> for log in logs:
...     print(f"{log.user.username}: ${log.cost_usd} - {log.task_type}")
```

**Monthly report:**
```python
from audioDiagnostic.models import AIProcessingLog
from datetime import datetime

year, month = 2026, 3
total = AIProcessingLog.get_user_monthly_cost(user, year, month)
print(f"Total for {datetime(year, month, 1).strftime('%B %Y')}: ${total}")
```

---

## Success Criteria

Phase 2 is successfully deployed when:

- ✅ All 6 API endpoints return valid responses
- ✅ Cost estimation works without authentication
- ✅ AI detection task starts and completes successfully
- ✅ Task status updates show progress (0-100%)
- ✅ Results are stored in database with cost tracking
- ✅ User cost limit enforcement works
- ✅ Celery worker can execute all 3 new tasks

---

## Support

**Documentation:**
- Phase 1: `docs/AI-models/PHASE1_DEPLOYMENT.md`
- Planning: `docs/AI-models/AI_DUPLICATE_DETECTION_TODO.md`
- Architecture: `docs/AI-models/AI_DUPLICATE_DETECTION_ARCHITECTURE.md`

**Contact:** Agent-built on March 21, 2026

**Estimated Cost Per Hour of Audio:**
- Duplicate Detection: ~$0.06/hour
- PDF Comparison: ~$0.08/hour
- Total Processing: ~$0.14/hour

**Safe Testing Budget:** $5-10 for initial testing (50-100 hours of audio)
