"""
AI-Powered Duplicate Detection Tasks

Celery tasks for AI-powered duplicate detection, paragraph expansion,
and PDF comparison using Anthropic Claude or OpenAI.
"""
from ._base import *
from audioDiagnostic.services.ai import DuplicateDetector, CostCalculator
from audioDiagnostic.models import (
    AudioFile,
    AudioProject,
    AIDuplicateDetectionResult,
    AIPDFComparisonResult,
    AIProcessingLog,
    DuplicateGroup,
)
from django.contrib.auth.models import User
from django.utils import timezone
import json
import time


@shared_task(bind=True)
def ai_detect_duplicates_task(
    self, 
    audio_file_id, 
    user_id,
    min_words=3,
    similarity_threshold=0.85,
    keep_occurrence='last',
    enable_paragraph_expansion=False
):
    """
    AI-powered duplicate detection task
    
    Args:
        audio_file_id: ID of AudioFile to process
        user_id: ID of User initiating the request
        min_words: Minimum words to qualify as duplicate
        similarity_threshold: 0-1, semantic similarity threshold
        keep_occurrence: 'first', 'last', or 'best'
        enable_paragraph_expansion: If True, run paragraph expansion after detection
    
    Returns:
        Dict with result_id and summary
    """
    task_id = self.request.id
    r = get_redis_connection()
    
    try:
        # Get audio file and user
        audio_file = AudioFile.objects.get(id=audio_file_id)
        user = User.objects.get(id=user_id)
        
        logger.info(
            f"Starting AI duplicate detection for audio_file_id={audio_file_id}, "
            f"user_id={user_id}, task_id={task_id}"
        )
        
        # Update progress
        r.set(f"progress:{task_id}", 5)
        r.set(f"status:{task_id}", json.dumps({
            'status': 'processing',
            'message': 'Preparing transcript data...'
        }))
        
        # Check if audio file has transcription
        if not hasattr(audio_file, 'transcription'):
            raise ValueError(
                f"Audio file {audio_file_id} has not been transcribed. "
                "Please transcribe the audio file first."
            )
        
        transcription = audio_file.transcription
        segments = transcription.segments.all().order_by('segment_index')
        
        if not segments.exists():
            raise ValueError(
                f"No transcription segments found for audio file {audio_file_id}. "
                "Please ensure transcription includes segments."
            )
        
        # Prepare transcript data in JSON format
        r.set(f"progress:{task_id}", 10)
        r.set(f"status:{task_id}", json.dumps({
            'status': 'processing',
            'message': 'Formatting transcript for AI...'
        }))
        
        transcript_data = {
            'metadata': {
                'audio_file_id': audio_file_id,
                'filename': audio_file.filename,
                'duration_seconds': audio_file.duration_seconds or 0,
                'total_segments': segments.count(),
                'transcription_method': 'whisper',
            },
            'segments': [],
            'detection_settings': {
                'min_words_to_match': min_words,
                'similarity_threshold': similarity_threshold,
                'keep_occurrence': keep_occurrence,
            }
        }
        
        # Add segments with word-level timing
        for segment in segments:
            words_data = []
            for word in segment.words.all().order_by('word_index'):
                words_data.append({
                    'word': word.word,
                    'start': word.start_time,
                    'end': word.end_time,
                    'confidence': word.confidence or 0.9
                })
            
            transcript_data['segments'].append({
                'segment_id': segment.segment_index,
                'text': segment.text,
                'start_time': segment.start_time,
                'end_time': segment.end_time,
                'confidence': segment.confidence_score or 0.9,
                'words': words_data
            })
        
        logger.info(f"Prepared {len(transcript_data['segments'])} segments for AI processing")
        
        # Initialize AI detector
        r.set(f"progress:{task_id}", 20)
        r.set(f"status:{task_id}", json.dumps({
            'status': 'processing',
            'message': 'Calling AI service...'
        }))
        
        detector = DuplicateDetector()
        
        # Check user cost limit
        if not detector.client.check_user_cost_limit(user_id):
            raise ValueError(
                f"User {user_id} has exceeded monthly AI cost limit. "
                "Please contact support or wait until next month."
            )
        
        # Call AI for duplicate detection
        start_time = time.time()
        
        try:
            result = detector.detect_sentence_level_duplicates(
                transcript_data=transcript_data,
                min_words=min_words,
                similarity_threshold=similarity_threshold,
                keep_occurrence=keep_occurrence
            )
        except Exception as e:
            logger.error(f"AI API call failed: {e}")
            
            # Log the failure
            AIProcessingLog.objects.create(
                user=user,
                audio_file=audio_file,
                ai_provider=detector.client.model.split('-')[0] if '-' in detector.client.model else 'anthropic',
                ai_model=detector.client.model,
                task_type='duplicate_detection',
                timestamp=timezone.now(),
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                processing_time_seconds=time.time() - start_time,
                cost_usd=0,
                status='failure',
                error_message=str(e),
                user_consented=True,
                data_sanitized=True
            )
            raise
        
        processing_time = time.time() - start_time
        
        r.set(f"progress:{task_id}", 60)
        r.set(f"status:{task_id}", json.dumps({
            'status': 'processing',
            'message': 'AI analysis complete, saving results...'
        }))
        
        # Extract AI metadata
        ai_metadata = result.get('ai_metadata', {})
        usage = ai_metadata.get('usage', {})
        
        # Calculate statistics
        summary = result.get('summary', {})
        duplicate_groups = result.get('duplicate_groups', [])
        
        duplicate_count = summary.get('total_duplicate_groups', len(duplicate_groups))
        occurrences_to_delete = summary.get('occurrences_to_delete', 0)
        estimated_time_saved = summary.get('estimated_time_saved_seconds', 0)
        
        # Calculate average confidence
        confidences = [group.get('confidence', 0) for group in duplicate_groups]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        high_confidence_count = sum(1 for c in confidences if c > 0.9)
        
        # Track user cost
        cost = ai_metadata.get('cost', 0)
        detector.client.track_user_cost(user_id, cost)
        
        # Store result in database
        detection_result = AIDuplicateDetectionResult.objects.create(
            audio_file=audio_file,
            user=user,
            ai_provider='anthropic',
            ai_model=ai_metadata.get('model', detector.client.model),
            processing_time_seconds=processing_time,
            input_tokens=usage.get('input_tokens', 0),
            output_tokens=usage.get('output_tokens', 0),
            total_tokens=usage.get('total_tokens', 0),
            api_cost_usd=cost,
            duplicate_groups=duplicate_groups,
            duplicate_count=duplicate_count,
            occurrences_to_delete=occurrences_to_delete,
            estimated_time_saved_seconds=estimated_time_saved,
            average_confidence=avg_confidence,
            high_confidence_count=high_confidence_count,
            detection_settings={
                'min_words': min_words,
                'similarity_threshold': similarity_threshold,
                'keep_occurrence': keep_occurrence
            },
            paragraph_expansion_performed=False,
            user_confirmed=False,
            user_modified=False
        )
        
        # Log the successful API call
        AIProcessingLog.objects.create(
            user=user,
            audio_file=audio_file,
            project=audio_file.project,
            ai_provider='anthropic',
            ai_model=ai_metadata.get('model', detector.client.model),
            task_type='duplicate_detection',
            timestamp=timezone.now(),
            input_tokens=usage.get('input_tokens', 0),
            output_tokens=usage.get('output_tokens', 0),
            total_tokens=usage.get('total_tokens', 0),
            processing_time_seconds=processing_time,
            cost_usd=cost,
            status='success',
            user_consented=True,
            data_sanitized=True
        )
        
        logger.info(
            f"AI duplicate detection complete. "
            f"Found {duplicate_count} groups, "
            f"cost: ${cost:.4f}, "
            f"result_id: {detection_result.id}"
        )

        # --- Write standard DuplicateGroup rows and TranscriptionSegment flags ---
        # This makes the AI path identical to the non-AI path so the same review /
        # deletion / assembly flow works unchanged (Gaps 1, 2, 4, 5).
        r.set(f"progress:{task_id}", 65)
        r.set(f"status:{task_id}", json.dumps({
            'status': 'processing',
            'message': 'Writing duplicate groups to database...'
        }))
        try:
            from .duplicate_tasks import refine_duplicate_timestamps_task

            # Clear any previously detected groups for this file
            DuplicateGroup.objects.filter(audio_file=audio_file).delete()

            segments_to_update = []
            for group_index, ai_group in enumerate(duplicate_groups):
                occurrences = ai_group.get('occurrences', [])
                if not occurrences:
                    continue

                # Gather all segment PKs, honouring the AI 'action' field
                all_segment_pks = []
                keep_segment_pks = set()
                for occ in occurrences:
                    pk_list = occ.get('segment_ids') or []
                    if not pk_list and occ.get('segment_id'):
                        pk_list = [occ['segment_id']]
                    action = occ.get('action', '')
                    for pk in pk_list:
                        all_segment_pks.append(int(pk))
                        if action == 'keep':
                            keep_segment_pks.add(int(pk))

                if not all_segment_pks:
                    continue

                # Fetch real segment objects — use DB timestamps, not LLM timestamps
                db_segments = list(
                    TranscriptionSegment.objects.filter(
                        id__in=all_segment_pks,
                        transcription=audio_file.transcription
                    ).order_by('start_time')
                )

                if not db_segments:
                    continue

                # If AI gave no explicit 'keep', keep the last occurrence (non-AI default)
                if not keep_segment_pks:
                    keep_segment_pks = {db_segments[-1].id}

                total_duration = sum(
                    max(0.0, (s.end_time or 0.0) - (s.start_time or 0.0))
                    for s in db_segments
                    if s.id not in keep_segment_pks
                )

                group_db_id = f"group_{audio_file_id}_{group_index + 1}"
                DuplicateGroup.objects.create(
                    audio_file=audio_file,
                    group_id=group_db_id,
                    duplicate_text=(
                        ai_group.get('duplicate_text') or db_segments[0].text
                    )[:500],
                    occurrence_count=len(db_segments),
                    total_duration_seconds=total_duration,
                )

                for seg in db_segments:
                    seg.duplicate_group_id = group_db_id
                    seg.is_kept = seg.id in keep_segment_pks
                    seg.is_duplicate = seg.id not in keep_segment_pks
                    segments_to_update.append(seg)

            if segments_to_update:
                TranscriptionSegment.objects.bulk_update(
                    segments_to_update,
                    ['duplicate_group_id', 'is_duplicate', 'is_kept']
                )

            groups_written = DuplicateGroup.objects.filter(audio_file=audio_file).count()
            logger.info(
                f"Wrote {groups_written} DuplicateGroup rows and updated "
                f"{len(segments_to_update)} TranscriptionSegment flags "
                f"for audio_file_id={audio_file_id}"
            )

            # Chain timestamp refinement — snaps boundaries to silence (same as non-AI path)
            if groups_written > 0:
                refine_duplicate_timestamps_task.apply_async(args=[audio_file_id])
                logger.info(
                    f"Chained refine_duplicate_timestamps_task for audio_file_id={audio_file_id}"
                )

        except Exception as db_write_err:
            # Non-fatal: the AIDuplicateDetectionResult is already saved.
            # Log the failure but let the task succeed so the user gets results.
            logger.error(
                f"Failed to write DuplicateGroup rows for audio_file_id={audio_file_id}: "
                f"{db_write_err}",
                exc_info=True
            )

        # Optionally run paragraph expansion
        if enable_paragraph_expansion and duplicate_count > 0:
            r.set(f"progress:{task_id}", 70)
            r.set(f"status:{task_id}", json.dumps({
                'status': 'processing',
                'message': 'Expanding to paragraph level...'
            }))
            
            try:
                expansion_result = detector.expand_to_paragraph_level(
                    duplicate_groups=duplicate_groups,
                    transcript_segments=transcript_data['segments'],
                    context_window=5
                )
                
                # Update result with expansion
                expansion_metadata = expansion_result.get('ai_metadata', {})
                expansion_usage = expansion_metadata.get('usage', {})
                expansion_cost = expansion_metadata.get('cost', 0)
                
                detection_result.paragraph_expansion_performed = True
                detection_result.expanded_groups = expansion_result.get('expanded_groups', [])
                detection_result.api_cost_usd += expansion_cost
                detection_result.total_tokens += expansion_usage.get('total_tokens', 0)
                detection_result.save()
                
                # Track additional cost
                detector.client.track_user_cost(user_id, expansion_cost)
                
                # Log expansion
                AIProcessingLog.objects.create(
                    user=user,
                    audio_file=audio_file,
                    project=audio_file.project,
                    ai_provider='anthropic',
                    ai_model=expansion_metadata.get('model', detector.client.model),
                    task_type='paragraph_expansion',
                    timestamp=timezone.now(),
                    input_tokens=expansion_usage.get('input_tokens', 0),
                    output_tokens=expansion_usage.get('output_tokens', 0),
                    total_tokens=expansion_usage.get('total_tokens', 0),
                    processing_time_seconds=expansion_result.get('processing_time_seconds', 0),
                    cost_usd=expansion_cost,
                    status='success',
                    user_consented=True,
                    data_sanitized=True
                )
                
                logger.info(f"Paragraph expansion complete. Additional cost: ${expansion_cost:.4f}")
                
            except Exception as e:
                logger.error(f"Paragraph expansion failed: {e}")
                # Continue anyway - we have the base detection
        
        # Update progress to complete
        r.set(f"progress:{task_id}", 100)
        r.set(f"status:{task_id}", json.dumps({
            'status': 'completed',
            'message': f'Found {duplicate_count} duplicate groups',
            'result_id': detection_result.id
        }))
        
        return {
            'success': True,
            'result_id': detection_result.id,
            'duplicate_count': duplicate_count,
            'occurrences_to_delete': occurrences_to_delete,
            'estimated_time_saved_seconds': estimated_time_saved,
            'average_confidence': avg_confidence,
            'cost_usd': float(detection_result.api_cost_usd),
            'processing_time_seconds': processing_time
        }
        
    except Exception as e:
        logger.error(f"AI duplicate detection task failed: {e}", exc_info=True)
        
        r.set(f"status:{task_id}", json.dumps({
            'status': 'failed',
            'message': str(e)
        }))
        
        raise


