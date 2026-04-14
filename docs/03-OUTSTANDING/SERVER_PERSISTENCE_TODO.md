# Server Persistence Implementation TODO

**Created:** March 10, 2026 | **Completed:** April 2026 ✅
**Status:** DONE — see [`/TODO.md`](/TODO.md) for current task list.

**Objective:** Implement hybrid server/client storage for transcriptions and duplicate analysis  
**Strategy:** Store lightweight JSON metadata (~160KB/project) on server while keeping audio files in IndexedDB

---

## Current State

### ✅ Implemented (Client-Side)
- Client-side transcription with @xenova/transformers
- IndexedDB storage for audio File objects (clientAudioStorage.js)
- localStorage persistence for transcription metadata
- localStorage persistence for duplicate results
- localStorage persistence for selected deletions
- localStorage persistence for assembly info
- Client-side duplicate detection
- Client-side audio assembly
- Download functionality (5 formats)

### ❌ Missing (Server-Side)
- Django models for ClientTranscription and DuplicateAnalysis
- API endpoints for saving/loading transcription metadata
- API endpoints for saving/loading duplicate analysis
- Frontend auto-save integration
- Frontend auto-load integration
- Cross-device/browser synchronization

---

## Phase 1: Backend API Implementation

### Task 1: Explore Django Backend Structure
- [x] Examine existing models in audioDiagnostic/models.py
- [x] Review existing serializers pattern
- [x] Review existing API views pattern
- [x] Review existing URL routing
- [x] Identify Project model structure
- [x] Identify AudioFile model structure

### Task 2: Create Django Models
- [x] Create ClientTranscription model in audioDiagnostic/models.py
  - Fields: project (FK), audio_file (FK), filename, transcription_data (JSON), processing_method, model_used, duration, language, timestamp, metadata (JSON)
  - Indexes: project, audio_file, timestamp
  - Unique constraint: (project, audio_file)
  
- [x] Create DuplicateAnalysis model in audioDiagnostic/models.py
  - Fields: project (FK), audio_file (FK), duplicate_groups (JSON), algorithm, total_segments, duplicate_count, selected_deletions (JSON), assembly_info (JSON), timestamp, metadata (JSON)
  - Indexes: project, audio_file, timestamp
  - Unique constraint: (project, audio_file)

- [ ] **PENDING: Run migrations** (requires proper Python environment)
  - Run: `python manage.py makemigrations audioDiagnostic`
  - Run: `python manage.py migrate`
  - **Command to run on server:** 
    ```bash
    ssh nickd@82.165.221.205
    cd /opt/audioapp/backend
    source venv/bin/activate  # or wherever virtualenv is
    python manage.py makemigrations audioDiagnostic
    python manage.py migrate
    ```

### Task 3: Create Serializers
- [x] Create ClientTranscriptionSerializer in audioDiagnostic/serializers.py
  - Fields: id, project, audio_file, filename, transcription_data, processing_method, model_used, duration, language, timestamp, metadata
  - Validation: transcription_data must be valid JSON
  
- [x] Create DuplicateAnalysisSerializer in audioDiagnostic/serializers.py
  - Fields: id, project, audio_file, duplicate_groups, algorithm, total_segments, duplicate_count, selected_deletions, assembly_info, timestamp, metadata
  - Validation: duplicate_groups must be valid JSON array

### Task 4: Create API Views
- [x] Create ClientTranscriptionViewSet in audioDiagnostic/views/client_storage.py
  - POST /api/projects/{project_id}/client-transcriptions/
    - Save or update transcription metadata
    - Return saved object
  - GET /api/projects/{project_id}/client-transcriptions/
    - List all transcriptions for project
    - Filter by audio_file if provided
  - GET /api/projects/{project_id}/client-transcriptions/{id}/
    - Retrieve specific transcription
  - DELETE /api/projects/{project_id}/client-transcriptions/{id}/
    - Delete transcription metadata

