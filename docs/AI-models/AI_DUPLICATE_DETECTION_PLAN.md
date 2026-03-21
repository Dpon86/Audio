# AI-Powered Duplicate Detection - Implementation Plan

**Created:** March 21, 2026  
**Status:** 📋 Planning Phase  
**Priority:** High - Major Feature Enhancement

---

## 🎯 Executive Summary

**Goal:** Add AI-powered duplicate detection as an alternative to the current algorithmic approach, providing intelligent context-aware duplicate identification with minimal user configuration.

**Current System:** Algorithm-based duplicate detection (TF-IDF, windowed retry, PDF hints)  
**Proposed Addition:** AI-powered analysis using LLM for context-aware duplicate detection

**Key Constraint:** Server has only 4GB RAM - **Cannot run large language models locally**

---

## 📋 Feature Overview

### User Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Transcription (Existing)                           │
│  • Upload audio file                                        │
│  • Transcribe (client-side or server-side)                 │
│  • Upload PDF reference document (optional)                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Choose Detection Method (NEW)                      │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │   Algorithm      │   OR    │   AI-Powered     │         │
│  │  (Current Fast)  │         │  (New Smart)     │         │
│  └──────────────────┘         └──────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: AI Analysis (NEW)                                  │
│  • Task 1: Sentence-level duplicate detection              │
│  • Task 2: Paragraph-level expansion                       │
│  • Task 3: PDF comparison & verification                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: Review & Edit (Existing with Enhancements)        │
│  • View detected duplicates on waveform                    │
│  • AI confidence scores displayed                          │
│  • Manual timestamp adjustment                             │
│  • Accept/reject AI suggestions                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🤖 AI Task Breakdown

### Task 1: Sentence-Level Duplicate Detection

**Input:**
```json
{
  "segments": [
    {
      "segment_id": 1,
      "text": "Hello, welcome to the audiobook.",
      "start_time": 0.0,
      "end_time": 2.5,
      "words": [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "welcome", "start": 0.6, "end": 1.2},
        {"word": "to", "start": 1.3, "end": 1.4},
        {"word": "the", "start": 1.5, "end": 1.6},
        {"word": "audiobook", "start": 1.7, "end": 2.5}
      ]
    },
    // ... more segments
  ],
  "detection_settings": {
    "min_words_to_match": 3,
    "similarity_threshold": 0.85,
    "keep_occurrence": "last"  // or "first"
  }
}
```

**AI Task:**
1. Analyze all segments for semantic similarity (not just exact matches)
2. Identify repeated phrases (minimum 3 words by default)
3. Group related repetitions together
4. Mark which occurrence to keep (default: last)
5. Calculate confidence scores

**Output:**
```json
{
  "duplicate_groups": [
    {
      "group_id": "dup_001",
      "duplicate_text": "Hello, welcome to the audiobook.",
      "confidence": 0.95,
      "keep_occurrence": "last",
      "occurrences": [
        {
          "occurrence_id": 1,
          "segment_ids": [1],
          "start_time": 0.0,
          "end_time": 2.5,
          "action": "delete",
          "reason": "Exact duplicate, keeping last occurrence"
        },
        {
          "occurrence_id": 2,
          "segment_ids": [45],
          "start_time": 120.0,
          "end_time": 122.5,
          "action": "keep",
          "reason": "Last occurrence retained"
        }
      ]
    }
  ],
  "processing_summary": {
    "total_segments_analyzed": 500,
    "duplicate_groups_found": 25,
    "total_duplicates": 75,
    "total_time_to_remove": 187.5,
    "ai_model": "gpt-4-turbo",
    "processing_time_seconds": 15.3
  }
}
```

### Task 2: Paragraph-Level Expansion

**Input:** Results from Task 1 + original transcript

