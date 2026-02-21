# Interactive Waveform Editor Implementation Plan
## Tab3Duplicates Enhancement - Visual Duplicate Management

**Created:** February 17, 2026  
**Status:** Planning Phase  
**Estimated Timeline:** 12-16 hours development

---

## 🎯 Feature Overview

### Current State
Tab3Duplicates has a simple audio player at the top with a scrollable list of duplicate groups below. Users can:
- Play/pause/stop audio
- Click group headers to seek to timestamp
- Click individual timestamps to jump to that position
- Review duplicate text and occurrences

### Target State
An interactive waveform editor that provides:
- **Full audio waveform visualization** with zoom controls
- **Color-coded regions** (🔴 red = delete, 🟢 green = keep)
- **Draggable region boundaries** to adjust deletion start/end times
- **Two-way synchronization**: click list → jump to waveform, click waveform → highlight list
- **Modular component architecture** for easy maintenance and future enhancements
- **Precision editing** with visual feedback

### User Benefits
- **Visual confirmation** of what will be deleted vs. kept
- **Fine-tune boundaries** by dragging handles instead of manual time entry
- **Quick navigation** between waveform and list
- **Zoom in** to verify exact cut points don't split words
- **Immediate feedback** on deletion impact

---

## 📦 Technical Stack

### Libraries Required

#### 1. WaveSurfer.js (Core)
**Status:** ✅ Already installed  
**Version:** Latest (check package.json)  
**Purpose:** Audio waveform visualization and playback

#### 2. WaveSurfer Regions Plugin
**Status:** ⚠️ Need to install  
**Installation:** `npm install wavesurfer.js --save` (ensure latest version)  
**Import:** `import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js'`  
**Features:**
- Interactive region overlay on waveform
- Drag to move entire region
- Resize handles on start/end boundaries
- Color customization per region
- Events: `region-clicked`, `region-updated`, `region-in`, `region-out`

### Component Architecture

```
Tab3Duplicates.js (main container)
    │
    ├── State Management
    │   ├── duplicateGroups (from backend)
    │   ├── selectedGroupId (currently selected)
    │   └── modifiedTimes (track user changes)
    │
    ├── WaveformDuplicateEditor.js ← NEW COMPONENT
    │   │
    │   ├── Props (inputs)
    │   │   ├── audioFile (audio source URL)
    │   │   ├── duplicateGroups (array of groups with segments)
    │   │   ├── selectedGroupId (highlight which region)
    │   │   ├── onRegionUpdate (callback when boundary dragged)
    │   │   └── onGroupSelect (callback when region clicked)
    │   │
    │   ├── Internal State
    │   │   ├── wavesurfer (WaveSurfer instance)
    │   │   ├── regionsPlugin (Regions plugin instance)
    │   │   ├── zoomLevel (1-20 pixels per second)
    │   │   ├── isPlaying (playback state)
    │   │   ├── currentTime (playhead position)
    │   │   └── regions (Map of region objects)
    │   │
    │   ├── Sub-components
    │   │   ├── Waveform Container (canvas element)
    │   │   ├── Zoom Controls (+/- buttons, slider)
    │   │   ├── Playback Controls (play/pause/stop)
    │   │   ├── Time Display (current / total)
    │   │   └── Region Legend (red/green indicators)
    │   │
    │   └── Event Handlers
    │       ├── handleRegionClick()
    │       ├── handleRegionUpdate()
    │       ├── handleZoomChange()
    │       └── scrollToRegion()
    │
    └── DuplicateGroupsList (existing, enhanced)
        │
        ├── Props (inputs)
        │   ├── duplicateGroups
        │   ├── selectedGroupId ← NEW
        │   └── onGroupClick ← ENHANCED
        │
        └── Features
            ├── Highlight selected item (border + background)
            ├── Auto-scroll to selected item
            └── Click handler notifies parent
```

---

## ✅ Implementation Plan - 10 Steps

