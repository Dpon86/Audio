"""
Tab 2: Single-File Transcription APIs
Handles transcribing individual audio files with word-level timestamps
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, TokenAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from ..models import AudioProject, AudioFile, Transcription
from ..serializers import TranscriptionSerializer, AudioFileDetailSerializer
from ..tasks import transcribe_single_audio_file_task


class SingleFileTranscribeView(APIView):
    """
    POST: Transcribe a single audio file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        """Transcribe a single audio file"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Check if file is in correct status
        if audio_file.status not in ['uploaded', 'transcribed', 'failed']:
            return Response({
                'success': False,
                'error': f'Cannot transcribe file with status: {audio_file.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if audio file exists
        if not audio_file.file:
            return Response({
                'success': False,
                'error': 'Audio file not found'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update status to transcribing
        audio_file.status = 'transcribing'
        audio_file.error_message = None
        audio_file.save()
        
        # Start transcription task
        try:
            task = transcribe_single_audio_file_task.delay(audio_file.id)
            audio_file.task_id = task.id
            audio_file.save()
            
            return Response({
                'success': True,
                'message': 'Transcription started',
                'task_id': task.id,
                'audio_file_id': audio_file.id
            })
        except Exception as e:
            audio_file.status = 'failed'
            audio_file.error_message = str(e)
            audio_file.save()
            
            return Response({
                'success': False,
                'error': f'Failed to start transcription: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SingleFileTranscriptionResultView(APIView):
    """
    GET: Get transcription results for a single audio file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Get transcription results"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Check if transcription exists
        if not hasattr(audio_file, 'transcription'):
            return Response({
                'success': False,
                'error': 'Transcription not found',
                'has_transcription': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        transcription = audio_file.transcription
        serializer = TranscriptionSerializer(transcription)
        
        # Get segments
        segments = transcription.segments.all().order_by('segment_index')
        segments_data = [{
            'id': seg.id,
            'text': seg.text,
            'start_time': seg.start_time,
            'end_time': seg.end_time,
            'segment_index': seg.segment_index,
            'confidence_score': seg.confidence_score
        } for seg in segments[:100]]  # Limit to first 100 for preview
        
        return Response({
            'success': True,
            'transcription': serializer.data,
            'segments': segments_data,
            'total_segments': segments.count()
        })


class SingleFileTranscriptionStatusView(APIView):
    """
    GET: Check transcription status (for polling)
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Get transcription status"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        response_data = {
            'success': True,
            'status': audio_file.status,
            'audio_file_id': audio_file.id,
            'filename': audio_file.filename
        }
        
        # If transcribing, try to get task progress
        if audio_file.status == 'transcribing' and audio_file.task_id:
            try:
                from celery.result import AsyncResult
                task = AsyncResult(audio_file.task_id)
                
                if task.state == 'PROGRESS':
                    response_data['progress'] = task.info.get('progress', 0)
                    response_data['message'] = task.info.get('message', 'Transcribing...')
                elif task.state == 'SUCCESS':
                    response_data['status'] = 'transcribed'
                    response_data['completed'] = True
                elif task.state == 'FAILURE':
                    response_data['status'] = 'failed'
                    response_data['error'] = str(task.info)
                else:
                    response_data['progress'] = 0
                    response_data['message'] = 'Starting transcription...'
            except Exception as e:
                response_data['progress'] = 0
                response_data['message'] = 'Processing...'
        
        # If transcribed, include summary
        if audio_file.status == 'transcribed' and hasattr(audio_file, 'transcription'):
            transcription = audio_file.transcription
            response_data['completed'] = True
            response_data['word_count'] = transcription.word_count
            response_data['confidence_score'] = transcription.confidence_score
            response_data['transcription_id'] = transcription.id
        
        # If failed, include error
        if audio_file.status == 'failed':
            response_data['error'] = audio_file.error_message or 'Transcription failed'
            response_data['completed'] = True
        
        return Response(response_data)


class TranscriptionDownloadView(APIView):
    """
    GET: Download transcription as text or JSON
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Download transcription"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        if not hasattr(audio_file, 'transcription'):
            return Response({
                'success': False,
                'error': 'Transcription not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        transcription = audio_file.transcription
        format_type = request.query_params.get('format', 'txt')
        
        if format_type == 'json':
            # Return JSON with segments
            segments = transcription.segments.all().order_by('segment_index')
            segments_data = [{
                'text': seg.text,
                'start_time': seg.start_time,
                'end_time': seg.end_time,
                'confidence': seg.confidence_score
            } for seg in segments]
            
            from django.http import JsonResponse
            return JsonResponse({
                'filename': audio_file.filename,
                'full_text': transcription.full_text,
                'word_count': transcription.word_count,
                'segments': segments_data
            })
        else:
            # Return plain text
            from django.http import HttpResponse
            response = HttpResponse(transcription.full_text, content_type='text/plain')
            response['Content-Disposition'] = f'attachment; filename="{audio_file.filename}_transcript.txt"'
            return response
