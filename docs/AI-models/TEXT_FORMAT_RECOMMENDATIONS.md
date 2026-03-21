# AI Text Format Recommendations

**Created:** March 21, 2026  
**Purpose:** Define optimal formats for AI processing of audio transcriptions

---

## 📋 Overview

This document specifies the recommended text formats for:
1. **Input to AI** - How to send transcription data to AI models
2. **Output from AI** - How AI should return duplicate detection results
3. **Waveform Integration** - Format for displaying results in the waveform editor
4. **PDF Comparison** - Format for comparing transcript to PDF reference

---

## 1. Input Format: Transcription to AI

### Recommended Format: **Structured JSON with Metadata**

**Why JSON?**
- ✅ Preserves all timing information (crucial for audio editing)
- ✅ Maintains word-level granularity
- ✅ Easy for AI models to parse and understand
- ✅ Contains full context in structured way
- ✅ Can include confidence scores from transcription
- ✅ Supports hierarchical data (segments → words)

### JSON Schema

```json
{
  "metadata": {
    "audio_file_id": 123,
    "filename": "audiobook_chapter1.wav",
    "duration_seconds": 3600.5,
    "total_segments": 450,
    "total_words": 12500,
    "transcription_method": "whisper-large-v3",
    "transcription_date": "2026-03-21T10:30:00Z",
    "language": "en",
    "model_confidence_avg": 0.92
  },
  
  "segments": [
    {
      "segment_id": 1,
      "text": "Hello, welcome to this audiobook.",
      "start_time": 0.0,
      "end_time": 2.5,
      "duration": 2.5,
      "confidence": 0.95,
      "segment_index": 0,
      
      "words": [
        {
          "word": "Hello",
          "start": 0.0,
          "end": 0.5,
          "confidence": 0.96
        },
        {
          "word": "welcome",
          "start": 0.6,
          "end": 1.2,
          "confidence": 0.94
        },
        {
          "word": "to",
          "start": 1.3,
          "end": 1.4,
          "confidence": 0.92
        },
        {
          "word": "this",
          "start": 1.5,
          "end": 1.7,
          "confidence": 0.93
        },
        {
          "word": "audiobook",
          "start": 1.8,
          "end": 2.5,
          "confidence": 0.97
        }
      ]
    },
    {
      "segment_id": 2,
      "text": "This is chapter one.",
      "start_time": 2.6,
      "end_time": 4.8,
      "duration": 2.2,
      "confidence": 0.89,
      "segment_index": 1,
      
      "words": [...]
    }
    // ... more segments
  ],
  
  "detection_settings": {
    "min_words_to_match": 3,
    "similarity_threshold": 0.85,
    "keep_occurrence": "last",
    "enable_semantic_matching": true,
    "enable_paragraph_expansion": true
  }
}
```

### Alternative Format: **Plain Text with Timestamps (SRT-like)**

For simpler AI models or token budget constraints:

```
1
00:00:00,000 --> 00:00:02,500
Hello, welcome to this audiobook.

2
00:00:02,600 --> 00:00:04,800
This is chapter one.

3
00:00:04,900 --> 00:00:08,300
The story begins on a dark and stormy night.

...
```

**When to use:**
- ⚠️ When JSON token count is too expensive
- ⚠️ When AI model struggles with JSON parsing
- ⚠️ For human readability needs

**Limitations:**
- ❌ No word-level timing
- ❌ No confidence scores
- ❌ Harder to maintain structure
- ❌ More parsing required

**Verdict:** Use JSON as primary format, SRT as fallback

---

## 2. Output Format: AI Detection Results

### Recommended Format: **Nested JSON with Action Items**

