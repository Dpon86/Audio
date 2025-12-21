# Refactoring to Tab-Based UI - Analysis & Implementation Plan

## 📋 Current State Analysis

### What Exists Now
The current application has a **single-page workflow** in `ProjectDetailPage.js` that:
- Processes multiple audio files together as a batch
- Shows all steps on one scrolling page
- Combines all audio files into one final output
- Processes duplicates across ALL audio files simultaneously
- Designed for "record the whole book in one go" workflow

### What We Need
A **tab-based interface** where:
- Each audio file is processed **independently**
- Users can work on one file at a time
- Tab 1 serves as central file management hub
- Tabs 2-4 operate on single files selected from Tab 1
- Better for "record chapter by chapter" workflow

---

## 🔍 Gap Analysis

### Backend Changes Needed

#### ✅ Already Have (Can Reuse)
- `AudioProject` model - basic structure exists
- `AudioFile` model - supports multiple files per project
- `TranscriptionSegment` model - has word-level timestamps
- `TranscriptionWord` model - detailed word data
- File upload functionality
- Transcription with Whisper
- Duplicate detection algorithms
- PDF comparison logic

#### ❌ Missing or Needs Changes

1. **Model Relationships**
   - Current: AudioFile transcripts stored in `transcript_text` field (flat)
   - Need: Separate `Transcription` model with one-to-one relationship
   - Need: Link processed audio back to original AudioFile

2. **API Endpoints**
   - Current: Endpoints process ALL files in project at once
   - Need: Single-file transcription endpoint
   - Need: Single-file duplicate detection endpoint  
   - Need: Single-file processed audio generation endpoint

3. **Status Management**
   - Current: Project-level status only
   - Need: Per-file status tracking (uploaded → transcribing → transcribed → processing → processed)

4. **Duplicate Detection Scope**
   - Current: Finds duplicates across ALL audio files
   - Need: Find duplicates within ONE audio file only

### Frontend Changes Needed

#### ✅ Already Have (Can Reuse)
- ProjectDetailPage.js component structure
- Audio upload components
- PDF upload components
- Audio playback functionality
- Transcription display
- Duplicate review components
- PDF comparison UI

#### ❌ Missing or Needs Complete Refactor

1. **Tab Navigation System**
   - Need: Tab navigation component (4 tabs)
   - Need: Tab content routing/switching
   - Need: Active tab state management
   - Need: Cross-tab communication (passing selected files)

2. **Tab 1: File Management Hub**
   - Need: Complete new component
   - Need: Audio file list with status badges
   - Need: File selection mechanism for other tabs
   - Need: Quick action buttons (navigate to Tab 2/3/4 with pre-selection)

3. **Tab 2: Transcription Interface**
   - Need: File selector dropdown (only uploaded files)
   - Need: Single-file transcription trigger
   - Need: Transcription progress display
   - Need: Results display with return to Tab 1

4. **Tab 3: Duplicate Detection Interface**
   - Need: File selector dropdown (only transcribed files)
   - Need: Single-file duplicate detection
   - Need: Modified duplicate review (single file context)
   - Need: Generate clean audio for THIS file only

5. **Tab 4: PDF Comparison Interface**
   - Can mostly reuse existing comparison UI
   - Need: Transcription selector dropdown
   - Need: Results scoped to single transcription

6. **State Management**
   - Need: Context for shared file list state
   - Need: Context for current tab state
   - Need: Context for selected file across tabs

---

## 📝 Detailed Implementation TODO List

### Phase 1: Backend Foundation (Database & Models)

#### Task 1.1: Create New Transcription Model
**File:** `backend/audioDiagnostic/models.py`
```python
class Transcription(models.Model):
    audio_file = models.OneToOneField(AudioFile, on_delete=models.CASCADE, related_name='transcription')
    full_text = models.TextField()
    word_count = models.IntegerField()
    confidence_score = models.FloatField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # PDF matching results (from Tab 4)
    matched_pdf_section = models.TextField(null=True, blank=True)
    pdf_start_page = models.IntegerField(null=True)
    pdf_end_page = models.IntegerField(null=True)
    pdf_match_percentage = models.FloatField(null=True)
```

