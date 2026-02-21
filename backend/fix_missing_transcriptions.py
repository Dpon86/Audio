"""
Fix script: Create missing Transcription objects for files that have transcript_text but no Transcription
Run this once to fix all existing transcribed files
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from audioDiagnostic.models import AudioFile, Transcription

def fix_missing_transcriptions():
    """Create Transcription objects for all AudioFiles that have transcript_text but no Transcription"""
    
    # Find all audio files with transcript_text
    audio_files = AudioFile.objects.filter(
        transcript_text__isnull=False
    ).exclude(transcript_text='')
    
    total = audio_files.count()
    fixed = 0
    skipped = 0
    
    print(f"Found {total} audio files with transcript_text")
    
    for audio_file in audio_files:
        try:
            # Check if Transcription already exists
            if hasattr(audio_file, 'transcription') and audio_file.transcription:
                print(f"  ✓ {audio_file.filename} - already has Transcription object")
                skipped += 1
                continue
        except Transcription.DoesNotExist:
            pass
        
        # Create missing Transcription object
        transcription = Transcription.objects.create(
            audio_file=audio_file,
            full_text=audio_file.transcript_text,
            word_count=len(audio_file.transcript_text.split()) if audio_file.transcript_text else 0,
            confidence_score=None
        )
        
        # Ensure status is correct
        if audio_file.status == 'uploaded':
            audio_file.status = 'transcribed'
        
        # Set transcript_source if not set
        if not audio_file.transcript_source or audio_file.transcript_source == 'none':
            audio_file.transcript_source = 'original'
        
        audio_file.save()
        
        print(f"  ✅ {audio_file.filename} - created Transcription object (ID: {transcription.id})")
        fixed += 1
    
    print(f"\n✅ Complete!")
    print(f"   Fixed: {fixed}")
    print(f"   Skipped (already had Transcription): {skipped}")
    print(f"   Total: {total}")

if __name__ == '__main__':
    fix_missing_transcriptions()
