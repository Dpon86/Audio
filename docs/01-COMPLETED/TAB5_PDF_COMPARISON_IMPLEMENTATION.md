# Tab 5: PDF Comparison Implementation

## Overview
Implemented complete PDF comparison functionality for Tab 5 (Compare PDF) that allows users to:
- Compare audio transcription against the source PDF document
- Find where the audio starts in the PDF
- Identify missing content (in PDF but not in audio)
- Identify extra content (in audio but not in PDF, like narrator info)
- Mark sections to ignore (e.g., "Narrated by Jane Doe", chapter titles)
- View side-by-side comparison of transcription vs PDF

## Implementation Components

### 1. Backend - Celery Task
**File**: `backend/audioDiagnostic/tasks/compare_pdf_task.py`

**Main Task**: `compare_transcription_to_pdf_task(audio_file_id)`

#### Features:
- Extracts PDF text (cached in project)
- Finds matching section in PDF using sequence matching (difflib)
- Filters out user-marked ignored sections
- Identifies missing content (in PDF but not in transcript)
- Identifies extra content (in transcript but not in PDF)
- Classifies extra content (chapter markers, narrator info, other)
- Calculates comprehensive statistics (coverage, accuracy, match confidence)
- Supports progress tracking via Redis

#### Key Functions:
1. **`find_pdf_section_match(pdf_text, transcript)`**
   - Uses exact matching first, falls back to fuzzy matching
   - Returns matched section with confidence score, start/end positions
   - High accuracy for exact matches (95%), reasonable for fuzzy (ratio-based)

2. **`find_missing_content(transcript, pdf_section)`**
   - Splits PDF into sentences
   - Checks each sentence against transcript
   - Uses 70% word match threshold
   - Returns list with text, length, word count

3. **`find_extra_content(transcript, pdf_section)`**
   - Splits transcript into sentences
   - Checks each against PDF
   - Classifies type (chapter, narrator, other)
   - Helps identify sections to ignore

4. **`calculate_comparison_stats(transcript, pdf_section, missing_content, extra_content)`**
   - Word counts for transcript and PDF
   - Coverage percentage (words in both / PDF words)
   - Accuracy percentage (matching words / transcript words)
   - Match quality rating (excellent/good/fair/poor)

### 2. Backend - API Endpoints
**File**: `backend/audioDiagnostic/views/tab5_pdf_comparison.py`

#### Endpoints:

1. **POST** `/api/projects/{project_id}/files/{audio_file_id}/compare-pdf/`
   - Starts PDF comparison task
   - Returns task_id for progress tracking
   - Validates PDF and transcription exist

2. **GET** `/api/projects/{project_id}/files/{audio_file_id}/pdf-result/`
   - Returns comparison results
   - Includes match result, missing content, extra content, statistics
   - Also returns ignored sections list

3. **GET** `/api/projects/{project_id}/files/{audio_file_id}/pdf-status/`
   - Polls comparison task progress
   - Checks Redis for progress percentage
   - Falls back to Celery task state
   - Returns completed/progress/error status

4. **GET** `/api/projects/{project_id}/files/{audio_file_id}/side-by-side/`
   - Generates side-by-side comparison view
   - Uses difflib.SequenceMatcher to align text
   - Returns segments marked as: match, extra (transcription only), missing (PDF only)
   - Includes statistics about segment counts

5. **POST/GET** `/api/projects/{project_id}/files/{audio_file_id}/ignored-sections/`
   - POST: Add/update ignored sections
   - Automatically re-runs comparison after update
   - GET: Retrieve current ignored sections

6. **POST** `/api/projects/{project_id}/files/{audio_file_id}/reset-comparison/`
   - Clears all comparison results and ignored sections
   - Allows fresh start

### 3. Database Model Updates
**File**: `backend/audioDiagnostic/models.py`

#### New AudioFile Fields:
```python
# Tab 5 PDF Comparison fields
pdf_comparison_results = JSONField()  # Full comparison results
pdf_comparison_completed = BooleanField(default=False)
pdf_ignored_sections = JSONField()  # List of text sections to ignore
```

#### Data Structure for `pdf_comparison_results`:
```python
{
    'match_result': {
        'matched_section': str,  # The PDF section that matches
        'confidence': float,  # 0-1 confidence score
        'start_char': int,  # Start position in PDF
        'end_char': int,  # End position in PDF
        'start_preview': str,  # First 100 chars
        'end_preview': str,  # Last 100 chars
        'pdf_length': int,
        'transcript_length': int
    },
    'missing_content': [
        {
            'text': str,  # Missing sentence/phrase
            'length': int,
            'word_count': int
        },
        ...
    ],
    'extra_content': [
        {
            'text': str,  # Extra sentence/phrase
            'length': int,
            'word_count': int,
            'possible_type': str  # 'chapter', 'narrator', 'other'
        },
        ...
    ],
    'statistics': {
        'transcript_word_count': int,
        'pdf_word_count': int,
        'missing_word_count': int,
        'extra_word_count': int,
        'missing_sections': int,
        'extra_sections': int,
        'coverage_percentage': float,  # 0-100
        'accuracy_percentage': float,  # 0-100
        'match_quality': str  # 'excellent', 'good', 'fair', 'poor'
    },
    'ignored_sections_count': int
}
```

