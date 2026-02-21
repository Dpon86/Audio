"""
Tab 3: Single-File Duplicate Detection & Processing APIs
Detects and removes duplicates within ONE audio file at a time
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, TokenAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from ..models import AudioProject, AudioFile, Transcription, TranscriptionSegment, DuplicateGroup
from ..serializers import AudioFileDetailSerializer, DuplicateGroupSerializer
from ..tasks.duplicate_tasks import detect_duplicates_single_file_task, process_deletions_single_file_task


class SingleFileDetectDuplicatesView(APIView):
    """
    POST: Detect duplicates within a single audio file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        """Detect duplicates in a single audio file"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Check if file has transcription
        if not hasattr(audio_file, 'transcription'):
            return Response({
                'success': False,
                'error': 'Audio file must be transcribed first'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check status
        if audio_file.status not in ['transcribed', 'processed']:
            return Response({
                'success': False,
                'error': f'Cannot detect duplicates for file with status: {audio_file.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Start duplicate detection task
        try:
            task = detect_duplicates_single_file_task.delay(audio_file.id)
            
            return Response({
                'success': True,
                'message': 'Duplicate detection started',
                'task_id': task.id,
                'audio_file_id': audio_file.id
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Failed to start duplicate detection: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SingleFileDuplicatesReviewView(APIView):
    """
    GET: Get detected duplicates for review
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Get duplicate groups for review"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Get all duplicate groups for this audio file
        duplicate_groups = DuplicateGroup.objects.filter(audio_file=audio_file)
        
        if not duplicate_groups.exists():
            return Response({
                'success': True,
                'message': 'No duplicates found',
                'duplicate_groups': [],
                'total_duplicates': 0
            })
        
        # Build detailed duplicate information
        groups_data = []
        for group in duplicate_groups:
            # Get all segments in this duplicate group
            segments = TranscriptionSegment.objects.filter(
                duplicate_group_id=group.group_id,
                transcription=audio_file.transcription
            ).order_by('start_time')
            
            # Identify last occurrence (recommended to keep)
            last_segment = segments.last()
            
            segments_data = []
            for seg in segments:
                segments_data.append({
                    'id': seg.id,
                    'text': seg.text,
                    'start_time': seg.start_time,
                    'end_time': seg.end_time,
                    'duration': seg.end_time - seg.start_time,
                    'is_last_occurrence': seg.id == last_segment.id,
                    'is_duplicate': seg.is_duplicate,  # True = DELETE, False = KEEP
                    'is_kept': seg.is_kept,
                    'segment_index': seg.segment_index
                })
            
            groups_data.append({
                'group_id': group.group_id,
                'duplicate_text': group.duplicate_text,
                'occurrence_count': group.occurrence_count,
                'total_duration_seconds': group.total_duration_seconds,
                'segments': segments_data,  # Changed from 'occurrences' to 'segments'
                'occurrences': segments_data  # Keep both for backwards compatibility
            })
        
        return Response({
            'success': True,
            'duplicate_groups': groups_data,
            'total_groups': duplicate_groups.count(),
            'total_duplicates': sum(g.occurrence_count for g in duplicate_groups)
        })


