"""
Celery task for comparing transcription to PDF document using Myers Diff algorithm.
Implements three-phase sequence alignment:
- Phase 1: Find starting point in PDF using sliding window
- Phase 2: Myers diff algorithm for optimal sequence alignment  
- Phase 3: Classify and aggregate differences into missing/extra sections
"""
import re
import logging
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def compare_transcription_to_pdf_task(self, audio_file_id):
    """
    Compare a transcribed audio file to the PDF document.
    
    Steps:
    1. Get the audio file and its transcript
    2. Load the PDF text from the project
    3. Find where the audio starts in the PDF (section matching)
    4. Compare the transcript to the PDF section
    5. Identify missing content (in PDF but not in audio)
    6. Identify extra content (in audio but not in PDF)
    7. Calculate match statistics
    
    Returns:
        dict: Comparison results with match info, missing content, extra content, statistics
    """
    task_id = self.request.id
    
    try:
        from ..models import AudioFile, AudioProject, TranscriptionSegment
        from ..utils import get_redis_connection
        from PyPDF2 import PdfReader
        
        r = get_redis_connection()
        r.set(f"progress:{task_id}", 5)
        
        # Get audio file and project
        audio_file = AudioFile.objects.select_related('project').get(id=audio_file_id)
        project = audio_file.project
        
        if not project.pdf_file:
            raise ValueError("No PDF file found for this project")
        
        if not audio_file.transcript_text:
            raise ValueError("Audio file has not been transcribed yet")
        
        logger.info(f"Starting PDF comparison for audio file {audio_file_id}")
        
        r.set(f"progress:{task_id}", 10)
        
        # Step 1: Load PDF text
        if not project.pdf_text:
            # Extract PDF text if not already cached
            logger.info("Extracting PDF text")
            reader = PdfReader(project.pdf_file.path)
            pdf_text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
            project.pdf_text = pdf_text
            project.save(update_fields=['pdf_text'])
        else:
            pdf_text = project.pdf_text
        
        r.set(f"progress:{task_id}", 30)
        
        # Get transcript
        transcript = audio_file.transcript_text
        
        # Step 2: Find matching section in PDF using Phase 1 (sliding window)
        logger.info("Phase 1: Finding starting point in PDF")
        start_pos, confidence = find_start_position_in_pdf(pdf_text, transcript)
        
        r.set(f"progress:{task_id}", 40)
        
        # Extract PDF section for comparison
        pdf_section = extract_pdf_section(pdf_text, start_pos, len(transcript))
        
        r.set(f"progress:{task_id}", 50)
        
        # Step 3: Get ignored sections (if any)
        ignored_sections = audio_file.pdf_ignored_sections or []
        
        # Filter out ignored sections from comparison
        pdf_section_filtered = pdf_section
        for ignored in ignored_sections:
            if 'text' in ignored:
                pdf_section_filtered = pdf_section_filtered.replace(ignored['text'], '')
        
        r.set(f"progress:{task_id}", 55)
        
        # Step 4: Perform Myers diff alignment (Phase 2)
        logger.info("Phase 2: Performing sequence alignment")
        pdf_words = normalize_and_tokenize(pdf_section_filtered)
        transcript_words = normalize_and_tokenize(transcript)
        operations = myers_diff_words(pdf_words, transcript_words)
        
        r.set(f"progress:{task_id}", 70)
        
        # Step 5: Classify differences (Phase 3)
        logger.info("Phase 3: Classifying and aggregating differences")
        segments = list(TranscriptionSegment.objects.filter(audio_file=audio_file).order_by('start_time'))
        results = classify_differences(operations, pdf_words, transcript_words, transcript, segments)
        
        r.set(f"progress:{task_id}", 85)
        
        # Step 6: Build match result metadata
        match_result = {
            'start_position': start_pos,
            'confidence': confidence,
            'matched_section': pdf_section[:1000],  # Preview of matched section
            'start_char': start_pos,
            'end_char': start_pos + len(pdf_section),
            'start_preview': pdf_section[:100] if len(pdf_section) > 100 else pdf_section,
            'end_preview': pdf_section[-100:] if len(pdf_section) > 100 else pdf_section,
        }
        
        # Step 7: Calculate statistics
        stats = calculate_comparison_stats(
            results['matching_words'],
            results['missing_words'],
            results['extra_words'],
            len(transcript_words),
            len(pdf_words)
        )
        
        # Add section counts
        stats['missing_sections'] = len(results['missing_content'])
        stats['extra_sections'] = len(results['extra_content'])
        
        r.set(f"progress:{task_id}", 95)
        
        # Save results to audio file
        comparison_results = {
            'match_result': match_result,
            'missing_content': results['missing_content'],
            'extra_content': results['extra_content'],
            'statistics': stats,
            'ignored_sections_count': len(ignored_sections),
            'algorithm': 'myers_diff_v1'
        }
        
        audio_file.pdf_comparison_results = comparison_results
        audio_file.pdf_comparison_completed = True
        audio_file.save(update_fields=['pdf_comparison_results', 'pdf_comparison_completed'])
        
        r.set(f"progress:{task_id}", 100)
        
        logger.info(f"PDF comparison completed for audio file {audio_file_id}")
        
        return {
            'status': 'completed',
            'audio_file_id': audio_file_id,
            'comparison_results': comparison_results
        }
        
    except Exception as e:
        logger.error(f"PDF comparison failed for audio file {audio_file_id}: {str(e)}")
        r = get_redis_connection()
        r.set(f"progress:{task_id}", -1)
        raise


