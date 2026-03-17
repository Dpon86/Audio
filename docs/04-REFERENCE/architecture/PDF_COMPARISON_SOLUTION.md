# PDF-to-Transcript Comparison: Problem Definition & Solution

## Problem Statement

### Given:
- **PDF Document**: The complete, correct reference text of an entire book
- **Audio Transcript**: A section of the book that has been transcribed from audio recording

### Transcript Characteristics:
1. **Partial Coverage**: Transcript contains only a portion of the full book (e.g., chapters 1-3 of a 20-chapter book)
2. **Sequential Order**: Content follows the book's order, but with possible gaps
3. **Missing Content**: 
   - Words may be skipped during reading
   - Sentences may be omitted
   - Paragraphs may be missing
4. **Extra Content**:
   - Duplicate/repeated words or sentences (reading errors)
   - Narrator additions: "Chapter One", "Narrated by John Smith"
   - Recording artifacts: "Let me start that again"
5. **Variations**: Minor wording differences due to transcription errors or natural speech variations

### Goal:
1. **Find the matching section** in the PDF that corresponds to the transcript
2. **Measure accuracy**: What percentage of the PDF section matches the transcript?
3. **Identify missing content**: What text from the PDF is absent in the transcript?
4. **Identify extra content**: What text in the transcript doesn't appear in the PDF?
5. **Enable corrections**: Allow marking extra content (narrator info, duplicates) for removal

---

## Best Solution: Sequence Alignment with Gap Tracking

### Algorithm Choice: **Modified Myers Diff Algorithm**

This is the same algorithm used by Git for file comparison. It's proven, fast, and handles insertions/deletions well.

### Why This Approach?

| Algorithm | Pros | Cons | Verdict |
|-----------|------|------|---------|
| **String Substring Match** | Simple | Fails with small differences | ❌ Too fragile |
| **Character-level Diff** | Precise | Too sensitive to punctuation | ❌ Too strict |
| **Word Overlap Percentage** | Forgiving | Misses sequential order | ⚠️ Partial solution |
| **Longest Common Subsequence (LCS)** | Finds matching sequence | Slow for large texts (O(n²)) | ⚠️ Too slow |
| **Myers Diff Algorithm** | Fast (O(ND), optimal), handles gaps well | Requires implementation | ✅ **BEST CHOICE** |
| **Smith-Waterman (DNA alignment)** | Perfect for gaps | Overkill, complex | ⚠️ Over-engineered |

### Solution: Three-Phase Alignment Algorithm

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: FIND STARTING POINT IN PDF                            │
│                                                                 │
│ Input:                                                          │
│   - PDF: [entire book, 100,000 words]                         │
│   - Transcript: [section, 10,000 words]                       │
│                                                                 │
│ Method: Sliding Window Word Matching                           │
│   1. Take first 100 words of transcript                        │
│   2. Normalize both (lowercase, remove punctuation)            │
│   3. Slide window across PDF:                                  │
│      for pdf_pos in range(len(pdf_words)):                    │
│          window = pdf_words[pdf_pos:pdf_pos+100]              │
│          similarity = count_matches(window, transcript_start)  │
│          if similarity > 0.85:  # 85% match                   │
│              found_start = pdf_pos                            │
│              break                                            │
│                                                                 │
│ Output: Start position in PDF (word index)                     │
│ Performance: O(n*m) where m=100, stops early = ~O(n)          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: EXTRACT PDF SECTION & SEQUENCE ALIGNMENT              │
│                                                                 │
│ Input:                                                          │
│   - PDF section: [from start_pos, ~12,000 words]              │
│     (transcript length * 1.2 buffer for missing content)       │
│   - Transcript: [10,000 words]                                │
│                                                                 │
│ Method: Myers Diff Algorithm (Word-Level)                      │
│   1. Represent both as sequences of normalized words           │
│   2. Build edit graph (like Git diff):                         │
│      - Match: word in PDF == word in transcript                │
│      - Delete: word in PDF, not in transcript (MISSING)        │
│      - Insert: word in transcript, not in PDF (EXTRA)          │
│   3. Find shortest edit path (optimal alignment)               │
│   4. Backtrack to get alignment:                               │
│      PDF:        "The quick brown fox jumped over dog"         │
│      Transcript: "The quick [EXTRA: Chapter One] brown fox     │
│                   jumped [MISSING: over] the dog"              │
│                                                                 │
│ Output: Aligned sequences with operation markers                │
│ Performance: O(ND) where N=sum of lengths, D=differences       │
│              For 90% match: O(0.1*N) = very fast               │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: CLASSIFY & AGGREGATE DIFFERENCES                      │
│                                                                 │
│ Input: Aligned sequences with operations                        │
│                                                                 │
│ Method: Contextual Grouping                                     │
│   1. Group consecutive operations:                              │
│      - Consecutive "DELETE" operations = Missing section        │
│      - Consecutive "INSERT" operations = Extra content          │
│   2. Reconstruct sentences from word groups                     │
│   3. Classify extra content:                                    │
│      - Contains "Chapter", "Part", "Section" → Chapter marker   │
│      - Contains "Narrated by", "Read by" → Narrator info        │
│      - Appears multiple times in transcript → Duplicate         │
│      - Otherwise → Other extra content                          │
│   4. Match to TranscriptionSegments for timestamps              │
│                                                                 │
│ Output:                                                         │
│   - Missing content: [{text, position_in_pdf, word_count}]    │
│   - Extra content: [{text, type, timestamps, position}]        │
│   - Match statistics: {                                        │
│       total_words: 10000,                                      │
│       matching_words: 9400,                                    │
│       missing_words: 400,                                      │
│       extra_words: 200,                                        │
│       accuracy: 94%                                            │
│     }                                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Detailed Algorithm Specification