class SingleFileConfirmDeletionsView(APIView):
    """
    POST: Confirm deletions and generate clean audio for single file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        """Process confirmed deletions"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Get confirmed deletions from request
        confirmed_deletions = request.data.get('confirmed_deletions', [])
        
        if not confirmed_deletions:
            return Response({
                'success': False,
                'error': 'No deletions confirmed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate deletion data structure
        if not isinstance(confirmed_deletions, list):
            return Response({
                'success': False,
                'error': 'confirmed_deletions must be a list'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract segment IDs
        segment_ids = []
        for deletion in confirmed_deletions:
            if isinstance(deletion, dict) and 'segment_id' in deletion:
                segment_ids.append(deletion['segment_id'])
            elif isinstance(deletion, (int, str)):
                segment_ids.append(int(deletion))
        
        if not segment_ids:
            return Response({
                'success': False,
                'error': 'No valid segment IDs provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update audio file status
        audio_file.status = 'processing'
        audio_file.save()
        
        # Start processing task
        try:
            task = process_deletions_single_file_task.delay(audio_file.id, segment_ids)
            
            return Response({
                'success': True,
                'message': f'Processing {len(segment_ids)} confirmed deletions',
                'task_id': task.id,
                'confirmed_count': len(segment_ids)
            })
        except Exception as e:
            audio_file.status = 'transcribed'
            audio_file.save()
            
            return Response({
                'success': False,
                'error': f'Failed to start processing: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SingleFileProcessingStatusView(APIView):
    """
    GET: Check processing status (for polling)
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Get processing status"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        response_data = {
            'success': True,
            'status': audio_file.status,
            'audio_file_id': audio_file.id,
            'filename': audio_file.filename
        }
        
        # If processing, try to get task progress
        if audio_file.status == 'processing' and audio_file.task_id:
            try:
                from celery.result import AsyncResult
                task = AsyncResult(audio_file.task_id)
                
                if task.state == 'PROGRESS':
                    response_data['progress'] = task.info.get('progress', 0)
                    response_data['message'] = task.info.get('message', 'Processing...')
                elif task.state == 'SUCCESS':
                    response_data['status'] = 'processed'
                    response_data['completed'] = True
                elif task.state == 'FAILURE':
                    response_data['status'] = 'failed'
                    response_data['error'] = str(task.info)
                else:
                    response_data['progress'] = 0
                    response_data['message'] = 'Starting processing...'
            except Exception as e:
                response_data['progress'] = 0
                response_data['message'] = 'Processing...'
        
        # If processed, include processed audio info
        if audio_file.status == 'processed' and audio_file.processed_audio:
            response_data['completed'] = True
            response_data['processed_audio_url'] = audio_file.processed_audio.url
            response_data['has_processed_audio'] = True
        
        # If failed, include error
        if audio_file.status == 'failed':
            response_data['error'] = audio_file.error_message or 'Processing failed'
            response_data['completed'] = True
        
        return Response(response_data)


class SingleFileProcessedAudioView(APIView):
    """
    GET: Download processed (clean) audio file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Download processed audio"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        if not audio_file.processed_audio:
            return Response({
                'success': False,
                'error': 'Processed audio not available'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Return file URL for download
        return Response({
            'success': True,
            'processed_audio_url': audio_file.processed_audio.url,
            'filename': f"{audio_file.filename.rsplit('.', 1)[0]}_clean.wav"
        })


class SingleFileStatisticsView(APIView):
    """
    GET: Get before/after statistics for processed file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Get processing statistics"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Get duplicate groups
        duplicate_groups = DuplicateGroup.objects.filter(audio_file=audio_file)
        
        # Get segments marked for deletion
        if hasattr(audio_file, 'transcription'):
            total_segments = audio_file.transcription.segments.count()
            deleted_segments = audio_file.transcription.segments.filter(is_kept=False).count()
            kept_segments = audio_file.transcription.segments.filter(is_kept=True).count()
            
            # Calculate time saved
            deleted_duration = sum(
                seg.end_time - seg.start_time 
                for seg in audio_file.transcription.segments.filter(is_kept=False)
            )
        else:
            total_segments = 0
            deleted_segments = 0
            kept_segments = 0
            deleted_duration = 0
        
        return Response({
            'success': True,
            'statistics': {
                'original_duration': audio_file.duration_seconds or audio_file.original_duration,
                'duplicate_groups_found': duplicate_groups.count(),
                'total_duplicates': sum(g.occurrence_count for g in duplicate_groups),
                'total_segments': total_segments,
                'segments_deleted': deleted_segments,
                'segments_kept': kept_segments,
                'duration_deleted_seconds': deleted_duration,
                'has_processed_audio': bool(audio_file.processed_audio)
            }
        })


class UpdateSegmentTimesView(APIView):
    """
    PATCH: Update start_time and end_time for a specific transcription segment
    Used when user drags region boundaries in waveform editor
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, project_id, audio_file_id, segment_id):
        """Update segment boundary times"""
        # Verify ownership and get segment
        try:
            segment = TranscriptionSegment.objects.select_related(
                'transcription__audio_file__project'
            ).get(
                id=segment_id,
                transcription__audio_file_id=audio_file_id,
                transcription__audio_file__project_id=project_id,
                transcription__audio_file__project__user=request.user
            )
        except TranscriptionSegment.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Segment not found or access denied'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get new times from request
        new_start = request.data.get('start_time')
        new_end = request.data.get('end_time')
        
        # Validate inputs
        if new_start is None and new_end is None:
            return Response({
                'success': False,
                'error': 'At least one of start_time or end_time must be provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update times
        if new_start is not None:
            try:
                segment.start_time = float(new_start)
            except (ValueError, TypeError):
                return Response({
                    'success': False,
                    'error': 'Invalid start_time value'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if new_end is not None:
            try:
                segment.end_time = float(new_end)
            except (ValueError, TypeError):
                return Response({
                    'success': False,
                    'error': 'Invalid end_time value'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate time logic
        if segment.end_time <= segment.start_time:
            return Response({
                'success': False,
                'error': 'End time must be after start time'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate minimum duration (0.1 seconds)
        if segment.end_time - segment.start_time < 0.1:
            return Response({
                'success': False,
                'error': 'Segment duration must be at least 0.1 seconds'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save changes
        segment.save()
        
        return Response({
            'success': True,
            'segment': {
                'id': segment.id,
                'start_time': segment.start_time,
                'end_time': segment.end_time,
                'duration': segment.end_time - segment.start_time,
                'text': segment.text
            }
        })


class RetranscribeProcessedAudioView(APIView):
    """
    POST: Re-transcribe processed audio for maximum accuracy
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        """Trigger re-transcription of processed audio"""
        from audioDiagnostic.tasks import retranscribe_processed_audio_task
        
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Verify processed audio exists
        if not audio_file.processed_audio:
            return Response({
                'success': False,
                'error': 'No processed audio available. Process deletions first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already re-transcribing  
        if audio_file.retranscription_status == 'processing':
            return Response({
                'success': False,
                'error': 'Re-transcription already in progress',
                'task_id': audio_file.retranscription_task_id
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Start re-transcription task
        try:
            task = retranscribe_processed_audio_task.delay(audio_file.id)
            
            return Response({
                'success': True,
                'message': 'Started re-transcription of processed audio',
                'task_id': task.id
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Failed to start re-transcription: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request, project_id, audio_file_id):
        """Get re-transcription status"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        return Response({
            'success': True,
            'retranscription_status': audio_file.retranscription_status,
            'task_id': audio_file.retranscription_task_id,
            'transcript_source': audio_file.transcript_source
        })
