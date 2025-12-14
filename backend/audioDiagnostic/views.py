import os, json
import redis
import datetime
import tempfile
import logging
import io
logger = logging.getLogger(__name__)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication, BasicAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from django.http import JsonResponse, FileResponse, Http404, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from .models import AudioProject, AudioFile, TranscriptionSegment, TranscriptionWord
from .tasks import (
    process_audio_file_task, 
    transcribe_audio_file_task, 
    transcribe_all_project_audio_task,
    process_project_duplicates_task,
    transcribe_audio_task, 
    transcribe_audio_words_task, 
    analyze_transcription_vs_pdf,
    match_pdf_to_audio_task,
    detect_duplicates_task,
    process_confirmed_deletions_task
)
from celery.result import AsyncResult
# from pydub import AudioSegment  # Temporarily disabled for Python 3.13 compatibility

# ========================= NEW PROJECT-BASED VIEWS =========================

@method_decorator(csrf_exempt, name='dispatch')
class ProjectListCreateView(APIView):
    """
    GET: List user's projects
    POST: Create new project
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get only projects belonging to the authenticated user
        projects = AudioProject.objects.filter(user=request.user)
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
        title = request.data.get('title', '').strip()
        if not title:
            return Response({'error': 'Title is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create project for the authenticated user
        project = AudioProject.objects.create(
            user=request.user,
            title=title,
            status='setup'
        )
        
        return Response({
            'project': {
                'id': project.id,
                'title': project.title,
                'status': project.status,
                'user': request.user.username
            }
        }, status=status.HTTP_201_CREATED)

@method_decorator(csrf_exempt, name='dispatch')
class ProjectDetailView(APIView):
    """
    GET: Get project details including segments
    DELETE: Delete project and all associated data
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
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
                except Exception as e:
                    logger.warning(f"Could not delete file {file_path}: {str(e)}")
            
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
        except Exception as e:
            logger.error(f"Error deleting project {project_id}: {str(e)}", exc_info=True)
            return Response({
                'error': f'Failed to delete project: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def patch(self, request, project_id):
        """Update specific project fields (e.g., reset PDF match status)"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
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
            'pdf_chapter_title': project.pdf_chapter_title
        })

@method_decorator(csrf_exempt, name='dispatch')
class ProjectTranscriptView(APIView):
    """
    GET: Get full transcript for all audio files in the project
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
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

@method_decorator(csrf_exempt, name='dispatch')
class ProjectUploadPDFView(APIView):
    """
    POST: Upload PDF file for project
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        if 'pdf_file' not in request.FILES:
            return Response({'error': 'No PDF file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        pdf_file = request.FILES['pdf_file']
        
        # Validate file type
        if not pdf_file.name.lower().endswith('.pdf'):
            return Response({'error': 'File must be a PDF'}, status=status.HTTP_400_BAD_REQUEST)
        
        project.pdf_file = pdf_file
        project.save()
        
        return Response({
            'message': 'PDF uploaded successfully',
            'project_id': project.id,
            'pdf_filename': pdf_file.name
        })

@method_decorator(csrf_exempt, name='dispatch')
class ProjectUploadAudioView(APIView):
    """
    POST: Upload audio file for project
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        if 'audio_file' not in request.FILES:
            return Response({'error': 'No audio file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        audio_file = request.FILES['audio_file']
        
        # Validate file type
        allowed_extensions = ['.wav', '.mp3', '.m4a', '.flac', '.ogg']
        if not any(audio_file.name.lower().endswith(ext) for ext in allowed_extensions):
            return Response({'error': 'Invalid audio file format'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate title and order index for the audio file
        title = request.data.get('title', f"Audio File {project.audio_files.count() + 1}")
        order_index = project.audio_files.count()
        
        # Create AudioFile instance
        from .models import AudioFile
        audio_file_instance = AudioFile.objects.create(
            project=project,
            file=audio_file,
            filename=audio_file.name,
            title=title,
            order_index=order_index,
            status='uploaded'  # Ready for transcription
        )
        
        # Update project status if this is the first audio file
        if project.status == 'setup' and project.pdf_file:
            project.status = 'ready'  # Ready to start transcription
            project.save()
        
        return Response({
            'message': 'Audio uploaded successfully',
            'project_id': project.id,
            'audio_file_id': audio_file_instance.id,
            'audio_filename': audio_file.name,
            'title': title,
            'order_index': order_index,
            'project_status': project.status
        })

@method_decorator(csrf_exempt, name='dispatch')
class ProjectTranscribeView(APIView):
    """
    POST: Step 1-4: Transcribe ALL audio files in project with word timestamps
    This is the first phase of the new workflow
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Validate requirements  
        if not project.pdf_file:
            return Response({'error': 'PDF file required before transcription'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if project has audio files
        audio_files = project.audio_files.filter(status='uploaded')
        if not audio_files.exists():
            return Response({'error': 'No audio files ready for transcription'}, status=status.HTTP_400_BAD_REQUEST)
        
        if project.status in ['transcribing', 'processing']:
            return Response({'error': 'Project is already being processed'}, status=status.HTTP_400_BAD_REQUEST)
        
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

@method_decorator(csrf_exempt, name='dispatch')  
class ProjectProcessView(APIView):
    """
    POST: Step 5-10: Process transcribed audio files for duplicates
    This is the second phase - only works after all files are transcribed
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

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

@method_decorator(csrf_exempt, name='dispatch')
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

@method_decorator(csrf_exempt, name='dispatch')
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

@method_decorator(csrf_exempt, name='dispatch')
class ProjectMatchPDFView(APIView):
    """
    POST: Step 1 - Match audio transcript to PDF section/chapter
    Identifies which section of the PDF corresponds to the audio transcript
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Verify prerequisites
        if not project.pdf_file:
            return Response({'error': 'No PDF file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
        
        audio_files = project.audio_files.filter(status='transcribed')
        if not audio_files.exists():
            return Response({'error': 'No transcribed audio files found. Please transcribe audio first.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already in progress
        if project.status in ['matching_pdf', 'processing']:
            return Response({'error': 'PDF matching already in progress'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Start PDF matching as async Celery task to prevent timeouts
            task = match_pdf_to_audio_task.delay(project.id)
            
            # Update project status
            project.status = 'matching_pdf'
            project.save()
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Started PDF matching task {task.id} for project {project_id}")
            
            return Response({
                'success': True,
                'message': 'PDF matching started in background',
                'task_id': task.id,
                'project_id': project.id,
                'status': 'matching_pdf',
                'phase': 'pdf_matching'
            })
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to start PDF matching task for project {project_id}: {str(e)}")
            return Response({'error': f'Failed to start PDF matching: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def find_pdf_section_match(self, pdf_text, transcript):
        """
        Smart PDF-to-Audio matching using sentence-based boundaries
        Uses first few sentences and last few sentences to find start/end positions
        Returns: dict with matched_section, confidence, chapter_title
        """
        import difflib
        import re
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"Starting SENTENCE-BASED PDF matching - PDF: {len(pdf_text)} chars, Transcript: {len(transcript)} chars")
        
        # Clean and normalize texts for better matching
        def deep_clean_text(text):
            # Remove extra whitespace, normalize punctuation
            text = re.sub(r'\s+', ' ', text.lower().strip())
            text = re.sub(r'[^\w\s\.]', ' ', text)  # Keep only words and periods
            text = re.sub(r'\s+', ' ', text)
            return text
        
        # Extract sentences from transcript
        def extract_sentences(text, num_sentences=3):
            # Split by sentence endings but be flexible about transcription
            sentences = re.split(r'[.!?]+\s+', text.strip())
            sentences = [s.strip() for s in sentences if len(s.strip()) > 10]  # Min 10 chars per sentence
            return sentences
        
        pdf_clean = deep_clean_text(pdf_text)
        transcript_clean = deep_clean_text(transcript)
        
        # Get first and last sentences from transcript
        transcript_sentences = extract_sentences(transcript)
        logger.info(f"Extracted {len(transcript_sentences)} sentences from transcript")
        
        if len(transcript_sentences) < 2:
            logger.warning("Too few sentences in transcript - using fallback method")
            # Fallback to character-based chunks
            first_chunk = transcript_clean[:500]
            last_chunk = transcript_clean[-500:] if len(transcript_clean) > 500 else transcript_clean
        else:
            # Use first 3 and last 3 sentences
            num_boundary_sentences = min(3, len(transcript_sentences) // 2)
            
            first_sentences = transcript_sentences[:num_boundary_sentences]
            last_sentences = transcript_sentences[-num_boundary_sentences:]
            
            first_chunk = deep_clean_text(' '.join(first_sentences))
            last_chunk = deep_clean_text(' '.join(last_sentences))
            
            logger.info(f"Using {num_boundary_sentences} sentences for start/end detection")
            logger.info(f"First chunk: {first_chunk[:100]}...")
            logger.info(f"Last chunk: {last_chunk[:100]}...")
        
        # PHASE 1: Find START position using first sentences
        logger.info("PHASE 1: Finding START position using first sentences...")
        start_position = None
        start_method = None
        
        # Try different approaches to find the start
        search_variants = []
        
        # Variant 1: Full first chunk
        search_variants.append(("full_chunk", first_chunk))
        
        # Variant 2: Remove common words from first chunk
        first_chunk_filtered = re.sub(r'\b(the|and|of|to|a|in|is|it|you|that|he|was|for|on|are|as|with|his|they|i|at|be|this|have|from|or|one|had|by|word|but|not|what|all|were|we|when|your|can|said|there|each|which|she|do|how|their|if|so|up|out|if|about|who|get|which|go|me)\b', ' ', first_chunk)
        first_chunk_filtered = re.sub(r'\s+', ' ', first_chunk_filtered).strip()
        if len(first_chunk_filtered) > 30:
            search_variants.append(("filtered_chunk", first_chunk_filtered))
        
        # Variant 3: Key phrases from first chunk (8-word sequences)
        first_words = first_chunk.split()
        for i in range(0, min(len(first_words) - 7, 5)):  # Try first 5 possible 8-word phrases
            phrase = ' '.join(first_words[i:i+8])
            if len(phrase) > 25:
                search_variants.append((f"phrase_{i}", phrase))
        
        # Search for start position
        for variant_name, search_text in search_variants:
            if len(search_text) < 20:
                continue
                
            match_pos = pdf_clean.find(search_text)
            if match_pos != -1:
                start_position = match_pos
                start_method = variant_name
                logger.info(f"Found START at position {match_pos} using {variant_name}")
                logger.info(f"Matched text: {search_text[:80]}...")
                break
        
        # PHASE 2: Find END position using last sentences
        logger.info("PHASE 2: Finding END position using last sentences...")
        end_position = None
        end_method = None
        
        if start_position is not None:
            # Search for end position after the start
            end_search_variants = []
            
            # Variant 1: Full last chunk
            end_search_variants.append(("full_end_chunk", last_chunk))
            
            # Variant 2: Filtered last chunk
            last_chunk_filtered = re.sub(r'\b(the|and|of|to|a|in|is|it|you|that|he|was|for|on|are|as|with|his|they|i|at|be|this|have|from|or|one|had|by|word|but|not|what|all|were|we|when|your|can|said|there|each|which|she|do|how|their|if|so|up|out|if|about|who|get|which|go|me)\b', ' ', last_chunk)
            last_chunk_filtered = re.sub(r'\s+', ' ', last_chunk_filtered).strip()
            if len(last_chunk_filtered) > 30:
                end_search_variants.append(("filtered_end_chunk", last_chunk_filtered))
            
            # Variant 3: Key phrases from last chunk
            last_words = last_chunk.split()
            for i in range(max(0, len(last_words) - 15), len(last_words) - 7):  # Try last few 8-word phrases
                if i >= 0:
                    phrase = ' '.join(last_words[i:i+8])
                    if len(phrase) > 25:
                        end_search_variants.append((f"end_phrase_{i}", phrase))
            
            # Search for end position
            for variant_name, search_text in end_search_variants:
                if len(search_text) < 20:
                    continue
                
                # Look for this text AFTER the start position
                match_pos = pdf_clean.find(search_text, start_position + 100)  # Give some buffer
                if match_pos != -1:
                    end_position = match_pos + len(search_text)
                    end_method = variant_name
                    logger.info(f"Found END at position {match_pos} using {variant_name}")
                    logger.info(f"Matched text: {search_text[:80]}...")
                    break
        
        # PHASE 3: Extract the matched section
        if start_position is not None and end_position is not None and end_position > start_position:
            # SUCCESS: Found both start and end boundaries
            matched_length = end_position - start_position
            matched_section_clean = pdf_clean[start_position:end_position]
            
            # Calculate confidence
            confidence = self.calculate_comprehensive_similarity(matched_section_clean, transcript_clean)
            
            # Map back to original PDF text positions (approximate)
            char_ratio = len(pdf_text) / len(pdf_clean)
            original_start = int(start_position * char_ratio)
            original_end = int(end_position * char_ratio)
            
            # Expand slightly for context and ensure we don't go out of bounds
            context_buffer = 100
            expanded_start = max(0, original_start - context_buffer)
            expanded_end = min(len(pdf_text), original_end + context_buffer)
            
            matched_section = pdf_text[expanded_start:expanded_end]
            
            # Extract chapter title from context
            chapter_context = pdf_text[max(0, expanded_start - 800):expanded_start + 300]
            chapter_title = self.extract_chapter_title(chapter_context)
            
            coverage = matched_length / len(pdf_clean)
            
            logger.info(f"SUCCESS: COMPLETE BOUNDARY MATCH!")
            logger.info(f"- Start method: {start_method} at position {start_position}")
            logger.info(f"- End method: {end_method} at position {end_position}")
            logger.info(f"- Matched length: {matched_length} chars ({coverage*100:.1f}% of PDF)")
            logger.info(f"- Confidence: {confidence:.3f}")
            logger.info(f"- Chapter: {chapter_title}")
            
            return {
                'matched_section': matched_section,
                'confidence': confidence,
                'chapter_title': chapter_title,
                'coverage_analyzed': coverage,
                'start_position': start_position,
                'end_position': end_position,
                'match_type': 'sentence_boundary',
                'start_method': start_method,
                'end_method': end_method
            }
            
        elif start_position is not None:
            # PARTIAL: Found start but no clear end - use intelligent estimation
            logger.info("Found START boundary but not END - using intelligent estimation")
            
            # Estimate end position based on transcript length vs PDF length
            transcript_to_pdf_ratio = len(transcript_clean) / len(pdf_clean)
            estimated_length = min(
                int(len(transcript_clean) * 1.5),  # Assume PDF is 1.5x longer due to formatting
                len(pdf_clean) - start_position    # Don't exceed PDF length
            )
            
            estimated_end = start_position + estimated_length
            matched_section_clean = pdf_clean[start_position:estimated_end]
            confidence = self.calculate_comprehensive_similarity(matched_section_clean, transcript_clean)
            
            # Map back to original text
            char_ratio = len(pdf_text) / len(pdf_clean)
            original_start = int(start_position * char_ratio)
            original_end = int(estimated_end * char_ratio)
            
            expanded_start = max(0, original_start - 100)
            expanded_end = min(len(pdf_text), original_end + 100)
            
            matched_section = pdf_text[expanded_start:expanded_end]
            chapter_title = self.extract_chapter_title(pdf_text[max(0, expanded_start - 800):expanded_start + 300])
            
            coverage = estimated_length / len(pdf_clean)
            
            logger.info(f"PARTIAL MATCH from start boundary - Coverage: {coverage*100:.1f}%, Confidence: {confidence:.3f}")
            
            return {
                'matched_section': matched_section,
                'confidence': confidence,
                'chapter_title': chapter_title,
                'coverage_analyzed': coverage,
                'start_position': start_position,
                'match_type': 'start_boundary_estimated',
                'start_method': start_method
            }
        
        else:
            # FALLBACK: No clear boundaries found - use comprehensive analysis
            logger.warning("No sentence boundaries found - using comprehensive fallback")
            
            # Try to find ANY substantial match in the PDF
            best_match_pos = 0
            best_confidence = 0
            chunk_size = len(transcript_clean)
            
            # Sliding window to find best match
            step_size = max(1000, len(pdf_clean) // 20)  # Check 20 positions across PDF
            
            for pos in range(0, max(1, len(pdf_clean) - chunk_size), step_size):
                pdf_chunk = pdf_clean[pos:pos + chunk_size]
                confidence = self.calculate_comprehensive_similarity(pdf_chunk, transcript_clean)
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match_pos = pos
            
            # Use the best match found
            matched_section_clean = pdf_clean[best_match_pos:best_match_pos + chunk_size]
            
            # Map to original text
            char_ratio = len(pdf_text) / len(pdf_clean)
            original_start = int(best_match_pos * char_ratio)
            original_end = int((best_match_pos + chunk_size) * char_ratio)
            
            matched_section = pdf_text[original_start:original_end]
            chapter_title = self.extract_chapter_title(pdf_text[max(0, original_start - 800):original_start + 300])
            
            coverage = chunk_size / len(pdf_clean)
            
            logger.info(f"FALLBACK MATCH at position {best_match_pos} - Coverage: {coverage*100:.1f}%, Confidence: {best_confidence:.3f}")
            
            return {
                'matched_section': matched_section,
                'confidence': max(0.15, best_confidence),  # Ensure minimum confidence
                'chapter_title': chapter_title,
                'coverage_analyzed': coverage,
                'match_type': 'comprehensive_fallback',
                'best_match_position': best_match_pos
            }
    
    def calculate_comprehensive_similarity(self, text1, text2):
        """Comprehensive similarity for large text comparison"""
        import difflib
        import re
        
        # Method 1: Word overlap (primary method for transcription)
        words1 = set(re.findall(r'\b\w{4,}\b', text1.lower()))  # 4+ char words only
        words2 = set(re.findall(r'\b\w{4,}\b', text2.lower()))
        
        if words1 and words2:
            word_intersection = len(words1 & words2)
            word_union = len(words1 | words2)
            word_similarity = word_intersection / word_union if word_union > 0 else 0
        else:
            word_similarity = 0
        
        # Method 2: Phrase matching (6+ word sequences)
        phrases1 = []
        phrases2 = []
        
        words1_list = re.findall(r'\b\w+\b', text1.lower())
        words2_list = re.findall(r'\b\w+\b', text2.lower())
        
        # Create overlapping 6-word phrases
        for i in range(len(words1_list) - 5):
            phrases1.append(' '.join(words1_list[i:i+6]))
        for i in range(len(words2_list) - 5):
            phrases2.append(' '.join(words2_list[i:i+6]))
        
        phrases1_set = set(phrases1)
        phrases2_set = set(phrases2)
        
        if phrases1_set and phrases2_set:
            phrase_intersection = len(phrases1_set & phrases2_set)
            phrase_union = len(phrases1_set | phrases2_set)
            phrase_similarity = phrase_intersection / phrase_union if phrase_union > 0 else 0
        else:
            phrase_similarity = 0
        
        # Method 3: Character n-gram similarity (for structure)
        def get_ngrams(text, n=4):
            text_clean = re.sub(r'\s+', '', text.lower())
            return set(text_clean[i:i+n] for i in range(len(text_clean) - n + 1))
        
        ngrams1 = get_ngrams(text1)
        ngrams2 = get_ngrams(text2)
        
        if ngrams1 and ngrams2:
            ngram_intersection = len(ngrams1 & ngrams2)
            ngram_union = len(ngrams1 | ngrams2)
            ngram_similarity = ngram_intersection / ngram_union if ngram_union > 0 else 0
        else:
            ngram_similarity = 0
        
        # Weighted combination optimized for audio transcription
        combined_similarity = (
            word_similarity * 0.6 +     # 60% - word overlap (most reliable for audio)
            phrase_similarity * 0.3 +   # 30% - phrase matching (structure)
            ngram_similarity * 0.1      # 10% - character patterns
        )
        
        return combined_similarity
    
    def calculate_text_similarity(self, text1, text2):
        """Legacy method - redirect to comprehensive similarity"""
        return self.calculate_comprehensive_similarity(text1, text2)
    
    def extract_chapter_title(self, context_text):
        """Extract chapter/section title from context"""
        import re
        
        # Multiple patterns to find chapter titles
        chapter_patterns = [
            r'chapter\s+(\d+|[ivx]+)[\s\.:]*([^\n\r.]{1,100})',
            r'(\d+)\.\s+([A-Z][^\n\r.]{10,80})',  
            r'section\s+(\d+)[\s\.:]*([^\n\r.]{1,100})',
            r'^([A-Z][A-Z\s]{10,60})\s*$',  # All caps titles
            r'(Chapter\s+[A-Z][^\n\r.]{5,80})',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){2,8})\s*\n'  # Title Case
        ]
        
        for pattern in chapter_patterns:
            match = re.search(pattern, context_text, re.IGNORECASE | re.MULTILINE)
            if match:
                if len(match.groups()) >= 2:
                    # Two groups: number and title
                    return f"Chapter {match.group(1).strip()} - {match.group(2).strip()}"
                else:
                    # Single group: full title
                    return match.group(1).strip()
        
        # Fallback: look for the first meaningful sentence
        sentences = re.split(r'[.!?]\s+', context_text)
        for sentence in sentences:
            sentence = sentence.strip()
            if 20 <= len(sentence) <= 100 and not sentence.lower().startswith(('the ', 'and ', 'but ', 'however')):
                return f"Section: {sentence[:80]}..."
        
        return "PDF Beginning (auto-detected)"

@method_decorator(csrf_exempt, name='dispatch')
class ProjectRefinePDFBoundariesView(APIView):
    """
    POST: User refines the PDF match boundaries by selecting exact start and end positions
    Saves the refined boundaries for use in duplicate detection
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Verify prerequisites
        if not project.pdf_match_completed:
            return Response({'error': 'PDF matching must be completed first'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if not project.pdf_text:
            return Response({'error': 'PDF text not available'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get user-selected boundaries
            start_char = request.data.get('start_char')
            end_char = request.data.get('end_char')
            
            if start_char is None or end_char is None:
                return Response({'error': 'start_char and end_char are required'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            start_char = int(start_char)
            end_char = int(end_char)
            
            # Validate boundaries
            if start_char < 0 or end_char > len(project.pdf_text):
                return Response({'error': 'Invalid character positions'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            if start_char >= end_char:
                return Response({'error': 'Start position must be before end position'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Update project with refined boundaries
            project.pdf_match_start_char = start_char
            project.pdf_match_end_char = end_char
            
            # Extract the refined section
            refined_section = project.pdf_text[start_char:end_char]
            project.pdf_matched_section = refined_section
            
            # Recalculate confidence with refined section
            if project.combined_transcript:
                # Simple word overlap confidence
                import re
                pdf_words = set(re.findall(r'\b\w{4,}\b', refined_section.lower()))
                transcript_words = set(re.findall(r'\b\w{4,}\b', project.combined_transcript.lower()))
                
                if pdf_words and transcript_words:
                    intersection = len(pdf_words & transcript_words)
                    union = len(pdf_words | transcript_words)
                    confidence = intersection / union if union > 0 else 0
                    project.pdf_match_confidence = confidence
            
            project.save()
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"PDF boundaries refined for project {project_id}: chars {start_char}-{end_char} (length: {end_char - start_char})")
            
            return Response({
                'success': True,
                'message': 'PDF boundaries refined successfully',
                'start_char': start_char,
                'end_char': end_char,
                'section_length': end_char - start_char,
                'confidence': project.pdf_match_confidence,
                'refined_section_preview': refined_section[:500] + '...' if len(refined_section) > 500 else refined_section
            })
            
        except ValueError:
            return Response({'error': 'Invalid character position format'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to refine PDF boundaries for project {project_id}: {str(e)}")
            return Response({'error': f'Failed to refine boundaries: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class ProjectDetectDuplicatesView(APIView):
    """
    POST: Step 2 - Compare audio transcript against PDF to detect duplicates
    Returns detailed comparison with highlighted differences and duplicate segments
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Verify prerequisites
        if not project.pdf_match_completed:
            return Response({'error': 'PDF matching must be completed first'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already in progress
        if project.status in ['detecting_duplicates', 'processing']:
            return Response({'error': 'Duplicate detection already in progress'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Start duplicate detection as async Celery task to prevent timeouts
            task = detect_duplicates_task.delay(project.id)
            
            # Update project status
            project.status = 'detecting_duplicates'
            project.save()
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Started duplicate detection task {task.id} for project {project_id}")
            
            return Response({
                'success': True,
                'message': 'Duplicate detection started in background',
                'task_id': task.id,
                'project_id': project.id,
                'status': 'detecting_duplicates',
                'phase': 'duplicate_detection'
            })
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to start duplicate detection task for project {project_id}: {str(e)}")
            return Response({'error': f'Failed to start duplicate detection: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def detect_duplicates_against_pdf(self, segments, pdf_section, full_transcript):
        """
        Compare audio segments against PDF to find duplicates
        Returns detailed analysis with timestamps and highlighting
        """
        import re
        from collections import defaultdict
        
        # Normalize function for text comparison
        def normalize_text(text):
            return ' '.join(re.sub(r'[^\w\s]', '', text.lower()).split())
        
        # Group segments by normalized text
        text_groups = defaultdict(list)
        for segment in segments:
            normalized = normalize_text(segment['text'])
            if len(normalized) > 10:  # Only consider substantial segments
                text_groups[normalized].append(segment)
        
        # Find duplicates (groups with multiple occurrences)
        duplicates = []
        duplicate_groups = {}
        group_id = 0
        
        for normalized_text, occurrences in text_groups.items():
            if len(occurrences) > 1:
                # Sort by audio file order and timestamp to identify last occurrence
                sorted_occurrences = sorted(occurrences, 
                    key=lambda x: (x['audio_file_id'], x['start_time']))
                
                # Mark all but last as duplicates
                for i, segment in enumerate(sorted_occurrences):
                    is_last = (i == len(sorted_occurrences) - 1)
                    
                    duplicates.append({
                        'group_id': group_id,
                        'segment_id': segment['id'],
                        'audio_file_id': segment['audio_file_id'],
                        'audio_file_title': segment['audio_file_title'],
                        'text': segment['text'],
                        'start_time': segment['start_time'],
                        'end_time': segment['end_time'],
                        'normalized_text': normalized_text,
                        'is_last_occurrence': is_last,
                        'recommended_action': 'keep' if is_last else 'delete',
                        'occurrence_number': i + 1,
                        'total_occurrences': len(sorted_occurrences)
                    })
                
                duplicate_groups[group_id] = {
                    'normalized_text': normalized_text,
                    'original_text': sorted_occurrences[0]['text'],
                    'occurrences': len(sorted_occurrences),
                    'segments': [seg['segment_id'] for seg in sorted_occurrences]
                }
                group_id += 1
        
        # Generate text comparison with PDF
        pdf_comparison = self.compare_with_pdf(full_transcript, pdf_section)
        
        return {
            'duplicates': duplicates,
            'duplicate_groups': duplicate_groups,
            'pdf_comparison': pdf_comparison,
            'summary': {
                'total_duplicate_segments': len(duplicates),
                'unique_duplicate_groups': len(duplicate_groups),
                'segments_to_delete': len([d for d in duplicates if d['recommended_action'] == 'delete']),
                'segments_to_keep': len([d for d in duplicates if d['recommended_action'] == 'keep'])
            }
        }
    
    def compare_with_pdf(self, transcript, pdf_section):
        """
        Create side-by-side comparison highlighting differences
        """
        import difflib
        
        # Normalize texts for comparison
        transcript_lines = transcript.split('\n')
        pdf_lines = pdf_section.split('\n')
        
        # Generate unified diff
        diff = list(difflib.unified_diff(
            pdf_lines, 
            transcript_lines,
            fromfile='PDF (Reference)', 
            tofile='Audio Transcript',
            lineterm=''
        ))
        
        return {
            'pdf_text': pdf_section[:1000] + '...',  # Preview
            'transcript_text': transcript[:1000] + '...',  # Preview
            'diff_lines': diff[:50],  # First 50 diff lines
            'similarity_score': difflib.SequenceMatcher(None, pdf_section, transcript).ratio()
        }

@method_decorator(csrf_exempt, name='dispatch')
class ProjectDuplicatesReviewView(APIView):
    """
    GET: Step 3 - Get detected duplicates for interactive review
    Returns all duplicates with audio segment info for user confirmation
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Verify prerequisites
        if not project.duplicates_detection_completed:
            return Response({'error': 'Duplicate detection must be completed first'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get stored duplicate results
            duplicate_results = project.duplicates_detected or {}
            logger.info(f"Loading duplicate results for project {project_id}")
            logger.info(f"Duplicate results keys: {duplicate_results.keys()}")
            logger.info(f"Number of duplicates: {len(duplicate_results.get('duplicates', []))}")
            
            # Enrich with audio file paths for playback
            enriched_duplicates = []
            for idx, duplicate in enumerate(duplicate_results.get('duplicates', [])):
                try:
                    logger.debug(f"Processing duplicate {idx}: {type(duplicate)}")
                    logger.debug(f"Duplicate keys: {duplicate.keys() if isinstance(duplicate, dict) else 'NOT A DICT'}")
                    
                    # Get audio file info for playback
                    audio_file_id = duplicate.get('audio_file_id') if isinstance(duplicate, dict) else None
                    if not audio_file_id:
                        logger.error(f"Duplicate {idx} has no audio_file_id: {duplicate}")
                        continue
                        
                    audio_file = AudioFile.objects.get(id=audio_file_id)
                    
                    enriched_duplicate = {
                        **duplicate,
                        'audio_file_path': audio_file.file.url if audio_file.file else None,
                        'audio_file_name': audio_file.filename,
                        'duration': duplicate.get('end_time', 0) - duplicate.get('start_time', 0),
                        'preview_text': duplicate.get('text', '')[:100] + '...' if len(duplicate.get('text', '')) > 100 else duplicate.get('text', '')
                    }
                    enriched_duplicates.append(enriched_duplicate)
                except Exception as e:
                    logger.error(f"Error processing duplicate {idx}: {str(e)}", exc_info=True)
                    continue
            
            # Group duplicates by group_id for easier frontend handling
            grouped_duplicates = {}
            for duplicate in enriched_duplicates:
                group_id = duplicate['group_id']
                if group_id not in grouped_duplicates:
                    grouped_duplicates[group_id] = {
                        'group_info': duplicate_results['duplicate_groups'].get(str(group_id), {}),
                        'occurrences': []
                    }
                grouped_duplicates[group_id]['occurrences'].append(duplicate)
            
            return Response({
                'success': True,
                'duplicates': enriched_duplicates,
                'grouped_duplicates': grouped_duplicates,
                'summary': duplicate_results.get('summary', {}),
                'pdf_comparison': duplicate_results.get('pdf_comparison', {}),
                'review_ready': True
            })
            
        except Exception as e:
            logger.error(f"Duplicate review data retrieval failed: {str(e)}")
            return Response({'error': f'Failed to get duplicate review data: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class ProjectConfirmDeletionsView(APIView):
    """
    POST: Step 4 - Accept user-confirmed deletions and process final audio
    Removes confirmed duplicate segments and generates clean audio file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Get user confirmations
        confirmed_deletions = request.data.get('confirmed_deletions', [])
        
        if not confirmed_deletions:
            return Response({'error': 'No deletions confirmed'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Save user confirmations
            project.duplicates_confirmed_for_deletion = confirmed_deletions
            project.save()
            
            # Start background task to process deletions
            from .tasks import process_confirmed_deletions_task
            task = process_confirmed_deletions_task.delay(project_id, confirmed_deletions)
            
            return Response({
                'success': True,
                'message': 'Processing confirmed deletions...',
                'task_id': task.id,
                'confirmed_count': len(confirmed_deletions)
            })
            
        except Exception as e:
            logger.error(f"Deletion confirmation failed: {str(e)}")
            return Response({'error': f'Failed to process deletions: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProjectVerifyCleanupView(APIView):
    """
    POST: Step 4 - Verify clean audio against PDF section
    Compares the transcribed clean audio against the original PDF matched section
    to ensure all duplicates were removed successfully
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Check if clean audio has been transcribed
        if not project.clean_audio_transcribed:
            return Response({
                'error': 'Clean audio has not been transcribed yet. Please wait for processing to complete.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get verification transcript (is_verification=True)
            verification_segments = TranscriptionSegment.objects.filter(
                audio_file__project=project,
                is_verification=True
            ).order_by('segment_index')
            
            if not verification_segments.exists():
                return Response({
                    'error': 'Verification transcript not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Combine verification transcript
            clean_transcript = ' '.join([seg.text for seg in verification_segments])
            
            # Get original PDF section (using character positions if available)
            pdf_section = project.pdf_matched_section or ''
            if project.pdf_match_start_char and project.pdf_match_end_char and project.pdf_text:
                pdf_section = project.pdf_text[project.pdf_match_start_char:project.pdf_match_end_char]
            
            # Perform comparison analysis
            from difflib import SequenceMatcher
            
            # Calculate similarity ratio
            similarity = SequenceMatcher(None, 
                                        clean_transcript.lower().strip(), 
                                        pdf_section.lower().strip()).ratio()
            
            # Find common phrases (potential remaining duplicates)
            words_in_transcript = set(clean_transcript.lower().split())
            words_in_pdf = set(pdf_section.lower().split())
            common_words = words_in_transcript.intersection(words_in_pdf)
            
            # Check for repeated phrases in clean transcript
            transcript_sentences = clean_transcript.split('.')
            repeated_sentences = []
            seen = {}
            for sentence in transcript_sentences:
                sentence = sentence.strip().lower()
                if len(sentence) > 10:  # Ignore very short sentences
                    if sentence in seen:
                        repeated_sentences.append(sentence)
                    seen[sentence] = True
            
            # Save verification results
            verification_results = {
                'similarity_to_pdf': similarity,
                'clean_transcript_length': len(clean_transcript),
                'pdf_section_length': len(pdf_section),
                'common_words_count': len(common_words),
                'repeated_sentences_found': len(repeated_sentences),
                'repeated_sentences': repeated_sentences[:5] if repeated_sentences else [],  # Limit to first 5
                'verification_date': str(datetime.datetime.now())
            }
            
            project.verification_results = verification_results
            project.verification_completed = True
            project.save()
            
            return Response({
                'success': True,
                'clean_transcript': clean_transcript,
                'pdf_section': pdf_section,
                'verification_results': verification_results,
                'segments': [{
                    'text': seg.text,
                    'start_time': seg.start_time,
                    'end_time': seg.end_time
                } for seg in verification_segments]
            })
            
        except Exception as e:
            logger.error(f"Verification failed: {str(e)}")
            return Response({
                'error': f'Verification failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProjectValidatePDFView(APIView):
    """
    POST /api/projects/{id}/validate-against-pdf/
    Start word-by-word validation of clean transcript against PDF section
    Returns task_id for progress tracking
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id):
        try:
            project = AudioProject.objects.get(pk=project_id, user=request.user)
            
            # Validate prerequisites
            if not project.pdf_matched_section:
                return Response({
                    'error': 'PDF section not matched yet. Complete Step 2a first.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not project.duplicates_confirmed_for_deletion:
                return Response({
                    'error': 'No confirmed deletions to validate. Complete Step 2c first.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Start validation task
            from .tasks import validate_transcript_against_pdf_task
            task = validate_transcript_against_pdf_task.delay(project.id)
            
            logger.info(f"Started PDF validation task {task.id} for project {project.id}")
            
            return Response({
                'success': True,
                'task_id': task.id,
                'message': 'PDF validation started'
            })
            
        except AudioProject.DoesNotExist:
            return Response({
                'error': 'Project not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Failed to start PDF validation: {str(e)}")
            return Response({
                'error': f'Failed to start validation: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProjectValidationProgressView(APIView):
    """
    GET /api/projects/{id}/validation-progress/{task_id}/
    Check progress of PDF validation task
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, task_id):
        try:
            project = AudioProject.objects.get(pk=project_id, user=request.user)
            
            # Get task status from Celery
            from celery.result import AsyncResult
            task = AsyncResult(task_id)
            
            # Get progress from Redis
            from .utils import get_redis_connection
            r = get_redis_connection()
            progress = r.get(f"progress:{task_id}")
            progress_value = int(progress) if progress else 0
            
            response_data = {
                'task_id': task_id,
                'status': task.state,
                'progress': progress_value
            }
            
            if task.state == 'SUCCESS':
                # Task completed - return results from task (includes HTML)
                task_result = task.result
                response_data['completed'] = True
                if task_result and 'results' in task_result:
                    response_data['results'] = task_result['results']
                else:
                    # Fallback to database (without HTML)
                    project.refresh_from_db()
                    response_data['results'] = project.pdf_validation_results
                
            elif task.state == 'FAILURE':
                response_data['error'] = str(task.info)
                
            return Response(response_data)
            
        except AudioProject.DoesNotExist:
            return Response({
                'error': 'Project not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Failed to get validation progress: {str(e)}")
            return Response({
                'error': f'Failed to get progress: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProjectRedetectDuplicatesView(APIView):
    """
    POST: Step 6 - Create a NEW child project for iterative cleaning
    Copies PDF and clean audio to a fresh project, starts from Step 1
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        parent_project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Verify prerequisites
        if not parent_project.final_processed_audio:
            return Response({'error': 'Clean audio must be generated first'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Create a new child project
            from django.core.files import File
            import os
            
            child_project = AudioProject.objects.create(
                user=request.user,
                title=f"{parent_project.title} - Iteration {parent_project.iteration_number + 1}",
                parent_project=parent_project,
                iteration_number=parent_project.iteration_number + 1,
                status='setup'
            )
            
            logger.info(f"Created child project {child_project.id} from parent {parent_project.id}")
            
            # Copy PDF file - check if it exists first
            if parent_project.pdf_file:
                pdf_path = parent_project.pdf_file.path
                logger.info(f"Parent PDF path: {pdf_path}")
                logger.info(f"Parent PDF exists: {os.path.exists(pdf_path)}")
                
                if os.path.exists(pdf_path):
                    try:
                        with open(pdf_path, 'rb') as pdf:
                            child_project.pdf_file.save(
                                f"iteration_{child_project.iteration_number}_{os.path.basename(pdf_path)}",
                                File(pdf),
                                save=False  # Don't save yet
                            )
                        logger.info(f"PDF copied successfully to: {child_project.pdf_file.path}")
                    except Exception as e:
                        logger.error(f"Failed to copy PDF: {str(e)}")
                        raise
                else:
                    logger.error(f"Parent PDF file not found at: {pdf_path}")
                    raise FileNotFoundError(f"Parent PDF file not found: {pdf_path}")
                
                # Copy PDF metadata
                child_project.pdf_text = parent_project.pdf_text
                child_project.pdf_matched_section = parent_project.pdf_matched_section
                child_project.pdf_chapter_title = parent_project.pdf_chapter_title
                child_project.pdf_match_start_char = parent_project.pdf_match_start_char
                child_project.pdf_match_end_char = parent_project.pdf_match_end_char
                child_project.pdf_match_completed = True
                logger.info("PDF metadata copied")
            
            # Create single audio file from clean audio
            clean_audio_path = parent_project.final_processed_audio.path
            
            logger.info(f"Creating audio file from: {clean_audio_path}")
            logger.info(f"Clean audio exists: {os.path.exists(clean_audio_path)}")
            
            if not os.path.exists(clean_audio_path):
                raise FileNotFoundError(f"Clean audio file not found: {clean_audio_path}")
            
            audio_file = AudioFile.objects.create(
                project=child_project,
                title=f"Clean Audio - Iteration {child_project.iteration_number}",
                filename=f"iteration_{child_project.iteration_number}_{os.path.basename(clean_audio_path)}",
                order_index=0,
                status='pending'
            )
            
            logger.info(f"Created AudioFile with ID: {audio_file.id}, status: {audio_file.status}")
            
            with open(clean_audio_path, 'rb') as audio:
                audio_file.file.save(
                    f"iteration_{child_project.iteration_number}_{os.path.basename(clean_audio_path)}",
                    File(audio),
                    save=False  # Don't save yet
                )
            
            audio_file.status = 'uploaded'
            audio_file.save()
            
            logger.info(f"Audio file saved with status: {audio_file.status}, file path: {audio_file.file.path}")
            
            # Verify the audio file is queryable
            verify_audio = AudioFile.objects.filter(project=child_project, status='uploaded')
            logger.info(f"Verification: Found {verify_audio.count()} uploaded audio files in child project")
            
            child_project.status = 'ready'
            child_project.save()
            
            logger.info(f"Child project {child_project.id} setup complete - Status: {child_project.status}, Audio files: {verify_audio.count()}")
            
            return Response({
                'success': True,
                'message': 'Created new iteration project',
                'child_project_id': child_project.id,
                'iteration_number': child_project.iteration_number
            })
            
        except Exception as e:
            logger.error(f"Failed to create child project: {str(e)}")
            return Response({'error': f'Failed to create iteration project: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========================= LEGACY VIEWS (BACKWARD COMPATIBILITY) =========================



@csrf_exempt
def upload_chunk(request):
    if request.method == 'POST':
        upload_id = request.POST['upload_id']
        chunk_index = request.POST['chunk_index']
        chunk = request.FILES['chunk']

        upload_dir = os.path.join(settings.MEDIA_ROOT, 'chunks', upload_id)
        os.makedirs(upload_dir, exist_ok=True)
        chunk_path = os.path.join(upload_dir, f'chunk_{chunk_index}')
        with open(chunk_path, 'wb+') as destination:
            for chunk_part in chunk.chunks():
                destination.write(chunk_part)
        return JsonResponse({'status': 'chunk received'})
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def assemble_chunks(request):
    if request.method == 'POST':
        import datetime
        data = json.loads(request.body)
        upload_id = data['upload_id']
        filename = data['filename']
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'chunks', upload_id)
        chunk_files = sorted(
            [f for f in os.listdir(upload_dir) if f.startswith('chunk_')],
            key=lambda x: int(x.split('_')[1])
        )

        # Create Downloads directory if it doesn't exist
        downloads_dir = os.path.join(settings.MEDIA_ROOT, 'Downloads')
        os.makedirs(downloads_dir, exist_ok=True)

        # Create a timestamped filename
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(filename)
        download_filename = f"{base}_{now}{ext}"
        download_path = os.path.join(downloads_dir, download_filename)

        # Assemble the file in Downloads
        with open(download_path, 'wb') as assembled:
            for chunk_file in chunk_files:
                with open(os.path.join(upload_dir, chunk_file), 'rb') as cf:
                    assembled.write(cf.read())

        # Clean up chunks
        for chunk_file in chunk_files:
            os.remove(os.path.join(upload_dir, chunk_file))
        os.rmdir(upload_dir)

        # Build audio URL for frontend (not used for download, but for reference)
        audio_url = f"{settings.MEDIA_URL}Downloads/{download_filename}"

        # Start background processing (use download_path as input)
        task = transcribe_audio_task.delay(download_path, audio_url)

        # Return the download filename to the frontend
        return JsonResponse({'task_id': task.id, 'filename': download_filename})
    return JsonResponse({'error': 'Invalid request'}, status=400)

r = redis.Redis(host='localhost', port=6379, db=0)  # Adjust if needed

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

class AudioTaskStatusSentencesView(APIView):
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

def download_audio(request, filename):
    # Path to your Downloads folder
    downloads_dir = os.path.join(settings.BASE_DIR, "media", "Downloads")
    file_path = os.path.join(downloads_dir, filename)
    if os.path.exists(file_path):
        # You may want to set the correct content_type for your audio files
        return FileResponse(open(file_path, 'rb'), content_type='audio/wav')
    else:
        raise Http404("File not found")
    

def save_uploaded_file(uploaded_file):
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(uploaded_file.name)
    filename = f"{base}_{now}{ext}"
    save_path = os.path.join(settings.BASE_DIR, "media", "Downloads", filename)
    with open(save_path, "wb") as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)
    return filename  # Return the new filename for reference



@csrf_exempt
def cut_audio(request):
    if request.method != "POST":
        logger.error("cut_audio: Not a POST request")
        return HttpResponseBadRequest("POST only")
    try:
        logger.info("cut_audio: Received request body: %s", request.body)
        data = json.loads(request.body)
        file_name = data["fileName"]
        delete_sections = data["deleteSections"]  # list of {"start": float, "end": float}
        logger.info("cut_audio: file_name=%s", file_name)
        logger.info("cut_audio: delete_sections=%s", delete_sections)

        # Look for the file in media/Downloads/
        downloads_dir = os.path.join(settings.MEDIA_ROOT, "Downloads")
        audio_path = os.path.join(downloads_dir, file_name)
        logger.info("cut_audio: audio_path=%s", audio_path)

        if not os.path.exists(audio_path):
            logger.error("cut_audio: File not found at %s", audio_path)
            return JsonResponse({"error": f"File not found: {audio_path}"}, status=404)

        # Copy the file to a temp location before processing
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_copy:
            with open(audio_path, "rb") as src:
                temp_copy.write(src.read())
            temp_copy_path = temp_copy.name
        logger.info("cut_audio: Copied file to temp location: %s", temp_copy_path)

        # Load the copied audio file
        audio = AudioSegment.from_file(temp_copy_path)

        # Calculate keep sections
        delete_sections = sorted(delete_sections, key=lambda x: x["start"])
        keep_sections = []
        last_end = 0
        for section in delete_sections:
            if section["start"] > last_end:
                keep_sections.append((last_end, section["start"]))
            last_end = section["end"]
        if last_end < len(audio) / 1000:
            keep_sections.append((last_end, len(audio) / 1000))
        logger.info("cut_audio: keep_sections=%s", keep_sections)

        # Stitch together keep sections
        output = AudioSegment.empty()
        for start, end in keep_sections:
            logger.info("cut_audio: Adding keep section: start=%s, end=%s", start, end)
            output += audio[start * 1000:end * 1000]

        # Save to temp file and return
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            output.export(tmp.name, format="wav")
            tmp_path = tmp.name
        
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
        os.unlink(tmp_path)
        os.unlink(temp_copy_path)
        logger.info("cut_audio: Returning edited audio file")
        response = FileResponse(io.BytesIO(audio_bytes), content_type="audio/wav")
        response["Content-Disposition"] = 'attachment; filename="edited.wav"'
        return response

    except Exception as e:
        logger.error("cut_audio: Exception occurred: %s", str(e))
        return JsonResponse({"error": str(e)}, status=400)
    

#------------------------------Comparing Views ----------------

@method_decorator(csrf_exempt, name='dispatch')
class AnalyzePDFView(APIView):
    """
    POST: Accepts a PDF file and transcription data, starts analysis task.
    """
    def post(self, request):
        pdf_file = request.FILES.get('pdf')
        transcript = request.data.get('transcript', '')
        segments = request.data.get('segments', [])
        words = request.data.get('words', [])

        if not pdf_file or not transcript or not segments:
            return Response({"error": "Missing required data."}, status=status.HTTP_400_BAD_REQUEST)

        # Save PDF to temp location
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            for chunk in pdf_file.chunks():
                tmp.write(chunk)
            pdf_path = tmp.name

        task = analyze_transcription_vs_pdf.delay(pdf_path, transcript, segments, words)
        return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)

#------------------------------n8n-------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class N8NTranscribeView(APIView):
    """
    On POST, finds the latest .wav file in the specified folder and starts transcription.
    """
    FOLDER_TO_WATCH = r"C:\Users\user\Documents\GitHub\n8n\Files"  # Change as needed

    def post(self, request):
        folder = self.FOLDER_TO_WATCH
        wav_files = [f for f in os.listdir(folder) if f.lower().endswith('.wav')]
        if not wav_files:
            return Response({"error": "No .wav files found in folder."}, status=status.HTTP_404_NOT_FOUND)
        wav_files_full = [os.path.join(folder, f) for f in wav_files]
        latest_file = max(wav_files_full, key=os.path.getmtime)
        filename = os.path.basename(latest_file)
        audio_url = f"/media/Downloads/{filename}"
        downloads_dir = os.path.join(settings.MEDIA_ROOT, "Downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        dest_path = os.path.join(downloads_dir, filename)
        if latest_file != dest_path:
            with open(latest_file, "rb") as src, open(dest_path, "wb") as dst:
                dst.write(src.read())
        # Start the new transcription task
        task = transcribe_audio_words_task.delay(dest_path, audio_url)
        return Response({"task_id": task.id, "filename": filename}, status=status.HTTP_202_ACCEPTED)
    

@method_decorator(csrf_exempt, name='dispatch')
class TranscriptionStatusWordsView(APIView):
    """
    Check the status of the transcribe_audio_words_task by task_id.
    """

    def get(self, request, task_id):
        from .tasks import transcribe_audio_words_task  
        result = AsyncResult(task_id)
        if not result.ready():
            return JsonResponse({"status": "processing"})
        if result.failed():
            return JsonResponse({"status": "failed", "error": str(result.result)}, status=500)
        # Task is complete
        data = result.result
        data["status"] = "complete"
        return JsonResponse(data)


@method_decorator(csrf_exempt, name='dispatch')
class AudioFileListView(APIView):
    """
    GET: List all audio files in a project
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        from .models import AudioFile
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


@method_decorator(csrf_exempt, name='dispatch')
class AudioFileDetailView(APIView):
    """
    GET: Get details of a specific audio file
    DELETE: Delete an audio file and its transcription data
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        from .models import AudioFile
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
        from .models import AudioFile, TranscriptionSegment, TranscriptionWord
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


@method_decorator(csrf_exempt, name='dispatch')
class AudioFileProcessView(APIView):
    """
    POST: Process a specific audio file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        from .models import AudioFile
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


@method_decorator(csrf_exempt, name='dispatch')
class AudioFileStatusView(APIView):
    """
    GET: Get status of a specific audio file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        from .models import AudioFile
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Get segments for this audio file
        segments_data = []
        segments = TranscriptionSegment.objects.filter(audio_file=audio_file).order_by('start_time')
        for segment in segments:
            segments_data.append({
                'start_time': segment.start_time,
                'end_time': segment.end_time,
                'text': segment.text,
                'is_duplicate': segment.is_duplicate,
                'duplicate_reason': segment.duplicate_reason,
                'confidence': segment.confidence
            })

        return Response({
            'audio_file': {
                'id': audio_file.id,
                'filename': audio_file.filename,
                'status': audio_file.status,
                'task_id': audio_file.task_id,
                'created_at': audio_file.created_at.isoformat(),
                'updated_at': audio_file.updated_at.isoformat(),
                'has_transcription': audio_file.has_transcription,
                'has_processed_audio': bool(audio_file.processed_audio),
                'file_url': audio_file.file.url if audio_file.file else None,
                'processed_audio_url': audio_file.processed_audio.url if audio_file.processed_audio else None,
                'transcript_text': audio_file.transcript_text,
                'error_message': audio_file.error_message,
                'segments': segments_data
            }
        })


@method_decorator(csrf_exempt, name='dispatch')
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
        from .tasks import transcribe_audio_file_task
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


@method_decorator(csrf_exempt, name='dispatch')
class AudioFileRestartView(APIView):
    """
    POST: Restart transcription for an audio file (clears task and resets status)
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        from .models import AudioFile
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
        from .models import TranscriptionSegment
        TranscriptionSegment.objects.filter(audio_file=audio_file).delete()
        
        return Response({
            'message': 'Audio file reset successfully. You can now start transcription again.',
            'project_id': project.id,
            'audio_file_id': audio_file.id,
            'status': audio_file.status
        })


@method_decorator(csrf_exempt, name='dispatch')
class InfrastructureStatusView(APIView):
    """
    GET: Get Docker and Celery infrastructure status
    POST: Force shutdown infrastructure
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from .services.docker_manager import docker_celery_manager
        status = docker_celery_manager.get_status()
        return Response({
            'infrastructure_running': status['docker_running'],
            'active_tasks': status['active_tasks'],
            'task_ids': status['task_list']
        })
    
    def post(self, request):
        from .services.docker_manager import docker_celery_manager
        action = request.data.get('action', '')
        
        if action == 'force_shutdown':
            docker_celery_manager.force_shutdown()
            return Response({'message': 'Infrastructure forcefully shut down'})
        elif action == 'start':
            if docker_celery_manager.setup_infrastructure():
                return Response({'message': 'Infrastructure started successfully'})
            else:
                return Response({'error': 'Failed to start infrastructure'}, 
                              status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({'error': 'Invalid action'}, 
                          status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class TaskStatusView(APIView):
    """
    GET: Check status of background tasks to prevent frontend timeouts
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        try:
            from .utils import get_redis_connection
            
            # Get task result from Celery
            task_result = AsyncResult(task_id)
            
            # Get progress from Redis
            r = get_redis_connection()
            progress = r.get(f"progress:{task_id}")
            
            if progress is not None:
                progress = int(progress)
            else:
                progress = 0
            
            # Determine task status
            if task_result.state == 'PENDING':
                status_info = {
                    'status': 'pending',
                    'progress': progress,
                    'message': 'Task is waiting to be processed'
                }
            elif task_result.state == 'PROGRESS':
                status_info = {
                    'status': 'in_progress', 
                    'progress': progress,
                    'message': 'Task is currently running'
                }
            elif task_result.state == 'SUCCESS':
                status_info = {
                    'status': 'completed',
                    'progress': 100,
                    'result': task_result.result,
                    'message': 'Task completed successfully'
                }
            elif task_result.state == 'FAILURE':
                status_info = {
                    'status': 'failed',
                    'progress': -1,
                    'error': str(task_result.info),
                    'message': 'Task failed with an error'
                }
            else:
                # Handle other states (RETRY, REVOKED, etc.)
                status_info = {
                    'status': task_result.state.lower(),
                    'progress': progress,
                    'message': f'Task is in {task_result.state} state'
                }
            
            # Add task metadata
            status_info.update({
                'task_id': task_id,
                'task_state': task_result.state
            })
            
            return Response(status_info)
            
        except Exception as e:
            logger.error(f"Error checking task status {task_id}: {str(e)}")
            return Response({
                'status': 'error',
                'error': f'Failed to check task status: {str(e)}',
                'task_id': task_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class ProjectStatusView(APIView):
    """
    GET: Check project status and any running tasks
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        try:
            # Get project status and relevant information
            status_info = {
                'project_id': project.id,
                'project_title': project.title,
                'status': project.status,
                'pdf_match_completed': project.pdf_match_completed,
                'duplicates_detection_completed': project.duplicates_detection_completed,
                'error_message': project.error_message,
                'created_at': project.created_at,
                'updated_at': project.updated_at
            }
            
            # Add audio files status
            audio_files = project.audio_files.all()
            status_info['audio_files'] = {
                'total': audio_files.count(),
                'uploaded': audio_files.filter(status='uploaded').count(),
                'transcribed': audio_files.filter(status='transcribed').count(),
                'transcribing': audio_files.filter(status='transcribing').count(),
                'failed': audio_files.filter(status='failed').count()
            }
            
            # Add PDF information
            status_info['pdf'] = {
                'uploaded': bool(project.pdf_file),
                'filename': project.pdf_file.name if project.pdf_file else None,
                'text_extracted': bool(project.pdf_text),
                'match_completed': project.pdf_match_completed,
                'chapter_title': project.pdf_chapter_title,
                'match_confidence': project.pdf_match_confidence
            }
            
            # Add transcript information
            status_info['transcript'] = {
                'combined_available': bool(project.combined_transcript),
                'combined_length': len(project.combined_transcript) if project.combined_transcript else 0
            }
            
            # Add duplicate detection information
            status_info['duplicates'] = {
                'detection_completed': project.duplicates_detection_completed,
                'confirmed_for_deletion': project.duplicates_confirmed_for_deletion,
                'results_available': bool(project.duplicates_detected)
            }
            
            if project.duplicates_detected:
                duplicates_summary = project.duplicates_detected.get('summary', {})
                status_info['duplicates']['summary'] = duplicates_summary
            
            return Response(status_info)
            
        except Exception as e:
            logger.error(f"Error getting project status {project_id}: {str(e)}")
            return Response({
                'error': f'Failed to get project status: {str(e)}',
                'project_id': project_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
