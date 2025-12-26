# Review Tab Implementation Plan

## Overview
Add a new **Tab 3: Review Deletions** between the current Duplicates tab and Results tab to allow users to preview audio with deletions and restore segments before final processing.

## Updated Tab Structure
1. **Tab 1: Files** - Upload & Transcription
2. **Tab 2: Duplicates** - Detect & Select duplicates
3. **Tab 3: Review** ✅ NEW - Preview deletions with audio playback & restoration
4. **Tab 4: Results** - Final processed audio
5. **Tab 5: Compare PDF** - PDF validation

---

## User Workflow
```
┌─────────────┐
│   Tab 2:    │
│ Duplicates  │ User selects duplicates for deletion
└──────┬──────┘
       │ Click "Review Deletions"
       ↓
┌─────────────┐
│   Tab 3:    │
│   Review    │ 1. Generate preview audio (with deletions applied)
│             │ 2. Show deletion timeline with timestamps
│             │ 3. Play audio with highlighted deletion zones
│             │ 4. User can restore individual segments
│             │ 5. Statistics preview (time saved, duration, etc.)
└──────┬──────┘
       │ Click "Confirm & Process"
       ↓
┌─────────────┐
│   Tab 4:    │
│  Results    │ Final processed audio with download
└─────────────┘
```

---

## Backend Implementation

### New API Endpoints

#### 1. Generate Deletion Preview
```python
POST /api/projects/{project_id}/files/{file_id}/preview-deletions/
```
**Purpose:** Generate temporary preview audio with deletions applied
**Request Body:**
```json
{
  "segment_ids": [123, 456, 789],  // Segments to delete
  "deletion_groups": [...]          // Optional: full group data for metadata
}
```
**Response:**
```json
{
  "task_id": "abc123",
  "status": "processing",
  "message": "Generating preview audio..."
}
```
**Processing:**
- Creates temporary AudioSegment with deletions removed
- Exports to temporary WAV file (e.g., `preview_{file_id}_{timestamp}.wav`)
- Calculates deletion regions for visualization
- Stores preview metadata in database or cache

#### 2. Get Preview Status & Data
```python
GET /api/projects/{project_id}/files/{file_id}/deletion-preview/
```
**Response:**
```json
{
  "status": "ready",  // pending, processing, ready, failed
  "preview_audio_url": "/media/previews/preview_123_1234567890.wav",
  "original_duration": 3118.602,
  "preview_duration": 2847.134,
  "segments_deleted": 212,
  "time_saved": 271.468,
  "deletion_regions": [
    {
      "region_id": 1,
      "start_time": 45.2,
      "end_time": 48.7,
      "duration": 3.5,
      "text": "Are you not here to rob me?",
      "segment_ids": [123, 124],
      "group_id": 42,
      "is_deleted": true
    },
    ...
  ],
  "kept_regions": [
    {
      "start_time": 0,
      "end_time": 45.2,
      "duration": 45.2
    },
    ...
  ]
}
```

#### 3. Restore Segments
```python
POST /api/projects/{project_id}/files/{file_id}/restore-segments/
```
**Purpose:** Restore previously marked deletions
**Request Body:**
```json
{
  "segment_ids": [123, 456],  // Segments to restore (unmark for deletion)
  "regenerate_preview": true  // Whether to regenerate preview audio
}
```
**Response:**
```json
{
  "restored_count": 2,
  "remaining_deletions": 210,
  "task_id": "def456",  // If regenerate_preview=true
  "message": "Segments restored successfully"
}
```

#### 4. Stream Preview Audio
```python
GET /api/projects/{project_id}/files/{file_id}/preview-audio/
```
**Response:** Streams the preview WAV file
**Headers:** `Content-Type: audio/wav`

#### 5. Cancel Preview
```python
DELETE /api/projects/{project_id}/files/{file_id}/cancel-preview/
```
**Purpose:** Clear preview data and return to duplicates selection
**Response:**
```json
{
  "message": "Preview cancelled and cleaned up"
}
```

### Database Changes

#### Add to AudioFile Model
```python
class AudioFile(models.Model):
    # ... existing fields ...
    
    # Preview tracking
    preview_audio = models.FileField(upload_to='previews/', null=True, blank=True)
    preview_status = models.CharField(
        max_length=20,
        choices=[
            ('none', 'None'),
            ('generating', 'Generating'),
            ('ready', 'Ready'),
            ('failed', 'Failed'),
        ],
        default='none'
    )
    preview_generated_at = models.DateTimeField(null=True, blank=True)
    preview_metadata = models.JSONField(null=True, blank=True)  # Stores deletion_regions
```