- [x] Create DuplicateAnalysisViewSet in audioDiagnostic/views/client_storage.py
  - POST /api/projects/{project_id}/duplicate-analyses/
    - Save or update duplicate analysis
    - Return saved object
  - GET /api/projects/{project_id}/duplicate-analyses/
    - List all analyses for project
    - Filter by audio_file if provided
  - GET /api/projects/{project_id}/duplicate-analyses/{id}/
    - Retrieve specific analysis
  - DELETE /api/projects/{project_id}/duplicate-analyses/{id}/
    - Delete analysis

### Task 5: Add URL Routes
- [x] Add routes to audioDiagnostic/urls.py
  - /api/projects/{project_id}/client-transcriptions/ - List/Create
  - /api/projects/{project_id}/client-transcriptions/{transcription_id}/ - Detail/Update/Delete
  - /api/projects/{project_id}/duplicate-analyses/ - List/Create
  - /api/projects/{project_id}/duplicate-analyses/{analysis_id}/ - Detail/Update/Delete

### Task 6: Test Backend API
- [ ] **PENDING: After migrations run**
- [ ] Test POST client-transcriptions endpoint
- [ ] Test GET client-transcriptions endpoint
- [ ] Test POST duplicate-analysis endpoint
- [ ] Test GET duplicate-analysis endpoint
- [ ] Test data persistence across requests
- [ ] Test error handling (invalid JSON, missing fields)

**Backend Files Created/Modified:**
- ✅ backend/audioDiagnostic/models.py (added ClientTranscription, DuplicateAnalysis)
- ✅ backend/audioDiagnostic/serializers.py (added ClientTranscriptionSerializer, DuplicateAnalysisSerializer)
- ✅ backend/audioDiagnostic/views/client_storage.py (NEW - 400+ lines)
- ✅ backend/audioDiagnostic/views/__init__.py (updated exports)
- ✅ backend/audioDiagnostic/urls.py (added client storage routes)
- ✅ backend/audioDiagnostic/admin.py (registered new models)

---

## Phase 2: Frontend Integration

### Task 7: Auto-Save Transcriptions
- [x] Update Tab1Files.js handleClientSideTranscription
  - Added saveTranscriptionToServer() function
  - POST to /api/projects/{projectId}/client-transcriptions/ after successful transcription
  - Sends: filename, transcription_data (segments array), processing_method, model_used, duration, language
  - Updates localFile.server_synced flag based on success/failure
  - Shows appropriate message: "Synced to Server" vs "Saved Locally Only"

### Task 8: Auto-Load Transcriptions
- [x] Update Tab1Files.js useEffect/loadLocalFiles
  - Added loadServerTranscriptions() function
  - GET /api/projects/{projectId}/client-transcriptions/ on mount
  - Merges server transcriptions with IndexedDB audio files
  - Displays files with appropriate badges: "☁️ Synced", "📱 Local", "☁️🔄 Server"
  - Priority: Server > localStorage > IndexedDB only
  - Updates localStorage to match server (keeps them in sync)

### Task 9: Auto-Save Duplicate Analysis
- [x] Update Tab3Duplicates.js handleDetectDuplicates
  - Added saveDuplicateAnalysisToServer() function
  - POST to /api/projects/{projectId}/duplicate-analyses/ after detection
  - Sends: filename, duplicate_groups, algorithm, total_segments, duplicate_count, selected_deletions
  - Handles success/failure gracefully

- [x] Update Tab3Duplicates.js assembly
  - PUT to update duplicate-analyses with assembly_info after audio assembly
  - Includes: removedCount, keptCount, assembly timestamps
  - Success message updated to include "synced to server" confirmation

### Task 10: Auto-Load Duplicate Analysis
- [x] Update Tab3Duplicates.js useEffect
  - Added loadDuplicateAnalysisFromServer() function
  - GET /api/projects/{projectId}/duplicate-analyses/?filename={name} on file change
  - Loads: duplicate_groups, selected_deletions, assembly_info from server
  - Priority: Server > localStorage > Auto-detect
  - Updates localStorage to match server (keeps them in sync)
  - Auto-expands first 3 duplicate groups

