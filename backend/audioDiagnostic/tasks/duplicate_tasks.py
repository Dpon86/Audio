"""
Duplicate Tasks for audioDiagnostic app.
"""
from ._base import *
from audioDiagnostic.tasks.utils import get_final_transcript_without_duplicates, get_audio_duration, save_transcription_to_db, normalize
from .audio_processing_tasks import assemble_final_audio, generate_clean_audio

@shared_task(bind=True)
def process_project_duplicates_task(self, project_id):
    """
    Steps 5-10: Process ALL transcribed audio files in a project together:
    5. Store all transcriptions for editing
    6. Compare transcribed text to PDF book and locate sections  
    7. Find repeated words, sentences, paragraphs across ALL audio files
    8. Use timestamps to delete repeated content, keeping LAST occurrence
    9. Compare to PDF again and locate missing content
    10. Return final audio file without repetitions
    """
    task_id = self.request.id
    
    # Get Redis connection
    r = get_redis_connection()
    
    # Set up Docker and Celery infrastructure
    if not docker_celery_manager.setup_infrastructure():
        raise Exception("Failed to set up Docker and Celery infrastructure")
    
    # Register this task
    docker_celery_manager.register_task(task_id)
    
    try:
        # Get project and verify all audio files are transcribed
        from audioDiagnostic.models import AudioProject, AudioFile, ProcessingResult
        from PyPDF2 import PdfReader
        import hashlib
        
        project = AudioProject.objects.get(id=project_id)
        audio_files = project.audio_files.filter(status='transcribed').order_by('order_index')
        
        if not audio_files.exists():
            raise ValueError("No transcribed audio files found. Please transcribe audio files first.")
            
        if not project.pdf_file:
            raise ValueError("No PDF file provided")
        
        project.status = 'processing'
        project.save()
        
        r.set(f"progress:{task_id}", 5)
        logger.info(f"Starting duplicate processing for project {project_id} with {audio_files.count()} audio files")
        
        # Step 5: Collect all transcriptions (already stored, now compile)
        all_segments = []
        combined_transcript = []
        total_original_duration = 0
        
        for audio_file in audio_files:
            segments = TranscriptionSegment.objects.filter(audio_file=audio_file).order_by('segment_index')
            for segment in segments:
                all_segments.append({
                    'audio_file': audio_file,
                    'segment': segment,
                    'text': segment.text.strip(),
                    'start_time': segment.start_time,
                    'end_time': segment.end_time,
                    'file_order': audio_file.order_index
                })
            combined_transcript.append(audio_file.transcript_text or "")
            total_original_duration += audio_file.original_duration or 0
        
        project.combined_transcript = "\n".join(combined_transcript)
        project.save()
        
        r.set(f"progress:{task_id}", 15)
        
        # Step 6: Extract PDF text and compare to find book sections
        logger.info("Extracting PDF text and matching to transcriptions")
        reader = PdfReader(project.pdf_file.path)
        pdf_text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
        project.pdf_text = pdf_text
        project.save()
        
        # Match each segment to PDF content
        pdf_matches = 0
        for seg_data in all_segments:
            segment = seg_data['segment']
            if find_text_in_pdf(segment.text, pdf_text):
                segment.pdf_match_found = True
                pdf_matches += 1
            segment.save()
        
        r.set(f"progress:{task_id}", 30)
        
        # Step 7: Find repeated words, sentences, paragraphs across ALL audio files
        logger.info("Identifying duplicate content across all audio files")
        duplicates_found = identify_all_duplicates(all_segments)
        
        r.set(f"progress:{task_id}", 50)
        
        # Step 8: Mark duplicates for removal, keeping LAST occurrence of each
        logger.info("Marking duplicates for removal (keeping last occurrence)")
        duplicates_removed = mark_duplicates_for_removal(duplicates_found)
        
        r.set(f"progress:{task_id}", 70)
        
        # Step 9: Compare final result to PDF and find missing content  
        logger.info("Checking for missing content compared to PDF")
        final_transcript = get_final_transcript_without_duplicates(all_segments)
        missing_content = find_missing_pdf_content(final_transcript, pdf_text)
        project.missing_content = missing_content
        
        r.set(f"progress:{task_id}", 85)
        
        # Step 10: Generate final audio file without repetitions
        logger.info("Assembling final audio file without duplicates")
        final_audio_path = assemble_final_audio(project, all_segments)
        
        # Save final results
        project.final_processed_audio = final_audio_path
        project.total_duplicates_found = len(duplicates_removed)
        project.status = 'completed'
        project.save()
        
        # Create detailed processing result
        ProcessingResult.objects.update_or_create(
            project=project,
            defaults={
                'total_segments_processed': len(all_segments),
                'duplicates_removed': len(duplicates_removed),
                'words_removed': sum(1 for d in duplicates_removed if d['type'] == 'word'),
                'sentences_removed': sum(1 for d in duplicates_removed if d['type'] == 'sentence'),
                'paragraphs_removed': sum(1 for d in duplicates_removed if d['type'] == 'paragraph'),
                'original_total_duration': total_original_duration,
                'final_duration': get_audio_duration(final_audio_path),
                'pdf_coverage_percentage': (pdf_matches / len(all_segments)) * 100 if all_segments else 0,
                'missing_content_count': len(missing_content.split('\n')) if missing_content else 0,
                'processing_log': duplicates_removed
            }
        )
        
        r.set(f"progress:{task_id}", 100)
        
        # Unregister task
        docker_celery_manager.unregister_task(task_id)
        
        return {
            'status': 'completed',
            'message': f'Processing complete. Removed {len(duplicates_removed)} duplicates.',
            'duplicates_removed': len(duplicates_removed),
            'final_audio': final_audio_path
        }
        
    except Exception as e:
        logger.error(f"Processing failed for project {project_id}: {str(e)}")
        
        # Update project with error
        try:
            project.status = 'failed'
            project.error_message = str(e)
            project.save()
        except:
            pass
            
        # Unregister task even on failure
        docker_celery_manager.unregister_task(task_id)
            
        r.set(f"progress:{task_id}", -1)
        raise e

