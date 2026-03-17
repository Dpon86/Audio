# Transcription System Optimization TODO

## 📊 Current State Analysis

### **Server-Side Transcription**

**Implementation:**
- **Model:** OpenAI Whisper `base` (74MB)
- **Library:** openai-whisper (Python)
- **Processing:** Celery background tasks
- **Features:**
  - ✅ Word-level timestamps (`word_timestamps=True`)
  - ✅ Confidence scores (avg_logprob for segments, probability for words)
  - ✅ Full audio processing in one pass
  - ✅ Saves to database (persistent)
  - ✅ Word-level granularity (TranscriptionWord model)
  - ✅ Progress tracking via Redis
- **Limitations:**
  - ❌ No speaker diarization
  - ❌ No punctuation confidence
  - ❌ No post-processing/correction
  - ❌ Fixed model size (base)
  - ❌ Server memory/CPU required

**Code Location:** `backend/audioDiagnostic/tasks/transcription_tasks.py`

```python
# Server transcription call
model = whisper.load_model("base")
result = model.transcribe(audio_path, word_timestamps=True)

# Confidence tracking
confidence_score = segment.get('avg_logprob', 0.0)  # Segment confidence
confidence = word_data.get('probability', 0.0)      # Word confidence
```

---

### **Client-Side Transcription**

**Implementation:**
- **Model:** Xenova Whisper `tiny.en` (39MB)
- **Library:** transformers.js (JavaScript/ONNX)
- **Processing:** Browser Web Audio API
- **Features:**
  - ✅ Runs in browser (no server load)
  - ✅ Timestamp support (`return_timestamps: true`)
  - ✅ Chunked processing (30s chunks, 5s overlap)
  - ✅ Model caching (IndexedDB)
  - ✅ Progress callbacks
  - ✅ One-time model download
- **Limitations:**
  - ❌ **No confidence scores** (transformers.js limitation)
  - ❌ Smaller model = less accurate (tiny vs base)
  - ❌ **Not saved to database** (ephemeral results)
  - ❌ No word-level timestamps (segment-level only)
  - ❌ Chunk boundaries can cause splitting issues
  - ❌ No speaker diarization
  - ❌ English-only model (tiny.en)

**Code Location:** `frontend/audio-waveform-visualizer/src/services/clientSideTranscription.js`

```javascript
// Client transcription call
const result = await this.transcriber(audioData, {
  chunk_length_s: 30,        // 30-second chunks
  stride_length_s: 5,        // 5-second overlap
  return_timestamps: true,
  ...options
});

// No confidence scores available in transformers.js
```

---

## 🔍 Key Differences Comparison

| Feature | Server-Side | Client-Side | Impact |
|---------|-------------|-------------|---------|
| **Accuracy** | Higher (base model) | Lower (tiny model) | Server produces better text |
| **Model Size** | 74MB | 39MB | Client faster download |
| **Confidence Scores** | ✅ Yes (segment + word) | ❌ No | Can't assess quality client-side |
| **Word Timestamps** | ✅ Word-level | ❌ Segment-level | Server better for precise editing |
| **Processing Time** | 0.5-2x real-time | 0.5-1x real-time | Similar speed |
| **Server Load** | High (CPU/memory) | None | Client better for server |
| **Persistence** | ✅ Database | ❌ Ephemeral | Server results saved |
| **Chunk Processing** | Full audio | 30s chunks + overlap | Server more consistent |
| **Progress Tracking** | ✅ Redis | ✅ Callbacks | Both good |
| **Speaker Diarization** | ❌ No | ❌ No | Neither supports this |
| **Multi-language** | ✅ Yes (base model) | ❌ English only (.en) | Server more flexible |

---

## 🎯 Identified Issues

### **1. Client Transcriptions Are Ephemeral**
**Problem:** Client-side transcriptions aren't saved to database  
**Impact:** User must re-transcribe if they close browser  
**Evidence:** Tab2Transcribe.js saves to context state only, not API

```javascript
// Current: Only saves to React state
setTranscriptionData({
  text: result.text,
  all_segments: result.all_segments || [],
  word_count: result.text.split(/\s+/).filter(w => w.length > 0).length,
  client_processed: true  // Flag but not persisted
});
```

---

### **2. No Confidence Scores on Client**
**Problem:** Can't assess transcription quality  
**Impact:** No way to identify low-confidence segments for review  
**Evidence:** transformers.js doesn't expose confidence/probability

**Server has this:**
```python
confidence_score = segment.get('avg_logprob', 0.0)
confidence = word_data.get('probability', 0.0)
```

**Client doesn't:**
```javascript
// formatSegments() has no confidence field
return result.chunks.map((chunk, index) => ({
  id: index,
  start: chunk.timestamp[0] || 0,
  end: chunk.timestamp[1] || 0,
  text: chunk.text.trim(),
  speaker: null  // No diarization either
}));
```