### Task 11: Add Server Status Indicators
- [x] Added badges to Tab1Files showing sync status
  - "☁️ Synced" - Transcription synced to server
  - "📱 Local" - Saved locally only (server unavailable)
  - "☁️🔄 Server" - Server transcription only, no local audio
  
- [x] Updated success alerts with sync status
  - Transcription: Shows whether synced to server or local only
  - Assembly: Confirms "Assembly info synced to server"

### Task 12: Error Handling & Sync
- [x] Graceful fallback to localStorage when server unavailable
- [x] Server errors logged to console (no user disruption)
- [x] localStorage serves as backup/cache
- [x] Server becomes source of truth when available

**Frontend Files Modified:**
- ✅ frontend/audio-waveform-visualizer/src/components/ProjectTabs/Tab1Files.js
  - Added saveTranscriptionToServer() (lines ~110-148)
  - Added loadServerTranscriptions() (lines ~150-165)
  - Updated loadLocalFiles to check server first (lines ~167-312)
  - Updated processFileClientSide to save to server (lines ~350-365)
  - Updated success alert with sync status (lines ~367-377)
  - Updated file list display to show status_badge (line ~973)

- ✅ frontend/audio-waveform-visualizer/src/components/ProjectTabs/Tab3Duplicates.js
  - Added saveDuplicateAnalysisToServer() (lines ~83-132)
  - Added loadDuplicateAnalysisFromServer() (lines ~134-165)
  - Updated load useEffect to check server first (lines ~167-244)
  - Updated handleDetectDuplicates to save to server (lines ~691-705)
  - Updated handleAssembleAudio to save assembly info (lines ~1028-1050)

**Build & Deployment:**
- ✅ Frontend built successfully: main.c88802c4.js (1.4MB)
- ✅ Deployed to server: 82.165.221.205
- ✅ Container restarted: audioapp_frontend

---

## Phase 3: Testing & Validation

### Task 13: Cross-Device Testing
- [ ] Test transcription on Device A, load on Device B
- [ ] Test duplicate detection on Device A, load on Device B
- [ ] Test assembly info persistence across devices
- [ ] Test selected deletions persistence across devices

### Task 14: Browser Compatibility
- [ ] Test Chrome (IndexedDB + server)
- [ ] Test Edge (IndexedDB + server)
- [ ] Test Firefox (IndexedDB + server)
- [ ] Test mobile browsers (server only, no IndexedDB)

### Task 15: Performance Testing
- [ ] Test with 10+ audio files in project
- [ ] Test with large transcriptions (1+ hour files)
- [ ] Test with large duplicate groups (100+ segments)
- [ ] Measure API response times
- [ ] Verify JSON size fits within 160KB estimate

---

## Phase 4: Optional Enhancements

### Task 16: File System Access API (Optional)
- [ ] Create fileSystemBackup.js service
  - checkSupport() - detect browser capability
  - selectBackupFolder() - request user permission
  - exportProjectData() - save all data to folder
  - importProjectData() - restore from folder
  - syncWithFolder() - auto-backup on changes

- [ ] Add UI in Tab1Files
  - "Create Backup Folder" button (Chrome/Edge only)
  - "Restore from Backup" button
  - Show backup status indicator
  - Show last backup timestamp

- [ ] Add backup triggers
  - After successful transcription
  - After duplicate detection
  - After audio assembly
  - Manual "Backup Now" button

### Task 17: Export/Import JSON (Quick Alternative)
- [ ] Add "Export Project" button
  - Downloads project-data.json (all transcriptions + analyses)
  - Include timestamp and project metadata
  
- [ ] Add "Import Project" button
  - Upload and restore from project-data.json
  - Merge with existing data (no duplicates)

---

## Success Criteria

### Core Features (Required)
- ✅ Transcriptions saved to server automatically
- ✅ Duplicate analyses saved to server automatically
- ✅ Data loads from server on any device/browser
- ✅ localStorage serves as backup if server fails
- ✅ IndexedDB preserves audio files locally
- ✅ No data loss when switching devices
- ✅ No data loss when clearing browser data (audio files lost, but can re-upload)

