# Tab 5 PDF Comparison - Enhancements

## Overview
Added two major enhancements to the PDF comparison feature:
1. **Display matched PDF section** - Shows the exact PDF text that is being compared against the transcription
2. **Timestamps for extra content** - Shows time ranges for extra content and allows marking for deletion

## Changes Implemented

### Backend Changes

#### 1. Updated `compare_pdf_task.py`
- **New Function**: `find_extra_content_with_timestamps(transcript, pdf_section, audio_file)`
  - Matches extra content sentences to `TranscriptionSegment` records
  - Returns timestamps (`start_time`, `end_time`) for each extra content item
  - Provides array of all matching segments for sentences appearing multiple times

#### 2. New API Endpoint: `MarkContentForDeletionView`
- **URL**: `POST /api/projects/{project_id}/files/{audio_file_id}/mark-for-deletion/`
- **Purpose**: Mark segments for deletion based on timestamps from PDF comparison
- **Request Body**:
  ```json
  {
    "start_time": 123.45,
    "end_time": 145.67,
    "text": "Content to remove",
    "reason": "pdf_comparison_extra_content",
    "type": "narrator",
    "timestamps": [
      {"segment_id": 123, "start_time": 123.45, "end_time": 130.00},
      {"segment_id": 124, "start_time": 130.00, "end_time": 145.67}
    ]
  }
  ```
- **Functionality**:
  - Marks `TranscriptionSegment` records with `is_kept=False`
  - Integrates with existing deletion workflow (Tab 3 Results)
  - Supports both time-range queries and specific segment IDs

#### 3. Updated URL Routes (`urls.py`)
- Added import for `MarkContentForDeletionView`
- Added route: `path('api/projects/<int:project_id>/files/<int:audio_file_id>/mark-for-deletion/', ...)`

### Frontend Changes

#### 1. Enhanced UI Components in `Tab5ComparePDF.js`

**New Section: Matched PDF Section Display**
- Shows after statistics, before content lists
- Displays:
  - Character positions (start_char, end_char)
  - Match confidence percentage
  - Full matched PDF text (scrollable, max-height: 200px)
  - Preview of start text
- Green background (#f0fdf4) for easy identification
- Located at lines ~545-575

**Enhanced Extra Content Display**
- Added timestamp display with clock emoji (🕒)
- Format: `MM:SS - MM:SS` (e.g., "2:34 - 2:48")
- Shows "Found in X segments" for repeated content
- Color-coded: timestamps in teal (#0891b2)

**New Button: "Mark for Deletion"**
- Appears only for items with timestamps
- Red button (#dc2626) for clear visual distinction
- Located next to "Ignore This" button
- Triggers confirmation dialog with time range

#### 2. New Helper Functions

**`formatTime(seconds)`**
- Converts seconds to `MM:SS` format
- Handles undefined/null values gracefully
- Zero-pads seconds (e.g., 2:04 instead of 2:4)

**`handleMarkForDeletion(item)`**
- Shows confirmation dialog with formatted time range
- Calls new API endpoint
- Displays success/error messages
- Integrates marked segments into Tab 3 deletion workflow

## User Workflow

### Before Enhancement
1. User runs PDF comparison
2. Sees extra content list (narrator info, chapter titles)
3. Can only "Ignore This" to exclude from future comparisons
4. No way to actually remove the content from audio

### After Enhancement
1. User runs PDF comparison
2. **NEW**: Views matched PDF section to understand what's being compared
3. Sees extra content with timestamps (e.g., "2:34 - 2:48")
4. Can click "Mark for Deletion" button
5. Confirms deletion in dialog
6. Content is marked for deletion (integrates with Tab 3)
7. Can still "Ignore This" for sections that should stay in audio but not in comparison

## Data Flow

```
PDF Comparison Task (Celery)
  ↓
find_extra_content_with_timestamps()
  ↓
Searches TranscriptionSegment records for matching text
  ↓
Returns extra content with timestamps
  ↓
Frontend displays timestamps
  ↓
User clicks "Mark for Deletion"
  ↓
API: MarkContentForDeletionView
  ↓
Updates TranscriptionSegment.is_kept = False
  ↓
Segments marked for deletion (visible in Tab 3)
```

## API Response Structure

### Extra Content Item (Enhanced)
```json
{
  "text": "Chapter One: The Beginning",
  "length": 27,
  "word_count": 4,
  "possible_type": "chapter",
  "timestamps": [
    {
      "segment_id": 123,
      "start_time": 123.45,
      "end_time": 130.00
    }
  ],
  "start_time": 123.45,    // First occurrence
  "end_time": 130.00        // Last occurrence
}
```

### Match Result (Now Displayed)
```json
{
  "matched_section": "Full text of matched PDF section...",
  "start_char": 1500,
  "end_char": 5000,
  "confidence": 0.95,
  "start_preview": "...text before match...",
  "end_preview": "...text after match..."
}
```

## Technical Details

### Time Matching Logic
- Normalizes text by removing punctuation, lowercasing
- Searches all TranscriptionSegment records ordered by start_time
- Matches when sentence text contains segment text OR vice versa
- Returns all matching segments (handles repeated phrases)
- Uses earliest `start_time` and latest `end_time` for overall range

### Deletion Integration
- Uses existing `is_kept` field on TranscriptionSegment model
- Compatible with Tab 3 Results workflow
- Segments marked here appear in deletion preview
- Can be reviewed/restored using existing Tab 3 features

## Testing Checklist

- [x] Backend compiles without errors
- [x] Frontend compiles without errors
- [x] Celery worker restarts successfully
- [ ] Run PDF comparison and verify:
  - [ ] Matched PDF section displays correctly
  - [ ] Extra content shows timestamps
  - [ ] "Mark for Deletion" button appears
  - [ ] Clicking button shows confirmation dialog
  - [ ] Segments marked successfully
  - [ ] Marked segments visible in Tab 3

## Future Enhancements

1. **Bulk Deletion**: Select multiple extra content items and mark all at once
2. **Smart Filtering**: Auto-detect and bulk-mark all "chapter" or "narrator" type content
3. **Time Range Preview**: Play audio snippet before marking for deletion
4. **Undo Marking**: Add quick undo button after marking
5. **Deletion History**: Track what was marked and when
6. **Export Report**: Generate PDF comparison report with marked sections

## Files Modified

### Backend
1. `backend/audioDiagnostic/tasks/compare_pdf_task.py`
   - Added `find_extra_content_with_timestamps()` function
   - Updated task to use new function

2. `backend/audioDiagnostic/views/tab5_pdf_comparison.py`
   - Added `MarkContentForDeletionView` class

3. `backend/audioDiagnostic/urls.py`
   - Added import for new view
   - Added URL route for mark-for-deletion endpoint

### Frontend
4. `frontend/audio-waveform-visualizer/src/components/ProjectTabs/Tab5ComparePDF.js`
   - Added matched PDF section display
   - Enhanced extra content rendering with timestamps
   - Added `formatTime()` helper function
   - Added `handleMarkForDeletion()` handler
   - Added "Mark for Deletion" button

### Documentation
5. `docs/TAB5_PDF_COMPARISON_ENHANCEMENTS.md` (this file)