# ============================================================================
# PHASE 1: FIND STARTING POINT IN PDF
# ============================================================================

def normalize_and_tokenize(text):
    """
    Normalize text for comparison: lowercase, remove punctuation, filter short words.
    Returns list of significant words (>= 3 characters).
    """
    # Remove punctuation and normalize
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    # Split and filter short words
    words = [w for w in text.split() if len(w) >= 3]
    return words


def find_start_position_in_pdf(pdf_text, transcript_text):
    """
    Phase 1: Find where the transcript begins in the PDF using sliding window.
    
    Returns: (start_word_index, confidence_score)
    """
    # Tokenize both documents
    pdf_words = normalize_and_tokenize(pdf_text)
    transcript_words = normalize_and_tokenize(transcript_text)
    
    logger.info(f"PDF: {len(pdf_words)} words, Transcript: {len(transcript_words)} words")
    
    # Define search window (first 100 words of transcript)
    window_size = min(100, len(transcript_words))
    search_window = transcript_words[:window_size]
    
    # Slide across PDF to find best match
    best_score = 0
    best_position = 0
    
    for i in range(len(pdf_words) - window_size):
        pdf_window = pdf_words[i:i + window_size]
        
        # Count exact matches
        matches = sum(1 for a, b in zip(pdf_window, search_window) if a == b)
        score = matches / window_size
        
        if score > best_score:
            best_score = score
            best_position = i
        
        # Early exit if excellent match (>85%)
        if score > 0.85:
            logger.info(f"Found excellent match at word {i} ({score:.1%})")
            break
    
    logger.info(f"Best match: word {best_position} with {best_score:.1%} confidence")
    return best_position, best_score


def extract_pdf_section(pdf_text, start_word_pos, transcript_length):
    """
    Extract section from PDF starting at word position.
    Section length = transcript length * 1.2 (20% buffer for missing content).
    """
    pdf_words_full = pdf_text.split()
    
    # Calculate section length with buffer
    section_word_count = int((transcript_length / 4) * 1.2)  # Approximate word count from char count
    
    # Extract words
    end_word_pos = min(start_word_pos + section_word_count, len(pdf_words_full))
    section_words = pdf_words_full[start_word_pos:end_word_pos]
    
    # Rejoin into text
    section_text = ' '.join(section_words)
    
    logger.info(f"Extracted {len(section_words)} words starting at position {start_word_pos}")
    return section_text


# ============================================================================
# PHASE 2: MYERS DIFF ALGORITHM (Sequence Alignment)
# ============================================================================