### Step 1: Create WaveformEditor Component Structure
**Files:** `frontend/src/components/ProjectTabs/WaveformDuplicateEditor.js`

**Tasks:**
- [ ] Create new functional component with React hooks
- [ ] Define props interface (TypeScript-style comments)
- [ ] Set up refs: `waveformRef`, `regionsPluginRef`
- [ ] Initialize state variables
- [ ] Create component skeleton with placeholder UI
- [ ] Export component

**Component Template:**
```javascript
import React, { useRef, useState, useEffect } from 'react';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js';
import './WaveformDuplicateEditor.css';

/**
 * Interactive waveform editor for duplicate segment visualization and editing
 * 
 * @param {Object} props
 * @param {string} props.audioFile - URL of audio file
 * @param {Array} props.duplicateGroups - Array of duplicate groups with segments
 * @param {string|null} props.selectedGroupId - Currently selected group ID
 * @param {Function} props.onRegionUpdate - Callback(groupId, segmentId, newStartTime, newEndTime)
 * @param {Function} props.onGroupSelect - Callback(groupId)
 */
const WaveformDuplicateEditor = ({ 
  audioFile, 
  duplicateGroups, 
  selectedGroupId, 
  onRegionUpdate, 
  onGroupSelect 
}) => {
  // Component implementation
};

export default WaveformDuplicateEditor;
```

**State Variables:**
```javascript
const [wavesurfer, setWavesurfer] = useState(null);
const [regionsPlugin, setRegionsPlugin] = useState(null);
const [zoomLevel, setZoomLevel] = useState(10); // pixels per second
const [isPlaying, setIsPlaying] = useState(false);
const [currentTime, setCurrentTime] = useState(0);
const [duration, setDuration] = useState(0);
const [regions, setRegions] = useState(new Map());
const waveformRef = useRef(null);
```

---

### Step 2: Install WaveSurfer Regions Plugin
**Location:** Frontend root directory

**Tasks:**
- [ ] Check current WaveSurfer version: `npm list wavesurfer.js`
- [ ] Update to latest if needed: `npm install wavesurfer.js@latest --save`
- [ ] Verify regions plugin is available in `node_modules/wavesurfer.js/dist/plugins/`
- [ ] Test import in component (no errors)

**Verification Command:**
```bash
cd C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer
npm list wavesurfer.js
# Should show version 7.x or higher
```

**Import Statement:**
```javascript
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js';
```

---

### Step 3: Implement Waveform Zoom Controls
**Component:** WaveformDuplicateEditor.js

**Tasks:**
- [ ] Add zoom state with min/max bounds (1-20)
- [ ] Create zoom in/out button handlers
- [ ] Create zoom slider (range input)
- [ ] Apply zoom to WaveSurfer: `wavesurfer.zoom(zoomLevel)`
- [ ] Add visual indicators (scale markers)
- [ ] Persist zoom level in localStorage (optional)

**Zoom Control UI:**
```javascript
const handleZoomIn = () => {
  setZoomLevel(prev => Math.min(prev + 2, 20));
};

const handleZoomOut = () => {
  setZoomLevel(prev => Math.max(prev - 2, 1));
};

useEffect(() => {
  if (wavesurfer) {
    wavesurfer.zoom(zoomLevel);
  }
}, [zoomLevel, wavesurfer]);
```

**JSX Template:**
```jsx
<div className="waveform-zoom-controls">
  <button onClick={handleZoomOut} disabled={zoomLevel <= 1}>
    🔍- Zoom Out
  </button>
  <input 
    type="range" 
    min="1" 
    max="20" 
    value={zoomLevel} 
    onChange={(e) => setZoomLevel(Number(e.target.value))}
    className="zoom-slider"
  />
  <span className="zoom-level">{zoomLevel}x</span>
  <button onClick={handleZoomIn} disabled={zoomLevel >= 20}>
    🔍+ Zoom In
  </button>
</div>
```

---

