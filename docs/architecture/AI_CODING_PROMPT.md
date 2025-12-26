# AI Coding Prompt: Audio Repetition Detection Software

## ✅ IMPLEMENTATION STATUS: PHASE 1 COMPLETE (December 2025)

**Backend APIs:** 100% Complete - All 4 tabs fully implemented with 18 API endpoints
**Frontend Components:** 100% Complete - Tab navigation, state management, and Tab 1-2 fully functional
**Database Models:** 100% Complete - All models migrated and tested
**Next Steps:** Full UI implementation for Tabs 3-4, integration testing

---

## 🎯 Project Overview

**Software Purpose:** A user authentication-based system that allows users to upload PDF books and multiple audio recordings of reading those books, then process each audio file individually to detect and remove repetitive words, sentences, or paragraphs keeping the LAST occurrence of each repeated element within that audio file.

**Enhanced Tab-Based Workflow Requirements:**
1. **User Authentication**: User login system with project ownership tied to user account
2. **Project Creation**: Create project with PDF upload for the book/document
3. **Tab 1 - File Management**: Central hub for all audio files and their transcriptions
   - Upload multiple audio files of reading sessions
   - View all uploaded audio files with status indicators
   - See which files have been transcribed
   - Access transcriptions generated from Tab 2
   - Select files for processing in other tabs
4. **Tab 2 - Transcription**: Merged with Tab 1 - Upload & Transcribe
   - ~~Select an audio file from Tab 1 (only untranscribed or re-transcribe)~~ NOW IN TAB 1
   - ~~Transcribe with word-level timestamps using OpenAI Whisper~~ NOW IN TAB 1
   - ~~Return transcription to Tab 1 for use in other tabs~~ NOW IN TAB 1
   - ~~Show transcription progress and results~~ NOW IN TAB 1
6. **Tab 3 - Detect & Delete Duplicates**: Process ONE audio file at a time ✅ IMPLEMENTED
   - Select a transcribed audio file from Tab 1
   - Detect duplicates within THAT SINGLE audio file only
   - Present duplicates with audio playback for review
   - User confirms which duplicates to delete (keeping LAST occurrence)
   - Navigate to Tab 4 (Review) with pending deletions
7. **Tab 4 - Review Deletions**: Preview and restore capability ✅ NEW
   - Automatically shown after selecting deletions in Tab 3
   - Visual deletion timeline with grouped segments
   - Audio preview player (WaveSurfer) showing processed audio
   - Real-time highlighting of deletion zones as audio plays
   - Restore individual segments or groups before final processing
   - Statistics preview (duration savings, deletion count)
   - Confirm & Process button → Navigate to Tab 5 (Results)
8. **Tab 5 - Results**: View and download processed audio ✅ IMPLEMENTED
   - Automatically shown after confirming deletions in Tab 4
   - Statistics display:
     * Original duration vs clean duration
     * Time saved and percentage reduction
   - WaveSurfer audio player with waveform visualization
   - Play/Pause/Stop controls with time progress
   - Download button for clean WAV audio file
   - Empty state when no processed files exist
9. **Tab 5 - Compare PDF**: Sequence alignment comparison ✅ IMPLEMENTED (December 2025)
   - **PDF Context**: Full book text (100,000+ words, correct reference)
   - **Transcript Context**: Section of book (10,000 words, with possible errors)
   - **Comparison Algorithm**: Modified Myers Diff (word-level sequence alignment)
     * Phase 1: Find starting point in PDF using sliding window (100-word chunks)
     * Phase 2: Extract PDF section (transcript length × 1.2) and perform alignment
     * Phase 3: Classify differences and aggregate into missing/extra sections
   - **Handles**:
     * Missing content (words/sentences in PDF but not in transcript)
     * Extra content (narrator info: "Chapter One", "Narrated by X")
     * Repeated/duplicate content (reading errors)
     * Natural speech variations and transcription errors
   - **Results Display**:
     * Matched PDF section preview with confidence score
     * Missing content list (in PDF, not in transcript)
     * Extra content list with classification (chapter markers, narrator info, duplicates)
     * Timestamps for extra content (for deletion marking)
     * Statistics: accuracy %, word counts, coverage %
   - **User Actions**:
     * Ignore sections (mark as acceptable narrator info)
     * Mark extra content for deletion (with timestamps)
     * View side-by-side alignment (color-coded: match/missing/extra)
   - **See**: `docs/architecture/PDF_COMPARISON_SOLUTION.md` for algorithm details

**🎯 Enhanced User Control Features:**
- **Side-by-side PDF comparison** with text highlighting
- **Interactive duplicate review** with audio segment playback  
- **User confirmation required** before any deletions
- **Smart recommendations** (keep last occurrence) with override capability
- **Visual feedback** and progress tracking throughout process
- **Comprehensive analytics** and processing summaries