**AI Task:**
1. Take each duplicate group from Task 1
2. Expand context window around each occurrence
3. Check if entire paragraph is repeated (not just sentences)
4. Adjust timestamps to include full paragraph if matched
5. Use semantic understanding to identify paragraph boundaries

**Example:**
```
Original detection: "He walked down the street." (5 seconds)
Expansion analysis: Checks surrounding 3-5 sentences
If context matches: "He woke up early. He walked down the street. 
                     The sun was rising." (15 seconds)
Adjusted timestamps: 10.0 → 25.0 (instead of 12.0 → 17.0)
```

**Output:** Updated duplicate groups with expanded timestamps

### Task 3: PDF Comparison & Verification

**Input:**
```json
{
  "clean_transcript": "Final text after removing duplicates...",
  "pdf_text": "Full PDF text content...",
  "pdf_metadata": {
    "filename": "book.pdf",
    "total_pages": 250,
    "extraction_method": "pdfplumber"
  }
}
```

**AI Task:**
1. Identify the section in PDF that corresponds to the audio transcript
2. Perform alignment between clean transcript and PDF section
3. Detect discrepancies:
   - **Missing content:** In PDF but not in transcript
   - **Extra content:** In transcript but not in PDF
   - **Modified phrasing:** Semantic differences
4. Calculate coverage percentage
5. Generate alignment map

**Output:**
```json
{
  "alignment_result": {
    "pdf_section_found": true,
    "pdf_start_page": 15,
    "pdf_end_page": 24,
    "pdf_start_char": 2500,
    "pdf_end_char": 15000,
    "coverage_percentage": 98.5,
    "confidence": 0.93
  },
  "discrepancies": [
    {
      "type": "missing_in_audio",
      "pdf_text": "This paragraph appears in the PDF but not in audio.",
      "pdf_location": "Page 18, paragraph 3",
      "expected_timestamp_range": [150.0, 165.0],
      "severity": "high"
    },
    {
      "type": "extra_in_audio",
      "audio_text": "This sentence was spoken but isn't in the PDF.",
      "audio_timestamp": [245.0, 250.0],
      "severity": "medium"
    },
    {
      "type": "paraphrased",
      "pdf_text": "The cat sat on the mat.",
      "audio_text": "The feline was sitting on the rug.",
      "semantic_similarity": 0.87,
      "audio_timestamp": [78.0, 81.5],
      "severity": "low"
    }
  ],
  "clean_transcript_with_markers": "Text with [MISSING], [EXTRA], [PARAPHRASED] markers..."
}
```

---

## 📊 Recommended Text Formats

### Format 1: Input to AI (Structured JSON)

**Why:** 
- Preserves all timestamp data
- Easy to parse programmatically
- Well-suited for API calls
- Maintains word-level timing information

**Structure:**
```json
{
  "metadata": {
    "audio_file_id": 123,
    "filename": "audiobook_chapter1.wav",
    "duration_seconds": 3600,
    "transcription_method": "whisper-large-v3",
    "language": "en"
  },
  "segments": [
    {
      "id": 1,
      "text": "Segment text here",
      "start": 0.0,
      "end": 2.5,
      "confidence": 0.95,
      "words": [...]
    }
  ],
  "pdf_reference": {
    "filename": "reference.pdf",
    "text": "Full PDF text...",
    "pages": 250
  }
}
```

### Format 2: Output from AI (Structured + Human-Readable)

**Why:**
- Frontend can easily parse and display
- Compatible with existing waveform editor
- Human-readable for debugging
- Includes AI reasoning for transparency

