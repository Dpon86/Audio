# Duplicate Detection Optimization TODO

## 📊 Current State Analysis

### Client-Side Algorithm
- ✅ **Fast:** O(n) complexity - single pass
- ❌ **Exact match only** - misses partial duplicates
- ❌ **Aggressive normalization** - removes ALL punctuation
- ❌ **No fuzzy matching** - despite having Jaccard similarity code
- ❌ **Algorithm selection doesn't work** - always uses exact match

### Server-Side Algorithms (Already Implemented)
- ✅ **TF-IDF Cosine Similarity:** Semantic matching with sklearn
- ✅ **Windowed Retry:** Optimized for narrator restarts (O(n × window))
- ✅ **Windowed Retry + PDF:** Uses PDF text to prevent false positives
- ✅ **Celery async processing:** Background tasks with progress tracking
- ✅ **Redis progress updates:** Real-time user feedback

---

## 🎯 Recommended Approach: Server-Side First

### Why Server-Side is Better for Your Use Case

**You said:** "I am not fussed about detection duplicates being a bit slower as long as it gets more of the duplicates"

**Analysis:**
1. **Server algorithms already exist** - fully implemented and tested
2. **Windowed algorithm is efficient** - O(n × 100) not O(n²)
3. **Celery handles the load** - async processing prevents UI blocking
4. **More accurate results** - catches partial matches and variations
5. **No client memory limits** - can handle large transcripts easily

### Server Load Assessment

**Will server duplicate detection be too heavy?**

**Answer: NO - Server is well-equipped**

Evidence:
- ✅ You're already using server-side detection successfully
- ✅ Windowed algorithm designed for efficiency (max 100 lookahead)
- ✅ Celery runs as background worker (doesn't block requests)
- ✅ Redis provides progress tracking
- ✅ No performance issues reported so far

**Resource Requirements by Algorithm:**

| Algorithm | Complexity | Memory | CPU | For 1000 segments |
|-----------|-----------|--------|-----|-------------------|
| **Windowed Retry** | O(n × 100) | Low | Medium | ~100k comparisons |
| **Windowed + PDF** | O(n × 100) | Low | Medium | ~100k comparisons + PDF lookups |
| **TF-IDF Cosine** | O(n²) | High | High | ~1M comparisons |

**Recommendation:** Use **Windowed Retry + PDF** for best accuracy/performance balance

---

## ✅ Quick Wins (Immediate Implementation)

### [ ] 1. Fix Client-Side Normalization
**Why:** Client removes ALL punctuation; server keeps it  
**Impact:** Better matches when client fallback is used  
**Effort:** 5 minutes

**File:** `frontend/src/services/clientDuplicateDetection.js`

```javascript
// BEFORE
normalizeText(text) {
    return text.replace(/[^\w\s]/g, ' ')  // Too aggressive
        .toLowerCase()
        .replace(/\s+/g, ' ')
        .trim();
}

// AFTER (match server behavior)
normalizeText(text) {
    // Remove [123] or [-1] prefixes like server
    text = text.replace(/^\[\-?\d+\]\s*/, '');
    // Keep punctuation, just normalize whitespace + lowercase
    return text.trim().toLowerCase().replace(/\s+/g, ' ');
}
```

---

### [ ] 2. Enable Client Fuzzy Matching
**Why:** Activate existing Jaccard similarity code  
**Impact:** Client catches more duplicates (better than exact match)  
**Effort:** 2 minutes

**File:** `frontend/src/components/ProjectTabs/Tab3Duplicates.js`

```javascript
// Find where detectDuplicates is called (around line 1450)
const results = await detector.detectDuplicates(processedSegments, {
    similarityThreshold: 0.85  // Add this option (0.85 = 85% similar)
});
```

---

### [ ] 3. Fix Algorithm Selection UI
**Why:** Dropdown shows algorithms but client always uses exact match  
**Impact:** Clearer user expectations  
**Effort:** 10 minutes

**Options:**
- **A)** Hide algorithm dropdown when using client-side detection
- **B)** Make client respect algorithm selection (implement multiple client algorithms)
- **C)** Show "Client: Exact Match" as fixed option when client-side enabled

**Recommended:** Option A (simplest)

---

## 🚀 Server-Side Optimizations (Recommended Path)

