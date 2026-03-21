# Duplicate Detection — Analysis & Improvement Plan

> **Date:** March 2026  
> **Status:** Assessment + Actionable Improvement Plan  
> **Related issue:** Detection misses 3rd occurrence of identical/near-identical narrator re-reads  

---

## 1. What the System Does Now

### Architecture Overview

```
Audio file
  └─ Whisper transcribes → TranscriptionSegment rows (sentence-level, with start/end times)
                           TranscriptionWord rows (word-level timestamps — stored but not used in detection)
  └─ User picks algorithm in Tab 3
  └─ Celery task: detect_duplicates_single_file_task
       ├─ Algorithm 1: tfidf_cosine     (global, TF-IDF cosine similarity)
       ├─ Algorithm 2: windowed_retry   (rolling 150-segment window, SequenceMatcher)
       └─ Algorithm 3: windowed_retry_pdf  (same + PDF position gate)  ← DEFAULT
  └─ DuplicateGroup records created; segments marked is_duplicate / is_kept
  └─ refine_duplicate_timestamps_task snaps audio cut-points to silence boundaries
  └─ User reviews in WaveformDuplicateEditor; can drag boundaries
```

---

## 2. The Three Algorithms — Current State

### Algorithm 1: `tfidf_cosine`

| Aspect | Detail |
|--------|--------|
| Comparison scope | **Global** — every segment vs. every other |
| Method | TF-IDF n-gram vectors (1–3 grams), cosine similarity |
| Default threshold | 0.85 |
| Pre-filtering | None (computes full n×n matrix) |

**Strengths:**
- Catches duplicates anywhere in the file regardless of distance
- Good at structurally similar but non-identical sentences (e.g., paraphrases)
- N-gram coverage handles partial word matches

**Weaknesses:**
- TF-IDF is trained on the same corpus being compared → common words like "the", "her", "and" inflate similarity between unrelated segments
- Two structurally similar but semantically different segments can hit 0.85 (false positives)
- Misses cases where the 3rd occurrence differs slightly (one mis-transcribed word drops it below 0.85)
- **The `processed_indices` logic is greedy and order-dependent:** Once segment `i` joins a group, all its future matches are skipped. If segment `A` matches `B` (cosine ≥ 0.85), and `B` matches `C` but `A`→`C` is only 0.84, then `C` is missed entirely because `B` was already processed.

### Algorithm 2: `windowed_retry`

| Aspect | Detail |
|--------|--------|
| Comparison scope | Rolling window — each segment looks forward up to **150 segments** |
| Method | SequenceMatcher character ratio + Jaccard word overlap |
| Primary threshold | ratio ≥ 0.90 (strong match), OR ratio ≥ 0.75 + overlap ≥ 0.58 |
| Pre-filters | Length difference, Jaccard overlap < 0.45 |
| Grouping | Connected components (DFS over adjacency graph) |

**Strengths:**
- Connected components correctly handles transitive relationships:  
  if A↔B and B↔C, even if A and C are 200 segments apart, all three end up in the same group
- SequenceMatcher character ratio is good for near-identical text with minor transcription errors
- Pre-filters make it fast

**Weaknesses — why the 3rd occurrence is missed:**

1. **The 150-segment window is a hard cutoff.** If occurrence 1 is at segment 20, occurrence 2 at segment 50, occurrence 3 at segment 220:
   - 1↔2: connected (within 150) ✓
   - 2↔3: within 150 of each other only if |50–220| ≤ 150 → **not connected** (170 segments apart) ✗
   - 1↔3: 200 segments apart → **not connected** ✗
   - Result: group {1, 2} is found; occurrence 3 is missed entirely

2. **Length difference pre-filter is aggressive:**  
   `(long_len - short_len) > max(8, 0.55 * long_len)` — if Whisper splits a long sentence into two parts and then transcribes the full sentence a second time, the length difference will reject the comparison before SequenceMatcher even runs.

