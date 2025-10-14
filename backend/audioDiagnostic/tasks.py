from celery import shared_task
import whisper
import difflib
import datetime

import os
import redis
from collections import defaultdict
import re
from pydub import AudioSegment, silence
from django.conf import settings
from .models import AudioProject, TranscriptionSegment, TranscriptionWord
from .services.docker_manager import docker_celery_manager
from .utils import get_redis_connection
import tempfile
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def transcribe_all_project_audio_task(self, project_id):
    """
    Step 1-4: Transcribe ALL audio files in a project with word timestamps
    This follows the exact workflow: transcribe all files first, then process them together
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
        # Get project and all its audio files
        from .models import AudioProject, AudioFile
        project = AudioProject.objects.get(id=project_id)
        audio_files = project.audio_files.filter(status='uploaded').order_by('order_index')
        
        if not audio_files.exists():
            raise ValueError("No audio files found to transcribe")
        
        project.status = 'transcribing'
        project.save()
        
        r.set(f"progress:{task_id}", 5)
        logger.info(f"Starting transcription for project {project_id} with {audio_files.count()} audio files")
        
        # Load Whisper model once
        model = whisper.load_model("base")
        
        total_files = audio_files.count()
        
        # Step 1-4: Transcribe each audio file with word timestamps
        for i, audio_file in enumerate(audio_files):
            logger.info(f"Transcribing audio file {audio_file.id}: {audio_file.title}")
            
            audio_file.status = 'transcribing'
            audio_file.save()
            
            # Transcribe with word timestamps
            audio_path = audio_file.file.path
            result = model.transcribe(audio_path, word_timestamps=True)
            
            # Store transcript text
            audio_file.transcript_text = result['text']
            audio_file.original_duration = result.get('duration', 0)
            
            # Clear existing segments for this audio file
            TranscriptionSegment.objects.filter(audio_file=audio_file).delete()
            TranscriptionWord.objects.filter(audio_file=audio_file).delete()
            
            # Save segments with word timestamps
            for seg_idx, segment in enumerate(result['segments']):
                seg_obj = TranscriptionSegment.objects.create(
                    audio_file=audio_file,
                    text=segment['text'].strip(),
                    start_time=segment['start'],
                    end_time=segment['end'],
                    confidence_score=segment.get('avg_logprob', 0.0),
                    segment_index=seg_idx
                )
                
                # Save individual words with timestamps
                if 'words' in segment:
                    for word_idx, word_data in enumerate(segment['words']):
                        TranscriptionWord.objects.create(
                            audio_file=audio_file,
                            segment=seg_obj,
                            word=word_data['word'].strip(),
                            start_time=word_data['start'],
                            end_time=word_data['end'],
                            confidence=word_data.get('probability', 0.0),
                            word_index=word_idx
                        )
            
            audio_file.status = 'transcribed'
            audio_file.save()
            
            # Update progress
            progress = 5 + int((i + 1) / total_files * 85)
            r.set(f"progress:{task_id}", progress)
        
        # All audio files transcribed
        project.status = 'transcribed'
        project.save()
        
        r.set(f"progress:{task_id}", 100)
        
        # Unregister task
        docker_celery_manager.unregister_task(task_id)
        
        return {
            'status': 'completed',
            'message': f'All {total_files} audio files transcribed successfully',
            'files_transcribed': total_files
        }
        
    except Exception as e:
        logger.error(f"Transcription failed for project {project_id}: {str(e)}")
        
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
def transcribe_audio_file_task(self, audio_file_id):
    """
    Legacy single-file transcription task - kept for backward compatibility
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
        from .models import AudioFile
        audio_file = AudioFile.objects.get(id=audio_file_id)
        
        audio_file.task_id = task_id
        audio_file.status = 'transcribing'
        audio_file.save()
        
        r.set(f"progress:{task_id}", 10)
        
        # Step 1: Transcribe audio with word timestamps
        logger.info(f"Starting transcription for audio file {audio_file_id}")
        model = whisper.load_model("base")
        
        audio_path = audio_file.file.path
        result = model.transcribe(audio_path, word_timestamps=True)
        
        r.set(f"progress:{task_id}", 60)
        
        # Save transcription results
        transcript_text = result['text']
        audio_file.transcript_text = transcript_text
        
        # Clear existing segments for this audio file
        TranscriptionSegment.objects.filter(audio_file=audio_file).delete()
        TranscriptionWord.objects.filter(audio_file=audio_file).delete()
        
        r.set(f"progress:{task_id}", 80)
        
        # Save segments (without duplicate detection at this stage)
        for segment_index, segment in enumerate(result['segments']):
            seg_obj = TranscriptionSegment.objects.create(
                audio_file=audio_file,
                text=segment['text'].strip(),
                start_time=segment['start'],
                end_time=segment['end'],
                confidence_score=segment.get('avg_logprob', 0.0),
                is_duplicate=False,  # Will be determined later in processing step
                segment_index=segment_index
            )
            
            # Save words if available
            if 'words' in segment:
                for word_index, word_data in enumerate(segment['words']):
                    TranscriptionWord.objects.create(
                        audio_file=audio_file,
                        segment=seg_obj,
                        word=word_data['word'].strip(),
                        start_time=word_data['start'],
                        end_time=word_data['end'],
                        confidence=word_data.get('probability', 0.0),
                        word_index=word_index
                    )
        
        r.set(f"progress:{task_id}", 100)
        
        # Update audio file status
        audio_file.status = 'transcribed'
        audio_file.save()
        
        # Unregister task (will trigger shutdown timer if no other tasks)
        docker_celery_manager.unregister_task(task_id)
        
        return {
            'status': 'completed',
            'message': 'Audio transcription completed successfully',
            'transcript_text': transcript_text,
            'segments_count': len(result['segments'])
        }
        
    except Exception as e:
        logger.error(f"Transcription failed for audio file {audio_file_id}: {str(e)}")
        
        # Update audio file with error
        try:
            audio_file.status = 'failed'
            audio_file.error_message = str(e)
            audio_file.save()
        except:
            pass
            
        # Unregister task even on failure
        docker_celery_manager.unregister_task(task_id)
            
        r.set(f"progress:{task_id}", -1)
        raise e

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
        from .models import AudioProject, AudioFile, ProcessingResult
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
        from .models import AudioFile
        audio_file = AudioFile.objects.get(id=audio_file_id)
        project = audio_file.project
        
        # Check if audio is already transcribed
        if audio_file.status != 'transcribed':
            raise ValueError(f"Audio file must be transcribed first. Current status: {audio_file.status}")
        
        audio_file.task_id = task_id
        audio_file.status = 'processing'
        audio_file.save()
        
        r.set(f"progress:{task_id}", 10)
        
        # Get existing transcription segments
        segments = TranscriptionSegment.objects.filter(audio_file=audio_file).order_by('start_time')
        if not segments.exists():
            raise ValueError("No transcription segments found. Please transcribe the audio first.")
        
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