### Step 4: Create Color-Coded Regions (Red/Green)
**Component:** WaveformDuplicateEditor.js

**Tasks:**
- [ ] Map duplicateGroups to region data structure
- [ ] Assign colors: red (DELETE), green (KEEP)
- [ ] Create regions using regionsPlugin.addRegion()
- [ ] Add labels (group number, occurrence number)
- [ ] Handle region creation on data change
- [ ] Clear and recreate regions when duplicateGroups update

**Region Mapping Logic:**
```javascript
useEffect(() => {
  if (!regionsPlugin || !duplicateGroups) return;

  // Clear existing regions
  regionsPlugin.clearRegions();

  // Create regions for each segment
  duplicateGroups.forEach((group, groupIndex) => {
    const segments = group.segments || [];
    
    segments.forEach((segment, segIndex) => {
      const isDelete = segment.is_duplicate === true;
      const isKeep = segment.is_kept === true;
      
      regionsPlugin.addRegion({
        id: `${group.group_id}-${segment.id}`,
        start: segment.start_time,
        end: segment.end_time,
        color: isDelete ? 'rgba(239, 68, 68, 0.3)' : 'rgba(34, 197, 94, 0.3)', // red : green
        drag: true,
        resize: true,
        content: `Group ${groupIndex + 1} - ${isDelete ? 'DELETE' : 'KEEP'}`,
        data: {
          groupId: group.group_id,
          segmentId: segment.id,
          isDelete,
          isKeep
        }
      });
    });
  });
}, [regionsPlugin, duplicateGroups]);
```

**Color Scheme:**
- **Red (DELETE):** `rgba(239, 68, 68, 0.3)` - semi-transparent red
- **Green (KEEP):** `rgba(34, 197, 94, 0.3)` - semi-transparent green
- **Selected:** Add darker border or increase opacity to 0.5

---

### Step 5: Add Region Drag/Resize Handlers
**Component:** WaveformDuplicateEditor.js

**Tasks:**
- [ ] Enable drag and resize on region creation
- [ ] Listen to `region-update-end` event
- [ ] Extract new start/end times from event
- [ ] Validate boundaries (no overlap, min duration)
- [ ] Call onRegionUpdate callback with new times
- [ ] Show visual feedback during drag (cursor change)
- [ ] Add snapping to other region boundaries (optional)

**Event Handler:**
```javascript
useEffect(() => {
  if (!regionsPlugin) return;

  const handleRegionUpdate = (region) => {
    const { groupId, segmentId } = region.data;
    const newStartTime = region.start;
    const newEndTime = region.end;
    
    // Validate minimum duration (e.g., 0.1 seconds)
    if (newEndTime - newStartTime < 0.1) {
      console.warn('Region too short, reverting');
      return;
    }
    
    // Validate boundaries (no negative times)
    if (newStartTime < 0 || newEndTime > duration) {
      console.warn('Region out of bounds, reverting');
      return;
    }
    
    // Call parent callback
    onRegionUpdate(groupId, segmentId, newStartTime, newEndTime);
  };

  regionsPlugin.on('region-update-end', handleRegionUpdate);
  
  return () => {
    regionsPlugin.un('region-update-end', handleRegionUpdate);
  };
}, [regionsPlugin, duration, onRegionUpdate]);
```

**Overlap Prevention (Advanced):**
```javascript
const checkOverlap = (regionA, regionB) => {
  return !(regionA.end <= regionB.start || regionA.start >= regionB.end);
};

// In handleRegionUpdate:
const allRegions = regionsPlugin.getRegions();
const hasOverlap = allRegions.some(r => 
  r.id !== region.id && checkOverlap(region, r)
);

if (hasOverlap) {
  // Snap to nearest boundary or reject change
}
```

---

### Step 6: Sync List-to-Waveform Selection
**Components:** Tab3Duplicates.js + WaveformDuplicateEditor.js

