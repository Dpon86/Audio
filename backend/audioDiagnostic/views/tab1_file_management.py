"""
Tab 1: File Management Hub APIs
Handles audio file upload, list, delete, and status management
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.authentication import SessionAuthentication, TokenAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q

from ..models import AudioProject, AudioFile
from ..serializers import AudioFileDetailSerializer, AudioFileUploadSerializer


class AudioFileListView(APIView):
    """
    GET: List all audio files for a project with status and metadata
    POST: Upload new audio file(s) to project
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    
    def get(self, request, project_id):
        """Get all audio files for a project"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_files = AudioFile.objects.filter(project=project).select_related('transcription').order_by('order_index', 'created_at')
        
        serializer = AudioFileDetailSerializer(audio_files, many=True)
        
        return Response({
            'success': True,
            'audio_files': serializer.data,
            'total_count': audio_files.count()
        })
    
    def post(self, request, project_id):
        """Upload new audio file"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Get the next order_index
        last_file = AudioFile.objects.filter(project=project).order_by('-order_index').first()
        next_order = (last_file.order_index + 1) if last_file else 0
        
        # Prepare data - don't copy request.data as it contains file handles that can't be pickled
        # Instead, build a new dict with the fields we need
        uploaded_file = request.FILES.get('file')
        
        data = {
            'project': project.id,
            'order_index': next_order,
            'file': uploaded_file,
        }
        
        # Auto-generate title from filename if not provided
        if request.data.get('title'):
            data['title'] = request.data.get('title')
        elif uploaded_file:
            data['title'] = uploaded_file.name.rsplit('.', 1)[0]  # Remove extension
        
        serializer = AudioFileUploadSerializer(data=data)
        
        if serializer.is_valid():
            audio_file = serializer.save()
            detail_serializer = AudioFileDetailSerializer(audio_file)
            
            return Response({
                'success': True,
                'message': 'Audio file uploaded successfully',
                'audio_file': detail_serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class AudioFileDetailDeleteView(APIView):
    """
    GET: Get details of a single audio file
    DELETE: Delete an audio file
    PATCH: Update audio file metadata (title, order, etc.)
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Get single audio file details"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        serializer = AudioFileDetailSerializer(audio_file)
        
        return Response({
            'success': True,
            'audio_file': serializer.data
        })
    
    def delete(self, request, project_id, audio_file_id):
        """Delete an audio file and its associated data"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Store filename for response
        filename = audio_file.filename
        
        # Delete associated files
        try:
            if audio_file.file:
                audio_file.file.delete(save=False)
            if audio_file.processed_audio:
                audio_file.processed_audio.delete(save=False)
        except Exception as e:
            pass  # Continue even if file deletion fails
        
        # Delete the database record (will cascade to related objects)
        audio_file.delete()
        
        return Response({
            'success': True,
            'message': f'Audio file "{filename}" deleted successfully'
        })
    
    def patch(self, request, project_id, audio_file_id):
        """Update audio file metadata"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Allow updating: title, order_index, chapter_number, section_number
        allowed_fields = ['title', 'order_index', 'chapter_number', 'section_number']
        
        for field in allowed_fields:
            if field in request.data:
                setattr(audio_file, field, request.data[field])
        
        audio_file.save()
        
        serializer = AudioFileDetailSerializer(audio_file)
        
        return Response({
            'success': True,
            'message': 'Audio file updated successfully',
            'audio_file': serializer.data
        })


class AudioFileStatusView(APIView):
    """
    GET: Get status of an audio file (for polling during processing)
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Get current status of audio file"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        return Response({
            'success': True,
            'status': audio_file.status,
            'has_transcription': audio_file.has_transcription,
            'has_processed_audio': audio_file.has_processed_audio,
            'error_message': audio_file.error_message
        })
