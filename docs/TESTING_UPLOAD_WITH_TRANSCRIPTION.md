# Testing Guide: Upload-With-Transcription Feature

**Feature:** Client-Side Transcription with Server-Side Assembly Integration  
**Date:** March 19, 2026  
**Commit:** 72b1228

---

## What Was Implemented

### 1. New Service: `uploadWithTranscription.js`
- Location: `frontend/audio-waveform-visualizer/src/services/uploadWithTranscription.js`
- Uploads audio file + pre-computed transcription segments to server
- Endpoint: `POST /api/projects/{project_id}/upload-with-transcription/`
- Tracks upload progress with callbacks
- Supports batch uploads

### 2. Modified: `Tab1Files.js`
- Integrated upload service after client-side transcription completes
- Added "Uploading to Server" processing step in UI
- Tracks `server_audio_file_id` for each transcribed file
- Updated success alerts to show upload status
- Stores upload status in localStorage and IndexedDB

### 3. Key Changes:
- **Line 7**: Import `uploadWithTranscription` service
- **Lines 378-399**: Upload audio + transcription after local transcription
- **Lines 441-467**: Enhanced state tracking with `server_audio_file_id`
- **Lines 501-535**: Updated success alert with upload status
- **Lines 994-1003**: New "Uploading to Server" UI step

---

## How to Test

### Prerequisites

1. **Backend Deployed**
   - Endpoint must be available: `/api/projects/{id}/upload-with-transcription/`
   - Check backend logs: `docker logs audioapp_backend -f`

2. **Frontend Built and Deployed**
   - Build: `cd frontend/audio-waveform-visualizer && npm run build`
   - Deploy to server (see docs/Deployment_plan.md)

3. **Test Audio File**
   - Have a small WAV/MP3 file ready (1-5 minutes for quick testing)
   - Example: speech recording, podcast clip, audiobook chapter

### Test Steps

#### Test 1: Basic Upload Flow

1. **Navigate to Project**
   - Login to https://audio.precisepouchtrack.com
   - Go to a project or create new one

2. **Upload & Transcribe Client-Side**
   - Go to Tab 1 (Upload & Transcribe)
   - Ensure "Use Client-Side Processing" is checked
   - Click "Select Audio Files" or drag & drop a file

3. **Watch Processing Steps**
   You should see these steps in order:
   - ⏳ Loading Processing Software (0-30%)
   - ⏳ Reading Audio File (30%)
   - ⏳ Transcribing Audio (30-70%)
   - ⏳ Finalizing Results (70%)
   - ⏳ **Uploading to Server** (70-90%) ← **NEW**
   - ✓ Complete (100%)

4. **Check Success Alert**
   Alert should show:
   ```
   ✅ Transcription Complete!
   
   📄 File: your-file.wav
   ⏱️ Duration: 2:30
   💬 Words: 350
   📝 Segments: 25
   
   ✅ Upload Complete: Audio + transcription uploaded to server
   ☁️ Metadata Synced: Transcription available on all devices
   
   🔧 Server-Side Features Available:
      • Server-side assembly (removes duplicates server-side)
      • Cross-device access
      • Persistent storage
   
   Your audio was transcribed on your device (no server load),
   then uploaded with transcription data for server-side assembly.
   ```

5. **Verify in Browser Console**
   Open DevTools (F12) → Console tab
   Look for these logs:
   ```
   [Tab1Files] Starting transcription - estimated time: ~2 minutes
   [Tab1Files] Client-side transcription complete, storing locally
   [Tab1Files] Uploading audio + transcription to server...
   [UploadWithTranscription] Starting upload: {filename: "test.wav", ...}
   [UploadWithTranscription] Upload progress: 50%
   [UploadWithTranscription] Upload progress: 100%
   [UploadWithTranscription] Upload successful! Server audio_file_id: 123
   [Tab1Files] Transcription metadata synced to server
   ```

6. **Verify in Network Tab**
   Look for POST request to:
   ```
   POST /api/projects/{id}/upload-with-transcription/
   Status: 200 OK
   Response:
   {
     "success": true,
     "audio_file_id": 123,
     "filename": "test.wav",
     "segments_count": 25,
     "words_count": 350,
     "duration": 150.5,
     "status": "transcribed"
   }
   ```

#### Test 2: Verify Server-Side Assembly Works

1. **After Upload Completes**
   - Stay in the same project
   - File should appear in file list with ✓ transcribed status

2. **Go to Tab 3 (Detect Duplicates)**
   - Click "Detect Duplicates"
   - Should find duplicate segments (if audio has repetition)

3. **Confirm Deletions**
   - Select segments to delete
   - Click "Confirm Deletions"

4. **Try Server-Side Assembly**
   - Click "Assemble Audio"
   - Choose "Server-Side Assembly"
   - Should work WITHOUT errors!
   
   **Before this fix:** Would get error "AudioProject matching query does not exist"
   **After this fix:** Should complete successfully and allow download

5. **Download Assembled Audio**
   - Should download processed audio file
   - File should have duplicates removed
   - Download should work properly

#### Test 3: Upload Failure Handling

1. **Disconnect Network**
   - Turn off WiFi or unplug ethernet

2. **Transcribe a File**
   - Go through transcription process
   - When it reaches "Uploading to Server" step, it will fail