def myers_diff_words(pdf_words, transcript_words):
    """
    Phase 2: Perform Myers diff algorithm on word sequences.
    Returns list of operations: (op_type, word, pdf_idx, transcript_idx)
    Operations: 'MATCH', 'DELETE' (in PDF not transcript), 'INSERT' (in transcript not PDF)
    
    This is the core alignment algorithm - same concept as Git diff.
    Complexity: O((N+M)*D) where D = number of differences
    """
    n = len(pdf_words)
    m = len(transcript_words)
    
    logger.info(f"Running Myers diff: {n} PDF words vs {m} transcript words")
    
    # Handle edge cases
    if n == 0:
        return [('INSERT', word, None, i) for i, word in enumerate(transcript_words)]
    if m == 0:
        return [('DELETE', word, i, None) for i, word in enumerate(pdf_words)]
    
    # Build edit graph
    max_d = n + m
    v = {1: 0}
    trace = []
    
    # Find shortest edit path
    for d in range(max_d + 1):
        trace.append(v.copy())
        
        for k in range(-d, d + 1, 2):
            # Determine path
            if k == -d or (k != d and v.get(k - 1, -1) < v.get(k + 1, -1)):
                x = v.get(k + 1, 0)
            else:
                x = v.get(k - 1, -1) + 1
            
            y = x - k
            
            # Extend diagonal (matches)
            while x < n and y < m and pdf_words[x] == transcript_words[y]:
                x += 1
                y += 1
            
            v[k] = x
            
            # Check if we reached the end
            if x >= n and y >= m:
                logger.info(f"Myers diff completed in {d} edits")
                return backtrack_diff(trace, pdf_words, transcript_words, d)
    
    # Should not reach here
    logger.warning("Myers diff did not converge, using fallback")
    return []


def backtrack_diff(trace, pdf_words, transcript_words, d):
    """
    Backtrack through the Myers diff trace to build the list of operations.
    """
    operations = []
    x = len(pdf_words)
    y = len(transcript_words)
    
    for depth in range(len(trace) - 1, -1, -1):
        v = trace[depth]
        k = x - y
        
        # Determine previous k
        if k == -depth or (k != depth and v.get(k - 1, -1) < v.get(k + 1, -1)):
            prev_k = k + 1
        else:
            prev_k = k - 1
        
        prev_x = v.get(prev_k, 0)
        prev_y = prev_x - prev_k
        
        # Add diagonal matches
        while x > prev_x and y > prev_y:
            x -= 1
            y -= 1
            operations.insert(0, ('MATCH', pdf_words[x], x, y))
        
        # Add insert/delete
        if depth > 0:
            if x == prev_x:
                # Insert (in transcript, not in PDF)
                y -= 1
                if y >= 0:
                    operations.insert(0, ('INSERT', transcript_words[y], None, y))
            else:
                # Delete (in PDF, not in transcript)
                x -= 1
                if x >= 0:
                    operations.insert(0, ('DELETE', pdf_words[x], x, None))
    
    logger.info(f"Backtrack complete: {len(operations)} operations")
    return operations


# ============================================================================
# PHASE 3: CLASSIFY AND AGGREGATE DIFFERENCES
# ============================================================================

def classify_differences(operations, pdf_words, transcript_words, transcript_text, segments):
    """
    Phase 3: Group consecutive operations into meaningful sections.
    Returns dict with missing_content, extra_content, and word counts.
    """
    missing_sections = []
    extra_sections = []
    current_missing = []
    current_extra = []
    
    matches = 0
    missing_words = 0
    extra_words = 0
    
    logger.info(f"Classifying {len(operations)} operations")
    
    for op, word, pdf_idx, trans_idx in operations:
        if op == 'MATCH':
            # Flush accumulated differences
            if current_missing:
                section = aggregate_missing_words(current_missing)
                if section:
                    missing_sections.append(section)
                    missing_words += section['word_count']
                current_missing = []
            
            if current_extra:
                section = aggregate_extra_words(current_extra, transcript_text, segments)
                if section:
                    extra_sections.append(section)
                    extra_words += section['word_count']
                current_extra = []
            
            matches += 1
            
        elif op == 'DELETE':
            # Missing from transcript (in PDF, not in transcript)
            current_missing.append((word, pdf_idx))
            
        elif op == 'INSERT':
            # Extra in transcript (in transcript, not in PDF)
            current_extra.append((word, trans_idx))
    
    # Flush remaining
    if current_missing:
        section = aggregate_missing_words(current_missing)
        if section:
            missing_sections.append(section)
            missing_words += section['word_count']
    
    if current_extra:
        section = aggregate_extra_words(current_extra, transcript_text, segments)
        if section:
            extra_sections.append(section)
            extra_words += section['word_count']
    
    logger.info(f"Found {len(missing_sections)} missing sections, {len(extra_sections)} extra sections")
    
    return {
        'missing_content': missing_sections,
        'extra_content': extra_sections,
        'matching_words': matches,
        'missing_words': missing_words,
        'extra_words': extra_words
    }