```json
{
  "analysis_metadata": {
    "ai_model": "gpt-4-turbo-2024-04-09",
    "api_version": "2024-02-15-preview",
    "processing_timestamp": "2026-03-21T10:35:42Z",
    "total_processing_time_seconds": 18.5,
    "total_tokens_used": 12450,
    "estimated_cost_usd": 0.124,
    "tasks_completed": [
      "sentence_duplicate_detection",
      "paragraph_expansion",
      "semantic_similarity_analysis"
    ]
  },
  
  "duplicate_groups": [
    {
      "group_id": "dup_001",
      "duplicate_text": "Hello, welcome to this audiobook.",
      "detection_method": "exact_match",
      "confidence": 0.99,
      "reason": "Identical text repeated 3 times",
      "severity": "high",
      "keep_occurrence": "last",
      
      "occurrences": [
        {
          "occurrence_id": 1,
          "segment_ids": [1],
          "start_time": 0.0,
          "end_time": 2.5,
          "duration": 2.5,
          "text": "Hello, welcome to this audiobook.",
          "action": "delete",
          "action_reason": "Earlier occurrence, marked for deletion"
        },
        {
          "occurrence_id": 2,
          "segment_ids": [45],
          "start_time": 120.0,
          "end_time": 122.5,
          "duration": 2.5,
          "text": "Hello, welcome to this audiobook.",
          "action": "delete",
          "action_reason": "Middle occurrence, marked for deletion"
        },
        {
          "occurrence_id": 3,
          "segment_ids": [189],
          "start_time": 480.0,
          "end_time": 482.5,
          "duration": 2.5,
          "text": "Hello, welcome to this audiobook.",
          "action": "keep",
          "action_reason": "Last occurrence, keeping as final version"
        }
      ],
      
      "time_saved_seconds": 5.0,
      "paragraph_context": null
    },
    
    {
      "group_id": "dup_002",
      "duplicate_text": "The story begins on a dark and stormy night. Thunder crashed overhead as rain poured down.",
      "detection_method": "semantic_match",
      "confidence": 0.87,
      "reason": "Semantically similar paragraphs detected",
      "severity": "medium",
      "keep_occurrence": "last",
      
      "occurrences": [
        {
          "occurrence_id": 1,
          "segment_ids": [15, 16],
          "start_time": 45.0,
          "end_time": 52.5,
          "duration": 7.5,
          "text": "The story begins on a dark and stormy night. Thunder crashed overhead as rain poured down.",
          "action": "delete",
          "action_reason": "Semantically identical paragraph, earlier occurrence"
        },
        {
          "occurrence_id": 2,
          "segment_ids": [95, 96],
          "start_time": 285.0,
          "end_time": 292.0,
          "duration": 7.0,
          "text": "The narrative started on a tempestuous evening. Lightning flashed while heavy rain fell.",
          "action": "keep",
          "action_reason": "Last occurrence with slightly different wording, keeping for variety"
        }
      ],
      
      "time_saved_seconds": 7.5,
      "paragraph_context": {
        "expanded": true,
        "original_segment_ids": [15],
        "expanded_segment_ids": [15, 16],
        "expansion_reason": "Full paragraph repeat detected"
      }
    }
  ],
  
  "processing_summary": {
    "total_segments_analyzed": 450,
    "total_words_analyzed": 12500,
    "duplicate_groups_found": 35,
    "total_duplicate_occurrences": 112,
    "occurrences_to_delete": 77,
    "occurrences_to_keep": 35,
    "total_time_to_remove_seconds": 285.5,
    "total_time_to_remove_formatted": "04:45.5",
    "percentage_duplicates": 7.9,
    "confidence_distribution": {
      "high_confidence": 28,
      "medium_confidence": 6,
      "low_confidence": 1
    }
  },
  
  "waveform_markers": [
    {
      "marker_id": "marker_001",
      "type": "duplicate_region_start",
      "time": 0.0,
      "group_id": "dup_001",
      "occurrence_id": 1,
      "color": "#FF5555",
      "label": "Duplicate (Delete)",
      "confidence": 0.99
    },
    {
      "marker_id": "marker_002",
      "type": "duplicate_region_end",
      "time": 2.5,
      "group_id": "dup_001",
      "occurrence_id": 1,
      "color": "#FF5555"
    },
    {
      "marker_id": "marker_003",
      "type": "duplicate_region_start",
      "time": 480.0,
      "group_id": "dup_001",
      "occurrence_id": 3,
      "color": "#55FF55",
      "label": "Duplicate (Keep)",
      "confidence": 0.99
    },
    {
      "marker_id": "marker_004",
      "type": "duplicate_region_end",
      "time": 482.5,
      "group_id": "dup_001",
      "occurrence_id": 3,
      "color": "#55FF55"
    }
    // ... more markers
  ]
}
```