**Example:** "I went to the store, I went to the store" → deletes the FIRST occurrence, keeps the LAST one.

## 🏗️ Architecture Requirements

### Backend: Django (Production-Ready)
- **Framework:** Django 5.2+ with Django REST Framework
- **Authentication:** Full Django authentication system with user management
- **Security:** CSRF protection, proper CORS handling, secure file uploads
- **Database:** SQLite for development, PostgreSQL for production
- **Task Processing:** Celery with Redis for background audio processing
- **File Storage:** Secure media handling with proper file validation
- **API Design:** RESTful endpoints with proper serialization and validation

### Frontend: React (Production-Ready) 
- **Framework:** React 18+ with modern hooks and functional components
- **State Management:** Context API or Redux Toolkit for complex state
- **UI/UX:** Professional, accessible interface with loading states and error handling
- **File Upload:** Drag-and-drop interface with progress indicators
- **Audio Playback:** Custom audio player with waveform visualization
- **Responsive:** Mobile-friendly design with proper breakpoints

### Processing Pipeline: Docker-Based Microservice
- **Containerization:** Separate Docker container for CPU-intensive processing
- **Transcription:** OpenAI Whisper or similar for accurate speech-to-text with timestamps
- **PDF Processing:** PyMuPDF or similar for reliable text extraction
- **Audio Processing:** pydub, librosa for audio manipulation and timestamp mapping
- **Communication:** REST API or message queue communication with main Django app

## 🔄 Tab-Based Processing Workflow

### Tab 1: File Management Hub ✅ IMPLEMENTED
```
Purpose: Central repository for all project files and their processing status

✅ COMPLETED FEATURES:
├── Audio File Management
│   ├── ✅ Drag & drop file upload with progress tracking
│   ├── ✅ Multiple file upload (MP3, WAV, M4A, FLAC, OGG) - max 500MB each
│   ├── ✅ Grid display with file cards showing:
│   │   ├── Filename, duration, file size
│   │   ├── Status badges (uploaded/processing/transcribed/processed/failed)
│   │   ├── Quick action buttons based on status
│   │   └── File selection highlighting
│   ├── ✅ Delete individual files with confirmation
│   ├── ✅ Automatic metadata extraction (duration, format)
│   └── ✅ Real-time status updates via polling
├── File Status Indicators (Color-coded badges)
│   ├── 🔵 Uploaded (ready to transcribe)
│   ├── 🟡 Processing (transcription/duplicate detection in progress)
│   ├── 🟢 Transcribed (ready for duplicate detection)
│   ├── 🟣 Processed (duplicates removed, clean audio available)
│   └── 🔴 Failed (with error message)
└── ✅ Cross-Tab Navigation
    ├── "Transcribe" button → Opens Tab 2 with file pre-selected
    ├── "Find Duplicates" button → Opens Tab 3 with file pre-selected
    ├── "Compare PDF" button → Opens Tab 4 with file pre-selected
    └── Context preserved across tab switches

📝 NOTES: ✅ IMPLEMENTED (Backend Complete, Frontend Basic)
```
Purpose: Transcribe ONE audio file at a time with word-level timestamps

✅ COMPLETED BACKEND APIs:
├── POST /api/projects/{id}/files/{id}/transcribe/
│   └── Starts async Whisper transcription with word timestamps
├── GET /api/projects/{id}/files/{id}/transcription/
│   └── Returns full transcription with segments
├── GET /api/projects/{id}/files/{id}/transcription/status/
│   └── Polls progress (0-100%) during transcription
└── GET /api/projects/{id}/files/{id}/transcription/download/
    └── Export as TXT or JSON format

✅ COMPLETED FRONTEND:
├── 1. File Selection
│   ├── ✅ Dropdown showing all audio files from Tab 1 (via context)
│   ├── ✅ Pre-selection when navigating from Tab 1 "Transcribe" button
│   └── ✅ Display file details (name, status)
├── 2. Transcription Process
│   ├── ✅ "Start Transcription" button (only for uploaded files)
│   ├── ✅ Real-time progress bar with 2-second polling
│   ├── ✅ Progress updates (10% → 100%)
│   └── ✅ Error handling
├── 3. Results Display
│   ├── ✅ Show complete transcription text
│   ├── ✅ Display word count
│   └── ⏳ Download button (backend ready, UI to add)
└── 4. Automatic Status Updates
    ├── ✅ File status updated to "transcribed" via context
    ├── ✅ Changes reflected immediately in Tab 1
    └── ✅ Transcription linked to audio file (one-to-one)