**Structure:**
```json
{
  "analysis_metadata": {
    "ai_model": "gpt-4-turbo",
    "processing_date": "2026-03-21T10:30:00Z",
    "total_processing_time": 15.3,
    "tasks_completed": ["duplicate_detection", "paragraph_expansion", "pdf_comparison"]
  },
  "duplicate_groups": [...],  // As shown above
  "pdf_alignment": {...},     // As shown above
  "visualization_data": {
    // Formatted specifically for waveform display
    "timeline_markers": [
      {
        "type": "duplicate_start",
        "time": 10.0,
        "group_id": "dup_001",
        "color": "#ff0000"
      },
      {
        "type": "duplicate_end",
        "time": 12.5,
        "group_id": "dup_001"
      }
    ]
  },
  "user_review_items": [
    {
      "id": "review_001",
      "type": "missing_content",
      "description": "Content found in PDF but not in audio",
      "location": "After timestamp 150.0s",
      "action_required": true,
      "suggested_action": "Review and decide if intentional"
    }
  ]
}
```

### Format 3: Clean Transcript Output (Markdown with Annotations)

**Why:**
- Easy to read and edit
- Preserves structure
- Can include inline comments
- Exportable format

**Example:**
```markdown
# Clean Transcript - Chapter 1

**Metadata:**
- Original Duration: 60:00
- Clean Duration: 45:30 (14:30 removed)
- Duplicates Removed: 25 groups
- PDF Coverage: 98.5%

---

## Transcript

[00:00:00 - 00:02:30] Hello, welcome to the audiobook.

[00:02:30 - 00:05:15] This is chapter one.

~~[REMOVED: 00:05:15 - 00:07:45] Duplicate of section at 01:20:00~~

[00:07:45 - 00:10:00] Continuing with the story...

[MISSING: Expected content from PDF page 18 should appear here]

[00:10:00 - 00:12:30] [PARAPHRASED: PDF says "The cat sat on the mat", Audio says "The feline was sitting on the rug"]

---

## Summary

- Total Segments: 250
- Segments Removed: 75
- Time Saved: 14:30
- Discrepancies Found: 3
```

---

## 🏗️ Architecture Design

### Option A: External API (RECOMMENDED for 4GB RAM)

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React)                                       │
│  • "Use AI Detection" toggle button                    │
│  • Progress indicator for AI processing                │
│  • Display AI confidence scores                        │
└─────────────────────────────────────────────────────────┘
                        ↓ HTTP Request
┌─────────────────────────────────────────────────────────┐
│  Backend (Django) - 4GB RAM Server                      │
│  • Receives transcription + PDF                         │
│  • Formats data for AI API                             │
│  • Calls external API (OpenAI/Anthropic)               │
│  • Processes AI response                               │
│  • Stores results in database                          │
└─────────────────────────────────────────────────────────┘
                        ↓ API Call
┌─────────────────────────────────────────────────────────┐
│  External AI Service                                    │
│  • OpenAI GPT-4 Turbo (Recommended)                    │
│  • Anthropic Claude 3 (Alternative)                    │
│  • Google Gemini Pro (Alternative)                     │
└─────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ No additional RAM needed
- ✅ State-of-the-art AI models
- ✅ Fast processing
- ✅ No GPU required
- ✅ Automatic updates/improvements
- ✅ Scales easily

**Cons:**
- ❌ Ongoing API costs (~$0.01-0.10 per audio hour)
- ❌ Requires internet connection
- ❌ Data sent to third party
- ❌ Rate limits

**Cost Estimate:**
- 1 hour transcription = ~10,000 tokens input + ~2,000 tokens output
- GPT-4 Turbo: ~$0.10 per hour of audio analyzed
- 100 hours/month = ~$10-15/month
- Claude 3 Sonnet: ~$0.03 per hour (cheaper alternative)

### Option B: Local Small Model (NOT RECOMMENDED)

