# Audiobook Production Quality Algorithm

## Problem Statement

Compare a PDF book against an audio transcription where:
- **PDF**: Book text with headers, footers, page numbers (not read aloud)
- **Transcription**: Audio transcript with timestamped words, containing:
  - Repeated sections (reader re-reads lines 2-3 times)
  - Potential mistakes or mispronunciations
  - Possible missing sections
  - Each word has a timestamp

**Goal**: Determine if audiobook is production-ready OR identify what needs editing/re-recording with precise timestamps.

## Key Principles

1. **Last Read Wins**: When a section is read multiple times, the LAST occurrence is the keeper
2. **Word-Level Precision**: Every comparison uses timestamped word boundaries
3. **Flexible Matching**: Account for minor variations (contractions, punctuation)
4. **Actionable Output**: Provide exact timestamps for required edits

## Algorithm Design

### Phase 1: Text Preparation

#### 1.1 PDF Preprocessing
```python
def prepare_pdf_text(pdf_text):
    """
    Clean PDF to match what would be read aloud.
    
    Remove:
    - Headers and footers (page numbers, book title, chapter)
    - Page numbers in text
    - Table of contents page numbers
    - Footnote markers
    - Section numbers (unless they're read in audio)
    
    Keep:
    - Chapter titles (if read aloud)
    - All narrative text
    - Dialogue
    """
    # Use existing clean_pdf_text utility
    cleaned = clean_pdf_text(pdf_text, remove_headers=True)
    
    # Additional audiobook-specific cleaning
    cleaned = remove_page_numbers(cleaned)
    cleaned = remove_footnote_markers(cleaned)
    
    return cleaned
```

#### 1.2 Text Normalization
```python
def normalize_for_comparison(text):
    """
    Normalize text for flexible matching.
    
    Normalizations:
    - Lowercase
    - Expand contractions (can't → cannot, she'd → she would/had)
    - Remove punctuation (but track for context)
    - Handle variant spellings (acknowledge both)
    """
    # Create two versions:
    # 1. Strict: exact word matching
    # 2. Loose: normalized for fuzzy matching
    
    return {
        'strict': text,
        'normalized': normalize_text(text),
        'words': tokenize_words(text)
    }
```

### Phase 2: Transcript Analysis

#### 2.1 Build Word-Timestamp Map
```python
def build_word_map(transcription_segments):
    """
    Create comprehensive word-level map with timestamps.
    
    Output:
    [
        {
            'word': 'hello',
            'start_time': 1.23,
            'end_time': 1.45,
            'segment_id': 123,
            'index': 0  # position in full transcript
        },
        ...
    ]
    """
    word_map = []
    global_index = 0
    
    for segment in transcription_segments:
        words = segment.text.split()
        duration = segment.end_time - segment.start_time
        time_per_word = duration / len(words)
        
        for i, word in enumerate(words):
            word_map.append({
                'word': normalize_word(word),
                'original': word,
                'start_time': segment.start_time + (i * time_per_word),
                'end_time': segment.start_time + ((i + 1) * time_per_word),
                'segment_id': segment.id,
                'index': global_index
            })
            global_index += 1
    
    return word_map
```

