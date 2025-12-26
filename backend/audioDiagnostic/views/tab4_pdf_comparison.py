"""
Tab 5: PDF Comparison APIs (Previously Tab 4)
Compare transcription against PDF - find matching section, missing content, extra content
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, TokenAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from celery.result import AsyncResult

from ..models import AudioProject, AudioFile
from ..tasks.compare_pdf_task import compare_transcription_to_pdf_task


class SingleTranscriptionPDFCompareView(APIView):
    """
    POST: Start PDF comparison for a single audio file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        """Start PDF comparison for audio file's transcription"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Check if project has PDF
        if not project.pdf_file:
            return Response({
                'success': False,
                'error': 'Project does not have a PDF file'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if audio file has transcription
        if not audio_file.transcript_text:
            return Response({
                'success': False,
                'error': 'Audio file must be transcribed first'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Start comparison task
        try:
            task = compare_transcription_to_pdf_task.delay(audio_file.id)
            
            return Response({
                'success': True,
                'message': 'PDF comparison started',
                'task_id': task.id,
                'audio_file_id': audio_file.id
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Failed to start PDF comparison: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SingleTranscriptionPDFResultView(APIView):
    """
    GET: Get PDF comparison results for a single audio file
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Get PDF comparison results"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Check if comparison has been done
        if not audio_file.pdf_comparison_completed:
            return Response({
                'success': False,
                'message': 'No PDF comparison results available',
                'has_results': False
            })
        
        return Response({
            'success': True,
            'has_results': True,
            'pdf_match_percentage': transcription.pdf_match_percentage,
            'validation_status': transcription.pdf_validation_status,
            'validation_result': validation_result,
            'transcription': TranscriptionSerializer(transcription).data
        })


class SingleTranscriptionPDFStatusView(APIView):
    """
    GET: Check PDF comparison status (for polling)
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Get comparison status"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        if not hasattr(audio_file, 'transcription'):
            return Response({
                'success': False,
                'error': 'Audio file has no transcription'
            }, status=status.HTTP_404_NOT_FOUND)
        
        transcription = audio_file.transcription
        
        response_data = {
            'success': True,
            'transcription_id': transcription.id,
            'has_comparison': bool(transcription.pdf_validation_status)
        }
        
        # If there's a task ID, check progress
        if audio_file.task_id:
            try:
                from celery.result import AsyncResult
                task = AsyncResult(audio_file.task_id)
                
                if task.state == 'PROGRESS':
                    response_data['progress'] = task.info.get('progress', 0)
                    response_data['message'] = task.info.get('message', 'Comparing...')
                    response_data['completed'] = False
                elif task.state == 'SUCCESS':
                    response_data['completed'] = True
                    response_data['pdf_match_percentage'] = transcription.pdf_match_percentage
                    response_data['validation_status'] = transcription.pdf_validation_status
                elif task.state == 'FAILURE':
                    response_data['error'] = str(task.info)
                    response_data['completed'] = True
                else:
                    response_data['progress'] = 0
                    response_data['message'] = 'Starting comparison...'
                    response_data['completed'] = False
            except Exception as e:
                response_data['progress'] = 0
                response_data['message'] = 'Comparing...'
                response_data['completed'] = False
        elif transcription.pdf_validation_status:
            # Comparison already done
            response_data['completed'] = True
            response_data['pdf_match_percentage'] = transcription.pdf_match_percentage
            response_data['validation_status'] = transcription.pdf_validation_status
        
        return Response(response_data)


class SingleTranscriptionSideBySideView(APIView):
    """
    GET: Get side-by-side comparison of transcription vs PDF
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Get side-by-side comparison"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        if not hasattr(audio_file, 'transcription'):
            return Response({
                'success': False,
                'error': 'Audio file has no transcription'
            }, status=status.HTTP_404_NOT_FOUND)
        
        transcription = audio_file.transcription
        
        # Check if comparison has been done
        if not transcription.pdf_validation_result:
            return Response({
                'success': False,
                'error': 'PDF comparison not yet performed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Parse validation result
        validation_result = transcription.pdf_validation_result
        if isinstance(validation_result, str):
            import json
            try:
                validation_result = json.loads(validation_result)
            except:
                validation_result = {}
        
        # Extract PDF text for comparison
        pdf_text = validation_result.get('pdf_text', '')
        transcription_text = transcription.full_text
        
        # Generate diff or alignment data
        from difflib import SequenceMatcher
        matcher = SequenceMatcher(None, transcription_text, pdf_text)
        
        # Get matching blocks
        matches = matcher.get_matching_blocks()
        
        # Build side-by-side segments
        segments = []
        transcription_pos = 0
        pdf_pos = 0
        
        for match in matches:
            trans_start, pdf_start, size = match.a, match.b, match.size
            
            # Add unmatched transcription segment (if any)
            if transcription_pos < trans_start:
                segments.append({
                    'type': 'transcription_only',
                    'transcription_text': transcription_text[transcription_pos:trans_start],
                    'pdf_text': ''
                })
            
            # Add unmatched PDF segment (if any)
            if pdf_pos < pdf_start:
                segments.append({
                    'type': 'pdf_only',
                    'transcription_text': '',
                    'pdf_text': pdf_text[pdf_pos:pdf_start]
                })
            
            # Add matched segment
            if size > 0:
                segments.append({
                    'type': 'match',
                    'transcription_text': transcription_text[trans_start:trans_start + size],
                    'pdf_text': pdf_text[pdf_start:pdf_start + size]
                })
            
            transcription_pos = trans_start + size
            pdf_pos = pdf_start + size
        
        return Response({
            'success': True,
            'pdf_match_percentage': transcription.pdf_match_percentage,
            'validation_status': transcription.pdf_validation_status,
            'segments': segments,
            'statistics': {
                'transcription_length': len(transcription_text),
                'pdf_length': len(pdf_text),
                'matched_blocks': len([s for s in segments if s['type'] == 'match']),
                'transcription_only_blocks': len([s for s in segments if s['type'] == 'transcription_only']),
                'pdf_only_blocks': len([s for s in segments if s['type'] == 'pdf_only'])
            }
        })


class SingleTranscriptionRetryComparisonView(APIView):
    """
    POST: Retry PDF comparison with different settings
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        """Retry comparison with custom settings"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        if not project.pdf_file:
            return Response({
                'success': False,
                'error': 'Project does not have a PDF file'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not hasattr(audio_file, 'transcription'):
            return Response({
                'success': False,
                'error': 'Audio file must be transcribed first'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        transcription = audio_file.transcription
        
        # Get custom settings from request
        custom_settings = {
            'similarity_threshold': request.data.get('similarity_threshold', 0.8),
            'use_processed': request.data.get('use_processed', False),  # Use processed audio transcription if available
            'pdf_page_range': request.data.get('pdf_page_range', None)  # Optional: [start_page, end_page]
        }
        
        # Start comparison task with custom settings
        try:
            task = compare_transcription_to_pdf_task.delay(
                transcription.id, 
                project.id,
                custom_settings=custom_settings
            )
            
            return Response({
                'success': True,
                'message': 'PDF comparison retry started',
                'task_id': task.id,
                'settings': custom_settings
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Failed to start PDF comparison: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
