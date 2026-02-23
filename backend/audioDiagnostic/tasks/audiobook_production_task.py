"""
Audiobook Production Analysis Task

Celery task for comprehensive audiobook quality analysis.
Analyzes PDF text against audio transcription to determine production readiness.
"""

import logging
from celery import shared_task
from django.db import transaction
from ..models import AudioFile, AudioProject, TranscriptionSegment
from ..utils import get_redis_connection
from ..utils.text_normalizer import prepare_pdf_for_audiobook
from ..utils.repetition_detector import (
    detect_repetitions,
    build_word_map_from_text,
    find_repeated_sequences,
    mark_excluded_words,
    build_final_transcript,
)
from ..utils.alignment_engine import align_transcript_to_pdf
from ..utils.quality_scorer import analyze_segments
from ..utils.gap_detector import find_missing_sections
from ..utils.production_report import generate_production_report

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='audioDiagnostic.audiobook_production_analysis')
def audiobook_production_analysis_task(self, project_id, audio_file_id=None, 
                                      min_repeat_length=5, max_repeat_length=50,
                                      segment_size=50, min_gap_words=10,
                                      pdf_start_char=None, pdf_end_char=None,
                                      transcript_start_char=None, transcript_end_char=None):
    """
    Comprehensive audiobook production analysis.
    
    Analyzes:
    1. Repeated sections (reader re-reading lines)
    2. Word-by-word PDF-transcript alignment
    3. Quality scoring by segment
    4. Missing sections detection
    5. Production readiness assessment
    
    Args:
        project_id: Project ID
        audio_file_id: Specific audio file ID (optional, uses all if None)
        min_repeat_length: Minimum words in repeated sequence
        max_repeat_length: Maximum words in repeated sequence
        segment_size: Words per quality segment
        min_gap_words: Minimum words to count as missing section
    
    Returns:
        dict: Production report
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Starting audiobook production analysis for project {project_id}")
    
    # Connect to Redis for progress tracking
    redis_conn = get_redis_connection()
    progress_key = f"audiobook_analysis:{task_id}"
    
    def update_progress(stage, percent, message=""):
        """Update task progress in Redis."""
        redis_conn.hset(progress_key, mapping={
            'stage': stage,
            'percent': percent,
            'message': message,
            'status': 'processing'
        })
        redis_conn.expire(progress_key, 3600)  # Expire after 1 hour
        logger.info(f"[Task {task_id}] {stage}: {message} ({percent}%)")
    
    try:
        # Phase 1: Load project and PDF
        update_progress('initialization', 5, 'Loading project and PDF text')
        
        project = AudioProject.objects.get(id=project_id)
        
        if not project.pdf_text:
            raise ValueError("Project has no PDF text. Please upload and process a PDF first.")
        
        # Apply optional PDF region selection before cleaning
        pdf_source_text = project.pdf_text
        if pdf_start_char is not None and pdf_end_char is not None:
            pdf_source_text = pdf_source_text[pdf_start_char:pdf_end_char]
            logger.info(f"[Task {task_id}] Using PDF region chars {pdf_start_char}-{pdf_end_char}")
        elif pdf_start_char is not None:
            pdf_source_text = pdf_source_text[pdf_start_char:]
            logger.info(f"[Task {task_id}] Using PDF from char {pdf_start_char} to end")
        elif pdf_end_char is not None:
            pdf_source_text = pdf_source_text[:pdf_end_char]
            logger.info(f"[Task {task_id}] Using PDF from start to char {pdf_end_char}")

        # Prepare PDF text for audiobook comparison
        update_progress('pdf_preparation', 10, 'Cleaning PDF text')
        pdf_text = prepare_pdf_for_audiobook(pdf_source_text)
        
        # Phase 2: Load transcription
        update_progress('transcription_loading', 15, 'Loading transcription')
        
        # Try to get TranscriptionSegments first (preferred)
        segments = None
        transcript_text = None
        
        if audio_file_id:
            # Use specific audio file
            audio_file = AudioFile.objects.get(id=audio_file_id, project=project)
            
            # If transcript region is specified, use text mode so char slicing is accurate
            use_transcript_region = transcript_start_char is not None or transcript_end_char is not None
            if use_transcript_region:
                segments = None
                transcript_text = audio_file.transcript_text or ''
                
                if transcript_start_char is not None and transcript_end_char is not None:
                    transcript_text = transcript_text[transcript_start_char:transcript_end_char]
                    logger.info(f"[Task {task_id}] Using transcript region chars {transcript_start_char}-{transcript_end_char}")
                elif transcript_start_char is not None:
                    transcript_text = transcript_text[transcript_start_char:]
                    logger.info(f"[Task {task_id}] Using transcript from char {transcript_start_char} to end")
                elif transcript_end_char is not None:
                    transcript_text = transcript_text[:transcript_end_char]
                    logger.info(f"[Task {task_id}] Using transcript from start to char {transcript_end_char}")
            else:
                segments = TranscriptionSegment.objects.filter(
                    audio_file=audio_file
                ).order_by('start_time')
                
                # Fall back to transcript_text if no segments
                if not segments.exists():
                    segments = None
                    transcript_text = audio_file.transcript_text
        else:
            if transcript_start_char is not None or transcript_end_char is not None:
                raise ValueError("Transcript region selection requires a specific audio file.")

            # Use all audio files in project
            segments = TranscriptionSegment.objects.filter(
                audio_file__project=project
            ).order_by('audio_file__file_number', 'start_time')
            
            # Fall back to combined transcript_text from all files
            if not segments.exists():
                segments = None
                audio_files = AudioFile.objects.filter(project=project).order_by('file_number')
                transcript_texts = [af.transcript_text for af in audio_files if af.transcript_text]
                transcript_text = ' '.join(transcript_texts) if transcript_texts else None
        
        # Check we have some form of transcription
        if segments is None and not transcript_text:
            raise ValueError("No transcription found. Please transcribe the audio first.")
        
        if segments:
            segment_count = segments.count()
            logger.info(f"[Task {task_id}] Loaded {segment_count} transcription segments")
        else:
            segment_count = len(transcript_text.split()) if transcript_text else 0
            logger.info(f"[Task {task_id}] Using transcript_text with ~{segment_count} words")
        
        # Phase 3: Detect repetitions
        update_progress('repetition_detection', 25, f'Analyzing transcription for repetitions')
        
        if segments:
            # Use segment-based detection (with timestamps)
            word_map, repetitions, final_transcript = detect_repetitions(
                segments,
                min_length=min_repeat_length,
                max_length=max_repeat_length
            )
        else:
            # Use text-based detection (no timestamps)
            # Build word map from plain text
            word_map = build_word_map_from_text(transcript_text)
            # For text-only, we can still try to detect repetitions
            # (but without timestamps for verification)
            repetitions = find_repeated_sequences(word_map, min_repeat_length, max_repeat_length)
            mark_excluded_words(word_map, repetitions)
            final_transcript = build_final_transcript(word_map)
            logger.info(f"[Task {task_id}] Text-only mode: {len(final_transcript)} words, {len(repetitions)} repetitions")
        
        if repetitions:
            logger.info(f"[Task {task_id}] Found {len(repetitions)} repeated sections")
            logger.info(f"[Task {task_id}] Final transcript: {len(final_transcript)} words "
                       f"(removed {len(word_map) - len(final_transcript)} repeated words)")
        
        update_progress('repetition_detection', 40, 
                       f'Found {len(repetitions)} repeated sections' if repetitions else 'Processing complete')
        
        # Phase 4: Align transcript with PDF
        update_progress('alignment', 50, 'Aligning transcript with PDF text')
        
        alignment = align_transcript_to_pdf(pdf_text, final_transcript)
        
        logger.info(f"[Task {task_id}] Created alignment with {len(alignment)} points")
        
        update_progress('alignment', 60, 'Alignment complete')
        
        # Phase 5: Quality analysis
        update_progress('quality_analysis', 70, 'Analyzing quality by segment')
        
        segments_analysis = analyze_segments(alignment, segment_size=segment_size)
        
        logger.info(f"[Task {task_id}] Created {len(segments_analysis)} quality segments")
        
        update_progress('quality_analysis', 80, 
                       f'Analyzed {len(segments_analysis)} segments')
        
        # Phase 6: Gap detection
        update_progress('gap_detection', 85, 'Detecting missing sections')
        
        missing_sections = find_missing_sections(alignment, min_gap_words=min_gap_words)
        
        logger.info(f"[Task {task_id}] Found {len(missing_sections)} missing sections")
        
        update_progress('gap_detection', 90, 
                       f'Found {len(missing_sections)} missing sections')
        
        # Phase 7: Generate report
        update_progress('report_generation', 95, 'Generating production report')
        
        report = generate_production_report(
            project_id=project_id,
            audio_file_id=audio_file_id or 0,
            pdf_text=pdf_text,
            word_map=word_map,
            repetitions=repetitions,
            final_transcript=final_transcript,
            alignment=alignment,
            segments=segments_analysis,
            missing_sections=missing_sections
        )
        
        # Convert to dictionary for JSON serialization
        report_dict = report.to_dict()
        
        # Store report summary in Redis for quick access
        summary_key = f"audiobook_report:{project_id}"
        redis_conn.hset(summary_key, mapping={
            'overall_status': report.overall_status,
            'overall_score': report.overall_score,
            'created_at': report.created_at.isoformat(),
            'checklist_items': len(report.editing_checklist),
            'critical_items': sum(1 for c in report.editing_checklist if c.priority == 'CRITICAL')
        })
        redis_conn.expire(summary_key, 86400)  # Expire after 24 hours
        
        # Complete
        update_progress('complete', 100, 
                       f'Analysis complete - Status: {report.overall_status}')
        
        redis_conn.hset(progress_key, 'status', 'completed')
        redis_conn.hset(progress_key, 'result', 'success')
        
        logger.info(f"[Task {task_id}] Audiobook production analysis complete")
        logger.info(f"[Task {task_id}] Overall status: {report.overall_status}")
        logger.info(f"[Task {task_id}] Overall score: {report.overall_score:.1%}")
        logger.info(f"[Task {task_id}] Checklist items: {len(report.editing_checklist)}")
        
        return report_dict
        
    except Exception as e:
        logger.error(f"[Task {task_id}] Error in audiobook production analysis: {str(e)}", 
                    exc_info=True)
        
        # Update Redis with error
        redis_conn.hset(progress_key, mapping={
            'status': 'failed',
            'error': str(e),
            'percent': 0
        })
        
        raise


@shared_task(name='audioDiagnostic.get_audiobook_analysis_progress')
def get_audiobook_analysis_progress(task_id):
    """
    Get progress of audiobook analysis task.
    
    Args:
        task_id: Celery task ID
    
    Returns:
        dict: Progress information
    """
    redis_conn = get_redis_connection()
    progress_key = f"audiobook_analysis:{task_id}"
    
    progress = redis_conn.hgetall(progress_key)
    
    if not progress:
        return {
            'status': 'not_found',
            'message': 'Task not found or expired'
        }
    
    return {
        'status': progress.get('status', 'unknown'),
        'stage': progress.get('stage', ''),
        'percent': int(progress.get('percent', 0)),
        'message': progress.get('message', ''),
        'error': progress.get('error', '')
    }


@shared_task(name='audioDiagnostic.get_audiobook_report_summary')
def get_audiobook_report_summary(project_id):
    """
    Get quick summary of the most recent audiobook analysis report.
    
    Args:
        project_id: Project ID
    
    Returns:
        dict: Report summary or None
    """
    redis_conn = get_redis_connection()
    summary_key = f"audiobook_report:{project_id}"
    
    summary = redis_conn.hgetall(summary_key)
    
    if not summary:
        return None
    
    return {
        'overall_status': summary.get('overall_status'),
        'overall_score': float(summary.get('overall_score', 0)),
        'created_at': summary.get('created_at'),
        'checklist_items': int(summary.get('checklist_items', 0)),
        'critical_items': int(summary.get('critical_items', 0))
    }