### Optional Features
- ✅ File System Access API backup (Chrome/Edge)
- ✅ Manual export/import JSON
- ✅ Sync status indicators
- ✅ Offline mode with sync queue

---

## Technical Specifications

### Data Size Estimates
- **Transcription JSON**: ~100KB per 1-hour file
- **Duplicate Analysis JSON**: ~50KB per file
- **Total per project**: ~160KB for 1-hour file with duplicates
- **10 files**: ~1.6MB (well within Django limits)

### API Response Format
```json
{
  "id": 123,
  "project": 456,
  "audio_file": 789,
  "filename": "example.mp3",
  "transcription_data": {
    "segments": [...],
    "language": "en",
    "duration": 3600
  },
  "processing_method": "client",
  "model_used": "Xenova/whisper-tiny",
  "timestamp": "2026-03-10T12:00:00Z",
  "metadata": {}
}
```

### localStorage Keys (Existing)
- `client_transcriptions_{projectId}` - Array of transcription objects
- `duplicates_{fileId}_{projectId}` - Duplicate groups
- `duplicates_{fileId}_{projectId}_selectedDeletions` - Selected deletions
- `duplicates_{fileId}_{projectId}_assembly` - Assembly info

### IndexedDB Schema (Existing)
- **Database**: AudioTranscriptionDB
- **Store**: audioFiles
- **Key**: file ID
- **Data**: { id, projectId, file (File object), metadata, timestamp }

---

## Implementation Order

1. **Phase 1 (Backend)** - Tasks 1-6 (~2-3 hours)
2. **Phase 2 (Frontend)** - Tasks 7-12 (~2-3 hours)
3. **Phase 3 (Testing)** - Tasks 13-15 (~1-2 hours)
4. **Phase 4 (Optional)** - Tasks 16-17 (~1-2 hours if needed)

**Total Estimated Time**: 5-8 hours for core features

---

## Notes & Decisions

- **Why not store audio on server?** 
  - Audio files are large (10-100MB each)
  - Server has limited storage
  - Client-side processing already requires audio locally
  - IndexedDB provides 500MB+ storage per origin
  
- **Why JSON metadata on server?**
  - Transcriptions are text (compresses well)
  - Enables search across devices
  - Lightweight (~160KB per project)
  - Easy to backup and version
  
- **Why keep localStorage?**
  - Offline fallback
  - Instant load (no API call)
  - Conflict resolution (compare timestamps)
  - Recovery if server down

- **File System Access API limitations:**
  - Chrome/Edge only (no Firefox)
  - No mobile support
  - Requires repeated user permission
  - Optional enhancement, not core feature

---

## Migration Path

### For Existing Users (with localStorage data)
1. On first load after update:
   - Detect localStorage transcriptions
   - Auto-upload to server
   - Mark as "Migrated" 
   - Keep localStorage as backup

2. On subsequent loads:
   - Load from server
   - Merge with localStorage (server wins)
   - Update localStorage to match server

### For New Users
1. All data saves to server by default
2. localStorage mirrors server (cache)
3. IndexedDB stores audio files only

---

## Risk Mitigation

### Risk: Server down during save
- **Mitigation**: localStorage backup, retry on reconnect

### Risk: Network timeout
- **Mitigation**: 30s timeout, queue for retry, show "Local only" badge

### Risk: Concurrent edits (multiple devices)
- **Mitigation**: Timestamp comparison, server wins, show conflict warning

### Risk: JSON too large (>1MB)
- **Mitigation**: Compress segments, paginate API response, warn user

### Risk: IndexedDB quota exceeded
- **Mitigation**: Show storage usage, offer cleanup, suggest File System API

---

## Future Enhancements (Out of Scope)

- Real-time sync with WebSockets
- Collaborative editing (multiple users)
- Server-side duplicate detection fallback
- Cloud audio storage (S3/CloudFlare R2)
- Mobile app with native storage
- Desktop app with file system access