### Key Features

**1. AI Metadata:**
- Model version (for reproducibility)
- Processing time (for performance tracking)
- Cost (for budget monitoring)
- Tasks completed (for transparency)

**2. Duplicate Groups:**
- Unique ID for each group
- Detection method (exact/semantic)
- Confidence score (0-1)
- Human-readable reason
- Severity level (high/medium/low)

**3. Occurrences:**
- Each instance of the duplicate
- Clear action (delete/keep)
- Reason for action
- Timing information

**4. Waveform Integration:**
- Pre-formatted markers for direct display
- Color coding for visual distinction
- Labels for user clarity

---

## 3. Waveform Display Format

### Visual Representation

```
Timeline (seconds):
0    60   120  180  240  300  360  420  480  540  600
|=====|=====|=====|=====|=====|=====|=====|=====|=====|

Waveform with markers:
|██████|      |███|         |█████|           |███|
|DUP(D)|      |D  |         |DUP(D)|          |K  |
| 99%  |      |87%|         | 99%  |          |99%|
|______|______|___|_________|______|__________|___|

Legend:
██ = Audio waveform
D  = Duplicate (Delete) - Red
K  = Duplicate (Keep) - Green
99% = AI Confidence
```

### Data Structure for Waveform Component

```typescript
interface WaveformMarker {
  id: string;
  type: 'duplicate_delete' | 'duplicate_keep' | 'pdf_discrepancy';
  startTime: number;
  endTime: number;
  groupId: string;
  color: string;
  label: string;
  confidence: number;
  tooltip: string;
  editable: boolean;
}

interface WaveformData {
  audioUrl: string;
  duration: number;
  markers: WaveformMarker[];
  regions: WaveformRegion[];
}
```