📝 TRANSCRIPTION → FILE LINKAGE:
- Each AudioFile has ONE Transcription (OneToOneField)
- Transcription includes: full_text, word_count, segments with timestamps
- TranscriptionSegment stores: text, start_time, end_time, word_index
- All tabs can access transcription via selectedAudioF ✅ BACKEND COMPLETE, FRONTEND STUB
```
Purpose: Detect and remove duplicates within ONE audio file at a time

✅ COMPLETED BACKEND APIs:
├── POST /api/projects/{id}/files/{id}/detect-duplicates/
│   └── Starts async duplicate detection (TF-IDF + cosine similarity ≥0.85)
├── GET /api/projects/{id}/files/{id}/duplicates/
│   └── Returns all duplicate groups with occurrences and timestamps
├── POST /api/projects/{id}/files/{id}/confirm-deletions/
│   └── Processes confirmed segment deletions, generates clean audio
├── GET /api/projects/{id}/files/{id}/processing-status/
│   └── Polls processing progress (0-100%)
├── GET /api/projects/{id}/files/{id}/processed-audio/
│   └── Download clean audio file URL
└── GET /api/projects/{id}/files/{id}/statistics/
    └── Returns before/after statistics (segments deleted, duration saved)

✅ COMPLETED BACKEND LOGIC:
├── DuplicateGroup model tracks groups within single audio file
├── TF-IDF vectorization with n-grams (1-3) for semantic matching
├── Cosine similarity threshold: 0.85 (configurable)
├── Automatic marking: Keep LAST occurrence, delete others
├── User can override auto-selections before confirming
├── Clean audio generation via pydub (removes selected segments)
├── Processed audio saved to AudioFile.processed_audio field
└── Progress tracking: 10% → 100% with real-time updates

⏳ FRONTEND TODO:
1. File Selection
   ├── Dropdown filter: Show ONLY transcribed/processed files from Tab 1
   ├── Pre-select file when navigating from Tab 1 "Find Duplicates" button
   └── Display transcription preview and word count

2. Duplicate Detection UI
   ├── "Detect Duplicates" button with loading state
   ├── Progress bar with polling (2-second intervals)
   └── Display: "Found X duplicate groups in Y seconds"

3. Interactive Review (KEY FEATURE)
   ├── List duplicate groups in collapsible cards
   ├── For each group show:
   │   ├── Duplicate text (first 100 chars)
   │   ├── Occurrence count (e.g., "Found 3 times")
   │   ├── Total duration that can be saved
   │   └── List of occurrences:
   │       ├── Timestamp (e.g., "01:23 - 01:28")
   │       ├── Checkbox (pre-checked for deletion, except last)
   │       ├── "KEEP (Last)" badge for final occurrence
   │       └── Mini audio player to preview segment
   ├── "Select All" / "Deselect All" buttons
   └── Summary: "X segments selected f ✅ BACKEND COMPLETE, FRONTEND STUB
```
Purpose: Compare a transcription against the PDF to find location and match percentage

✅ COMPLETED BACKEND APIs:
├── POST /api/projects/{id}/files/{id}/compare-pdf/
│   └── Starts async PDF comparison (TF-IDF + cosine similarity)
├── GET /api/projects/{id}/files/{id}/pdf-result/
│   └── Returns comparison results with match percentage
├── GET /api/projects/{id}/files/{id}/pdf-status/
│   └── Polls comparison progress (0-100%)
├── GET /api/projects/{id}/files/{id}/side-by-side/
│   └── Returns diff with matched/unmatched segments for visual display
└── POST /api/projects/{id}/files/{id}/retry-comparison/
    └── Retry with custom settings (threshold, page range)

✅ COMPLETED BACKEND LOGIC:
├── PDF text extraction via PyMuPDF (fitz)
├── TF-IDF vectorization with n-grams (1-3)
├── Cosine similarity calculation
├── Fallback to SequenceMatcher for detailed diff
├── Match percentage calculation (0-100%)
├── Validation status: excellent (≥90%), good (80-89%), acceptable (70-79%), poor (<70%)
├── Results stored on Transcription model:
│   ├── pdf_match_percentage
│   ├── pdf_validation_status
│   └── pdf_validation_result (JSON with detailed analysis)
├── Side-by-side diff generation:
│   ├── Matched blocks (text in both)
│   ├── Transcription-only blocks (extra words)
│   └── PDF-only blocks (missing words)
├── Custom settings support:
│   ├── similarity_threshold (default 0.8)
│   ├── pdf_page_range (optional: [start, end])
│   └── use_processed (compare clean audio transcription)
└── Progress tracking with real-time updates

⏳ FRONTEND TODO:
1. File Selection
   ├── Dropdown: Show transcribed OR processed files from Tab 1
   ├── Option: "Use original transcription" vs "Use processed transcription"
   ├── Pre-select when navigating from Tab 1 "Compare PDF" button
   └── Show which audio file the transcription belongs to

2. PDF Comparison Initiation
   ├── "Compare to PDF" button
   ├── Progress bar with polling
   └── Status: "Extracting PDF text... Comparing sections..."