3. **Jaccard overlap < 0.45 cutoff rejects partial matches:**  
   If Whisper mis-transcribes 3+ key words in one version (e.g., names, unusual nouns), the word overlap can drop below 0.45 even for obvious duplicates.

4. **Short segments (< 2 words) are skipped entirely** — short interjections, phrases, and half-sentences from split transcriptions are never compared.

### Algorithm 3: `windowed_retry_pdf`

Same as Algorithm 2, plus an extra gate: if two segments map to positions > 1200 characters apart in the PDF, the match is rejected unless ratio ≥ 0.90. This prevents false positives from recurring phrases in different chapters.

**Additional weakness:** PDF position estimation uses only the first 4–10 words as a phrase anchor. If the first words of the segment differ between occurrences (Whisper transcribes the start differently), `estimate_pdf_anchor` returns `None` for that occurrence, so the position gate doesn't apply — this part works correctly. But if the PDF text has minor differences from the spoken text (e.g., an author's stylistic change), the anchor lookup can fail, causing the position check to incorrectly allow or block the match.

---

## 3. Root Causes of Missed Duplicates

### Case: 3 occurrences, only 2 found

For "Her mother, the once countess of Bedford, dismissed her suspicions as nonsense, blinded":

**Most likely causes (in order of probability):**

1. **Window gap (most likely):** The 3rd occurrence is > 150 segments after the 2nd. Since they're not directly connected, and the 1st occurrence is also > 150 segments from the 3rd, the connected component only contains the first two.

2. **Length variation:** One version has the full sentence; another is a resumed read that starts mid-sentence (narrator paused and re-recorded from "blinded" onwards) creating a short fragment that fails the length pre-filter.

3. **Transcription divergence:** Whisper transcribes proper nouns inconsistently — "Bedford" might appear as "Bedfort" or "Bedfield" in one pass, dropping the character ratio below 0.90 and the word overlap below 0.58 (two unique words changed = ~15% of a 13-word sentence).

4. **Segment boundary split:** In one occurrence, Whisper splits the sentence across two segments:
   - `"Her mother, the once countess of Bedford,"`
   - `"dismissed her suspicions as nonsense, blinded"`  
   Neither half alone matches the full sentence at the required ratios.

---

## 4. Transcription Format Analysis

### Current Format

Whisper produces sentence-level segments with start/end times. The system stores:
- `TranscriptionSegment.text` — the sentence text
- `TranscriptionSegment.start_time`, `end_time` — timestamps
- `TranscriptionWord.word`, `start_time`, `end_time` — **already stored but NEVER used in detection**

### Why Word-Level Timestamps Would Help

If a narrator records:
> "Her mother, the once countess of Bedford..." then pauses mid-sentence

Whisper may produce one segment `[0s–14s]` for the full sentence, but in the retry it may produce:
- `[245s–247s]` "dismissed her suspicions"  
- `[247s–253s]` "as nonsense, blinded"

These are sub-sentence fragments. Word-level timestamps would let us reconstruct that both fragments together form the same sentence, making them detectable.

### Current Normalization (`normalize()`)

```python
def normalize(text):
    text = re.sub(r'^\[\-?\d+\]\s*', '', text)  # remove [N] prefixes
    return ' '.join(text.strip().lower().split())  # lowercase + whitespace collapse
```

**Missing normalizations that would improve matching:**
- Punctuation is kept — "Bedford," vs "Bedford" causes character ratio divergence
- Numbers and ordinals not normalized ("3rd" vs "third")
- Common name variations not handled
- No stemming — "suspicions" vs "suspicion" counts as different

---

## 5. Proposed Improvements

### Priority 1 — Increase the Window (Quick Win, High Impact)

**Change:** Increase `window_max_lookahead` from 150 to 400.

**Effect:** A narrator might restart a section many sentences later. In a typical audiobook chapter, 150 segments ≈ 10–15 minutes of audio. The narrator might restart a page 20+ minutes after the first reading (400+ segments).

**Trade-off:** Detection takes longer (seconds per file, not minutes). Completely acceptable per user requirements ("I am happy for it to take longer").

