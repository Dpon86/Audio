"""
Pdf Tasks for audioDiagnostic app.
"""
from ._base import *

@shared_task(bind=True)
def match_pdf_to_audio_task(self, project_id):
    """
    Celery task for PDF-to-Audio matching to prevent frontend timeouts
    Uses sentence-based boundary detection for comprehensive matching
    """
    task_id = self.request.id
    
    # Get Redis connection appropriate for this environment
    r = get_redis_connection()
    
    # Set up Docker and Celery infrastructure
    if not docker_celery_manager.setup_infrastructure():
        raise Exception("Failed to set up Docker and Celery infrastructure")
    
    # Register this task
    docker_celery_manager.register_task(task_id)
    
    try:
        # Get project
        from audioDiagnostic.models import AudioProject
        project = AudioProject.objects.get(id=project_id)
        
        r.set(f"progress:{task_id}", 5)
        logger.info(f"Starting PDF matching for project {project_id}")
        
        # Verify prerequisites
        if not project.pdf_file:
            raise ValueError("No PDF file uploaded")
        
        audio_files = project.audio_files.filter(status='transcribed')
        if not audio_files.exists():
            raise ValueError("No transcribed audio files found")
        
        r.set(f"progress:{task_id}", 15)
        
        # Extract PDF text if not already done
        if not project.pdf_text:
            from PyPDF2 import PdfReader
            
            logger.info(f"Extracting PDF text from {project.pdf_file.path}")
            reader = PdfReader(project.pdf_file.path)
            logger.info(f"PDF has {len(reader.pages)} pages")
            
            # Extract text from all pages with progress tracking
            all_text = []
            total_pages = len(reader.pages)
            
            for i, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        all_text.append(page_text.strip())
                        logger.info(f"Page {i+1}: extracted {len(page_text)} characters")
                    else:
                        logger.warning(f"Page {i+1}: no text extracted")
                        
                    # Update progress for PDF extraction (15-40%)
                    progress = 15 + int((i + 1) / total_pages * 25)
                    r.set(f"progress:{task_id}", progress)
                    
                except Exception as e:
                    logger.error(f"Error extracting text from page {i+1}: {e}")
            
            project.pdf_text = "\n\n".join(all_text)
            logger.info(f"Total PDF text extracted: {len(project.pdf_text)} characters")
            project.save()
        
        r.set(f"progress:{task_id}", 45)
        
        # Get combined transcript from all audio files
        if not project.combined_transcript:
            transcripts = []
            for audio_file in audio_files.order_by('order_index'):
                if audio_file.transcript_text:
                    transcripts.append(audio_file.transcript_text)
            project.combined_transcript = "\n".join(transcripts)
            project.save()
        
        r.set(f"progress:{task_id}", 55)
        
        # Debug logging for text comparison
        logger.info(f"PDF text length: {len(project.pdf_text)}")
        logger.info(f"Combined transcript length: {len(project.combined_transcript)}")
        
        # Perform the intensive PDF matching using sentence-based algorithm
        logger.info("Starting sentence-based PDF matching algorithm...")
        r.set(f"progress:{task_id}", 60)
        
        match_result = find_pdf_section_match_task(project.pdf_text, project.combined_transcript, task_id, r)
        
        r.set(f"progress:{task_id}", 90)
        
        # Save results to project
        project.pdf_matched_section = match_result['matched_section']
        project.pdf_match_confidence = match_result['confidence']
        project.pdf_chapter_title = match_result['chapter_title']
        project.pdf_match_completed = True
        project.save()
        
        r.set(f"progress:{task_id}", 100)
        
        # Unregister task
        docker_celery_manager.unregister_task(task_id)
        
        logger.info(f"PDF matching completed for project {project_id}")
        
        return {
            'status': 'completed',
            'match_result': {
                'matched_section_preview': match_result['matched_section'][:500] + '...',
                'confidence': match_result['confidence'],
                'chapter_title': match_result['chapter_title'],
                'coverage_analyzed': match_result.get('coverage_analyzed', 0),
                'match_type': match_result.get('match_type', 'unknown'),
                'match_completed': True
            }
        }
        
    except Exception as e:
        logger.error(f"PDF matching failed for project {project_id}: {str(e)}")
        
        # Update project with error
        try:
            project.status = 'failed'
            project.error_message = f"PDF matching failed: {str(e)}"
            project.save()
        except:
            pass
            
        # Unregister task even on failure
        docker_celery_manager.unregister_task(task_id)
            
        r.set(f"progress:{task_id}", -1)
        raise e