### [ ] 4. Set Windowed Retry as Default Algorithm
**Why:** Best balance of speed + accuracy  
**Impact:** Faster processing, still catches narrator retries  
**Effort:** 1 minute

**File:** `backend/audioDiagnostic/views/tab3_duplicate_detection.py`

```python
# Change default algorithm parameter
algorithm = request.GET.get('algorithm', 'windowed_retry')  # Instead of 'tfidf_cosine'
```

---

### [ ] 5. Optimize Windowed Parameters
**Why:** Fine-tune for audiobook narration patterns  
**Impact:** Better duplicate detection for your specific use case  
**Effort:** Testing + tweaking

**Current Defaults (from code):**
```python
max_lookahead = 100          # How far ahead to search
ratio_threshold = 0.80       # Minimum similarity (weak match)
strong_match_ratio = 0.92    # High similarity threshold
min_word_length = 1          # Minimum word length to consider
```

**Recommended Tuning for Audiobooks:**
```python
max_lookahead = 150          # Narrator might re-record further ahead
ratio_threshold = 0.75       # Slightly lower to catch more variations
strong_match_ratio = 0.90    # Slightly lower for narrator variations
min_word_length = 2          # Skip very short words (a, I, to)
```

**Where to change:** `backend/audioDiagnostic/tasks/duplicate_tasks.py` (task parameters)

---

### [ ] 6. Enable PDF Hints by Default
**Why:** Prevents false positives from similar text in different chapters  
**Impact:** Higher precision (fewer wrong duplicates)  
**Effort:** 1 minute

**File:** `frontend/src/components/ProjectTabs/Tab3Duplicates.js`

```javascript
// When calling server-side detection
const params = {
    algorithm: 'windowed_retry_pdf',  // Use PDF variant
    use_pdf_hint: true                // Enable hints
};
```

---

### [ ] 7. Add Server-Side Progress Granularity
**Why:** Better user feedback during detection  
**Impact:** User sees "Comparing segments 450/1000..." instead of generic progress  
**Effort:** 30 minutes

**File:** `backend/audioDiagnostic/tasks/duplicate_tasks.py`

```python
# Inside build_groups_windowed_retry
for i in range(total_segments):
    if i % 50 == 0:  # Every 50 segments
        progress = 40 + int((i / total_segments) * 20)
        r.set(f"progress:{task_id}", progress)
        self.update_state(state='PROGRESS', meta={
            'progress': progress,
            'message': f'Analyzing segment {i}/{total_segments}...'
        })
```

---

## 🔧 Optional Enhancements

### [ ] 8. Implement Two-Pass Detection (Hybrid Approach)
**Why:** Quick client scan, then deep server analysis  
**Impact:** Immediate feedback + comprehensive results  
**Effort:** 2-3 hours

**Workflow:**
1. **Client-side (fast):** Find obvious exact duplicates in <1 second
2. **Show preview:** "Found 45 exact duplicates, analyzing for more..."
3. **Server-side (deep):** Run windowed_retry_pdf in background
4. **Update results:** Add fuzzy matches found by server
5. **Final count:** "Found 102 total duplicates (45 exact + 57 partial)"

**Pros:**
- Instant user feedback
- Best of both worlds
- Progressive enhancement

**Cons:**
- More complex implementation
- Need to merge client + server results
- Potential UI confusion during transition

---

### [ ] 9. Add Common Word Ratio Check (Client-Side)
**Why:** Fast pre-filter before expensive similarity calculation  
**Impact:** 2-3x faster fuzzy matching  
**Effort:** 30 minutes

**File:** `frontend/src/services/clientDuplicateDetection.js`

```javascript
commonWordRatio(text1, text2) {
    const words1 = new Set(text1.split(/\s+/));
    const words2 = new Set(text2.split(/\s+/));
    const overlap = [...words1].filter(w => words2.has(w)).length;
    return overlap / Math.min(words1.size, words2.size);
}

// In detectDuplicates, before calculateSimilarity:
const wordOverlap = this.commonWordRatio(normalized1, normalized2);
if (wordOverlap < 0.45) continue;  // Skip: too different
```

---

### [ ] 10. Implement Length Sanity Check
**Why:** Avoid comparing vastly different segments  
**Impact:** 10-20% faster processing  
**Effort:** 5 minutes

