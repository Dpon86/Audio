# Tab-Based Architecture: Visual Flow Diagram

## 🎯 Cross-Tab Access Pattern

```
┌─────────────────────────────────────────────────────────────┐
│              ProjectTabContext (Shared State)               │
│─────────────────────────────────────────────────────────────│
│  audioFiles: []         ← All uploaded files (live updates) │
│  selectedAudioFile: {}  ← Currently selected file           │
│  projectData: {}        ← Project info (includes PDF)       │
│  activeTab: 'files'     ← Current tab                       │
│  transcriptionData: {}  ← Latest transcription              │
│  duplicatesData: {}     ← Latest duplicate detection        │
│  pdfComparisonData: {}  ← Latest PDF comparison             │
└─────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓                     ↓
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   TAB 1      │    │   TAB 2      │    │   TAB 3      │    │   TAB 4      │
│   FILES      │    │ TRANSCRIBE   │    │ DUPLICATES   │    │ COMPARE PDF  │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
      ↓                     ↓                     ↓                     ↓
  Can read:           Can read:           Can read:           Can read:
  - audioFiles        - audioFiles        - audioFiles        - audioFiles
  - selectedFile      - selectedFile      - selectedFile      - selectedFile
                      - transcription     - transcription     - transcription
  Can call:           Can call:           Can call:           Can call:
  - selectFile()      - selectFile()      - selectFile()      - selectFile()
  - setActiveTab()    - setActiveTab()    - setActiveTab()    - setActiveTab()
  - refreshFiles()    - updateFile()      - updateFile()      - updateFile()
  - removeFile()      - refreshFiles()    - refreshFiles()    - refreshFiles()
```

## 🔗 File-to-Transcription Linkage

```
DATABASE RELATIONSHIPS:
═══════════════════════

AudioFile (id=123, filename="chapter1.mp3", status="transcribed")
    ↓ OneToOne
Transcription (id=456, audio_file_id=123)
    ├── full_text: "The quick brown fox jumped over..."
    ├── word_count: 1523
    ├── pdf_match_percentage: 94.5  ← From Tab 4
    ├── pdf_validation_status: "excellent"
    └── segments: [...]
            ↓ ForeignKey (one-to-many)
    TranscriptionSegment[]
        ├── Segment 1 (id=789, text="The quick brown", start=0.0, end=1.2)
        │   ├── duplicate_group_id: "group_123_1"  ← From Tab 3
        │   ├── is_kept: false  ← User confirmed deletion
        │   └── words: [...word-level timestamps]
        ├── Segment 2 (id=790, text="fox jumped over", start=1.2, end=2.5)
        │   ├── duplicate_group_id: null
        │   ├── is_kept: true
        │   └── words: [...]
        └── ...

DuplicateGroup (audio_file_id=123, group_id="group_123_1")
    ├── duplicate_text: "The quick brown"
    ├── occurrence_count: 3
    └── total_duration_seconds: 4.5

AudioFile.processed_audio → "media/audio/processed/chapter1_clean.wav"


UI REPRESENTATION:
═════════════════

TAB 1 FILE CARD:
┌───────────────────────────────────────┐
│ 🎵 chapter1.mp3                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ ⏱️ 15:30  💾 45 MB  📝 1,523 words   │
│                                       │
│ Status: 🟢 Transcribed                │
│         📄 94% PDF Match (Excellent)  │← Shows PDF comparison result
│                                       │
│ Actions:                              │
│ [Re-transcribe] [Find Duplicates] [Compare PDF]
│ [Download Original] [Download Clean Audio]  ← If processed
└───────────────────────────────────────┘
         ↓ Click "Transcribe"
    (Navigates to Tab 2)

TAB 2 TRANSCRIPTION:
┌───────────────────────────────────────┐
│ Transcribe Audio File                 │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ Select File:                          │
│ [v chapter1.mp3 (transcribed) ▼]     │← Shows source clearly
│                                       │
│ Transcription for "chapter1.mp3"     │← Header links back
│ Word Count: 1,523                     │
│ Created: 2025-12-20 14:30             │
│                                       │
│ [View Segments] [Download TXT] [Download JSON]
│                                       │
│ Full Text:                            │
│ "The quick brown fox jumped..."       │
└───────────────────────────────────────┘

TAB 3 DUPLICATE DETECTION:
┌───────────────────────────────────────┐
│ Detect & Remove Duplicates            │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ Select File:                          │
│ [v chapter1.mp3 (transcribed) ▼]     │← Only shows transcribed
│                                       │
│ Duplicate Groups Found: 3             │
│ Total Duplicates: 7 occurrences       │
│                                       │
│ ┌─ Group 1: "The quick brown fox" ───┐
│ │ Found 3 times (4.5 seconds)        │
│ │                                     │
│ │ Occurrence 1: 00:00 - 00:01.2      │
│ │ [x] Delete [ ▶ Play]               │← Checkbox + Audio player
│ │                                     │
│ │ Occurrence 2: 05:30 - 05:31.2      │
│ │ [x] Delete [ ▶ Play]               │
│ │                                     │
│ │ Occurrence 3: 12:15 - 12:16.2      │
│ │ [ ] Keep (LAST) [ ▶ Play]          │← Recommended
│ └─────────────────────────────────────┘
│                                       │
│ Summary: 5 segments marked for deletion
│          (~8.2 seconds to be removed) │
│                                       │
│ [Generate Clean Audio]                │
└───────────────────────────────────────┘

TAB 4 PDF COMPARISON:
┌───────────────────────────────────────┐
│ Compare Transcription to PDF          │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ Select Transcription:                 │
│ [v chapter1.mp3 - Original ▼]        │← Shows source + type
│                                       │
│ Match Result: 94% 🟢 Excellent        │← Big badge
│                                       │
│ ┌─ PDF Section ──────┬─ Transcription ┐
│ │ The quick brown    │ The quick brown │ ← GREEN (matched)
│ │ fox jumped over    │ fox jumped over │
│ │ the lazy dog.      │ the lazy cat.   │ ← RED (different)
│ │ It was sunny.      │                 │ ← ORANGE (missing)
│ └────────────────────┴─────────────────┘
│                                       │
│ Statistics:                           │
│ • Matched: 1,437 words (94%)          │
│ • Missing from audio: 23 words        │
│ • Extra in audio: 63 words            │
│                                       │
│ [Retry with Settings] [Export Report] │
└───────────────────────────────────────┘
```

