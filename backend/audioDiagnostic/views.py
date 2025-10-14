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
    analyze_transcription_vs_pdf
)
from celery.result import AsyncResult
from pydub import AudioSegment

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
                'combined_transcript': project.combined_transcript,
                'duplicates_detection_completed': project.duplicates_detection_completed,
                'duplicates_detected': project.duplicates_detected,
                'duplicates_confirmed_for_deletion': project.duplicates_confirmed_for_deletion,
                # PDF file information
                'pdf_filename': project.pdf_file.name.split('/')[-1] if project.pdf_file else None
            }
        })
    
    def delete(self, request, project_id):
        """Delete project and all associated data"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        try:
            # Get all file paths before deletion for cleanup
            files_to_delete = []
            
            # PDF file
            if project.pdf_file:
                files_to_delete.append(project.pdf_file.path)
            
            # Final processed audio
            if project.final_processed_audio:
                files_to_delete.append(project.final_processed_audio.path)
            
            # Audio files and their processed versions
            for audio_file in project.audio_files.all():
                if audio_file.file:
                    files_to_delete.append(audio_file.file.path)
            
            project_title = project.title
            
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
            
            logger.info(f"Project '{project_title}' (ID: {project_id}) deleted by user {request.user.username}")
            logger.info(f"Cleaned up {len(deleted_files)} files")
            
            return Response({
                'message': f'Project "{project_title}" and all associated data deleted successfully',
                'files_deleted': len(deleted_files)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error deleting project {project_id}: {str(e)}")
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
        
        if not project.processed_audio:
            return Response({'error': 'No processed audio available'}, status=status.HTTP_404_NOT_FOUND)
        
        if not os.path.exists(project.processed_audio.path):
            return Response({'error': 'Processed audio file not found'}, status=status.HTTP_404_NOT_FOUND)
        
        response = FileResponse(
            open(project.processed_audio.path, 'rb'),
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
        
        try:
            # Extract PDF text if not already done
            if not project.pdf_text:
                from PyPDF2 import PdfReader
                reader = PdfReader(project.pdf_file.path)
                project.pdf_text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
                project.save()
            
            # Get combined transcript from all audio files
            if not project.combined_transcript:
                transcripts = []
                for audio_file in audio_files.order_by('order_index'):
                    if audio_file.transcript_text:
                        transcripts.append(audio_file.transcript_text)
                project.combined_transcript = "\n".join(transcripts)
                project.save()
            
            # Find matching PDF section
            match_result = self.find_pdf_section_match(project.pdf_text, project.combined_transcript)
            
            # Save results to project
            project.pdf_matched_section = match_result['matched_section']
            project.pdf_match_confidence = match_result['confidence']
            project.pdf_chapter_title = match_result['chapter_title']
            project.pdf_match_completed = True
            project.save()
            
            return Response({
                'success': True,
                'match_result': {
                    'matched_section': match_result['matched_section'][:500] + '...',  # Preview
                    'confidence': match_result['confidence'],
                    'chapter_title': match_result['chapter_title'],
                    'match_completed': True
                }
            })
            
        except Exception as e:
            logger.error(f"PDF matching failed: {str(e)}")
            return Response({'error': f'PDF matching failed: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def find_pdf_section_match(self, pdf_text, transcript):
        """
        Find the best matching section in PDF for the given transcript
        Returns: dict with matched_section, confidence, chapter_title
        """
        import difflib
        import re
        
        # Clean texts for comparison
        pdf_clean = ' '.join(pdf_text.lower().split())
        transcript_clean = ' '.join(transcript.lower().split())
        
        # Try to identify chapter boundaries in PDF
        chapter_pattern = r'(chapter\s+\d+|section\s+\d+|\d+\.\s+[A-Z][^.]{10,50})'
        chapters = re.split(chapter_pattern, pdf_text, flags=re.IGNORECASE)
        
        best_match = {
            'matched_section': '',
            'confidence': 0.0,
            'chapter_title': 'Unknown Section'
        }
        
        # If we found chapters, try to match against each
        if len(chapters) > 3:  # We have chapter divisions
            for i in range(1, len(chapters), 2):  # Every other element is a chapter title
                if i+1 < len(chapters):
                    chapter_title = chapters[i].strip()
                    chapter_content = chapters[i+1].strip()
                    
                    # Calculate similarity with transcript
                    chapter_clean = ' '.join(chapter_content.lower().split())
                    similarity = self.calculate_text_similarity(chapter_clean, transcript_clean)
                    
                    if similarity > best_match['confidence']:
                        best_match = {
                            'matched_section': chapter_content,
                            'confidence': similarity,
                            'chapter_title': chapter_title
                        }
        else:
            # No clear chapters, try substring matching
            transcript_start = transcript_clean[:300]  # First 300 chars
            match_pos = pdf_clean.find(transcript_start)
            
            if match_pos != -1:
                # Found match, extract surrounding context
                start_pos = max(0, match_pos - 500)
                end_pos = min(len(pdf_clean), match_pos + len(transcript_clean) + 500)
                matched_section = pdf_text[start_pos:end_pos]
                
                confidence = self.calculate_text_similarity(
                    pdf_clean[match_pos:match_pos + len(transcript_clean)], 
                    transcript_clean
                )
                
                best_match = {
                    'matched_section': matched_section,
                    'confidence': confidence,
                    'chapter_title': 'PDF Section (auto-detected)'
                }
        
        # Ensure minimum confidence
        if best_match['confidence'] < 0.1:
            # Fallback: use beginning of PDF
            best_match = {
                'matched_section': pdf_text[:2000],  # First 2000 chars
                'confidence': 0.1,
                'chapter_title': 'PDF Beginning (fallback)'
            }
        
        return best_match
    
    def calculate_text_similarity(self, text1, text2):
        """Calculate similarity between two texts using SequenceMatcher"""
        import difflib
        return difflib.SequenceMatcher(None, text1, text2).ratio()

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
        
        try:
            # Get all transcription segments
            all_segments = []
            audio_files = project.audio_files.filter(status='transcribed').order_by('order_index')
            
            for audio_file in audio_files:
                segments = TranscriptionSegment.objects.filter(audio_file=audio_file).order_by('segment_index')
                for segment in segments:
                    all_segments.append({
                        'id': segment.id,
                        'audio_file_id': audio_file.id,
                        'audio_file_title': audio_file.title,
                        'text': segment.text.strip(),
                        'start_time': segment.start_time,
                        'end_time': segment.end_time,
                        'segment_index': segment.segment_index
                    })
            
            # Detect duplicates by comparing against PDF
            duplicate_results = self.detect_duplicates_against_pdf(
                all_segments, 
                project.pdf_matched_section,
                project.combined_transcript
            )
            
            # Save results to project
            project.duplicates_detected = duplicate_results
            project.duplicates_detection_completed = True
            project.save()
            
            return Response({
                'success': True,
                'duplicate_results': duplicate_results,
                'total_segments': len(all_segments),
                'duplicates_found': len(duplicate_results['duplicates']),
                'detection_completed': True
            })
            
        except Exception as e:
            logger.error(f"Duplicate detection failed: {str(e)}")
            return Response({'error': f'Duplicate detection failed: {str(e)}'}, 
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
            
            # Enrich with audio file paths for playback
            enriched_duplicates = []
            for duplicate in duplicate_results.get('duplicates', []):
                # Get audio file info for playback
                audio_file = AudioFile.objects.get(id=duplicate['audio_file_id'])
                
                enriched_duplicate = {
                    **duplicate,
                    'audio_file_path': audio_file.file.url if audio_file.file else None,
                    'audio_file_name': audio_file.filename,
                    'duration': duplicate['end_time'] - duplicate['start_time'],
                    'preview_text': duplicate['text'][:100] + '...' if len(duplicate['text']) > 100 else duplicate['text']
                }
                enriched_duplicates.append(enriched_duplicate)
            
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
        
        if audio_file.status not in ['pending', 'failed']:
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