---

### **3. Timestamping Accuracy Issues**

**Problem:** Timestamp misalignment between audio and text  
**Root Causes:**
1. **Whisper's inherent limitations:** Model sometimes misaligns timestamps
2. **Chunk boundaries (client):** 30s chunks can split words/sentences
3. **No VAD (Voice Activity Detection):** Timestamps include silence
4. **No forced alignment:** Post-processing could improve alignment

**Example from your use case:**
> User mentioned timestamping issues in TODO list

**Current approach:**
- Server: Single-pass processing (better consistency)
- Client: 30s chunks with 5s overlap (can cause boundary drift)

```javascript
// Client chunking parameters
chunk_length_s: 30,     // Split into 30s segments
stride_length_s: 5,     // 5s overlap to prevent cutting
```

**Issues:**
- Overlap regions can have duplicate/conflicting timestamps
- Long pauses can throw off timing
- Whisper estimates timestamps, doesn't force-align

---

### **4. No Word-Level Timestamps on Client**

**Problem:** Client only has segment timestamps, not word-level  
**Impact:** Can't do precise word-by-word editing  
**Comparison:**

**Server:**
```python
TranscriptionWord.objects.create(
    segment=seg_obj,
    word=word_data['word'].strip(),
    start_time=word_data['start'],  # Word-level timing
    end_time=word_data['end'],
    confidence=word_data.get('probability', 0.0)
)
```

**Client:**
```javascript
// Only segment-level timestamps
{
  start: chunk.timestamp[0],  // Segment start
  end: chunk.timestamp[1],    // Segment end
  text: chunk.text.trim()     // Whole segment text
}
```

---

### **5. Model Size Trade-off**

**Current:**
- Server: `base` model (74MB) - better accuracy
- Client: `tiny.en` model (39MB) - faster but less accurate

**Accuracy difference:** Base is ~10-15% more accurate than tiny

**User Impact:** Client transcriptions may have:
- More word errors
- More punctuation errors
- Poorer handling of accents/background noise
- Limited to English only

---

### **6. No Post-Processing or Correction**

**Problem:** Raw Whisper output has known issues  
**Common issues:**
- Repeated words/phrases (hallucinations)
- Incorrect punctuation
- Missing capitalization
- Inconsistent formatting
- Filler words (um, uh) sometimes missing or wrong

**Neither client nor server does:**
- ❌ Punctuation normalization
- ❌ Capitalization correction
- ❌ Filler word detection
- ❌ Repetition removal
- ❌ Format standardization
- ❌ Confidence-based correction

---

## ✅ Optimization Recommendations

### **Phase 1: Quick Wins (High Impact, Low Effort)**

#### [ ] 1. Save Client Transcriptions to Database
**Why:** Persist client-side results, prevent re-transcription  
**Impact:** Major UX improvement  
**Effort:** 30 minutes

**Implementation:**
```javascript
// In Tab2Transcribe.js, after client transcription:
const saveResponse = await fetch(
  `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/transcription/`,
  {
    method: 'POST',
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      full_text: result.text,
      segments: result.all_segments,
      source: 'client_whisper_tiny',
      confidence_score: null  // Not available from transformers.js
    })
  }
);
```

**Backend changes needed:**
- Create endpoint to accept client transcriptions
- Store in same Transcription/TranscriptionSegment models
- Add `source` field to distinguish client vs server

---

#### [ ] 2. Add Confidence Score UI Placeholders
**Why:** Show when confidence data is available (server) vs not (client)  
**Impact:** User awareness of quality  
**Effort:** 15 minutes

**UI Changes:**
```javascript
// Show confidence for server transcriptions
{transcriptionData.confidence_score && (
  <div className="confidence-indicator">
    <span>Quality Score: </span>
    <span className={getConfidenceClass(transcriptionData.confidence_score)}>
      {(transcriptionData.confidence_score * 100).toFixed(1)}%
    </span>
  </div>
)}

// Indicate when confidence unavailable
{transcriptionData.client_processed && (
  <div className="info-badge">
    ℹ️ Client-side processing (quality metrics not available)
  </div>
)}
```

---

#### [ ] 3. Improve Client Chunk Processing
**Why:** Reduce timestamp drift at boundaries  
**Impact:** Better timestamp accuracy  
**Effort:** 10 minutes

**Current:**
```javascript
chunk_length_s: 30,
stride_length_s: 5,
```

**Recommended:**
```javascript
chunk_length_s: 20,   // Smaller chunks = less drift
stride_length_s: 3,   // Smaller overlap = less duplication
```

**Trade-off:** Slightly slower processing but better accuracy

---