**Would require:**
- Minimum 8GB RAM (you have 4GB)
- 4GB GPU VRAM (you don't have)
- Much slower processing
- Lower accuracy

**Verdict:** Not feasible with current hardware

### Option C: Hybrid Approach (BEST FOR PRIVACY-CONSCIOUS USERS)

```
┌─────────────────────────────────────────────────────────┐
│  User Chooses:                                          │
│  ┌──────────────────┐         ┌──────────────────┐     │
│  │   Local Model    │   OR    │   Cloud AI       │     │
│  │  (Limited Feat)  │         │  (Full Feat)     │     │
│  └──────────────────┘         └──────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

- **Local:** Use lightweight rule-based AI for basic duplicate detection
- **Cloud:** Use GPT-4 for advanced semantic analysis

---

## 🖥️ Server Requirements

### Current Server: 4GB RAM
**Limitations:**
- ❌ Cannot run LLMs locally (need 8GB+ RAM)
- ❌ Cannot run embedding models (need 4-6GB)
- ❌ Cannot load large ML frameworks

### Recommended Configuration for This Feature:

**Keep Current Server + Add External AI API:**
- Current: 4GB RAM for Django + PostgreSQL + Celery ✅
- New: External API calls (OpenAI GPT-4 Turbo) ✅
- Cost: ~$10-20/month for typical usage ✅

**Alternative: Upgrade Server (if budget allows):**
- **Option 1:** 8GB RAM + CPU-only
  - Can run small models (DistilBERT, small LLaMA)
  - Slower processing (30-60s per hour of audio)
  - One-time cost increase
  
- **Option 2:** 16GB RAM + GPU (T4 or better)
  - Can run medium models (LLaMA 7B, Mistral 7B)
  - Fast processing (5-10s per hour of audio)
  - Significant cost increase ($50-100/month)

**Recommendation:** **Stick with 4GB + External API** - Most cost-effective and reliable

---

## 🔄 Processing Pipeline

### Pipeline Flow

```
1. User uploads audio + PDF
   ↓
2. Transcription (existing)
   ↓
3. User clicks "Use AI Detection" button
   ↓
4. Backend Task Queue (Celery)
   ├─ Task 1: Format data for AI
   ├─ Task 2: Call AI API (Sentence detection)
   ├─ Task 3: Call AI API (Paragraph expansion)
   ├─ Task 4: Call AI API (PDF comparison)
   └─ Task 5: Store results
   ↓
5. Frontend displays results
   ├─ Waveform markers (duplicates)
   ├─ Confidence scores
   ├─ PDF discrepancies
   └─ Clean transcript preview
   ↓
6. User reviews and adjusts
   ↓
7. Server-side assembly (existing)
```

### Celery Tasks (New)

```python
# backend/audioDiagnostic/tasks/ai_tasks.py

@shared_task
def ai_detect_duplicates_task(audio_file_id, settings):
    """
    Main AI duplicate detection task
    """
    # 1. Load transcription
    # 2. Format for AI API
    # 3. Call OpenAI GPT-4 API
    # 4. Parse response
    # 5. Store results
    # 6. Update progress
    pass

@shared_task
def ai_expand_paragraphs_task(audio_file_id, duplicate_groups):
    """
    Expand duplicate detections to full paragraphs
    """
    pass

@shared_task
def ai_compare_pdf_task(audio_file_id, pdf_id):
    """
    Compare clean transcript to PDF
    """
    pass
```

---

## 🎨 Frontend Changes

### New UI Components

**1. Detection Method Selector (Tab 3)**
```jsx
<div className="detection-method-selector">
  <button 
    className={method === 'algorithm' ? 'active' : ''}
    onClick={() => setMethod('algorithm')}
  >
    <span className="icon">⚡</span>
    Algorithm Detection
    <span className="subtitle">Fast, rule-based</span>
  </button>
  
  <button 
    className={method === 'ai' ? 'active' : ''}
    onClick={() => setMethod('ai')}
  >
    <span className="icon">🤖</span>
    AI Detection
    <span className="subtitle">Smart, context-aware</span>
  </button>
</div>
```

**2. AI Confidence Display**
```jsx
<div className="duplicate-item">
  <div className="duplicate-text">
    "Hello, welcome to the audiobook."
  </div>
  <div className="ai-confidence">
    <span className="label">AI Confidence:</span>
    <span className="score">95%</span>
    <span className="tooltip">
      High confidence - Exact semantic match
    </span>
  </div>
  <div className="timestamps">
    00:10.5 - 00:13.2 (2.7s)
  </div>
</div>
```

**3. PDF Discrepancy Viewer**
```jsx
<div className="pdf-discrepancies">
  <h3>PDF Comparison Results</h3>
  <div className="coverage-meter">
    Coverage: 98.5%
  </div>
  
  <div className="discrepancy-list">
    <div className="discrepancy missing">
      <span className="icon">⚠️</span>
      <span className="text">Missing content at 02:30</span>
      <button>Review</button>
    </div>
  </div>
</div>
```

---

## 💾 Database Schema Changes

### New Models

```python
# backend/audioDiagnostic/models.py

class AIDuplicateDetectionResult(models.Model):
    """Stores AI-powered duplicate detection results"""
    audio_file = models.ForeignKey(AudioFile, related_name='ai_duplicate_results')
    
    # AI metadata
    ai_model = models.CharField(max_length=50)  # "gpt-4-turbo"
    processing_date = models.DateTimeField(auto_now_add=True)
    processing_time_seconds = models.FloatField()
    api_cost_usd = models.DecimalField(max_digits=10, decimal_places=4)
    
    # Results
    duplicate_groups = models.JSONField()  # Full AI response
    confidence_scores = models.JSONField()  # Per-group confidence
    
    # Settings used
    detection_settings = models.JSONField()
    
    class Meta:
        ordering = ['-processing_date']


class AIPDFComparisonResult(models.Model):
    """Stores AI PDF comparison results"""
    audio_file = models.ForeignKey(AudioFile, related_name='ai_pdf_comparisons')
    pdf_file = models.ForeignKey('PDFFile', related_name='ai_comparisons')
    
    # AI metadata
    ai_model = models.CharField(max_length=50)
    processing_date = models.DateTimeField(auto_now_add=True)
    
    # Results
    alignment_result = models.JSONField()
    discrepancies = models.JSONField()
    coverage_percentage = models.FloatField()
    confidence_score = models.FloatField()
    
    # Clean transcript with markers
    clean_transcript_marked = models.TextField()
    
    class Meta:
        ordering = ['-processing_date']
```

---

## 🔒 Security & Privacy Considerations

### Data Handling

**What gets sent to AI API:**
- ✅ Transcription text (necessary)
- ✅ Timestamps (necessary)
- ✅ PDF text (necessary for comparison)
- ❌ Audio files (NOT sent)
- ❌ User personal info (NOT sent)

### Privacy Options

**1. User Consent:**
```python
# Add to user settings
class UserSettings(models.Model):
    allow_ai_processing = models.BooleanField(default=False)
    ai_provider_preference = models.CharField(
        choices=[
            ('openai', 'OpenAI GPT-4'),
            ('anthropic', 'Anthropic Claude'),
            ('local', 'Local Processing Only')
        ]
    )
```

**2. Data Minimization:**
- Only send necessary text
- Strip personal identifiers
- Anonymize before API call

**3. Audit Log:**
```python
class AIProcessingLog(models.Model):
    user = models.ForeignKey(User)
    audio_file = models.ForeignKey(AudioFile)
    ai_provider = models.CharField(max_length=50)
    data_sent_bytes = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=4)
