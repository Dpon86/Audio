# AI Duplicate Detection - Implementation TODO

**Created:** March 21, 2026  
**Status:** 📋 Ready for Development  
**Estimated Time:** 6-8 weeks total

---

## 📋 Task Breakdown

### ✅ = Complete | 🟡 = In Progress | ⏳ = Blocked | ❌ = Not Started

---

## Phase 1: Foundation & Setup (Week 1-2)

### Task 1.1: Project Setup ❌
**Priority:** High  
**Estimated Time:** 2-3 hours  
**Dependencies:** None

- [ ] Create new folder: `backend/audioDiagnostic/services/ai/`
- [ ] Create new folder: `frontend/audio-waveform-visualizer/src/services/ai/`
- [ ] Create new folder: `docs/AI-models/`
- [ ] Set up environment variables for AI API keys
- [ ] Add `openai` package to `requirements.txt`
- [ ] Add API key configuration to Django settings
- [ ] Create AI configuration model in database

**Files to Create:**
- `backend/audioDiagnostic/services/ai/__init__.py`
- `backend/audioDiagnostic/services/ai/openai_client.py`
- `backend/audioDiagnostic/services/ai/prompt_templates.py`
- `backend/.env.example` (add AI API key placeholders)

**Acceptance Criteria:**
- ✅ OpenAI API key configured and tested
- ✅ Connection to OpenAI API verified
- ✅ Basic test call succeeds

---

### Task 1.2: Database Schema ❌
**Priority:** High  
**Estimated Time:** 3-4 hours  
**Dependencies:** Task 1.1

- [ ] Create `AIDuplicateDetectionResult` model
- [ ] Create `AIPDFComparisonResult` model  
- [ ] Create `AIProcessingLog` model
- [ ] Create `AIProcessingSetting` model (user preferences)
- [ ] Generate migrations
- [ ] Run migrations
- [ ] Create admin interface for new models
- [ ] Add indexes for performance

**Files to Modify:**
- `backend/audioDiagnostic/models.py`
- `backend/audioDiagnostic/admin.py`

**Acceptance Criteria:**
- ✅ All models created successfully
- ✅ Migrations applied without errors
- ✅ Admin interface accessible
- ✅ Sample data can be created

---

### Task 1.3: API Client Setup ❌
**Priority:** High  
**Estimated Time:** 4-5 hours  
**Dependencies:** Task 1.1

- [ ] Create OpenAI API client wrapper
- [ ] Implement retry logic with exponential backoff
- [ ] Add rate limiting handling
- [ ] Create token counting utility
- [ ] Add cost calculation function
- [ ] Implement error handling
- [ ] Create logging for API calls
- [ ] Add timeout configuration

**Files to Create:**
- `backend/audioDiagnostic/services/ai/openai_client.py`
- `backend/audioDiagnostic/services/ai/token_counter.py`
- `backend/audioDiagnostic/services/ai/cost_calculator.py`

**Code Example:**
```python
class OpenAIClient:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4-turbo-preview"
    
    def detect_duplicates(self, transcript_data, settings):
        """Call OpenAI API for duplicate detection"""
        pass
    
    def expand_paragraphs(self, duplicate_groups, context):
        """Expand duplicates to paragraph level"""
        pass
    
    def compare_to_pdf(self, transcript, pdf_text):
        """Compare transcript to PDF"""
        pass
```

**Acceptance Criteria:**
- ✅ API client can make successful calls
- ✅ Rate limiting works correctly
- ✅ Costs are tracked accurately
- ✅ Errors are handled gracefully

---

## Phase 2: Core AI Tasks (Week 2-4)

### Task 2.1: Prompt Engineering ❌
**Priority:** High  
**Estimated Time:** 8-10 hours  
**Dependencies:** Task 1.3

- [ ] Design prompt for Task 1 (sentence-level duplicates)
- [ ] Design prompt for Task 2 (paragraph expansion)
- [ ] Design prompt for Task 3 (PDF comparison)
- [ ] Test prompts with sample data
- [ ] Optimize for token usage
- [ ] Add few-shot examples to prompts
- [ ] Version prompts for A/B testing
- [ ] Document prompt format

**Files to Create:**
- `backend/audioDiagnostic/services/ai/prompt_templates.py`