def save_transcription_to_db(audio_file, segments, duplicates_info):
    """
    Save transcription segments and words to database with duplicate marking.
    """
    duplicate_indices = set(dup['index'] for dup in duplicates_info['duplicates_to_remove'])
    
    for i, segment in enumerate(segments):
        # Create segment
        is_duplicate = i in duplicate_indices
        
        db_segment = TranscriptionSegment.objects.create(
            audio_file=audio_file,
            text=segment['text'],
            start_time=segment['start'],
            end_time=segment['end'],
            is_duplicate=is_duplicate,
            segment_index=i,
            confidence_score=1.0  # Whisper doesn't provide segment confidence
        )
        
        # Create words for this segment
        for j, word_data in enumerate(segment.get('words', [])):
            TranscriptionWord.objects.create(
                segment=db_segment,
                audio_file=audio_file,
                word=word_data['word'],
                start_time=word_data['start'],
                end_time=word_data['end'],
                confidence=word_data.get('probability', 1.0),
                word_index=j
            )

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


def find_text_in_pdf(text, pdf_text):
    """Check if transcript text appears in PDF content"""
    normalized_text = ' '.join(text.strip().lower().split())
    normalized_pdf = ' '.join(pdf_text.strip().lower().split())
    return normalized_text in normalized_pdf

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

def get_final_transcript_without_duplicates(all_segments):
    """Get the final transcript with duplicates removed"""
    kept_segments = [seg_data for seg_data in all_segments 
                    if not hasattr(seg_data['segment'], 'is_kept') or seg_data['segment'].is_kept]
    
    # Sort by file order and time
    kept_segments.sort(key=lambda x: (x['file_order'], x['start_time']))
    
    return ' '.join([seg_data['text'] for seg_data in kept_segments])

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

def get_audio_duration(file_path):
    """Get duration of audio file in seconds"""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0  # Convert ms to seconds
    except:
        return 0

def normalize(text):
    # Remove leading [number] or [-1], lowercase, strip, and collapse whitespace
    text = re.sub(r'^\[\-?\d+\]\s*', '', text)
    return ' '.join(text.strip().lower().split())