#### 2.2 Detect Repeated Sections
```python
def detect_repetitions(word_map, min_repeat_length=5):
    """
    Find sections that are read multiple times.
    
    Algorithm:
    1. Use sliding window to find repeated sequences
    2. Group by semantic similarity (not just exact match)
    3. Track ALL occurrences of each repeated section
    4. Mark the LAST occurrence as the "keeper"
    
    Output:
    {
        'repetitions': [
            {
                'text': 'the quick brown fox',
                'occurrences': [
                    {'start_idx': 0, 'end_idx': 3, 'start_time': 1.0, 'end_time': 2.5, 'keep': False},
                    {'start_idx': 45, 'end_idx': 48, 'start_time': 15.2, 'end_time': 16.8, 'keep': False},
                    {'start_idx': 92, 'end_idx': 95, 'start_time': 30.1, 'end_time': 31.7, 'keep': True}
                ]
            }
        ]
    }
    """
    # Use sequence matching algorithm (e.g., Smith-Waterman)
    # to find repeated subsequences
    
    repetitions = []
    
    # Create n-grams of varying lengths (5-50 words)
    for n in range(min_repeat_length, 51):
        ngram_positions = find_repeated_ngrams(word_map, n)
        
        for ngram, positions in ngram_positions.items():
            if len(positions) > 1:
                # Multiple occurrences found
                repetitions.append({
                    'text': ngram,
                    'length': n,
                    'occurrences': positions,
                    'keeper_index': len(positions) - 1  # Last one
                })
    
    # Merge overlapping repetitions
    repetitions = merge_overlapping_reps(repetitions)
    
    return repetitions
```

### Phase 3: Alignment & Matching

#### 3.1 Build Clean Transcript
```python
def build_final_transcript(word_map, repetitions):
    """
    Create the "final" transcript using only keeper sections.
    
    Algorithm:
    1. Start with full word_map
    2. Remove all non-keeper repetitions
    3. Keep only the last read of each repeated section
    4. Maintain timestamp continuity
    """
    # Mark words to exclude
    exclude_indices = set()
    
    for rep in repetitions:
        for i, occurrence in enumerate(rep['occurrences']):
            if i != rep['keeper_index']:  # Not the keeper
                # Mark these word indices for exclusion
                exclude_indices.update(
                    range(occurrence['start_idx'], occurrence['end_idx'] + 1)
                )
    
    # Build final transcript
    final_words = [
        word for word in word_map 
        if word['index'] not in exclude_indices
    ]
    
    return final_words
```

#### 3.2 Align with PDF
```python
def align_transcript_to_pdf(pdf_words, transcript_words):
    """
    Create word-by-word alignment between PDF and final transcript.
    
    Use dynamic programming (Needleman-Wunsch) for global alignment:
    - Match: +2 points
    - Mismatch: -1 point
    - Gap: -2 points
    
    Consider:
    - Exact word match
    - Normalized match (can't vs cannot)
    - Phonetic similarity (for mispronunciations)
    
    Output:
    [
        {
            'pdf_word': 'cannot',
            'pdf_index': 45,
            'transcript_word': "can't",
            'transcript_index': 42,
            'match_type': 'normalized',  # exact, normalized, phonetic, mismatch
            'match_score': 0.95,
            'timestamp': {'start': 15.2, 'end': 15.6}
        },
        ...
    ]
    """
    alignment = []
    
    # Dynamic programming alignment
    dp_matrix = create_alignment_matrix(pdf_words, transcript_words)
    
    # Backtrack to get alignment
    i, j = len(pdf_words), len(transcript_words)
    
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            match_score = calculate_match_score(
                pdf_words[i-1], 
                transcript_words[j-1]
            )
            
            if dp_matrix[i][j] == dp_matrix[i-1][j-1] + match_score:
                # Match or mismatch
                alignment.append({
                    'pdf_word': pdf_words[i-1],
                    'pdf_index': i-1,
                    'transcript_word': transcript_words[j-1]['word'],
                    'transcript_index': j-1,
                    'match_type': determine_match_type(
                        pdf_words[i-1], 
                        transcript_words[j-1]['word']
                    ),
                    'match_score': match_score,
                    'timestamp': {
                        'start': transcript_words[j-1]['start_time'],
                        'end': transcript_words[j-1]['end_time']
                    }
                })
                i -= 1
                j -= 1
            elif dp_matrix[i][j] == dp_matrix[i-1][j] - 2:
                # Gap in transcript (missing word)
                alignment.append({
                    'pdf_word': pdf_words[i-1],
                    'pdf_index': i-1,
                    'transcript_word': None,
                    'match_type': 'missing',
                    'match_score': 0
                })
                i -= 1
            else:
                # Gap in PDF (extra word in transcript)
                alignment.append({
                    'pdf_word': None,
                    'transcript_word': transcript_words[j-1]['word'],
                    'transcript_index': j-1,
                    'match_type': 'extra',
                    'match_score': 0,
                    'timestamp': {
                        'start': transcript_words[j-1]['start_time'],
                        'end': transcript_words[j-1]['end_time']
                    }
                })
                j -= 1
        elif i > 0:
            # Remaining PDF words (missing from transcript)
            alignment.append({
                'pdf_word': pdf_words[i-1],
                'pdf_index': i-1,
                'transcript_word': None,
                'match_type': 'missing',
                'match_score': 0
            })
            i -= 1
        else:
            # Remaining transcript words (extra)
            alignment.append({
                'pdf_word': None,
                'transcript_word': transcript_words[j-1]['word'],
                'transcript_index': j-1,
                'match_type': 'extra',
                'match_score': 0,
                'timestamp': {
                    'start': transcript_words[j-1]['start_time'],
                    'end': transcript_words[j-1]['end_time']
                }
            })
            j -= 1
    
    return list(reversed(alignment))
```