@shared_task(bind=True)
def ai_compare_pdf_task(self, audio_file_id, user_id, pdf_file_path=None):
    """
    AI-powered PDF comparison task
    
    Args:
        audio_file_id: ID of AudioFile to compare
        user_id: ID of User initiating the request
        pdf_file_path: Optional path to PDF file (defaults to project PDF)
    
    Returns:
        Dict with result_id and summary
    """
    task_id = self.request.id
    r = get_redis_connection()
    
    try:
        # Get audio file and user
        audio_file = AudioFile.objects.get(id=audio_file_id)
        user = User.objects.get(id=user_id)
        project = audio_file.project
        
        logger.info(
            f"Starting AI PDF comparison for audio_file_id={audio_file_id}, "
            f"user_id={user_id}, task_id={task_id}"
        )
        
        # Update progress
        r.set(f"progress:{task_id}", 5)
        r.set(f"status:{task_id}", json.dumps({
            'status': 'processing',
            'message': 'Loading PDF and transcript...'
        }))
        
        # Get clean transcript (after duplicate removal if available)
        if not hasattr(audio_file, 'transcription'):
            raise ValueError("Audio file has not been transcribed")
        
        transcription = audio_file.transcription
        
        # Check for processed transcript first, fall back to original
        if audio_file.transcript_adjusted:
            clean_transcript = audio_file.transcript_adjusted
        elif transcription.full_text:
            clean_transcript = transcription.full_text
        else:
            raise ValueError("No transcript available for comparison")
        
        # Get PDF text
        if not project.pdf_text:
            raise ValueError("Project does not have PDF text extracted")
        
        pdf_text = project.pdf_text
        pdf_metadata = {
            'project_id': project.id,
            'project_title': project.title,
            'pdf_file': project.pdf_file.name if project.pdf_file else None,
            'total_chapters': project.total_chapters or 1
        }
        
        r.set(f"progress:{task_id}", 20)
        r.set(f"status:{task_id}", json.dumps({
            'status': 'processing',
            'message': 'Calling AI service...'
        }))
        
        # Initialize AI detector
        detector = DuplicateDetector()
        
        # Check user cost limit
        if not detector.client.check_user_cost_limit(user_id):
            raise ValueError("User has exceeded monthly AI cost limit")
        
        # Call AI for PDF comparison
        start_time = time.time()
        
        try:
            result = detector.compare_with_pdf(
                clean_transcript=clean_transcript,
                pdf_text=pdf_text,
                pdf_metadata=pdf_metadata
            )
        except Exception as e:
            logger.error(f"AI PDF comparison failed: {e}")
            
            # Log the failure
            AIProcessingLog.objects.create(
                user=user,
                audio_file=audio_file,
                project=project,
                ai_provider='anthropic',
                ai_model=detector.client.model,
                task_type='pdf_comparison',
                timestamp=timezone.now(),
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                processing_time_seconds=time.time() - start_time,
                cost_usd=0,
                status='failure',
                error_message=str(e),
                user_consented=True,
                data_sanitized=True
            )
            raise
        
        processing_time = time.time() - start_time
        
        r.set(f"progress:{task_id}", 70)
        r.set(f"status:{task_id}", json.dumps({
            'status': 'processing',
            'message': 'Saving comparison results...'
        }))
        
        # Extract results
        ai_metadata = result.get('ai_metadata', {})
        usage = ai_metadata.get('usage', {})
        cost = ai_metadata.get('cost', 0)
        
        summary = result.get('summary', {})
        alignment = result.get('alignment_result', {})
        discrepancies = result.get('discrepancies', [])
        
        # Count discrepancies by type and severity
        missing_count = sum(1 for d in discrepancies if d.get('type') == 'missing_in_audio')
        extra_count = sum(1 for d in discrepancies if d.get('type') == 'extra_in_audio')
        paraphrased_count = sum(1 for d in discrepancies if d.get('type') == 'paraphrased')
        
        high_severity = sum(1 for d in discrepancies if d.get('severity') == 'high')
        medium_severity = sum(1 for d in discrepancies if d.get('severity') == 'medium')
        low_severity = sum(1 for d in discrepancies if d.get('severity') == 'low')
        
        # Store result
        comparison_result = AIPDFComparisonResult.objects.create(
            audio_file=audio_file,
            user=user,
            project=project,
            ai_provider='anthropic',
            ai_model=ai_metadata.get('model', detector.client.model),
            processing_time_seconds=processing_time,
            input_tokens=usage.get('input_tokens', 0),
            output_tokens=usage.get('output_tokens', 0),
            total_tokens=usage.get('total_tokens', 0),
            api_cost_usd=cost,
            alignment_result=alignment,
            discrepancies=discrepancies,
            coverage_percentage=summary.get('coverage_percentage', 0),
            total_discrepancies=summary.get('total_discrepancies', len(discrepancies)),
            missing_in_audio_count=missing_count,
            extra_in_audio_count=extra_count,
            paraphrased_count=paraphrased_count,
            high_severity_count=high_severity,
            medium_severity_count=medium_severity,
            low_severity_count=low_severity,
            overall_quality=summary.get('overall_quality', 'good'),
            confidence_score=summary.get('confidence', 0.9),
            clean_transcript_marked=result.get('clean_transcript_with_markers', clean_transcript)
        )
        
        # Track cost
        detector.client.track_user_cost(user_id, cost)
        
        # Log the successful API call
        AIProcessingLog.objects.create(
            user=user,
            audio_file=audio_file,
            project=project,
            ai_provider='anthropic',
            ai_model=ai_metadata.get('model', detector.client.model),
            task_type='pdf_comparison',
            timestamp=timezone.now(),
            input_tokens=usage.get('input_tokens', 0),
            output_tokens=usage.get('output_tokens', 0),
            total_tokens=usage.get('total_tokens', 0),
            processing_time_seconds=processing_time,
            cost_usd=cost,
            status='success',
            user_consented=True,
            data_sanitized=True
        )
        
        logger.info(
            f"AI PDF comparison complete. "
            f"Coverage: {summary.get('coverage_percentage', 0):.1f}%, "
            f"Discrepancies: {len(discrepancies)}, "
            f"Cost: ${cost:.4f}"
        )
        
        r.set(f"progress:{task_id}", 100)
        r.set(f"status:{task_id}", json.dumps({
            'status': 'completed',
            'message': f"Comparison complete: {summary.get('coverage_percentage', 0):.1f}% coverage",
            'result_id': comparison_result.id
        }))
        
        return {
            'success': True,
            'result_id': comparison_result.id,
            'coverage_percentage': summary.get('coverage_percentage', 0),
            'total_discrepancies': len(discrepancies),
            'overall_quality': summary.get('overall_quality', 'good'),
            'cost_usd': float(cost),
            'processing_time_seconds': processing_time
        }
        
    except Exception as e:
        logger.error(f"AI PDF comparison task failed: {e}", exc_info=True)
        
        r.set(f"status:{task_id}", json.dumps({
            'status': 'failed',
            'message': str(e)
        }))
        
        raise


@shared_task
def estimate_ai_cost_task(audio_duration_seconds, task_type='duplicate_detection'):
    """
    Simple task to estimate AI processing cost
    
    Args:
        audio_duration_seconds: Length of audio in seconds
        task_type: 'duplicate_detection' or 'pdf_comparison'
    
    Returns:
        Dict with cost estimate
    """
    calculator = CostCalculator()
    estimate = calculator.estimate_cost_for_audio(
        provider='anthropic',
        model='claude-3-5-sonnet-20241022',
        audio_duration_seconds=audio_duration_seconds,
        task_type=task_type
    )
    return estimate