#### Add DeletionReview Model (Optional)
```python
class DeletionReview(models.Model):
    """Track user's review of pending deletions"""
    audio_file = models.ForeignKey(AudioFile, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Deletion tracking
    selected_segments = models.JSONField()  # Array of segment IDs
    restored_segments = models.JSONField(default=list)  # Array of restored IDs
    
    # Statistics
    original_deletion_count = models.IntegerField()
    current_deletion_count = models.IntegerField()
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('reviewing', 'Reviewing'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
        ],
        default='reviewing'
    )
```

### Celery Tasks

#### preview_deletions_task
```python
@shared_task
def preview_deletions_task(audio_file_id, segment_ids):
    """Generate preview audio with deletions applied"""
    audio_file = AudioFile.objects.get(id=audio_file_id)
    audio_file.preview_status = 'generating'
    audio_file.save()
    
    try:
        # Load original audio
        audio = AudioSegment.from_file(audio_file.file.path)
        
        # Get transcription segments
        segments = TranscriptionSegment.objects.filter(
            transcription__audio_file=audio_file
        ).order_by('start_time')
        
        # Build kept audio (excluding marked segments)
        kept_audio = AudioSegment.empty()
        deletion_regions = []
        current_time = 0
        
        for segment in segments:
            if segment.id in segment_ids:
                # This segment will be deleted - record region
                deletion_regions.append({
                    'region_id': len(deletion_regions) + 1,
                    'start_time': current_time,
                    'end_time': current_time + (segment.end_time - segment.start_time),
                    'duration': segment.end_time - segment.start_time,
                    'text': segment.text,
                    'segment_ids': [segment.id],
                    'is_deleted': True
                })
            else:
                # Keep this segment
                start_ms = int(segment.start_time * 1000)
                end_ms = int(segment.end_time * 1000)
                segment_audio = audio[start_ms:end_ms]
                kept_audio += segment_audio
                current_time += (segment.end_time - segment.start_time)
        
        # Export preview audio
        preview_path = f'media/previews/preview_{audio_file_id}_{int(time.time())}.wav'
        kept_audio.export(preview_path, format='wav')
        
        # Update audio file
        audio_file.preview_audio = preview_path
        audio_file.preview_status = 'ready'
        audio_file.preview_generated_at = timezone.now()
        audio_file.preview_metadata = {
            'deletion_regions': deletion_regions,
            'original_duration': len(audio) / 1000.0,
            'preview_duration': len(kept_audio) / 1000.0,
            'segments_deleted': len(segment_ids)
        }
        audio_file.save()
        
        return {'status': 'success', 'preview_path': preview_path}
        
    except Exception as e:
        audio_file.preview_status = 'failed'
        audio_file.save()
        raise
```

---

## Frontend Implementation

### Component Structure
```
src/components/ProjectTabs/
├── Tab3Review.js          ✅ NEW - Main review component
├── Tab3Review.css         ✅ NEW - Styles
└── components/
    ├── DeletionTimeline.js    ✅ NEW - Timeline view of deletions
    ├── AudioPreviewPlayer.js  ✅ NEW - WaveSurfer player with regions
    └── RestorationControls.js ✅ NEW - Restore buttons and actions
```

### Tab3Review.js - Main Component