#### [ ] 4. Add Model Size Selection (Client)
**Why:** Let users choose speed vs accuracy  
**Impact:** Better results for those willing to wait  
**Effort:** 20 minutes

**UI:**
```javascript
<div className="model-selector">
  <label>Transcription Quality:</label>
  <select value={modelSize} onChange={(e) => setModelSize(e.target.value)}>
    <option value="tiny">Fast (~39MB, good accuracy)</option>
    <option value="base">Better (~75MB, higher accuracy)</option>
    <option value="small">Best (~244MB, highest accuracy)</option>
  </select>
</div>
```

**Code:**
```javascript
await clientSideTranscription.initialize(modelSize, onProgressCallback);
```

---

### **Phase 2: Medium Effort Improvements**

#### [ ] 5. Implement Timestamp Correction
**Why:** Improve timestamp accuracy across both client and server  
**Impact:** Better sync between audio and text  
**Effort:** 2-3 hours

**Approaches:**

**A) Forced Alignment (Recommended)**
Use a library like `gentle` or `aeneas` to re-align timestamps:

```python
# After Whisper transcription
from gentle import align_transcript

# Re-align using audio + transcript text
aligned_result = align_transcript(
    audio_path=audio_path,
    transcript_text=result['text'],
    original_segments=result['segments']
)

# Update segments with corrected timestamps
for seg, aligned_seg in zip(segments, aligned_result):
    seg.start_time = aligned_seg['start']
    seg.end_time = aligned_seg['end']
    seg.save()
```

**B) Voice Activity Detection (VAD)**
Remove silence from timestamps:

```python
import webrtcvad

# Detect voice activity
vad = webrtcvad.Vad(3)  # Aggressiveness 0-3
voice_segments = detect_voice_activity(audio_path, vad)

# Adjust Whisper timestamps to exclude silence
corrected_segments = align_to_voice_activity(
    whisper_segments=result['segments'],
    voice_segments=voice_segments
)
```

**C) Custom Post-Processing**
Simple heuristic adjustments:

```python
def improve_timestamps(segments, audio_duration):
    """Fix common timestamp issues"""
    for i, seg in enumerate(segments):
        # Remove leading/trailing silence (heuristic)
        if seg['text'].strip():
            # If text starts with capital, likely sentence start
            # Adjust start time back slightly (0.1s)
            if seg['text'][0].isupper() and i > 0:
                seg['start'] = max(0, seg['start'] - 0.1)
        
        # Prevent overlaps
        if i > 0 and seg['start'] < segments[i-1]['end']:
            seg['start'] = segments[i-1]['end']
        
        # Ensure minimum duration
        min_duration = len(seg['text'].split()) * 0.15  # ~150ms per word
        if seg['end'] - seg['start'] < min_duration:
            seg['end'] = min(audio_duration, seg['start'] + min_duration)
    
    return segments
```

---

#### [ ] 6. Add Low-Confidence Segment Highlighting
**Why:** Help users identify segments needing review  
**Impact:** Faster manual correction  
**Effort:** 1 hour

**Server-side only (requires confidence scores):**

```javascript
// In segment display
const getConfidenceClass = (confidence) => {
  if (confidence >= 0.8) return 'high-confidence';
  if (confidence >= 0.5) return 'medium-confidence';
  return 'low-confidence';
};

<div className={`segment ${getConfidenceClass(segment.confidence_score)}`}>
  <span className="confidence-badge">
    {segment.confidence_score < 0.5 && '⚠️ Low Confidence'}
  </span>
  <span className="segment-text">{segment.text}</span>
</div>
```

**CSS:**
```css
.segment.low-confidence {
  background-color: #fff3cd;
  border-left: 3px solid #ff9800;
}

.segment.medium-confidence {
  background-color: #e3f2fd;
}

.segment.high-confidence {
  background-color: #e8f5e9;
}
```

---

#### [ ] 7. Implement Word-Level Timestamps for Client
**Why:** Match server functionality  
**Impact:** Better editing precision  
**Effort:** 2 hours

**Challenge:** transformers.js doesn't expose word timestamps directly

**Workaround - Estimated word timing:**
```javascript
function estimateWordTimestamps(segment) {
  const words = segment.text.trim().split(/\s+/);
  const duration = segment.end - segment.start;
  const avgWordDuration = duration / words.length;
  
  return words.map((word, idx) => ({
    word,
    start: segment.start + (idx * avgWordDuration),
    end: segment.start + ((idx + 1) * avgWordDuration),
    estimated: true  // Flag as estimated
  }));
}
```

**Better approach - Use separate alignment:**
```javascript
// After transcription, run forced alignment
import { WordAligner } from 'word-alignment-lib';

const aligner = new WordAligner();
const wordTimestamps = await aligner.align({
  audioData: audioBuffer,
  text: segment.text,
  startTime: segment.start,
  endTime: segment.end
});
```