### Phase 1: Starting Point Detection

```python
def find_start_position_in_pdf(pdf_text, transcript_text):
    """
    Find where the transcript begins in the PDF.
    
    Returns: (start_index, confidence_score)
    """
    # 1. Normalize and tokenize
    pdf_words = normalize_and_tokenize(pdf_text)
    transcript_words = normalize_and_tokenize(transcript_text)
    
    # 2. Create search window from transcript start
    window_size = 100  # First 100 words
    search_window = transcript_words[:window_size]
    
    # 3. Slide across PDF and find best match
    best_score = 0
    best_position = 0
    
    for i in range(len(pdf_words) - window_size):
        pdf_window = pdf_words[i:i + window_size]
        
        # Count exact matches
        matches = sum(1 for a, b in zip(pdf_window, search_window) if a == b)
        score = matches / window_size
        
        if score > best_score:
            best_score = score
            best_position = i
        
        # Early exit if excellent match
        if score > 0.85:
            break
    
    return best_position, best_score

def normalize_and_tokenize(text):
    """
    Normalize text for comparison.
    - Remove punctuation
    - Lowercase
    - Split into words
    - Filter out very short words (< 3 chars)
    """
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    words = [w for w in text.split() if len(w) >= 3]
    return words
```

### Phase 2: Myers Diff Algorithm (Simplified)

```python
def myers_diff_words(pdf_words, transcript_words):
    """
    Perform word-level diff using Myers algorithm.
    
    Returns: List of operations [(op, word, pdf_idx, transcript_idx)]
    Operations: 'MATCH', 'DELETE' (in PDF not transcript), 'INSERT' (in transcript not PDF)
    """
    n = len(pdf_words)
    m = len(transcript_words)
    
    # Build the edit graph
    # v[k] represents furthest reaching path on diagonal k
    max_d = n + m
    v = {1: 0}
    trace = []
    
    for d in range(max_d + 1):
        trace.append(v.copy())
        
        for k in range(-d, d + 1, 2):
            # Choose path
            if k == -d or (k != d and v[k - 1] < v[k + 1]):
                x = v[k + 1]  # Move down (insert in transcript)
            else:
                x = v[k - 1] + 1  # Move right (delete from PDF)
            
            y = x - k
            
            # Extend diagonal (matches)
            while x < n and y < m and pdf_words[x] == transcript_words[y]:
                x += 1
                y += 1
            
            v[k] = x
            
            # Check if we reached the end
            if x >= n and y >= m:
                return backtrack_diff(trace, pdf_words, transcript_words, d)
    
    return []

def backtrack_diff(trace, pdf_words, transcript_words, d):
    """
    Backtrack through the trace to build the list of operations.
    """
    operations = []
    x = len(pdf_words)
    y = len(transcript_words)
    
    for d in range(len(trace) - 1, -1, -1):
        v = trace[d]
        k = x - y
        
        # Determine previous k
        if k == -d or (k != d and v[k - 1] < v[k + 1]):
            prev_k = k + 1
        else:
            prev_k = k - 1
        
        prev_x = v[prev_k]
        prev_y = prev_x - prev_k
        
        # Add diagonal matches (going backwards)
        while x > prev_x and y > prev_y:
            x -= 1
            y -= 1
            operations.insert(0, ('MATCH', pdf_words[x], x, y))
        
        # Add insert/delete
        if d > 0:
            if x == prev_x:
                # Insert in transcript (not in PDF)
                y -= 1
                operations.insert(0, ('INSERT', transcript_words[y], None, y))
            else:
                # Delete from PDF (not in transcript)
                x -= 1
                operations.insert(0, ('DELETE', pdf_words[x], x, None))
    
    return operations
```