**Prompt Example (Task 1):**
```python
DUPLICATE_DETECTION_PROMPT = """
You are an expert audiobook editor analyzing transcripts for duplicate content.

Your task: Identify repeated sentences or phrases in the transcript below.

Rules:
1. Find semantic duplicates (not just exact matches)
2. Minimum {min_words} words to qualify as duplicate
3. Group related repetitions together
4. Mark which occurrence to keep (default: {keep_occurrence})
5. Calculate confidence score (0-1) for each group

Input format:
```json
{
  "segments": [
    {"id": 1, "text": "...", "start": 0.0, "end": 2.5},
    ...
  ]
}
```

Output format:
```json
{
  "duplicate_groups": [
    {
      "group_id": "dup_001",
      "duplicate_text": "...",
      "confidence": 0.95,
      "occurrences": [...]
    }
  ]
}
```

Transcript:
{transcript_json}

Settings:
- Minimum words to match: {min_words}
- Keep occurrence: {keep_occurrence}
- Similarity threshold: {similarity_threshold}

Analyze and return ONLY the JSON output:
"""
```

**Acceptance Criteria:**
- ✅ Prompts generate accurate results
- ✅ Token usage is optimized
- ✅ Output format is consistent
- ✅ Edge cases are handled

---

### Task 2.2: Task 1 - Sentence-Level Detection ❌
**Priority:** High  
**Estimated Time:** 6-8 hours  
**Dependencies:** Task 2.1

- [ ] Implement data formatting for AI input
- [ ] Create Celery task: `ai_detect_duplicates_task()`
- [ ] Call OpenAI API with formatted data
- [ ] Parse AI response
- [ ] Validate response format
- [ ] Store results in database
- [ ] Create API endpoint: `/api/projects/{id}/files/{id}/ai-detect-duplicates/`
- [ ] Add progress tracking

**Files to Create:**
- `backend/audioDiagnostic/tasks/ai_duplicate_tasks.py`
- `backend/audioDiagnostic/services/ai/duplicate_detector.py`
- `backend/audioDiagnostic/views/ai_detection_views.py`

**Code Example:**
```python
@shared_task(bind=True)
def ai_detect_duplicates_task(self, audio_file_id, settings):
    """
    AI-powered duplicate detection task
    """
    audio_file = AudioFile.objects.get(id=audio_file_id)
    
    # 1. Format transcription data
    transcript_data = format_transcript_for_ai(audio_file)
    
    # 2. Call OpenAI API
    client = OpenAIClient()
    result = client.detect_duplicates(transcript_data, settings)
    
    # 3. Store results
    AIDuplicateDetectionResult.objects.create(
        audio_file=audio_file,
        duplicate_groups=result['duplicate_groups'],
        ai_model='gpt-4-turbo',
        processing_time_seconds=result['processing_time'],
        api_cost_usd=result['cost']
    )
    
    # 4. Update progress
    self.update_state(state='SUCCESS', meta={'result': result})
    
    return result
```

**Acceptance Criteria:**
- ✅ Task processes transcripts successfully
- ✅ Duplicate groups are identified accurately
- ✅ Confidence scores are meaningful
- ✅ Results are stored in database
- ✅ API endpoint returns results

---

### Task 2.3: Task 2 - Paragraph Expansion ❌
**Priority:** Medium  
**Estimated Time:** 6-8 hours  
**Dependencies:** Task 2.2

- [ ] Create expansion algorithm
- [ ] Design expansion prompt
- [ ] Implement context window extraction
- [ ] Create Celery task: `ai_expand_paragraphs_task()`
- [ ] Integrate with Task 1 results
- [ ] Update timestamps for expanded groups
- [ ] Add validation for expansions
- [ ] Test with various paragraph structures

**Files to Create:**
- `backend/audioDiagnostic/services/ai/paragraph_expander.py`

**Logic Flow:**
```
For each duplicate group from Task 1:
  1. Extract context (N segments before/after)
  2. Send context + duplicate to AI
  3. AI analyzes if paragraph is repeated
  4. If yes, adjust start/end timestamps
  5. Update duplicate group in database
```

**Acceptance Criteria:**
- ✅ Paragraphs are correctly identified
- ✅ Timestamps are adjusted accurately
- ✅ No false expansions
- ✅ Processing time is reasonable

---

### Task 2.4: Task 3 - PDF Comparison ❌
**Priority:** Medium  
**Estimated Time:** 8-10 hours  
**Dependencies:** Task 2.2