**File:** `frontend/src/services/clientDuplicateDetection.js`

```javascript
// Before similarity calculation
const longLen = Math.max(text1.length, text2.length);
const shortLen = Math.min(text1.length, text2.length);
const maxDiff = Math.max(50, longLen * 0.55);
if (longLen - shortLen > maxDiff) {
    continue;  // Too different in length
}
```

---

## 📋 Implementation Priority

### **Phase 1: Server-First Approach (Recommended)**
Maximize accuracy using existing server infrastructure

- [ ] **#4:** Set windowed_retry as default (1 min)
- [ ] **#6:** Enable PDF hints by default (1 min)
- [ ] **#5:** Tune windowed parameters for audiobooks (testing)
- [ ] **#7:** Add progress granularity (30 min)

**Result:** Better duplicate detection with no heavy lifting on client

---

### **Phase 2: Client Improvements (Optional)**
Improve client-side fallback for offline/quick scans

- [ ] **#1:** Fix normalization to match server (5 min)
- [ ] **#2:** Enable fuzzy matching (2 min)
- [ ] **#3:** Fix algorithm selection UI (10 min)

**Result:** Client-side becomes useful for quick previews

---

### **Phase 3: Advanced Features (Future)**
Only if Phase 1 isn't sufficient

- [ ] **#8:** Hybrid two-pass detection (2-3 hours)
- [ ] **#9:** Add word ratio pre-filter (30 min)
- [ ] **#10:** Length sanity check (5 min)

---

## 🎯 Final Recommendation

**Use Server-Side Detection Exclusively**

**Why:**
1. ✅ **Already built** - windowed_retry and PDF algorithms exist
2. ✅ **Optimized** - designed for efficiency (O(n × 100) not O(n²))
3. ✅ **Accurate** - catches partial duplicates, narrator retries, variations
4. ✅ **Async** - Celery handles background processing
5. ✅ **Your preference** - "not fussed about being slower"

**Server Load Answer:**
**NO, server will NOT be overloaded**
- Windowed algorithm is efficient (~100k comparisons for 1000 segments)
- Celery workers handle async processing
- Redis provides progress updates
- You're already using it successfully

**Next Steps:**
1. Implement Phase 1 (server optimizations) - **10 minutes total**
2. Test with your audiobook transcripts
3. Tune parameters based on results
4. Only add client improvements if needed for offline use

---

## 📊 Algorithm Comparison Reference

### Server Normalization
```python
def normalize(text):
    text = re.sub(r'^\[\-?\d+\]\s*', '', text)  # Remove [123]
    return ' '.join(text.strip().lower().split())
```
- Keeps punctuation
- Removes segment number prefixes
- Normalizes whitespace

### Client Normalization (Current - Too Aggressive)
```javascript
normalizeText(text) {
    return text.replace(/[^\w\s]/g, ' ')  // REMOVES punctuation
        .toLowerCase()
        .replace(/\s+/g, ' ')
        .trim();
}
```
- Removes ALL punctuation (too aggressive)
- No prefix removal
- Same whitespace normalization

### Server Windowed Algorithm Features
1. **Sliding window** - only compares nearby segments (narrator retries are close)
2. **Multi-tier matching:**
   - Quick length check (reject vastly different segments)
   - Word overlap ≥ 45% (fast pre-filter)
   - Strong match: similarity ≥ 92%
   - Weak match: similarity ≥ 80% AND overlap ≥ 58%
3. **PDF anchoring** - prevents false positives across chapters
4. **Graph clustering** - finds connected duplicate groups

### Client Algorithm (Current)
1. **Exact match only** - no fuzzy logic
2. **Map-based grouping** - O(n) single pass
3. **No windowing** - compares everything to everything
4. **Jaccard similarity exists but unused** - threshold always 1.0

---

## 🔍 Testing Checklist

After implementing changes:

- [ ] Test with small file (50 segments) - verify correctness
- [ ] Test with medium file (500 segments) - check performance
- [ ] Test with large file (2000+ segments) - ensure no timeout
- [ ] Verify PDF hints reduce false positives
- [ ] Check progress updates work smoothly
- [ ] Confirm all marked segments are removed in assembly
- [ ] Validate time reduction percentage is accurate

---

**Updated:** March 14, 2026  
**Next Review:** After Phase 1 implementation