**Tasks:**
- [ ] Add selectedGroupId prop to WaveformDuplicateEditor
- [ ] In Tab3Duplicates, track selectedGroupId state
- [ ] Pass selectedGroupId when list item clicked
- [ ] In WaveformDuplicateEditor, highlight selected region
- [ ] Auto-scroll waveform to show selected region
- [ ] Add smooth scroll animation

**Tab3Duplicates.js Changes:**
```javascript
const [selectedGroupId, setSelectedGroupId] = useState(null);

const handleGroupSelect = (groupId) => {
  setSelectedGroupId(groupId);
  // Optionally scroll list to this item too
};
```

**WaveformDuplicateEditor.js - Highlight Selected:**
```javascript
useEffect(() => {
  if (!regionsPlugin || !selectedGroupId) return;

  const allRegions = regionsPlugin.getRegions();
  
  allRegions.forEach(region => {
    const isSelected = region.data.groupId === selectedGroupId;
    
    // Update region appearance
    region.update({
      color: isSelected 
        ? (region.data.isDelete ? 'rgba(239, 68, 68, 0.6)' : 'rgba(34, 197, 94, 0.6)') // darker
        : (region.data.isDelete ? 'rgba(239, 68, 68, 0.3)' : 'rgba(34, 197, 94, 0.3)') // lighter
    });
    
    // Scroll to selected region
    if (isSelected) {
      const regionCenter = (region.start + region.end) / 2;
      wavesurfer.seekTo(regionCenter / duration);
    }
  });
}, [selectedGroupId, regionsPlugin, wavesurfer, duration]);
```

---

### Step 7: Sync Waveform-to-List Selection
**Components:** Tab3Duplicates.js + WaveformDuplicateEditor.js

**Tasks:**
- [ ] Listen to region click events in WaveformDuplicateEditor
- [ ] Extract groupId from clicked region
- [ ] Call onGroupSelect callback to notify parent
- [ ] Parent updates selectedGroupId state
- [ ] List component scrolls to matching item
- [ ] Highlight selected list item

**WaveformDuplicateEditor.js - Region Click:**
```javascript
useEffect(() => {
  if (!regionsPlugin) return;

  const handleRegionClick = (region) => {
    const { groupId } = region.data;
    onGroupSelect(groupId);
  };

  regionsPlugin.on('region-clicked', handleRegionClick);
  
  return () => {
    regionsPlugin.un('region-clicked', handleRegionClick);
  };
}, [regionsPlugin, onGroupSelect]);
```

**Tab3Duplicates.js - List Item Highlighting:**
```jsx
// In the duplicate groups list rendering:
<div 
  key={group.group_id} 
  className={`duplicate-group-card ${selectedGroupId === group.group_id ? 'selected' : ''}`}
  onClick={() => handleGroupSelect(group.group_id)}
>
  {/* existing content */}
</div>
```

**CSS for Selected Item:**
```css
.duplicate-group-card.selected {
  border: 2px solid #2563eb;
  background: rgba(37, 99, 235, 0.1);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}
```

**Auto-scroll to List Item:**
```javascript
useEffect(() => {
  if (!selectedGroupId) return;
  
  const selectedElement = document.querySelector(`[data-group-id="${selectedGroupId}"]`);
  if (selectedElement) {
    selectedElement.scrollIntoView({ 
      behavior: 'smooth', 
      block: 'center' 
    });
  }
}, [selectedGroupId]);
```

---

### Step 8: Update Segment Times on Boundary Change
**Components:** Tab3Duplicates.js + Backend API

**Tasks:**
- [ ] Implement onRegionUpdate handler in Tab3Duplicates
- [ ] Update local state with new times
- [ ] Create PATCH API endpoint in backend
- [ ] Send update to backend
- [ ] Show saving indicator
- [ ] Handle errors and rollback on failure
- [ ] Refresh duplicate groups after save