#### Data Structure for `pdf_ignored_sections`:
```python
[
    {
        'text': str,  # Text to ignore
        'reason': str,  # 'user_marked', etc.
        'timestamp': str  # ISO format
    },
    ...
]
```

### 4. Frontend - React Component
**File**: `frontend/audio-waveform-visualizer/src/components/ProjectTabs/Tab5ComparePDF.js`

#### Features:
1. **File Selection**
   - Dropdown to select from transcribed audio files
   - Auto-loads previous comparison results

2. **Comparison Controls**
   - Start Comparison button
   - Progress bar with percentage
   - Error display
   - Reset button to clear results

3. **Statistics Display**
   - Match quality badge (color-coded)
   - Coverage percentage
   - Accuracy percentage
   - Match confidence
   - Word counts (transcript, PDF, missing, extra)

4. **Content Lists**
   - Missing Content section (yellow background)
     - Shows text, word count for each missing piece
   - Extra Content section (blue background)
     - Shows text, word count, type classification
     - "Ignore This" button for narrator/chapter content

5. **Ignored Sections Management**
   - Dialog to add/remove ignored sections
   - Text area for manual entry
   - List of current ignored sections with remove buttons
   - Auto-recompares after changes

6. **Side-by-Side View**
   - Two-column layout (Transcription | PDF)
   - Color-coded segments:
     - Green: Matching content
     - Orange: Extra in transcription
     - Red: Missing from transcription
   - Legend at bottom
   - Scrollable view for long documents

#### State Management:
- Uses `useProjectTab` context for file selection
- Polls status every 2 seconds during comparison
- Loads results on mount if available
- Real-time progress updates

### 5. URL Routing Updates
**File**: `backend/audioDiagnostic/urls.py`

Updated imports to use new `tab5_pdf_comparison` views:
```python
from .views.tab5_pdf_comparison import (
    StartPDFComparisonView,
    PDFComparisonResultView,
    PDFComparisonStatusView,
    SideBySideComparisonView,
    MarkIgnoredSectionsView,
    ResetPDFComparisonView,
)
```

Routes:
- `compare-pdf/` → StartPDFComparisonView
- `pdf-result/` → PDFComparisonResultView
- `pdf-status/` → PDFComparisonStatusView
- `side-by-side/` → SideBySideComparisonView
- `ignored-sections/` → MarkIgnoredSectionsView (GET/POST)
- `reset-comparison/` → ResetPDFComparisonView

## User Workflow

1. **Select Audio File**
   - User navigates to Tab 5 (Compare PDF)
   - Selects a transcribed audio file from dropdown

2. **Start Comparison**
   - Clicks "Start Comparison" button
   - Backend extracts PDF text (cached)
   - Finds matching section using sequence matching
   - Identifies missing and extra content
   - Calculates statistics

3. **Review Results**
   - Statistics dashboard shows match quality, coverage, accuracy
   - Missing content list shows what's in PDF but not in audio
   - Extra content list shows what's in audio but not in PDF

4. **Mark Ignored Sections** (Optional)
   - User identifies narrator info, chapter titles, etc. in Extra Content
   - Clicks "Ignore This" button or manually enters text
   - System automatically re-runs comparison without ignored sections
   - Statistics update to reflect filtered comparison

5. **View Side-by-Side** (Optional)
   - Clicks "View Side-by-Side" button
   - See aligned transcription and PDF text
   - Color-coded segments show matches and differences
   - Helps understand where content differs

6. **Assessment**
   - Match quality indicator guides user:
     - **Excellent** (≥95%): Audio matches PDF very well
     - **Good** (≥85%): Minor differences
     - **Fair** (≥70%): Some missing content
     - **Poor** (<70%): Significant differences
   - Missing content count helps identify gaps
   - Extra content with classification helps find non-book material

## Algorithm Details

### PDF Section Matching Algorithm
1. **Exact Match (Preferred)**:
   - Take first 300 chars of transcript
   - Search for exact match in PDF
   - If found, estimate end position based on transcript length
   - Confidence: 95%

2. **Fuzzy Match (Fallback)**:
   - Use `difflib.SequenceMatcher` to find longest common subsequence
   - Minimum match length: 200 characters
   - Confidence: Based on sequence ratio (0-1)

3. **Last Resort**:
   - Return first 2000 chars of PDF
   - Confidence: 30%

### Content Comparison Algorithm
1. **Split into Sentences**:
   - Use regex: `r'[.!?]+'`
   - Filter out short segments (<10 chars)

2. **Normalize Text**:
   - Lowercase
   - Remove extra whitespace
   - Preserve word order

3. **Match Detection**:
   - Exact substring match first
   - If >5 words: Calculate word overlap ratio
   - Threshold: 70% word match required
   - Below threshold = missing/extra content

4. **Extra Content Classification**:
   - Check for keywords: "chapter", "narrated by", "read by"
   - Classify as: 'chapter', 'narrator', 'other'

## Statistics Calculation