#### Task 1.2: Update AudioFile Model
**File:** `backend/audioDiagnostic/models.py`
- Add `processed_audio` field (FileField for clean audio after duplicate removal)
- Add `duration_seconds` field (FloatField)
- Add `file_size_bytes` field (BigIntegerField)
- Add `format` field (CharField - mp3, wav, etc.)
- Update status choices to match tab workflow

#### Task 1.3: Update TranscriptionSegment Model
**File:** `backend/audioDiagnostic/models.py`
- Change `audio_file` foreign key to `transcription`
- Update `duplicate_group_id` logic for single-file context
- Ensure `is_last_occurrence` works within single file

#### Task 1.4: Create DuplicateGroup Model
**File:** `backend/audioDiagnostic/models.py`
```python
class DuplicateGroup(models.Model):
    audio_file = models.ForeignKey(AudioFile, on_delete=models.CASCADE)
    group_id = models.CharField(max_length=100)
    duplicate_text = models.TextField()
    occurrence_count = models.IntegerField()
    total_duration_seconds = models.FloatField()
```

#### Task 1.5: Create and Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

---

### Phase 2: Backend API Development

#### Task 2.1: Tab 1 - File Management APIs
**Files:** `backend/audioDiagnostic/views.py`, `urls.py`

Create endpoints:
- `GET /api/projects/{id}/audio-files/` - List all audio files with status
- `POST /api/projects/{id}/audio-files/` - Upload new audio file
- `DELETE /api/projects/{id}/audio-files/{audio_id}/` - Delete audio file
- `GET /api/projects/{id}/audio-files/{audio_id}/` - Get single file details

Response format:
```json
{
  "id": 1,
  "filename": "chapter1.mp3",
  "duration_seconds": 1234.5,
  "status": "transcribed",
  "has_transcription": true,
  "has_processed_audio": false,
  "upload_order": 1,
  "transcription_id": 5
}
```

#### Task 2.2: Tab 2 - Transcription APIs
**Files:** `backend/audioDiagnostic/views.py`, `tasks.py`

Create endpoints:
- `POST /api/audio-files/{id}/transcribe/` - Transcribe single file
- `GET /api/audio-files/{id}/transcription/` - Get transcription results
- `GET /api/audio-files/{id}/transcription/status/` - Check transcription progress

Update `transcribe_audio_task`:
- Process ONE audio file only
- Create Transcription object
- Create TranscriptionSegment objects
- Update AudioFile status

#### Task 2.3: Tab 3 - Duplicate Detection APIs
**Files:** `backend/audioDiagnostic/views.py`, `tasks.py`

Create endpoints:
- `POST /api/audio-files/{id}/detect-duplicates/` - Detect in single file
- `GET /api/audio-files/{id}/duplicates/` - Get duplicate groups
- `POST /api/audio-files/{id}/confirm-deletions/` - Process deletions for this file
- `GET /api/audio-files/{id}/processed-audio/` - Download clean audio

Update duplicate detection logic:
- Analyze segments from ONE audio file only
- Group duplicates within that file
- Mark last occurrence in that file
- Generate processed audio for that file only

#### Task 2.4: Tab 4 - PDF Comparison APIs
**Files:** `backend/audioDiagnostic/views.py`

Create endpoints:
- `POST /api/transcriptions/{id}/compare-pdf/` - Compare single transcription to PDF
- `GET /api/transcriptions/{id}/pdf-match/` - Get comparison results

Update PDF matching logic:
- Accept transcription ID (not project ID)
- Compare one transcription at a time
- Store results on Transcription model

---

### Phase 3: Frontend Tab Structure

#### Task 3.1: Create Tab Navigation Component
**File:** `frontend/src/components/Layout/ProjectTabs.js`