**Implementation:** Change the default in `duplicate_tasks.py` line 1045:
```python
window_max_lookahead = 400 if window_max_lookahead is None else int(window_max_lookahead)
```
Also expose this as a UI control in Tab 3 → Algorithm Settings.

---

### Priority 2 — Fix the `tfidf_cosine` Grouping Bug (Medium effort, fixes false negatives)

**Problem:** The current `processed_indices` logic prevents `C` from joining a group if `B` was already processed, even if `B↔C` is a valid match.

**Fix:** Replace the greedy single-pass with connected components (same as Algorithm 2):

```python
def build_groups_with_tfidf(segments, normalized_texts, similarity_threshold=0.85):
    vectorizer = TfidfVectorizer(ngram_range=(1, 3), min_df=1, max_df=0.9)
    tfidf_matrix = vectorizer.fit_transform(normalized_texts)
    similarity_matrix = cosine_similarity(tfidf_matrix)
    
    # Build adjacency graph
    adjacency = defaultdict(set)
    n = len(segments)
    for i in range(n):
        for j in range(i + 1, n):
            if similarity_matrix[i][j] >= similarity_threshold:
                adjacency[i].add(j)
                adjacency[j].add(i)
    
    # Connected components via DFS
    visited = set()
    duplicate_groups = []
    for start in range(n):
        if start in visited or start not in adjacency:
            continue
        stack, component = [start], []
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            stack.extend(adjacency[node] - visited)
        if len(component) > 1:
            duplicate_groups.append(sorted(component))
    
    return duplicate_groups
```

This ensures indirect connections (A↔B, B↔C → group {A,B,C}) are always captured.

---

### Priority 3 — Multi-Pass Detection Strategy (Highest Impact, More Work)

**Concept:** Run multiple passes at different sensitivity levels and merge results.

#### Pass 1 — Anchor Phrase Fingerprinting (New)

Build an inverted index of distinctive 5-word phrases. Any two segments sharing a distinctive phrase are candidates:

```python
from collections import defaultdict

def anchor_phrase_pass(segments, normalized_texts, phrase_len=5, min_phrase_frequency=1):
    """Find segments sharing rareN-gram phrases — no window limit."""
    phrase_index = defaultdict(list)
    
    for i, text in enumerate(normalized_texts):
        words = text.split()
        for start in range(len(words) - phrase_len + 1):
            phrase = ' '.join(words[start:start + phrase_len])
            phrase_index[phrase].append(i)
    
    adjacency = defaultdict(set)
    for phrase, indices in phrase_index.items():
        # Only treat as signal if the phrase is "rare" (not a stock phrase)
        if 2 <= len(indices) <= 6:  # appears 2-6 times = likely a retry, not a common phrase
            for a in indices:
                for b in indices:
                    if a != b:
                        adjacency[a].add(b)
    
    # Build groups from adjacency
    ...
```

**Advantage:** Catches duplicates regardless of distance. Distinctive 5-word phrases like "once countess of Bedford dismissed" will appear in only the narrator re-reads, not random other segments.

#### Pass 2 — Sub-Sentence Greedy Match (New)

For short segments (< 8 words), check whether the full text of the short segment appears embedded in any longer segment:

```python
def sub_sentence_pass(segments, normalized_texts):
    """Catch cases where one occurrence is a sentence fragment matching part of a longer read."""
    adjacency = defaultdict(set)
    
    for i, short_text in enumerate(normalized_texts):
        if len(short_text.split()) >= 8:
            continue  # only look at short segments as candidates
        for j, long_text in enumerate(normalized_texts):
            if i == j or len(long_text.split()) < 8:
                continue
            # Check if short_text appears as a subsequence in long_text
            if short_text in long_text or SequenceMatcher(None, short_text, long_text[:len(short_text)*2]).ratio() >= 0.85:
                adjacency[i].add(j)
                adjacency[j].add(i)
    
    return adjacency
```

#### Pass 3 — Lowered Threshold Second Pass