### Phase 4: Quality Analysis

#### 4.1 Segment Quality Scoring
```python
def analyze_segments(alignment, segment_size=50):
    """
    Break alignment into logical segments and score quality.
    
    Segment types:
    - Perfect: 95-100% match
    - Good: 85-95% match (minor mistakes, acceptable)
    - Fair: 70-85% match (noticeable issues, may need review)
    - Poor: <70% match (needs re-recording)
    
    Output segments with:
    - Start/end timestamps
    - Quality score
    - List of specific errors
    - Production readiness status
    """
    segments = []
    
    for i in range(0, len(alignment), segment_size):
        segment_alignment = alignment[i:i+segment_size]
        
        # Calculate metrics
        total_words = len(segment_alignment)
        exact_matches = sum(1 for a in segment_alignment if a['match_type'] == 'exact')
        normalized_matches = sum(1 for a in segment_alignment if a['match_type'] == 'normalized')
        mismatches = sum(1 for a in segment_alignment if a['match_type'] == 'mismatch')
        missing = sum(1 for a in segment_alignment if a['match_type'] == 'missing')
        extra = sum(1 for a in segment_alignment if a['match_type'] == 'extra')
        
        # Calculate score
        score = (exact_matches * 1.0 + normalized_matches * 0.95) / total_words
        
        # Determine status
        if score >= 0.95 and missing == 0:
            status = 'production_ready'
        elif score >= 0.85:
            status = 'needs_minor_edits'
        elif score >= 0.70:
            status = 'needs_review'
        else:
            status = 'needs_rerecording'
        
        # Get timestamp range
        timestamps = [a['timestamp'] for a in segment_alignment if a.get('timestamp')]
        start_time = min(t['start'] for t in timestamps) if timestamps else None
        end_time = max(t['end'] for t in timestamps) if timestamps else None
        
        segments.append({
            'segment_id': i // segment_size,
            'start_time': start_time,
            'end_time': end_time,
            'quality_score': score,
            'status': status,
            'metrics': {
                'total_words': total_words,
                'exact_matches': exact_matches,
                'normalized_matches': normalized_matches,
                'mismatches': mismatches,
                'missing_words': missing,
                'extra_words': extra
            },
            'errors': extract_errors(segment_alignment)
        })
    
    return segments
```