### Phase 3: Group and Classify Differences

```python
def classify_differences(operations, transcript_segments):
    """
    Group consecutive operations into meaningful sections.
    
    Returns: {
        'missing_content': [{text, position, word_count}],
        'extra_content': [{text, type, timestamps, position}],
        'statistics': {...}
    }
    """
    missing_sections = []
    extra_sections = []
    current_missing = []
    current_extra = []
    
    matches = 0
    total_words = 0
    
    for op, word, pdf_idx, trans_idx in operations:
        total_words += 1
        
        if op == 'MATCH':
            # Flush any accumulated differences
            if current_missing:
                missing_sections.append(aggregate_words(current_missing, 'missing'))
                current_missing = []
            if current_extra:
                extra_sections.append(aggregate_words(current_extra, 'extra', transcript_segments))
                current_extra = []
            matches += 1
            
        elif op == 'DELETE':
            # Missing from transcript
            current_missing.append((word, pdf_idx))
            
        elif op == 'INSERT':
            # Extra in transcript
            current_extra.append((word, trans_idx))
    
    # Flush remaining
    if current_missing:
        missing_sections.append(aggregate_words(current_missing, 'missing'))
    if current_extra:
        extra_sections.append(aggregate_words(current_extra, 'extra', transcript_segments))
    
    # Calculate statistics
    accuracy = (matches / total_words * 100) if total_words > 0 else 0
    
    return {
        'missing_content': missing_sections,
        'extra_content': extra_sections,
        'statistics': {
            'total_words': total_words,
            'matching_words': matches,
            'missing_words': sum(s['word_count'] for s in missing_sections),
            'extra_words': sum(s['word_count'] for s in extra_sections),
            'accuracy_percentage': round(accuracy, 2)
        }
    }

def aggregate_words(words_list, content_type, segments=None):
    """
    Combine consecutive words into sentences.
    """
    text = ' '.join(word for word, idx in words_list)
    
    section = {
        'text': text,
        'word_count': len(words_list),
        'position': words_list[0][1]  # First word's index
    }
    
    if content_type == 'extra':
        section['type'] = classify_extra_content(text)
        if segments:
            section['timestamps'] = find_matching_segments(text, segments)
    
    return section

def classify_extra_content(text):
    """
    Determine what type of extra content this is.
    """
    text_lower = text.lower()
    
    if re.search(r'\bchapter\b|\bpart\b|\bsection\b|\bbook\b', text_lower):
        return 'chapter_marker'
    
    if any(phrase in text_lower for phrase in 
           ['narrated by', 'read by', 'performed by', 'audiobook']):
        return 'narrator_info'
    
    # Check for duplicates by searching transcript for multiple occurrences
    # (This would require passing full transcript context)
    
    return 'other'
```

---

## Implementation in Django/Celery

### Updated Task Structure