**Tab3Duplicates.js - Update Handler:**
```javascript
const handleRegionUpdate = async (groupId, segmentId, newStartTime, newEndTime) => {
  try {
    // Update local state immediately (optimistic update)
    setDuplicateGroups(prevGroups => 
      prevGroups.map(group => {
        if (group.group_id !== groupId) return group;
        
        return {
          ...group,
          segments: group.segments.map(seg => 
            seg.id === segmentId 
              ? { ...seg, start_time: newStartTime, end_time: newEndTime }
              : seg
          )
        };
      })
    );
    
    // Save to backend
    const response = await fetch(
      `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/segments/${segmentId}/`,
      {
        method: 'PATCH',
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          start_time: newStartTime,
          end_time: newEndTime
        })
      }
    );
    
    if (!response.ok) {
      throw new Error('Failed to update segment times');
    }
    
    console.log('Segment times updated successfully');
    
  } catch (error) {
    console.error('Error updating segment:', error);
    // Rollback: reload duplicate groups from backend
    await loadDuplicateGroups();
  }
};
```

**Backend API Endpoint (NEW):**
```python
# backend/audioDiagnostic/views/tab3_duplicate_detection.py

@api_view(['PATCH'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_segment_times(request, project_id, audio_file_id, segment_id):
    """
    Update start_time and end_time for a specific transcription segment.
    Used when user drags region boundaries in waveform editor.
    """
    try:
        # Verify segment belongs to this audio file
        segment = TranscriptionSegment.objects.get(
            id=segment_id,
            transcription__audio_file_id=audio_file_id,
            transcription__audio_file__project_id=project_id,
            transcription__audio_file__project__user=request.user
        )
        
        # Update times
        new_start = request.data.get('start_time')
        new_end = request.data.get('end_time')
        
        if new_start is not None:
            segment.start_time = float(new_start)
        if new_end is not None:
            segment.end_time = float(new_end)
        
        # Validate
        if segment.end_time <= segment.start_time:
            return Response(
                {'error': 'End time must be after start time'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        segment.save()
        
        return Response({
            'success': True,
            'segment_id': segment.id,
            'start_time': segment.start_time,
            'end_time': segment.end_time
        })
        
    except TranscriptionSegment.DoesNotExist:
        return Response(
            {'error': 'Segment not found'},
            status=status.HTTP_404_NOT_FOUND
        )
```

**URL Pattern (Add to urls.py):**
```python
path('projects/<int:project_id>/files/<int:audio_file_id>/segments/<int:segment_id>/',
     views.update_segment_times,
     name='update-segment-times'),
```

---

### Step 9: Add CSS Styling and Layout
**Files:** 
- `frontend/src/components/ProjectTabs/WaveformDuplicateEditor.css`
- `frontend/src/components/ProjectTabs/Tab3Duplicates.css` (modifications)

**Tasks:**
- [ ] Create WaveformDuplicateEditor.css
- [ ] Style waveform container (height, borders, shadows)
- [ ] Style zoom controls (buttons, slider)
- [ ] Style playback controls
- [ ] Add region label styling
- [ ] Make waveform sticky or give it fixed height
- [ ] Ensure responsive design
- [ ] Add loading states and spinners
- [ ] Polish hover effects and transitions

