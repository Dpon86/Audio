"""
Management command: Create missing Transcription objects for files that have transcript_text but no Transcription
Usage: python manage.py fix_transcriptions
"""
from django.core.management.base import BaseCommand
from audioDiagnostic.models import AudioFile, Transcription


class Command(BaseCommand):
    help = 'Create Transcription objects for all AudioFiles that have transcript_text but no Transcription'

    def handle(self, *args, **options):
        """Create Transcription objects for all AudioFiles that have transcript_text but no Transcription"""
        
        # Find all audio files with transcript_text
        audio_files = AudioFile.objects.filter(
            transcript_text__isnull=False
        ).exclude(transcript_text='')
        
        total = audio_files.count()
        fixed = 0
        skipped = 0
        
        self.stdout.write(f"Found {total} audio files with transcript_text")
        
        for audio_file in audio_files:
            try:
                # Check if Transcription already exists
                if hasattr(audio_file, 'transcription') and audio_file.transcription:
                    self.stdout.write(f"  ✓ {audio_file.filename} - already has Transcription object")
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
            if audio_file.status == 'uploaded' or audio_file.status == 'failed':
                audio_file.status = 'transcribed'
            
            # Set transcript_source if not set
            if not audio_file.transcript_source or audio_file.transcript_source == 'none':
                audio_file.transcript_source = 'original'
            
            audio_file.save()
            
            self.stdout.write(self.style.SUCCESS(
                f"  ✅ {audio_file.filename} - created Transcription object (ID: {transcription.id})"
            ))
            fixed += 1
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Complete!"))
        self.stdout.write(f"   Fixed: {fixed}")
        self.stdout.write(f"   Skipped (already had Transcription): {skipped}")
        self.stdout.write(f"   Total: {total}")