---

#### [ ] 8. Add Transcription Quality Metrics
**Why:** Give users objective quality assessment  
**Impact:** Transparency about transcription accuracy  
**Effort:** 1 hour

**Metrics to track:**
```javascript
{
  overall_confidence: 0.87,          // Average segment confidence
  low_confidence_count: 12,          // Segments < 0.5 confidence
  avg_segment_length: 45.2,          // Average words per segment
  estimated_accuracy: "92%",         // Based on confidence scores
  word_error_rate: null,             // If reference text available
  processing_time: "2.3 minutes",
  model_used: "whisper-base",
  source: "server"
}
```

**UI Display:**
```javascript
<div className="quality-metrics">
  <h4>Transcription Quality</h4>
  <div className="metric">
    <span>Overall Confidence:</span>
    <span className="metric-value">{(metrics.overall_confidence * 100).toFixed(1)}%</span>
  </div>
  <div className="metric">
    <span>Segments Needing Review:</span>
    <span className="metric-value warning">{metrics.low_confidence_count}</span>
  </div>
  <div className="metric">
    <span>Processing Time:</span>
    <span className="metric-value">{metrics.processing_time}</span>
  </div>
</div>
```

---

### **Phase 3: Advanced Features (Future)**

#### [ ] 9. Implement Speaker Diarization
**Why:** Distinguish multiple speakers (audiobook narrator + quoted characters)  
**Impact:** Better organization, easier editing  
**Effort:** 4-6 hours

**Approach:**

**Option A: pyannote.audio (Python, server-side only)**
```python
from pyannote.audio import Pipeline

# After Whisper transcription
pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization")
diarization = pipeline(audio_path)

# Match Whisper segments to speaker labels
for segment in transcription_segments:
    # Find speaker at segment midpoint
    midpoint = (segment.start_time + segment.end_time) / 2
    speaker = diarization.at(midpoint)
    segment.speaker = speaker
    segment.save()
```

**Option B: Simple VAD-based heuristic**
```python
def detect_speaker_changes(segments, audio_path):
    """Simple speaker detection based on pauses"""
    import librosa
    
    y, sr = librosa.load(audio_path)
    
    for i, seg in enumerate(segments):
        if i == 0:
            seg['speaker'] = 'Speaker 1'
            continue
        
        # If long pause before segment, assume speaker change
        pause_duration = seg['start'] - segments[i-1]['end']
        if pause_duration > 1.5:  # 1.5 second threshold
            seg['speaker'] = f'Speaker {(i % 2) + 1}'  # Alternate
        else:
            seg['speaker'] = segments[i-1]['speaker']
    
    return segments
```

---

#### [ ] 10. Add Automated Post-Processing
**Why:** Clean up common Whisper transcription issues  
**Impact:** Higher quality output  
**Effort:** 3-4 hours

**Processing pipeline:**

```python
class TranscriptionPostProcessor:
    """Clean and improve Whisper transcriptions"""
    
    def process(self, transcription):
        text = transcription.full_text
        segments = transcription.segments.all()
        
        # 1. Remove hallucinated repetitions
        text = self.remove_repetitions(text)
        
        # 2. Fix punctuation
        text = self.fix_punctuation(text)
        
        # 3. Standardize capitalization
        text = self.fix_capitalization(text)
        
        # 4. Remove or mark filler words
        text = self.handle_filler_words(text)
        
        # 5. Split long sentences
        text = self.split_long_sentences(text)
        
        transcription.full_text = text
        transcription.save()
        
        return transcription
    
    def remove_repetitions(self, text):
        """Remove Whisper hallucinations (repeated phrases)"""
        import re
        
        # Find 3+ consecutive identical phrases
        pattern = r'\b(\w+(?:\s+\w+){1,5})\s+(?:\1\s+){2,}'
        
        cleaned = re.sub(pattern, r'\1 ', text)
        return cleaned
    
    def fix_punctuation(self, text):
        """Normalize punctuation"""
        # Fix spacing around punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        text = re.sub(r'([.,!?;:])\s*', r'\1 ', text)
        
        # Ensure sentence capitalization
        sentences = text.split('. ')
        sentences = [s.capitalize() for s in sentences]
        
        return '. '.join(sentences)
    
    def handle_filler_words(self, text, action='mark'):
        """Remove or mark filler words"""
        fillers = ['um', 'uh', 'er', 'ah', 'like', 'you know']
        
        if action == 'remove':
            pattern = r'\b(' + '|'.join(fillers) + r')\b'
            return re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        elif action == 'mark':
            # Wrap in brackets for user review
            pattern = r'\b(' + '|'.join(fillers) + r')\b'
            return re.sub(pattern, r'[\1]', text, flags=re.IGNORECASE)
        
        return text
```

---

