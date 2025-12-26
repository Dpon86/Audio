"""
Project Views for audioDiagnostic app.
"""
from ._base import *

from ..tasks import transcribe_all_project_audio_task, process_project_duplicates_task

class ProjectListCreateView(APIView):
    """
    GET: List user's projects
    POST: Create new project
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get only projects belonging to the authenticated user
        # Optimize query with select_related for user and prefetch for audio files
        projects = AudioProject.objects.filter(user=request.user).select_related('user')
        project_data = []
        for project in projects:
            project_data.append({
                'id': project.id,
                'title': project.title,
                'status': project.status,
                'has_pdf': bool(project.pdf_file),
                'audio_files_count': project.audio_files_count,
                'processed_files_count': project.processed_files_count,
                'description': project.description,
                'total_chapters': project.total_chapters,
                'created_at': project.created_at.isoformat(),
                'updated_at': project.updated_at.isoformat(),
            })
        
        logger.info(f"Returning {len(project_data)} projects for user {request.user.username}")
        return Response({'projects': project_data})

    def post(self, request):
        serializer = ProjectCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create project for the authenticated user
        project = serializer.save()
        
        return Response({
            'project': {
                'id': project.id,
                'title': project.title,
                'status': project.status,
                'user': request.user.username
            }
        }, status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    """
    GET: Get project details including segments
    DELETE: Delete project and all associated data
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        # Optimize query with prefetch_related for audio files
        project = get_object_or_404(
            AudioProject.objects.prefetch_related('audio_files'),
            id=project_id,
            user=request.user
        )
        
        # Get audio files info
        audio_files_data = []
        for audio_file in project.audio_files.all().order_by('order_index'):
            audio_files_data.append({
                'id': audio_file.id,
                'title': audio_file.title,
                'filename': audio_file.filename,
                'status': audio_file.status,
                'order_index': audio_file.order_index,
                'has_transcript': bool(audio_file.transcript_text),
                'original_duration': audio_file.original_duration,
                'created_at': audio_file.created_at.isoformat()
            })
        
        # Get processing results if completed
        processing_result = None
        if hasattr(project, 'processing_result'):
            result = project.processing_result
            processing_result = {
                'total_segments_processed': result.total_segments_processed,
                'duplicates_removed': result.duplicates_removed,
                'words_removed': result.words_removed,
                'sentences_removed': result.sentences_removed,
                'paragraphs_removed': result.paragraphs_removed,
                'original_total_duration': result.original_total_duration,
                'final_duration': result.final_duration,
                'time_saved': result.time_saved,
                'pdf_coverage_percentage': result.pdf_coverage_percentage,
                'missing_content_count': result.missing_content_count
            }

        # Determine what actions are available based on current status
        available_actions = []
        if project.status == 'setup' and project.pdf_file and project.audio_files.exists():
            available_actions.append('transcribe')
        elif project.status == 'transcribed':
            available_actions.append('process')
        elif project.status == 'completed':
            available_actions.append('download')

        return Response({
            'project': {
                'id': project.id,
                'title': project.title,
                'status': project.status,
                'has_pdf': bool(project.pdf_file),
                'pdf_file': project.pdf_file.url if project.pdf_file else None,  # Add PDF URL
                'audio_files_count': project.audio_files.count(),
                'transcribed_files_count': project.audio_files.filter(status='transcribed').count(),
                'uploaded_files_count': project.audio_files.filter(status='uploaded').count(),
                'has_final_audio': bool(project.final_processed_audio),
                'total_duplicates_found': project.total_duplicates_found,
                'missing_content': project.missing_content,
                'error_message': project.error_message,
                'created_at': project.created_at.isoformat(),
                'updated_at': project.updated_at.isoformat(),
                'audio_files': audio_files_data,
                'processing_result': processing_result,
                'available_actions': available_actions,
                'workflow_status': {
                    'pdf_uploaded': bool(project.pdf_file),
                    'audio_files_uploaded': project.audio_files.filter(status='uploaded').exists(),
                    'transcription_complete': project.status in ['transcribed', 'processing', 'completed'],
                    'processing_complete': project.status == 'completed'
                },
                # Step-by-step workflow fields
                'pdf_match_completed': project.pdf_match_completed,
                'pdf_chapter_title': project.pdf_chapter_title,
                'pdf_match_confidence': project.pdf_match_confidence,
                'pdf_matched_section': project.pdf_matched_section,
                # Only include pdf_text if explicitly requested (can be very large)
                'pdf_text': project.pdf_text if request.GET.get('include_pdf_text') else None,
                'pdf_match_start_char': getattr(project, 'pdf_match_start_char', None),  # Boundary positions
                'pdf_match_end_char': getattr(project, 'pdf_match_end_char', None),
                'combined_transcript': project.combined_transcript,
                'duplicates_detection_completed': project.duplicates_detection_completed,
                'duplicates_detected': project.duplicates_detected,
                'duplicates_confirmed_for_deletion': project.duplicates_confirmed_for_deletion,
                # Duration statistics
                'original_audio_duration': project.original_audio_duration,
                'duration_deleted': project.duration_deleted,
                'final_audio_duration': project.final_audio_duration,
                # Final processed audio
                'final_processed_audio': project.final_processed_audio.url if project.final_processed_audio else None,
                # Clean audio transcription status
                'clean_audio_transcribed': project.clean_audio_transcribed,
                # PDF file information
                'pdf_filename': project.pdf_file.name.split('/')[-1] if project.pdf_file else None,
                # Iterative cleaning
                'parent_project_id': project.parent_project.id if project.parent_project else None,
                'iteration_number': project.iteration_number,
                'has_iterations': project.iterations.exists() if hasattr(project, 'iterations') else False
            }
        })
    
    def delete(self, request, project_id):
        """Delete project and all associated data"""
        try:
            # Get project - for dev, skip user check if no authentication
            if hasattr(request, 'user') and request.user.is_authenticated:
                project = get_object_or_404(AudioProject, id=project_id, user=request.user)
            else:
                # Development mode - allow deletion without authentication
                project = get_object_or_404(AudioProject, id=project_id)
            
            # Get all file paths before deletion for cleanup
            files_to_delete = []
            
            # PDF file
            if project.pdf_file:
                try:
                    files_to_delete.append(project.pdf_file.path)
                except Exception:
                    pass
            
            # Final processed audio
            if project.final_processed_audio:
                try:
                    files_to_delete.append(project.final_processed_audio.path)
                except Exception:
                    pass
            
            # Audio files and their processed versions
            for audio_file in project.audio_files.all():
                if audio_file.file:
                    try:
                        files_to_delete.append(audio_file.file.path)
                    except Exception:
                        pass
            
            project_title = project.title
            project_id_str = str(project_id)
            
            # Delete the project (this will cascade delete all related objects)
            project.delete()
            
            # Clean up physical files
            import os
            deleted_files = []
            for file_path in files_to_delete:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        deleted_files.append(file_path)
                except OSError as e:
                    logger.warning(f"Could not delete file {file_path}: {str(e)}")
                except PermissionError as e:
                    logger.warning(f"Permission denied deleting file {file_path}: {str(e)}")
            
            username = request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous'
            logger.info(f"Project '{project_title}' (ID: {project_id_str}) deleted by user {username}")
            logger.info(f"Cleaned up {len(deleted_files)} files")
            
            return Response({
                'message': f'Project "{project_title}" and all associated data deleted successfully',
                'files_deleted': len(deleted_files)
            }, status=status.HTTP_200_OK)
            
        except AudioProject.DoesNotExist:
            logger.error(f"Project {project_id} not found")
            return Response({
                'error': f'Project not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            logger.error(f"Invalid project ID format: {project_id}")
            return Response({
                'error': 'Invalid project ID format'
            }, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as e:
            logger.error(f"Permission error deleting project {project_id}: {str(e)}")
            return Response({
                'error': 'Insufficient permissions to delete project files'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Unexpected error deleting project {project_id}: {str(e)}", exc_info=True)
            return Response({
                'error': 'An unexpected error occurred while deleting the project'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def patch(self, request, project_id):
        """Update specific project fields (e.g., reset PDF match status, upload PDF)"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Handle PDF file upload
        pdf_file = request.FILES.get('pdf_file')
        if pdf_file:
            # Delete old PDF if it exists
            if project.pdf_file:
                try:
                    project.pdf_file.delete(save=False)
                except Exception as e:
                    logger.warning(f"Could not delete old PDF: {str(e)}")
            
            # Save new PDF
            project.pdf_file = pdf_file
            project.save()
            
            # Return success with project data including pdf_file URL
            return Response({
                'id': project.id,
                'title': project.title,
                'pdf_file': project.pdf_file.url if project.pdf_file else None,
                'message': 'PDF uploaded successfully'
            })
        
        # Get fields to update from request
        pdf_match_completed = request.data.get('pdf_match_completed')
        pdf_matched_section = request.data.get('pdf_matched_section')
        pdf_match_confidence = request.data.get('pdf_match_confidence')
        pdf_chapter_title = request.data.get('pdf_chapter_title')
        reset_pdf_text = request.data.get('reset_pdf_text')
        
        # Handle PDF text reset if requested
        if reset_pdf_text:
            project.pdf_text = None
            project.pdf_match_completed = False
            project.pdf_matched_section = None
            project.pdf_match_confidence = None
            project.pdf_chapter_title = None
        
        # Update fields if provided
        if pdf_match_completed is not None:
            project.pdf_match_completed = pdf_match_completed
        if pdf_matched_section is not None:
            project.pdf_matched_section = pdf_matched_section
        if pdf_match_confidence is not None:
            project.pdf_match_confidence = pdf_match_confidence
        if pdf_chapter_title is not None:
            project.pdf_chapter_title = pdf_chapter_title
            
        project.save()
        
        return Response({
            'message': 'Project updated successfully',
            'pdf_match_completed': project.pdf_match_completed,
            'pdf_chapter_title': project.pdf_chapter_title,
            'pdf_file': project.pdf_file.url if project.pdf_file else None
        })


class ProjectTranscriptView(APIView):
    """
    GET: Get full transcript for all audio files in the project
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        # Optimize query with prefetch_related for audio files and their segments
        project = get_object_or_404(
            AudioProject.objects.prefetch_related(
                'audio_files',
                'audio_files__segments'
            ),
            id=project_id,
            user=request.user
        )
        
        transcript_data = []
        total_segments = 0
        
        # Get transcripts for all audio files in the project
        for audio_file in project.audio_files.all().order_by('order_index'):
            segments = TranscriptionSegment.objects.filter(audio_file=audio_file).order_by('segment_index')
            
            file_transcript = {
                'audio_file_id': audio_file.id,
                'filename': audio_file.filename,
                'title': audio_file.title,
                'status': audio_file.status,
                'segments_count': segments.count(),
                'segments': []
            }
            
            for segment in segments:
                file_transcript['segments'].append({
                    'id': segment.id,
                    'text': segment.text,
                    'start_time': segment.start_time,
                    'end_time': segment.end_time,
                    'confidence_score': segment.confidence_score,
                    'is_duplicate': segment.is_duplicate,
                    'segment_index': segment.segment_index
                })
                
            total_segments += segments.count()
            transcript_data.append(file_transcript)
        
        # Get full text transcript
        full_transcript = ""
        for file_data in transcript_data:
            if file_data['segments']:
                full_transcript += f"\n\n=== {file_data['filename']} ===\n\n"
                for segment in file_data['segments']:
                    full_transcript += segment['text'] + " "
        
        return Response({
            'project_id': project.id,
            'project_title': project.title,
            'total_segments': total_segments,
            'audio_files_count': len(transcript_data),
            'full_transcript': full_transcript.strip(),
            'transcript_data': transcript_data
        })


class ProjectStatusView(APIView):
    """
    GET: Get processing status and progress
    """
    # authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    # permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id)  # Remove user filter for testing
        
        # Return project status without task tracking for now
        # The project status is updated directly by the task
        return Response({
            'status': project.status,
            'progress': 0 if project.status == 'processing' else 100,
            'message': project.error_message if project.status == 'failed' else None
        })
        
        if task_result.state == 'PENDING':
            progress = 0
        elif task_result.state == 'SUCCESS':
            progress = 100
            project.status = 'completed'
            project.save()
        elif task_result.state == 'FAILURE':
            progress = -1
            project.status = 'failed'
            project.error_message = str(task_result.result)
            project.save()
        else:
            # Get progress from Redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            progress = r.get(f"progress:{project.task_id}")
            progress = int(progress) if progress else 0
        
        response_data = {
            'status': project.status,
            'progress': progress,
            'task_state': task_result.state
        }
        
        if task_result.state == 'SUCCESS':
            response_data['result'] = task_result.result
        elif task_result.state == 'FAILURE':
            response_data['error'] = str(task_result.result)
            
        return Response(response_data)


class ProjectDownloadView(APIView):
    """
    GET: Download processed audio file
    """
    # authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    # permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id)  # Remove user filter for testing
        
        # Check for final_processed_audio first (new workflow), then fallback to processed_audio (legacy)
        audio_file = project.final_processed_audio if project.final_processed_audio else getattr(project, 'processed_audio', None)
        
        if not audio_file:
            return Response({'error': 'No processed audio available yet. Processing may still be in progress.'}, status=status.HTTP_404_NOT_FOUND)
        
        if not os.path.exists(audio_file.path):
            return Response({'error': 'Processed audio file not found on server'}, status=status.HTTP_404_NOT_FOUND)
        
        response = FileResponse(
            open(audio_file.path, 'rb'),
            as_attachment=True,
            filename=f"processed_{project.title}.wav"
        )
        return response

# ========================= NEW STEP-BY-STEP PROCESSING VIEWS =========================

