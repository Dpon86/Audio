# Client-Side Transcription with Server-Side Assembly Integration

**Date:** March 19, 2026  
**Status:** Backend Complete - Frontend Implementation Required

---

## Overview

This guide documents the new hybrid workflow that allows **local client-side transcription** while enabling **server-side audio assembly**. This solves the issue where transcribing locally prevented the use of server-side duplicate removal and assembly features.

### Problem Statement

Previously, when users transcribed audio files locally (in the browser):
- Audio files were never uploaded to the server
- Transcription segments remained in browser memory only
- Server-side assembly failed because it had no audio files or transcription data
- Error: "AudioProject matching query does not exist" or empty assembly results

### Solution

New backend endpoint that accepts:
1. **Audio file upload** (physical file to server)
2. **Pre-computed transcription data** (from client-side Whisper.js or similar)

This enables the workflow:
1. User loads audio files in browser
2. Browser transcribes locally using Whisper.js (no server load)
3. **Frontend uploads audio + transcription to server** ← NEW STEP
4. Server stores both audio files and transcription segments in database
5. User performs duplicate detection (client or server side)
6. **Server-side assembly now works** because it has the audio files and segments

---

## Backend Changes (COMPLETED)

### New Endpoint

**URL:** `POST /api/projects/{project_id}/upload-with-transcription/`

**Purpose:** Upload audio file with pre-computed transcription segments

**Authentication:** Required (Token/Session/Basic)

**Request Format:**
```
Content-Type: multipart/form-data

Fields:
- audio_file: (File) The actual audio file
- transcription_data: (JSON string or object) Array of transcription segments
- title: (string, optional) Title for the audio file
- order_index: (integer, optional) Order index for the file
```

**Transcription Data Format:**
```json
[
  {
    "text": "This is the first segment text.",
    "start": 0.0,
    "end": 2.5,
    "confidence": 0.95,
    "words": [
      {
        "word": "This",
        "start": 0.0,
        "end": 0.3,
        "confidence": 0.96
      },
      {
        "word": "is",
        "start": 0.3,
        "end": 0.5,
        "confidence": 0.94
      }
      // ... more words
    ]
  },
  {
    "text": "Second segment text here.",
    "start": 2.5,
    "end": 5.0,
    "confidence": 0.92,
    "words": [...]
  }
  // ... more segments
]
```

**Response Format:**
```json
{
  "success": true,
  "audio_file_id": 123,
  "filename": "chapter_01.wav",
  "title": "Chapter 1",
  "segments_count": 150,
  "words_count": 1250,
  "duration": 300.5,
  "status": "transcribed"
}
```

**Error Responses:**
- `400 Bad Request` - Missing audio file, invalid transcription data, or JSON parse error
- `401 Unauthorized` - Authentication required
- `404 Not Found` - Project not found or user doesn't own project
- `500 Internal Server Error` - Server processing failure

---

## Frontend Implementation Required

### 1. Update Upload Workflow

**Current Flow (Local Only):**
```
User selects files → Load into browser → Transcribe locally → Store in state
```

**New Flow (Hybrid):**
```
User selects files → Load into browser → Transcribe locally → 
  Upload to server (audio + transcription) → Store server IDs in state
```

### 2. Implementation Steps

#### Step 1: After Local Transcription Completes

When your Whisper.js (or similar) transcription finishes:

```javascript
// After transcription completes for a file
async function uploadTranscribedAudio(audioFile, transcriptionResult, projectId) {
  const formData = new FormData();
  
  // Add the actual audio file
  formData.append('audio_file', audioFile);
  
  // Format transcription segments
  const segments = transcriptionResult.segments.map(segment => ({
    text: segment.text,
    start: segment.start,
    end: segment.end,
    confidence: segment.confidence || 0.0,
    words: segment.words?.map(word => ({
      word: word.word,
      start: word.start,
      end: word.end,
      confidence: word.confidence || 0.0
    })) || []
  }));
  
  // Add transcription data as JSON string
  formData.append('transcription_data', JSON.stringify(segments));
  
  // Optional: Add metadata
  formData.append('title', audioFile.name);
  formData.append('order_index', fileIndex);
  
  try {
    const response = await fetch(
      `/api/projects/${projectId}/upload-with-transcription/`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Token ${authToken}`,
        },
        body: formData
      }
    );
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Upload failed');
    }
    
    const result = await response.json();
    console.log('Upload successful:', result);
    
    // Store server audio_file_id for later use
    return result;
    
  } catch (error) {
    console.error('Upload failed:', error);
    throw error;
  }
}
```

#### Step 2: Update State Management

After successful upload, store the server-side IDs:

```javascript
// Example state structure
const [audioFiles, setAudioFiles] = useState([
  {
    localId: 'local-1234567890',      // Browser-generated ID
    serverAudioFileId: 123,            // ← NEW: Server audio_file ID
    file: File,                        // Original File object
    filename: 'chapter_01.wav',
    transcription: [...],              // Transcription segments
    uploadStatus: 'completed',         // ← NEW: Track upload status
    segmentsCount: 150,
    duration: 300.5
  }
]);
```

#### Step 3: Update Duplicate Detection Workflow

When sending duplicate detection results to the server, use server IDs:

```javascript
// When user confirms deletions
async function confirmDeletions(projectId, deletions) {
  const payload = {
    confirmed_deletions: deletions.map(deletion => ({
      // Use serverAudioFileId instead of local ID
      audio_file_id: deletion.serverAudioFileId,
      segment_id: deletion.segmentId,
      start_time: deletion.start,
      end_time: deletion.end
    }))
  };
  
  const response = await fetch(
    `/api/projects/${projectId}/confirm-deletions/`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Token ${authToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    }
  );
  
  return response.json();
}
```

### 3. UI/UX Considerations

#### Progress Indicators

Add progress tracking for the upload step:

```javascript
const [uploadProgress, setUploadProgress] = useState({
  current: 0,
  total: 0,
  status: 'idle' // 'idle' | 'uploading' | 'completed' | 'error'
});