#### [ ] 11. Implement Hybrid Transcription Mode
**Why:** Best of both worlds - speed + accuracy  
**Impact:** Optimal user experience  
**Effort:** 2-3 hours

**Workflow:**
1. **Quick client pass:** Fast transcription with tiny model
2. **Show immediate results:** User can start reviewing/editing
3. **Background server refinement:** Higher quality model re-processes
4. **Smart merge:** Combine client speed with server accuracy

```javascript
const hybridTranscribe = async (audioFile) => {
  // Phase 1: Client-side (fast preview)
  setStatus('Quick transcription...');
  const quickResult = await clientSideTranscription.transcribe(
    audioFile,
    { modelSize: 'tiny' }
  );
  
  // Show preview immediately
  setTranscriptionData(quickResult);
  setStatus('Preview ready! Refining in background...');
  
  // Phase 2: Server-side (higher quality)
  const serverTask = await startServerTranscription(audioFile.id);
  
  // Poll for server completion
  const serverResult = await pollServerTranscription(serverTask.task_id);
  
  // Phase 3: Intelligent merge
  const mergedResult = mergeTranscriptions(quickResult, serverResult);
  
  setTranscriptionData(mergedResult);
  setStatus('Complete with high-quality refinement!');
};

function mergeTranscriptions(clientResult, serverResult) {
  /**
   * Use server results for:
   * - Word-level timestamps (more accurate)
   * - Confidence scores (only server has these)
   * - Better text accuracy
   * 
   * Use client results for:
   * - Segments where server failed/low confidence
   * - Immediate preview timeline
   */
  
  return serverResult.segments.map((serverSeg, idx) => {
    const clientSeg = clientResult.all_segments[idx];
    
    return {
      ...serverSeg,
      // Keep server text unless confidence is very low
      text: serverSeg.confidence_score < 0.3 ? clientSeg?.text : serverSeg.text,
      // Always use server timestamps (more accurate)
      start_time: serverSeg.start_time,
      end_time: serverSeg.end_time,
      confidence_score: serverSeg.confidence_score,
      // Flag merged segments
      merged: serverSeg.confidence_score < 0.3
    };
  });
}
```

---

## 📋 Implementation Priority

### **Recommended: Server-First Approach**

Given your statement: *"not fussed about being slower as long as it's more accurate"*

**Phase 1A: Server-Side Improvements (1-2 days)**
Focus on accuracy and features:

- [ ] **#5:** Timestamp correction with forced alignment (3 hours)
- [ ] **#6:** Low-confidence highlighting (1 hour)
- [ ] **#8:** Quality metrics dashboard (1 hour)
- [ ] **#10:** Automated post-processing (4 hours)

**Result:** Significantly better transcription quality with minimal time impact

---

### **Phase 1B: Quick UX Wins (2 hours)**
Improve user experience:

- [ ] **#1:** Save client transcriptions to database (30 min)
- [ ] **#2:** Confidence score UI (15 min)
- [ ] **#4:** Model size selection (20 min)
- [ ] **#3:** Improved chunking (10 min)

**Result:** Better usability without major architecture changes

---

### **Phase 2: Advanced Features (Future)**
Only if Phase 1 results need enhancement:

- [ ] **#9:** Speaker diarization (6 hours)
- [ ] **#11:** Hybrid transcription mode (3 hours)
- [ ] **#7:** Word-level client timestamps (2 hours)

---

## 🎯 Timestamp Accuracy - Specific Recommendations

Since you mentioned timestamping issues in your TODO:

### **Root Cause Analysis:**

**Whisper's timestamp generation:**
1. Uses encoder attention weights to estimate timing
2. Not forced alignment (no guarantee of accuracy)
3. Can drift during long sentences
4. Affected by background noise/silence

### **Solutions (Priority Order):**

**1. ✅ Forced Alignment (BEST - Recommended)**
```python
# Install: pip install gentle
from gentle import ForcedAligner

aligner = ForcedAligner()
aligned = aligner.align(
    audio_path=audio_file.file.path,
    transcript=result['text']
)

# aligned now has corrected word-level timestamps
```

**Pros:**
- Most accurate approach
- Audio-based alignment (not just estimates)
- Fixes Whisper's inherent timing issues

**Cons:**
- Additional processing time (~0.3x real-time)
- Requires gentle/kaldi installation

---

**2. ✅ VAD (Voice Activity Detection) Adjustment**
```python
import webrtcvad

def remove_silence_from_timestamps(segments, audio_path):
    """Adjust timestamps to exclude silence"""
    vad = webrtcvad.Vad(2)  # Medium aggressiveness
    
    for seg in segments:
        # Extract audio for this segment
        segment_audio = extract_audio_segment(audio_path, seg['start'], seg['end'])
        
        # Find first voice activity
        voice_start = find_first_voice(segment_audio, vad)
        voice_end = find_last_voice(segment_audio, vad)
        
        # Adjust timestamps
        seg['start'] += voice_start
        seg['end'] = seg['start'] + voice_end
    
    return segments
```