```python
# backend/audioDiagnostic/tasks/compare_pdf_task.py

@shared_task(bind=True)
def compare_transcription_to_pdf_task(self, audio_file_id):
    """
    Three-phase comparison with proper sequence alignment.
    """
    # Load data
    audio_file = AudioFile.objects.get(id=audio_file_id)
    pdf_text = audio_file.project.pdf_text
    transcript = audio_file.transcript_text
    
    # PHASE 1: Find starting point
    start_pos, confidence = find_start_position_in_pdf(pdf_text, transcript)
    
    # PHASE 2: Extract section and perform alignment
    pdf_section = extract_pdf_section(pdf_text, start_pos, len(transcript))
    operations = myers_diff_words(
        normalize_and_tokenize(pdf_section),
        normalize_and_tokenize(transcript)
    )
    
    # PHASE 3: Classify differences
    segments = TranscriptionSegment.objects.filter(audio_file=audio_file)
    results = classify_differences(operations, segments)
    
    # Add metadata
    results['match_result'] = {
        'start_position': start_pos,
        'confidence': confidence,
        'matched_section': pdf_section[:1000]  # Preview
    }
    
    # Save results
    audio_file.pdf_comparison_results = results
    audio_file.pdf_comparison_completed = True
    audio_file.save()
    
    return results
```

---

## Performance Characteristics

### Time Complexity

| Phase | Complexity | Example (100K PDF, 10K transcript) |
|-------|------------|-------------------------------------|
| Phase 1: Find start | O(n*m) but exits early | ~1-2 seconds |
| Phase 2: Myers diff | O((N+M)*D) where D=differences | ~2-3 seconds (if 90% match) |
| Phase 3: Classify | O(num_operations) | < 1 second |
| **Total** | **~5 seconds** | **Fast enough for real-time** |

### Space Complexity

| Component | Space | Notes |
|-----------|-------|-------|
| Word arrays | O(N+M) | ~50KB for 10K words |
| Edit graph | O(D²) | Small if high similarity |
| Operations list | O(N+M) | ~100KB for 10K operations |
| **Total** | **< 1MB** | **Memory efficient** |

---

## Expected Results

### Accuracy Metrics

Based on this approach, we expect:

| Scenario | Starting Point Accuracy | Alignment Accuracy | Overall Quality |
|----------|-------------------------|-------------------|-----------------|
| **Perfect match** (99%+ similar) | 99% | 99% | Excellent |
| **Good match** (90-98% similar) | 95% | 95% | Very Good |
| **Fair match** (80-90% similar) | 85% | 85% | Good |
| **Poor match** (< 80% similar) | 70% | 70% | Needs improvement |

### Example Output

```json
{
  "match_result": {
    "start_position": 5234,
    "confidence": 0.92,
    "matched_section": "Elizabeth Caldwell tightened her grip..."
  },
  "missing_content": [
    {
      "text": "slowly down the dark winding street on that cold November evening",
      "word_count": 11,
      "position": 1523
    }
  ],
  "extra_content": [
    {
      "text": "Chapter One The Beginning",
      "word_count": 4,
      "type": "chapter_marker",
      "timestamps": [
        {"start_time": 0.0, "end_time": 2.5, "segment_id": 1}
      ]
    },
    {
      "text": "The man walked The man walked",
      "word_count": 6,
      "type": "duplicate",
      "timestamps": [
        {"start_time": 45.2, "end_time": 47.8, "segment_id": 15},
        {"start_time": 47.8, "end_time": 50.4, "segment_id": 16}
      ]
    }
  ],
  "statistics": {
    "total_words": 10000,
    "matching_words": 9200,
    "missing_words": 600,
    "extra_words": 200,
    "accuracy_percentage": 92.0
  }
}
```

---

## Next Steps

1. **Implement Myers Diff**: Replace current word-overlap algorithm with Myers diff
2. **Add Duplicate Detection**: Enhance to identify repeated sections within transcript
3. **Visual Diff View**: Update frontend to show aligned comparison (like Git diff)
4. **Performance Testing**: Benchmark on various book sizes and accuracy levels
5. **User Feedback Loop**: Allow users to mark incorrect matches, improve algorithm

---

## References

- Myers, E. W. (1986). "An O(ND) Difference Algorithm and Its Variations"
- Git Diff Algorithm: https://git-scm.com/docs/git-diff
- Python difflib module (uses Ratcliff/Obershelp algorithm, similar concept)