@shared_task(bind=True)
def transcribe_audio_task(self, audio_path, audio_url):
    import pprint
    task_id = self.request.id
    
    # Get Redis connection appropriate for this environment
    r = get_redis_connection()
    r.set(f"progress:{task_id}", 0)

    model = whisper.load_model("base")
    r.set(f"progress:{task_id}", 10)

    # Transcribe with word timestamps
    result = model.transcribe(audio_path, word_timestamps=True)
    r.set(f"progress:{task_id}", 80)

    segments = result.get("segments", [])

    # Split segments into sentences with approximate timestamps
    all_sentences = []
    for seg in segments:
        all_sentences.extend(split_segment_to_sentences(seg))

    # Group sentences by normalized text (exact matches)
    sentence_map = defaultdict(list)
    for idx, sent in enumerate(all_sentences):
        norm = normalize(sent['text'])
        if norm:  # skip empty lines
            sentence_map[norm].append({**sent, 'index': idx})

    # Only keep groups with more than one occurrence (exact repeats)
    repetitive = [group for group in sentence_map.values() if len(group) > 1]

    # --- Fuzzy matching for potential repeats ---
    norm_sentences = [(normalize(s['text']), i, s) for i, s in enumerate(all_sentences)]
    fuzzy_groups = []
    threshold = 0.85  # Adjust as needed

    # Build a set of all indices in exact repeats to exclude from fuzzy
    exact_indices = set()
    for group in repetitive:
        for item in group:
            exact_indices.add(item['index'])

    # For each sentence, compare to all others (excluding exact repeats)
    visited_pairs = set()
    for i, (norm_i, idx_i, sent_i) in enumerate(norm_sentences):
        if idx_i in exact_indices or not norm_i:
            continue
        group = [{**sent_i, 'index': idx_i}]
        for j, (norm_j, idx_j, sent_j) in enumerate(norm_sentences):
            if i == j or idx_j in exact_indices or not norm_j:
                continue
            pair_key = tuple(sorted([idx_i, idx_j]))
            if pair_key in visited_pairs:
                continue
            ratio = difflib.SequenceMatcher(None, norm_i, norm_j).ratio()
            if ratio >= threshold:
                group.append({**sent_j, 'index': idx_j})
                visited_pairs.add(pair_key)
        unique_texts = set(s['text'] for s in group)
        if len(group) > 1 and len(unique_texts) > 1:
            group_indices = set(s['index'] for s in group)
            if not any(group_indices <= set(s['index'] for s in g) for g in fuzzy_groups):
                fuzzy_groups.append(group)

    # Find noise regions (non-speech)
    noise_regions = find_noise_regions(audio_path, all_sentences)

    r.set(f"progress:{task_id}", 100)

    pprint.pprint({
        'audio_url': audio_url,
        'all_segments': all_sentences,
        'repetitive_groups': repetitive,
        'potential_repetitive_groups': fuzzy_groups,
        'noise_regions': noise_regions,
    })

    return {
        'audio_url': audio_url,
        'all_segments': all_sentences,
        'repetitive_groups': repetitive,
        'potential_repetitive_groups': fuzzy_groups,
        'noise_regions': noise_regions,
    }

def split_segment_to_sentences(seg, next_segment_start=None, audio_end=None):
    import logging
    logger = logging.getLogger("audioDiagnostic.tasks")
    text = seg['text']
    words = seg.get('words', [])
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(sentences) == 1 or not words:
        buffer = 0.5  # 200 ms
        # Don't go past the next segment or audio end
        max_end = seg['end']
        if next_segment_start:
            max_end = min(max_end + buffer, next_segment_start)
        elif audio_end:
            max_end = min(max_end + buffer, audio_end)
        else:
            max_end = max_end + buffer
        logger.info(f"Only one sentence or no words. Returning segment as is, but with padded end: {max_end:.2f}")
        return [{
            'text': sentences[0],
            'start': seg['start'],
            'end': max_end,
            'words': words
        }]

    total_words = len(words)
    avg_words = total_words // len(sentences)
    result = []
    word_idx = 0
    for i, sent in enumerate(sentences):
        if i == len(sentences) - 1:
            sent_words = words[word_idx:]
        else:
            sent_words = words[word_idx:word_idx+avg_words]
        if sent_words:
            start = sent_words[0]['start']
            if i == len(sentences) - 1:
                end = seg['end']
                logger.info(
                    f"Sentence {i+1}/{len(sentences)} (LAST): '{sent}' | "
                    f"Start: {start:.2f}, End: {end:.2f} (using seg['end']: {seg['end']}) | "
                    f"First word: {sent_words[0]['word']}, Last word: {sent_words[-1]['word']}"
                )
            else:
                buffer = 0.5
                end = sent_words[-1]['end'] + buffer
                logger.info(
                    f"Sentence {i+1}/{len(sentences)}: '{sent}' | "
                    f"Start: {start:.2f}, End: {end:.2f} (last word end: {sent_words[-1]['end']}, buffer: {buffer}) | "
                    f"First word: {sent_words[0]['word']}, Last word: {sent_words[-1]['word']}"
                )
        else:
            start = seg['start']
            end = seg['end']
            logger.info(
                f"Sentence {i+1}/{len(sentences)}: '{sent}' | "
                f"Start: {start:.2f}, End: {end:.2f} (no words fallback)"
            )
        result.append({
            'text': sent,
            'start': start,
            'end': end,
            'words': sent_words
        })
        word_idx += avg_words
    return result