#### 4.2 Identify Missing Sections
```python
def find_missing_sections(alignment, min_gap_words=10):
    """
    Find contiguous sections of PDF not found in transcript.
    
    These are sections that need to be recorded.
    
    Output:
    [
        {
            'pdf_start_index': 450,
            'pdf_end_index': 475,
            'missing_text': 'The entire paragraph that was skipped...',
            'word_count': 25,
            'context_before': 'last 10 words before gap',
            'context_after': 'first 10 words after gap',
            'suggested_recording_time': '0:45-1:30'  # estimate based on word count
        }
    ]
    """
    missing_sections = []
    current_gap = []
    
    for item in alignment:
        if item['match_type'] == 'missing':
            current_gap.append(item)
        else:
            if len(current_gap) >= min_gap_words:
                # Found a significant gap
                missing_sections.append({
                    'pdf_start_index': current_gap[0]['pdf_index'],
                    'pdf_end_index': current_gap[-1]['pdf_index'],
                    'missing_text': ' '.join(g['pdf_word'] for g in current_gap),
                    'word_count': len(current_gap),
                    'context_before': get_context_before(alignment, current_gap[0]['pdf_index']),
                    'context_after': get_context_after(alignment, current_gap[-1]['pdf_index']),
                    'estimated_duration': estimate_reading_time(len(current_gap))
                })
            current_gap = []
    
    return missing_sections
```

### Phase 5: Production Report

#### 5.1 Generate Comprehensive Report
```python
def generate_production_report(pdf_text, word_map, repetitions, alignment, segments, missing_sections):
    """
    Create actionable production report.
    
    Report includes:
    1. Overall Status: Production Ready / Needs Editing / Needs Re-recording
    2. Summary Statistics
    3. Repetition Analysis (what was re-read)
    4. Segment-by-Segment Quality
    5. Missing Sections (with timestamps for context)
    6. Error Details (mispronunciations, mistakes)
    7. Editing Checklist
    """
    
    # Calculate overall score
    overall_score = sum(s['quality_score'] for s in segments) / len(segments)
    
    # Determine overall status
    if overall_score >= 0.95 and len(missing_sections) == 0:
        overall_status = 'PRODUCTION READY ✓'
    elif overall_score >= 0.85 and len(missing_sections) == 0:
        overall_status = 'NEEDS MINOR EDITING'
    else:
        overall_status = 'NEEDS SIGNIFICANT WORK'
    
    report = {
        'overall_status': overall_status,
        'overall_score': overall_score,
        
        'summary': {
            'total_pdf_words': len(pdf_text.split()),
            'total_transcript_words': len(word_map),
            'total_final_words': len([w for w in word_map if not is_excluded(w, repetitions)]),
            'repetitions_found': len(repetitions),
            'total_repeated_words': count_repeated_words(repetitions),
            'missing_sections': len(missing_sections),
            'total_missing_words': sum(m['word_count'] for m in missing_sections)
        },
        
        'repetition_analysis': [
            {
                'text_preview': rep['text'][:100] + '...',
                'times_read': len(rep['occurrences']),
                'timestamps': [
                    {
                        'attempt': i + 1,
                        'start': occ['start_time'],
                        'end': occ['end_time'],
                        'kept': i == rep['keeper_index']
                    }
                    for i, occ in enumerate(rep['occurrences'])
                ]
            }
            for rep in repetitions
        ],
        
        'segment_quality': segments,
        
        'missing_sections': missing_sections,
        
        'errors': compile_all_errors(alignment),
        
        'editing_checklist': generate_checklist(segments, missing_sections, repetitions)
    }
    
    return report
```