- [ ] Create PDF text extraction utility (if not exists)
- [ ] Design PDF comparison prompt
- [ ] Implement alignment algorithm
- [ ] Create Celery task: `ai_compare_pdf_task()`
- [ ] Detect missing content
- [ ] Detect extra content
- [ ] Detect paraphrased content
- [ ] Calculate coverage percentage
- [ ] Create API endpoint: `/api/projects/{id}/files/{id}/ai-pdf-compare/`
- [ ] Store results in database

**Files to Create:**
- `backend/audioDiagnostic/services/ai/pdf_comparator.py`
- `backend/audioDiagnostic/services/ai/alignment_helper.py`

**Acceptance Criteria:**
- ✅ PDF content is extracted correctly
- ✅ Alignment is accurate (>95%)
- ✅ Discrepancies are identified
- ✅ Coverage percentage is calculated
- ✅ Results stored and retrievable

---

## Phase 3: Frontend Integration (Week 4-5)

### Task 3.1: UI Components ❌
**Priority:** High  
**Estimated Time:** 6-8 hours  
**Dependencies:** Task 2.2

- [ ] Create "Use AI Detection" toggle button
- [ ] Add AI vs Algorithm selector component
- [ ] Create AI processing indicator
- [ ] Add confidence score display
- [ ] Create PDF discrepancy viewer
- [ ] Add cost estimate display
- [ ] Create AI settings panel
- [ ] Add "What's this?" tooltips

**Files to Create:**
- `frontend/audio-waveform-visualizer/src/components/AIDetection/AIToggle.js`
- `frontend/audio-waveform-visualizer/src/components/AIDetection/AIProgress.js`
- `frontend/audio-waveform-visualizer/src/components/AIDetection/AIConfidence.js`
- `frontend/audio-waveform-visualizer/src/components/AIDetection/PDFDiscrepancies.js`

**Component Example:**
```jsx
function AIDetectionToggle({ onMethodChange }) {
  const [method, setMethod] = useState('algorithm');
  
  return (
    <div className="detection-method-selector">
      <button 
        className={method === 'algorithm' ? 'active' : ''}
        onClick={() => {
          setMethod('algorithm');
          onMethodChange('algorithm');
        }}
      >
        <span className="icon">⚡</span>
        <span className="title">Algorithm Detection</span>
        <span className="subtitle">Fast, rule-based</span>
        <span className="badge">Free</span>
      </button>
      
      <button 
        className={method === 'ai' ? 'active' : ''}
        onClick={() => {
          setMethod('ai');
          onMethodChange('ai');
        }}
      >
        <span className="icon">🤖</span>
        <span className="title">AI Detection</span>
        <span className="subtitle">Smart, context-aware</span>
        <span className="badge">~$0.10/hour</span>
      </button>
    </div>
  );
}
```

**Acceptance Criteria:**
- ✅ Toggle works smoothly
- ✅ UI is intuitive
- ✅ Progress is visible
- ✅ Confidence scores are clear
- ✅ Costs are transparent

---

### Task 3.2: API Integration ❌
**Priority:** High  
**Estimated Time:** 4-6 hours  
**Dependencies:** Task 3.1, Task 2.2

- [ ] Create AI detection service
- [ ] Implement API calls to backend
- [ ] Add polling for task status
- [ ] Handle errors gracefully
- [ ] Display results on waveform
- [ ] Show AI confidence scores
- [ ] Enable manual adjustment
- [ ] Add cancel/retry functionality

**Files to Create:**
- `frontend/audio-waveform-visualizer/src/services/ai/aiDetectionService.js`

**Service Example:**
```javascript
export async function detectDuplicatesWithAI(audioFileId, projectId, settings, token) {
  try {
    // Start AI detection task
    const response = await fetch(
      `/api/projects/${projectId}/files/${audioFileId}/ai-detect-duplicates/`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
      }
    );
    
    const { task_id } = await response.json();
    
    // Poll for results
    const result = await pollTaskStatus(task_id, token);
    
    return result;
  } catch (error) {
    console.error('[AIDetection] Error:', error);
    throw error;
  }
}
```

**Acceptance Criteria:**
- ✅ API calls work correctly
- ✅ Task status polling works
- ✅ Results are displayed
- ✅ Errors are handled
- ✅ User can cancel/retry

---

### Task 3.3: Waveform Integration ❌
**Priority:** High  
**Estimated Time:** 6-8 hours  
**Dependencies:** Task 3.2

