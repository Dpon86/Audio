"""
Quick-fix view: Create missing Transcription objects for all files with transcript_text
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, TokenAuthentication, BasicAuthentication

from ..models import AudioFile, Transcription


class FixMissingTranscriptionsView(APIView):
    """
    POST: Create Transcription objects for all AudioFiles that have transcript_text but no Transcription
    This fixes files that were transcribed with old code before the Transcription model was required
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id):
        """Fix all missing transcriptions for files in this project"""
        from django.shortcuts import get_object_or_404
        from ..models import AudioProject
        
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Find all audio files in this project with transcript_text but no Transcription
        audio_files = project.audio_files.filter(
            transcript_text__isnull=False
        ).exclude(transcript_text='')
        
        fixed = 0
        skipped = 0
        errors = []
        
        for audio_file in audio_files:
            try:
                # Check if Transcription already exists
                if hasattr(audio_file, 'transcription') and audio_file.transcription:
                    skipped += 1
                    continue
            except Transcription.DoesNotExist:
                pass
            
            try:
                # Create missing Transcription object
                transcription = Transcription.objects.create(
                    audio_file=audio_file,
                    full_text=audio_file.transcript_text,
                    word_count=len(audio_file.transcript_text.split()) if audio_file.transcript_text else 0
                )
                
                # Ensure status is correct
                if audio_file.status in ['uploaded', 'failed']:
                    audio_file.status = 'transcribed'
                
                # Set transcript_source if not set
                if not audio_file.transcript_source or audio_file.transcript_source == 'none':
                    audio_file.transcript_source = 'original'
                
                # Clear error message
                audio_file.error_message = None
                
                audio_file.save()
                fixed += 1
                
            except Exception as e:
                errors.append(f"{audio_file.filename}: {str(e)}")
        
        return Response({
            'success': True,
            'message': f'Fixed {fixed} files, skipped {skipped} files',
            'fixed': fixed,
            'skipped': skipped,
            'errors': errors
        })
