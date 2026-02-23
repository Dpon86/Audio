# Duplicate Detection Algorithm Requirements

## Goal
Detect repeated spoken content in a single transcribed audio file where narrators retry words, sentences, or full paragraphs, and always keep the last occurrence.

## Core Rules
- Duplicate groups can contain 2, 3, 4, or more occurrences.
- The last chronological occurrence in each group is the keeper.
- All earlier occurrences in that group are candidates for deletion.
- Detection must use transcription segments and timestamps.
- UI must clearly highlight repeated words in each grouped occurrence.

## Input Data
- Segment text (`TranscriptionSegment.text`)
- Segment timing (`start_time`, `end_time`)
- Segment order (`segment_index`)
- Optional script/PDF text (`AudioProject.pdf_text`)

## Output Data
For each duplicate group:
- Group identifier
- Duplicate text preview
- Occurrence count
- Total duration saved if duplicates removed
- Segment list with:
  - segment id
  - start/end timestamps
  - text
  - `is_duplicate` (delete)
  - `is_kept` (keep)
  - `is_last_occurrence`

## Algorithms to Test

### 1) Classic TF-IDF Cosine (baseline, no PDF)
- Uses n-gram TF-IDF vectors over segment text.
- Groups segments above similarity threshold.
- Good baseline for near-exact repeats.

### 2) Windowed Retry-Aware (new, no PDF)
- New algorithm focused on narrator retry behavior.
- Compares segments within a local lookahead window.
- Uses combined lexical overlap + sequence similarity.
- Better for partial restarts and nearby re-reads.

### 3) Windowed Retry-Aware + PDF Anchoring (with PDF)
- Same as #2 plus optional PDF-position hinting.
- Prevents false positives where similar text appears in different script locations.
- Falls back gracefully when PDF text is unavailable.

## Evaluation Matrix
For each algorithm run, measure:
- Duplicate groups found
- Segments marked for deletion
- Precision (manual check of true duplicates)
- Recall (missed duplicates)
- Time saved (sum of deleted duration)
- Runtime/performance on long files

## Test Scenarios
- Single-word retry (“the the the” then corrected phrase)
- Partial sentence restart
- Full sentence re-read
- Multi-sentence paragraph re-read
- Similar-but-not-duplicate lines in different chapter contexts
- Very short segments and very long segments

## UX Requirements
- Tab 3 must support choosing algorithm before detection.
- Include a quick action for the new algorithm.
- Show grouped occurrences in chronological order.
- Keep last occurrence auto-selected as KEEP.
- Highlight repeated words directly in occurrence text.

## Safety/Edge Cases
- If no transcription exists, return clear error.
- If no duplicates found, return empty groups without failing.
- If PDF hint is requested but PDF text is missing, continue without PDF hint and log warning.

## Rollout Plan
1. Run baseline (TF-IDF) on existing sample files.
2. Run new windowed algorithm on same files.
3. Run windowed + PDF on script-backed files.
4. Compare precision/recall and reviewer feedback.
5. Promote best algorithm to default after validation.