```jsx
const ProjectTabs = ({ projectId, activeTab, onTabChange }) => {
  const tabs = [
    { id: 'files', label: 'Files & Uploads', icon: '📁' },
    { id: 'transcribe', label: 'Transcribe', icon: '🎤' },
    { id: 'duplicates', label: 'Detect Duplicates', icon: '🔍' },
    { id: 'compare', label: 'Compare to PDF', icon: '📄' }
  ];
  
  return (
    <div className="project-tabs">
      {tabs.map(tab => (
        <button 
          key={tab.id}
          className={`tab ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onTabChange(tab.id)}
        >
          {tab.icon} {tab.label}
        </button>
      ))}
    </div>
  );
};
```

#### Task 3.2: Refactor ProjectDetailPage
**File:** `frontend/src/screens/ProjectDetailPage.js`

- Add tab state: `const [activeTab, setActiveTab] = useState('files')`
- Render tab navigation
- Conditionally render tab content based on activeTab
- Remove single-page workflow steps

---

### Phase 4: Tab 1 - File Management Hub

#### Task 4.1: Create FileManagementTab Component
**File:** `frontend/src/components/Tab1_FileManagement/FileManagementTab.js`

Components to create:
- PDFUpload.js - PDF upload section
- AudioUpload.js - Multi-file audio upload with drag-drop
- AudioFileList.js - Table/list of all audio files
- FileStatusBadge.js - Visual status indicators
- QuickActions.js - Navigate to other tabs with file pre-selected

Features:
- Upload multiple audio files
- Display all files with metadata (name, duration, size, format)
- Show status badges (uploaded, transcribing, transcribed, processing, processed)
- Delete file action
- Click to navigate to Tab 2 with file pre-selected
- Click to navigate to Tab 3 with file pre-selected

---

### Phase 5: Tab 2 - Transcription Interface

#### Task 5.1: Create TranscriptionTab Component
**File:** `frontend/src/components/Tab2_Transcription/TranscriptionTab.js`

Components:
- FileSelector.js - Dropdown to select audio file
- AudioPreview.js - Preview selected file with basic player
- TranscriptionProgress.js - Real-time progress bar
- TranscriptDisplay.js - Show results with timestamps
- TranscriptDownload.js - Export as TXT/JSON

Workflow:
1. Select audio file from dropdown (only uploaded or transcribed files)
2. Show file details and preview player
3. Click "Transcribe Audio" button
4. Show progress bar with status updates
5. Display transcription results
6. Provide download options
7. Auto-update Tab 1 status
8. Show "Return to Files" button

---

### Phase 6: Tab 3 - Duplicate Detection Interface

#### Task 6.1: Create DuplicateDetectionTab Component
**File:** `frontend/src/components/Tab3_DuplicateDetection/DuplicateDetectionTab.js`

Components:
- TranscribedFileSelector.js - Dropdown (only transcribed files)
- DuplicateDetectionProgress.js - Progress during detection
- DuplicateReviewList.js - List all duplicate groups
- DuplicateGroupCard.js - Individual duplicate display
- SegmentAudioPlayer.js - Play specific segments
- DeletionConfirmation.js - Review before processing
- ProcessingResults.js - Show before/after stats

Workflow:
1. Select transcribed audio file
2. Click "Detect Duplicates"
3. Show progress
4. Display duplicate groups with audio playback
5. Pre-select all except last occurrence
6. User reviews and modifies selections
7. Click "Generate Clean Audio"
8. Show processing progress
9. Display results and download link
10. Update Tab 1 with processed audio

---

### Phase 7: Tab 4 - PDF Comparison Interface

#### Task 7.1: Create PDFComparisonTab Component
**File:** `frontend/src/components/Tab4_PDFComparison/PDFComparisonTab.js`

Components:
- TranscriptionSelector.js - Select transcription to compare
- ComparisonProgress.js - Progress during analysis
- ComparisonView.js - Side-by-side display
- PDFPanel.js - Left panel with PDF content
- TranscriptPanel.js - Right panel with transcription
- MatchStatistics.js - Percentage and metrics
- LocationInfo.js - PDF page/chapter info
- ComparisonReport.js - Detailed analysis

Workflow:
1. Select transcription (original or processed)
2. Click "Compare to PDF"
3. Show progress
4. Display side-by-side comparison
5. Show match percentage and statistics
6. Display location in PDF
7. Show missing content report
8. Provide export report option

---

### Phase 8: State Management & Context

#### Task 8.1: Create FileManagementContext
**File:** `frontend/src/contexts/FileManagementContext.js`

Manage:
- List of audio files
- Selected file for other tabs
- Refresh file list function
- File status updates

#### Task 8.2: Create TabNavigationContext
**File:** `frontend/src/contexts/TabNavigationContext.js`

Manage:
- Active tab state
- Navigate to tab with pre-selected file
- Tab completion tracking

---

### Phase 9: Shared Components

#### Task 9.1: Create Reusable Components
**Directory:** `frontend/src/components/Shared/`

Components:
- AudioPlayer.js - Configurable audio player
- ProgressBar.js - Progress indicator
- StatusBadge.js - File status indicators
- FileSelector.js - Reusable dropdown
- ErrorDisplay.js - Error messages
- LoadingSpinner.js - Loading states

---

### Phase 10: Testing & Refinement

#### Task 10.1: Backend Testing
- Test single-file transcription
- Test single-file duplicate detection
- Test PDF comparison for single transcription
- Test file upload/delete operations

#### Task 10.2: Frontend Testing
- Test tab navigation
- Test file selection across tabs
- Test upload functionality
- Test each tab's workflow independently
- Test state synchronization between tabs

#### Task 10.3: Integration Testing
- End-to-end: Upload → Transcribe → Detect → Compare
- Test multiple files processed independently
- Test error handling at each step
- Test progress indicators

#### Task 10.4: UI/UX Polish
- Add loading states
- Add empty states (no files uploaded yet)
- Add helpful tooltips and hints
- Add keyboard navigation
- Ensure mobile responsiveness

---

## 🚀 Implementation Order (Priority)

### Week 1: Backend Foundation
1. Update models (Tasks 1.1-1.4)
2. Run migrations (Task 1.5)
3. Create Tab 1 APIs (Task 2.1)
4. Create Tab 2 APIs (Task 2.2)

### Week 2: Backend Completion
5. Create Tab 3 APIs (Task 2.3)
6. Create Tab 4 APIs (Task 2.4)
7. Test all APIs with Postman/curl

### Week 3: Frontend Structure
8. Create tab navigation (Task 3.1)
9. Refactor ProjectDetailPage (Task 3.2)
10. Create Tab 1 UI (Task 4.1)
11. Create context providers (Tasks 8.1-8.2)

### Week 4: Tab Interfaces
12. Create Tab 2 UI (Task 5.1)
13. Create Tab 3 UI (Task 6.1)
14. Create Tab 4 UI (Task 7.1)
15. Create shared components (Task 9.1)

### Week 5: Testing & Polish
16. Backend testing (Task 10.1)
17. Frontend testing (Task 10.2)
18. Integration testing (Task 10.3)
19. UI/UX polish (Task 10.4)
20. Documentation updates

---

## 📊 Estimated Effort

| Phase | Tasks | Estimated Hours |
|-------|-------|----------------|
| Backend Models | 5 tasks | 8-12 hours |
| Backend APIs | 10 endpoints | 16-24 hours |
| Frontend Structure | 4 tasks | 8-12 hours |
| Tab 1 UI | 6 components | 12-16 hours |
| Tab 2 UI | 5 components | 10-14 hours |
| Tab 3 UI | 8 components | 16-20 hours |
| Tab 4 UI | 8 components | 12-16 hours |
| State Management | 2 contexts | 4-6 hours |
| Shared Components | 6 components | 8-12 hours |
| Testing & Polish | All | 16-24 hours |
| **TOTAL** | | **110-156 hours** |

---

## ⚠️ Breaking Changes & Migration

### Data Migration
- Existing projects have transcripts in flat `transcript_text` field
- Need migration script to create Transcription objects from existing data
- Need to preserve existing duplicate detection results

### API Compatibility
- Old endpoints will still work for existing projects
- New tab-based UI uses new endpoints
- Consider versioning: `/api/v2/audio-files/...`

---

## 🎯 Success Criteria

✅ Each audio file can be processed independently  
✅ Tab 1 shows all files with accurate status  
✅ Tab 2 can transcribe one file at a time  
✅ Tab 3 detects duplicates within single file  
✅ Tab 4 compares single transcription to PDF  
✅ State syncs properly across tabs  
✅ No loss of existing functionality  
✅ Mobile-responsive tab interface  
✅ Clear error messages and loading states  
✅ Performance: Each tab loads in <1 second  

---

## 📚 Additional Documentation Needed

1. API documentation for new endpoints
2. Component documentation for new React components
3. User guide for new tab-based workflow
4. Migration guide for existing projects
5. Developer setup guide for new structure
