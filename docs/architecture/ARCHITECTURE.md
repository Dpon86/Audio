# Software Architecture Documentation
# Audio Duplicate Detection System

## ✅ **Architecture Version: 2.0 - Tab-Based (December 2025)**

**Major Update:** Migrated from single-page batch processing to **tab-based individual file workflow**.

### **Implementation Status:**
- ✅ **Backend:** 100% Complete (18 new API endpoints, all models migrated)
- ✅ **Frontend:** 70% Complete (Tab 1-2 functional, Tab 3-4 stubs ready)
- 📚 **Documentation:** AI_CODING_PROMPT.md, IMPLEMENTATION_STATUS.md, TAB_ARCHITECTURE_VISUAL.md

## 🏗️ **System Overview**

The Audio Duplicate Detection system is built with a **microservices architecture** using Django REST API backend, React frontend with tab-based UI, and Docker containerization for audio processing tasks.

```
┌─────────────────────────────────────────────────────────────┐
│              React Frontend (Port 3000)                     │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐   │
│  │  Tab 1   │  Tab 2   │  Tab 3   │  Tab 4   │  Tab 5   │   │ ✅ UPDATED
│  │  Files   │Duplicates│ Results  │ Review   │ Compare  │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘   │
│         │ ProjectTabContext (Shared State)                  │
└─────────┼───────────────────────────────────────────────────┘
          │
          │ REST API (22 endpoints)
          ↓
┌─────────────────────────────────────────────────────────────┐
│              Django API (Port 8000)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Views: tab1_file_management, tab2_duplicate_detection│   │
│  │        tab3_results, tab4_review_comparison,         │   │ ✅ UPDATED
│  │        tab5_pdf_comparison                           │   │
│  └──────────────────────────────────────────────────────┘   │
│         │ Celery Background Tasks                           │
└─────────┼───────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│         Docker Services (Celery + Redis)                    │
│  - transcribe_single_audio_file_task                        │ ✅ NEW
│  - detect_duplicates_single_file_task                       │ ✅ NEW
│  - process_deletions_single_file_task                       │ ✅ NEW
│  - generate_comparison_report_task (processed vs original)  │ ✅ NEW
│  - compare_transcription_to_pdf_task                        │ ✅ NEW
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 **Frontend Architecture** 
**Location:** `frontend/audio-waveform-visualizer/`

### **Architecture Version 2.0: Tab-Based UI** ✅ NEW

#### **Core Design Principles:**
1. **Individual File Processing:** Each audio file processed independently (not batched)
2. **Shared State:** ProjectTabContext provides cross-tab access to files and selections
3. **Progressive Workflow:** Upload → Transcribe → Detect Duplicates → Compare PDF
4. **Real-time Updates:** Status changes propagate immediately to all tabs

#### **`src/App.js`**
- **Purpose:** Main application component and routing configuration
- **Responsibilities:** 
  - React Router setup for navigation
  - Global app-wide state management
  - Authentication context provider
  - Error boundary implementation
- **Routes:**
  - `/` → Project list page
  - `/project/:id` → ProjectDetailPageNew (Tab-based) ✅ NEW
  - `/project/:id/legacy` → ProjectDetailPage (Old single-page) 🔄 Legacy
  - `/create` → New project creation

#### **`src/index.js`**
- **Purpose:** Application entry point and React DOM mounting
- **Responsibilities:**
  - React app initialization
  - Global CSS imports
  - Service worker registration (if applicable)

### **Screen Components** 
**Location:** `src/screens/`

#### **`ProjectListPage.js`**
- **Purpose:** Main dashboard showing all user projects
- **Features:**
  - Project grid/list view with status indicators
  - Create new project button
  - Project filtering and search
  - Real-time status updates
- **API Calls:** `GET /api/projects/`
- **State Management:** Project list state, loading states

#### **`ProjectDetailPageNew.js`** ✅ **NEW - Tab-Based Architecture**
- **Purpose:** Modern tab-based interface for individual file processing
- **Architecture:**
  - 5-tab layout: Files, Duplicates, Results, Review, Compare PDF
  - Shared state via ProjectTabContext
  - Tab workflow: Upload → Transcribe → Detect → Process → Review → Compare
  - Each tab accesses same file list
  - File selection persists across tabs
- **Features:**
  - Tab navigation with badges and icons
  - Cross-tab file selection and status updates
  - Real-time progress tracking per file
  - Visual status indicators (color-coded)
- **API Calls:** Uses new tab-specific endpoints (see API section)
- **Components:**
  - `ProjectTabs`: Navigation component
  - `Tab1Files`: Upload & file management (merged upload + transcribe)
  - `Tab2Duplicates`: Single-file duplicate detection
  - `Tab3Results`: Processed audio playback & download
  - `Tab4Review`: Project-wide comparison (processed vs original vs PDF vs deletions) ✅ UPDATED
  - `Tab5ComparePDF`: PDF validation
- **State Management:** 
  - ProjectTabContext: Shared file list, selection, navigation
  - File status updates propagate to all tabs
  - Comparison state for review workflow
  - Loading states per operation

#### **`ProjectDetailPage.js`** 🔄 **LEGACY - Single-Page Architecture**
- **Status:** Maintained for backward compatibility
- **Purpose:** Original batch processing interface (all files together)
- **Features:**
  - PDF file upload with drag-and-drop
  - Audio file upload with validation
  - Multi-step processing workflow:
    - Step 1: Transcribe all audio files together
    - Step 2a: Match combined audio to PDF section
    - Step 2b: Detect duplicates across all files
    - Step 2c: Interactive duplicate review
  - Infrastructure status monitoring
  - Real-time progress tracking
  - Results download interface
- **APITab Components** ✅ NEW
**Location:** `src/components/ProjectTabs/`

##### **`ProjectTabs.js`**
- **5 tabs with icons:** 📁 Files, 🔍 Duplicates, ✅ Results, 👁️ Review, 📄 Compare PDF
  - Active tab highlighting
  - Badge counts (file count, pending deletions, etc.)
  - Smooth transitions
  - Responsive design

##### **`Tab1Files.js`** ✅ IMPLEMENTED (100%)
- **Purpose:** File management and transcription hub
- **Features:**
  - Drag & drop file upload (MP3, WAV, M4A, FLAC, OGG)
  - File grid with cards (filename, duration, size, status)
  - Status badges (uploaded/processing/transcribed/processed/failed)
  - Transcribe button (triggers transcription for individual files)
  - Quick action buttons (Find Duplicates, Compare PDF)
  - Delete with confirmation
  - Real-time status updates
  - Cross-tab navigation (click button → switch tab with file pre-selected)
- **API Calls:**
  - `GET /api/projects/{id}/files/` - List files
  - `POST /api/projects/{id}/files/` - Upload files
  - `POST /api/projects/{id}/files/{id}/transcribe/` - Start transcription
  - `DELETE /api/projects/{id}/files/{id}/` - Delete file
  - `GET /api/projects/{id}/files/{id}/status/` - Poll status

##### **`Tab2Duplicates.js`** ✅ IMPLEMENTED (95%)
- **Purpose:** Single-file duplicate detection and selection
- **Features:**
  - File selector (transcribed files only)
  - "Detect Duplicates" button with auto-polling
  - Interactive duplicate group cards (expandable)
  - Checkbox selection (auto-selects all except last occurrence)
  - Group metadata (occurrence count, total duration)
  - Visual indicators (kept vs deleted segments)
  - "Confirm & Process" button → Navigates to Tab 3 Results
- **API Calls:**
  - `POST /api/projects/{id}/files/{id}/detect-duplicates/`
  - `GET /api/projects/{id}/files/{id}/duplicates/`
- **Backend:** All APIs implemented and functional

##### **`Tab3Results.js`** ✅ IMPLEMENTED (100%)
- **Purpose:** Final processed audio playback and download
- **Features:**
  - File selector (processed files only: status='processed')
  - Statistics cards:
    * Original duration
    * Clean duration (final)
    * Time saved (with percentage)
  - WaveSurfer audio player:
    * Visual waveform display
    * Play/Pause/Stop controls
    * Time progress display
  - Download button (exports clean WAV file)
  - Processing status indicator during deletion task
  - "Review Changes" button → Navigates to Tab 4 Review
  - Empty state messages
- **API Calls:**
  - `POST /api/projects/{id}/files/{id}/confirm-deletions/` - Process final deletions
  - `GET /tasks/{task_id}/status/` - Poll processing status
  - `GET /media/processed/{filename}` - Stream processed audio

##### **`Tab4Review.js`** ✅ NEW - Project-Wide Comparison
- **Purpose:** Compare processed audio against original, PDF transcript, and detected deletions across entire project
- **Scope:** PROJECT-WIDE (not per-file) - Shows all files and their transformations
- **Features:**
  - **Multi-File Comparison View:**
    * Grid/list of all processed files in project
    * Each row shows: Filename, Original Duration, Final Duration, Time Saved, Status
    * Select files to compare side-by-side
  - **Dual Audio Player:**
    * Left: Original audio with waveform
    * Right: Processed audio with waveform
    * Synchronized playback (play both simultaneously)
    * Individual playback controls
    * Time-synced highlighting of deletion regions
  - **Deletion Regions Overlay:**
    * Red highlighted regions on original waveform showing what was removed
    * Timestamps of deletions displayed
    * Click region to jump to that timestamp
    * Hover shows segment text that was deleted
  - **PDF Transcript Comparison:**
    * Side-by-side view of:
      - PDF transcript (if uploaded)
      - Original transcription
      - Processed transcription (after deletions)
    * Highlight differences and deletions
    * Scroll-synced navigation
  - **Statistics Dashboard:**
    * Project-wide metrics:
      - Total files processed
      - Total time saved across all files
      - Total deletions count
      - Average compression ratio
    * Per-file breakdown table
  - **Verification Actions:**
    * "Mark as Reviewed" button per file
    * "Export Comparison Report" (PDF or CSV)
    * "Revert File" - Restore specific file to original
    * "Approve All" - Mark entire project as reviewed
- **API Calls:**
  - `GET /api/projects/{id}/comparison/` - Get all files with comparison data
  - `GET /api/projects/{id}/files/{id}/comparison-details/` - Detailed comparison for one file
  - `GET /api/projects/{id}/files/{id}/deletion-regions/` - Get deletion regions
  - `POST /api/projects/{id}/files/{id}/mark-reviewed/` - Mark file as reviewed
  - `POST /api/projects/{id}/export-comparison/` - Generate comparison report
  - `POST /api/projects/{id}/files/{id}/revert/` - Revert file to original
- **Technical Details:**
  - Uses WaveSurfer.js RegionsPlugin for deletion highlighting
  - Synchronized audio playback using Web Audio API
  - PDF rendering using PDF.js
  - Comparison data cached on backend for performance
  - Real-time status updates if files still processing

##### **`Tab5ComparePDF.js`** ✅ IMPLEMENTED (100%) - December 2025
- **Purpose:** Sequence alignment comparison between transcript and PDF book
- **Problem Domain:**
  - PDF = Full book text (entire reference, e.g., 100K words)
  - Transcript = Audio section (partial, e.g., 10K words from middle of book)
  - Transcript may contain: missing words/sentences, extra content (narrator info, chapter markers), duplicates, variations
  - Goal: Find where transcript starts in PDF, measure accuracy, identify differences
- **Comparison Algorithm: Modified Myers Diff (Word-Level Sequence Alignment)**
  - **Phase 1 - Find Starting Point:**
    * Sliding window search (100 words from transcript start)
    * Scan PDF with normalized word matching
    * Stop when 85%+ match found (early exit optimization)
    * Result: Starting position in PDF + confidence score
  - **Phase 2 - Sequence Alignment:**
    * Extract PDF section (transcript length × 1.2 buffer for missing content)
    * Myers diff algorithm on word arrays (like Git diff)
    * Build edit graph: MATCH, DELETE (missing from transcript), INSERT (extra in transcript)
    * Find shortest edit path (optimal alignment)
    * Complexity: O((N+M)*D) where D=differences, very fast for high similarity (90%+)
  - **Phase 3 - Classify & Aggregate:**
    * Group consecutive operations into sections
    * Missing content: Consecutive DELETE operations (in PDF, not in transcript)
    * Extra content: Consecutive INSERT operations (in transcript, not in PDF)
    * Classify extra: chapter markers, narrator info, duplicates, other
    * Match to TranscriptionSegments for timestamps
- **Features:**
  - File selector (transcribed files only)
  - "Start Comparison" button with progress polling
  - **Matched PDF Section Display:**
    * Shows exact section of PDF being compared
    * Character positions and confidence score
    * Preview of matched text (scrollable)
  - **Missing Content List:**
    * Sentences/words in PDF but not in transcript
    * Word counts and match percentages
    * Position in PDF for context
  - **Extra Content List:**
    * Content in transcript not in PDF
    * Classification: chapter_marker, narrator_info, duplicate, other
    * Timestamps (start/end time) for deletion marking
    * "Ignore This" button (mark as acceptable)
    * "Mark for Deletion" button (with timestamp confirmation)
  - **Ignored Sections Management:**
    * View all ignored sections
    * Remove from ignored list
    * Auto-recompare after changes
  - **Side-by-Side Comparison:**
    * Color-coded alignment view
    * Green = matching content
    * Orange = extra in transcript
    * Pink = missing from transcript
  - **Statistics Dashboard:**
    * Match quality (excellent/good/fair/poor)
    * Coverage % (PDF words found in transcript)
    * Accuracy % (transcript words matching PDF)
    * Word counts (transcript, PDF, missing, extra)
  - **Reset Comparison:** Clear all results and start fresh
- **API Calls:**
  - `POST /api/projects/{id}/files/{id}/compare-pdf/` - Start comparison task
  - `GET /api/projects/{id}/files/{id}/pdf-result/` - Get comparison results
  - `GET /api/projects/{id}/files/{id}/pdf-status/` - Poll progress
  - `GET /api/projects/{id}/files/{id}/side-by-side/` - Get aligned comparison
  - `POST /api/projects/{id}/files/{id}/ignored-sections/` - Save ignored sections
  - `POST /api/projects/{id}/files/{id}/mark-for-deletion/` - Mark segments for deletion
  - `POST /api/projects/{id}/files/{id}/reset-comparison/` - Reset results
- **Backend:** Fully implemented with Myers diff algorithm
- **Documentation:** 
  - `docs/architecture/PDF_COMPARISON_SOLUTION.md` - Detailed algorithm explanation
  - `docs/PDF_COMPARISON_ALGORITHM_IMPROVEMENTS.md` - Implementation details
  - `docs/TAB5_PDF_COMPARISON_ENHANCEMENTS.md` - Feature documentation

#### **Shared Context** ✅ NEW
**Location:** `src/contexts/`

##### **`ProjectTabContext.js`**
- **Purpose:** Cross-tab state management
- **Provides:**
  - `audioFiles[]` - All uploaded files (live updates)
  - `selectedAudioFile` - Currently selected file
  - `selectAudioFile()` - Select file (persists across tabs)
  - `refreshAudioFiles()` - Reload file list
  - `updateAudioFile()` - Update single file status
  - `removeAudioFile()` - Remove from list
  - `activeTab` - Current tab ('fil✅ **Enhanced for Tab-Based Architecture**
```python
class AudioProject(models.Model):
    """Main project container - One per book/document"""
    # Core Fields: user (FK), title, status, created_at, updated_at
    # PDF: pdf_file (FileField), pdf_page_count, pdf_text_content
    # Legacy fields maintained for backward compatibility