### Coverage Percentage
```
(PDF words - Missing words) / PDF words * 100
```
Represents: How much of the PDF is covered by the transcription

### Accuracy Percentage
```
(Common words) / Transcript words * 100
```
Represents: How much of the transcription matches the PDF

### Match Quality Rating
- **Excellent**: Coverage ≥ 95%
- **Good**: Coverage ≥ 85%
- **Fair**: Coverage ≥ 70%
- **Poor**: Coverage < 70%

## Error Handling

### Backend:
- Validates PDF file exists
- Validates transcription exists
- Catches PDF extraction errors
- Handles sequence matching failures
- Sets task progress to -1 on error
- Returns detailed error messages

### Frontend:
- Displays error messages in red alert box
- Handles network errors gracefully
- Falls back to empty states when no data
- Shows appropriate messages for each state:
  - No file selected
  - No results yet
  - Comparison in progress
  - Comparison failed
  - Results available

## Performance Considerations

1. **PDF Text Caching**:
   - PDF text extracted once and cached in `project.pdf_text`
   - Subsequent comparisons reuse cached text
   - Saves processing time

2. **Progress Tracking**:
   - Uses Redis for fine-grained progress (5%, 10%, 30%, etc.)
   - Falls back to Celery task state if Redis unavailable
   - 2-second polling interval (balance between responsiveness and load)

3. **Ignored Sections**:
   - Stored as JSON field
   - Applied during comparison, not after
   - Re-comparison is automatic but user-initiated

4. **Side-by-Side Generation**:
   - Generated on-demand (not stored)
   - Uses efficient sequence matching
   - Limited to segments displayed in UI

## Testing Checklist

- [x] Backend task imports correctly
- [x] Views have no syntax errors
- [x] URLs route to correct views
- [x] Model fields added
- [x] React component created and integrated
- [ ] End-to-end test: Upload PDF → Transcribe → Compare
- [ ] Test ignored sections workflow
- [ ] Test side-by-side view
- [ ] Test with various PDF formats
- [ ] Test with very long documents
- [ ] Test error handling (no PDF, no transcript)
- [ ] Test progress polling
- [ ] Test reset functionality

## Future Enhancements

1. **Page-Level Matching**:
   - Track which PDF pages correspond to audio
   - Enable page-range comparisons

2. **Confidence Scoring Improvements**:
   - Use more sophisticated NLP algorithms
   - Consider word order and semantic similarity

3. **Auto-Detection of Ignored Sections**:
   - Machine learning to identify narrator phrases
   - Pattern recognition for chapter titles

4. **Export Functionality**:
   - Export comparison results to PDF
   - Generate reports with highlighted differences

5. **Batch Processing**:
   - Compare all audio files to PDF at once
   - Project-level comparison summary

6. **Visual Highlighting**:
   - Highlight text in PDF viewer
   - Sync audio playback with PDF position

## Deployment Notes

1. **Database Migration**:
   - Fields added to existing AudioFile model
   - No migration needed if using existing migration 0015

2. **Celery Worker**:
   - Task registered automatically
   - No additional configuration needed
   - Uses existing Celery infrastructure

3. **Dependencies**:
   - Existing: difflib (Python stdlib)
   - Existing: PyPDF2 (already installed)
   - No new dependencies required

4. **Redis**:
   - Uses existing Redis connection from utils
   - Progress keys: `progress:{task_id}`
   - No additional setup needed

## Troubleshooting

### "No PDF file found"
- Ensure PDF uploaded in Tab 1 (Files)
- Check `project.pdf_file` is not null

### "Audio file has not been transcribed yet"
- Run transcription in Tab 1 first
- Check audio file status is 'transcribed' or 'processed'

### "Comparison stuck at 0%"
- Check Celery worker is running
- Check Redis is accessible
- Look for task errors in Celery logs

### "Poor match quality"
- PDF might not match audio content
- Audio might be reading different chapter
- Try adjusting PDF boundaries (future feature)

### "Side-by-side not loading"
- Ensure comparison completed successfully
- Check browser console for errors
- Verify API endpoint is accessible

## Files Modified/Created

### Created:
1. `backend/audioDiagnostic/tasks/compare_pdf_task.py` - Celery task
2. `backend/audioDiagnostic/views/tab5_pdf_comparison.py` - API views
3. `frontend/audio-waveform-visualizer/src/components/ProjectTabs/Tab5ComparePDF.js` - React component

### Modified:
1. `backend/audioDiagnostic/models.py` - Added PDF comparison fields
2. `backend/audioDiagnostic/urls.py` - Updated imports and routes
3. `frontend/audio-waveform-visualizer/src/screens/ProjectDetailPageNew.js` - Updated Tab5 import

## Summary

The PDF Comparison feature (Tab 5) provides a comprehensive solution for comparing audio transcriptions against source PDF documents. It uses intelligent matching algorithms, detailed content analysis, and user-friendly UI to help identify where audio matches PDF, what content is missing, and what extra content should be ignored. The implementation follows the established patterns in the codebase, uses existing infrastructure (Celery, Redis, Django REST Framework), and provides a solid foundation for future enhancements.