After the primary detection, run a second pass on any segment within 50 segments of a known duplicate group member, with lower thresholds (ratio ≥ 0.65, overlap ≥ 0.45). These "neighbors" of known duplicates are high-probability candidates.

#### Merging Passes

After all passes produce `adjacency` graphs, merge them:
```python
# Merge adjacency graphs from all passes
combined_adjacency = defaultdict(set)
for adj in [tfidf_adj, windowed_adj, anchor_adj, sub_sentence_adj, second_pass_adj]:
    for k, v in adj.items():
        combined_adjacency[k].update(v)
# Then run connected components once on combined_adjacency
```

---

### Priority 4 — Better Text Normalization (Low effort, meaningful impact)

Improve `normalize()` to strip punctuation and normalize common transcription variants:

```python
import re

def normalize(text):
    # Remove [N] prefixes from segments
    text = re.sub(r'^\[\-?\d+\]\s*', '', text)
    # Lowercase
    text = text.lower()
    # Remove all punctuation (keep apostrophes for contractions)
    text = re.sub(r"[^\w\s']", ' ', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    return text
```

**Impact example:**
- `"Bedford, dismissed"` → `"bedford dismissed"`  
- `"Bedford dismissed"` → `"bedford dismissed"`  
Now these match exactly instead of having a small character difference.

---

### Priority 5 — Word-Level Segment Re-Merging (Higher effort, significant impact)

Before detection, merge adjacent short segments that look like they belong to one sentence:

```python
def merge_short_segments(segments, max_gap_seconds=0.5, min_words_for_standalone=4):
    """
    Re-merge Whisper segments that are fragments of the same sentence.
    Useful when Whisper splits a sentence across two segments mid-word or at punctuation.
    """
    merged = []
    i = 0
    while i < len(segments):
        current = segments[i]
        words = current.text.split()
        # If this segment is short AND the next segment starts quickly, merge
        while (len(words) < min_words_for_standalone and 
               i + 1 < len(segments) and
               segments[i+1].start_time - current.end_time <= max_gap_seconds):
            i += 1
            current = {
                'text': current.text.rstrip() + ' ' + segments[i].text.lstrip(),
                'start_time': current.start_time,
                'end_time': segments[i].end_time,
            }
            words = current.text.split()
        merged.append(current)
        i += 1
    return merged
```

This would prevent the scenario where "Her mother, the once countess of Bedford," is one segment and "dismissed her suspicions as nonsense, blinded" is another — before detection they'd be merged into the correct full sentence.

---

### Priority 6 — Expose All Algorithm Parameters in the UI

Currently, the default parameters are hardcoded and only overridable via direct API parameters. The frontend Algorithm Settings section should expose:

| Parameter | Current Default | Suggested Range |
|-----------|----------------|-----------------|
| Window lookahead | 150 | 50 – 500 |
| Ratio threshold | 0.75 | 0.60 – 0.90 |
| Strong match ratio | 0.90 | 0.80 – 0.98 |
| Min word overlap | 0.45 | 0.30 – 0.65 |
| TF-IDF threshold | 0.85 | 0.70 – 0.95 |

A "Sensitivity" slider (Low / Medium / High / Maximum) could map to preset parameter combinations.

---

## 6. Algorithm Comparison Table

| Algorithm | Scope | Speed | Recall | Precision | Best for |
|-----------|-------|-------|--------|-----------|---------|
| `tfidf_cosine` (current) | Global | Medium | Medium | Medium | Files with many paraphrases |
| `tfidf_cosine` (fixed) | Global | Medium | **High** | Medium | Same + catches indirect chains |
| `windowed_retry` (current) | 150 segments | Fast | Medium | High | Close retries < 10 min |
| `windowed_retry` (400 window) | 400 segments | Medium | **High** | High | Page-level retries |
| Multi-pass (proposed) | Global | Slower | **Highest** | High | All cases, no misses |

---

## 7. Recommended Implementation Order

### Step 1 — Quick Wins (1–2 hours each, deploy today)