3. **Check Alert Message**
   Should show:
   ```
   ✅ Transcription Complete!
   
   ...
   
   ⚠️ Upload Failed: Local-only processing
   📱 Local Metadata: Server unavailable for sync
   
   📱 Your transcription is saved locally but:
      • Server-side assembly NOT available
      • Limited to this device only
      • Will try to upload again later
   
   To enable server-side features, check your connection
   and try re-processing this file.
   ```

4. **Verify Graceful Degradation**
   - File should still appear in list
   - Transcription should be viewable
   - Local duplicate detection should work
   - But server-side assembly will not work

#### Test 4: Backend Verification

SSH to server and check:

```bash
# Check backend logs for upload
docker logs --tail 100 audioapp_backend | grep -A 5 "upload-with-transcription"

# Check database for new audio file
docker exec audioapp_backend python manage.py shell
>>> from audioDiagnostic.models import AudioFile
>>> AudioFile.objects.latest('id')
>>> # Should show your uploaded file with transcription segments

# Verify transcription segments saved
>>> from audioDiagnostic.models import TranscriptionSegment
>>> TranscriptionSegment.objects.filter(audio_file__filename='test.wav').count()
>>> # Should show count matching segments in alert
```

---

## Expected Results

### ✅ Success Indicators

1. **Upload Progress**
   - "Uploading to Server" step appears (70-90%)
   - Progress bar advances smoothly
   - No errors in console

2. **Server Response**
   - Returns `audio_file_id` in response
   - Status 200 OK
   - Success alert shows "Upload Complete"

3. **File State**
   - File appears in list with transcribed status
   - `server_audio_file_id` stored in localStorage
   - File accessible in Tab 2 and Tab 3

4. **Server-Side Assembly**
   - Works without errors
   - Can download assembled audio
   - Duplicates properly removed

### ❌ Failure Indicators

1. **Upload Fails**
   - Alert shows "Upload Failed: Local-only processing"
   - Console shows error:
     ```
     [Tab1Files] Upload failed: [error message]
     ```
   - Server-side assembly will NOT work

2. **Backend Errors**
   - 400 Bad Request: Invalid transcription format
   - 401 Unauthorized: Auth token invalid
   - 404 Not Found: Project doesn't exist or user doesn't own it
   - 500 Internal Server Error: Backend processing failure

3. **State Issues**
   - `server_audio_file_id` is null
   - File marked as `client_only: true`
   - Server-side features unavailable

---

## Troubleshooting

### Issue: Upload Fails with 400 Bad Request

**Cause:** Transcription data format mismatch

**Check:**
```javascript
// In browser console after transcription
const result = // your transcription result
console.log('Segments:', result.all_segments);
// Should be array of objects with: text, start, end, confidence, words
```

**Fix:** Verify `clientSideTranscription.js` returns correct format

### Issue: Upload Timeout

**Cause:** File too large (>100MB)

**Solution:**
- Use smaller audio files
- Check `xhr.timeout` in `uploadWithTranscription.js` (currently 10 min)
- Consider implementing chunked upload for very large files

### Issue: Server-Side Assembly Still Fails

**Cause:** `audio_file_id` not used correctly in assembly

**Check:**
```javascript
// In localStorage
const storage = localStorage.getItem(`client_transcriptions_${projectId}`);
console.log(JSON.parse(storage));
// Should show server_audio_file_id for each file
```

**Fix:** Verify Tab3 uses `server_audio_file_id` when confirming deletions

### Issue: "Uploading to Server" Step Never Shows

**Cause:** Code didn't update correctly

**Check:**
1. Build was successful
2. Deployed correct build to server
3. Browser cache cleared (Ctrl + Shift + R)
4. Check browser console for errors

---

## Performance Metrics

Expected timing for 5-minute audio file:

- **Transcription:** 2-5 minutes (client-side)
- **Upload:** 10-30 seconds (depends on file size and connection)
- **Total:** 2.5-5.5 minutes

Compare with server-side:
- **Server-side transcription:** 1-3 minutes
- **No upload needed**
- **Total:** 1-3 minutes

**Trade-off:** Client-side saves server resources but takes longer overall. Upload enables server-side assembly without requiring separate transcription.

---

## Next Steps After Testing

1. **If Tests Pass:**
   - ✅ Mark backend status as "Deployed & Working"
   - ✅ Mark frontend status as "Implemented & Tested"
   - Update docs/frontend_wrok.md with test results

2. **If Tests Fail:**
   - Document specific errors
   - Check backend logs for issues
   - Verify endpoint is available
   - Debug with browser DevTools

3. **Future Enhancements:**
   - Add resume capability for failed uploads
   - Implement chunked upload for large files
   - Add retry logic with exponential backoff
   - Show upload progress in file list
   - Auto-retry failed uploads when connection restored

---

## Quick Verification Checklist

- [ ] Backend endpoint `/api/projects/{id}/upload-with-transcription/` is available
- [ ] Frontend built with new code (upload With Transcription service)
- [ ] Frontend deployed to server
- [ ] Client-side transcription completes
- [ ] "Uploading to Server" step appears in UI
- [ ] Upload progress shows 70-90%
- [ ] Success alert shows "Upload Complete"
- [ ] Console logs show `audio_file_id` received
- [ ] File appears in list with transcribed status
- [ ] Server-side assembly works without errors
- [ ] Downloaded audio plays correctly

---

**Test Date:** _________________  
**Tester:** _________________  
**Result:** ☐ Pass  ☐ Fail  ☐ Partial  
**Notes:**