class AudioFile(models.Model): ✅ ENHANCED
    """Individual audio files - Multiple per project"""
    # Core: project (FK), filename, audio_file (FileField)
    # NEW FIELDS:
    # - duration_seconds: Float (auto-extracted via pydub)
    # - file_size_bytes: BigInteger (for UI display)
    # - format: String (mp3, wav, m4a, flac, ogg)
    # - processed_audio: FileField (clean audio after duplicate removal)
    # - task_id: String (for progress tracking)
    # - last_processed_at: DateTime
    # Status: uploaded → processing → transcribed → processed → failed
    # Order: order_index (upload order)

class Transcription(models.Model): ✅ NEW
    """One transcription per audio file - OneToOne relationship"""
    # audio_file: OneToOneField (AudioFile)
    # full_text: TextField (complete transcription)
    # word_count: Integer
    # confidence_score: Float (average)
    # created_at: DateTime
    # PDF Comparison Results (from Tab 4):
    # - pdf_match_percentage: Float (0-100)
    # - pdf_validation_status: String (excellent/good/acceptable/poor)
    # - pdf_validation_result: JSON (detailed analysis)
    # Legacy: matched_pdf_section, pdf_start_page, pdf_end_page

class TranscriptionSegment(models.Model): ✅ ENHANCED
    """Word/phrase segments with timestamps and duplicate tracking"""
    # transcription: ForeignKey (Transcription) ✅ NEW - changed from audio_file
    # Core: text, start_time, end_time, segment_index
    # confidence_score: Float
    # Duplicate Detection (Tab 3):
    # - duplicate_group_id: String (groups identical segments)
    # - is_kept: Boolean (user's deletion decision)
    # Default: All segments kept (is_kept=True) unless user confirms deletion