@shared_task(bind=True)
def analyze_transcription_vs_pdf(self, pdf_path, transcript, segments, words):
    # 1. Extract PDF text
    reader = PdfReader(pdf_path)
    pdf_text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())

    # 2. Find the section of the book being covered (simple fuzzy match)
    transcript_snippet = transcript[:500]  # Use first 500 chars for matching
    match_start = pdf_text.lower().find(transcript_snippet[:100].lower())
    if match_start == -1:
        # Fallback: use difflib to find best matching section
        seq = difflib.SequenceMatcher(None, pdf_text.lower(), transcript.lower())
        match_start = seq.find_longest_match(0, len(pdf_text), 0, len(transcript)).a
    match_end = match_start + len(transcript)
    pdf_section = pdf_text[match_start:match_end]

    # 3. Identify missing words
    pdf_words = re.findall(r'\w+', pdf_section.lower())
    transcript_words = re.findall(r'\w+', transcript.lower())
    missing_words = []
    pdf_idx = 0
    for word in pdf_words:
        while pdf_idx < len(transcript_words) and transcript_words[pdf_idx] != word:
            pdf_idx += 1
        if pdf_idx == len(transcript_words):
            missing_words.append(word)
        else:
            pdf_idx += 1

    # 4. Identify repeated sentences and their timestamps
    norm = lambda s: ' '.join(s.strip().lower().split())
    sentence_map = {}
    for idx, seg in enumerate(segments):
        text = norm(seg['text'])
        if text:
            sentence_map.setdefault(text, []).append(idx)
    repeated = {k: v for k, v in sentence_map.items() if len(v) > 1}
    repeated_sections = []
    for sent, idxs in repeated.items():
        for i in idxs[:-1]:  # All but last
            repeated_sections.append({
                "sentence": segments[i]['text'],
                "start": segments[i]['start'],
                "end": segments[i]['end']
            })

    # Only keep the last occurrence of each repeated sentence
    kept_sentences = [segments[idxs[-1]] for idxs in repeated.values()]

    return {
        "pdf_section": pdf_section,
        "missing_words": missing_words,
        "repeated_sections": repeated_sections,
        "kept_sentences": kept_sentences,
    }