def find_noise_regions(audio_path, speech_segments, min_silence_len=300, silence_thresh=-40):
    """
    Returns a list of noise regions (start, end in seconds) not covered by speech_segments.
    """
    audio = AudioSegment.from_file(audio_path)
    duration = len(audio) / 1000.0  # seconds

    # Get all non-silent (speech) regions from your speech_segments
    speech_times = []
    for seg in speech_segments:
        speech_times.append((seg['start'], seg['end']))

    # Merge overlapping speech regions
    speech_times.sort()
    merged = []
    for start, end in speech_times:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    # Find noise regions between speech
    noise_regions = []
    prev_end = 0.0
    for start, end in merged:
        if start > prev_end:
            noise_regions.append({'start': prev_end, 'end': start, 'label': 'Noise'})
        prev_end = end
    if prev_end < duration:
        noise_regions.append({'start': prev_end, 'end': duration, 'label': 'Noise'})
    return noise_regions



#---------------------------------n8n integration---------------------------------

@shared_task(bind=True)
def transcribe_audio_words_task(self, audio_path, audio_url):
    """
    Transcribe the audio and return:
      - a list of words with their start and end times,
      - the full transcript,
      - the segments (phrases/sentences with timings).
    """
    import whisper
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, word_timestamps=True)

    # Collect all words with timestamps
    words = []
    for segment in result.get("segments", []):
        for word in segment.get("words", []):
            words.append({
                "word": word["word"],
                "start": word["start"],
                "end": word["end"],
                "probability": word.get("probability")
            })

    # Use segments as sentences/phrases
    segments = []
    for segment in result.get("segments", []):
        segments.append({
            "text": segment.get("text", ""),
            "start": segment.get("start"),
            "end": segment.get("end"),
            "words": segment.get("words", [])
        })

    # Full transcript as a string
    transcript = result.get("text", "")

    # Repeat detection using normalized segment texts
    from collections import defaultdict
    def normalize(text):
        import re
        text = re.sub(r'^\[\-?\d+\]\s*', '', text)
        return ' '.join(text.strip().lower().split())

    sentence_map = defaultdict(list)
    for idx, seg in enumerate(segments):
        norm = normalize(seg['text'])
        if norm:
            sentence_map[norm].append({**seg, 'index': idx})

    repetitive = [group for group in sentence_map.values() if len(group) > 1]

    return {
        "audio_url": audio_url,
        "transcript": transcript,
        "segments": segments,
        "words": words,
        "repetitive_groups": repetitive
    }





from celery import shared_task
import difflib
import re
from PyPDF2 import PdfReader

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
def process_confirmed_deletions_task(self, project_id, confirmed_deletions):
    """
    Process user-confirmed deletions and generate final clean audio file
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
        from .models import AudioProject, AudioFile, TranscriptionSegment
        
        project = AudioProject.objects.get(id=project_id)
        project.status = 'processing'
        project.save()
        
        r.set(f"progress:{task_id}", 10)
        logger.info(f"Processing {len(confirmed_deletions)} confirmed deletions for project {project_id}")
        
        # Get all audio files in order
        audio_files = project.audio_files.filter(status='transcribed').order_by('order_index')
        
        # Create set of segment IDs to delete
        segments_to_delete = set(deletion['segment_id'] for deletion in confirmed_deletions)
        
        r.set(f"progress:{task_id}", 30)
        
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
        final_audio_path = self.generate_clean_audio(project, segments_to_delete)
        
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
        
        r.set(f"progress:{task_id}", 100)
        logger.info(f"Successfully processed deletions for project {project_id}")
        
        return {
            'success': True,
            'deletions_processed': len(confirmed_deletions),
            'final_audio': project.final_processed_audio.url if project.final_processed_audio else None
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

    def generate_clean_audio(self, project, segments_to_delete):
        """
        Generate final audio file with specified segments removed
        """
        from pydub import AudioSegment
        import os
        
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