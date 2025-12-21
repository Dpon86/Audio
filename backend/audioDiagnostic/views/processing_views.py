"""
Processing Views for audioDiagnostic app.
"""
from ._base import *

from ..tasks import process_project_duplicates_task, process_audio_file_task

class ProjectProcessView(APIView):
    """
    POST: Step 5-10: Process transcribed audio files for duplicates
    This is the second phase - only works after all files are transcribed
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProcessRateThrottle]
    throttle_classes = [ProcessRateThrottle]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Validate that transcription is complete
        if project.status != 'transcribed':
            return Response({
                'error': f'Project must be transcribed first. Current status: {project.status}',
                'required_status': 'transcribed',
                'current_status': project.status
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check that all audio files are transcribed
        transcribed_files = project.audio_files.filter(status='transcribed')
        if not transcribed_files.exists():
            return Response({'error': 'No transcribed audio files found'}, status=status.HTTP_400_BAD_REQUEST)
        
        if project.status == 'processing':
            return Response({'error': 'Project is already being processed'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Start duplicate processing for all transcribed files
        task = process_project_duplicates_task.delay(project.id)
        
        project.status = 'processing'
        project.save()
        
        return Response({
            'message': f'Started processing duplicates across {transcribed_files.count()} transcribed files',
            'task_id': task.id,
            'project_id': project.id,
            'transcribed_files_count': transcribed_files.count(),
            'phase': 'duplicate_processing'
        })


class AudioFileProcessView(APIView):
    """
    POST: Process a specific audio file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        from audioDiagnostic.models import AudioFile
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Validate requirements
        if not project.pdf_file:
            return Response({'error': 'PDF file required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if audio_file.status != 'transcribed':
            return Response({'error': f'Audio file must be transcribed first. Current status: {audio_file.status}'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if audio_file.status == 'processing':
            return Response({'error': 'Audio file is already being processed'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Start processing task for this specific audio file
        task = process_audio_file_task.delay(audio_file.id)
        audio_file.task_id = task.id
        audio_file.status = 'processing'
        audio_file.save()
        
        return Response({
            'message': 'Processing started for audio file',
            'task_id': task.id,
            'project_id': project.id,
            'audio_file_id': audio_file.id
        })


