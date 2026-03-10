# Client-Side Processing Migration Plan

**Date:** March 8, 2026  
**Goal:** Migrate all processing to client-side (local device) while preserving server-side code for future scalability

## Current State Analysis

### System Architecture
- **Frontend:** React app with Tab-based UI (5 tabs)
- **Backend:** Django + Celery workers (crashes on low-memory server)
- **Client-Side:** Whisper tiny model via transformers.js (39MB, works!)
- **Server:** 3GB RAM Ubuntu server (insufficient for audio processing)

### Current Processing Options

#### Server-Side Processing (CRASHES)
- Transcription: Whisper on server CPU/GPU
- Diarization: pyannote (requires GPU, heavy memory)
- Duplicate detection: Server-side algorithm
- Audio assembly: ffmpeg on server
- **Problem:** Server crashes due to low memory (3GB insufficient)

#### Client-Side Processing (WORKS)
- Transcription: Whisper tiny via transformers.js ✅
- Runs in browser, no server load ✅
- 39MB model download (cached) ✅
- **Problem:** Not default, UI needs improvement

### Current Pages & Toggle Status

| Page/Tab | Toggle Default | Server Option | Client Option | Status |
|----------|---------------|---------------|---------------|--------|
| Tab1 Files | ❌ Server | Enabled | Enabled | CRASHES |
| Tab2 Transcribe | ✅ Client | Enabled | Enabled | WORKS |
| AudioPage (legacy) | ❌ Server | Enabled | Enabled | CRASHES |

### Current Workflow Issues

1. **Toggle defaults to server** → Immediate crash risk
2. **Server option still visible** → Users select it and crash server
3. **"AI Model" terminology** → Confusing, sounds technical
4. **Upload to server after client processing** → Unnecessary, causes hangs
5. **No visibility of client-processed files** → Files stored in localStorage not shown

## Proposed Changes

### Phase 1: Immediate Fixes (Prevent Crashes)

#### 1.1 Default All Toggles to Client-Side
**Files to modify:**
- `src/components/ProjectTabs/Tab1Files.js` - Line 32
- `src/screens/AudioPage.js` - Line 52

**Changes:**
```javascript
// BEFORE
const [useClientSide, setUseClientSide] = useState(false);

// AFTER
const [useClientSide, setUseClientSide] = useState(true);
```

#### 1.2 Disable Server-Side Option
**Files to modify:**
- `src/components/ProjectTabs/Tab1Files.js`
- `src/components/ProjectTabs/Tab2Transcribe.js`
- `src/screens/AudioPage.js`

**Changes:**
```javascript
// Option 1: Hide server toggle completely
{false && clientSideSupported && (
  <div className="processing-mode-selector">
    {/* Toggle UI */}
  </div>
)}

// Option 2: Show toggle but disable server option with message
<p className="server-disabled-notice">
  ⚠️ Server processing temporarily disabled due to low memory. 
  Using your device for faster, private processing.
</p>
```

**Recommendation:** Option 1 (hide completely) - simpler UX

#### 1.3 Update Terminology
**Find/Replace across all files:**
- "AI Model" → "Processing Software"
- "Downloading AI Model" → "Loading Processing Software"
- "Model loaded" → "Processing software ready"

**Files affected:**
- `src/services/clientSideTranscription.js` (console logs)
- `src/components/ProjectTabs/Tab1Files.js` (UI text)
- `src/components/ProjectTabs/Tab2Transcribe.js` (UI text)
- `src/screens/AudioPage.js` (UI text)

### Phase 2: Improve Client-Side Workflow

#### 2.1 Remove Server Upload After Client Processing
**Current issue:** After transcribing locally, tries to upload to server (hangs)

**Fix:** Already implemented in latest build
- Store in localStorage
- Display in UI immediately
- Show success alert
- NO server upload

#### 2.2 Display Client-Processed Files
**Current issue:** Files processed client-side stored in localStorage but not shown in UI

**Solution:**
- Merge localStorage files with server files in display
- Add "📱 Local" badge to client-processed files
- Allow playback of local files from browser memory