def aggregate_missing_words(words_list):
    """
    Combine consecutive missing words into a section.
    Only create section if >= 5 words (filter out noise).
    """
    if len(words_list) < 5:
        return None
    
    text = ' '.join(word for word, idx in words_list)
    
    # Reconstruct sentences by splitting on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
    
    if not sentences:
        return None
    
    # Use longest sentence as representative text
    representative_text = max(sentences, key=len) if sentences else text
    
    return {
        'text': representative_text,
        'word_count': len(words_list),
        'position': words_list[0][1]  # First word's PDF index
    }


def aggregate_extra_words(words_list, transcript_text, segments):
    """
    Combine consecutive extra words into a section with timestamps.
    Classify the type and match to TranscriptionSegments.
    """
    if len(words_list) < 5:
        return None
    
    text = ' '.join(word for word, idx in words_list)
    
    # Reconstruct sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
    
    if not sentences:
        return None
    
    representative_text = max(sentences, key=len) if sentences else text
    
    # Classify type
    content_type = classify_extra_content(representative_text)
    
    # Find matching segments for timestamps
    timestamps = find_matching_segments(representative_text, segments)
    
    return {
        'text': representative_text,
        'word_count': len(words_list),
        'possible_type': content_type,
        'position_in_transcript': words_list[0][1] if words_list[0][1] is not None else 0,
        'timestamps': timestamps,
        'start_time': timestamps[0]['start_time'] if timestamps else None,
        'end_time': timestamps[-1]['end_time'] if timestamps else None,
    }


def find_matching_segments(text, segments):
    """
    Find TranscriptionSegments that contain this text.
    Uses word overlap for matching.
    """
    text_words_set = set(normalize_and_tokenize(text))
    matching_segments = []
    
    for segment in segments:
        segment_words_set = set(normalize_and_tokenize(segment.text))
        
        # Calculate overlap
        if not text_words_set or not segment_words_set:
            continue
        
        overlap = len(text_words_set.intersection(segment_words_set))
        overlap_ratio = overlap / min(len(text_words_set), len(segment_words_set))
        
        # If >40% overlap, consider it a match
        if overlap_ratio > 0.4:
            matching_segments.append({
                'start_time': segment.start_time,
                'end_time': segment.end_time,
                'segment_id': segment.id
            })
    
    return matching_segments


def classify_extra_content(sentence):
    """
    Classify what type of extra content this might be.
    Returns: 'chapter_marker', 'narrator_info', 'duplicate', 'other'
    """
    sentence_lower = sentence.lower()
    
    # Check for chapter markers
    if re.search(r'\bchapter\b|\bpart\b|\bsection\b|\bbook\b', sentence_lower):
        return 'chapter_marker'
    
    # Check for narrator phrases
    narrator_phrases = [
        'narrated by', 'read by', 'performed by', 'audiobook',
        'introduction', 'epilogue', 'prologue', 'afterword'
    ]
    if any(phrase in sentence_lower for phrase in narrator_phrases):
        return 'narrator_info'
    
    return 'other'


# ============================================================================
# STATISTICS CALCULATION
# ============================================================================

def calculate_comparison_stats(matching_words, missing_words, extra_words, transcript_word_count, pdf_word_count):
    """
    Calculate statistics based on Myers diff results.
    """
    total_operations = matching_words + missing_words + extra_words
    
    # Coverage: what % of PDF words are in transcript
    coverage_percentage = (matching_words / pdf_word_count * 100) if pdf_word_count > 0 else 0
    
    # Accuracy: what % of transcript words match PDF
    accuracy_percentage = (matching_words / transcript_word_count * 100) if transcript_word_count > 0 else 0
    
    # Match quality
    if accuracy_percentage >= 95:
        match_quality = 'excellent'
    elif accuracy_percentage >= 85:
        match_quality = 'good'
    elif accuracy_percentage >= 70:
        match_quality = 'fair'
    else:
        match_quality = 'poor'
    
    logger.info(f"Stats: {matching_words} matches, {missing_words} missing, {extra_words} extra")
    logger.info(f"Accuracy: {accuracy_percentage:.1f}%, Coverage: {coverage_percentage:.1f}%, Quality: {match_quality}")
    
    return {
        'transcript_word_count': transcript_word_count,
        'pdf_word_count': pdf_word_count,
        'matching_word_count': matching_words,
        'missing_word_count': missing_words,
        'extra_word_count': extra_words,
        'missing_sections': 0,  # Will be filled by classify_differences
        'extra_sections': 0,    # Will be filled by classify_differences
        'coverage_percentage': round(coverage_percentage, 2),
        'accuracy_percentage': round(accuracy_percentage, 2),
        'match_quality': match_quality
    }
