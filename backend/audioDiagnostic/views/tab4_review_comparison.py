"""
Tab 4 - Review/Comparison API Views
Provides endpoints for project-wide comparison of processed vs original audio
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, TokenAuthentication, BasicAuthentication
from django.shortcuts import get_object_or_404
from audioDiagnostic.models import AudioFile, AudioProject, TranscriptionSegment
import logging

logger = logging.getLogger(__name__)


class ProjectComparisonView(APIView):
    """
    GET: Get project-wide comparison data for all processed files
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id):
        """Get comparison data for all files in project"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Get all processed files
        processed_files = AudioFile.objects.filter(
            project=project,
            status='processed'
        ).order_by('order_index')
        
        files_data = []
        total_time_saved = 0
        total_deletions = 0
        reviewed_count = 0
        
        for audio_file in processed_files:
            # Calculate time saved
            original_duration = audio_file.duration_seconds or audio_file.original_duration or 0
            processed_duration = audio_file.processed_duration_seconds or 0
            time_saved = original_duration - processed_duration
            
            # Count deletions
            deletion_count = 0
            if hasattr(audio_file, 'transcription'):
                deletion_count = audio_file.transcription.segments.filter(is_duplicate=True).count()
            
            # Build comparison metadata if not exists
            if not audio_file.comparison_metadata:
                comparison_metadata = {
                    'original_duration': original_duration,
                    'processed_duration': processed_duration,
                    'time_saved': time_saved,
                    'deletion_count': deletion_count,
                    'compression_ratio': (time_saved / original_duration) if original_duration > 0 else 0
                }
                audio_file.comparison_metadata = comparison_metadata
                audio_file.comparison_status = 'pending'
                audio_file.save()
            
            files_data.append({
                'id': audio_file.id,
                'filename': audio_file.filename,
                'original_duration': original_duration,
                'processed_duration': processed_duration,
                'time_saved': time_saved,
                'deletion_count': deletion_count,
                'compression_ratio': (time_saved / original_duration) if original_duration > 0 else 0,
                'comparison_status': audio_file.comparison_status,
                'reviewed_at': audio_file.reviewed_at,
            })
            
            total_time_saved += time_saved
            total_deletions += deletion_count
            
            if audio_file.comparison_status in ['reviewed', 'approved']:
                reviewed_count += 1
        
        # Project-wide statistics
        project_stats = {
            'total_files': processed_files.count(),
            'processed_files': processed_files.count(),
            'total_time_saved': total_time_saved,
            'total_deletions': total_deletions,
            'avg_compression_ratio': (total_time_saved / sum(f['original_duration'] for f in files_data)) if files_data else 0,
            'reviewed_files': reviewed_count,
        }
        
        return Response({
            'project_stats': project_stats,
            'files': files_data
        })


class FileComparisonDetailView(APIView):
    """
    GET: Get detailed comparison data for a single file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Get detailed comparison data for one file"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        if audio_file.status != 'processed':
            return Response(
                {'error': 'File must be processed first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get deletion regions
        deletion_regions = []
        if hasattr(audio_file, 'transcription'):
            deleted_segments = audio_file.transcription.segments.filter(
                is_duplicate=True
            ).order_by('start_time')
            
            for segment in deleted_segments:
                deletion_regions.append({
                    'segment_id': segment.id,
                    'start_time': segment.start_time,
                    'end_time': segment.end_time,
                    'duration': segment.end_time - segment.start_time,
                    'text': segment.text,
                })
        
        response_data = {
            'file_id': audio_file.id,
            'filename': audio_file.filename,
            'original_duration': audio_file.duration_seconds or audio_file.original_duration,
            'processed_duration': audio_file.processed_duration_seconds,
            'time_saved': (audio_file.duration_seconds or audio_file.original_duration or 0) - (audio_file.processed_duration_seconds or 0),
            'deletion_regions': deletion_regions,
            'original_audio_url': audio_file.file.url if audio_file.file else None,
            'processed_audio_url': audio_file.processed_audio.url if audio_file.processed_audio else None,
            'comparison_status': audio_file.comparison_status,
            'comparison_notes': audio_file.comparison_notes,
        }
        
        return Response(response_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_file_reviewed(request, project_id, audio_file_id):
    """
    Mark a file as reviewed
    
    POST /api/projects/{project_id}/files/{audio_file_id}/mark-reviewed/
    
    Request Body:
    {
        "notes": "Optional review notes",
        "status": "reviewed" or "approved"
    }
    """
    try:
        from django.utils import timezone
        
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        notes = request.data.get('notes', '')
        review_status = request.data.get('status', 'reviewed')
        
        audio_file.comparison_status = review_status
        audio_file.comparison_notes = notes
        audio_file.reviewed_at = timezone.now()
        audio_file.reviewed_by = request.user
        audio_file.save()
        
        return Response({
            'success': True,
            'message': f'File marked as {review_status}',
            'comparison_status': audio_file.comparison_status
        })
        
    except Exception as e:
        logger.error(f"Error marking file as reviewed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_deletion_regions(request, project_id, audio_file_id):
    """
    Get deletion regions for visualization
    
    GET /api/projects/{project_id}/files/{audio_file_id}/deletion-regions/
    """
    try:
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        deletion_regions = []
        if hasattr(audio_file, 'transcription'):
            deleted_segments = audio_file.transcription.segments.filter(
                is_duplicate=True
            ).order_by('start_time')
            
            for segment in deleted_segments:
                deletion_regions.append({
                    'id': segment.id,
                    'start': segment.start_time,
                    'end': segment.end_time,
                    'text': segment.text,
                    'duration': segment.end_time - segment.start_time,
                })
        
        return Response({
            'deletion_regions': deletion_regions,
            'total_count': len(deletion_regions)
        })
        
    except Exception as e:
        logger.error(f"Error getting deletion regions: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