**New state management:**
```javascript
// Tab1Files.js - useEffect to load local files
useEffect(() => {
  const storageKey = `client_transcriptions_${projectId}`;
  const localFiles = JSON.parse(localStorage.getItem(storageKey) || '[]');
  
  // Merge with server files
  const mergedFiles = [...audioFiles, ...localFiles.map(formatLocalFile)];
  setDisplayFiles(mergedFiles);
}, [audioFiles, projectId]);
```

#### 2.3 Better Progress Display
**Current:** Generic progress bar  
**Proposed:** Detailed step-by-step progress

```
✓ Loading processing software... (30%)
✓ Reading audio file... (40%)
✓ Converting to mono 16kHz... (50%)
⏳ Transcribing audio... (50-90%)
✓ Processing segments... (95%)
✓ Complete! (100%)
```

### Phase 3: Enhanced Client-Side Features

#### 3.1 Client-Side Duplicate Detection
**Current:** Server-side only  
**Proposed:** JavaScript algorithm in browser

**Algorithm:**
- Compare text segments for similarity
- Flag repetitions (same text within N seconds)
- Calculate Levenshtein distance
- No server needed

**New file:** `src/services/clientDuplicateDetection.js`

#### 3.2 Client-Side Audio Assembly
**Current:** ffmpeg on server  
**Proposed:** Web Audio API in browser

**Features:**
- Load audio file in browser
- Remove duplicate segments
- Stitch remaining segments
- Export as WAV/MP3 using RecordRTC
- Download directly to user's device

**New file:** `src/services/clientAudioAssembly.js`

#### 3.3 Client-Side PDF Comparison
**Current:** Server-side text comparison  
**Proposed:** JavaScript comparison in browser

**Already client-side:** PDF parsing (pdf.js)  
**Add:** Text comparison algorithm

**No changes needed** - Already works client-side!

### Phase 4: Future Server Integration (When Upgraded)

#### 4.1 Conditional Server Features
**Show server option only when:**
- Server memory > 8GB detected
- User has "premium" flag
- Specific features require server (diarization)

#### 4.2 Hybrid Mode
**Smart routing:**
- Transcription → Client-side
- Diarization → Server-side (requires GPU)
- Duplicate detection → Client-side
- Audio assembly → Client-side

## Proposed File Structure Changes

### New Files to Create

```
src/
  services/
    clientSideTranscription.js ✅ (already exists)
    clientDuplicateDetection.js ⚠️ (NEW)
    clientAudioAssembly.js ⚠️ (NEW)
    clientPdfComparison.js ⚠️ (NEW - or enhance existing)
  
  components/
    ProjectTabs/
      Tab1Files.js ✏️ (modify)
      Tab2Transcribe.js ✏️ (modify)
      Tab3Duplicates.js ✏️ (modify - use client detection)
      Tab4Results.js ✏️ (modify - use client assembly)
      Tab5ComparePDF.js ✏️ (minimal changes - already client)
  
  screens/
    AudioPage.js ✏️ (modify - legacy page)
```

### Backend Files - NO CHANGES
**Keep intact for future server upgrade:**
- `backend/audioDiagnostic/tasks/*.py` - Celery tasks
- `backend/audioDiagnostic/views/*.py` - API views
- `backend/audioDiagnostic/services/*.py` - Processing services

## User Experience Flow (Proposed)

### Uploading Files (Tab 1)

```
1. User opens Tab 1
2. Drag & drop audio file OR click "Select Files"
3. Processing starts immediately (client-side)
   
   Progress shown:
   [=====>                    ] 30%
   Loading processing software...
   
   [=============>            ] 70%
   Transcribing audio...
   
   [======================>   ] 95%
   Finalizing...
   
   [=========================] 100%
   ✅ Transcription complete!
   
   Alert shows:
   ✅ Transcription complete!
   
   File: chapter1.mp3
   Words: 1,247
   Segments: 45
   Duration: 5:32
   
   Processed entirely on your device.
   
4. File appears in list with 📱 badge
5. User can immediately proceed to other tabs
```

### Transcribing Individual Files (Tab 2)

```
1. User selects file from dropdown
2. Button shows: "🎙️ Start Transcription (On Your Device)"
3. Click to start
4. Progress shown with detailed steps
5. Results display immediately:
   - Full text
   - Segments with timestamps
   - Word count
   - 📱 "Processed locally" badge
```