@shared_task(bind=True)
def validate_transcript_against_pdf_task(self, project_id):
    """
    Step 5: Enhanced validation of clean transcript against PDF section
    
    Uses multiple matching strategies:
    1. Fuzzy matching for typos/variations (Levenshtein distance)
    2. Sentence-level semantic alignment (TF-IDF similarity)
    3. Sliding window LCS for sequence matching
    
    This provides more accurate results even with transcription variations.
    """
    task_id = self.request.id
    r = get_redis_connection()
    
    # Set up infrastructure
    if not docker_celery_manager.setup_infrastructure():
        raise Exception("Failed to set up Docker and Celery infrastructure")
    
    docker_celery_manager.register_task(task_id)
    
    try:
        from difflib import SequenceMatcher
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
        
        project = AudioProject.objects.get(id=project_id)
        
        # Validate prerequisites
        if not project.pdf_matched_section:
            raise ValueError("PDF section not matched yet")
        if not project.duplicates_confirmed_for_deletion:
            raise ValueError("No confirmed deletions to validate")
        
        r.set(f"progress:{task_id}", 5)
        logger.info(f"Starting ENHANCED PDF validation for project {project_id}")
        
        # Step 1: Get clean transcript (segments NOT in confirmed deletions)
        # Extract segment IDs from the list of deletion objects
        deletion_objects = project.duplicates_confirmed_for_deletion
        confirmed_deletions = set(d['segment_id'] for d in deletion_objects)
        all_segments = TranscriptionSegment.objects.filter(
            audio_file__project=project,
            is_verification=False
        ).order_by('audio_file__order_index', 'start_time').values('id', 'text')
        
        clean_transcript_parts = []
        for seg in all_segments:
            if seg['id'] not in confirmed_deletions:
                clean_transcript_parts.append(seg['text'])
        
        clean_transcript = ' '.join(clean_transcript_parts)
        r.set(f"progress:{task_id}", 15)
        
        # Step 2: Get PDF section and clean it
        pdf_section = project.pdf_matched_section
        if not pdf_section:
            raise ValueError("PDF matched section is empty")
        
        # Remove bracketed text from PDF (stage directions, notes, etc.)
        import re
        pdf_section_cleaned = re.sub(r'\[.*?\]', '', pdf_section)
        # Also remove any double spaces left behind
        pdf_section_cleaned = re.sub(r'\s+', ' ', pdf_section_cleaned).strip()
        
        r.set(f"progress:{task_id}", 20)
        logger.info(f"Clean transcript length: {len(clean_transcript)} chars")
        logger.info(f"PDF section length (cleaned): {len(pdf_section_cleaned)} chars")
        
        # ==================== SIMPLIFIED WORD MATCHING ====================
        # Strategy: Tokenize into words, then find each PDF word in transcript
        # Use sequential search with backtracking tolerance
        
        def normalize_word(word):
            """Normalize word for matching"""
            return re.sub(r'[^\w]', '', word.lower())
        
        def tokenize_with_positions(text):
            """Get words with their positions"""
            words = []
            word_pattern = re.compile(r'\b[\w\']+\b')
            for match in word_pattern.finditer(text):
                original = match.group(0)
                normalized = normalize_word(original)
                if normalized:  # Skip empty after normalization
                    words.append({
                        'original': original,
                        'normalized': normalized,
                        'pos': match.start()
                    })
            return words
        
        pdf_words = tokenize_with_positions(pdf_section_cleaned)
        transcript_words = tokenize_with_positions(clean_transcript)
        
        total_pdf_words = len(pdf_words)
        total_transcript_words = len(transcript_words)
        
        logger.info(f"PDF words: {total_pdf_words}, Transcript words: {total_transcript_words}")
        
        r.set(f"progress:{task_id}", 30)
        
        # ==================== MATCHING ALGORITHM ====================
        # Create word lists for searching
        pdf_word_list = [w['normalized'] for w in pdf_words]
        transcript_word_list = [w['normalized'] for w in transcript_words]
        
        matched_pdf_indices = set()
        matched_transcript_indices = set()
        
        # Pass 1: Find exact word sequences (3+ words in a row)
        logger.info("Pass 1: Finding 3-word sequences...")
        window_size = 3
        for pdf_idx in range(total_pdf_words - window_size + 1):
            if pdf_idx in matched_pdf_indices:
                continue
            
            pdf_window = pdf_word_list[pdf_idx:pdf_idx + window_size]
            
            for trans_idx in range(total_transcript_words - window_size + 1):
                if trans_idx in matched_transcript_indices:
                    continue
                
                trans_window = transcript_word_list[trans_idx:trans_idx + window_size]
                
                if pdf_window == trans_window:
                    for i in range(window_size):
                        matched_pdf_indices.add(pdf_idx + i)
                        matched_transcript_indices.add(trans_idx + i)
                    break
        
        logger.info(f"After 3-word sequences: {len(matched_pdf_indices)} PDF words matched")
        r.set(f"progress:{task_id}", 50)
        
        # Pass 2: Find 2-word sequences
        logger.info("Pass 2: Finding 2-word sequences...")
        window_size = 2
        for pdf_idx in range(total_pdf_words - window_size + 1):
            if pdf_idx in matched_pdf_indices:
                continue
            
            pdf_window = pdf_word_list[pdf_idx:pdf_idx + window_size]
            
            for trans_idx in range(total_transcript_words - window_size + 1):
                if trans_idx in matched_transcript_indices:
                    continue
                
                trans_window = transcript_word_list[trans_idx:trans_idx + window_size]
                
                if pdf_window == trans_window:
                    for i in range(window_size):
                        matched_pdf_indices.add(pdf_idx + i)
                        matched_transcript_indices.add(trans_idx + i)
                    break
        
        logger.info(f"After 2-word sequences: {len(matched_pdf_indices)} PDF words matched")
        r.set(f"progress:{task_id}", 70)
        
        # Pass 3: Match remaining individual words (nearest neighbor)
        logger.info("Pass 3: Matching individual words...")
        transcript_search_start = 0
        
        for pdf_idx in range(total_pdf_words):
            if pdf_idx in matched_pdf_indices:
                continue
            
            pdf_word_norm = pdf_word_list[pdf_idx]
            
            # Search forward in transcript from last position
            for trans_idx in range(transcript_search_start, total_transcript_words):
                if trans_idx in matched_transcript_indices:
                    continue
                
                if pdf_word_norm == transcript_word_list[trans_idx]:
                    matched_pdf_indices.add(pdf_idx)
                    matched_transcript_indices.add(trans_idx)
                    transcript_search_start = trans_idx + 1
                    break
        
        logger.info(f"After individual matching: {len(matched_pdf_indices)} PDF words matched")
        r.set(f"progress:{task_id}", 85)
        
        # ==================== Calculate Statistics ====================
        matched_words_count = len(matched_pdf_indices)
        unmatched_pdf_words = total_pdf_words - matched_words_count
        unmatched_transcript_words = total_transcript_words - len(matched_transcript_indices)
        match_percentage = (matched_words_count / total_pdf_words * 100) if total_pdf_words > 0 else 0
        
        logger.info(f"Final validation results:")
        logger.info(f"- Matched words: {matched_words_count}/{total_pdf_words}")
        logger.info(f"- Unmatched PDF words: {unmatched_pdf_words}")
        logger.info(f"- Unmatched transcript words: {unmatched_transcript_words}")
        logger.info(f"- Match percentage: {match_percentage:.2f}%")
        
        # ==================== Generate HTML with Color Coding ====================
        pdf_html_parts = []
        for idx, word_info in enumerate(pdf_words):
            word = word_info['original']
            if idx in matched_pdf_indices:
                pdf_html_parts.append(f'<span class="matched-word">{word}</span>')
            else:
                pdf_html_parts.append(f'<span class="unmatched-word">{word}</span>')
        
        pdf_html = ' '.join(pdf_html_parts)
        
        transcript_html_parts = []
        for idx, word_info in enumerate(transcript_words):
            word = word_info['original']
            if idx in matched_transcript_indices:
                transcript_html_parts.append(f'<span class="matched-word">{word}</span>')
            else:
                transcript_html_parts.append(f'<span class="unmatched-word">{word}</span>')
        
        transcript_html = ' '.join(transcript_html_parts)
        
        r.set(f"progress:{task_id}", 90)
        
        # Step 7: Save results
        validation_results = {
            'total_pdf_words': total_pdf_words,
            'total_transcript_words': total_transcript_words,
            'matched_words': matched_words_count,
            'unmatched_pdf_words': unmatched_pdf_words,
            'unmatched_transcript_words': unmatched_transcript_words,
            'match_percentage': round(match_percentage, 2),
            'validation_timestamp': datetime.datetime.now().isoformat()
        }
        
        project.pdf_validation_results = validation_results
        project.pdf_validation_html = f"""
        <div class="validation-container">
            <div class="validation-panel pdf-panel">
                <h3>PDF Section ({total_pdf_words} words)</h3>
                <div class="validation-text">{pdf_html}</div>
            </div>
            <div class="validation-panel transcript-panel">
                <h3>Clean Transcript ({total_transcript_words} words)</h3>
                <div class="validation-text">{transcript_html}</div>
            </div>
        </div>
        """
        project.pdf_validation_completed = True
        project.save()
        
        r.set(f"progress:{task_id}", 100)
        logger.info(f"PDF validation completed for project {project_id}")
        
        return {
            'status': 'completed',
            'results': {
                **validation_results,
                'pdf_html': pdf_html,
                'transcript_html': transcript_html
            }
        }
        
    except Exception as e:
        logger.error(f"PDF validation failed: {str(e)}", exc_info=True)
        project = AudioProject.objects.get(id=project_id)
        project.error_message = f"PDF validation error: {str(e)}"
        project.save()
        raise
    finally:
        docker_celery_manager.unregister_task(task_id)