3. Results Display (KEY FEATURE)
   ├── Large match percentage badge (color-coded):
   │   ├── Green: ≥90% (Excellent)
   │   ├── Blue: 80-89% (Good)
   │   ├── Yellow: 70-79% (Acceptable)
   │   └── Red: <70% (Poor - needs review)
   ├── Quick statistics:
   │   ├── Transcription length (word count)
   │   ├── PDF length (character count)
   │   ├── Matched characters
   │   └── Coverage percentages
   └── Action buttons based on score

4. Side-by-Side Comparison (ADVANCED FEATURE)
   ├── Two-panel layout (PDF left, Transcription right)
   ├── Synchronized scrolling
   ├── Color-coded highlighting:
   │   ├── GREEN: Text found in both
   │   ├── RED/ORANGE: PDF text not in transcription (missing)
   │   └── YELLOW: Transcription text not in PDF (extra)
   ├── Matching blocks counter
   └── Jump-to buttons for mismatched sections

5. Detailed Analysis
   ├── Location info (if detected):
   │   └── "PDF pages X-Y processed"
   ├── Quality assessment
   ├── Recommendations based on match percentage
   └── Export comparison report button

6. Actions
   ├── "Retry with Different Settings" button
   │   ├── Adjust similarity threshold slider
   │   └── Specify PDF page range
   ├── "Accept Results" - Save to project
   ├── "Re-process Duplicates" - Go back to Tab 3
   └── "Process Another File" - Return to Tab 1

📝 TRANSCRIPTION → PDF LINKAGE:
- Transcription model includes PDF comparison fields:
  - pdf_match_percentage: Float (0-100)
  - pdf_validation_status: String (excellent/good/acceptable/poor)
  - pdf_validation_result: JSON (detailed analysis)
- Results persist across sessions
- Tab 1 can show PDF match badge on transcribed files
- Clear indication of which transcription was compared

⏳ PRIORITY: Implement side-by-side comparison UI (Step 4 above)
   │   ├── Highlight missing words in RED
   │   └── Show section metadata (page, chapter)
   ├── Right Panel: Transcription
   │   ├── Highlight words found in PDF in GREEN
   │   ├── Highlight extra words not in PDF in ORANGE
   │   └── Show transcription metadata (duration, word count)
   ├── Match Statistics
   │   ├── Overall Match Percentage (X% of transcription found in PDF)
   │   ├── PDF Coverage (X% of PDF section covered by audio)
   │   ├── Missing Words Count
   │   └── Extra Words Count
   └── Synchronization: Scroll both panels together for comparison

4. Detailed Analysis Results
   ├── Location Information
   │   ├── PDF page range (e.g., "Pages 45-52")
   │   ├── Chapter/section name if detected
   │   └── Approximate position percentage in book
   ├── Quality Metrics
   │   ├── Word-level accuracy percentage
   │   ├── Sentence-level match count
   │   ├── Paragraph alignment quality
   │   └── Confidence score (0-100)
   ├── Missing Content Report
   │   ├── List of PDF sentences NOT found in audio
   │   ├── Suggested sections for re-recording
   │   └── Gaps in coverage visualization
   └── Recommendations
       ├── Quality assessment (Excellent/Good/Poor)
       ├── Suggestions for improvement
       └── Next steps guidance

5. Actions & Export
   ├── Accept Match: Save PDF section mapping to project
   ├── Reject & Retry: Try different matching parameters
   ├── Export Report: Download detailed comparison PDF
   ├── Return to Tab 1: Save results and update file status
   └── Navigate to Tab 3: If match is poor, re-process duplicates

Note: This tab helps verify audio quality and identify which part of the PDF
the recording covers. Useful for managing multi-file book recording projects.
```

### Single-File Duplicate Detection Algorithm
```python
def identify_duplicates_in_single_file(audio_file_segments):
    """
    Tab 3: Find repeated words, sentences, paragraphs within ONE audio file
    Note: Only processes a single audio file's segments at a time
    """
    # Group by normalized text within this file only
    text_groups = defaultdict(list)
    for segment in audio_file_segments:
        normalized_text = normalize(segment.text)
        text_groups[normalized_text].append(segment)
    
    # Find groups with multiple occurrences in THIS file
    duplicates = {text: segments for text, segments in text_groups.items() 
                 if len(segments) > 1}
    return duplicates

def mark_duplicates_for_removal_single_file(duplicates):
    """
    Tab 3: Keep LAST occurrence within the file, mark others for removal
    """
    removed = []
    for text, occurrences in duplicates.items():
        # Sort by timestamp within this single file
        sorted_occurrences = sorted(occurrences, key=lambda x: x.start_time)
        
        # Keep LAST occurrence, remove all others
        for segment in sorted_occurrences[:-1]:  # All but last
            segment.is_kept = False
            removed.append(segment)
        
        # Keep the last one
        sorted_occurrences[-1].is_kept = True
    
    return removed

