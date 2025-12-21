"""
Audio Processing Tasks for audioDiagnostic app.
"""
from ._base import *
from .pdf_tasks import find_pdf_section_match, identify_pdf_based_duplicates
from audioDiagnostic.tasks.utils import save_transcription_to_db, get_audio_duration, normalize

@shared_task(bind=True)
def process_audio_file_task(self, audio_file_id):
    """
    Processing task that works with already-transcribed audio:
    1. Check that audio is already transcribed
    2. Extract and align with PDF text 
    3. Identify duplicates by comparing to PDF
    4. Mark segments for removal (keep last occurrence)
    5. Generate processed audio file
    Auto-manages Docker and Celery infrastructure
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
        # Get audio file and project
        from audioDiagnostic.models import AudioFile
        audio_file = AudioFile.objects.get(id=audio_file_id)
        project = audio_file.project
        
        # Check if audio has transcription (more flexible status check)
        if audio_file.status not in ['transcribed', 'processed', 'processing']:
            raise ValueError(f"Audio file must be transcribed first. Current status: {audio_file.status}")
        
        # Check for existing transcription segments as the real validation
        segments = TranscriptionSegment.objects.filter(audio_file=audio_file).order_by('start_time')
        if not segments.exists():
            raise ValueError("No transcription segments found. Please transcribe the audio first.")
        
        audio_file.task_id = task_id
        audio_file.status = 'processing'
        audio_file.save()
        
        r.set(f"progress:{task_id}", 10)
        
        logger.info(f"Starting duplicate detection for audio file {audio_file_id} with {segments.count()} segments")
        
        r.set(f"progress:{task_id}", 20)
        
        # Step 2: Extract PDF text
        logger.info(f"Extracting PDF text for audio file {audio_file_id}")
        from PyPDF2 import PdfReader
        
        if not project.pdf_file:
            raise ValueError("No PDF file provided")
            
        reader = PdfReader(project.pdf_file.path)
        pdf_text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
        
        r.set(f"progress:{task_id}", 40)
        
        # Step 3: Get existing transcript text
        transcript = audio_file.transcript_text or ""
        if not transcript:
            raise ValueError("No transcript found. Audio must be transcribed first.")
        
        # Find the section of PDF that matches the transcript
        pdf_section = find_pdf_section_match(pdf_text, transcript)
        audio_file.pdf_section_matched = pdf_section
        audio_file.save()
        
        r.set(f"progress:{task_id}", 50)
        
        # Step 4: Get existing segments and identify duplicates
        segments_data = []
        for segment in segments:
            segments_data.append({
                'text': segment.text,
                'start': segment.start_time,
                'end': segment.end_time
            })
        duplicates_info = identify_pdf_based_duplicates(segments_data, pdf_section, transcript)
        
        r.set(f"progress:{task_id}", 70)
        
        # Step 5: Update existing segments with duplicate information
        for i, segment in enumerate(segments):
            if i < len(duplicates_info.get('duplicates_to_remove', [])):
                segment.is_duplicate = True
                segment.duplicate_reason = "PDF-based duplicate detection"
                segment.save()
        
        r.set(f"progress:{task_id}", 80)
        
        # Step 6: Generate processed audio (remove duplicates, keep last occurrence)
        audio_path = audio_file.file.path
        processed_audio_path = generate_processed_audio(audio_file, audio_path, duplicates_info)
        
        # Save processed audio file reference
        if processed_audio_path:
            import os
            from django.core.files import File
            with open(processed_audio_path, 'rb') as f:
                file_name = f"processed_{audio_file.id}_{os.path.basename(processed_audio_path)}"
                audio_file.processed_audio.save(file_name, File(f))
        
        # Store processing metadata
        audio_file.duplicates_removed_count = len(duplicates_info.get('duplicates_to_remove', []))
        
        r.set(f"progress:{task_id}", 100)
        
        audio_file.status = 'completed'
        audio_file.save()
        
        # Unregister task (will trigger shutdown timer if no other tasks)
        docker_celery_manager.unregister_task(task_id)
        
        return {
            "status": "completed",
            "audio_file_id": audio_file_id,
            "project_id": project.id,
            "pdf_section": pdf_section[:500] + "..." if len(pdf_section) > 500 else pdf_section,
            "duplicates_removed": len(duplicates_info.get('duplicates_to_remove', [])),
            "segments_kept": len(duplicates_info.get('segments_to_keep', [])),
            "processed_audio_url": audio_file.processed_audio.url if audio_file.processed_audio else None
        }
        
    except Exception as e:
        logger.error(f"Error processing audio file {audio_file_id}: {str(e)}")
        audio_file.status = 'failed'
        audio_file.error_message = str(e)
        audio_file.save()
        
        # Unregister task even on failure
        docker_celery_manager.unregister_task(task_id)
        
        r.set(f"progress:{task_id}", -1)  # Error indicator
        raise

def generate_processed_audio(audio_file, audio_path, duplicates_info):
    """
    Generate processed audio file with duplicates removed.
    Keep only the segments that are marked to keep (last occurrences).
    """
    try:
        # Load original audio
        audio = AudioSegment.from_file(audio_path)
        
        # Store original duration
        audio_file.original_duration = len(audio) / 1000.0  # Convert to seconds
        
        # Get segments to keep, sorted by start time
        segments_to_keep = sorted(duplicates_info['segments_to_keep'], key=lambda x: x['start'])
        
        # Build new audio from kept segments
        processed_audio = AudioSegment.empty()
        
        for segment_info in segments_to_keep:
            start_ms = int(segment_info['start'] * 1000)
            end_ms = int(segment_info['end'] * 1000)
            
            # Extract segment and add to processed audio
            segment_audio = audio[start_ms:end_ms]
            processed_audio += segment_audio
            
            # Add small gap between segments for natural flow
            processed_audio += AudioSegment.silent(duration=100)  # 100ms gap
        
        # Store processed duration
        audio_file.processing_duration = len(processed_audio) / 1000.0  # Convert to seconds
        
        # Save processed audio
        output_path = os.path.join(
            settings.MEDIA_ROOT, 
            'processed', 
            f'processed_{audio_file.id}_{os.path.basename(audio_path)}'
        )
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Export processed audio
        processed_audio.export(output_path, format="wav")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error generating processed audio: {str(e)}")
        return None


def generate_clean_audio(project, segments_to_delete):
    """
    Generate final audio file with specified segments removed
    """
    from pydub import AudioSegment
    import os
    from audioDiagnostic.models import TranscriptionSegment
    
    final_audio = AudioSegment.empty()
    
    # Process each audio file in order
    audio_files = project.audio_files.filter(status='transcribed').order_by('order_index')
    
    for audio_file in audio_files:
        logger.info(f"Processing audio file: {audio_file.filename}")
        
        # Load audio file
        audio = AudioSegment.from_file(audio_file.file.path)
        
        # Get segments for this audio file that should be kept
        segments = TranscriptionSegment.objects.filter(
            audio_file=audio_file
        ).order_by('segment_index')
        
        # Build list of time ranges to keep
        keep_ranges = []
        for segment in segments:
            if segment.id not in segments_to_delete:
                # Keep this segment
                start_ms = int(segment.start_time * 1000)
                end_ms = int(segment.end_time * 1000)
                keep_ranges.append((start_ms, end_ms))
        
        # Extract and combine kept segments
        for start_ms, end_ms in keep_ranges:
            segment_audio = audio[start_ms:end_ms]
            
            # Add small fade to avoid clicks
            if len(segment_audio) > 100:  # Only if segment is long enough
                segment_audio = segment_audio.fade_in(50).fade_out(50)
            
            final_audio += segment_audio
    
    # Export final audio
    output_dir = os.path.join(settings.MEDIA_ROOT, 'assembled')
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = int(datetime.datetime.now().timestamp() * 1000)
    filename = f"{timestamp}-{project.title.replace(' ', '_')}_clean.wav"
    output_path = os.path.join(output_dir, filename)
    
    final_audio.export(output_path, format="wav")
    logger.info(f"Generated clean audio: {output_path}")
    
    return output_path


def transcribe_clean_audio_for_verification(project, clean_audio_path):
    """
    Transcribe the clean/processed audio file for verification purposes
    Saves segments with is_verification=True flag to distinguish from original transcription
    """
    logger.info(f"Transcribing clean audio for verification: {clean_audio_path}")
    
    # Load Whisper model
    model = whisper.load_model("base")
    
    # Transcribe with word timestamps
    result = model.transcribe(clean_audio_path, word_timestamps=True)
    
    # Clear any existing verification segments for this project
    TranscriptionSegment.objects.filter(
        audio_file__project=project,
        is_verification=True
    ).delete()
    
    # Get the first audio file to associate verification segments with
    # (or we could create a special verification AudioFile object)
    first_audio_file = project.audio_files.first()
    
    # Save verification segments
    for segment_index, segment in enumerate(result['segments']):
        seg_obj = TranscriptionSegment.objects.create(
            audio_file=first_audio_file,  # Associate with first file
            text=segment['text'].strip(),
            start_time=segment['start'],
            end_time=segment['end'],
            confidence_score=segment.get('avg_logprob', 0.0),
            is_duplicate=False,
            segment_index=segment_index,
            is_verification=True  # Mark as verification transcript
        )
        
        # Save words if available
        if 'words' in segment:
            for word_index, word_data in enumerate(segment['words']):
                TranscriptionWord.objects.create(
                    audio_file=first_audio_file,
                    segment=seg_obj,
                    word=word_data['word'].strip(),
                    start_time=word_data['start'],
                    end_time=word_data['end'],
                    confidence=word_data.get('probability', 0.0),
                    word_index=word_index
                )
    
    logger.info(f"Verification transcription completed: {len(result['segments'])} segments")
    return result


def assemble_final_audio(project, all_segments):
    """
    Step 10: Generate final audio file without duplicates
    """
    from pydub import AudioSegment
    import os
    
    # Create output directory
    output_dir = os.path.join(settings.MEDIA_ROOT, 'assembled')
    os.makedirs(output_dir, exist_ok=True)
    
    final_audio = AudioSegment.empty()
    
    # Process each audio file in order
    audio_files = project.audio_files.filter(status='transcribed').order_by('order_index')
    
    for audio_file in audio_files:
        # Load the original audio
        audio_segment = AudioSegment.from_file(audio_file.file.path)
        
        # Get segments to keep (not marked for removal)
        kept_segments = TranscriptionSegment.objects.filter(
            audio_file=audio_file,
            is_kept=True
        ).order_by('segment_index')
        
        # Extract and combine kept segments
        for segment in kept_segments:
            start_ms = int(segment.start_time * 1000)
            end_ms = int(segment.end_time * 1000)
            
            # Extract segment and add fade in/out for smooth transitions
            segment_audio = audio_segment[start_ms:end_ms]
            segment_audio = segment_audio.fade_in(100).fade_out(100)
            
            final_audio += segment_audio
    
    # Save final audio
    timestamp = int(datetime.datetime.now().timestamp() * 1000)
    filename = f"{timestamp}-{project.title.replace(' ', '_')}_processed.wav"
    output_path = os.path.join(output_dir, filename)
    
    final_audio.export(output_path, format="wav")
    
    # Return relative path for FileField
    return f"assembled/{filename}"