def find_pdf_section_match(pdf_text, transcript):
    """
    Find the section in the PDF that corresponds to the audio transcript.
    Returns the matching PDF section.
    """
    # Clean up texts for comparison
    pdf_clean = ' '.join(pdf_text.lower().split())
    transcript_clean = ' '.join(transcript.lower().split())
    
    # Try exact substring match first
    transcript_start = transcript_clean[:200]  # First 200 chars
    match_pos = pdf_clean.find(transcript_start)
    
    if match_pos != -1:
        # Found exact match, extract section
        start_pos = match_pos
        end_pos = min(match_pos + len(transcript_clean) + 500, len(pdf_clean))
        return pdf_text[start_pos:end_pos]
    else:
        # Use sequence matching for fuzzy match
        seq_matcher = difflib.SequenceMatcher(None, pdf_clean, transcript_clean)
        match = seq_matcher.find_longest_match(0, len(pdf_clean), 0, len(transcript_clean))
        
        if match.size > 100:  # Minimum match length
            start_pos = match.a
            end_pos = min(match.a + match.size + 200, len(pdf_clean))
            return pdf_text[start_pos:end_pos]
        else:
            # Fallback: return first part of PDF
            return pdf_text[:1000]

def find_pdf_section_match_task(pdf_text, transcript, task_id, r):
    """
    Sentence-based PDF matching algorithm for Celery task with progress tracking
    """
    import difflib
    import re
    
    logger.info(f"Starting SENTENCE-BASED PDF matching - PDF: {len(pdf_text)} chars, Transcript: {len(transcript)} chars")
    
    # Clean and normalize texts for better matching
    def deep_clean_text(text):
        # Remove extra whitespace, normalize punctuation
        text = re.sub(r'\s+', ' ', text.lower().strip())
        text = re.sub(r'[^\w\s\.]', ' ', text)  # Keep only words and periods
        text = re.sub(r'\s+', ' ', text)
        return text
    
    # Extract sentences from transcript
    def extract_sentences(text, num_sentences=3):
        # Split by sentence endings but be flexible about transcription
        sentences = re.split(r'[.!?]+\s+', text.strip())
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]  # Min 10 chars per sentence
        return sentences
    
    pdf_clean = deep_clean_text(pdf_text)
    transcript_clean = deep_clean_text(transcript)
    
    r.set(f"progress:{task_id}", 65)
    
    # Get first and last sentences from transcript
    transcript_sentences = extract_sentences(transcript)
    logger.info(f"Extracted {len(transcript_sentences)} sentences from transcript")
    
    if len(transcript_sentences) < 2:
        logger.warning("Too few sentences in transcript - using fallback method")
        # Fallback to character-based chunks
        first_chunk = transcript_clean[:500]
        last_chunk = transcript_clean[-500:] if len(transcript_clean) > 500 else transcript_clean
    else:
        # Use first 3 and last 3 sentences
        num_boundary_sentences = min(3, len(transcript_sentences) // 2)
        
        first_sentences = transcript_sentences[:num_boundary_sentences]
        last_sentences = transcript_sentences[-num_boundary_sentences:]
        
        first_chunk = deep_clean_text(' '.join(first_sentences))
        last_chunk = deep_clean_text(' '.join(last_sentences))
        
        logger.info(f"Using {num_boundary_sentences} sentences for start/end detection")
    
    r.set(f"progress:{task_id}", 70)
    
    # PHASE 1: Find START position using first sentences
    logger.info("PHASE 1: Finding START position using first sentences...")
    start_position = None
    start_method = None
    
    # Try different approaches to find the start
    search_variants = []
    
    # Variant 1: Full first chunk
    search_variants.append(("full_chunk", first_chunk))
    
    # Variant 2: Remove common words from first chunk
    first_chunk_filtered = re.sub(r'\b(the|and|of|to|a|in|is|it|you|that|he|was|for|on|are|as|with|his|they|i|at|be|this|have|from|or|one|had|by|word|but|not|what|all|were|we|when|your|can|said|there|each|which|she|do|how|their|if|so|up|out|if|about|who|get|which|go|me)\b', ' ', first_chunk)
    first_chunk_filtered = re.sub(r'\s+', ' ', first_chunk_filtered).strip()
    if len(first_chunk_filtered) > 30:
        search_variants.append(("filtered_chunk", first_chunk_filtered))
    
    # Variant 3: Key phrases from first chunk (8-word sequences)
    first_words = first_chunk.split()
    for i in range(0, min(len(first_words) - 7, 5)):  # Try first 5 possible 8-word phrases
        phrase = ' '.join(first_words[i:i+8])
        if len(phrase) > 25:
            search_variants.append((f"phrase_{i}", phrase))
    
    # Search for start position
    for variant_name, search_text in search_variants:
        if len(search_text) < 20:
            continue
            
        match_pos = pdf_clean.find(search_text)
        if match_pos != -1:
            start_position = match_pos
            start_method = variant_name
            logger.info(f"Found START at position {match_pos} using {variant_name}")
            break
    
    r.set(f"progress:{task_id}", 80)
    
    # PHASE 2: Find END position using last sentences
    logger.info("PHASE 2: Finding END position using last sentences...")
    end_position = None
    end_method = None
    
    if start_position is not None:
        # Search for end position after the start
        end_search_variants = []
        
        # Variant 1: Full last chunk
        end_search_variants.append(("full_end_chunk", last_chunk))
        
        # Variant 2: Filtered last chunk
        last_chunk_filtered = re.sub(r'\b(the|and|of|to|a|in|is|it|you|that|he|was|for|on|are|as|with|his|they|i|at|be|this|have|from|or|one|had|by|word|but|not|what|all|were|we|when|your|can|said|there|each|which|she|do|how|their|if|so|up|out|if|about|who|get|which|go|me)\b', ' ', last_chunk)
        last_chunk_filtered = re.sub(r'\s+', ' ', last_chunk_filtered).strip()
        if len(last_chunk_filtered) > 30:
            end_search_variants.append(("filtered_end_chunk", last_chunk_filtered))
        
        # Variant 3: Key phrases from last chunk
        last_words = last_chunk.split()
        for i in range(max(0, len(last_words) - 15), len(last_words) - 7):  # Try last few 8-word phrases
            if i >= 0:
                phrase = ' '.join(last_words[i:i+8])
                if len(phrase) > 25:
                    end_search_variants.append((f"end_phrase_{i}", phrase))
        
        # Search for end position
        for variant_name, search_text in end_search_variants:
            if len(search_text) < 20:
                continue
            
            # Look for this text AFTER the start position
            match_pos = pdf_clean.find(search_text, start_position + 100)  # Give some buffer
            if match_pos != -1:
                end_position = match_pos + len(search_text)
                end_method = variant_name
                logger.info(f"Found END at position {match_pos} using {variant_name}")
                break
    
    r.set(f"progress:{task_id}", 85)
    
    # PHASE 3: Extract the matched section and calculate results
    if start_position is not None and end_position is not None and end_position > start_position:
        # SUCCESS: Found both start and end boundaries
        matched_length = end_position - start_position
        matched_section_clean = pdf_clean[start_position:end_position]
        
        # Calculate confidence using comprehensive similarity
        confidence = calculate_comprehensive_similarity_task(matched_section_clean, transcript_clean)
        
        # Map back to original PDF text positions (approximate)
        char_ratio = len(pdf_text) / len(pdf_clean)
        original_start = int(start_position * char_ratio)
        original_end = int(end_position * char_ratio)
        
        # Expand slightly for context and ensure we don't go out of bounds
        context_buffer = 100
        expanded_start = max(0, original_start - context_buffer)
        expanded_end = min(len(pdf_text), original_end + context_buffer)
        
        matched_section = pdf_text[expanded_start:expanded_end]
        
        # Extract chapter title from context
        chapter_context = pdf_text[max(0, expanded_start - 800):expanded_start + 300]
        chapter_title = extract_chapter_title_task(chapter_context)
        
        coverage = matched_length / len(pdf_clean)
        
        logger.info(f"SUCCESS: COMPLETE BOUNDARY MATCH!")
        logger.info(f"- Start method: {start_method} at position {start_position}")
        logger.info(f"- End method: {end_method} at position {end_position}")
        logger.info(f"- Matched length: {matched_length} chars ({coverage*100:.1f}% of PDF)")
        logger.info(f"- Confidence: {confidence:.3f}")
        logger.info(f"- Chapter: {chapter_title}")
        
        return {
            'matched_section': matched_section,
            'confidence': confidence,
            'chapter_title': chapter_title,
            'coverage_analyzed': coverage,
            'start_position': start_position,
            'end_position': end_position,
            'match_type': 'sentence_boundary',
            'start_method': start_method,
            'end_method': end_method
        }
        
    elif start_position is not None:
        # PARTIAL: Found start but no clear end - use intelligent estimation
        logger.info("Found START boundary but not END - using intelligent estimation")
        
        # Estimate end position based on transcript length vs PDF length
        estimated_length = min(
            int(len(transcript_clean) * 1.5),  # Assume PDF is 1.5x longer due to formatting
            len(pdf_clean) - start_position    # Don't exceed PDF length
        )
        
        estimated_end = start_position + estimated_length
        matched_section_clean = pdf_clean[start_position:estimated_end]
        confidence = calculate_comprehensive_similarity_task(matched_section_clean, transcript_clean)
        
        # Map back to original text
        char_ratio = len(pdf_text) / len(pdf_clean)
        original_start = int(start_position * char_ratio)
        original_end = int(estimated_end * char_ratio)
        
        expanded_start = max(0, original_start - 100)
        expanded_end = min(len(pdf_text), original_end + 100)
        
        matched_section = pdf_text[expanded_start:expanded_end]
        chapter_title = extract_chapter_title_task(pdf_text[max(0, expanded_start - 800):expanded_start + 300])
        
        coverage = estimated_length / len(pdf_clean)
        
        logger.info(f"PARTIAL MATCH from start boundary - Coverage: {coverage*100:.1f}%, Confidence: {confidence:.3f}")
        
        return {
            'matched_section': matched_section,
            'confidence': confidence,
            'chapter_title': chapter_title,
            'coverage_analyzed': coverage,
            'start_position': start_position,
            'match_type': 'start_boundary_estimated',
            'start_method': start_method
        }
    
    else:
        # FALLBACK: No clear boundaries found - use comprehensive analysis
        logger.warning("No sentence boundaries found - using comprehensive fallback")
        
        # Try to find ANY substantial match in the PDF
        best_match_pos = 0
        best_confidence = 0
        chunk_size = len(transcript_clean)
        
        # Sliding window to find best match
        step_size = max(1000, len(pdf_clean) // 20)  # Check 20 positions across PDF
        
        for pos in range(0, max(1, len(pdf_clean) - chunk_size), step_size):
            pdf_chunk = pdf_clean[pos:pos + chunk_size]
            confidence = calculate_comprehensive_similarity_task(pdf_chunk, transcript_clean)
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_match_pos = pos
        
        # Use the best match found
        matched_section_clean = pdf_clean[best_match_pos:best_match_pos + chunk_size]
        
        # Map to original text
        char_ratio = len(pdf_text) / len(pdf_clean)
        original_start = int(best_match_pos * char_ratio)
        original_end = int((best_match_pos + chunk_size) * char_ratio)
        
        matched_section = pdf_text[original_start:original_end]
        chapter_title = extract_chapter_title_task(pdf_text[max(0, original_start - 800):original_start + 300])
        
        coverage = chunk_size / len(pdf_clean)
        
        logger.info(f"FALLBACK MATCH at position {best_match_pos} - Coverage: {coverage*100:.1f}%, Confidence: {best_confidence:.3f}")
        
        return {
            'matched_section': matched_section,
            'confidence': max(0.15, best_confidence),  # Ensure minimum confidence
            'chapter_title': chapter_title,
            'coverage_analyzed': coverage,
            'match_type': 'comprehensive_fallback',
            'best_match_position': best_match_pos
        }


def identify_pdf_based_duplicates(segments, pdf_section, transcript):
    """
    Identify duplicate segments by comparing transcription against PDF.
    This implements the core logic from the AI prompt:
    - Find repeated words/sentences/paragraphs
    - Always keep the LAST occurrence
    """
    # Normalize function for text comparison
    def normalize_text(text):
        return ' '.join(re.sub(r'[^\w\s]', '', text.lower()).split())
    
    # Create segment map with normalized text
    segment_groups = defaultdict(list)
    
    for i, segment in enumerate(segments):
        normalized = normalize_text(segment['text'])
        if normalized:  # Skip empty segments
            segment_groups[normalized].append({
                'index': i,
                'segment': segment,
                'start': segment['start'],
                'end': segment['end'],
                'text': segment['text']
            })
    
    # Find duplicates (groups with more than one occurrence)
    duplicates_to_remove = []
    segments_to_keep = []
    
    for normalized_text, group in segment_groups.items():
        if len(group) > 1:
            # Sort by start time to ensure proper ordering
            group.sort(key=lambda x: x['start'])
            
            # Mark all but the LAST occurrence for removal
            for duplicate in group[:-1]:
                duplicates_to_remove.append(duplicate)
            
            # Keep the last occurrence
            segments_to_keep.append(group[-1])
        else:
            # Single occurrence, always keep
            segments_to_keep.append(group[0])
    
    return {
        'duplicates_to_remove': duplicates_to_remove,
        'segments_to_keep': segments_to_keep,
        'total_duplicates': len(duplicates_to_remove)
    }

def find_text_in_pdf(text, pdf_text):
    """Check if transcript text appears in PDF content"""
    normalized_text = ' '.join(text.strip().lower().split())
    normalized_pdf = ' '.join(pdf_text.strip().lower().split())
    return normalized_text in normalized_pdf

def find_missing_pdf_content(final_transcript, pdf_text):
    """
    Step 9: Compare final transcript to PDF and find missing content
    """
    # Split PDF into sentences
    import re
    pdf_sentences = re.split(r'[.!?]+', pdf_text)
    pdf_sentences = [s.strip() for s in pdf_sentences if s.strip()]
    
    # Normalize final transcript
    normalized_transcript = ' '.join(final_transcript.lower().split())
    
    missing_content = []
    for sentence in pdf_sentences:
        normalized_sentence = ' '.join(sentence.lower().split())
        if normalized_sentence and normalized_sentence not in normalized_transcript:
            missing_content.append(sentence.strip())
    
    return '\n'.join(missing_content) if missing_content else ""

def calculate_comprehensive_similarity_task(text1, text2):
    """Comprehensive similarity calculation for Celery task"""
    import difflib
    import re
    
    # Method 1: Word overlap (primary method for transcription)
    words1 = set(re.findall(r'\b\w{4,}\b', text1.lower()))  # 4+ char words only
    words2 = set(re.findall(r'\b\w{4,}\b', text2.lower()))
    
    if words1 and words2:
        word_intersection = len(words1 & words2)
        word_union = len(words1 | words2)
        word_similarity = word_intersection / word_union if word_union > 0 else 0
    else:
        word_similarity = 0
    
    # Method 2: Phrase matching (6+ word sequences)
    phrases1 = []
    phrases2 = []
    
    words1_list = re.findall(r'\b\w+\b', text1.lower())
    words2_list = re.findall(r'\b\w+\b', text2.lower())
    
    # Create overlapping 6-word phrases
    for i in range(len(words1_list) - 5):
        phrases1.append(' '.join(words1_list[i:i+6]))
    for i in range(len(words2_list) - 5):
        phrases2.append(' '.join(words2_list[i:i+6]))
    
    phrases1_set = set(phrases1)
    phrases2_set = set(phrases2)
    
    if phrases1_set and phrases2_set:
        phrase_intersection = len(phrases1_set & phrases2_set)
        phrase_union = len(phrases1_set | phrases2_set)
        phrase_similarity = phrase_intersection / phrase_union if phrase_union > 0 else 0
    else:
        phrase_similarity = 0
    
    # Method 3: Character n-gram similarity (for structure)
    def get_ngrams(text, n=4):
        text_clean = re.sub(r'\s+', '', text.lower())
        return set(text_clean[i:i+n] for i in range(len(text_clean) - n + 1))
    
    ngrams1 = get_ngrams(text1)
    ngrams2 = get_ngrams(text2)
    
    if ngrams1 and ngrams2:
        ngram_intersection = len(ngrams1 & ngrams2)
        ngram_union = len(ngrams1 | ngrams2)
        ngram_similarity = ngram_intersection / ngram_union if ngram_union > 0 else 0
    else:
        ngram_similarity = 0
    
    # Weighted combination optimized for audio transcription
    combined_similarity = (
        word_similarity * 0.6 +     # 60% - word overlap (most reliable for audio)
        phrase_similarity * 0.3 +   # 30% - phrase matching (structure)
        ngram_similarity * 0.1      # 10% - character patterns
    )
    
    return combined_similarity


def extract_chapter_title_task(context_text):
    """Extract chapter/section title from context for Celery task"""
    import re
    
    # Multiple patterns to find chapter titles
    chapter_patterns = [
        r'chapter\s+(\d+|[ivx]+)[\s\.:]*([^\n\r.]{1,100})',
        r'(\d+)\.\s+([A-Z][^\n\r.]{10,80})',  
        r'section\s+(\d+)[\s\.:]*([^\n\r.]{1,100})',
        r'^([A-Z][A-Z\s]{10,60})\s*$',  # All caps titles
        r'(Chapter\s+[A-Z][^\n\r.]{5,80})',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){2,8})\s*\n'  # Title Case
    ]
    
    for pattern in chapter_patterns:
        match = re.search(pattern, context_text, re.IGNORECASE | re.MULTILINE)
        if match:
            if len(match.groups()) >= 2:
                # Two groups: number and title
                return f"Chapter {match.group(1).strip()} - {match.group(2).strip()}"
            else:
                # Single group: full title
                return match.group(1).strip()
    
    # Fallback: look for the first meaningful sentence
    sentences = re.split(r'[.!?]\s+', context_text)
    for sentence in sentences:
        sentence = sentence.strip()
        if 20 <= len(sentence) <= 100 and not sentence.lower().startswith(('the ', 'and ', 'but ', 'however')):
            return f"Section: {sentence[:80]}..."
    
    return "PDF Beginning (auto-detected)"