#### 5.2 Editing Checklist
```python
def generate_checklist(segments, missing_sections, repetitions):
    """
    Create step-by-step checklist for editor/narrator.
    
    Prioritized by:
    1. Missing sections (must record)
    2. Poor quality segments (should re-record)
    3. Fair quality segments (review and decide)
    4. Repeated sections to delete
    """
    checklist = []
    
    # Missing sections first
    for ms in missing_sections:
        checklist.append({
            'priority': 'CRITICAL',
            'action': 'RECORD',
            'description': f'Record missing section ({ms["word_count"]} words)',
            'text': ms['missing_text'],
            'context': {
                'before': ms['context_before'],
                'after': ms['context_after']
            },
            'estimated_time': ms['estimated_duration']
        })
    
    # Poor quality segments
    for seg in segments:
        if seg['status'] == 'needs_rerecording':
            checklist.append({
                'priority': 'HIGH',
                'action': 'RE-RECORD',
                'description': f'Segment #{seg["segment_id"]} quality too low ({seg["quality_score"]:.1%})',
                'timestamp': f'{seg["start_time"]:.2f} - {seg["end_time"]:.2f}',
                'errors': seg['errors']
            })
    
    # Repetitions to remove (non-keeper takes)
    for rep in repetitions:
        for i, occ in enumerate(rep['occurrences']):
            if i != rep['keeper_index']:
                checklist.append({
                    'priority': 'MEDIUM',
                    'action': 'DELETE',
                    'description': f'Remove failed take #{i+1} of {len(rep["occurrences"])}',
                    'timestamp': f'{occ["start_time"]:.2f} - {occ["end_time"]:.2f}',
                    'text_preview': rep['text'][:100]
                })
    
    # Review segments
    for seg in segments:
        if seg['status'] == 'needs_review':
            checklist.append({
                'priority': 'LOW',
                'action': 'REVIEW',
                'description': f'Segment #{seg["segment_id"]} may need touch-ups',
                'timestamp': f'{seg["start_time"]:.2f} - {seg["end_time"]:.2f}',
                'errors': seg['errors']
            })
    
    return sorted(checklist, key=lambda x: {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}[x['priority']])
```

## Implementation Strategy

### Data Structures

```python
# Core data models
AudiobookComparison = {
    'project_id': int,
    'audio_file_id': int,
    'pdf_text': str,
    'word_map': List[WordTimestamp],
    'repetitions': List[Repetition],
    'final_transcript': List[WordTimestamp],
    'alignment': List[AlignmentPoint],
    'segments': List[QualitySegment],
    'missing_sections': List[MissingSection],
    'report': ProductionReport,
    'created_at': datetime,
    'overall_status': str,
    'overall_score': float
}

WordTimestamp = {
    'word': str,
    'original': str,
    'start_time': float,
    'end_time': float,
    'segment_id': int,
    'index': int,
    'excluded': bool  # If part of non-keeper repetition
}

Repetition = {
    'text': str,
    'length': int,  # word count
    'occurrences': List[Occurrence],
    'keeper_index': int
}

Occurrence = {
    'start_idx': int,
    'end_idx': int,
    'start_time': float,
    'end_time': float,
    'keep': bool
}
```

### Performance Considerations

1. **Caching**: Cache PDF cleaning results
2. **Chunking**: Process large books in chapters
3. **Parallel Processing**: Run repetition detection and alignment in parallel where possible
4. **Progress Tracking**: Update progress for long-running comparisons

### Testing Strategy

1. **Unit Tests**: Test each phase independently
2. **Integration Tests**: Full pipeline with sample audiobook
3. **Edge Cases**:
   - Very short books
   - Books with unusual formatting
   - Heavy repetition (nervous reader)
   - Multiple missing chapters

## Expected Output Format

```json
{
  "overall_status": "NEEDS MINOR EDITING",
  "overall_score": 0.92,
  "summary": {
    "total_pdf_words": 50000,
    "total_transcript_words": 52000,
    "total_final_words": 50100,
    "repetitions_found": 45,
    "total_repeated_words": 1900,
    "missing_sections": 2,
    "total_missing_words": 150
  },
  "editing_checklist": [
    {
      "priority": "CRITICAL",
      "action": "RECORD",
      "description": "Record missing section (75 words)",
      "text": "The entire paragraph about...",
      "timestamp_context": "After 15:32, before 16:45"
    },
    {
      "priority": "HIGH",
      "action": "RE-RECORD",
      "description": "Segment #23 quality too low (65%)",
      "timestamp": "45:12 - 47:30"
    }
  ]
}
```

## Next Steps

1. Implement core utilities (normalization, tokenization)
2. Build repetition detection algorithm
3. Implement alignment engine
4. Create quality scoring system
5. Build report generator
6. Integrate with existing Celery task infrastructure
7. Create UI for visualizing results