```javascript
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js';
import './Tab3Review.css';

const Tab3Review = () => {
  const { token } = useAuth();
  const { 
    projectId, 
    selectedAudioFile,
    pendingDeletions,
    setPendingDeletions,
    setActiveTab 
  } = useProjectTab();
  
  const [previewStatus, setPreviewStatus] = useState('none'); // none, loading, ready, failed
  const [previewData, setPreviewData] = useState(null);
  const [restoredSegments, setRestoredSegments] = useState([]);
  const [wavesurfer, setWavesurfer] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const waveformRef = useRef(null);
  const regionsRef = useRef(null);
  
  // Generate preview on mount
  useEffect(() => {
    if (pendingDeletions && pendingDeletions.audioFile) {
      generatePreview();
    }
  }, [pendingDeletions]);
  
  const generatePreview = async () => {
    setPreviewStatus('loading');
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${pendingDeletions.audioFile.id}/preview-deletions/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            segment_ids: pendingDeletions.segmentIds,
            deletion_groups: pendingDeletions.duplicateGroups
          })
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        // Poll for completion
        pollPreviewStatus(data.task_id);
      } else {
        setPreviewStatus('failed');
      }
    } catch (error) {
      console.error('Error generating preview:', error);
      setPreviewStatus('failed');
    }
  };
  
  const pollPreviewStatus = async (taskId) => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(
          `http://localhost:8000/api/projects/${projectId}/files/${pendingDeletions.audioFile.id}/deletion-preview/`,
          {
            headers: {
              'Authorization': `Token ${token}`,
              'Content-Type': 'application/json'
            }
          }
        );
        
        if (response.ok) {
          const data = await response.json();
          
          if (data.status === 'ready') {
            clearInterval(interval);
            setPreviewData(data);
            setPreviewStatus('ready');
            initializeWaveform(data.preview_audio_url, data.deletion_regions);
          } else if (data.status === 'failed') {
            clearInterval(interval);
            setPreviewStatus('failed');
          }
        }
      } catch (error) {
        console.error('Error polling preview:', error);
      }
    }, 2000);
  };
  
  const initializeWaveform = (audioUrl, deletionRegions) => {
    if (waveformRef.current) {
      const ws = WaveSurfer.create({
        container: waveformRef.current,
        waveColor: '#4a90e2',
        progressColor: '#1e5a99',
        cursorColor: '#ff6b6b',
        barWidth: 2,
        barRadius: 3,
        responsive: true,
        height: 120,
        plugins: [
          RegionsPlugin.create({})
        ]
      });
      
      ws.load(audioUrl);
      
      ws.on('ready', () => {
        // Add deletion regions as overlays
        const regions = ws.registerPlugin(RegionsPlugin.create());
        
        deletionRegions.forEach((region, index) => {
          if (region.is_deleted && !restoredSegments.includes(region.segment_ids[0])) {
            regions.addRegion({
              id: `deletion-${index}`,
              start: region.start_time,
              end: region.end_time,
              color: 'rgba(255, 107, 107, 0.3)', // Red overlay for deletions
              drag: false,
              resize: false,
              content: `Deleted: ${region.text.substring(0, 30)}...`
            });
          }
        });
      });
      
      ws.on('audioprocess', () => {
        setCurrentTime(ws.getCurrentTime());
      });
      
      ws.on('play', () => setIsPlaying(true));
      ws.on('pause', () => setIsPlaying(false));
      
      setWavesurfer(ws);
      regionsRef.current = ws.registerPlugin(RegionsPlugin.create());
    }
  };
  
  const handleRestoreSegment = async (segmentId) => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${pendingDeletions.audioFile.id}/restore-segments/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            segment_ids: [segmentId],
            regenerate_preview: true
          })
        }
      );
      
      if (response.ok) {
        setRestoredSegments([...restoredSegments, segmentId]);
        // Update pending deletions
        const updatedSegments = pendingDeletions.segmentIds.filter(id => id !== segmentId);
        setPendingDeletions({
          ...pendingDeletions,
          segmentIds: updatedSegments,
          deletionCount: updatedSegments.length
        });
        
        // Regenerate preview
        generatePreview();
      }
    } catch (error) {
      console.error('Error restoring segment:', error);
    }
  };
  
  const handleConfirmAndProcess = () => {
    // Navigate to Results tab for final processing
    setActiveTab('results');
  };
  
  const handleCancel = () => {
    // Clear preview and return to duplicates
    setPendingDeletions(null);
    setActiveTab('duplicates');
  };
  
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  if (!pendingDeletions) {
    return (
      <div className="tab3-review-container">
        <div className="empty-state">
          <p>No pending deletions to review. Go to Duplicates tab to select segments.</p>
          <button onClick={() => setActiveTab('duplicates')} className="primary-button">
            Go to Duplicates
          </button>
        </div>
      </div>
    );
  }
  
  return (
    <div className="tab3-review-container">
      <div className="tab-header">
        <h2>👁️ Review Deletions</h2>
        <p>Preview audio with deletions and restore segments before final processing</p>
      </div>
      
      {/* Statistics Cards */}
      {previewData && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon">⏱️</div>
            <div className="stat-info">
              <div className="stat-label">Original Duration</div>
              <div className="stat-value">{formatTime(previewData.original_duration)}</div>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon">✂️</div>
            <div className="stat-info">
              <div className="stat-label">Preview Duration</div>
              <div className="stat-value">{formatTime(previewData.preview_duration)}</div>
            </div>
          </div>
          
          <div className="stat-card success">
            <div className="stat-icon">💾</div>
            <div className="stat-info">
              <div className="stat-label">Time Saved</div>
              <div className="stat-value">{formatTime(previewData.time_saved)}</div>
              <div className="stat-subtitle">
                {((previewData.time_saved / previewData.original_duration) * 100).toFixed(1)}% reduction
              </div>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon">🗑️</div>
            <div className="stat-info">
              <div className="stat-label">Deletions</div>
              <div className="stat-value">{pendingDeletions.deletionCount - restoredSegments.length}</div>
              <div className="stat-subtitle">{restoredSegments.length} restored</div>
            </div>
          </div>
        </div>
      )}
      
      {/* Loading State */}
      {previewStatus === 'loading' && (
        <div className="loading-card">
          <div className="loading-spinner"></div>
          <div className="loading-content">
            <h3>🔄 Generating Preview</h3>
            <p>Creating audio preview with deletions applied...</p>
            <p className="loading-info">This may take a few moments.</p>
          </div>
        </div>
      )}
      
      {/* Preview Ready */}
      {previewStatus === 'ready' && previewData && (
        <>
          {/* Audio Player */}
          <div className="audio-player-card">
            <h3>🎵 Preview Audio</h3>
            <p>Red regions show deleted sections. Click to restore individual segments.</p>
            
            <div ref={waveformRef} className="waveform-container"></div>
            
            <div className="player-controls">
              <button
                onClick={() => wavesurfer?.playPause()}
                className="play-button"
              >
                {isPlaying ? '⏸️ Pause' : '▶️ Play'}
              </button>
              <button
                onClick={() => wavesurfer?.stop()}
                className="stop-button"
              >
                ⏹️ Stop
              </button>
              <span className="time-display">
                {formatTime(currentTime)} / {formatTime(previewData.preview_duration)}
              </span>
            </div>
          </div>
          
          {/* Deletion Timeline */}
          <div className="deletion-timeline-card">
            <h3>📋 Deletion Timeline</h3>
            <p>{pendingDeletions.deletionCount - restoredSegments.length} segments marked for deletion</p>
            
            <div className="deletion-list">
              {previewData.deletion_regions.map((region, index) => {
                const isRestored = restoredSegments.includes(region.segment_ids[0]);
                return (
                  <div 
                    key={index} 
                    className={`deletion-item ${isRestored ? 'restored' : ''}`}
                    onClick={() => wavesurfer?.setTime(region.start_time)}
                  >
                    <div className="deletion-header">
                      <span className="deletion-time">
                        {formatTime(region.start_time)} - {formatTime(region.end_time)}
                      </span>
                      <span className="deletion-duration">({region.duration.toFixed(1)}s)</span>
                      {isRestored && <span className="restored-badge">✅ Restored</span>}
                    </div>
                    <div className="deletion-text">{region.text}</div>
                    {!isRestored && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRestoreSegment(region.segment_ids[0]);
                        }}
                        className="restore-button-small"
                      >
                        ↩️ Restore
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
      
      {/* Error State */}
      {previewStatus === 'failed' && (
        <div className="error-card">
          <h3>❌ Preview Generation Failed</h3>
          <p>Unable to generate preview audio. Please try again.</p>
          <button onClick={generatePreview} className="retry-button">
            🔄 Retry
          </button>
        </div>
      )}
      
      {/* Action Buttons */}
      <div className="action-buttons">
        <button
          onClick={handleCancel}
          className="cancel-button"
        >
          ← Back to Duplicates
        </button>
        
        <button
          onClick={handleConfirmAndProcess}
          disabled={previewStatus !== 'ready'}
          className="confirm-button primary"
        >
          ✅ Confirm & Process ({pendingDeletions.deletionCount - restoredSegments.length} deletions)
        </button>
      </div>
    </div>
  );
};

export default Tab3Review;
```

---

## Implementation Steps (TODO List)

### Phase 1: Backend Setup ⏳
- [ ] Create preview_deletions_task in Celery
- [ ] Add preview fields to AudioFile model
- [ ] Create migration for database changes
- [ ] Implement POST /preview-deletions/ endpoint
- [ ] Implement GET /deletion-preview/ endpoint
- [ ] Implement POST /restore-segments/ endpoint
- [ ] Implement GET /preview-audio/ streaming endpoint
- [ ] Implement DELETE /cancel-preview/ endpoint
- [ ] Add preview file cleanup (delete old previews)
- [ ] Test all endpoints with Postman/curl

### Phase 2: Frontend Component ⏳
- [ ] Create Tab3Review.js component
- [ ] Create Tab3Review.css styles
- [ ] Implement preview generation request
- [ ] Implement status polling logic
- [ ] Add WaveSurfer.js integration
- [ ] Add RegionsPlugin for deletion highlighting
- [ ] Create deletion timeline list
- [ ] Implement restore functionality
- [ ] Add statistics cards
- [ ] Add loading/error states

### Phase 3: Navigation Updates ⏳
- [ ] Update ProjectTabs.js (add Review tab icon 👁️)
- [ ] Rename Tab3Duplicates to Tab2Duplicates
- [ ] Rename Tab4Results to Tab5Results
- [ ] Update tab navigation logic in ProjectDetailPageNew.js
- [ ] Update context to handle review state
- [ ] Update "Review Deletions" button in Tab2 to navigate to Tab3
- [ ] Update Tab3 to navigate to Tab5 (Results) on confirm

### Phase 4: Testing & Polish ⏳
- [ ] Test complete workflow: Duplicates → Review → Results
- [ ] Test restoration of individual segments
- [ ] Test restoration of all segments
- [ ] Test cancel/back navigation
- [ ] Verify audio preview plays correctly
- [ ] Verify deletion regions highlight properly
- [ ] Test mobile responsiveness
- [ ] Add keyboard shortcuts (Space: play/pause)
- [ ] Add tooltips and help text
- [ ] Performance testing with large files

### Phase 5: User Experience ⏳
- [ ] Add smooth transitions between states
- [ ] Add fade in/out animations for restorations
- [ ] Add sound feedback for actions
- [ ] Add progress indicators
- [ ] Add confirmation dialogs for bulk actions
- [ ] Add undo/redo capability
- [ ] Add export deletion report (PDF/JSON)
- [ ] Add sharing/collaboration features

---

## User Interface Mockup

```
┌─────────────────────────────────────────────────────────────┐
│ 👁️ Review Deletions                                         │
│ Preview audio with deletions and restore segments before    │
│ final processing                                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ ⏱️ 52:00  │  │ ✂️ 47:29  │  │ 💾 4:31  │  │ 🗑️ 212   │   │
│  │ Original  │  │ Preview   │  │ Saved    │  │ Deletions│   │
│  │ Duration  │  │ Duration  │  │ 8.7%     │  │ 0 restored│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🎵 Preview Audio                                           │
│  Red regions show deleted sections                          │
│                                                             │
│  ▓▓▓▓▓░░░░▓▓▓▓▓▓▓░░░▓▓▓▓▓▓▓▓▓▓░░░░░▓▓▓▓▓  (Waveform)      │
│     ↑ Deletion                                              │
│                                                             │
│  [▶️ Play] [⏹️ Stop]         2:15 / 47:29                   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📋 Deletion Timeline (212 segments)                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ⏱️ 2:15 - 2:45 (30s)                   [↩️ Restore] │   │
│  │ "Are you not here to rob me? Are you not?"          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ⏱️ 5:32 - 5:48 (16s)                   [↩️ Restore] │   │
│  │ "So, she tried to maintain her commanding tone..."  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ⏱️ 8:10 - 8:15 (5s)                    [↩️ Restore] │   │
│  │ "Stand and deliver!"                                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ... (209 more)                                             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [← Back to Duplicates]        [✅ Confirm & Process (212)] │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Benefits of Review Tab

✅ **User Control:** Users can hear exactly what will be deleted before committing
✅ **Error Prevention:** Catch mistakes before permanent deletion
✅ **Transparency:** Clear visualization of what's being removed
✅ **Flexibility:** Easy restoration of individual segments
✅ **Confidence:** Preview audio gives certainty about the result
✅ **User-Friendly:** Audio playback with visual highlighting is intuitive
✅ **Professional:** Matches industry-standard audio editing workflows

---

## Next Steps

1. Review and approve this implementation plan
2. Begin Phase 1: Backend API development
3. Test backend with Postman/curl
4. Begin Phase 2: Frontend component development
5. Integration testing
6. User acceptance testing
7. Production deployment