- [ ] Display AI-detected duplicates on waveform
- [ ] Show confidence scores on markers
- [ ] Add color coding by confidence
- [ ] Enable manual timestamp adjustment
- [ ] Update duplicate groups when adjusted
- [ ] Add AI badge to duplicate items
- [ ] Show AI reasoning tooltips
- [ ] Sync with existing duplicate display

**Files to Modify:**
- `frontend/audio-waveform-visualizer/src/components/ProjectTabs/Tab3Duplicates.js`
- `frontend/audio-waveform-visualizer/src/components/Waveform/WaveformEditor.js`

**Visual Design:**
```
Waveform:
[====🤖===][====🤖===][=======][====🤖===]
     95%        92%              88%
   (Exact)   (Similar) (Para-)  (Likely)
```

**Acceptance Criteria:**
- ✅ Duplicates visible on waveform
- ✅ Confidence scores shown
- ✅ Manual adjustment works
- ✅ Visual design is clear
- ✅ Performance is good

---

### Task 3.4: PDF Comparison UI ❌
**Priority:** Medium  
**Estimated Time:** 6-8 hours  
**Dependencies:** Task 2.4, Task 3.2

- [ ] Create PDF comparison results panel
- [ ] Display coverage percentage
- [ ] Show discrepancy list
- [ ] Add filtering by type (missing/extra/paraphrased)
- [ ] Enable jump to discrepancy location
- [ ] Show PDF page reference
- [ ] Add accept/reject for discrepancies
- [ ] Export comparison report

**Files to Create:**
- `frontend/audio-waveform-visualizer/src/components/PDFComparison/ComparisonResults.js`
- `frontend/audio-waveform-visualizer/src/components/PDFComparison/DiscrepancyItem.js`

**UI Layout:**
```
╔════════════════════════════════════════╗
║  PDF Comparison Results                ║
╠════════════════════════════════════════╣
║  Coverage: 98.5% ████████████████░░    ║
║  Confidence: 93%                       ║
║                                        ║
║  Discrepancies Found: 3                ║
║  ┌─────────────────────────────────┐  ║
║  │ ⚠️ Missing at 02:30              │  ║
║  │ "This paragraph not in audio"   │  ║
║  │ PDF: Page 18, Para 3            │  ║
║  │ [Review] [Ignore]               │  ║
║  └─────────────────────────────────┘  ║
╚════════════════════════════════════════╝
```

**Acceptance Criteria:**
- ✅ Results displayed clearly
- ✅ Discrepancies are actionable
- ✅ Navigation works
- ✅ Can export report
- ✅ UI is responsive

---

## Phase 4: Testing & Quality (Week 5-6)

### Task 4.1: Unit Tests ❌
**Priority:** High  
**Estimated Time:** 8-10 hours  
**Dependencies:** Phase 2 complete

**Backend Tests:**
- [ ] Test OpenAI client wrapper
- [ ] Test prompt generation
- [ ] Test data formatting
- [ ] Test response parsing
- [ ] Test error handling
- [ ] Test cost calculation
- [ ] Test database storage
- [ ] Test Celery tasks

**Frontend Tests:**
- [ ] Test AI toggle component
- [ ] Test API service
- [ ] Test result display
- [ ] Test waveform integration
- [ ] Test PDF comparison UI

**Files to Create:**
- `backend/audioDiagnostic/tests/test_ai_detection.py`
- `backend/audioDiagnostic/tests/test_ai_prompts.py`
- `backend/audioDiagnostic/tests/test_ai_client.py`
- `frontend/audio-waveform-visualizer/src/tests/AIDetection.test.js`

**Test Coverage Goal:** >80%

**Acceptance Criteria:**
- ✅ All tests pass
- ✅ Coverage >80%
- ✅ Edge cases covered
- ✅ Error paths tested

---

### Task 4.2: Integration Tests ❌
**Priority:** High  
**Estimated Time:** 6-8 hours  
**Dependencies:** Task 4.1

- [ ] Test end-to-end flow (upload → detect → display)
- [ ] Test with real audio files
- [ ] Test with various transcript lengths
- [ ] Test with different languages
- [ ] Test PDF comparison workflow
- [ ] Test error recovery
- [ ] Test concurrent processing
- [ ] Load test API calls

**Test Scenarios:**
1. Short audio (5 min)
2. Medium audio (30 min)
3. Long audio (2 hours)
4. Audio with many duplicates (50+)
5. Audio with no duplicates
6. Audio with PDF comparison
7. Multiple files processed simultaneously