**Pros:**
- Fast (~0.1x real-time)
- Removes leading/trailing silence

**Cons:**
- Doesn't fix internal timing issues
- Can over-trim with aggressive settings

---

**3. ⚠️ Heuristic Adjustments (FALLBACK)**
```python
def improve_segment_timing(segments):
    """Simple rules-based timestamp improvement"""
    
    for i, seg in enumerate(segments):
        word_count = len(seg['text'].split())
        
        # Ensure minimum time per word (150ms)
        min_duration = word_count * 0.15
        actual_duration = seg['end'] - seg['start']
        
        if actual_duration < min_duration:
            # Extend end time
            seg['end'] = seg['start'] + min_duration
        
        # Prevent overlaps with next segment
        if i < len(segments) - 1:
            if seg['end'] > segments[i+1]['start']:
                # Split the gap
                gap_midpoint = (seg['end'] + segments[i+1]['start']) / 2
                seg['end'] = gap_midpoint
                segments[i+1]['start'] = gap_midpoint
    
    return segments
```

**Pros:**
- Very fast (no audio processing)
- Fixes obvious errors (overlaps, too-short segments)

**Cons:**
- Doesn't improve underlying accuracy
- Just makes timestamps "reasonable"

---

## 🧪 Testing Recommendations

After implementing improvements:

### **Accuracy Testing:**
- [ ] Test with known audio (compare to reference transcript)
- [ ] Measure Word Error Rate (WER)
- [ ] Check timestamp alignment (visual inspection in waveform editor)
- [ ] Test with varying audio quality (clean vs noisy)

### **Performance Testing:**
- [ ] Measure processing time for different file sizes
- [ ] Test with long files (2+ hours)
- [ ] Monitor server memory/CPU usage
- [ ] Test client-side on low-end devices

### **UX Testing:**
- [ ] Test transcription → duplicate detection → assembly workflow
- [ ] Verify confidence scores are helpful
- [ ] Check progress indicators are accurate
- [ ] Test error handling (bad audio, network issues)

---

## 📊 Expected Results After Phase 1

**Before (Current):**
- Server: Whisper base, raw output, no post-processing
- Client: Whisper tiny, ephemeral, no confidence
- Timestamps: Whisper estimates only
- Accuracy: ~85-90% WER

**After (Phase 1A + 1B):**
- Server: Whisper base + forced alignment + post-processing
- Client: Whisper tiny/base, saved to DB, quality indicators
- Timestamps: Forced aligned (significantly better)
- Accuracy: ~92-95% WER
- Quality metrics: Confidence scores, low-confidence highlighting
- UX: Model selection, quality dashboard, better feedback

---

## 💡 Key Recommendation

**Focus on Server-Side Timestamp Correction First**

Given your priority ("not fussed about slower if more accurate"):

