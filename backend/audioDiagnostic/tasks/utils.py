"""
Utils for audioDiagnostic app.
"""
from ._base import *

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

def get_final_transcript_without_duplicates(all_segments):
    """Get the final transcript with duplicates removed"""
    kept_segments = [seg_data for seg_data in all_segments 
                    if not hasattr(seg_data['segment'], 'is_kept') or seg_data['segment'].is_kept]
    
    # Sort by file order and time
    kept_segments.sort(key=lambda x: (x['file_order'], x['start_time']))
    
    return ' '.join([seg_data['text'] for seg_data in kept_segments])

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
