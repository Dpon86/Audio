"""
Duplicate Views for audioDiagnostic app.
"""
from ._base import *

from ..tasks import detect_duplicates_task, process_confirmed_deletions_task

class ProjectRefinePDFBoundariesView(APIView):
    """
    POST: User refines the PDF match boundaries by selecting exact start and end positions
    Saves the refined boundaries for use in duplicate detection
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Verify prerequisites
        if not project.pdf_match_completed:
            return Response({'error': 'PDF matching must be completed first'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if not project.pdf_text:
            return Response({'error': 'PDF text not available'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get user-selected boundaries
            start_char = request.data.get('start_char')
            end_char = request.data.get('end_char')
            
            if start_char is None or end_char is None:
                return Response({'error': 'start_char and end_char are required'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            start_char = int(start_char)
            end_char = int(end_char)
            
            # Validate boundaries
            if start_char < 0 or end_char > len(project.pdf_text):
                return Response({'error': 'Invalid character positions'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            if start_char >= end_char:
                return Response({'error': 'Start position must be before end position'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Update project with refined boundaries
            project.pdf_match_start_char = start_char
            project.pdf_match_end_char = end_char
            
            # Extract the refined section
            refined_section = project.pdf_text[start_char:end_char]
            project.pdf_matched_section = refined_section
            
            # Recalculate confidence with refined section
            if project.combined_transcript:
                # Simple word overlap confidence
                import re
                pdf_words = set(re.findall(r'\b\w{4,}\b', refined_section.lower()))
                transcript_words = set(re.findall(r'\b\w{4,}\b', project.combined_transcript.lower()))
                
                if pdf_words and transcript_words:
                    intersection = len(pdf_words & transcript_words)
                    union = len(pdf_words | transcript_words)
                    confidence = intersection / union if union > 0 else 0
                    project.pdf_match_confidence = confidence
            
            project.save()
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"PDF boundaries refined for project {project_id}: chars {start_char}-{end_char} (length: {end_char - start_char})")
            
            return Response({
                'success': True,
                'message': 'PDF boundaries refined successfully',
                'start_char': start_char,
                'end_char': end_char,
                'section_length': end_char - start_char,
                'confidence': project.pdf_match_confidence,
                'refined_section_preview': refined_section[:500] + '...' if len(refined_section) > 500 else refined_section
            })
            
        except ValueError:
            return Response({'error': 'Invalid character position format'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to refine PDF boundaries for project {project_id}: {str(e)}")
            return Response({'error': f'Failed to refine boundaries: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProjectDetectDuplicatesView(APIView):
    """
    POST: Step 2 - Compare audio transcript against PDF to detect duplicates
    Returns detailed comparison with highlighted differences and duplicate segments
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Verify prerequisites
        if not project.pdf_match_completed:
            return Response({'error': 'PDF matching must be completed first'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already in progress
        if project.status in ['detecting_duplicates', 'processing']:
            return Response({'error': 'Duplicate detection already in progress'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Start duplicate detection as async Celery task to prevent timeouts
            task = detect_duplicates_task.delay(project.id)
            
            # Update project status
            project.status = 'detecting_duplicates'
            project.save()
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Started duplicate detection task {task.id} for project {project_id}")
            
            return Response({
                'success': True,
                'message': 'Duplicate detection started in background',
                'task_id': task.id,
                'project_id': project.id,
                'status': 'detecting_duplicates',
                'phase': 'duplicate_detection'
            })
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to start duplicate detection task for project {project_id}: {str(e)}")
            return Response({'error': f'Failed to start duplicate detection: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def detect_duplicates_against_pdf(self, segments, pdf_section, full_transcript):
        """
        Compare audio segments against PDF to find duplicates
        Returns detailed analysis with timestamps and highlighting
        """
        import re
        from collections import defaultdict
        
        # Normalize function for text comparison
        def normalize_text(text):
            return ' '.join(re.sub(r'[^\w\s]', '', text.lower()).split())
        
        # Group segments by normalized text
        text_groups = defaultdict(list)
        for segment in segments:
            normalized = normalize_text(segment['text'])
            if len(normalized) > 10:  # Only consider substantial segments
                text_groups[normalized].append(segment)
        
        # Find duplicates (groups with multiple occurrences)
        duplicates = []
        duplicate_groups = {}
        group_id = 0
        
        for normalized_text, occurrences in text_groups.items():
            if len(occurrences) > 1:
                # Sort by audio file order and timestamp to identify last occurrence
                sorted_occurrences = sorted(occurrences, 
                    key=lambda x: (x['audio_file_id'], x['start_time']))
                
                # Mark all but last as duplicates
                for i, segment in enumerate(sorted_occurrences):
                    is_last = (i == len(sorted_occurrences) - 1)
                    
                    duplicates.append({
                        'group_id': group_id,
                        'segment_id': segment['id'],
                        'audio_file_id': segment['audio_file_id'],
                        'audio_file_title': segment['audio_file_title'],
                        'text': segment['text'],
                        'start_time': segment['start_time'],
                        'end_time': segment['end_time'],
                        'normalized_text': normalized_text,
                        'is_last_occurrence': is_last,
                        'recommended_action': 'keep' if is_last else 'delete',
                        'occurrence_number': i + 1,
                        'total_occurrences': len(sorted_occurrences)
                    })
                
                duplicate_groups[group_id] = {
                    'normalized_text': normalized_text,
                    'original_text': sorted_occurrences[0]['text'],
                    'occurrences': len(sorted_occurrences),
                    'segments': [seg['segment_id'] for seg in sorted_occurrences]
                }
                group_id += 1
        
        # Generate text comparison with PDF
        pdf_comparison = self.compare_with_pdf(full_transcript, pdf_section)
        
        return {
            'duplicates': duplicates,
            'duplicate_groups': duplicate_groups,
            'pdf_comparison': pdf_comparison,
            'summary': {
                'total_duplicate_segments': len(duplicates),
                'unique_duplicate_groups': len(duplicate_groups),
                'segments_to_delete': len([d for d in duplicates if d['recommended_action'] == 'delete']),
                'segments_to_keep': len([d for d in duplicates if d['recommended_action'] == 'keep'])
            }
        }
    
    def compare_with_pdf(self, transcript, pdf_section):
        """
        Create side-by-side comparison highlighting differences
        """
        import difflib
        
        # Normalize texts for comparison
        transcript_lines = transcript.split('\n')
        pdf_lines = pdf_section.split('\n')
        
        # Generate unified diff
        diff = list(difflib.unified_diff(
            pdf_lines, 
            transcript_lines,
            fromfile='PDF (Reference)', 
            tofile='Audio Transcript',
            lineterm=''
        ))
        
        return {
            'pdf_text': pdf_section[:1000] + '...',  # Preview
            'transcript_text': transcript[:1000] + '...',  # Preview
            'diff_lines': diff[:50],  # First 50 diff lines
            'similarity_score': difflib.SequenceMatcher(None, pdf_section, transcript).ratio()
        }


class ProjectDuplicatesReviewView(APIView):
    """
    GET: Step 3 - Get detected duplicates for interactive review
    Returns all duplicates with audio segment info for user confirmation
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Verify prerequisites
        if not project.duplicates_detection_completed:
            return Response({'error': 'Duplicate detection must be completed first'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get stored duplicate results
            duplicate_results = project.duplicates_detected or {}
            logger.info(f"Loading duplicate results for project {project_id}")
            logger.info(f"Duplicate results keys: {duplicate_results.keys()}")
            logger.info(f"Number of duplicates: {len(duplicate_results.get('duplicates', []))}")
            
            # Enrich with audio file paths for playback
            enriched_duplicates = []
            for idx, duplicate in enumerate(duplicate_results.get('duplicates', [])):
                try:
                    logger.debug(f"Processing duplicate {idx}: {type(duplicate)}")
                    logger.debug(f"Duplicate keys: {duplicate.keys() if isinstance(duplicate, dict) else 'NOT A DICT'}")
                    
                    # Get audio file info for playback
                    audio_file_id = duplicate.get('audio_file_id') if isinstance(duplicate, dict) else None
                    if not audio_file_id:
                        logger.error(f"Duplicate {idx} has no audio_file_id: {duplicate}")
                        continue
                        
                    audio_file = AudioFile.objects.get(id=audio_file_id)
                    
                    enriched_duplicate = {
                        **duplicate,
                        'audio_file_path': audio_file.file.url if audio_file.file else None,
                        'audio_file_name': audio_file.filename,
                        'duration': duplicate.get('end_time', 0) - duplicate.get('start_time', 0),
                        'preview_text': duplicate.get('text', '')[:100] + '...' if len(duplicate.get('text', '')) > 100 else duplicate.get('text', '')
                    }
                    enriched_duplicates.append(enriched_duplicate)
                except Exception as e:
                    logger.error(f"Error processing duplicate {idx}: {str(e)}", exc_info=True)
                    continue
            
            # Group duplicates by group_id for easier frontend handling
            grouped_duplicates = {}
            for duplicate in enriched_duplicates:
                group_id = duplicate['group_id']
                if group_id not in grouped_duplicates:
                    grouped_duplicates[group_id] = {
                        'group_info': duplicate_results['duplicate_groups'].get(str(group_id), {}),
                        'occurrences': []
                    }
                grouped_duplicates[group_id]['occurrences'].append(duplicate)
            
            return Response({
                'success': True,
                'duplicates': enriched_duplicates,
                'grouped_duplicates': grouped_duplicates,
                'summary': duplicate_results.get('summary', {}),
                'pdf_comparison': duplicate_results.get('pdf_comparison', {}),
                'review_ready': True
            })
            
        except Exception as e:
            logger.error(f"Duplicate review data retrieval failed: {str(e)}")
            return Response({'error': f'Failed to get duplicate review data: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProjectConfirmDeletionsView(APIView):
    """
    POST: Step 4 - Accept user-confirmed deletions and process final audio
    Removes confirmed duplicate segments and generates clean audio file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Get user confirmations
        confirmed_deletions = request.data.get('confirmed_deletions', [])
        
        if not confirmed_deletions:
            return Response({'error': 'No deletions confirmed'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Save user confirmations
            project.duplicates_confirmed_for_deletion = confirmed_deletions
            project.save()
            
            # Start background task to process deletions
            from audioDiagnostic.tasks import process_confirmed_deletions_task
            task = process_confirmed_deletions_task.delay(project_id, confirmed_deletions)
            
            return Response({
                'success': True,
                'message': 'Processing confirmed deletions...',
                'task_id': task.id,
                'confirmed_count': len(confirmed_deletions)
            })
            
        except Exception as e:
            logger.error(f"Deletion confirmation failed: {str(e)}")
            return Response({'error': f'Failed to process deletions: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ProjectVerifyCleanupView(APIView):
    """
    POST: Step 4 - Verify clean audio against PDF section
    Compares the transcribed clean audio against the original PDF matched section
    to ensure all duplicates were removed successfully
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Check if clean audio has been transcribed
        if not project.clean_audio_transcribed:
            return Response({
                'error': 'Clean audio has not been transcribed yet. Please wait for processing to complete.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get verification transcript (is_verification=True)
            verification_segments = TranscriptionSegment.objects.filter(
                audio_file__project=project,
                is_verification=True
            ).order_by('segment_index')
            
            if not verification_segments.exists():
                return Response({
                    'error': 'Verification transcript not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Combine verification transcript
            clean_transcript = ' '.join([seg.text for seg in verification_segments])
            
            # Get original PDF section (using character positions if available)
            pdf_section = project.pdf_matched_section or ''
            if project.pdf_match_start_char and project.pdf_match_end_char and project.pdf_text:
                pdf_section = project.pdf_text[project.pdf_match_start_char:project.pdf_match_end_char]
            
            # Perform comparison analysis
            from difflib import SequenceMatcher
            
            # Calculate similarity ratio
            similarity = SequenceMatcher(None, 
                                        clean_transcript.lower().strip(), 
                                        pdf_section.lower().strip()).ratio()
            
            # Find common phrases (potential remaining duplicates)
            words_in_transcript = set(clean_transcript.lower().split())
            words_in_pdf = set(pdf_section.lower().split())
            common_words = words_in_transcript.intersection(words_in_pdf)
            
            # Check for repeated phrases in clean transcript
            transcript_sentences = clean_transcript.split('.')
            repeated_sentences = []
            seen = {}
            for sentence in transcript_sentences:
                sentence = sentence.strip().lower()
                if len(sentence) > 10:  # Ignore very short sentences
                    if sentence in seen:
                        repeated_sentences.append(sentence)
                    seen[sentence] = True
            
            # Save verification results
            verification_results = {
                'similarity_to_pdf': similarity,
                'clean_transcript_length': len(clean_transcript),
                'pdf_section_length': len(pdf_section),
                'common_words_count': len(common_words),
                'repeated_sentences_found': len(repeated_sentences),
                'repeated_sentences': repeated_sentences[:5] if repeated_sentences else [],  # Limit to first 5
                'verification_date': str(datetime.datetime.now())
            }
            
            project.verification_results = verification_results
            project.verification_completed = True
            project.save()
            
            return Response({
                'success': True,
                'clean_transcript': clean_transcript,
                'pdf_section': pdf_section,
                'verification_results': verification_results,
                'segments': [{
                    'text': seg.text,
                    'start_time': seg.start_time,
                    'end_time': seg.end_time
                } for seg in verification_segments]
            })
            
        except Exception as e:
            logger.error(f"Verification failed: {str(e)}")
            return Response({
                'error': f'Verification failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ProjectRedetectDuplicatesView(APIView):
    """
    POST: Step 6 - Create a NEW child project for iterative cleaning
    Copies PDF and clean audio to a fresh project, starts from Step 1
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        parent_project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Verify prerequisites
        if not parent_project.final_processed_audio:
            return Response({'error': 'Clean audio must be generated first'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Create a new child project
            from django.core.files import File
            import os
            
            child_project = AudioProject.objects.create(
                user=request.user,
                title=f"{parent_project.title} - Iteration {parent_project.iteration_number + 1}",
                parent_project=parent_project,
                iteration_number=parent_project.iteration_number + 1,
                status='setup'
            )
            
            logger.info(f"Created child project {child_project.id} from parent {parent_project.id}")
            
            # Copy PDF file - check if it exists first
            if parent_project.pdf_file:
                pdf_path = parent_project.pdf_file.path
                logger.info(f"Parent PDF path: {pdf_path}")
                logger.info(f"Parent PDF exists: {os.path.exists(pdf_path)}")
                
                if os.path.exists(pdf_path):
                    try:
                        with open(pdf_path, 'rb') as pdf:
                            child_project.pdf_file.save(
                                f"iteration_{child_project.iteration_number}_{os.path.basename(pdf_path)}",
                                File(pdf),
                                save=False  # Don't save yet
                            )
                        logger.info(f"PDF copied successfully to: {child_project.pdf_file.path}")
                    except Exception as e:
                        logger.error(f"Failed to copy PDF: {str(e)}")
                        raise
                else:
                    logger.error(f"Parent PDF file not found at: {pdf_path}")
                    raise FileNotFoundError(f"Parent PDF file not found: {pdf_path}")
                
                # Copy PDF metadata
                child_project.pdf_text = parent_project.pdf_text
                child_project.pdf_matched_section = parent_project.pdf_matched_section
                child_project.pdf_chapter_title = parent_project.pdf_chapter_title
                child_project.pdf_match_start_char = parent_project.pdf_match_start_char
                child_project.pdf_match_end_char = parent_project.pdf_match_end_char
                child_project.pdf_match_completed = True
                logger.info("PDF metadata copied")
            
            # Create single audio file from clean audio
            clean_audio_path = parent_project.final_processed_audio.path
            
            logger.info(f"Creating audio file from: {clean_audio_path}")
            logger.info(f"Clean audio exists: {os.path.exists(clean_audio_path)}")
            
            if not os.path.exists(clean_audio_path):
                raise FileNotFoundError(f"Clean audio file not found: {clean_audio_path}")
            
            audio_file = AudioFile.objects.create(
                project=child_project,
                title=f"Clean Audio - Iteration {child_project.iteration_number}",
                filename=f"iteration_{child_project.iteration_number}_{os.path.basename(clean_audio_path)}",
                order_index=0,
                status='pending'
            )
            
            logger.info(f"Created AudioFile with ID: {audio_file.id}, status: {audio_file.status}")
            
            with open(clean_audio_path, 'rb') as audio:
                audio_file.file.save(
                    f"iteration_{child_project.iteration_number}_{os.path.basename(clean_audio_path)}",
                    File(audio),
                    save=False  # Don't save yet
                )
            
            audio_file.status = 'uploaded'
            audio_file.save()
            
            logger.info(f"Audio file saved with status: {audio_file.status}, file path: {audio_file.file.path}")
            
            # Verify the audio file is queryable
            verify_audio = AudioFile.objects.filter(project=child_project, status='uploaded')
            logger.info(f"Verification: Found {verify_audio.count()} uploaded audio files in child project")
            
            child_project.status = 'ready'
            child_project.save()
            
            logger.info(f"Child project {child_project.id} setup complete - Status: {child_project.status}, Audio files: {verify_audio.count()}")
            
            return Response({
                'success': True,
                'message': 'Created new iteration project',
                'child_project_id': child_project.id,
                'iteration_number': child_project.iteration_number
            })
            
        except Exception as e:
            logger.error(f"Failed to create child project: {str(e)}")
            return Response({'error': f'Failed to create iteration project: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========================= LEGACY VIEWS (BACKWARD COMPATIBILITY) =========================



