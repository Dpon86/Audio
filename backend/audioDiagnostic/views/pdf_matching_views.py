"""
Pdf Matching Views for audioDiagnostic app.
"""
from ._base import *

from ..tasks import match_pdf_to_audio_task, validate_transcript_against_pdf_task

class ProjectMatchPDFView(APIView):
    """
    POST: Step 1 - Match audio transcript to PDF section/chapter
    Identifies which section of the PDF corresponds to the audio transcript
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Verify prerequisites
        if not project.pdf_file:
            return Response({'error': 'No PDF file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
        
        audio_files = project.audio_files.filter(status='transcribed')
        if not audio_files.exists():
            return Response({'error': 'No transcribed audio files found. Please transcribe audio first.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already in progress
        if project.status in ['matching_pdf', 'processing']:
            return Response({'error': 'PDF matching already in progress'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Start PDF matching as async Celery task to prevent timeouts
            task = match_pdf_to_audio_task.delay(project.id)
            
            # Update project status
            project.status = 'matching_pdf'
            project.save()
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Started PDF matching task {task.id} for project {project_id}")
            
            return Response({
                'success': True,
                'message': 'PDF matching started in background',
                'task_id': task.id,
                'project_id': project.id,
                'status': 'matching_pdf',
                'phase': 'pdf_matching'
            })
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to start PDF matching task for project {project_id}: {str(e)}")
            return Response({'error': f'Failed to start PDF matching: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def find_pdf_section_match(self, pdf_text, transcript):
        """
        Smart PDF-to-Audio matching using sentence-based boundaries
        Uses first few sentences and last few sentences to find start/end positions
        Returns: dict with matched_section, confidence, chapter_title
        """
        import difflib
        import re
        import logging
        
        logger = logging.getLogger(__name__)
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
            logger.info(f"First chunk: {first_chunk[:100]}...")
            logger.info(f"Last chunk: {last_chunk[:100]}...")
        
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
                logger.info(f"Matched text: {search_text[:80]}...")
                break
        
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
                    logger.info(f"Matched text: {search_text[:80]}...")
                    break
        
        # PHASE 3: Extract the matched section
        if start_position is not None and end_position is not None and end_position > start_position:
            # SUCCESS: Found both start and end boundaries
            matched_length = end_position - start_position
            matched_section_clean = pdf_clean[start_position:end_position]
            
            # Calculate confidence
            confidence = self.calculate_comprehensive_similarity(matched_section_clean, transcript_clean)
            
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
            chapter_title = self.extract_chapter_title(chapter_context)
            
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
            transcript_to_pdf_ratio = len(transcript_clean) / len(pdf_clean)
            estimated_length = min(
                int(len(transcript_clean) * 1.5),  # Assume PDF is 1.5x longer due to formatting
                len(pdf_clean) - start_position    # Don't exceed PDF length
            )
            
            estimated_end = start_position + estimated_length
            matched_section_clean = pdf_clean[start_position:estimated_end]
            confidence = self.calculate_comprehensive_similarity(matched_section_clean, transcript_clean)
            
            # Map back to original text
            char_ratio = len(pdf_text) / len(pdf_clean)
            original_start = int(start_position * char_ratio)
            original_end = int(estimated_end * char_ratio)
            
            expanded_start = max(0, original_start - 100)
            expanded_end = min(len(pdf_text), original_end + 100)
            
            matched_section = pdf_text[expanded_start:expanded_end]
            chapter_title = self.extract_chapter_title(pdf_text[max(0, expanded_start - 800):expanded_start + 300])
            
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
                confidence = self.calculate_comprehensive_similarity(pdf_chunk, transcript_clean)
                
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
            chapter_title = self.extract_chapter_title(pdf_text[max(0, original_start - 800):original_start + 300])
            
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
    
    def calculate_comprehensive_similarity(self, text1, text2):
        """Comprehensive similarity for large text comparison"""
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
    
    def calculate_text_similarity(self, text1, text2):
        """Legacy method - redirect to comprehensive similarity"""
        return self.calculate_comprehensive_similarity(text1, text2)
    
    def extract_chapter_title(self, context_text):
        """Extract chapter/section title from context"""
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


class ProjectValidatePDFView(APIView):
    """
    POST /api/projects/{id}/validate-against-pdf/
    Start word-by-word validation of clean transcript against PDF section
    Returns task_id for progress tracking
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id):
        try:
            project = AudioProject.objects.get(pk=project_id, user=request.user)
            
            # Validate prerequisites
            if not project.pdf_matched_section:
                return Response({
                    'error': 'PDF section not matched yet. Complete Step 2a first.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not project.duplicates_confirmed_for_deletion:
                return Response({
                    'error': 'No confirmed deletions to validate. Complete Step 2c first.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Start validation task
            from audioDiagnostic.tasks import validate_transcript_against_pdf_task
            task = validate_transcript_against_pdf_task.delay(project.id)
            
            logger.info(f"Started PDF validation task {task.id} for project {project.id}")
            
            return Response({
                'success': True,
                'task_id': task.id,
                'message': 'PDF validation started'
            })
            
        except AudioProject.DoesNotExist:
            return Response({
                'error': 'Project not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Failed to start PDF validation: {str(e)}")
            return Response({
                'error': f'Failed to start validation: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ProjectValidationProgressView(APIView):
    """
    GET /api/projects/{id}/validation-progress/{task_id}/
    Check progress of PDF validation task
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, task_id):
        try:
            project = AudioProject.objects.get(pk=project_id, user=request.user)
            
            # Get task status from Celery
            from celery.result import AsyncResult
            task = AsyncResult(task_id)
            
            # Get progress from Redis
            from audioDiagnostic.utils import get_redis_connection
            r = get_redis_connection()
            progress = r.get(f"progress:{task_id}")
            progress_value = int(progress) if progress else 0
            
            response_data = {
                'task_id': task_id,
                'status': task.state,
                'progress': progress_value
            }
            
            if task.state == 'SUCCESS':
                # Task completed - return results from task (includes HTML)
                task_result = task.result
                response_data['completed'] = True
                if task_result and 'results' in task_result:
                    response_data['results'] = task_result['results']
                else:
                    # Fallback to database (without HTML)
                    project.refresh_from_db()
                    response_data['results'] = project.pdf_validation_results
                
            elif task.state == 'FAILURE':
                response_data['error'] = str(task.info)
                
            return Response(response_data)
            
        except AudioProject.DoesNotExist:
            return Response({
                'error': 'Project not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Failed to get validation progress: {str(e)}")
            return Response({
                'error': f'Failed to get progress: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