1. **Increase default `window_max_lookahead` from 150 → 400** in `duplicate_tasks.py`
2. **Fix `tfidf_cosine` greedy grouping bug** — replace with connected components
3. **Improve `normalize()`** to strip punctuation before comparison

### Step 2 — Medium Effort (half day each)

4. **Add Anchor Phrase Pass** — 5-word fingerprint inverted index, no window limit
5. **Expose algorithm parameters in Tab 3 UI** — sensitivity slider
6. **Add SRT/VTT output to download options** (already in code but endpoint needs wiring)

### Step 3 — Larger Work (1–2 days each)

7. **Segment re-merging pre-pass** — merge short Whisper fragments before detection
8. **Sub-sentence pass** — catch fragment-vs-full-sentence matches
9. **Multi-pass orchestration** — combine all adjacency graphs, single connected-component pass
10. **New "Exhaustive" algorithm option** in the UI — runs all passes, user warned it takes longer

---

## 8. Download Transcription Bug Fix

### Root Cause

`handleDownloadTranscription()` in [Tab3Duplicates.js](../frontend/audio-waveform-visualizer/src/components/ProjectTabs/Tab3Duplicates.js) checks `selectedAudioFile.transcription.all_segments`, but `AudioFileSerializer.get_transcription()` only returns `{ id, text, word_count, confidence_score }` — **no segments array**.

This means `allSegments` is always empty for server-transcribed files, and the function shows:
> "No transcription segments found for this file."

### Fix Applied

The `handleDownloadTranscription` function now:
1. Checks `all_segments` in memory (will still work if ever populated)
2. Falls back to `localStorage` for client-only files
3. **NEW:** If still empty and the file has a server transcription, calls  
   `GET /api/projects/{id}/files/{id}/transcription/download/?format=json`  
   and uses the returned `segments` array for all client-side format conversions

This fix is already applied to [Tab3Duplicates.js](../frontend/audio-waveform-visualizer/src/components/ProjectTabs/Tab3Duplicates.js).

---

## 9. Why the Transcription Format is Generally Fine

The current sentence-level segment approach is appropriate for duplicate detection. Key reasons:

- **Whisper naturally segments at sentence boundaries** — this aligns with how narrators re-read (they restart at sentence beginnings)
- **Word-level timestamps already stored** (`TranscriptionWord`) — available for future use without re-transcription
- **Segment-level matching is faster** — word-level matching would be O(total_words²) per comparison

The main gap is that Whisper sometimes segments the same sentence differently across recordings. The fix is normalization and flexible matching (the improvements above), not a different transcription format.

**However**, for highest recall, future work could add a "word-sequence fingerprint" pass that uses the stored `TranscriptionWord` data to match at word-token level. This would be Pass 6 in the multi-pass strategy.

---

## 10. Summary of Changes

| Change | Location | Effort | Impact |
|--------|----------|--------|--------|
| ✅ Fix download transcription (fetch from API) | Tab3Duplicates.js | Done | Unblocks all download formats |
| 🔲 Increase lookahead 150→400 | duplicate_tasks.py line 1045 | 5 min | High — catches distant 3rd occurrences |
| 🔲 Fix tfidf_cosine grouping bug | duplicate_tasks.py ~1076 | 30 min | High — catches indirect chains |
| 🔲 Strip punctuation in normalize() | tasks/utils.py | 10 min | Medium — reduces character-ratio divergence |
| 🔲 Add anchor phrase pass | duplicate_tasks.py | 2 hrs | Very high — global scope, no window limit |
| 🔲 Sub-sentence pass | duplicate_tasks.py | 2 hrs | High — catches fragment matches |
| 🔲 Segment merge pre-pass | duplicate_tasks.py | 3 hrs | High — fixes split-sentence misses |
| 🔲 Multi-pass orchestration | duplicate_tasks.py | 1 day | Highest overall recall |
| 🔲 UI sensitivity slider | Tab3Duplicates.js | 3 hrs | Good UX for tuning |