@shared_task(bind=True)
def detect_duplicates_task(self, project_id, use_clean_audio=False):
    """
    Celery task for duplicate detection to prevent frontend timeouts
    Compares audio segments against PDF to find duplicates
    
    Args:
        project_id: ID of the AudioProject
        use_clean_audio: If True, use is_verification=True segments (clean audio)
                        If False, use original transcription segments
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
        from audioDiagnostic.models import AudioProject, AudioFile, TranscriptionSegment
        project = AudioProject.objects.get(id=project_id)
        
        r.set(f"progress:{task_id}", 5)
        logger.info(f"Starting duplicate detection for project {project_id} (use_clean_audio={use_clean_audio})")
        
        # Verify prerequisites
        if not project.pdf_match_completed:
            raise ValueError("PDF matching must be completed first")
        
        if not project.pdf_matched_section:
            raise ValueError("No PDF matched section found")
        
        if use_clean_audio and not project.final_processed_audio:
            raise ValueError("Clean audio must be generated first")
        
        r.set(f"progress:{task_id}", 15)
        
        # Get transcription segments based on use_clean_audio flag
        logger.info(f"Collecting transcription segments (clean_audio={use_clean_audio})...")
        all_segments = []
        audio_files = project.audio_files.filter(status='transcribed').order_by('order_index')
        
        total_files = audio_files.count()
        
        for i, audio_file in enumerate(audio_files):
            # Filter by is_verification if using clean audio
            if use_clean_audio:
                segments = TranscriptionSegment.objects.filter(
                    audio_file=audio_file, 
                    is_verification=True
                ).order_by('segment_index')
            else:
                segments = TranscriptionSegment.objects.filter(
                    audio_file=audio_file
                ).order_by('segment_index')
                
            for segment in segments:
                all_segments.append({
                    'id': segment.id,
                    'audio_file_id': audio_file.id,
                    'audio_file_title': audio_file.title,
                    'text': segment.text.strip(),
                    'start_time': segment.start_time,
                    'end_time': segment.end_time,
                    'segment_index': segment.segment_index
                })
            
            # Update progress for segment collection (15-40%)
            progress = 15 + int((i + 1) / total_files * 25)
            r.set(f"progress:{task_id}", progress)
        
        logger.info(f"Collected {len(all_segments)} segments from {total_files} audio files")
        r.set(f"progress:{task_id}", 45)
        
        # Detect duplicates by comparing against PDF
        logger.info("Starting duplicate detection algorithm...")
        duplicate_results = detect_duplicates_against_pdf_task(
            all_segments, 
            project.pdf_matched_section,
            project.combined_transcript,
            task_id,
            r
        )
        
        r.set(f"progress:{task_id}", 90)
        
        # Save results to project
        project.duplicates_detected = duplicate_results
        project.duplicates_detection_completed = True
        project.status = 'duplicates_detected'  # Update status
        project.save()
        
        r.set(f"progress:{task_id}", 100)
        
        # Unregister task
        docker_celery_manager.unregister_task(task_id)
        
        logger.info(f"Duplicate detection completed for project {project_id}")
        logger.info(f"Found {len(duplicate_results.get('duplicates', []))} duplicates")
        
        return {
            'status': 'completed',
            'duplicate_results': {
                'total_segments': len(all_segments),
                'duplicates_found': len(duplicate_results.get('duplicates', [])),
                'detection_completed': True,
                'duplicates_preview': duplicate_results.get('duplicates', [])[:5]  # First 5 for preview
            }
        }
        
    except Exception as e:
        logger.error(f"Duplicate detection failed for project {project_id}: {str(e)}")
        
        # Update project with error
        try:
            project.status = 'failed'
            project.error_message = f"Duplicate detection failed: {str(e)}"
            project.save()
        except:
            pass
            
        # Unregister task even on failure
        docker_celery_manager.unregister_task(task_id)
            
        r.set(f"progress:{task_id}", -1)
        raise e


@shared_task(bind=True)
def process_confirmed_deletions_task(self, project_id, confirmed_deletions, use_clean_audio=False):
    """
    Process user-confirmed deletions and generate final clean audio file
    
    Args:
        project_id: ID of the AudioProject
        confirmed_deletions: List of segment IDs to delete
        use_clean_audio: If True, apply deletions to clean audio (second pass)
                        If False, apply deletions to original audio (first pass)
    """
    task_id = self.request.id
    
    print(f"\n\n===== DELETION TASK STARTED =====")
    print(f"Task ID: {task_id}")
    print(f"Project ID: {project_id}")
    print(f"Deletions: {len(confirmed_deletions)}")
    print(f"===================================\n\n")
    
    logger.info(f"===== TASK STARTED: process_confirmed_deletions_task =====")
    logger.info(f"Task ID: {task_id}")
    logger.info(f"Project ID: {project_id}")
    logger.info(f"Confirmed deletions count: {len(confirmed_deletions)}")
    logger.info(f"Use clean audio: {use_clean_audio}")
    
    # Get Redis connection
    r = get_redis_connection()
    logger.info(f"Redis connection established")
    
    # Set up Docker and Celery infrastructure
    if not docker_celery_manager.setup_infrastructure():
        raise Exception("Failed to set up Docker and Celery infrastructure")
    
    # Register this task
    docker_celery_manager.register_task(task_id)
    
    try:
        from audioDiagnostic.models import AudioProject, AudioFile, TranscriptionSegment
        
        project = AudioProject.objects.get(id=project_id)
        project.status = 'processing_second_pass' if use_clean_audio else 'processing'
        project.save()
        
        r.set(f"progress:{task_id}", 10)
        logger.info(f"Processing {len(confirmed_deletions)} confirmed deletions for project {project_id} (second_pass={use_clean_audio})")
        
        # Get all audio files in order
        audio_files = project.audio_files.filter(status='transcribed').order_by('order_index')
        
        # Create set of segment IDs to delete
        segments_to_delete = set(deletion['segment_id'] for deletion in confirmed_deletions)
        
        r.set(f"progress:{task_id}", 30)
        
        # Calculate duration statistics
        logger.info("Calculating duration statistics...")
        logger.info(f"Segments to delete count: {len(segments_to_delete)}")
        logger.info(f"First few segment IDs to delete: {list(segments_to_delete)[:5]}")
        
        # Get segments based on use_clean_audio flag
        if use_clean_audio:
            # Second pass: use clean audio segments (is_verification=True)
            all_segments = TranscriptionSegment.objects.filter(
                audio_file__project=project,
                is_verification=True
            )
            audio_source = project.final_processed_audio.path if project.final_processed_audio else None
            if not audio_source:
                raise ValueError("Clean audio file not found for second-pass processing")
        else:
            # First pass: use original segments (don't filter by is_verification)
            # Get all segments that belong to transcribed audio files
            all_segments = TranscriptionSegment.objects.filter(
                audio_file__project=project
            ).exclude(is_verification=True)  # Exclude verification segments if any
        
        logger.info(f"Found {all_segments.count()} total segments to analyze")
        
        # Debug: Check a sample segment
        if all_segments.exists():
            sample_seg = all_segments.first()
            logger.info(f"Sample segment - ID: {sample_seg.id}, start: {sample_seg.start_time}, end: {sample_seg.end_time}, duration: {sample_seg.end_time - sample_seg.start_time}")
        
        # Calculate original total duration (sum of all segments)
        original_duration = sum(
            (segment.end_time - segment.start_time) 
            for segment in all_segments
            if segment.start_time is not None and segment.end_time is not None
        )
        
        logger.info(f"Calculated original duration: {original_duration:.2f}s from {all_segments.count()} segments")
        
        # Calculate deleted duration (only confirmed deletions)
        deleted_segments = all_segments.filter(id__in=segments_to_delete)
        logger.info(f"Found {deleted_segments.count()} segments in database matching deletion IDs")
        
        deleted_duration = sum(
            (segment.end_time - segment.start_time)
            for segment in deleted_segments
            if segment.start_time is not None and segment.end_time is not None
        )
        
        logger.info(f"Calculated deleted duration: {deleted_duration:.2f}s from {deleted_segments.count()} segments")
        
        # Final duration is original minus deleted
        final_duration = original_duration - deleted_duration
        
        # Save to project (update if second pass)
        if use_clean_audio:
            # Update with second-pass stats
            project.duration_deleted += deleted_duration  # Add to existing
            project.final_audio_duration = final_duration  # Update final
        else:
            # First pass stats
            project.original_audio_duration = original_duration
            project.duration_deleted = deleted_duration
            project.final_audio_duration = final_duration
        project.save()
        
        logger.info(f"Duration stats - Original: {original_duration:.2f}s, Deleted: {deleted_duration:.2f}s, Final: {final_duration:.2f}s")
        
        r.set(f"progress:{task_id}", 40)
        
        # Mark segments for deletion in database
        for segment_id in segments_to_delete:
            try:
                segment = TranscriptionSegment.objects.get(id=segment_id)
                segment.is_kept = False
                segment.save()
            except TranscriptionSegment.DoesNotExist:
                logger.warning(f"Segment {segment_id} not found")
        
        r.set(f"progress:{task_id}", 50)
        
        # Generate final audio file without deleted segments
        final_audio_path = generate_clean_audio(project, segments_to_delete)
        
        r.set(f"progress:{task_id}", 80)
        
        # Update project with final audio
        from django.core.files import File
        with open(final_audio_path, 'rb') as f:
            project.final_processed_audio.save(
                f"processed_{project.title.replace(' ', '_')}.wav",
                File(f)
            )
        
        # Update project status
        project.status = 'completed'
        project.total_duplicates_found = len(confirmed_deletions)
        project.save()
        
        logger.info(f"Successfully processed deletions for project {project_id}")
        
        # Mark task as complete BEFORE transcription
        r.set(f"progress:{task_id}", 100)
        
        # Step 4: Auto-transcribe the clean audio for verification (don't block completion)
        logger.info(f"Starting automatic transcription of clean audio for verification")
        try:
            transcribe_clean_audio_for_verification(project, final_audio_path)
            project.clean_audio_transcribed = True
            project.save()
            logger.info(f"Clean audio transcription completed for project {project_id}")
        except Exception as transcribe_error:
            logger.error(f"Failed to transcribe clean audio: {str(transcribe_error)}")
            # Don't fail the whole task if transcription fails
        
        return {
            'success': True,
            'deletions_processed': len(confirmed_deletions),
            'final_audio': project.final_processed_audio.url if project.final_processed_audio else None,
            'clean_audio_transcribed': project.clean_audio_transcribed
        }
        
    except Exception as e:
        logger.error(f"Deletion processing failed: {str(e)}")
        project.status = 'failed'
        project.error_message = str(e)
        project.save()
        
        r.set(f"progress:{task_id}", -1)
        raise e
    finally:
        # Unregister task
        docker_celery_manager.unregister_task(task_id)


def identify_all_duplicates(all_segments):
    """
    Step 7: Find repeated words, sentences, paragraphs across ALL audio files
    Returns list of duplicate groups with their occurrences
    """
    from collections import defaultdict
    import re
    
    # Group segments by normalized text
    text_groups = defaultdict(list)
    
    for seg_data in all_segments:
        text = seg_data['text'].strip()
        if not text:
            continue
            
        # Normalize text for comparison
        normalized = ' '.join(text.lower().split())
        
        # Determine content type
        word_count = len(text.split())
        if word_count == 1:
            content_type = 'word'
        elif word_count <= 15:  # Sentences typically under 15 words
            content_type = 'sentence'
        else:
            content_type = 'paragraph'
            
        text_groups[normalized].append({
            'segment_data': seg_data,
            'normalized_text': normalized,
            'content_type': content_type,
            'word_count': word_count
        })
    
    # Find duplicates (groups with more than one occurrence)
    duplicates = {}
    group_id = 0
    
    for normalized_text, occurrences in text_groups.items():
        if len(occurrences) > 1:
            group_id += 1
            duplicate_group_id = f"dup_{group_id}"
            
            duplicates[duplicate_group_id] = {
                'normalized_text': normalized_text,
                'content_type': occurrences[0]['content_type'],
                'occurrences': occurrences,
                'count': len(occurrences)
            }
            
            logger.info(f"Found duplicate group {duplicate_group_id}: {len(occurrences)} occurrences of '{normalized_text[:50]}...'")
    
    return duplicates

def mark_duplicates_for_removal(duplicates_found):
    """
    Step 8: Mark duplicates for removal, keeping LAST occurrence of each
    Updates database records and returns list of removed items
    """
    duplicates_removed = []
    
    for group_id, group_data in duplicates_found.items():
        occurrences = group_data['occurrences']
        content_type = group_data['content_type']
        
        # Sort by file order, then by time within file to find truly LAST occurrence
        sorted_occurrences = sorted(occurrences, key=lambda x: (
            x['segment_data']['file_order'], 
            x['segment_data']['start_time']
        ))
        
        # Keep the LAST occurrence, mark others for removal  
        for i, occurrence in enumerate(sorted_occurrences):
            segment = occurrence['segment_data']['segment']
            
            # Mark segment with duplicate info
            segment.duplicate_group_id = group_id
            segment.duplicate_type = content_type
            
            if i < len(sorted_occurrences) - 1:  # Not the last occurrence
                segment.is_duplicate = True
                segment.is_kept = False
                duplicates_removed.append({
                    'group_id': group_id,
                    'type': content_type,
                    'text': segment.text,
                    'audio_file': occurrence['segment_data']['audio_file'].title,
                    'start_time': segment.start_time,
                    'end_time': segment.end_time
                })
                logger.info(f"Removing duplicate {content_type}: '{segment.text[:50]}...' at {segment.start_time:.2f}s")
            else:  # Last occurrence - keep it
                segment.is_duplicate = True  # It's still a duplicate, but we keep this one
                segment.is_kept = True
                logger.info(f"Keeping last {content_type}: '{segment.text[:50]}...' at {segment.start_time:.2f}s")
            
            segment.save()
    
    return duplicates_removed

def detect_duplicates_against_pdf_task(segments, pdf_section, full_transcript, task_id, r):
    """
    Find REPEATED/DUPLICATE segments within the audio transcription
    Returns segments that appear multiple times (keep last occurrence, mark earlier ones as duplicates)
    """
    import difflib
    import re
    from collections import defaultdict
    
    logger.info(f"Analyzing {len(segments)} segments for repeated content")
    
    # Clean text for better comparison
    def clean_text_for_comparison(text):
        # Normalize whitespace and punctuation
        text = re.sub(r'\s+', ' ', text.lower().strip())
        text = re.sub(r'[^\w\s]', ' ', text)  # Remove punctuation except spaces
        text = re.sub(r'\s+', ' ', text)  # Normalize spaces
        return text
    
    duplicates = []
    unique_segments = []
    total_segments = len(segments)
    
    # Progress tracking for duplicate detection (45-85%)
    base_progress = 45
    progress_range = 40
    
    # Create a map of cleaned text to list of segments with that text
    text_to_segments = defaultdict(list)
    
    # First pass: group segments by similar text
    logger.info("First pass: Grouping similar segments...")
    for i, segment in enumerate(segments):
        segment_text = segment['text']
        segment_clean = clean_text_for_comparison(segment_text)
        
        # Skip very short segments (likely not meaningful duplicates)
        if len(segment_clean.split()) < 3:
            unique_segments.append(segment)
            continue
        
        # Add to the map
        text_to_segments[segment_clean].append({
            'index': i,
            'segment': segment,
            'clean_text': segment_clean
        })
        
        # Update progress (first 20% of range)
        progress = base_progress + int((i + 1) / total_segments * (progress_range * 0.2))
        r.set(f"progress:{task_id}", progress)
    
    # Second pass: find fuzzy matches for groups with single items
    logger.info("Second pass: Finding fuzzy duplicates...")
    segment_groups = []
    processed_indices = set()
    
    for i, segment in enumerate(segments):
        if i in processed_indices:
            continue
            
        segment_clean = clean_text_for_comparison(segment['text'])
        
        # Skip very short segments
        if len(segment_clean.split()) < 3:
            continue
        
        # Create a group for this segment
        group = [{
            'index': i,
            'segment': segment,
            'clean_text': segment_clean
        }]
        processed_indices.add(i)
        
        # Find similar segments (fuzzy matching)
        for j, other_segment in enumerate(segments[i+1:], start=i+1):
            if j in processed_indices:
                continue
                
            other_clean = clean_text_for_comparison(other_segment['text'])
            
            # Skip very short segments
            if len(other_clean.split()) < 3:
                continue
            
            # Calculate similarity
            similarity = difflib.SequenceMatcher(None, segment_clean, other_clean).ratio()
            
            # If highly similar (>85%), add to group
            if similarity >= 0.85:
                group.append({
                    'index': j,
                    'segment': other_segment,
                    'clean_text': other_clean
                })
                processed_indices.add(j)
        
        # If group has more than one segment, it's a duplicate group
        if len(group) > 1:
            segment_groups.append(group)
        
        # Update progress (remaining 80% of range)
        progress = base_progress + int(progress_range * 0.2) + int(len(processed_indices) / total_segments * (progress_range * 0.8))
        r.set(f"progress:{task_id}", progress)
    
    # Third pass: Mark duplicates (keep LAST occurrence)
    logger.info("Third pass: Marking duplicates (keeping last occurrence)...")
    duplicate_indices = set()
    duplicate_groups_info = {}  # Store group information for backend
    
    for group_idx, group in enumerate(segment_groups):
        # Sort by index to ensure we keep the LAST occurrence
        group_sorted = sorted(group, key=lambda x: x['index'])
        
        # Store group info
        duplicate_groups_info[str(group_idx)] = {
            'group_id': group_idx,
            'occurrences_count': len(group_sorted),
            'kept_occurrence': group_sorted[-1]['index'],  # Last one is kept
            'sample_text': group_sorted[0]['segment']['text'][:100] + '...' if len(group_sorted[0]['segment']['text']) > 100 else group_sorted[0]['segment']['text']
        }
        
        # Add ALL occurrences to duplicates list (mark which to keep vs delete)
        for item in group_sorted:
            # Calculate how many times this segment appears
            occurrences = len(group_sorted)
            
            # Find which occurrence this is (1st, 2nd, etc.)
            occurrence_number = group_sorted.index(item) + 1
            is_last_occurrence = (occurrence_number == occurrences)
            
            # Flatten the structure for easier backend access
            segment = item['segment']
            duplicate_info = {
                # Flatten segment data to top level for backend compatibility
                'id': segment.get('id'),
                'audio_file_id': segment.get('audio_file_id'),
                'audio_file_title': segment.get('audio_file_title'),
                'text': segment.get('text'),
                'start_time': segment.get('start_time'),
                'end_time': segment.get('end_time'),
                'segment_index': segment.get('segment_index'),
                # Duplicate metadata
                'is_duplicate': not is_last_occurrence,  # True for segments to delete, False for kept occurrence
                'is_last_occurrence': is_last_occurrence,
                'similarity_score': 1.0,  # High confidence - actual repeat
                'duplicate_of_index': group_sorted[-1]['index'],  # Last occurrence
                'occurrence_number': occurrence_number,
                'total_occurrences': occurrences,
                'group_id': group_idx,  # Group identifier
                'confidence': 'high',
                'reason': f'Repeated content (occurrence {occurrence_number} of {occurrences}, {"KEEP - last occurrence" if is_last_occurrence else "DELETE - earlier occurrence"})'
            }
            duplicates.append(duplicate_info)
            
            # Only add to duplicate_indices if it's NOT the last occurrence
            if not is_last_occurrence:
                duplicate_indices.add(item['index'])
    
    # Add unique segments (not in duplicate list)
    for i, segment in enumerate(segments):
        if i not in duplicate_indices and len(clean_text_for_comparison(segment['text']).split()) >= 3:
            unique_segments.append(segment)
    
    # Calculate summary statistics
    total_duplicate_time = sum(
        dup['end_time'] - dup['start_time'] 
        for dup in duplicates
    )
    
    total_unique_time = sum(
        seg['end_time'] - seg['start_time'] 
        for seg in unique_segments
    )
    
    duplicate_percentage = (len(duplicates) / total_segments * 100) if total_segments > 0 else 0
    
    logger.info(f"Duplicate detection completed:")
    logger.info(f"- Total segments: {total_segments}")
    logger.info(f"- Duplicate groups found: {len(segment_groups)}")
    logger.info(f"- Duplicates found: {len(duplicates)} ({duplicate_percentage:.1f}%)")
    logger.info(f"- Unique segments: {len(unique_segments)}")
    logger.info(f"- Duplicate time: {total_duplicate_time:.1f}s")
    logger.info(f"- Unique time: {total_unique_time:.1f}s")
    
    return {
        'duplicates': duplicates,
        'unique_segments': unique_segments,
        'duplicate_groups': duplicate_groups_info,  # Dict of group info, not just count
        'summary': {
            'total_segments': total_segments,
            'duplicates_count': len(duplicates),
            'total_duplicate_segments': len(duplicates),  # For frontend compatibility
            'unique_duplicate_groups': len(segment_groups),  # For frontend compatibility
            'segments_to_delete': len(duplicates),  # For frontend compatibility
            'segments_to_keep': len(unique_segments),  # For frontend compatibility
            'unique_count': len(unique_segments),
            'duplicate_percentage': duplicate_percentage,
            'total_duplicate_time': total_duplicate_time,
            'total_unique_time': total_unique_time,
            'pdf_section_length': len(pdf_section),
            'analysis_method': 'comprehensive_similarity'
        }
    }


@shared_task(bind=True)
def detect_duplicates_single_file_task(self, audio_file_id):
    """
    Detect duplicate segments within a SINGLE audio file (not across files).
    Creates DuplicateGroup records for review.
    """
    task_id = self.request.id
    r = get_redis_connection()
    
    # Set up infrastructure
    if not docker_celery_manager.setup_infrastructure():
        raise Exception("Failed to set up Docker and Celery infrastructure")
    
    docker_celery_manager.register_task(task_id)
    
    try:
        from audioDiagnostic.models import AudioFile, Transcription, TranscriptionSegment, DuplicateGroup
        from collections import defaultdict
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
        
        # Get audio file and transcription
        audio_file = AudioFile.objects.get(id=audio_file_id)
        
        if not hasattr(audio_file, 'transcription'):
            raise ValueError("Audio file must be transcribed first")
        
        transcription = audio_file.transcription
        segments = list(transcription.segments.all().order_by('start_time'))
        
        if not segments:
            raise ValueError("No transcription segments found")
        
        audio_file.status = 'processing'
        audio_file.task_id = task_id
        audio_file.save()
        
        r.set(f"progress:{task_id}", 10)
        self.update_state(state='PROGRESS', meta={'progress': 10, 'message': 'Loading segments...'})
        logger.info(f"Detecting duplicates in audio file {audio_file_id} with {len(segments)} segments")
        
        # Clear existing duplicate groups
        DuplicateGroup.objects.filter(audio_file=audio_file).delete()
        for seg in segments:
            seg.duplicate_group_id = None
            seg.is_kept = True
            seg.is_duplicate = False
        TranscriptionSegment.objects.bulk_update(segments, ['duplicate_group_id', 'is_kept', 'is_duplicate'])
        
        r.set(f"progress:{task_id}", 20)
        self.update_state(state='PROGRESS', meta={'progress': 20, 'message': 'Analyzing text similarity...'})
        
        # Normalize texts
        segment_texts = [normalize(seg.text) for seg in segments]
        
        # Use TF-IDF and cosine similarity
        vectorizer = TfidfVectorizer(ngram_range=(1, 3), min_df=1, max_df=0.9)
        tfidf_matrix = vectorizer.fit_transform(segment_texts)
        
        r.set(f"progress:{task_id}", 40)
        self.update_state(state='PROGRESS', meta={'progress': 40, 'message': 'Finding duplicate groups...'})
        
        # Calculate similarity matrix
        similarity_matrix = cosine_similarity(tfidf_matrix)
        
        # Find duplicates (similarity >= 0.85)
        SIMILARITY_THRESHOLD = 0.85
        duplicate_groups = []
        processed_indices = set()
        
        for i in range(len(segments)):
            if i in processed_indices:
                continue
            
            # Find all segments similar to this one
            similar_indices = []
            for j in range(i, len(segments)):
                if j in processed_indices:
                    continue
                if similarity_matrix[i][j] >= SIMILARITY_THRESHOLD:
                    similar_indices.append(j)
            
            # Only create group if duplicates found (more than 1 occurrence)
            if len(similar_indices) > 1:
                # Sort indices to ensure chronological order (important for keeping LAST)
                similar_indices.sort()
                duplicate_groups.append(similar_indices)
                processed_indices.update(similar_indices)
        
        r.set(f"progress:{task_id}", 60)
        self.update_state(state='PROGRESS', meta={'progress': 60, 'message': f'Creating {len(duplicate_groups)} duplicate groups...'})
        
        # Create DuplicateGroup records and mark duplicates
        groups_created = 0
        for group_indices in duplicate_groups:
            # Ensure indices are sorted chronologically
            group_indices = sorted(group_indices)
            
            # Get representative text from first occurrence
            duplicate_text = segments[group_indices[0]].text
            
            # Calculate total duration
            total_duration = sum(
                segments[idx].end_time - segments[idx].start_time 
                for idx in group_indices
            )
            
            # Create group ID
            group_id = f"group_{audio_file_id}_{groups_created + 1}"
            
            # Create DuplicateGroup with list of all occurrences
            duplicate_group = DuplicateGroup.objects.create(
                audio_file=audio_file,
                group_id=group_id,
                duplicate_text=duplicate_text,
                occurrence_count=len(group_indices),
                total_duration_seconds=total_duration
            )
            
            # Mark segments: DELETE all except LAST occurrence
            # group_indices is sorted chronologically, so last index is the one to keep
            last_index = group_indices[-1]
            
            segments_to_save = []
            for position, idx in enumerate(group_indices):
                segment = segments[idx]
                segment.duplicate_group_id = group_id
                # Delete all EXCEPT the last occurrence (position < len-1 means DELETE)
                is_last = (position == len(group_indices) - 1)
                segment.is_duplicate = not is_last  # True if should be deleted
                segment.is_kept = is_last  # True only for last occurrence
                segments_to_save.append(segment)
                
                logger.info(f"BEFORE SAVE - Segment ID {segment.id} at position {position}/{len(group_indices)-1}: is_duplicate={segment.is_duplicate}, is_kept={segment.is_kept}")
            
            # Save segments for this group immediately
            updated_count = TranscriptionSegment.objects.bulk_update(segments_to_save, ['duplicate_group_id', 'is_duplicate', 'is_kept'])
            logger.info(f"Bulk update completed, updated {len(segments_to_save)} segments")
            
            # Verify the save worked
            for seg in segments_to_save:
                seg.refresh_from_db()
                logger.info(f"AFTER SAVE - Segment ID {seg.id}: is_duplicate={seg.is_duplicate}, is_kept={seg.is_kept}")
            
            groups_created += 1
            
            logger.info(f"Group {group_id}: {len(group_indices)} occurrences, DELETE first {len(group_indices)-1}, KEEP last at index {last_index}")
        
        r.set(f"progress:{task_id}", 90)
        self.update_state(state='PROGRESS', meta={'progress': 90, 'message': 'Finalizing...'})
        
        # Update audio file
        audio_file.status = 'transcribed'  # Return to transcribed (ready for review)
        audio_file.save()
        
        r.set(f"progress:{task_id}", 100)
        logger.info(f"Duplicate detection complete for audio file {audio_file_id}: {groups_created} groups found")
        
        return {
            'success': True,
            'audio_file_id': audio_file_id,
            'duplicate_groups_found': groups_created,
            'total_duplicates': sum(len(g) for g in duplicate_groups),
            'message': f'Found {groups_created} duplicate groups'
        }
        
    except Exception as e:
        logger.error(f"Error in detect_duplicates_single_file_task: {str(e)}")
        try:
            from audioDiagnostic.models import AudioFile
            audio_file = AudioFile.objects.get(id=audio_file_id)
            audio_file.status = 'failed'
            audio_file.error_message = str(e)
            audio_file.save()
        except:
            pass
        raise
    finally:
        docker_celery_manager.unregister_task(task_id)


@shared_task(bind=True)
def process_deletions_single_file_task(self, audio_file_id, segment_ids_to_delete):
    """
    Process confirmed deletions and generate clean audio for a single file.
    """
    task_id = self.request.id
    r = get_redis_connection()
    
    # Set up infrastructure
    if not docker_celery_manager.setup_infrastructure():
        raise Exception("Failed to set up Docker and Celery infrastructure")
    
    docker_celery_manager.register_task(task_id)
    
    try:
        from audioDiagnostic.models import AudioFile, TranscriptionSegment
        from pydub import AudioSegment as PydubAudioSegment
        import os
        from django.core.files import File
        
        # Get audio file
        audio_file = AudioFile.objects.get(id=audio_file_id)
        
        if not hasattr(audio_file, 'transcription'):
            raise ValueError("Audio file must be transcribed first")
        
        audio_file.status = 'processing'
        audio_file.task_id = task_id
        audio_file.save()
        
        r.set(f"progress:{task_id}", 10)
        self.update_state(state='PROGRESS', meta={'progress': 10, 'message': 'Updating deletions...'})
        logger.info(f"Processing {len(segment_ids_to_delete)} deletions for audio file {audio_file_id}")
        
        # CRITICAL: First, ensure ALL segments default to is_kept=True
        # This protects against any segments that may have been incorrectly marked
        total_segments = audio_file.transcription.segments.count()
        audio_file.transcription.segments.all().update(is_kept=True)
        logger.info(f"Reset all {total_segments} segments to is_kept=True")
        
        # Now mark only the specific segments for deletion
        segments_to_update = TranscriptionSegment.objects.filter(
            id__in=segment_ids_to_delete,
            transcription=audio_file.transcription
        )
        deleted_count = segments_to_update.update(is_kept=False)
        logger.info(f"Marked {deleted_count} segments for deletion (is_kept=False)")
        
        # Verify the counts
        kept_count = audio_file.transcription.segments.filter(is_kept=True).count()
        not_kept_count = audio_file.transcription.segments.filter(is_kept=False).count()
        logger.info(f"Segment counts - Total: {total_segments}, Kept: {kept_count}, Deleted: {not_kept_count}")
        
        r.set(f"progress:{task_id}", 30)
        self.update_state(state='PROGRESS', meta={'progress': 30, 'message': 'Loading audio...'})
        
        # Load original audio
        original_audio_path = audio_file.file.path
        audio = PydubAudioSegment.from_file(original_audio_path)
        
        # Ensure original duration is saved (in case it wasn't extracted during upload)
        if not audio_file.duration_seconds:
            audio_file.duration_seconds = len(audio) / 1000.0
            audio_file.save(update_fields=['duration_seconds'])
            logger.info(f"Extracted original duration: {audio_file.duration_seconds}s")
        
        r.set(f"progress:{task_id}", 50)
        self.update_state(state='PROGRESS', meta={'progress': 50, 'message': 'Generating clean audio...'})
        
        # Get all segments to keep (is_kept=True), ordered by time
        kept_segments = audio_file.transcription.segments.filter(is_kept=True).order_by('start_time')
        
        # Build clean audio by concatenating kept segments
        clean_audio = PydubAudioSegment.silent(duration=0)
        
        for segment in kept_segments:
            start_ms = int(segment.start_time * 1000)
            end_ms = int(segment.end_time * 1000)
            segment_audio = audio[start_ms:end_ms]
            clean_audio += segment_audio
        
        r.set(f"progress:{task_id}", 70)
        self.update_state(state='PROGRESS', meta={'progress': 70, 'message': 'Saving processed audio...'})
        
        # Save processed audio
        output_filename = f"{audio_file.filename.rsplit('.', 1)[0]}_clean.wav"
        output_path = os.path.join(settings.MEDIA_ROOT, 'audio', 'processed', output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        clean_audio.export(output_path, format='wav')
        
        # Update audio file with processed audio
        with open(output_path, 'rb') as f:
            audio_file.processed_audio.save(output_filename, File(f), save=False)
        
        # Calculate processed duration
        processed_duration = len(clean_audio) / 1000.0
        
        audio_file.status = 'processed'
        audio_file.processed_duration_seconds = processed_duration
        audio_file.last_processed_at = timezone.now()
        audio_file.save()
        
        r.set(f"progress:{task_id}", 100)
        logger.info(f"Processing complete for audio file {audio_file_id}")
        
        # Calculate statistics
        deleted_count = len(segment_ids_to_delete)
        total_segments = audio_file.transcription.segments.count()
        kept_count = total_segments - deleted_count
        
        return {
            'success': True,
            'audio_file_id': audio_file_id,
            'processed_audio_url': audio_file.processed_audio.url,
            'statistics': {
                'total_segments': total_segments,
                'segments_deleted': deleted_count,
                'segments_kept': kept_count,
                'original_duration': audio_file.duration_seconds,
                'processed_duration': processed_duration
            }
        }
        
    except Exception as e:
        logger.error(f"Error in process_deletions_single_file_task: {str(e)}")
        try:
            from audioDiagnostic.models import AudioFile
            audio_file = AudioFile.objects.get(id=audio_file_id)
            audio_file.status = 'failed'
            audio_file.error_message = str(e)
            audio_file.save()
        except:
            pass
        raise
    finally:
        docker_celery_manager.unregister_task(task_id)