### Duplicate Detection (Tab 3)

```
1. User selects transcribed file
2. Button: "🔍 Detect Duplicates (On Your Device)"
3. Client-side algorithm runs:
   - Compares all segments
   - Finds repetitions
   - Highlights in waveform
4. Results shown immediately
5. User marks duplicates for deletion
```

### Audio Assembly (Tab 4)

```
1. User reviews marked duplicates
2. Button: "✂️ Remove Duplicates (On Your Device)"
3. Client-side assembly:
   - Loads original audio
   - Removes marked segments
   - Stitches remaining audio
   - Shows preview waveform
4. User can download cleaned audio
5. Download triggers browser download (no server)
```

### PDF Comparison (Tab 5)

```
Already client-side!
1. Load PDF (client-side parsing)
2. Compare with transcription (client-side)
3. Show differences
4. Export report (client-side download)
```

## Server Resource Savings

### Current Server Load (Per File)
- Transcription: ~2GB RAM, 5-10 minutes CPU
- Diarization: ~3GB RAM, GPU required
- Total: **Server crashes** 💥

### After Migration (Per File)
- Server: 0 bytes RAM, 0% CPU ✅
- Client: User's device resources
- Total: **Server stable** 🎉

### Cost Savings
- Server upgrade: NOT NEEDED
- Bandwidth: Reduced (only 39MB model download, cached)
- Processing: FREE (users' devices)

## Implementation Priority

### Critical (Do First)
1. ✅ Default toggle to client-side
2. ✅ Disable server option UI
3. ✅ Change "AI Model" to "Processing Software"
4. ✅ Remove server upload after client processing

### High Priority
5. ⚠️ Display local files in UI
6. ⚠️ Better progress indicators
7. ⚠️ Success alerts with detailed stats

### Medium Priority
8. ⚠️ Client-side duplicate detection
9. ⚠️ Client-side audio assembly
10. ⚠️ Download functionality

### Low Priority (Future)
11. ⏳ Server toggle (when server upgraded)
12. ⏳ Hybrid processing mode
13. ⏳ Advanced features (diarization via server)

## Testing Checklist

- [ ] Tab 1: Upload file, transcribe, see in list
- [ ] Tab 2: Select file, transcribe, see results
- [ ] Tab 3: Detect duplicates (when implemented)
- [ ] Tab 4: Remove duplicates (when implemented)
- [ ] Tab 5: PDF comparison
- [ ] Console: No errors
- [ ] Network: No failed requests
- [ ] localStorage: Files persisted
- [ ] Refresh: Files still visible
- [ ] Multiple files: All work correctly
- [ ] Large files: Handle gracefully
- [ ] Error handling: Clear messages

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Browser compatibility | Medium | Check for WebAudio, ArrayBuffer support |
| Large files (>500MB) | High | Add file size limits, chunking |
| Browser crashes | Medium | Process in Web Workers |
| Data loss (refresh) | High | Persist to localStorage frequently |
| Model download fails | High | Retry logic, fallback to server (if available) |

## Browser Requirements

**Minimum:**
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

**Required APIs:**
- Web Audio API ✅
- ArrayBuffer ✅
- localStorage ✅
- File API ✅
- Web Workers (future) ⏳

## Success Metrics

- ✅ 0 server crashes during transcription
- ✅ 100% files processed client-side
- ✅ <5 seconds time-to-first-interaction
- ✅ 39MB one-time download (cached)
- ✅ No upload bandwidth used
- ✅ Works offline (after model cached)

## Future Enhancements

1. **Web Workers** - Run transcription in background thread
2. **IndexedDB** - Store larger files (>5MB)
3. **Progressive Web App** - Offline support
4. **Export formats** - JSON, CSV, SRT, VTT
5. **Batch processing** - Multiple files queued
6. **Drag-and-drop** - Better file upload UX
7. **Keyboard shortcuts** - Power user features
8. **Dark mode** - UI enhancement
9. **Waveform editing** - Visual duplicate marking
10. **Real-time preview** - See transcription as it processes

---

**Document Version:** 1.0  
**Last Updated:** March 8, 2026  
**Status:** Ready for Implementation  
**Estimated Effort:** 2-3 days for critical + high priority items