## 📊 User Flow: Complete Workflow

```
START: User logs in
  ↓
┌─────────────────────────────────────┐
│ 1. CREATE PROJECT                   │
│    - Enter title                    │
│    - Upload PDF book                │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│ 2. TAB 1: UPLOAD AUDIO FILES        │
│    - Drag & drop "chapter1.mp3"     │
│    - Drag & drop "chapter2.mp3"     │
│    - See: 🔵 Uploaded status        │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│ 3. CLICK "Transcribe" on chapter1   │
│    → Navigates to Tab 2             │
│    → chapter1.mp3 pre-selected      │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│ 4. TAB 2: TRANSCRIBE                │
│    - Click "Start Transcription"    │
│    - Wait: Progress 0% → 100%       │
│    - View: Transcription text       │
│    - File auto-updates: 🟢 Transcribed
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│ 5. SWITCH TO TAB 1                  │
│    - See updated status badge       │
│    - "Find Duplicates" now visible  │
│    - Click "Find Duplicates"        │
│    → Navigates to Tab 3             │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│ 6. TAB 3: DETECT DUPLICATES         │
│    - Click "Detect Duplicates"      │
│    - Review: 3 duplicate groups     │
│    - Listen to each occurrence      │
│    - Confirm: Keep last, delete rest│
│    - Click "Generate Clean Audio"   │
│    - Wait: Processing 0% → 100%     │
│    - File updates: 🟣 Processed     │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│ 7. TAB 1: VIEW RESULTS              │
│    - Download clean audio           │
│    - See processing stats           │
│    - Click "Compare PDF"            │
│    → Navigates to Tab 4             │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│ 8. TAB 4: COMPARE TO PDF            │
│    - Click "Compare to PDF"         │
│    - View: 94% match (Excellent)    │
│    - Review: Side-by-side diff      │
│    - See: What's missing/extra      │
│    - Export: Comparison report      │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│ 9. REPEAT FOR OTHER FILES           │
│    - Return to Tab 1                │
│    - Process chapter2.mp3           │
│    - All tabs accessible at any time│
└─────────────────────────────────────┘
  ↓
COMPLETE: Download all processed files
```

## 🎨 Visual Status Indicators

```
FILE STATUS PROGRESSION:
═══════════════════════

🔵 Uploaded
  ↓ (Click "Transcribe" in Tab 1 → Go to Tab 2)
🟡 Processing (Transcribing...)
  ↓ (Transcription completes)
🟢 Transcribed
  ↓ (Click "Find Duplicates" in Tab 1 → Go to Tab 3)
🟡 Processing (Detecting duplicates...)
  ↓ (User confirms deletions, clean audio generated)
🟣 Processed
  ↓ (Optional: Click "Compare PDF" in Tab 1 → Go to Tab 4)
📄 Validated (94% match)


COLOR CODING THROUGHOUT UI:
═══════════════════════════

BLUE (🔵):   Uploaded, ready to start
YELLOW (🟡): Processing in progress (animated pulse)
GREEN (🟢):  Transcribed, ready for duplicate detection
PURPLE (🟣): Processed, clean audio available
RED (🔴):    Failed, with error message


TAB BADGES:
═══════════

┌─────────┬─────────┬─────────┬─────────┐
│ Files 4 │Transcribe│Duplicates│Compare │
│ 📁      │  🎙️     │  🔍     │  📄    │
└─────────┴─────────┴─────────┴─────────┘
     ↑        ↑          ↑         ↑
   Count    Icon       Icon      Icon
```

## ✅ Implementation Checklist

**Backend (100%):**
- [x] All models created and migrated
- [x] All 18 API endpoints implemented
- [x] All 4 Celery background tasks working
- [x] File validation and error handling
- [x] Progress tracking with polling
- [x] OneToOne relationships (AudioFile ↔ Transcription)
- [x] ForeignKey relationships (Transcription → Segments)
- [x] DuplicateGroup linking

**Frontend Core (100%):**
- [x] ProjectTabContext created
- [x] Tab navigation component
- [x] Cross-tab state management
- [x] File selection persistence
- [x] Status badge system

**Tab 1 - Files (100%):**
- [x] Drag & drop upload
- [x] File cards with metadata
- [x] Status indicators
- [x] Quick action buttons
- [x] Delete functionality
- [x] Cross-tab navigation

**Tab 2 - Transcribe (60%):**
- [x] File selector
- [x] Start transcription
- [x] Progress tracking
- [x] Display results
- [ ] Segment display
- [ ] Download buttons
- [ ] Audio preview

**Tab 3 - Duplicates (10%):**
- [x] File selector (stub)
- [ ] Detect duplicates button
- [ ] Duplicate group cards
- [ ] Audio segment playback
- [ ] Checkbox confirmation
- [ ] Generate clean audio
- [ ] Statistics display

**Tab 4 - Compare PDF (10%):**
- [x] File selector (stub)
- [ ] Compare button
- [ ] Match percentage display
- [ ] Side-by-side view
- [ ] Text highlighting
- [ ] Statistics panel
- [ ] Retry functionality