**WaveformDuplicateEditor.css:**
```css
/* Main Container */
.waveform-editor-container {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 1.5rem;
  margin-bottom: 2rem;
  position: sticky;
  top: 0;
  z-index: 50;
}

/* Header */
.waveform-editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.waveform-editor-title {
  font-size: 1.2rem;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

/* Zoom Controls */
.waveform-zoom-controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: #f8fafc;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  margin-bottom: 1rem;
}

.zoom-slider {
  width: 200px;
  height: 6px;
  cursor: pointer;
}

.zoom-level {
  font-size: 0.9rem;
  color: #64748b;
  font-weight: 600;
  min-width: 40px;
}

/* Waveform Container */
.waveform-container {
  width: 100%;
  height: 400px;
  background: #f8fafc;
  border-radius: 6px;
  overflow-x: auto;
  overflow-y: hidden;
  margin-bottom: 1rem;
  border: 2px solid #e2e8f0;
}

/* Playback Controls */
.waveform-playback-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding-top: 1rem;
  border-top: 2px solid #e2e8f0;
}

.waveform-control-btn {
  padding: 0.5rem 1.25rem;
  border: none;
  border-radius: 6px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.play-btn {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
}

.play-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #059669 0%, #047857 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 6px rgba(16, 185, 129, 0.3);
}

.stop-btn {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
}

.stop-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 6px rgba(239, 68, 68, 0.3);
}

/* Time Display */
.waveform-time-display {
  font-family: 'Courier New', monospace;
  font-size: 1rem;
  color: #1e293b;
  font-weight: 600;
  margin-left: auto;
}

/* Legend */
.waveform-legend {
  display: flex;
  gap: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
  font-size: 0.9rem;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.legend-color {
  width: 24px;
  height: 16px;
  border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.legend-color.delete {
  background: rgba(239, 68, 68, 0.5);
}

.legend-color.keep {
  background: rgba(34, 197, 94, 0.5);
}

/* Loading State */
.waveform-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: #64748b;
  font-size: 1.1rem;
}

/* Responsive */
@media (max-width: 768px) {
  .waveform-container {
    height: 250px;
  }
  
  .zoom-slider {
    width: 120px;
  }
  
  .waveform-editor-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }
}
```

**Tab3Duplicates.css Modifications:**
```css
/* Ensure list has max height and scrolls independently */
.duplicate-groups-list {
  max-height: 600px;
  overflow-y: auto;
  padding-right: 0.5rem;
}

/* Highlight selected group */
.duplicate-group-card.selected {
  border: 2px solid #2563eb;
  background: rgba(37, 99, 235, 0.05);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
}

/* Smooth transitions */
.duplicate-group-card {
  transition: all 0.2s ease-in-out;
}
```

---

### Step 10: Test and Refine UX
**Testing Checklist:**

**Functional Tests:**
- [ ] Waveform loads correctly with audio file
- [ ] All duplicate regions appear in correct positions
- [ ] Colors match deletion status (red/green)
- [ ] Zoom in/out works smoothly
- [ ] Can drag region boundaries
- [ ] Boundary changes persist (saved to backend)
- [ ] Clicking list item highlights waveform region
- [ ] Clicking waveform region highlights list item
- [ ] Playback controls work (play/pause/stop)
- [ ] Time display updates accurately

**Edge Cases:**
- [ ] Very short segments (< 0.5 seconds) are visible
- [ ] Very long audio files (> 1 hour) load efficiently
- [ ] Many duplicate groups (50+) render without lag
- [ ] Overlapping regions handled correctly
- [ ] Boundary dragging near audio start/end works
- [ ] Invalid time updates are rejected
- [ ] Network errors show user-friendly messages

**UX Refinements:**
- [ ] Add tooltips to region labels
- [ ] Show "Saving..." indicator during updates
- [ ] Add undo/redo for boundary changes
- [ ] Keyboard shortcuts (space = play/pause, +/- = zoom)
- [ ] Minimap for long audio files (optional)
- [ ] Export region data as JSON (optional)
- [ ] Reset all boundaries button

**Performance Tests:**
- [ ] Measure render time with 100 regions
- [ ] Check memory usage with long audio
- [ ] Verify smooth scrolling on zoom
- [ ] Test on slower hardware/browsers

**Browser Compatibility:**
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Edge (latest)
- [ ] Safari (if applicable)

---

## 📁 Files to Create/Modify

### New Files

```
frontend/src/components/ProjectTabs/
├── WaveformDuplicateEditor.js          [350-500 lines]
│   ├── Component logic
│   ├── WaveSurfer initialization
│   ├── Regions plugin setup
│   ├── Event handlers
│   └── Zoom controls
│
└── WaveformDuplicateEditor.css         [150-200 lines]
    ├── Container styling
    ├── Control buttons
    ├── Waveform appearance
    ├── Legend styling
    └── Responsive design
```