class DuplicateGroup(models.Model): ✅ NEW
    """Track duplicate groups within a single audio file"""
    # audio_file: ForeignKey (AudioFile)
    # group_id: String (unique, e.g., "group_123_1")
    # duplicate_text: TextField (representative text)
    # occurrence_count: Integer (how many times it appears)
    # total_duration_seconds: Float (time that can be saved)
    # created_at: DateTime
    # Links to TranscriptionSegments via duplicate_group_id

class TranscriptionWord(models.Model):
    """Word-level timestamps from Whisper - Unchanged"""
    # segment: ForeignKey (TranscriptionSegment)
    # word: String, start: Float, end: Float
    # confidence: Float, word_index: Integer

class ProcessingResult(models.Model): 🔄 LEGACY
    """Tracks results of batch processing - Maintained for compatibility"""
    # Statistics: total_segments_processed, duplicates_removed, time_saved
    # Content Analysis: pdf_coverage_percentage, missing_content_count
    # Processing Log: detailed_processing_steps (JSON)
```

#### **Key Relationship Changes:**
```
OLD (Batch Processing):
AudioFile → TranscriptionSegment (direct FK)

NEW (Individual Processing):
AudioFile → Transcription (OneToOne) → TranscriptionSegment (FK)
                   ↓
          DuplicateGroup (FK to AudioFile
  - Waveform visualization
  - Playback controls
  - Timestamp navigation
  - Volume control

### **Styling and Assets**
**Location:** `src/styles/` and `public/`

#### **`App.css`**
- **Purpose:** Global application styles
- **Contains:** Layout, typography, color scheme, responsive breakpoints

#### **`components/`** (CSS files)
- **Purpose:** Component-specific styling
- **Structure:** Modular CSS for each component

---

## 🚀 **Backend Architecture** 
**Location:** `backend/`

### **Django Project Structure**

#### **`myproject/` (Django Settings)**

##### **`settings.py`** ⭐ **Configuration Hub**
- **Purpose:** Central configuration for entire Django application
- **Key Sections:**
  - Database configuration (SQLite/PostgreSQL)
  - Celery settings for background tasks
  - File storage and media handling
  - CORS configuration for React frontend
  - Security settings (CSRF, ALLOWED_HOSTS)
  - API authentication settings
- **Environment Variables:** Database URLs, secret keys, debug flags

##### **`urls.py`**
- **Purpose:** Root URL routing configuration
- **Routes:**
  - `/api/` → API endpoints
  - `/media/` → File serving
  - `/admin/` → Django admin interface

##### **`celery.py`**
- **Purpose:** Celery configuration for background task processing
- **Responsibilitie- **Tab-Based Architecture** ✅ NEW

##### **View Organization**
**Location:** `audioDiagnostic/views/`
- `tab1_file_management.py` - File upload, list, delete, status
- `tab2_transcription.py` - Individual file transcription
- `tab3_duplicate_detection.py` - Single-file duplicate detection
- `tab4_pdf_comparison.py` - Transcription-to-PDF validation

##### **Tab 1: File Management Views** ✅ IMPLEMENTED
**Location:** `views/tab1_file_management.py`
- **`AudioFileListView`:** GET/POST - List files, upload new files
- **`AudioFileDetailDeleteView`:** GET/DELETE/PATCH - File operations
- **`AudioFileStatusView`:** GET - Poll file status (for real-time updates)
- **Features:**
  - File validation (type, size limits: 500MB max)
  - Auto-extract metadata (duration via pydub)
  - Order management (upload sequence)
  - Delete with cleanup (file + database)

##### **Tab 2: Transcription Views** ✅ IMPLEMENTED
**Location:** `views/tab2_transcription.py`
- **`SingleFileTranscribeView`:** POST - Start transcription for ONE file
- **`SingleFileTranscriptionResultView`:** GET - Get full transcription
- **`SingleFileTranscriptionStatusView`:** GET - Poll progress (0-100%)
- **`TranscriptionDownloadView`:** GET - Export as TXT or JSON
- **Features:**
  - Async Celery task with progress tracking
  - Word-level timestamps from Whisper
  - Creates Transcription + TranscriptionSegment records
  - Status updates: uploaded → processing → transcribed

##### **Tab 3: Duplicate Detection Views** ✅ IMPLEMENTED
**Location:** `views/tab3_duplicate_detection.py`
- **`SingleFileDetectDuplicatesView`:** POST - Detect duplicates in ONE file
- **`SingleFileDuplicatesReviewView`:** GET - Get duplicates for review
- **`SingleFileConfirmDeletionsView`:** POST - Process confirmed deletions
- **`SingleFileProcessingStatusView`:** GET - Poll processing progress
- **`SingleFileProcessedAudioView`:** GET - Download clean audio
- **`SingleFileStatisticsView`:** GET - Before/after stats
- **Features:**
  - TF-IDF + cosine similarity (≥0.85 threshold)
  - Creates DuplicateGroup records
  - Interactive review: User confirms which to delete
  - Keep LAST occurrence by default
  - Generates clean audio (removes confirmed segments)
  - Status updates: transcribed → processing → processed

##### **Tab 4: PDF Comparison Views** ✅ IMPLEMENTED
**Location:** `views/tab4_pdf_comparison.py`
- **`SingleTranscriptionPDFCompareView`:** POST - Compare transcription to PDF
- **`SingleTranscriptionPDFResultView`:** GET - Get comparison results
- **`SingleTranscriptionPDFStatusView`:** GET - Poll comparison progress
- **`SingleTranscriptionSideBySideView`:** GET - Diff with matched/unmatched blocks
- **`SingleTranscriptionRetryComparisonView`:** POST - Retry with custom settings
- **Features:**
  - TF-IDF + cosine similarity for matching
  - Match percentage (0-100%)
  - Validation status (excellent/good/acceptable/poor)
  - Side-by-side diff generation
  - Custom settings (threshold, page range)
  - Results stored on Transcription model

##### **Legacy Views** 🔄 (Maintained for Compatibility)
- **`ProjectListCreateView`:** Create/list projects
- **`ProjectDetailView`:** Get/update project details
- **`ProjectPDFUploadView`:** Handle PDF uploads
- **`ProjectAudioUploadVie- **Tab-Based Architecture** ✅ NEW

##### **Task Organization**
**Location:** `audioDiagnostic/tasks/`
- `transcription_tasks.py` - Audio transcription
- `duplicate_tasks.py` - Duplicate detection and deletion
- `pdf_comparison_tasks.py` - PDF validation
- `audio_processing_tasks.py` - Audio generation utilities

##### **`transcribe_single_audio_file_task()`** ✅ NEW
**Location:** `tasks/transcription_tasks.py`
- **Purpose:** Transcribe ONE audio file (not batch)
- **Process:**
  1. Auto-start Docker/Celery infrastructure
  2. Load audio file
  3. Run OpenAI Whisper with word_timestamps=True
  4. Create Transcription record (OneToOne with AudioFile)
  5. Save TranscriptionSegment records with timestamps
  6. Save TranscriptionWord records for precise playback
  7. Update audio file status to 'transcribed'
  8. Progress tracking: 10% → 20% → 30% → 70% → 100%
- **Infrastructure:** Manages Docker containers automatically
- **Error Handling:** Updates status to 'failed' with error message

##### **`detect_duplicates_single_file_task()`** ✅ NEW
**Location:** `tasks/duplicate_tasks.py`
- **Purpose:** Detect duplicates within ONE audio file only
- **Process:**
  1. Load transcription segments for this file
  2. Normalize text (lowercase, remove punctuation)
  3. TF-IDF vectorization with n-grams (1-3)
  4. Calculate cosine similarity matrix
  5. Find duplicates (similarity ≥ 0.85)
  6. Group identical segments
  7. Create DuplicateGroup records
  8. Mark segments: Keep LAST occurrence, suggest deleting others
  9. Link segments via duplicate_group_id
  10. Return for user review
- **Note:** Does NOT automatically delete - awaits user confirmation

##### **`process_deletions_single_file_task()`** ✅ NEW
**Location:** `tasks/duplicate_tasks.py`
- **Purpose:** Generate clean audio after user confirms deletions
- **Process:**
  1. Receive list of confirmed segment IDs to delete
  2. Update is_kept=False for confirmed segments
  3. Load original audio file
  4. Extract kept segments (is_kept=True) in order
  5. Concatenate segments with pydub
  6. Export as clean audio (WAV format)
  7. Save to AudioFile.processed_audio field
  8. Update status to 'processed'
  9. Calculate statistics (duration saved, segments removed)
- **Progress:** 10% → 30% → 50% → 70% → 100%

##### **`compare_transcription_to_pdf_task()`** ✅ NEW
**Location:** `tasks/pdf_comparison_tasks.py`
- **Purpose:** Compare transcription against project PDF
- **Process:**
  1. Load project PDF and extract text (via PyMuPDF)
  2. Load transcription text
  3. Normalize both texts
  4. TF-IDF vectorization with n-grams (1-3)
  5. Calculate cosine similarity
  6. Determine match percentage (0-100%)
  7. Generate validation status:
     - ≥90%: excellent
     - 80-89%: good
     - 70-79%: acceptable
     - <70%: poor
  8. Create side-by-side diff using SequenceMatcher
  9. Identify matched/unmatched blocks
  10. Save results to Transcription model
  11. Store detailed analysis as JSON
- **Custom Settings:** Similarity threshold, PDF page range
- **Progress:** 10% → 30% → 50% → 70% → 90% → 100%

##### **`batch_compare_transcriptions_to_pdf_task()`** ✅ NEW
**Location:** `tasks/pdf_comparison_tasks.py`
- **Purpose:** Compare multiple transcriptions in batch
- **Process:** Loops through files, calls compare_transcription_to_pdf_task for each

##### **Legacy Tasks** 🔄 (Maintained for Compatibility)
- **`transcribe_audio_file_task()`** - Batch transcription (all files together)
- **`process_project_duplicates_task()`** - Batch duplicate detection
- **`process_audio_file_task()`** - Legacy automatic processing
##### **Project Management Views**
- **`ProjectListCreateView`:** Create/list projects
- **`ProjectDetailView`:** Get/update/patch project details ⭐ **Enhanced**
- **`ProjectPDFUploadView`:** Handle PDF file uploads
- **`ProjectAudioUploadView`:** Handle audio file uploads

##### **Step-by-Step Processing Views** ⭐ **New Architecture**
- **`ProjectMatchPDFView`:** Step 2a - Match audio transcript to PDF section
- **`ProjectDetectDuplicatesView`:** Step 2b - Detect duplicates with detailed analysis
- **`ProjectDuplicatesReviewView`:** Step 2c - Get duplicates for interactive review
- **`ProjectConfirmDeletionsView`:** Step 3 - Process user-confirmed deletions

##### **Legacy Processing Views** (Backward Compatible)
- **`TranscribeAudioFileView`:** Start audio transcription (Step 1)
- **`ProcessAudioFileView`:** Legacy automatic duplicate detection
- **`InfrastructureStatusView`:** Monitor Docker/Celery status

##### **Utility Views**
- **`ProjectProgressView`:** Real-time progress tracking
- **`ProjectDownloadView`:** Serve processed files

#### **Background Tasks** (`tasks.py`) ⭐ **Core Processing**

##### **`transcribe_audio_file_task()`**
- **Purpose:** Audio-to-text conversion using OpenAI Whisper
- **Process:**
  1. Auto-start Docker/Celery infrastructure
  2. Load Whisper model for speech recognition
  3. Generate timestamped transcription segments
  4. Save segments and words to database
  5. Update audio file status to 'transcribed'
- **Infrastructure:** Manages Docker containers automatically

##### **`process_confirmed_deletions_task()`** ⭐ **New Core Task**
- **Purpose:** Process user-confirmed duplicate deletions and audio reconstruction
- **Process:**
  1. Receive user-confirmed deletion list
  2. Mark confirmed segments for removal in database
  3. Generate clean audio excluding confirmed duplicates
  4. Apply smooth transitions (fade in/out)
  5. Create downloadable result file
  6. Update project status to 'completed'

##### **`process_audio_file_task()`** (Legacy - Maintained for Compatibility)
- **Purpose:** Legacy automatic duplicate detection and audio reconstruction
- **Process:**
  1. Load transcribed segments and PDF text
  2. Apply duplicate detection algorithms
  3. Generate cleaned audio without duplicates
  4. Create downloadable result file
  5. Update project status to 'completed'

#### **Service Layer** (`services/`)

##### **`docker_manager.py`** ⭐ **Infrastructure Management**
- **Purpose:** Automatic Docker and Celery lifecycle management
- **Key Methods:**
  - `setup_infrastructure()`: Start Docker containers
  - `register_task()`: Track active processing tasks
  - `unregister_task()`: Monitor task completion
  - `shutdown_infrastructure()`: Auto-shutdown after 60s idle
- **Features:**
  - Resource-efficient auto-scaling
  - Graceful shutdown management
  - Redis connectivity monitoring

### **Docker Infrastructure**

#### **`docker-compose.yml`**
- **Purpose:** Multi-container orchestration configuration
- **Services:**
  - **redis:** Message broker for Celery tasks
  - **celery_worker:** Background task processing
  - **celery_beat:** Scheduled task management
- **Networking:** Internal Docker network for service communication
- **Volumes:** Shared media storage between containers

#### **`Dockerfile`**
- **Purpose:** Container image definition for audio processing
- **Base Image:** Python 3.12-slim with audio processing libraries

#### **Tab-Based Endpoints** ✅ NEW (18 endpoints)
```
Tab 1 - File Management (3 endpoints):
  GET    /api/projects/{id}/files/                        # List all files
  POST   /api/projects/{id}/files/                        # Upload new file(s)
  GET    /api/projects/{id}/files/{file_id}/              # Get file details
  DELETE /api/projects/{id}/files/{file_id}/              # Delete file
  PATCH  /api/projects/{id}/files/{file_id}/              # Update metadata
  GET    /api/projects/{id}/files/{file_id}/status/       # Poll file status

Tab 2 - Transcription (4 endpoints):
  POST   /api/projects/{id}/files/{file_id}/transcribe/              # Start transcription
  GET    /api/projects/{id}/files/{file_id}/transcription/           # Get results
  GET    /api/projects/{id}/files/{file_id}/transcription/status/    # Poll progress
  GET    /api/projects/{id}/files/{file_id}/transcription/download/  # Export TXT/JSON

Tab 3 - Duplicate Detection (6 endpoints):
  POST   /api/projects/{id}/files/{file_id}/detect-duplicates/   # Start detection
  GET    /api/projects/{id}/files/{file_id}/duplicates/          # Review duplicates
  POST   /api/projects/{id}/files/{file_id}/confirm-deletions/   # Process deletions
  GET    /api/projects/{id}/files/{file_id}/processing-status/   # Poll processing
  GET    /api/projects/{id}/files/{file_id}/processed-audio/     # Download clean audio
  GET    /api/projects/{id}/files/{file_id}/statistics/          # Before/after stats

Tab 4 - PDF Comparison (5 endpoints):
  POST   /api/projects/{id}/files/{file_id}/compare-pdf/       # Start comparison
  GET    /api/projects/{id}/files/{file_id}/pdf-result/        # Get results
  GET    /api/projects/{id}/files/{file_id}/pdf-status/        # Poll progress
  GET    /api/projects/{id}/files/{file_id}/side-by-side/      # Diff view data
  POST   /api/projects/{id}/files/{file_id}/retry-comparison/  # Retry with settings
```

#### **Legacy Endpoints** 🔄 (Maintained for Compatibility)
```
Projects:
  GET    /api/projects/                    # List projects
  POST   /api/projects/                    # Create project
  GET    /api/projects/{id}/               # Get project details
  PATCH  /api/projects/{id}/               # Update project fields
  DELETE /api/projects/{id}/               # Delete project

File Management:
  POST   /api/projects/{id}/upload-pdf/    # Upload PDF (legacy batch upload)
  POST   /api/projects/{id}/upload-audio/  # Upload audio (legacy batch upload)

Legacy Batch Processing:
  POST   /api/projects/{id}/transcribe/            # Batch: Transcribe all files
  POST   /api/projects/{id}/match-pdf/             # Batch: Match all to PDF
  POST   /api/projects/{id}/detect-duplicates/     # Batch: Detect across all files
  GET    /api/projects/{id}/duplicates/            # Batch: Get all duplicates
  POST   /api/projects/{id}/confirm-deletions/     # Batch: Process all confirmations
  POST   /api/projects/{id}/verify-cleanup/        # Batch: Verify cleanup
  POST   /api/projects/{id}/validate-against-pdf/  # Batch: Validate all
  GET    /api/projects/{id}/validation-progress/{task_id}/  # Poll validation
  POST   /api/projects/{id}/process/               # Legacy: Auto processing
  GET    /api/projects/{id}/progress/              # Get progress status

Audio File Management (Legacy):
  GET    /api/projects/{id}/audio-files/                    # List audio files
  GET    /api/projects/{id}/audio-files/{file_id}/         # Get file details
  DELETE /api/projects/{id}/audio-files/{file_id}/         # Delete audio file
  POST   /api/projects/{id}/audio-files/{file_id}/process/ # Process individual file

Infrastructure:
  GET    /api/infrastructure/status/       # Docker/Celery status
  POST   /api/infrastructure/shutdown/     # Force shutdown

Downloads:
  GET    /api/projects/{id}/download/      # Download processed audio (legacy)
```

### **API Design Patterns**

#### **File-Centric Routing** ✅ NEW
- **Pattern:** `/api/projects/{project_id}/files/{file_id}/{action}/`
- **Philosophy:** Each audio file is processed independently
- **Benefits:**
  - Clear resource hierarchy
  - Individual file status tracking
  - Parallel processing capability
  - Simplified error handling

#### **Progress Polling Pattern** ✅ NEW
- **Endpoints:** All `*-status` endpoints
- **Polling Interval:** 2 seconds (frontend)
- **Response:**
  ```json
  {
    "success": true,
    "progress": 75,
    "message": "Processing...",
    "completed": false
  }
  ```
- **Used in:** Transcription, Duplicate Detection, PDF Comparison

### **Infrastructure Management** (Unchanged)
```
Task Registration:
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Action   │───▶│   Docker Manager │───▶│ Container Start │
└─────────────────┘    └──────────────────┘    └─────────────────┘

Task Completion:
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Task Finished  │───▶│   60s Timer      │───▶│Container Shutdown│
└─────────────────┘    └──────────────────┘    └─────────────────┘
```
  POST   /api/projects/{id}/process/               # Legacy: Auto processing
  GET    /api/projects/{id}/progress/              # Get progress status

Audio File Management (Legacy):
  GET    /api/projects/{id}/audio-files/                    # List audio files
  GET    /api/projects/{id}/audio-files/{file_id}/         # Get file details
  DELETE /api/projects/{id}/audio-files/{file_id}/         # Delete audio file
  POST   /api/projects/{id}/audio-files/{file_id}/process/ # Process individual file

Infrastructure:
  GET    /api/infrastructure/status/       # Docker/Celery status
  POST   /api/infrastructure/shutdown/     # Force shutdown

Downloads:
  GET    /api/projects/{id}/download/      # Download processed audio (legacy)
```

### **API Design Patterns**

#### **File-Centric Routing** ✅ NEW
- **Pattern:** `/api/projects/{project_id}/files/{file_id}/{action}/`
- **Philosophy:** Each audio file is processed independently
- **Benefits:**
  - Clear resource hierarchy
  - Individual file status tracking
  - Parallel processing capability
  - Simplified error handling

#### **Progress Polling Pattern** ✅ NEW
- **Endpoints:** All `*-status` endpoints
- **Polling Interval:** 2 seconds (frontend)
- **Response:**
  ```json
  {
    "success": true,
    "progress": 75,
    "message": "Processing...",
    "completed": false
  }
  ```
- **Used in:** Transcription, Duplicate Detection, PDF ComparisonDisplay side-by-side comparison → User reviews match quality
5. User confirms/rejects match → Update pdf_match_completed status

Step 2b: Duplicate Detection
1. User clicks "Detect Duplicates" → POST /api/projects/{id}/detect-duplicates/
2. Compare transcript against matched PDF section
3. Identify repeated words/sentences/paragraphs
4. Group duplicates and mark last occurrences
5. Save results → duplicates_detected field

Step 2c: Interactive Review
1. User clicks "Review Duplicates" → GET /api/projects/{id}/duplicates/
2. Display interactive interface with audio playback
3. User selects/deselects duplicates for deletion
4. User clicks "Confirm Deletions" → POST /api/projects/{id}/confirm-deletions/
5. Background task processes confirmed deletions → Generate clean audio

Step 3: Automatic Clean Audio Transcription ⭐ New
1. After generating clean audio, system automatically transcribes it
2. Saves verification segments with is_verification=True flag
3. Sets clean_audio_transcribed = True
4. Ready for verification comparison

Step 4: Post-Processing Verification ⭐ New
1. User clicks "Compare Clean Audio to PDF" → POST /api/projects/{id}/verify-cleanup/
2. System compares clean audio transcript against original PDF matched section
3. Calculates similarity score and identifies any remaining duplicates
4. Displays side-by-side comparison with statistics
5. Alerts user if repeated sentences still exist
6. Sets verification_completed = True

Step 5: Word-by-Word PDF Validation ⭐ New
1. User clicks "Test Against PDF Section" → POST /api/projects/{id}/validate-against-pdf/
2. System starts Celery background task → Returns task_id for tracking
3. Task gets clean transcript (excludes confirmed deletions)
4. Tokenizes PDF section and clean transcript into individual words
5. Sequential matching algorithm:
   - For each word in PDF, search in transcript from last matched position
   - If found: Mark GREEN in both PDF and transcript
   - If not found: Mark RED in PDF, continue searching in transcript
   - Move to next PDF word, resume from last matched transcript position
6. Generate color-coded HTML with <span> tags for highlighting
7. Calculate statistics: matched words, unmatched PDF words, unmatched transcript words
8. Save results to database → pdf_validation_results, pdf_validation_html
9. Frontend polls progress endpoint every second → Update progress bar
10. Display results with side-by-side panels, match percentage, quality warnings
11. Sets pdf_validation_completed = True
```
6. Sets verification_completed = True
```

### **Infrastructure Management**
```
Task Registration:
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   User Action   │───▶│   Docker Manager  │───▶│ Container Start  │
└─────────────────┘     └──────────────────┘     └──────────────────┘

Task Completion:
┌─────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  Task Finished  │───▶│   60s Timer       │───▶│Container Shutdown │
└─────────────────┘     └──────────────────┘     └───────────────────┘
```

---

## 🔌 **API Architecture**

### **RESTful Endpoints**
```
Projects:
  GET    /api/projects/                    # List projects
  POST   /api/projects/                    # Create project
  GET    /api/projects/{id}/               # Get project details
  PATCH  /api/projects/{id}/               # Update project fields ⭐ New
  DELETE /api/projects/{id}/               # Delete project

File Management:
  POST   /api/projects/{id}/upload-pdf/    # Upload PDF
  POST   /api/projects/{id}/upload-audio/  # Upload audio

Step-by-Step Processing (New Interactive Workflow): ⭐ New
  POST   /api/projects/{id}/match-pdf/                      # Step 2a: Match PDF section
  POST   /api/projects/{id}/detect-duplicates/             # Step 2b: Detect duplicates
  GET    /api/projects/{id}/duplicates/                    # Step 2c: Get review data
  POST   /api/projects/{id}/confirm-deletions/             # Step 3: Process confirmations
  POST   /api/projects/{id}/verify-cleanup/                # Step 4: Verify clean audio ⭐ New
  POST   /api/projects/{id}/validate-against-pdf/          # Step 5: Start PDF validation ⭐ New
  GET    /api/projects/{id}/validation-progress/{task_id}/ # Step 5: Check validation progress ⭐ New

Legacy Processing (Backward Compatible):
  POST   /api/projects/{id}/transcribe/    # Step 1: Start transcription
  POST   /api/projects/{id}/process/       # Legacy: Auto duplicate detection
  GET    /api/projects/{id}/progress/      # Get progress status

Audio File Management: ⭐ Enhanced
  GET    /api/projects/{id}/audio-files/                    # List audio files
  GET    /api/projects/{id}/audio-files/{file_id}/         # Get file details
  DELETE /api/projects/{id}/audio-files/{file_id}/         # Delete audio file
  POST   /api/projects/{id}/audio-files/{file_id}/process/ # Process individual file

Infrastructure:
  GET    /api/infrastructure/status/       # Docker/Celery status
  POST   /api/infrastructure/shutdown/     # Force shutdown

Downloads:
  GET    /api/projects/{id}/download/      # Download processed audio
```

### **WebSocket Architecture** (Future Enhancement)
```
Real-time Updates:
  ws://localhost:8000/ws/project/{id}/     # Live progress updates
  ws://localhost:8000/ws/infrastructure/   # Infrastructure monitoring
```

---

## 📊 **Database Schema**

### **Relationships** ✅ UPDATED
```
User (Django Auth)
  │
  └── AudioProject (One per book/document)
        │
        ├── pdf_file (FileField)
        │
        └── AudioFile (Multiple files per project) ✅ ENHANCED
              │
              ├── audio_file (FileField) - original upload
              ├── processed_audio (FileField) - clean version ✅ NEW
              │
              ├──→ Transcription (OneToOne) ✅ NEW
              │      │
              │      └── TranscriptionSegment (Many) ✅ UPDATED
              │            │
              │            └── TranscriptionWord (Many)
              │
              └──→ DuplicateGroup (Many) ✅ NEW
                     Links to TranscriptionSegments via duplicate_group_id
```

### **Status State Machine** ✅ UPDATED
```
AudioFile Status Flow (Tab-Based Architecture):
uploaded → processing → transcribed → processing → processed → failed
   │          ↓              ↓             ↓            ↓
   │      (transcribing) (detecting)  (generating)  (comparing)
   │                                                      │
   └── failed ←─────────────────────────────────────────┘

Status Badges in UI:
- uploaded: Blue badge "📁 Ready"
- processing: Yellow badge "⏳ Processing..."
- transcribed: Green badge "✅ Transcribed"
- processed: Purple badge "✨ Processed"
- failed: Red badge "❌ Failed"

Project Status Flow (Legacy):
setup → ready → processing → completed
  │                             │
  └── error ←───────────────────┘
```

---

## 🔧 **Development Workflow**

### **Local Development Setup**
1. **Backend:** `python manage.py runserver` (Port 8000)
2. **Frontend:** `npm start` (Port 3000) 
3. **Docker:** Auto-started on first transcription task
4. **Database:** SQLite for development, automatic migrations

### **Recent Major Changes** ✅ NEW (December 2025)
1. **Migration 0012:** Added Transcription, DuplicateGroup models
2. **View Refactoring:** Split into 4 tab-specific view files
3. **Task Refactoring:** Individual file processing tasks created
4. **Frontend Rebuild:** ProjectDetailPageNew with tab architecture
5. **Context API:** ProjectTabContext for cross-tab state management
6. **URL Routing:** 18 new API endpoints for tab-based workflow

### **Development Priority Queue**
1. ✅ **Backend:** 100% Complete (All APIs, models, tasks)
2. ✅ **Tab 1 (Upload & Transcribe):** 100% Complete (Merged workflow)
3. ✅ **Tab 3 (Duplicates):** 95% Complete (Detection, review, confirmation)
4. ✅ **Tab 4 (Results):** 100% Complete (Playback, statistics, download) ✅ NEW
5. ⏳ **Tab 4 (Compare PDF):** 10% Complete (Stub exists, needs side-by-side UI)
6. 🔮 **Future:** Real-time WebSocket updates, batch operations

### **File Structure Summary**
```
Audio repetative detection/
├── frontend/audio-waveform-visualizer/         # React App
│   ├── src/
│   │   ├── screens/
│   │   │   ├── ProjectDetailPageNew.js         # ✅ NEW Tab-based main page
│   │   │   └── ProjectDetailPage.js            # 🔄 Legacy single-page
│   │   ├── components/
│   │   │   ├── ProjectTabs/                    # ✅ NEW Tab components
│   │   │   │   ├── ProjectTabs.js              # Navigation
│   │   │   │   ├── Tab1Files.js                # ✅ Upload & transcribe (complete)
│   │   │   │   ├── Tab3Duplicates.js           # ✅ Duplicates (complete)
│   │   │   │   ├── Tab4Results.js              # ✅ Processed audio (NEW)
│   │   │   │   └── Tab4ComparePDF.js           # ⏳ PDF compare (stub)
│   │   │   ├── FileUpload.js                   # 🔄 Legacy component
│   │   │   ├── ProgressTracker.js              # 🔄 Legacy component
│   │   │   └── AudioPlayer.js                  # 🔄 Legacy component
│   │   └── contexts/
│   │       └── ProjectTabContext.js            # ✅ NEW Shared state
│   └── public/                                 # Static assets
├── backend/                                    # Django API
│   ├── audioDiagnostic/                        # Main app
│   │   ├── models.py                           # ✅ UPDATED (Migration 0012)
│   │   ├── serializers.py                      # ✅ NEW Tab-based serializers
│   │   ├── urls.py                             # ✅ UPDATED (18 new routes)
│   │   ├── views/                              # ✅ NEW Organized by tab
│   │   │   ├── tab1_file_management.py         # 3 views
│   │   │   ├── tab2_transcription.py           # 4 views
│   │   │   ├── tab3_duplicate_detection.py     # 6 views
│   │   │   └── tab4_pdf_comparison.py          # 5 views
│   │   ├── tasks/                              # ✅ NEW Organized tasks
│   │   │   ├── transcription_tasks.py          # Single-file transcription
│   │   │   ├── duplicate_tasks.py              # Detection & deletion
│   │   │   └── pdf_comparison_tasks.py         # PDF validation
│   │   └── services/
│   │       └── docker_manager.py               # Infrastructure
│   ├── myproject/
│   │   └── settings.py                         # Configuration
│   ├── docker-compose.yml                      # Container setup
│   └── requirements.txt                        # Dependencies
├── docs/
│   ├── architecture/
│   │   ├── AI_CODING_PROMPT.md                 # ✅ UPDATED Architecture guide
│   │   └── ARCHITECTURE.md                     # ✅ UPDATED This file
│   ├── IMPLEMENTATION_STATUS.md                # ✅ NEW Detailed status
│   └── TAB_ARCHITECTURE_VISUAL.md              # ✅ NEW Visual guide
├── start-dev.bat                               # Development launcher
└── docker-diagnostic.bat                       # Setup troubleshooting
```

### **Key Design Decisions**

#### **Why Tab-Based Architecture?** ✅
- **Better UX:** Users process files one at a time, not in bulk
- **Clearer Flow:** Upload → Transcribe → Detect → Compare (step-by-step)
- **Easier Debugging:** Issues isolated to individual files
- **Scalability:** Can process files in parallel later
- **Flexibility:** Users choose which files to transcribe/process

#### **Why OneToOne Relationship (AudioFile ↔ Transcription)?** ✅
- **Clarity:** Each audio file has exactly one transcription
- **Performance:** Faster queries (no joins needed)
- **Data Integrity:** Can't accidentally link wrong transcriptions
- **UI Simplicity:** File status badges show transcription state directly

#### **Why Context API (Not Redux)?** ✅
- **Simplicity:** Built into React, no extra dependencies
- **Sufficient:** Only 4 tabs need shared state
- **Performance:** Updates only re-render subscribed components
- **Maintainability:** Less boilerplate than Redux

#### **Why Keep Legacy Code?** 🔄
- **Safety:** Users may have projects in old workflow
- **Migration Path:** Can switch between old/new UI
- **Testing:** Compare new architecture against known working baseline
- **Rollback:** If new architecture has issues

---

## 📚 **Additional Documentation**

### **For Detailed Implementation:**
- [AI_CODING_PROMPT.md](AI_CODING_PROMPT.md) - Complete architecture guide with examples
- [IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md) - Line-by-line completion checklist
- [TAB_ARCHITECTURE_VISUAL.md](../TAB_ARCHITECTURE_VISUAL.md) - Visual diagrams and flows

### **For Setup and Troubleshooting:**
- [QUICK_START_WORKING.md](../setup-guides/QUICK_START_WORKING.md) - Setup guide
- [START_HERE.md](../setup-guides/START_HERE.md) - Getting started
- [FFMPEG_FIX.md](../troubleshooting/FFMPEG_FIX.md) - Audio processing issues

---

This architecture provides **scalable, maintainable, and production-ready** audio duplicate detection with:
- ✅ Individual file processing (not batch)
- ✅ Clear visual linkage between files and transcriptions
- ✅ Cross-tab state management
- ✅ Real-time progress tracking
- ✅ Modern React patterns (hooks, context, functional components)
- ✅ RESTful API design with clear resource hierarchy