**Color Scheme:**
- 🔴 **Red (#FF5555)** - Duplicate to delete (high confidence >90%)
- 🟠 **Orange (#FF9955)** - Duplicate to delete (medium confidence 70-90%)
- 🟡 **Yellow (#FFFF55)** - Duplicate to delete (low confidence <70%)
- 🟢 **Green (#55FF55)** - Duplicate to keep
- 🔵 **Blue (#5555FF)** - PDF discrepancy
- ⚫ **Gray (#999999)** - AI processing region

---

## 4. PDF Comparison Format

### Input Format

```json
{
  "clean_transcript": {
    "text": "Full transcript after duplicate removal...",
    "segments": [
      {
        "segment_id": 1,
        "text": "Segment text",
        "start_time": 0.0,
        "end_time": 2.5,
        "kept": true
      }
    ],
    "metadata": {
      "original_duration": 3600,
      "clean_duration": 3300,
      "time_saved": 300
    }
  },
  
  "pdf_reference": {
    "filename": "audiobook_reference.pdf",
    "total_pages": 250,
    "full_text": "Entire PDF content as text...",
    "extraction_method": "pdfplumber",
    "extraction_quality": 0.95
  },
  
  "comparison_settings": {
    "enable_semantic_matching": true,
    "detect_missing_content": true,
    "detect_extra_content": true,
    "detect_paraphrasing": true,
    "similarity_threshold": 0.80
  }
}
```

### Output Format

```json
{
  "alignment_result": {
    "pdf_section_found": true,
    "pdf_start_page": 15,
    "pdf_end_page": 24,
    "pdf_start_char": 2500,
    "pdf_end_char": 15000,
    "alignment_method": "semantic_similarity",
    "coverage_percentage": 98.5,
    "confidence": 0.93,
    "total_pdf_characters": 125000,
    "matched_characters": 12320
  },
  
  "discrepancies": [
    {
      "discrepancy_id": "disc_001",
      "type": "missing_in_audio",
      "severity": "high",
      "pdf_text": "This is an entire paragraph from the PDF that doesn't appear in the audio at all.",
      "pdf_location": {
        "page": 18,
        "paragraph": 3,
        "char_start": 5600,
        "char_end": 5780
      },
      "expected_audio_location": {
        "after_segment_id": 145,
        "estimated_timestamp": 450.0,
        "estimated_duration": 15.0
      },
      "confidence": 0.91,
      "suggested_action": "Review PDF to determine if intentionally skipped"
    },
    
    {
      "discrepancy_id": "disc_002",
      "type": "extra_in_audio",
      "severity": "medium",
      "audio_text": "This sentence was spoken in the audio but doesn't appear anywhere in the PDF.",
      "audio_location": {
        "segment_id": 189,
        "start_time": 588.5,
        "end_time": 593.2,
        "duration": 4.7
      },
      "pdf_search_attempted": true,
      "confidence": 0.87,
      "suggested_action": "Verify if this is narrator commentary or ad-lib"
    },
    
    {
      "discrepancy_id": "disc_003",
      "type": "paraphrased",
      "severity": "low",
      "pdf_text": "The cat sat comfortably on the mat.",
      "audio_text": "The feline was resting on the rug.",
      "semantic_similarity": 0.82,
      "pdf_location": {
        "page": 20,
        "paragraph": 7,
        "char_start": 8900,
        "char_end": 8935
      },
      "audio_location": {
        "segment_id": 205,
        "start_time": 638.0,
        "end_time": 641.5,
        "duration": 3.5
      },
      "confidence": 0.88,
      "suggested_action": "Accept if paraphrasing is acceptable, flag if exact match required"
    }
  ],
  
  "clean_transcript_annotated": {
    "format": "markdown",
    "content": "# Clean Transcript with PDF Comparison\n\n[00:00 - 00:03] Hello, welcome to this audiobook.\n\n[00:03 - 00:06] This is chapter one.\n\n**[MISSING: PDF page 18, paragraph 3]**\n*Expected content: \"This is an entire paragraph from the PDF...\"*\n*Estimated timestamp: 00:07:30*\n\n[00:07 - 00:10] Continuing with the story...\n\n[00:10 - 00:13] **[EXTRA]** This sentence was spoken but not in PDF.\n\n[00:14 - 00:17] **[PARAPHRASED - 82% similar]**\nAudio: \"The feline was resting on the rug.\"\nPDF: \"The cat sat comfortably on the mat.\"\n\n..."
  },
  
  "comparison_summary": {
    "total_discrepancies": 15,
    "missing_count": 3,
    "extra_count": 5,
    "paraphrased_count": 7,
    "high_severity": 3,
    "medium_severity": 7,
    "low_severity": 5,
    "requires_user_review": 10,
    "auto_acceptable": 5
  }
}
```

---

## 5. Best Practices for AI Processing

### Token Optimization

**1. Segment Large Transcripts:**
```python
# Don't send 3 hours at once (too many tokens)
# Instead, process in chunks of 30-60 minutes

def chunk_transcript(segments, max_duration=1800):  # 30 minutes
    chunks = []
    current_chunk = []
    current_duration = 0
    
    for segment in segments:
        duration = segment['end_time'] - segment['start_time']
        if current_duration + duration > max_duration:
            chunks.append(current_chunk)
            current_chunk = [segment]
            current_duration = duration
        else:
            current_chunk.append(segment)
            current_duration += duration
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks
```

**2. Minimize Redundancy:**
```json
// ❌ Bad: Repeating metadata in every segment
{
  "segments": [
    {
      "filename": "audio.wav",  // Don't repeat!
      "transcription_method": "whisper",  // Don't repeat!
      "text": "Hello world"
    }
  ]
}

// ✅ Good: Metadata once at top level
{
  "metadata": {
    "filename": "audio.wav",
    "transcription_method": "whisper"
  },
  "segments": [
    {"text": "Hello world"},
    {"text": "Next segment"}
  ]
}
```

**3. Use Concise Field Names:**
```json
// ✅ Short keys save tokens
{"id": 1, "txt": "...", "s": 0.0, "e": 2.5}

// ❌ Long keys waste tokens
{"segment_identifier": 1, "text_content": "...", "start_timestamp": 0.0, "end_timestamp": 2.5}
```

### AI Model Selection

**Recommended Models by Use Case:**

| Use Case | Recommended Model | Cost/1M Tokens | Speed | Accuracy |
|----------|------------------|----------------|-------|----------|
| Simple duplicate detection | GPT-3.5-turbo | $0.50 | Very Fast | Good |
| Complex semantic analysis | GPT-4-turbo | $10 | Fast | Excellent |
| Budget-conscious | Claude 3 Haiku | $0.25 | Very Fast | Good |
| High accuracy needed | Claude 3 Opus | $15 | Medium | Excellent |
| Balanced option | Claude 3 Sonnet | $3 | Fast | Very Good |

**Recommendation:** Start with **Claude 3 Sonnet** (good balance of cost, speed, accuracy)

---

## 6. Error Handling in Formats

### Input Validation

```python
def validate_transcript_json(data):
    """Validate transcript JSON before sending to AI"""
    
    required_fields = ['metadata', 'segments']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
    
    if not isinstance(data['segments'], list):
        raise ValueError("Segments must be a list")
    
    if len(data['segments']) == 0:
        raise ValueError("Segments cannot be empty")
    
    for i, segment in enumerate(data['segments']):
        if 'text' not in segment:
            raise ValueError(f"Segment {i} missing text field")
        if 'start_time' not in segment:
            raise ValueError(f"Segment {i} missing start_time")
        if 'end_time' not in segment:
            raise ValueError(f"Segment {i} missing end_time")
        
        if segment['end_time'] <= segment['start_time']:
            raise ValueError(f"Segment {i} has invalid timing")
    
    return True
```

### Output Validation

```python
def validate_ai_response(response):
    """Validate AI response format"""
    
    if 'duplicate_groups' not in response:
        raise ValueError("AI response missing duplicate_groups field")
    
    for group in response['duplicate_groups']:
        if 'group_id' not in group:
            raise ValueError("Duplicate group missing ID")
        if 'occurrences' not in group:
            raise ValueError("Duplicate group missing occurrences")
        if len(group['occurrences']) < 2:
            raise ValueError("Duplicate group must have at least 2 occurrences")
        
        for occ in group['occurrences']:
            if 'action' not in occ or occ['action'] not in ['keep', 'delete']:
                raise ValueError(f"Invalid action in occurrence: {occ.get('action')}")
    
    return True
```

---

## 7. Summary & Recommendations

### ✅ Primary Recommendations

1. **Input Format:** **JSON with nested structure**
   - Preserves all timing data
   - Easy for AI to parse
   - Maintains word-level granularity

2. **Output Format:** **Structured JSON with action items**
   - Clear duplicate groups
   - Explicit actions (keep/delete)
   - Waveform-ready markers
   - Human-readable reasons

3. **Waveform Format:** **Timeline markers + regions**
   - Visual color coding
   - Confidence scores displayed
   - Editable timestamps
   - Tooltips for context

4. **PDF Format:** **Annotated markdown + JSON**
   - Easy to read for users
   - Actionable discrepancies
   - Clear severity levels
   - Suggested actions

### 🎯 Key Takeaways

- **Structured > Unstructured:** JSON beats plain text
- **Context Matters:** Include metadata, confidence, reasons
- **Visual Clarity:** Color coding and labels improve UX
- **Token Optimization:** Balance detail vs. cost
- **Validation:** Always validate input and output
- **Flexibility:** Support multiple formats for different use cases

---

**Next Steps:**
1. Implement input formatting in backend
2. Design prompt templates with these formats
3. Create output parsing logic
4. Build waveform visualization components
5. Test with real audio transcriptions

**Related Documents:**
- [AI_DUPLICATE_DETECTION_PLAN.md](AI_DUPLICATE_DETECTION_PLAN.md)
- [AI_DUPLICATE_DETECTION_TODO.md](AI_DUPLICATE_DETECTION_TODO.md)