def process_single_audio_file(audio_file_id, confirmed_deletions):
    """
    Tab 3: Process ONE audio file with user-confirmed deletions
    Returns clean audio file for this specific recording
    """
    audio_file = AudioFile.objects.get(id=audio_file_id)
    segments = audio_file.segments.all()
    
    # Keep only segments not in confirmed_deletions
    segments_to_keep = [s for s in segments if s.id not in confirmed_deletions]
    
    # Generate clean audio from kept segments
    clean_audio = generate_audio_from_segments(
        audio_file.file_path, 
        segments_to_keep
    )
    
    # Save as processed audio linked to original
    audio_file.processed_audio = clean_audio
    audio_file.status = 'processed'
    audio_file.save()
    
    return clean_audio
```

## 🏗️ Implementation Status & Architecture

### ✅ COMPLETED IMPLEMENTATION (December 2025)

**Backend API Layer (100% Complete):**
- Django REST Framework with proper authentication
- 18 new API endpoints across 4 tabs
- Celery background tasks with Redis
- Progress tracking and real-time polling
- File validation and error handling
- Database models with proper relationships

**Frontend Foundation (80% Complete):**
- React 18 with hooks and context API
- ProjectTabContext for cross-tab state management
- Tab navigation component with badges
- Tab 1 (Files): Fully functional with upload/delete
- Tab 2 (Transcribe): Basic UI with progress tracking
- Tab 3 & 4: Stubs ready for expansion
- Responsive CSS with modern styling

**What Works Right Now:**
1. ✅ Upload multiple audio files (drag & drop supported)
2. ✅ View all files with status indicators
3. ✅ Select file and navigate to transcription tab
4. ✅ Transcribe individual files with progress
5. ✅ View transcription results
6. ✅ File status updates propagate to Tab 1
7. ✅ Backend ready for duplicate detection
8. ✅ Backend ready for PDF comparison

**What Needs Frontend Work:**
- Tab 3: Interactive duplicate review UI
- Tab 4: Side-by-side comparison display
- Audio segment playback components
- Enhanced transcription display with timestamps

### 🔗 Cross-Tab Access & File Linkage

**How All Tabs Access Files:**
```javascript
// ProjectTabContext provides shared state
const {
  audioFiles,           // All uploaded files
  selectedAudioFile,    // Currently selected file
  selectAudioFile,      // Function to select a file
  refreshAudioFiles,    // Reload file list
  setActiveTab          // Navigate between tabs
} = useProjectTab();

// Any tab can:
1. View all files via audioFiles array
2. Select a file for processing
3. Navigate to another tab with file pre-selected
4. Trigger refresh to see updated file status
```

**File → Transcription → Processing Linkage:**
```
AudioFile (id=123, filename="chapter1.mp3")
    ↓ (OneToOne relationship)
Transcription (id=456, audio_file_id=123)
    ├── full_text: "The quick brown fox..."
    ├── word_count: 1523
    ├── pdf_match_percentage: 94.5
    └── segments → TranscriptionSegment[]
            ├── (id=789, text="The quick", start=0.0, end=0.5)
            ├── (id=790, text="brown fox", start=0.5, end=1.0)
            └── ... (with duplicate_group_id, is_kept flags)
    ↓ (ForeignKey relationship)
DuplicateGroup (id=321, audio_file_id=123)
    ├── group_id: "group_123_1"
    ├── duplicate_text: "The quick brown fox"
    ├── occurrence_count: 3
    └── (links to TranscriptionSegments via group_id)
    ↓
AudioFile.processed_audio → "media/audio/processed/chapter1_clean.wav"
```

**Visual Indicators Across Tabs:**

**Tab 1 File Card Shows:**
- ✅ Filename with icon
- ✅ Status badge (color-coded)
- ✅ Duration and file size
- ✅ "Transcribe" button (if uploaded)
- ✅ "Find Duplicates" button (if transcribed)
- ✅ "Compare PDF" button (if transcribed/processed)
- ⏳ TODO: PDF match percentage badge (if compared)
- ⏳ TODO: "Download Clean Audio" button (if processed)

**Tab 2 Transcription Shows:**
- ✅ Which audio file is being transcribed (dropdown selection)
- ✅ File status before starting
- ✅ Real-time progress bar
- ✅ Transcription results with word count
- ⏳ TODO: Link back to source file in Tab 1

**Tab 3 Duplicate Detection Shows:**
- ⏳ Which file's duplicates are being reviewed
- ⏳ Original audio filename at top
- ⏳ Link to transcription in Tab 2
- ⏳ Each duplicate occurrence with timestamp and audio preview

**Tab 4 PDF Comparison Shows:**
- ⏳ Which transcription is being compared
- ⏳ Source audio filename
- ⏳ Whether using original or processed transcription
- ⏳ Link to audio file in Tab 1

### 🎯 User Flow Examples

**Scenario 1: Upload → Transcribe → Review**
```
1. User in Tab 1: Uploads "chapter1.mp3"
2. User clicks "Transcribe" button on file card
   → Navigates to Tab 2 with chapter1.mp3 pre-selected
