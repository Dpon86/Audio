# PDF Edit Tab — Full Implementation Plan

> Created: 2026-05-15  
> Legend: ✅ Complete | 🔄 In Progress | ⏳ Pending

---

## Overview

A dedicated **"PDF Edit"** tab that reads the uploaded PDF, finds its structural elements (page breaks, paragraphs, chapters), maps those elements to audio timestamps using the transcript, then injects coloured markers into the Edit tab waveform. Users can attach gap durations or pre-recorded room tone to each marker, providing a complete post-production gap-management workflow.

---

## Status Dashboard

| Task | Status |
|---|---|
| Plan document created | ✅ |
| `pdfEditMarkers` state added to ProjectTabContext | ✅ |
| `pdfRoomTone` state added to ProjectTabContext | ✅ |
| `TabPDFEdit.js` component created | ✅ |
| PDF viewer (iframe embed) | ✅ |
| PDF text + structure loaded from `/api/projects/{id}/pdf-text/` | ✅ |
| Page-break detection | ✅ |
| Paragraph detection from double-newlines | ✅ |
| Character-to-timestamp mapping algorithm | ✅ |
| Marker list with timestamps | ✅ |
| Per-marker gap duration controls | ✅ |
| Room tone upload & preview | ✅ |
| Push markers to Edit tab waveform | ✅ |
| Purple/orange region colour in Edit tab | ✅ |
| Register tab in ProjectTabs.js nav | ✅ |
| Register tab routing in ProjectDetailPageNew.js | ✅ |
| User-placed custom gap markers | ✅ |
| Build verified | ✅ |
| Backend: `/api/projects/{id}/pdf-structure/` endpoint | ⏳ |
| Backend: Save marker configuration to DB | ⏳ |
| Backend: Apply gaps to final exported audio | ⏳ |
| Room tone injection into exported audio (FFmpeg) | ⏳ |
| Chapter heading auto-detection from font size/bold | ⏳ |

---

## Architecture

### Data Flow

```
Tab 1 (Files)
  └─ audioFiles, selectedAudioFile, transcriptionData (all_segments)
         │
         ▼
Tab PDF Edit
  ├─ Fetch PDF text + page_breaks from /api/projects/{id}/pdf-text/
  ├─ Detect paragraphs (double-newline splits)
  ├─ Map each structural element to audio time via transcript matching
  ├─ Build pdfEditMarkers[] in context
  └─ Push to TabEdit via shared context
         │
         ▼
Tab Edit
  └─ Draw pdfEditMarkers as purple regions on WaveSurfer waveform
```

### Marker Data Structure

```json
{
  "id": "marker-uuid",
  "type": "page_break | paragraph | chapter | custom",
  "label": "Page 5",
  "audioTime": 123.45,
  "pdfCharPos": 4500,
  "pdfPage": 5,
  "gapSeconds": 2.0,
  "useRoomTone": false,
  "color": "rgba(147,51,234,0.4)"
}
```

---

## Implementation Details

### 1. Character-to-Timestamp Algorithm

Uses a two-pass approach:

**Pass 1 — Word matching:**
- Tokenise both PDF text and transcript segments into words
- For a given PDF character position, extract a 10-word window around it
- Search for those words in the transcript word-time map
- Return the audio time of the first matching word found

**Pass 2 — Proportional fallback:**
- If no word match found, use `(charPos / totalPDFChars) × audioDuration`
- This gives a reasonable estimate even if PDF and transcript diverge slightly

### 2. PDF Viewer

Uses `<iframe>` embedding the PDF file served via Django's media server. Falls back to text view if no PDF file is attached to the project.

Displays:
- Full PDF in left panel
- Page indicator and navigation
- Detected markers overlaid on the page list

### 3. Paragraph Detection

Client-side: scan the extracted PDF text for `\n\n` (double newline) sequences which indicate paragraph boundaries. Filter out very short paragraphs (< 20 chars) as they are likely headers/footers already stripped by the backend cleaner.

### 4. Gap & Room Tone

Each marker has:
- **Gap seconds** — how much silence to add at this position
- **Use room tone** — if checked, the uploaded room tone clip is repeated to fill the gap duration instead of silence

The room tone file is uploaded locally (stays in browser memory as a Blob URL). It is previewed in an `<audio>` element before being applied.

**Future backend work:** A `/api/projects/{id}/assemble-with-gaps/` endpoint will accept the markers array and room tone file, then use FFmpeg to assemble the final audio with all gaps/room tones injected at the correct timestamps.

### 5. Waveform Integration (TabEdit)

TabEdit reads `pdfEditMarkers` from `ProjectTabContext`. For each marker it adds a WaveSurfer region:
- Color: `rgba(147, 51, 234, 0.35)` (purple) for page breaks
- Color: `rgba(249, 115, 22, 0.35)` (orange) for paragraph breaks
- Color: `rgba(236, 72, 153, 0.35)` (pink) for chapter headings
- Non-draggable by default (these are structural, not editorial)
- Tooltip shows: label + timestamp + gap duration

---

## Remaining Backend Work (Future Sprint)

### `/api/projects/{id}/pdf-structure/` (POST)
Accept markers array from frontend; persist to `AudioProject.pdf_structure` (new JSONField).

### `/api/projects/{id}/assemble-with-gaps/` (POST)
Accept:
- `markers[]` with gap durations
- Optional `room_tone` file upload

Use FFmpeg to:
1. Slice audio at each marker timestamp
2. Insert silence or room tone clip between each slice
3. Concatenate to final output
4. Return download URL or task ID for polling

---

## File Inventory

| File | Action | Status |
|---|---|---|
| `docs/PDF_EDIT_TAB_PLAN.md` | Created | ✅ |
| `src/contexts/ProjectTabContext.js` | Modified — added `pdfEditMarkers`, `pdfRoomTone` | ✅ |
| `src/components/ProjectTabs/TabPDFEdit.js` | Created | ✅ |
| `src/components/ProjectTabs/ProjectTabs.js` | Modified — added PDF Edit tab | ✅ |
| `src/screens/ProjectDetailPageNew.js` | Modified — routed pdf-edit tab | ✅ |
| `src/components/ProjectTabs/TabEdit.js` | Modified — renders PDF markers as purple regions | ✅ |
| `backend/audioDiagnostic/views/pdf_edit_views.py` | To create | ⏳ |
| `backend/audioDiagnostic/urls.py` | To update | ⏳ |