**Acceptance Criteria:**
- ✅ E2E flow works smoothly
- ✅ All scenarios pass
- ✅ Performance is acceptable
- ✅ No memory leaks

---

### Task 4.3: User Acceptance Testing ❌
**Priority:** High  
**Estimated Time:** 4-6 hours  
**Dependencies:** Task 4.2

- [ ] Create test user accounts
- [ ] Prepare test audio files
- [ ] Write user testing script
- [ ] Recruit 5-10 beta testers
- [ ] Conduct testing sessions
- [ ] Gather feedback
- [ ] Document issues
- [ ] Prioritize improvements

**Testing Script:**
1. Upload audio file
2. Transcribe audio
3. Switch to AI detection mode
4. Start detection
5. Review results
6. Adjust timestamps manually
7. Compare to PDF
8. Assemble final audio
9. Rate experience (1-5)
10. Provide feedback

**Acceptance Criteria:**
- ✅ Average rating >4/5
- ✅ Major issues identified
- ✅ Feedback documented
- ✅ Improvements planned

---

## Phase 5: Documentation & Deployment (Week 6-8)

### Task 5.1: Documentation ❌
**Priority:** Medium  
**Estimated Time:** 6-8 hours  
**Dependencies:** Phase 4 complete

- [ ] Write user guide for AI detection
- [ ] Document API endpoints
- [ ] Create developer documentation
- [ ] Write deployment guide
- [ ] Document cost management
- [ ] Create troubleshooting guide
- [ ] Add inline code comments
- [ ] Create video tutorial

**Documents to Create:**
- `docs/AI-models/USER_GUIDE.md`
- `docs/AI-models/API_DOCUMENTATION.md`
- `docs/AI-models/DEVELOPER_GUIDE.md`
- `docs/AI-models/DEPLOYMENT_GUIDE.md`
- `docs/AI-models/COST_MANAGEMENT.md`
- `docs/AI-models/TROUBLESHOOTING.md`

**Acceptance Criteria:**
- ✅ All documents complete
- ✅ Examples included
- ✅ Screenshots added
- ✅ Code samples tested

---

### Task 5.2: Performance Optimization ❌
**Priority:** Medium  
**Estimated Time:** 8-10 hours  
**Dependencies:** Task 4.2

- [ ] Profile API call performance
- [ ] Optimize prompt token usage
- [ ] Implement response caching
- [ ] Add batch processing for multiple files
- [ ] Optimize database queries
- [ ] Add API request queuing
- [ ] Implement rate limit handling
- [ ] Add retry with exponential backoff

**Optimization Targets:**
- API calls: < 30 seconds per hour of audio
- Token usage: < 10,000 tokens per hour of audio
- Cost: < $0.15 per hour of audio
- Database queries: < 5 per detection request

**Acceptance Criteria:**
- ✅ Performance targets met
- ✅ Costs optimized
- ✅ No bottlenecks
- ✅ Graceful degradation

---

### Task 5.3: Cost Management ❌
**Priority:** High  
**Estimated Time:** 4-6 hours  
**Dependencies:** Phase 2 complete

- [ ] Implement cost tracking
- [ ] Add per-user cost limits
- [ ] Create cost dashboard (admin)
- [ ] Set up billing alerts
- [ ] Implement cost optimization strategies
- [ ] Add cost estimates before processing
- [ ] Create usage reports
- [ ] Document cost breakdown

**Cost Controls:**
- Per-user monthly limit: $50 default
- Cost warning at 80% of limit
- Auto-pause at 100% unless approved
- Admin can override limits
- Track costs per file and per user

**Acceptance Criteria:**
- ✅ Costs tracked accurately
- ✅ Limits enforced
- ✅ Alerts working
- ✅ Dashboard functional

---

### Task 5.4: Staging Deployment ❌
**Priority:** High  
**Estimated Time:** 4-6 hours  
**Dependencies:** Task 5.1, Task 5.2

- [ ] Set up staging environment
- [ ] Deploy backend changes
- [ ] Deploy frontend changes
- [ ] Configure AI API keys
- [ ] Test all features on staging
- [ ] Run smoke tests
- [ ] Performance test on staging
- [ ] Document deployment steps

**Staging Checklist:**
- ✅ Environment variables set
- ✅ Database migrations applied
- ✅ Static files collected
- ✅ Celery workers running
- ✅ AI API keys valid
- ✅ All tests pass

