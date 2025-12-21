"""
Transcription Views for audioDiagnostic app.
"""
from ._base import *

from ..tasks import transcribe_all_project_audio_task, transcribe_audio_file_task

class ProjectTranscribeView(APIView):
    """
    POST: Step 1-4: Transcribe ALL audio files in project with word timestamps
    This is the first phase of the new workflow
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [TranscribeRateThrottle]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Validate requirements  
        if not project.pdf_file:
            return Response({'error': 'PDF file required before transcription'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if project has audio files - allow restart for uploaded, transcribing, transcribed, or failed
        audio_files = project.audio_files.filter(status__in=['uploaded', 'transcribing', 'transcribed', 'failed'])
        if not audio_files.exists():
            return Response({'error': 'No audio files available for transcription'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Reset audio files to uploaded status for fresh transcription
        audio_files.update(status='uploaded')
        
        # Start transcription for ALL audio files
        task = transcribe_all_project_audio_task.delay(project.id)
        
        project.status = 'transcribing'
        project.save()
        
        return Response({
            'message': f'Started transcribing all {audio_files.count()} audio files',
            'task_id': task.id,
            'project_id': project.id,
            'audio_files_count': audio_files.count(),
            'phase': 'transcription'
        })


class AudioFileTranscribeView(APIView):
    """
    POST: Transcribe a specific audio file (step 1 of 2-step process)
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        from .models import AudioFile
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Allow transcription for pending, failed, or uploaded status
        if audio_file.status not in ['pending', 'failed', 'uploaded']:
            return Response({'error': f'Audio file cannot be transcribed. Current status: {audio_file.status}'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Start transcription task for this specific audio file
        from audioDiagnostic.tasks import transcribe_audio_file_task
        task = transcribe_audio_file_task.delay(audio_file.id)
        audio_file.task_id = task.id
        audio_file.status = 'transcribing'
        audio_file.save()
        
        return Response({
            'message': 'Audio transcription started',
            'task_id': task.id,
            'project_id': project.id,
            'audio_file_id': audio_file.id
        })



class AudioFileRestartView(APIView):
    """
    POST: Restart transcription for an audio file (clears task and resets status)
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        from audioDiagnostic.models import AudioFile
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Cancel any existing Celery task if it exists
        if audio_file.task_id:
            from celery.result import AsyncResult
            task_result = AsyncResult(audio_file.task_id)
            task_result.revoke(terminate=True)
        
        # Reset the audio file status and clear task_id
        audio_file.status = 'pending'
        audio_file.task_id = None
        audio_file.transcript_text = None
        audio_file.error_message = None
        audio_file.save()
        
        # Clear any existing transcription segments
        from audioDiagnostic.models import TranscriptionSegment
        TranscriptionSegment.objects.filter(audio_file=audio_file).delete()
        
        return Response({
            'message': 'Audio file reset successfully. You can now start transcription again.',
            'project_id': project.id,
            'audio_file_id': audio_file.id,
            'status': audio_file.status
        })



class TranscriptionStatusWordsView(APIView):
    """
    Check the status of the transcribe_audio_words_task by task_id.
    """

    def get(self, request, task_id):
        from audioDiagnostic.tasks import transcribe_audio_words_task  
        result = AsyncResult(task_id)
        if not result.ready():
            return JsonResponse({"status": "processing"})
        if result.failed():
            return JsonResponse({"status": "failed", "error": str(result.result)}, status=500)
        # Task is complete
        data = result.result
        data["status"] = "complete"
        return JsonResponse(data)



class AudioFileListView(APIView):
    """
    GET: List all audio files in a project
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        from audioDiagnostic.models import AudioFile
        audio_files = AudioFile.objects.filter(project=project).order_by('created_at')
        
        audio_files_data = []
        for audio_file in audio_files:
            audio_files_data.append({
                'id': audio_file.id,
                'title': audio_file.title,
                'filename': audio_file.filename,
                'status': audio_file.status,
                'task_id': audio_file.task_id,
                'order_index': audio_file.order_index,
                'has_transcript': bool(audio_file.transcript_text),
                'original_duration': audio_file.original_duration,
                'created_at': audio_file.created_at.isoformat(),
                'updated_at': audio_file.updated_at.isoformat(),
                'file_url': audio_file.file.url if audio_file.file else None,
                'error_message': audio_file.error_message
            })
        
        return Response({
            'project_id': project.id,
            'audio_files': audio_files_data
        })



class AudioFileDetailView(APIView):
    """
    GET: Get details of a specific audio file
    DELETE: Delete an audio file and its transcription data
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        from audioDiagnostic.models import AudioFile
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        return Response({
            'id': audio_file.id,
            'title': audio_file.title,
            'filename': audio_file.filename,
            'status': audio_file.status,
            'task_id': audio_file.task_id,
            'order_index': audio_file.order_index,
            'has_transcript': bool(audio_file.transcript_text),
            'original_duration': audio_file.original_duration,
            'created_at': audio_file.created_at.isoformat(),
            'updated_at': audio_file.updated_at.isoformat(),
            'file_url': audio_file.file.url if audio_file.file else None,
            'error_message': audio_file.error_message
        })
    
    def delete(self, request, project_id, audio_file_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        from audioDiagnostic.models import AudioFile, TranscriptionSegment, TranscriptionWord
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        try:
            # Get file path for cleanup
            file_path = None
            if audio_file.file:
                file_path = audio_file.file.path
            
            filename = audio_file.filename
            
            # Delete related transcription data
            TranscriptionWord.objects.filter(audio_file=audio_file).delete()
            TranscriptionSegment.objects.filter(audio_file=audio_file).delete()
            
            # Delete the audio file record
            audio_file.delete()
            
            # Clean up physical file
            import os
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted physical file: {file_path}")
                except Exception as e:
                    logger.warning(f"Could not delete physical file {file_path}: {str(e)}")
            
            logger.info(f"Audio file '{filename}' (ID: {audio_file_id}) deleted from project {project_id} by user {request.user.username}")
            
            return Response({
                'message': f'Audio file "{filename}" and all associated data deleted successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error deleting audio file {audio_file_id}: {str(e)}")
            return Response({
                'error': f'Failed to delete audio file: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class AudioTaskStatusWordsView(APIView):
    def get(self, request, task_id):
        result = AsyncResult(task_id)
        progress = r.get(f"progress:{task_id}")
        progress = int(progress) if progress else 0
        if result.failed():
            return Response({"status": "failed", "error": str(result.result), "progress": progress}, status=500)
        if result.ready():
            return Response({**result.result, "progress": 100})
        else:
            return Response({'status': 'processing', 'progress': progress}, status=202)