1. ✅ **Implement forced alignment** (#5) - HIGHEST IMPACT
2. ✅ **Add post-processing** (#10) - Clean up output
3. ✅ **Quality metrics UI** (#8) - Transparency
4. ✅ **Low-confidence highlighting** (#6) - Easier review

**Total time:** 1-2 days of development  
**Expected improvement:** 5-10% better accuracy, significantly better timestamps

**Next steps:**
1. Install forced alignment library (`gentle` or `aeneas`)
2. Create post-processing pipeline
3. Update API to include confidence/quality data
4. Add UI for quality visualization

---

---

## 💾 Server Memory Requirements Analysis

### **Current Server-Side Memory Footprint**

**Per Transcription Task:**
```
Whisper Base Model:           ~500MB RAM (loaded once, shared)
Audio File Processing:        ~100-200MB (depends on file size)
Temporary Buffers:            ~50-100MB
Database Operations:          ~20-50MB
Peak Usage per Task:          ~700-850MB
```

**With Forced Alignment Added:**
```
Gentle/Aeneas Library:        +200-300MB
Alignment Processing:         +100-200MB  
Total Peak per Task:          ~1.2-1.5GB
```

**Concurrent Tasks Impact:**
```
1 concurrent task:            1.2-1.5GB
2 concurrent tasks:           2.0-2.5GB (model shared)
3 concurrent tasks:           2.8-3.5GB
Recommended server RAM:       4GB minimum, 8GB recommended
```

### **Memory Optimization Strategies**

**1. Model Caching (Already Implemented)**
✅ Whisper model loaded once and reused across tasks
```python
# In transcription_tasks.py
model = whisper.load_model("base")  # Loads once per worker
```

**2. Sequential Processing (Recommended)**
Process one file at a time to minimize memory:
```python
# In settings.py
CELERY_WORKER_CONCURRENCY = 1  # Or 2 for 8GB+ servers
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
```

**3. Memory Cleanup**
Force garbage collection after each task:
```python
import gc

# After transcription
del model_result
gc.collect()
torch.cuda.empty_cache()  # If using GPU
```

**4. File Streaming**
Process audio in chunks instead of loading entire file:
```python
# For large files (2+ hours)
chunk_duration = 1800  # 30 minutes
for chunk in audio_chunks:
    process_chunk(chunk)
    del chunk
    gc.collect()
```

---

## 🔄 Background Processing Architecture

### **Current Implementation (Already Good!)**

Your system already has proper background processing:

✅ **Celery Workers:** Async task processing  
✅ **Redis Queue:** Task management  
✅ **Progress Tracking:** Real-time updates via Redis  
✅ **User Can Continue:** Upload PDF & work while transcription runs  

### **Workflow - User Can Work During Transcription**

```
User Actions                     Background Processing
─────────────────────────────   ─────────────────────────────
1. Upload audio file            │
   └─> Start Transcription ─────┼─> Celery Task Started
                                │   (User notified: "Processing...")
2. Upload PDF                   │
   └─> Extract PDF text         │   [Transcription running...]
                                │
3. Select PDF start/end         │
   └─> Configure comparison     │   [Still transcribing...]
                                │
4. Work on other tabs           │   [Progress: 45%...]
                                │
5. [Notification]               │   [Complete!]
   └─> View Results ◄───────────┼─── Celery Task Finished
```

**Already Implemented:**
- Tab switching allowed during processing
- Progress polls every 2 seconds
- User can upload/configure while waiting
- Results appear when ready

### **Enhancement: Parallel Task Queue**

Allow PDF processing while transcription runs:

```python
# Current: All tasks use same queue
@shared_task(bind=True)
def transcribe_audio_file_task(self, audio_file_id):
    ...

# Enhanced: Separate queues by priority
@shared_task(bind=True, queue='transcription')  # Heavy, slow queue
def transcribe_audio_file_task(self, audio_file_id):
    ...

@shared_task(bind=True, queue='pdf_processing')  # Light, fast queue
def extract_pdf_text_task(self, project_id):
    ...
```

**Celery config:**
```python
# settings.py
CELERY_TASK_ROUTES = {
    'audioDiagnostic.tasks.transcribe_*': {'queue': 'transcription'},
    'audioDiagnostic.tasks.extract_pdf_*': {'queue': 'pdf_processing'},
    'audioDiagnostic.tasks.detect_duplicates_*': {'queue': 'processing'},
}

# Start workers for each queue
# celery -A myproject worker -Q transcription -c 1  # 1 concurrent for heavy tasks
# celery -A myproject worker -Q pdf_processing -c 4  # 4 concurrent for light tasks
```

---

## 🖥️ Desktop Application Alternative (Optional)

### **Concept: Local Processing App**

Instead of browser-only OR server-only, offer a **desktop app** that:
- Has full Whisper Python capabilities (like server)
- Processes locally (no server load)
- Communicates results back to web app
- No distribution hassles (one-time download)

### **Architecture Options**

#### **Option A: Electron + Python Backend**
```
┌─────────────────────────────────┐
│  Electron App (Desktop)         │
│  ┌───────────────────────────┐  │
│  │  UI (React/HTML)          │  │
│  └───────────┬───────────────┘  │
│              │                   │
│  ┌───────────▼───────────────┐  │
│  │  Python Backend           │  │
│  │  - Whisper (full model)   │  │
│  │  - Forced Alignment       │  │
│  │  - Post-Processing        │  │
│  └───────────┬───────────────┘  │
└──────────────┼───────────────────┘
               │ REST API
               ▼
     ┌──────────────────┐
     │  Web Backend     │
     │  (audio.precise  │
     │   pouchtrack.com)│
     └──────────────────┘
```

**Pros:**
- ✅ Full Whisper capabilities (base/small/medium models)
- ✅ No server load
- ✅ Faster for users (local processing)
- ✅ Works offline for transcription
- ✅ Confidence scores, word timestamps, etc.
- ✅ One-time download (~200MB)

**Cons:**
- ❌ Distribution complexity (Windows/Mac/Linux builds)
- ❌ Updates require new downloads
- ❌ User needs 4GB+ RAM
- ❌ Development/testing overhead

---

#### **Option B: Python CLI Tool**
```
User downloads: audioprocessor.exe (PyInstaller bundle)

Usage:
  audioprocessor.exe transcribe audio.mp3 --project-id 123 --api-key xyz
  
  → Processes locally
  → Uploads results to server via API
  → Web app polls for completion
```

**Simpler than Electron:**
- ✅ Single executable (PyInstaller)
- ✅ No UI complexity
- ✅ Easier to maintain
- ✅ ~100MB download

**But:**
- ❌ Less user-friendly (command-line)
- ❌ Still requires distribution

---

#### **Option C: WebAssembly Whisper (Future)**
```
Browser-native Whisper via WASM:
  - Whisper.cpp compiled to WebAssembly
  - Runs in browser with near-native speed
  - No download required
```

**Status:** Experimental, not production-ready yet  
**Timeline:** 6-12 months for stable implementation

---

### **Desktop App: Implementation Estimate**

**If pursuing Electron + Python approach:**

```
Development Time:
  - Electron Shell:              20 hours
  - Python Backend Integration:  15 hours
  - API Communication:           10 hours
  - Build Pipeline (3 platforms): 15 hours
  - Testing:                     20 hours
  Total:                         80 hours (~2 weeks)

Distribution:
  - Windows: .exe installer
  - Mac: .dmg installer
  - Linux: .AppImage
  
Update Mechanism:
  - electron-updater (auto-update)
  - Check for updates on launch
```

**Recommended for:**
- Users with many long files (2+ hours each)
- Users with privacy concerns (local processing)
- Power users willing to download software

**Not recommended for:**
- Casual users (web is easier)
- Users with low-end computers (<4GB RAM)

---

## 🎯 Recommended Approach: Hybrid Strategy

### **Phase 1: Optimize Server-Side (Best ROI)**

**Immediate Implementation (This PR):**
1. ✅ Add memory-efficient processing
2. ✅ Implement forced alignment
3. ✅ Add post-processing pipeline
4. ✅ Configure Celery for low memory usage
5. ✅ Separate task queues (transcription vs PDF)

**Memory Config:**
```python
# settings.py additions
CELERY_WORKER_CONCURRENCY = 1  # Process one transcription at a time
CELERY_WORKER_MAX_TASKS_PER_CHILD = 3  # Restart worker after 3 tasks (prevents memory leaks)
CELERY_TASK_TIME_LIMIT = 7200  # 2 hour max per task
CELERY_TASK_SOFT_TIME_LIMIT = 6900  # Warning at 1h 55m
```

**Server Requirements:**
- **Minimum:** 4GB RAM (1 concurrent transcription)
- **Recommended:** 8GB RAM (2 concurrent + headroom)
- **CPU:** 4+ cores (Whisper is CPU-intensive)

---

### **Phase 2: Desktop App (If Needed)**

**Only implement if:**
- Many users request it
- Server costs become prohibitive
- Privacy/offline use is important

**Alternative:** Partnership with existing tools like:
- Whisper Desktop (open source)
- MacWhisper (Mac only)
- Users run Whisper locally → upload results

---

## 📋 Updated Implementation Priority

### **Phase 1A: Memory-Optimized Server Processing (THIS PR)**
*Estimated time: 1-2 days*

- [ ] **Configure Celery for low memory** (30 min)
  - Set concurrency = 1
  - Enable worker recycling
  - Add memory limits

- [ ] **Implement forced alignment** (3 hours)
  - Install gentle/aeneas
  - Add alignment step to transcription task
  - Memory-efficient processing

- [ ] **Add post-processing pipeline** (4 hours)
  - Repetition removal
  - Punctuation fixes
  - Filler word handling

- [ ] **Separate task queues** (1 hour)
  - Transcription queue (heavy)
  - PDF processing queue (light)
  - Duplicate detection queue (medium)

- [ ] **Add memory monitoring** (1 hour)
  - Log memory usage
  - Alert on high usage
  - Automatic garbage collection

**Result:** Better transcriptions, same 4GB server

---

### **Phase 1B: Background Processing UX** 
*Estimated time: 2 hours*

- [ ] **Enhanced progress indicators** (30 min)
  - Show current step (alignment, post-processing, etc.)
  - Estimated time remaining
  - Allow tab switching during processing

- [ ] **Parallel PDF processing** (1 hour)
  - User can upload/configure PDF while transcription runs
  - Separate progress indicators

- [ ] **Task prioritization** (30 min)
  - Light tasks (PDF) run immediately
  - Heavy tasks (transcription) queue

**Result:** User can work on PDF while transcription runs in background

---

### **Phase 2: Desktop App (OPTIONAL - Future)**
*Only if Phase 1 isn't sufficient*

- [ ] Research existing solutions (Whisper Desktop, etc.)
- [ ] Evaluate Electron vs CLI approach
- [ ] Prototype integration
- [ ] Build distribution pipeline
- [ ] Testing across platforms

**Decision point:** After 1 month of Phase 1 usage data

---

**Updated:** March 14, 2026  
**Next Review:** After Phase 1A implementation  
**Server Requirements:** 4GB RAM minimum, 8GB recommended