**Acceptance Criteria:**
- ✅ Staging deployment successful
- ✅ All features working
- ✅ No critical errors
- ✅ Performance acceptable

---

### Task 5.5: Production Deployment ❌
**Priority:** High  
**Estimated Time:** 4-6 hours  
**Dependencies:** Task 5.4

- [ ] Create production deployment plan
- [ ] Schedule maintenance window
- [ ] Backup production database
- [ ] Deploy backend changes
- [ ] Deploy frontend changes
- [ ] Run database migrations
- [ ] Restart Celery workers
- [ ] Verify deployment
- [ ] Monitor for errors
- [ ] Announce new feature

**Deployment Steps:**
```bash
# 1. Backup database
ssh nickd@82.165.221.205
cd /opt/audioapp
docker exec audioapp_backend python manage.py dumpdata > backup_$(date +%Y%m%d).json

# 2. Deploy backend
git pull origin master
docker exec audioapp_backend python manage.py migrate
docker restart audioapp_celery_worker

# 3. Deploy frontend
cd frontend/audio-waveform-visualizer
npm run build
scp -r build/* nickd@82.165.221.205:/opt/audioapp/frontend/build/
ssh nickd@82.165.221.205 "cd /opt/audioapp && rsync -av --delete frontend/build/ frontend/audio-waveform-visualizer/build/ && sudo systemctl reload nginx"

# 4. Verify
curl https://audio.precisepouchtrack.com/api/health/
```

**Acceptance Criteria:**
- ✅ Deployment successful
- ✅ Zero downtime
- ✅ All features working
- ✅ No rollback needed

---

## Phase 6: Monitoring & Maintenance (Ongoing)

### Task 6.1: Monitoring Setup ❌
**Priority:** Medium  
**Estimated Time:** 6-8 hours  
**Dependencies:** Task 5.5

- [ ] Set up API error monitoring
- [ ] Add performance monitoring
- [ ] Create cost alerts
- [ ] Monitor accuracy metrics
- [ ] Track user adoption
- [ ] Set up logging dashboard
- [ ] Add Sentry error tracking
- [ ] Configure uptime monitoring

**Metrics to Track:**
- API call success rate (target: >99%)
- Average processing time
- Cost per hour of audio
- User satisfaction rating
- Duplicate detection accuracy
- False positive rate

**Acceptance Criteria:**
- ✅ Monitoring active
- ✅ Alerts configured
- ✅ Dashboard accessible
- ✅ Logs centralized

---

### Task 6.2: User Feedback Loop ❌
**Priority:** Medium  
**Estimated Time:** Ongoing  
**Dependencies:** Task 5.5

- [ ] Add feedback form in UI
- [ ] Create feedback collection process
- [ ] Review feedback weekly
- [ ] Prioritize improvements
- [ ] Track satisfaction over time
- [ ] Respond to user requests
- [ ] Document common issues
- [ ] Plan feature iterations

**Acceptance Criteria:**
- ✅ Feedback mechanism active
- ✅ Reviews conducted regularly
- ✅ Issues tracked
- ✅ Improvements implemented

---

## 🎯 Summary

### Total Estimated Time: **6-8 weeks**

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| Phase 1 | 1-2 weeks | Setup, database, API client |
| Phase 2 | 2-3 weeks | Core AI tasks (detection, expansion, PDF) |
| Phase 3 | 1-2 weeks | Frontend integration |
| Phase 4 | 1-2 weeks | Testing & QA |
| Phase 5 | 1-2 weeks | Documentation & deployment |
| Phase 6 | Ongoing | Monitoring & maintenance |

### Critical Path:
1. Task 1.1 → Task 1.2 → Task 1.3 (Foundation)
2. Task 2.1 → Task 2.2 (Core AI)
3. Task 3.1 → Task 3.2 → Task 3.3 (Frontend)
4. Task 4.1 → Task 4.2 → Task 5.4 → Task 5.5 (Deploy)

### Dependencies:
- OpenAI API key (required before starting)
- $50-100 budget for testing (estimated)
- 4GB RAM server (sufficient with external API)
- Frontend build environment (existing)

### Risks:
- API cost overruns (mitigation: cost limits)
- Accuracy issues (mitigation: extensive testing)
- Performance bottlenecks (mitigation: optimization phase)
- User adoption (mitigation: good UX + documentation)

---

**Ready to start?** Begin with Phase 1, Task 1.1!