3. User clicks "Start Transcription"
   → Progress bar shows 0% → 100%
   → Transcription appears
4. User switches back to Tab 1
   → chapter1.mp3 now shows "Transcribed" badge
   → "Find Duplicates" button now visible
```

**Scenario 2: Detect Duplicates → Generate Clean Audio**
```
1. User in Tab 1: Selects transcribed file
2. User clicks "Find Duplicates" button
   → Navigates to Tab 3 with file pre-selected
3. User clicks "Detect Duplicates"
   → Backend finds 15 duplicate groups
   → UI shows interactive review (TODO)
4. User reviews duplicates, confirms deletions
   → Progress bar shows processing
   → Clean audio generated
5. User returns to Tab 1
   → File now shows "Processed" badge
   → "Download Clean Audio" button available (TODO)
```

**Scenario 3: Compare to PDF**
```
1. User in Tab 1: Selects transcribed file
2. User clicks "Compare PDF" button
   → Navigates to Tab 4 with file pre-selected
3. User clicks "Compare to PDF"
   → Backend calculates 87% match
   → Side-by-side view shows differences (TODO)
4. User sees "Good" match status
   → Can retry with different settings
   → Or accept and continue
```

### 🛠️ Implementation Guidelines

### Django Backend Structure
```
backend/
├── audioDiagnostic/           # Main Django app
│   ├── models.py             # AudioProject, ProcessingTask models
│   ├── serializers.py        # DRF serializers
│   ├── views.py              # API endpoints
│   ├── tasks.py              # Celery background tasks
│   └── services/             # Business logic separation
│       ├── pdf_processor.py
│       ├── audio_processor.py
│       └── duplicate_detector.py
├── media/                    # File storage
├── Tab-Based React Frontend Structure
```
frontend/
├── src/
│   Updated Django Models for Tab-Based Architecture
```python
class AudioProject(models.Model):
    """One project per book/document"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    pdf_file = models.FileField(upload_to='pdfs/')
    pdf_page_count = models.IntegerField(null=True)
    pdf_text_content = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class AudioFile(models.Model):
    """Multiple audio files per project - Tab 1"""
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('transcribing', 'Transcribing'),
        ('transcribed', 'Transcribed'),
        ('processing', 'Processing Duplicates'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ]
    
    project = models.ForeignKey(AudioProject, on_delete=models.CASCADE, related_name='audio_files')
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='audio/')
    duration_seconds = models.FloatField(null=True)
    file_size_bytes = models.BigIntegerField()
    format = models.CharField(max_length=10)  # mp3, wav, etc.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    upload_order = models.IntegerField()  # Order files were uploaded
    
    # Processed audio (after duplicate removal)
    processed_audio = models.FileField(upload_to='processed/', null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    last_processed_at = models.DateTimeField(null=True)
    error_message = models.TextField(null=True, blank=True)
    
    class Meta:
        ordering = ['upload_order']

class Transcription(models.Model):
    """One transcription per audio file - Generated in Tab 2"""
    audio_file = models.OneToOneField(AudioFile, on_delete=models.CASCADE, related_name='transcription')
    full_text = models.TextField()
    word_count = models.IntegerField()
    confidence_score = models.FloatField(null=True)  # Average confidence
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional: Link to PDF section if compared in Tab 4
    matched_pdf_section = models.TextField(null=True, blank=True)
    pdf_start_page = models.IntegerField(null=True)
    pdf_end_page = models.IntegerField(null=True)
    pdf_match_percentage = models.FloatField(null=True)

class TranscriptionSegment(models.Model):
    """Word/phrase segments with timestamps - Used in Tab 3"""
    transcription = models.ForeignKey(Transcription, on_delete=models.CASCADE, related_name='segments')
    text = models.TextField()
    start_time = models.FloatField()  # seconds
    end_time = models.FloatField()
    word_index = models.IntegerField()  # Position in transcription
    confidence_score = models.FloatField()
    
    # Duplicate detection metadata (Tab 3)
    is_duplicate = models.BooleanField(default=False)
    duplicate_group_id = models.CharField(max_length=100, null=True)  # Groups identical segments
    is_last_occurrence = models.BooleanField(default=False)  # Recommended to keep
    is_kept = models.BooleanField(default=True)  # User's decision
    
    class Meta:
        ordering = ['start_time']

class DuplicateGroup(models.Model):
    """Track duplicate groups for a single audio file - Tab 3"""
    audio_file = models.ForeignKey(AudioFile, on_delete=models.CASCADE, related_name='duplicate_groups')
    group_id = models.CharField(max_length=100)
    duplicate_text = models.TextField()
    occurrence_count = models.IntegerField()
    total_duration_seconds = models.FloatField()  # Time saved if all removed
    created_at = models.DateTimeField(auto_now_add=True Preview selected audio file
│   │   ├── Tab3_DuplicateDetection/
│   │   │   ├── DuplicateDetectionTab.js    # Main container for Tab 3
│   │   │   ├── TranscribedFileSelector.js  # Select from transcribed files only
│   │   │   ├── DuplicateReviewList.js      # List of duplicate groups
│   │   │   ├── DuplicateGroupCard.js       # Individual duplicate display
│   │   │   ├── SegmentAudioPlayer.js       # Play specific audio segments
│   │   │   ├── DeletionConfirmation.js     # Confirm selections before processing
│   │   │   └── ProcessingResults.js        # Show before/after statistics
│   │   ├── Tab4_PDFComparison/
│   │   │   ├── PDFComparisonTab.js         # Main container for Tab 4
│   │   │   ├── TranscriptionSelector.js    # Select transcription to compare
│   │   │   ├── ComparisonView.js           # Side-by-side comparison display
│   │   │   ├── PDFPanel.js                 # Left panel showing PDF content
│   │   │   ├── TranscriptPanel.js          # Right panel showing transcription
│   │   │   ├── MatchStatistics.js          # Display match percentage and metrics
│   │   │   ├── LocationInfo.js             # Show PDF location details
│   │   │   └── ComparisonReport.js         # Detailed analysis and export
│   │   ├── Shared/
│   │   │   ├── AudioPlayer.js              # Reusable audio player component
│   │   │   ├── ProgressBar.js              # Progress indicator
│   │   │   ├── StatusIndicator.js          # Processing status display
│   │   │   ├── ErrorDisplay.js             # Error message component
│   │   │   └── LoadingSpinner.js           # Loading state component
│   │   └── ProjectDashboard/              # Project selection/creation
│   ├── hooks/
│   │   ├── useAudioFiles.js               # Manage audio file state
│   │   ├── useTranscription.js            # Transcription operations
│   │   ├── useDuplicateDetection.js       # Duplicate detection logic
│   │   ├── usePDFComparison.js            # PDF comparison operations
│   │   └── useTabNavigation.js            # Tab state management
│   ├── services/
│   │   ├── audioFileService.js            # Audio file API calls
│   │   ├── transcriptionService.js        # Transcription API calls
│   │   ├── duplicateService.js            # Duplicate detection API calls
│   │   └── pdfComparisonService.js        # PDF comparison API calls
│   ├── contexts/
│   │   ├── ProjectContext.js              # Project-level state
│   │   ├── FileManagementContext.js       # Tab 1 state management
│   │   └── AuthContext.js                 # Authentication state
│   └── pages/
│       ├── ProjectDetailPage.js           # Main page with tabs
│       └── ProjectListPage.js             # Project selection
    text = models.TextField()
    start_time = models.FloatField()  # seconds
    end_time = models.FloatField()
    is_duplicate = models.BooleanField(default=False)
    confidence_score = models.FloatField()
```

### Enhanced React Frontend Structure
```
frontend/
├── src/
│   ├── components/
│   │   ├── Upload/                    # File upload components
│   │   ├── AudioPlayer/               # Custom audio player with segment playback
│   │   ├── ProjectDashboard/          # Project management
│   │   ├── ProcessingStatus/          # Real-time status updates
│   │   ├── PDFMatchComparison/        # Side-by-side PDF vs Audio comparison ⭐ New
│   │   ├── DuplicateReviewComponent/  # Interactive duplicate confirmation ⭐ New
│   │   ├── TextHighlighting/          # Visual text comparison tools ⭐ New
│   │   └── AudioSegmentPlayer/        # Precise segment playback ⭐ New
│   ├── hooks/               # Custom React hooks
│   ├── services/            # Enhanced API communication
│   ├── utils/               # Helper functions including audio processing
│   └── contexts/            # React context providers with enhanced state
└── package.json
```

## 🔧 Technical Specifications

### Audio Processing Requirements
- **Input Formats:** MP3, WAV, M4A, FLAC
- **Output Quality:** Maintain original audio quality
- **Timestamping:** Precise word-level timestamps for accurate editing
- **Transition Handling:** Smooth audio cuts to avoid clicks/pops

### PDF Processing Requirements
- **Text Extraction:** Handle various PDF formats (text-based, OCR if needed)
- **Layout Preservation:** Maintain paragraph and section structure
- **Error Handling:** Graceful handling of corrupted/protected PDFs

### Performance Requirements
- **File Size Limits:** Support large files (500MB+ audio, 100MB+ PDF)
- **Processing Time:** Show progress indicators for long operations
- **Memory Management:** Stream processing for large files
- **Concurrent Users:** Handle multiple simultaneous processing tasks

## 🚀 User Experience Flow

### 1. Project Creation
```
1. User logs in/registers
2. Creates new project with title
3. Uploads PDF and audio files
4. Optionally specifies section to process
5. Initiates processing
```

### 2. Processing Feedback
```
1. Real-time progress updates
2. Visual representation of processing stages
3. Error handling with clear messages
4. Ability to cancel long-running tasks
```

### 3. Results Review
```
1. Side-by-side comparison (original vs. processed)
2. Waveform visualization showing removed segments
3. Transcript with highlighted duplicates
4. Audio player with playback controls
5. Download processed audio file
```

## 🔒 Security & Best Practices

### Django Security
- CSRF protection on all forms
- Proper file type validation and scanning
- User authentication and authorization
- Rate limiting on API endpoints
- Secure file storage with access controls

### React Security
- Input sanitization and validation
- Secure file upload handling
- Environment variable management
- CSP headers for XSS protection

### Docker Security
- Non-root user execution
- Minimal base images
- Resource limits and monitoring
- Network isolation between services

## 🧪 Testing Strategy

### Backend Testing
- Unit tests for all business logic
- Integration tests for API endpoints
- Celery task testing
- File processing pipeline tests

### Frontend Testing
- Component unit tests with Jest/React Testing Library
- Integration tests for user workflows
- E2E tests with Cypress/Playwright

## 📦 Deployment Considerations

### Development Setup
- Docker Compose for local development
- Hot reload for both Django and React
- Shared volumes for file processing
- Redis for Celery task queue

### Production Setup
- Container orchestration (Kubernetes/Docker Swarm)
- Load balancing for processing services
- Persistent storage for user files
- Monitoring and logging solutions

## 🎯 Success Criteria

1. **Accuracy:** >95% accuracy in detecting actual duplicates
2. **Performance:** Process 1-hour audio file in <10 minutes
3. **Usability:** Non-technical users can complete workflow easily
4. **Reliability:** Handle edge cases gracefully without data loss
5. **Scalability:** Support multiple concurrent users processing files

## 📋 Development Phases

### ✅ Phase 1: Backend Foundation (COMPLETE - December 2025)
- ✅ Database models with proper relationships
- ✅ All API endpoints implemented (18 total)
- ✅ Celery background tasks with progress tracking
- ✅ File validation and error handling
- ✅ Authentication and authorization
- ✅ TF-IDF duplicate detection algorithm
- ✅ PDF comparison with match percentage
- ✅ Clean audio generation from segments

### ⏳ Phase 2: Frontend MVP (70% COMPLETE - In Progress)
- ✅ Tab navigation infrastructure
- ✅ Cross-tab state management (ProjectTabContext)
- ✅ Tab 1: File upload, list, delete (100%)
- ✅ Tab 2: Basic transcription UI (60%)
- ⏳ Tab 3: Interactive duplicate review UI (10%)
- ⏳ Tab 4: PDF comparison display (10%)
- ⏳ Audio segment playback components
- ⏳ Side-by-side comparison view

### Phase 3: Enhanced Features (Planned)
- Advanced duplicate detection settings (custom thresholds)
- Waveform visualization for audio editing
- Batch processing (queue multiple files)
- Comparison report export (PDF/HTML)
- Project statistics dashboard
- User preferences and settings
- Mobile-optimized responsive design

### Phase 4: Production Ready (Planned)
- Performance optimization (large file handling)
- Comprehensive E2E test suite
- Advanced error handling and recovery
- Monitoring and logging infrastructure
- User documentation and tutorials
- Deployment automation (CI/CD)

---

## 📖 Implementation Status Summary

**✅ WHAT'S WORKING NOW (December 2025):**
1. Upload audio files with drag & drop
2. View all files with real-time status updates
3. Transcribe individual files with progress tracking
4. View transcription results
5. Navigate between tabs with file pre-selection
6. All backend APIs ready for duplicate detection
7. All backend APIs ready for PDF comparison
8. Database relationships properly established

**⏳ WHAT NEEDS FRONTEND WORK:**
1. Tab 3: Interactive duplicate review interface
2. Tab 4: Side-by-side PDF comparison display
3. Audio segment playback components
4. Enhanced transcription display with timestamps
5. Download buttons and export functionality

**📝 KEY DOCUMENTATION:**
- Architecture Spec: `/docs/architecture/AI_CODING_PROMPT.md` (this file)
- Implementation Status: `/docs/IMPLEMENTATION_STATUS.md` (detailed checklist)
- Refactoring Plan: `/docs/REFACTORING_TAB_BASED_UI.md` (original plan)

---

**Note for AI Assistants:** 
- **Backend is 100% complete** - All APIs tested and working
- **Frontend is 70% complete** - Tab 1-2 functional, Tab 3-4 need UI work
- **Next Priority:** Build interactive duplicate review UI (Tab 3)
- **Architecture:** Tab-based with shared state via React Context
- **File Linkage:** Clear one-to-one relationships with visual indicators
- Follow existing patterns in Tab1Files.js and Tab2Transcribe.js for consistency