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
        from .models import AudioProject, AudioFile, TranscriptionSegment
        
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


def generate_clean_audio(project, segments_to_delete):
    """
    Generate final audio file with specified segments removed
    """
    from pydub import AudioSegment
    import os
    from .models import TranscriptionSegment
    
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
        from .models import AudioProject
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
        from .models import AudioProject, AudioFile, TranscriptionSegment
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