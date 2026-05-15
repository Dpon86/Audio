# Waveform Editor Revamp Plan

> Last Updated: 2026-05-14  
> Legend: ✅ Complete | 🔄 In Progress | ⏳ Pending

---

## Status Dashboard

| Feature | Status |
|---|---|
| TabEdit.js component created | ✅ |
| WaveSurfer waveform + timeline | ✅ |
| Duplicate regions (kept=green, deleted=red) | ✅ |
| Skip Deleted Sections toggle | ✅ |
| Zoom slider with live update | ✅ |
| Waveform loading spinner | ✅ |
| Transcript pulled from API (same as Tab 1) | ✅ |
| Segment-level transcript with word timing | ✅ |
| Active segment highlighting as audio plays | ✅ |
| Click segment to seek playhead | ✅ |
| Align to Silence (ported from Duplicates tab) | ✅ |
| Professional DAW-style UI | ✅ |
| Align to Silence in Duplicates tab | ✅ |
| `deleted_items` DB column (soft delete) | ✅ |
| Cut / Paste / Volume tools | ⏳ |
| Undo / Redo history | ⏳ |
| Save Region Timings to backend | ⏳ |
| Multitrack timeline (Adobe Audition style) | ⏳ |
| Fade In / Fade Out on clips | ⏳ |

---

## 1. Overview
The goal of this revamp is to separate the analytical "Detect Duplicates" process from the new, fully-featured "Edit" process. The audio editor is housed in its own dedicated tab (TabEdit.js), complete with advanced audio editing tools, enhanced waveform visualization, and a robust layout. Backend support tracks deleted duplicates without permanently losing data (soft delete via `deleted_items` JSONField).

## 2. Backend Architecture Changes
### 2.1. Database Schema Update
- Add a new column `deleted_items` (JSONField or related table, depending on the current structure) to track duplicate items that the user removes from the list.
- **Purpose**: When a user deletes an item from the duplicates list, it is moved to `deleted_items` so it remains stored in the database for history or potential recovery.

### 2.2. API Endpoint Updates
- Update the duplicate deletion/resolution endpoints to append to `deleted_items` rather than hard-deleting the record from the database.
- Ensure the GET endpoints for duplicates filter out the deleted items by default for the main list, but can still fetch the deleted history.

## 3. Audio Processing Logic
### 3.1. Align to Silence
- Ensure the "Align to silence" logic properly calculates and **updates the actual timings** (start/end) for the audio segments.
- The updated timings must be reflected immediately in the frontend state, updating both the list and the highlighted waveform regions.

## 4. Frontend & UI Restructuring
### 4.1. Tab Reorganization
- **Current Tab ("Detect Duplicates")**:
  - Focus solely on the AI detection process and reviewing the list of duplicates.
  - The waveform view will be removed from this tab to simplify the interface.
- **New Tab ("Edit")**:
  - Create a new, dedicated editing environment.
  - House the large, interactive waveform visualizer here.
  - Keep the **"Align to Silence"** button in this step, integrated closely with the waveform.

### 4.2. Waveform Editor Enhancements
- **Advanced Editing Tools (New UI)**:
  - Add a dedicated toolbar above or beside the waveform.
  - Controls for Zoom in/out, pan, and scroll.
  - Drag-and-drop region boundaries to manually adjust timings.
  - **Multitrack Editing**: Additional lines/tracks underneath the main timeline to allow audio to be sliced, moved, and overlapped (similar to professional tools like Adobe Audition).
  - Playback controls specific to regions (play, pause, loop selection).
  - UI options for **cut, paste, and sound/volume adjustment** for individual clips.
  - **Standard DAW Features**: Include standard tools such as Undo/Redo history, Fade in/out, precise playhead snapping, splitting/merging clips, and volume adjustment/normalization.
- **Transcript Synchronization**:
  - Display the corresponding audio transcript directly underneath the waveform so users can read along with the audio.
  - Highlight the transcript words simultaneously as the audio plays.
- **Timing & State Sync**:
  - Sync the kept and deleted timings directly from the Detect Duplicates step.
  - Provide live updates (or a distinct "Sync new timings" button) to push any adjusted timeline boundaries back to the central data store.
  - **Align to Silence**: Reproduce the "Align to Silence" capabilities directly in the Edit tab, allowing users to apply it while viewing the multitrack waveform.
- **Playback & Preview Features**:
  - **"Skip deleted sections" Button**: A toggle that modifies playback to seamlessly jump over any sections marked as deleted. This allows the user to preview exactly how the edited audio flows together, so they can finely adjust the boundaries of their deleted sections.
- **Better User Experience**:
  - Give the Edit tab a clean, professional DAW (Digital Audio Workstation) feel.
  - Display exact timestamps (start/end/duration) dynamically as the user interacts with the waveform.

## 5. Implementation Steps

### Step 1: Backend Setup ✅
- Created Django migration for the `deleted_items` JSONField.
- Updated view/serializer logic handling deletions.
- Deployed and rebuilt backend containers.

### Step 2: Frontend Tab & Routing Setup ✅
- Created `TabEdit.js` component.
- Updated `ProjectTabs.js` navigation to include the "Edit" tab.
- WaveSurfer initialized with RegionsPlugin + TimelinePlugin inside TabEdit.

### Step 3: State Management & Logic Refactoring ✅
- Duplicate state accessed via `/api/projects/{id}/files/{id}/duplicates/` in both Duplicates and Edit tabs.
- Transcription loaded from shared `ProjectTabContext.transcriptionData` (populated by Tab 1).
- Align to Silence ported from WaveformDuplicateEditor into TabEdit.

### Step 4: UI/UX Editor Polish ✅
- Professional DAW-style card layout with stat badges, toolbars, transcript panel, and tool groups.
- Waveform loading spinner overlay while audio decodes.
- Segment-level transcript with live highlighting and click-to-seek.
- Toolbar includes zoom, skip-deleted toggle, time display, and playback controls.

### Step 5: Remaining Work ⏳
- **Cut / Paste / Volume** — Requires Web Audio API editing (AudioBuffer slicing, gain nodes).
- **Undo / Redo** — Requires immutable region state history.
- **Save Region Timings** — PATCH `/api/.../duplicates/{id}/` with new start/end after drag.
- **Multitrack** — Additional WaveSurfer tracks below main for clip layer editing.
- **Fade In / Out** — Gain envelope ramp on clip boundaries via AudioWorklet.

### Step 6: Final Review & Deployment ⏳
- Test state persistence when switching between tabs.
- Build locally → SCP → rsync into Nginx container.