### Modified Files

```
frontend/src/components/ProjectTabs/
├── Tab3Duplicates.js                    [Moderate changes]
│   ├── Import WaveformDuplicateEditor
│   ├── Add selectedGroupId state
│   ├── Add handleRegionUpdate
│   ├── Add handleGroupSelect
│   └── Pass props to new component
│
└── Tab3Duplicates.css                   [Minor additions]
    ├── Selected group styling
    ├── List height adjustments
    └── Transition effects

backend/audioDiagnostic/
├── views/tab3_duplicate_detection.py    [Add 1 endpoint]
│   └── update_segment_times()
│
└── urls.py                              [Add 1 URL pattern]
    └── segments/<id>/ PATCH route
```

### Package Dependencies

```json
// frontend/package.json
{
  "dependencies": {
    "wavesurfer.js": "^7.0.0"  // Ensure latest version with Regions plugin
  }
}
```

---

## ⏱️ Estimated Timeline

### Breakdown by Phase

| Phase | Steps | Estimated Time | Deliverable |
|-------|-------|----------------|-------------|
| **Phase 1** | Steps 1-4 | 4-6 hours | Static waveform with colored regions |
| **Phase 2** | Steps 5-7 | 5-7 hours | Interactive regions with two-way sync |
| **Phase 3** | Steps 8-10 | 3-4 hours | Backend integration + polish |
| **Total** | All Steps | **12-17 hours** | Fully functional waveform editor |

### Detailed Timeline

**Day 1 (4-6 hours):**
- Step 1: Component structure (1 hour)
- Step 2: Plugin installation (30 min)
- Step 3: Zoom controls (1.5 hours)
- Step 4: Region visualization (2-3 hours)

**Day 2 (5-7 hours):**
- Step 5: Drag/resize handlers (3-4 hours)
- Step 6: List-to-waveform sync (1-1.5 hours)
- Step 7: Waveform-to-list sync (1-1.5 hours)

**Day 3 (3-4 hours):**
- Step 8: Backend integration (1.5-2 hours)
- Step 9: CSS styling (1 hour)
- Step 10: Testing & refinements (1-1.5 hours)

---

## 🚀 Recommended Implementation Approach

### Three-Phase Strategy

#### **Phase 1: Visual Foundation (Steps 1-4)**
**Goal:** Get visual feedback working first

**What You'll See:**
- Waveform appears with full audio visualization
- Colored regions overlay (red for delete, green for keep)
- Zoom controls allow detailed inspection
- Playback controls work

**Why Start Here:**
- Provides immediate visual value
- Easy to verify correctness
- No complex interactions yet
- Can demo to stakeholders early

**Testing:**
- Load an audio file with detected duplicates
- Verify all segments appear as colored regions
- Check colors match deletion status
- Test zoom in/out functionality

---

#### **Phase 2: Interactivity (Steps 5-7)**
**Goal:** Make it interactive with two-way sync

**What You'll See:**
- Can drag region boundaries with mouse
- Clicking waveform region highlights list item
- Clicking list item scrolls waveform to region
- Selected region appears darker/highlighted

**Why Second:**
- Builds on solid visual foundation
- Most complex logic here
- Requires careful event handling
- Benefits from Phase 1 debugging

**Testing:**
- Drag region boundaries, verify visual update
- Click multiple regions, check list highlights
- Click list items, verify waveform scrolls
- Test with many regions (performance)

---

#### **Phase 3: Persistence & Polish (Steps 8-10)**
**Goal:** Save changes and refine UX

**What You'll See:**
- Boundary changes save to database
- "Saving..." indicators appear
- Smooth animations and transitions
- Error handling with user feedback