```

---

## 📈 Performance Expectations

### Processing Times (GPT-4 Turbo)

| Audio Duration | AI Processing Time | Cost Estimate |
|----------------|-------------------|---------------|
| 5 minutes      | 3-5 seconds       | $0.01         |
| 30 minutes     | 10-15 seconds     | $0.05         |
| 1 hour         | 20-30 seconds     | $0.10         |
| 3 hours        | 60-90 seconds     | $0.30         |

### Comparison to Algorithm

| Feature | Algorithm | AI-Powered |
|---------|-----------|------------|
| Speed | ⚡ Very Fast (1-5s) | 🐢 Slower (10-30s) |
| Accuracy | 📊 Good (85-92%) | 🎯 Excellent (95-99%) |
| Context Awareness | ❌ Limited | ✅ Excellent |
| Semantic Understanding | ❌ No | ✅ Yes |
| Cost | ✅ Free | 💰 ~$0.10/hour |
| Requires Internet | ❌ No | ✅ Yes |

---

## 🧪 Testing Strategy

### Test Cases

**1. Exact Duplicates**
- Input: "Hello world" repeated 3 times
- Expected: All occurrences detected, last one kept

**2. Paraphrased Duplicates**
- Input: "The cat sat on the mat" vs "The feline was on the rug"
- Expected: Detected with high confidence

**3. Paragraph Expansion**
- Input: Sentence detected as duplicate
- Expected: Full surrounding paragraph checked and included

**4. PDF Comparison**
- Input: Audio transcript + PDF reference
- Expected: Missing/extra content identified

**5. Edge Cases**
- Very long transcripts (3+ hours)
- Multiple languages
- Technical content
- Poetry/song lyrics

---

## 💰 Cost Analysis

### Monthly Cost Estimates

**Low Usage (10 hours/month):**
- API Cost: ~$1-2/month
- Total: Very affordable

**Medium Usage (100 hours/month):**
- API Cost: ~$10-15/month
- Total: Reasonable for small business

**High Usage (1000 hours/month):**
- API Cost: ~$100-150/month
- Total: May want to consider local model

### Cost Optimization Strategies

1. **Caching:** Store AI results to avoid re-processing
2. **Batch Processing:** Process multiple files in single API call
3. **Smart Prompts:** Optimize prompts to reduce token usage
4. **Provider Switching:** Use cheaper models for simple tasks
5. **Hybrid Approach:** Use algorithm first, AI for failures

---

## 🔮 Future Enhancements

### Phase 2 Features

1. **Multi-Language Support**
   - Detect duplicates in any language
   - Cross-language comparison

2. **Custom AI Training**
   - Fine-tune on user's specific audiobook style
   - Improve accuracy over time

3. **Real-Time Suggestions**
   - AI suggestions during transcription
   - Live duplicate detection

4. **Batch Processing**
   - Process entire book series at once
   - Consistent style across files

5. **AI Quality Scoring**
   - Rate transcription quality
   - Suggest re-recording sections

---

## ✅ Success Metrics

### KPIs to Track

1. **Accuracy:** % of correctly identified duplicates
2. **False Positives:** % of incorrect detections
3. **User Satisfaction:** Rating of AI vs algorithm
4. **Processing Time:** Average time per hour of audio
5. **Cost per Hour:** API cost tracking
6. **Adoption Rate:** % of users choosing AI mode

---

## 🚀 Rollout Plan

### Phase 1: MVP (2-3 weeks)
- ✅ External AI API integration (OpenAI GPT-4)
- ✅ Basic duplicate detection (Task 1)
- ✅ Frontend toggle button
- ✅ Results display on waveform

### Phase 2: Enhanced Features (2-3 weeks)
- ✅ Paragraph expansion (Task 2)
- ✅ PDF comparison (Task 3)
- ✅ Confidence scores
- ✅ User review interface

### Phase 3: Polish & Optimize (1-2 weeks)
- ✅ Cost optimization
- ✅ Performance tuning
- ✅ User testing & feedback
- ✅ Documentation

### Phase 4: Production (Ongoing)
- ✅ Monitor costs
- ✅ Track accuracy
- ✅ User support
- ✅ Continuous improvement

---

**Next Steps:** See [AI_DUPLICATE_DETECTION_TODO.md](AI_DUPLICATE_DETECTION_TODO.md) for detailed implementation tasks.
