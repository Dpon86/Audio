"""
Tab 3 - Review Deletions API Views
Provides endpoints for previewing deletions with audio playback and restoration capability.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from audioDiagnostic.models import AudioFile, AudioProject, TranscriptionSegment
from audioDiagnostic.tasks.duplicate_tasks import preview_deletions_task
import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def preview_deletions(request, project_id, audio_file_id):
    """
    Generate preview audio with deletions applied.
    
    POST /api/projects/{project_id}/files/{audio_file_id}/preview-deletions/
    
    Request Body:
    {
        "segment_ids": [123, 456, 789],  // Segments to delete
        "deletion_groups": [...]          // Optional: full group data for metadata
    }
    
    Response:
    {
        "task_id": "abc123",
        "status": "processing",
        "message": "Generating preview audio..."
    }
    """
    try:
        # Verify project ownership
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Validate audio file has transcription
        if not hasattr(audio_file, 'transcription'):
            return Response(
                {'error': 'Audio file must be transcribed before generating preview'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get segment IDs from request
        segment_ids = request.data.get('segment_ids', [])
        
        if not segment_ids:
            return Response(
                {'error': 'No segments specified for deletion'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate segments belong to this audio file
        valid_segment_ids = audio_file.transcription.segments.filter(
            id__in=segment_ids
        ).values_list('id', flat=True)
        
        if len(valid_segment_ids) != len(segment_ids):
            return Response(
                {'error': 'Some segment IDs do not belong to this audio file'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Start preview generation task
        task = preview_deletions_task.delay(audio_file_id, list(segment_ids))
        
        logger.info(f"Started preview generation task {task.id} for audio file {audio_file_id}")
        
        return Response({
            'task_id': task.id,
            'status': 'processing',
            'message': 'Generating preview audio...'
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logger.error(f"Error in preview_deletions: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_deletion_preview(request, project_id, audio_file_id):
    """
    Get preview status and metadata.
    
    GET /api/projects/{project_id}/files/{audio_file_id}/deletion-preview/
    
    Response:
    {
        "status": "ready",  // none, generating, ready, failed
        "preview_audio_url": "/media/previews/preview_123_1234567890.wav",
        "original_duration": 3118.602,
        "preview_duration": 2847.134,
        "segments_deleted": 212,
        "time_saved": 271.468,
        "deletion_regions": [...],
        "kept_regions": [...]
    }
    """
    try:
        # Verify project ownership
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        response_data = {
            'status': audio_file.preview_status,
        }
        
        if audio_file.preview_status == 'ready' and audio_file.preview_metadata:
            response_data.update({
                'preview_audio_url': audio_file.preview_audio.url if audio_file.preview_audio else None,
                'original_duration': audio_file.preview_metadata.get('original_duration'),
                'preview_duration': audio_file.preview_metadata.get('preview_duration'),
                'segments_deleted': audio_file.preview_metadata.get('segments_deleted'),
                'time_saved': audio_file.preview_metadata.get('time_saved'),
                'deletion_regions': audio_file.preview_metadata.get('deletion_regions', []),
                'kept_regions': audio_file.preview_metadata.get('kept_regions', [])
            })
        elif audio_file.preview_status == 'failed':
            response_data['error'] = audio_file.error_message
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error in get_deletion_preview: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def restore_segments(request, project_id, audio_file_id):
    """
    Restore previously marked deletions.
    
    POST /api/projects/{project_id}/files/{audio_file_id}/restore-segments/
    
    Request Body:
    {
        "segment_ids": [123, 456],  // Segments to restore (unmark for deletion)
        "regenerate_preview": true  // Whether to regenerate preview audio
    }
    
    Response:
    {
        "restored_count": 2,
        "task_id": "def456",  // If regenerate_preview=true
        "message": "Segments restored successfully"
    }
    """
    try:
        # Verify project ownership
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        segment_ids_to_restore = request.data.get('segment_ids', [])
        regenerate_preview = request.data.get('regenerate_preview', False)
        
        if not segment_ids_to_restore:
            return Response(
                {'error': 'No segments specified for restoration'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get current deletion preview metadata
        if not audio_file.preview_metadata:
            return Response(
                {'error': 'No preview metadata found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get current deletion regions
        deletion_regions = audio_file.preview_metadata.get('deletion_regions', [])
        
        # Remove restored segments from deletion regions
        updated_deletions = [
            region for region in deletion_regions
            if region['segment_ids'][0] not in segment_ids_to_restore
        ]
        
        # Update metadata
        audio_file.preview_metadata['deletion_regions'] = updated_deletions
        audio_file.preview_metadata['segments_deleted'] = len(updated_deletions)
        audio_file.save()
        
        response_data = {
            'restored_count': len(segment_ids_to_restore),
            'remaining_deletions': len(updated_deletions),
            'message': 'Segments restored successfully'
        }
        
        # Optionally regenerate preview
        if regenerate_preview:
            # Get remaining segment IDs to delete
            remaining_segment_ids = [region['segment_ids'][0] for region in updated_deletions]
            
            if remaining_segment_ids:
                task = preview_deletions_task.delay(audio_file_id, remaining_segment_ids)
                response_data['task_id'] = task.id
                response_data['message'] = 'Segments restored. Regenerating preview...'
            else:
                # No deletions remaining, clear preview
                audio_file.preview_status = 'none'
                audio_file.preview_audio = None
                audio_file.preview_metadata = None
                audio_file.save()
                response_data['message'] = 'All deletions restored. Preview cleared.'
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error in restore_segments: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stream_preview_audio(request, project_id, audio_file_id):
    """
    Stream preview audio file.
    
    GET /api/projects/{project_id}/files/{audio_file_id}/preview-audio/
    
    Response: Streams the preview WAV file
    """
    try:
        # Verify project ownership
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        if not audio_file.preview_audio:
            raise Http404("Preview audio not found")
        
        # Stream the file
        response = FileResponse(audio_file.preview_audio.open('rb'), content_type='audio/wav')
        response['Content-Disposition'] = f'inline; filename="{audio_file.preview_audio.name}"'
        
        return response
        
    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in stream_preview_audio: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def cancel_preview(request, project_id, audio_file_id):
    """
    Cancel preview and clear preview data.
    
    DELETE /api/projects/{project_id}/files/{audio_file_id}/cancel-preview/
    
    Response:
    {
        "message": "Preview cancelled and cleaned up"
    }
    """
    try:
        # Verify project ownership
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Clear preview data
        if audio_file.preview_audio:
            audio_file.preview_audio.delete(save=False)
        
        audio_file.preview_audio = None
        audio_file.preview_status = 'none'
        audio_file.preview_metadata = None
        audio_file.preview_generated_at = None
        audio_file.save()
        
        return Response({
            'message': 'Preview cancelled and cleaned up'
        })
        
    except Exception as e:
        logger.error(f"Error in cancel_preview: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
