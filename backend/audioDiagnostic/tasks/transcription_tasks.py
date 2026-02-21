"""
Transcription Tasks for audioDiagnostic app.
"""
from ._base import *

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
        from audioDiagnostic.models import AudioProject, AudioFile
        project = AudioProject.objects.get(id=project_id)
        audio_files = project.audio_files.filter(status='uploaded').order_by('order_index')
        
        if not audio_files.exists():
            raise ValueError("No audio files found to transcribe")
        
        project.status = 'transcribing'
        project.save()
        
        r.set(f"progress:{task_id}", 5)
        logger.info(f"Starting transcription for project {project_id} with {audio_files.count()} audio files")
        
        # Ensure FFmpeg is available for Whisper
        ensure_ffmpeg_in_path()
        
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
            transcript_text = result['text']
            audio_file.transcript_text = transcript_text
            audio_file.transcript_source = 'original'
            audio_file.original_duration = result.get('duration', 0)
            audio_file.error_message = ''  # Clear any previous errors
            
            # Create or update Transcription object (required for frontend)
            from audioDiagnostic.models import Transcription
            transcription, created = Transcription.objects.get_or_create(
                audio_file=audio_file,
                defaults={
                    'full_text': transcript_text,
                    'word_count': len(transcript_text.split())
                }
            )
            
            if not created:
                transcription.full_text = transcript_text
                transcription.word_count = len(transcript_text.split())
                transcription.save()
            
            # Clear existing segments for this audio file
            TranscriptionSegment.objects.filter(audio_file=audio_file).delete()
            TranscriptionWord.objects.filter(audio_file=audio_file).delete()
            
            # Save segments with word timestamps
            for seg_idx, segment in enumerate(result['segments']):
                seg_obj = TranscriptionSegment.objects.create(
                    audio_file=audio_file,
                    transcription=transcription,
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
            
            # Calculate average confidence
            segments = TranscriptionSegment.objects.filter(audio_file=audio_file)
            if segments.exists():
                avg_confidence = segments.aggregate(models.Avg('confidence_score'))['confidence_score__avg']
                transcription.confidence_score = avg_confidence
                transcription.save()
            
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
        from audioDiagnostic.models import AudioFile
        audio_file = AudioFile.objects.get(id=audio_file_id)
        
        audio_file.task_id = task_id
        audio_file.status = 'transcribing'
        audio_file.save()
        
        r.set(f"progress:{task_id}", 10)
        
        # Ensure FFmpeg is available for Whisper
        ensure_ffmpeg_in_path()
        
        # Step 1: Transcribe audio with word timestamps
        logger.info(f"Starting transcription for audio file {audio_file_id}")
        model = whisper.load_model("base")
        
        audio_path = audio_file.file.path
        result = model.transcribe(audio_path, word_timestamps=True)
        
        r.set(f"progress:{task_id}", 60)
        
        # Save transcription results
        transcript_text = result['text']
        audio_file.transcript_text = transcript_text
        audio_file.transcript_source = 'original'
        
        # Create or update Transcription object (required for frontend)
        from audioDiagnostic.models import Transcription
        transcription, created = Transcription.objects.get_or_create(
            audio_file=audio_file,
            defaults={
                'full_text': transcript_text,
                'word_count': len(transcript_text.split())
            }
        )
        
        if not created:
            transcription.full_text = transcript_text
            transcription.word_count = len(transcript_text.split())
            transcription.save()
        
        # Clear existing segments for this audio file
        TranscriptionSegment.objects.filter(audio_file=audio_file).delete()
        TranscriptionWord.objects.filter(audio_file=audio_file).delete()
        
        r.set(f"progress:{task_id}", 80)
        
        # Save segments (without duplicate detection at this stage)
        for segment_index, segment in enumerate(result['segments']):
            seg_obj = TranscriptionSegment.objects.create(
                audio_file=audio_file,
                transcription=transcription,
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
        
        # Calculate average confidence
        segments = TranscriptionSegment.objects.filter(audio_file=audio_file)
        if segments.exists():
            avg_confidence = segments.aggregate(models.Avg('confidence_score'))['confidence_score__avg']
            transcription.confidence_score = avg_confidence
            transcription.save()
        
        r.set(f"progress:{task_id}", 100)
        
        # Update audio file status
        audio_file.status = 'transcribed'
        audio_file.error_message = ''  # Clear any previous errors
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

def ensure_ffmpeg_in_path():
    """
    Ensure FFmpeg is in the PATH environment variable.
    This is needed for Whisper to work on Windows.
    Uses FFMPEG_PATH environment variable if set, otherwise defaults to common locations.
    """
    # Try environment variable first
    ffmpeg_path = os.getenv('FFMPEG_PATH')
    
    # If not set, try common locations (platform-specific defaults)
    if not ffmpeg_path:
        import platform
        if platform.system() == 'Windows':
            ffmpeg_path = r"C:\ffmpeg\ffmpeg-8.0-essentials_build\bin"
        else:
            # On Linux/Mac, ffmpeg is usually in PATH already
            ffmpeg_path = None
    
    # If we have a path, add it to PATH if it exists
    if ffmpeg_path:
        if os.path.exists(ffmpeg_path):
            current_path = os.environ.get('PATH', '')
            if ffmpeg_path not in current_path:
                os.environ['PATH'] = ffmpeg_path + os.pathsep + current_path
                logger.info(f"Added FFmpeg to PATH: {ffmpeg_path}")
            return True
        else:
            logger.warning(f"FFmpeg not found at {ffmpeg_path}")
            return False
    else:
        # Assume ffmpeg is already in PATH
        logger.info("Using system FFmpeg from PATH")
        return True

# ============================================================================
# TAB 2: SINGLE-FILE TRANSCRIPTION TASK
# ============================================================================

@shared_task(bind=True)
def transcribe_single_audio_file_task(self, audio_file_id):
    """
    Tab 2: Transcribe a SINGLE audio file with word-level timestamps
    Creates a Transcription object and TranscriptionSegment records
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
        from audioDiagnostic.models import AudioFile, Transcription, TranscriptionSegment, TranscriptionWord
        
        # Get audio file
        audio_file = AudioFile.objects.get(id=audio_file_id)
        
        # Update progress
        self.update_state(state='PROGRESS', meta={'progress': 10, 'message': 'Loading audio file...'})
        r.set(f"progress:{task_id}", 10)
        
        logger.info(f"Starting transcription for audio file {audio_file_id}: {audio_file.filename}")
        
        # Ensure FFmpeg is available
        ensure_ffmpeg_in_path()
        
        # Update progress
        self.update_state(state='PROGRESS', meta={'progress': 20, 'message': 'Loading Whisper model...'})
        r.set(f"progress:{task_id}", 20)
        
        # Load Whisper model
        model = whisper.load_model("base")
        
        # Update progress
        self.update_state(state='PROGRESS', meta={'progress': 30, 'message': 'Transcribing audio...'})
        r.set(f"progress:{task_id}", 30)
        
        # Transcribe with word timestamps
        audio_path = audio_file.file.path
        result = model.transcribe(audio_path, word_timestamps=True)
        
        # Update progress
        self.update_state(state='PROGRESS', meta={'progress': 70, 'message': 'Saving transcription...'})
        r.set(f"progress:{task_id}", 70)
        
        # Create or update Transcription object
        transcription, created = Transcription.objects.get_or_create(
            audio_file=audio_file,
            defaults={
                'full_text': result['text'],
                'word_count': len(result['text'].split())
            }
        )
        
        if not created:
            # Update existing transcription
            transcription.full_text = result['text']
            transcription.word_count = len(result['text'].split())
            transcription.save()
        
        # Clear existing segments
        TranscriptionSegment.objects.filter(transcription=transcription).delete()
        
        # Save segments with word timestamps
        for seg_idx, segment in enumerate(result['segments']):
            seg_obj = TranscriptionSegment.objects.create(
                transcription=transcription,
                audio_file=audio_file,  # For backwards compatibility
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
        
        # Calculate average confidence
        segments = TranscriptionSegment.objects.filter(transcription=transcription)
        if segments.exists():
            avg_confidence = segments.aggregate(models.Avg('confidence_score'))['confidence_score__avg']
            transcription.confidence_score = avg_confidence
            transcription.save()
        
        # Update audio file status
        audio_file.status = 'transcribed'
        audio_file.transcript_text = result['text']  # Legacy field
        audio_file.original_duration = result.get('duration', 0)
        audio_file.error_message = ''  # Clear any previous errors
        audio_file.save()
        
        # Update progress
        self.update_state(state='PROGRESS', meta={'progress': 100, 'message': 'Transcription complete!'})
        r.set(f"progress:{task_id}", 100)
        
        logger.info(f"Transcription complete for audio file {audio_file_id}")
        
        return {
            'success': True,
            'audio_file_id': audio_file.id,
            'transcription_id': transcription.id,
            'word_count': transcription.word_count,
            'segment_count': segments.count()
        }
        
    except Exception as e:
        logger.error(f"Transcription failed for audio file {audio_file_id}: {str(e)}")
        
        # Update audio file status
        try:
            audio_file = AudioFile.objects.get(id=audio_file_id)
            audio_file.status = 'failed'
            audio_file.error_message = str(e)
            audio_file.save()
        except:
            pass
        
        r.set(f"progress:{task_id}", -1)
        raise e
    
    finally:
        # Unregister task
        docker_celery_manager.unregister_task(task_id)


@shared_task(bind=True)
def retranscribe_processed_audio_task(self, audio_file_id):
    """
    Re-transcribe a processed audio file (after deletions) for maximum accuracy.
    This creates a fresh transcription of the clean audio.
    Option C (Hybrid): Provides most accurate transcript after deletions.
    """
    task_id = self.request.id
    r = get_redis_connection()
    
    # Set up infrastructure
    if not docker_celery_manager.setup_infrastructure():
        raise Exception("Failed to set up Docker and Celery infrastructure")
    
    docker_celery_manager.register_task(task_id)
    
    try:
        from audioDiagnostic.models import AudioFile
        
        # Get audio file
        audio_file = AudioFile.objects.get(id=audio_file_id)
        
        # Must have processed audio
        if not audio_file.processed_audio:
            raise ValueError("No processed audio file found. Run deletion processing first.")
        
        # Update status
        audio_file.retranscription_status = 'processing'
        audio_file.retranscription_task_id = task_id
        audio_file.save()
        
        r.set(f"progress:{task_id}", 10)
        self.update_state(state='PROGRESS', meta={'progress': 10, 'message': 'Starting re-transcription...'})
        logger.info(f"Starting re-transcription for processed audio file {audio_file_id}")
        
        # Ensure FFmpeg is available
        ensure_ffmpeg_in_path()
        
        # Load Whisper model
        r.set(f"progress:{task_id}", 20)
        self.update_state(state='PROGRESS', meta={'progress': 20, 'message': 'Loading Whisper model...'})
        model = whisper.load_model("base")
        
        # Transcribe the processed audio
        r.set(f"progress:{task_id}", 30)
        self.update_state(state='PROGRESS', meta={'progress': 30, 'message': 'Transcribing processed audio...'})
        audio_path = audio_file.processed_audio.path
        result = model.transcribe(audio_path, word_timestamps=True)
        
        r.set(f"progress:{task_id}", 70)
        self.update_state(state='PROGRESS', meta={'progress': 70, 'message': 'Saving new transcription...'})
        
        # Update the transcript_text with the new transcription
        transcript_text = result['text']
        
        # Create or update Transcription object (required for frontend to recognize transcription)
        from audioDiagnostic.models import Transcription
        transcription, created = Transcription.objects.get_or_create(
            audio_file=audio_file,
            defaults={
                'full_text': transcript_text,
                'word_count': len(transcript_text.split())
            }
        )
        
        if not created:
            # Update existing transcription
            transcription.full_text = transcript_text
            transcription.word_count = len(transcript_text.split())
            transcription.save()
        
        # Update audio file fields
        audio_file.transcript_text = transcript_text  # Overwrite with fresh transcription
        audio_file.transcript_source = 'retranscribed'  # Mark as most accurate
        audio_file.retranscription_status = 'completed'
        audio_file.status = 'transcribed'  # Ensure status is correct
        audio_file.error_message = ''  # Clear any previous errors
        
        r.set(f"progress:{task_id}", 90)
        logger.info(f"Re-transcription complete for audio file {audio_file_id}: {len(transcript_text)} chars")
        
        # Save
        audio_file.save()
        
        r.set(f"progress:{task_id}", 100)
        self.update_state(state='PROGRESS', meta={'progress': 100, 'message': 'Re-transcription complete!'})
        
        return {
            'success': True,
            'audio_file_id': audio_file_id,
            'transcript_text': transcript_text,
            'transcript_length': len(transcript_text),
            'segments_count': len(result['segments']),
            'transcript_source': 'retranscribed'
        }
        
    except Exception as e:
        logger.error(f"Re-transcription failed for audio file {audio_file_id}: {str(e)}")
        
        # Update status
        try:
            audio_file = AudioFile.objects.get(id=audio_file_id)
            audio_file.retranscription_status = 'failed'
            audio_file.error_message = str(e)
            audio_file.save()
        except:
            pass
        
        r.set(f"progress:{task_id}", -1)
        raise e
    
    finally:
        docker_celery_manager.unregister_task(task_id)