**Why Last:**
- Requires backend API changes
- Depends on stable frontend
- Final polish and bug fixes
- User testing and feedback

**Testing:**
- Drag boundary, reload page, verify persisted
- Disconnect network, test error handling
- Test on different browsers/devices
- Full end-to-end workflow testing

---

## 🔧 Technical Challenges & Solutions

| Challenge | Impact | Solution | Complexity |
|-----------|--------|----------|------------|
| **Region overlap prevention** | Prevents invalid states | Validate on update, snap to boundaries | Medium |
| **Performance with 50+ regions** | UI lag, slow rendering | Lazy load, virtualize if needed | Medium |
| **Precise time alignment** | Word cutoff prevention | Store times as floats, round to 2 decimals | Low |
| **Sync timing issues** | Race conditions | Use useEffect with proper dependencies | Medium |
| **Undo/reset functionality** | User mistakes | Store original times, add reset button | Low |
| **Mobile responsiveness** | Small screen usability | Reduce waveform height, stack controls | Low |
| **Long audio files (>1hr)** | Memory usage | Optimize WaveSurfer settings, use peaks | High |
| **Network failures** | Lost changes | Optimistic updates, rollback on error | Medium |

---

## 📚 Additional Resources

### WaveSurfer.js Documentation
- **Main Docs:** https://wavesurfer.xyz/
- **Regions Plugin:** https://wavesurfer.xyz/docs/plugins/regions
- **Examples:** https://wavesurfer.xyz/examples/

### React Best Practices
- **useEffect Dependencies:** Ensure all referenced values are in dependency array
- **Ref Management:** Use `useRef` for DOM elements and WaveSurfer instances
- **Callback Optimization:** Use `useCallback` for event handlers passed to children

### Performance Optimization
- **Debouncing:** Debounce region update events (limit to 1 per 200ms)
- **Virtual Scrolling:** If >100 list items, use react-window or react-virtualized
- **Memoization:** Use `useMemo` for expensive calculations (region data mapping)

---

## ✅ Success Criteria

### Minimum Viable Product (MVP)
- [ ] Waveform displays full audio file
- [ ] All duplicate segments appear as colored regions
- [ ] Can zoom in/out to inspect details
- [ ] Can drag region boundaries
- [ ] List-to-waveform sync works
- [ ] Waveform-to-list sync works
- [ ] Changes save to backend

### Enhanced Features (Optional)
- [ ] Keyboard shortcuts (space, +/-, arrow keys)
- [ ] Minimap for long audio navigation
- [ ] Export region data as JSON
- [ ] Undo/redo stack for changes
- [ ] Batch boundary adjustment (select multiple regions)
- [ ] Audio playback loops selected region
- [ ] Waveform spectrogram view option

---

## 🎯 Next Steps

1. **Review this plan** and confirm approach
2. **Start Phase 1** (Steps 1-4) to get visual foundation
3. **Demo Phase 1** before proceeding to interactions
4. **Iterate based on feedback**
5. **Complete Phases 2 & 3** incrementally

---

## 📝 Notes & Considerations

### Design Decisions
- **Sticky vs Fixed:** Waveform uses `position: sticky` to stay visible while scrolling list
- **Color Scheme:** Red/green chosen for accessibility (but may need colorblind-friendly option)
- **Zoom Range:** 1-20x based on typical audio editing tools
- **Region Labels:** Show group number and DELETE/KEEP status

### Future Enhancements
- **AI-assisted boundary refinement:** Auto-snap to silence gaps
- **Waveform caching:** Pre-generate peaks for faster loading
- **Collaborative editing:** Real-time multi-user support
- **Audio effects preview:** Hear result before confirming deletions

### Known Limitations
- **WaveSurfer v7:** Regions plugin API may differ from v6
- **Browser support:** Safari may have audio decoding issues with some formats
- **File size:** Very large files (>100MB) may need chunked loading
- **Precision:** Millisecond precision limited by audio sample rate

---

**End of Implementation Plan**