// Show progress to user
<ProgressBar 
  label="Uploading transcribed audio to server"
  current={uploadProgress.current}
  total={uploadProgress.total}
  status={uploadProgress.status}
/>
```

#### Error Handling

Handle upload failures gracefully:

```javascript
try {
  await uploadTranscribedAudio(file, transcription, projectId);
} catch (error) {
  // Show error to user
  toast.error(`Failed to upload ${file.name}: ${error.message}`);
  
  // Allow retry
  setFileStatus(fileId, 'upload-failed');
}
```

#### Batch Upload Strategy

For multiple files, upload sequentially or in small batches:

```javascript
async function uploadAllTranscriptions(files, projectId) {
  const results = [];
  
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    
    try {
      setUploadProgress({ current: i + 1, total: files.length, status: 'uploading' });
      
      const result = await uploadTranscribedAudio(
        file.file, 
        file.transcription, 
        projectId
      );
      
      results.push({ ...file, serverAudioFileId: result.audio_file_id });
      
    } catch (error) {
      console.error(`Upload failed for ${file.filename}:`, error);
      results.push({ ...file, uploadError: error.message });
    }
  }
  
  setUploadProgress({ current: files.length, total: files.length, status: 'completed' });
  return results;
}
```

### 4. Updated Component Flow

**Example React Component Structure:**

```javascript
function TranscriptionWorkflow({ projectId }) {
  const [files, setFiles] = useState([]);
  const [transcriptionStatus, setTranscriptionStatus] = useState('idle');
  const [uploadStatus, setUploadStatus] = useState('idle');
  
  // Step 1: Load files
  const handleFileSelect = (selectedFiles) => {
    const fileObjects = selectedFiles.map((file, index) => ({
      localId: `local-${Date.now()}-${index}`,
      file: file,
      filename: file.name,
      transcriptionStatus: 'pending',
      uploadStatus: 'pending'
    }));
    setFiles(fileObjects);
  };
  
  // Step 2: Transcribe locally
  const handleTranscribeLocally = async () => {
    setTranscriptionStatus('processing');
    
    for (const file of files) {
      try {
        const transcription = await transcribeWithWhisper(file.file);
        updateFile(file.localId, { 
          transcription, 
          transcriptionStatus: 'completed' 
        });
      } catch (error) {
        updateFile(file.localId, { 
          transcriptionStatus: 'error',
          transcriptionError: error.message
        });
      }
    }
    
    setTranscriptionStatus('completed');
  };
  
  // Step 3: Upload to server (NEW)
  const handleUploadToServer = async () => {
    setUploadStatus('uploading');
    
    const transcribedFiles = files.filter(f => f.transcriptionStatus === 'completed');
    
    for (const file of transcribedFiles) {
      try {
        const result = await uploadTranscribedAudio(
          file.file,
          file.transcription,
          projectId
        );
        
        updateFile(file.localId, {
          serverAudioFileId: result.audio_file_id,
          uploadStatus: 'completed'
        });
        
      } catch (error) {
        updateFile(file.localId, {
          uploadStatus: 'error',
          uploadError: error.message
        });
      }
    }
    
    setUploadStatus('completed');
  };
  
  // Step 4: Continue with duplicate detection, assembly, etc.
  const handleDuplicateDetection = () => {
    // Use serverAudioFileId from files that have uploadStatus === 'completed'
    // ... existing duplicate detection code
  };
  
  return (
    <div>
      <FileUploader onFilesSelected={handleFileSelect} />
      
      {files.length > 0 && (
        <>
          <Button 
            onClick={handleTranscribeLocally}
            disabled={transcriptionStatus === 'processing'}
          >
            Transcribe Locally
          </Button>
          
          {transcriptionStatus === 'completed' && (
            <Button 
              onClick={handleUploadToServer}
              disabled={uploadStatus === 'uploading'}
            >
              Upload to Server
            </Button>
          )}
          
          {uploadStatus === 'completed' && (
            <Button onClick={handleDuplicateDetection}>
              Detect Duplicates
            </Button>
          )}
        </>
      )}
      
      <FileList files={files} />
    </div>
  );
}
```

---

## Testing the Implementation

### Backend Testing (Completed)

Endpoint is deployed and available at:
```
POST https://audio.precisepouchtrack.com/api/projects/{project_id}/upload-with-transcription/
```

### Frontend Testing Steps

1. **Test with single file:**
   - Load one audio file
   - Transcribe locally
   - Upload using new endpoint
   - Verify server responds with audio_file_id
   - Check in browser network tab for successful response

2. **Test with multiple files:**
   - Load 3-5 audio files
   - Transcribe all locally
   - Upload all to server
   - Verify all receive unique audio_file_ids

3. **Test duplicate detection:**
   - After uploading transcribed files
   - Run duplicate detection
   - Confirm deletions
   - Verify server-side assembly works

4. **Test error handling:**
   - Try uploading without transcription data
   - Try uploading with invalid JSON
   - Verify error messages display correctly

### Verification Checklist

- [ ] Audio files upload successfully
- [ ] Transcription segments save to database
- [ ] Word-level data saves correctly (if provided)
- [ ] Server returns correct audio_file_id
- [ ] Duplicate detection works with uploaded data
- [ ] Server-side assembly produces audio output
- [ ] Download assembled audio works
- [ ] Error messages display appropriately
- [ ] Progress indicators work correctly
- [ ] Multiple file upload handles edge cases

---

## Migration Notes

### For Existing Users

Users with projects that have local-only transcriptions will need to:
1. Re-select their audio files
2. Re-transcribe (or load cached transcriptions if available)
3. Use the new upload flow

Consider adding a migration prompt in the UI for projects with local-only data.

### Backwards Compatibility

The new endpoint **does not break** existing workflows:
- Old server-side transcription endpoint still works: `/api/projects/{id}/transcribe/`
- Users can still choose full server-side workflow if preferred
- This is an **additional option**, not a replacement

---

## Performance Considerations

### Upload Size

- Audio files can be large (50-500MB for audiobook chapters)
- Consider chunked uploads for files >100MB
- Show upload progress with percentage

### Network Reliability

- Implement retry logic for failed uploads
- Consider resumable uploads for large files
- Store upload state to allow resuming after page refresh

### Browser Memory

- After successful upload, consider releasing browser File objects
- Keep only essential metadata in state
- Use server as source of truth after upload completes

---

## Security Considerations

- Authentication required for all uploads
- User can only upload to their own projects
- File size limits enforced server-side (check `settings.py` for limits)
- File type validation on both client and server
- JSON validation prevents injection attacks

---

## Future Enhancements

Potential improvements to consider:

1. **Chunked Uploads:** For very large files (>1GB)
2. **Background Upload:** Upload in background while user continues work
3. **Compression:** Compress audio before upload (lossy formats only)
4. **Delta Sync:** Only upload changed segments if re-transcribing
5. **Caching:** Cache transcriptions locally to avoid re-transcription

---

## Support & Troubleshooting

### Common Issues

**Issue:** Upload fails with 403 Forbidden
- **Solution:** Ensure user is authenticated and owns the project

**Issue:** Transcription data format error
- **Solution:** Verify JSON structure matches expected format (array of segments with text, start, end)

**Issue:** Server-side assembly still fails after upload
- **Solution:** Check that audio_file_id was saved correctly and used in deletion requests

**Issue:** Upload timeout for large files
- **Solution:** Increase timeout settings or implement chunked upload

### Debug Logging

Enable frontend logging:
```javascript
console.log('Upload payload:', {
  filename: audioFile.name,
  segmentsCount: segments.length,
  duration: segments[segments.length - 1].end
});
```

Check backend logs:
```bash
docker logs audioapp_backend -f
```

---

## Contact

For questions or issues with this integration:
- Check backend logs: `docker logs audioapp_backend`
- Check Celery logs: `docker logs audioapp_celery_worker`
- Review API response errors for specific guidance

---

**Document Version:** 1.0  
**Last Updated:** March 19, 2026  
**Backend Status:** ✅ Deployed  
**Frontend Status:** ⏳ Implementation Required
