"""
Tab 5: PDF Comparison APIs
Compare transcription against PDF - find matching section, missing content, extra content
Allow marking sections as ignored (narrator info, chapter titles, etc.)
"""
import re
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, TokenAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from celery.result import AsyncResult

from ..models import AudioProject, AudioFile
from ..tasks.ai_pdf_comparison_task import ai_compare_transcription_to_pdf_task  # AI-powered comparison
from ..tasks.precise_pdf_comparison_task import precise_compare_transcription_to_pdf_task  # Precise word-by-word
from ..utils import get_redis_connection


class StartPDFComparisonView(APIView):
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
            task = ai_compare_transcription_to_pdf_task.delay(audio_file.id)
            
            # Save task ID to audio file
            audio_file.task_id = task.id
            audio_file.save(update_fields=['task_id'])
            
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


class StartPrecisePDFComparisonView(APIView):
    """
    POST: Start precise word-by-word PDF comparison for a single audio file
    Supports manual PDF region selection
    
    Request body:
    {
        "algorithm": "precise",  # Use precise word-by-word algorithm
        "pdf_start_char": 1000,  # Optional: starting character position in PDF
        "pdf_end_char": 5000     # Optional: ending character position in PDF
    }
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        """Start precise PDF comparison with optional region selection"""
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
        
        # Get algorithm preference
        algorithm = request.data.get('algorithm', 'ai')  # Default to AI
        pdf_start_char = request.data.get('pdf_start_char')
        pdf_end_char = request.data.get('pdf_end_char')
        transcript_start_char = request.data.get('transcript_start_char')
        transcript_end_char = request.data.get('transcript_end_char')
        
        # Start appropriate comparison task
        try:
            if algorithm == 'precise':
                task = precise_compare_transcription_to_pdf_task.delay(
                    audio_file.id,
                    pdf_start_char=pdf_start_char,
                    pdf_end_char=pdf_end_char,
                    transcript_start_char=transcript_start_char,
                    transcript_end_char=transcript_end_char
                )
                message = 'Precise word-by-word PDF comparison started'
            else:
                task = ai_compare_transcription_to_pdf_task.delay(audio_file.id)
                message = 'AI-powered PDF comparison started'
            
            # Save task ID to audio file
            audio_file.task_id = task.id
            audio_file.save(update_fields=['task_id'])
            
            return Response({
                'success': True,
                'message': message,
                'task_id': task.id,
                'audio_file_id': audio_file.id,
                'algorithm': algorithm,
                'pdf_region': {
                    'start_char': pdf_start_char,
                    'end_char': pdf_end_char,
                    'manually_selected': pdf_start_char is not None or pdf_end_char is not None
                },
                'transcript_region': {
                    'start_char': transcript_start_char,
                    'end_char': transcript_end_char,
                    'manually_selected': transcript_start_char is not None or transcript_end_char is not None
                }
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Failed to start PDF comparison: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetPDFTextView(APIView):
    """
    GET: Get PDF text content for manual region selection
    Returns the full PDF text so frontend can display and allow user to select region
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def clean_pdf_text(self, text, page_num):
        """
        Remove headers, footers, and narrator instructions from PDF page text
        
        Common patterns to remove:
        - "An Improbable Scheme" + number (odd pages)
        - Number + "LAURA BEERS" (even pages)
        - Standalone page numbers
        - Narrator instructions in parentheses
        - "Dreamscape presents:" etc.
        """
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # Skip empty lines at start/end
            if not line_stripped:
                cleaned_lines.append(line)
                continue
            
            # Pattern 1: "An Improbable Scheme" followed by optional number
            if re.match(r'^An Improbable Scheme\s*\d*$', line_stripped, re.IGNORECASE):
                continue
            
            # Pattern 2: Number followed by "LAURA BEERS"
            if re.match(r'^\d+\s*LAURA BEERS$', line_stripped, re.IGNORECASE):
                continue
            
            # Pattern 3: Just "LAURA BEERS"
            if re.match(r'^LAURA BEERS$', line_stripped, re.IGNORECASE):
                continue
            
            # Pattern 4: Just "An Improbable Scheme"
            if re.match(r'^An Improbable Scheme$', line_stripped, re.IGNORECASE):
                continue
            
            # Pattern 5: Standalone page numbers (single line with just digits)
            if re.match(r'^\d+$', line_stripped) and len(line_stripped) <= 4:
                continue
            
            # Pattern 6: Narrator instructions (text in parentheses with colons)
            if re.match(r'^\([^)]*:.*\)$', line_stripped):
                continue
            
            # Pattern 7: "Dreamscape presents:" or similar publisher text
            if re.match(r'^Dreamscape presents:', line_stripped, re.IGNORECASE):
                continue
            
            # Pattern 8: "Narrated by" lines
            if re.match(r'^Narrated by', line_stripped, re.IGNORECASE):
                continue
            
            # Remove inline narrator instructions from the line
            # e.g., "(Marian : Please add 3 seconds of room tone before beginning) Rest of text"
            line_cleaned = re.sub(r'\([^)]*:\s*[^)]+\)\s*', '', line)
            
            if line_cleaned.strip():
                cleaned_lines.append(line_cleaned)
        
        return '\n'.join(cleaned_lines)
    
    def get(self, request, project_id):
        """Get PDF text content with headers/footers removed"""
        from PyPDF2 import PdfReader
        
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Check if project has PDF
        if not project.pdf_file:
            return Response({
                'success': False,
                'error': 'Project does not have a PDF file'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Extract and clean PDF text
            reader = PdfReader(project.pdf_file.path)
            
            # Extract text page by page and clean headers/footers
            cleaned_pages = []
            page_breaks = []
            char_count = 0
            
            for i, page in enumerate(reader.pages):
                raw_text = page.extract_text() or ""
                
                # Clean headers and footers
                cleaned_text = self.clean_pdf_text(raw_text, i + 1)
                
                # Remove excessive blank lines
                cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
                cleaned_text = cleaned_text.strip()
                
                if cleaned_text:
                    cleaned_pages.append(cleaned_text)
                    
                    # Track page breaks
                    page_breaks.append({
                        'page_num': i + 1,
                        'start_char': char_count,
                        'end_char': char_count + len(cleaned_text),
                        'preview': cleaned_text[:200] if cleaned_text else '(blank page)'
                    })
                    
                    char_count += len(cleaned_text) + 1  # +1 for newline between pages
            
            # Join all cleaned pages
            pdf_text = '\n'.join(cleaned_pages)
            
            # Save cleaned text if not already saved
            if not project.pdf_text or len(project.pdf_text) != len(pdf_text):
                project.pdf_text = pdf_text
                project.save(update_fields=['pdf_text'])
            
            # Split into sentences for better selection UI
            sentence_pattern = r'([^.!?]+[.!?]+)'
            sentences = re.findall(sentence_pattern, pdf_text)
            
            # Build sentence map with character positions
            sentence_map = []
            current_pos = 0
            
            for sentence in sentences:
                sentence_text = sentence.strip()
                if sentence_text:
                    # Find position in original text
                    pos = pdf_text.find(sentence_text, current_pos)
                    if pos != -1:
                        sentence_map.append({
                            'text': sentence_text,
                            'start_char': pos,
                            'end_char': pos + len(sentence_text),
                            'words': len(sentence_text.split())
                        })
                        current_pos = pos + len(sentence_text)
            
            return Response({
                'success': True,
                'pdf_text': pdf_text,
                'total_chars': len(pdf_text),
                'total_pages': len(page_breaks),
                'page_breaks': page_breaks,
                'sentences': sentence_map[:500],  # Limit to first 500 sentences for performance
                'total_sentences': len(sentence_map),
                'pdf_filename': project.pdf_file.name
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Failed to read PDF: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PDFComparisonResultView(APIView):
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
        
        results = audio_file.pdf_comparison_results or {}
        
        return Response({
            'success': True,
            'has_results': True,
            'audio_file': {
                'id': audio_file.id,
                'filename': audio_file.filename,
                'title': audio_file.title
            },
            'match_result': results.get('match_result', {}),
            'missing_content': results.get('missing_content', []),
            'extra_content': results.get('extra_content', []),
            'statistics': results.get('statistics', {}),
            'ignored_sections': audio_file.pdf_ignored_sections or []
        })


class PDFComparisonStatusView(APIView):
    """
    GET: Check PDF comparison status (for polling)
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Get comparison task status and progress"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        response_data = {
            'success': True,
            'audio_file_id': audio_file.id,
            'has_comparison': audio_file.pdf_comparison_completed
        }
        
        # If there's a task ID, check progress
        if audio_file.task_id:
            try:
                # Check Redis for progress
                r = get_redis_connection()
                progress = r.get(f"progress:{audio_file.task_id}")
                
                if progress:
                    progress = int(progress)
                    if progress == 100:
                        response_data['completed'] = True
                        response_data['progress'] = 100
                    elif progress == -1:
                        response_data['error'] = 'Comparison failed'
                        response_data['completed'] = True
                    else:
                        response_data['progress'] = progress
                        response_data['message'] = 'Comparing transcription to PDF...'
                        response_data['completed'] = False
                else:
                    # No progress info, check Celery task
                    task = AsyncResult(audio_file.task_id)
                    
                    if task.state == 'SUCCESS':
                        response_data['completed'] = True
                        response_data['progress'] = 100
                    elif task.state == 'FAILURE':
                        response_data['error'] = str(task.info)
                        response_data['completed'] = True
                    elif task.state == 'PENDING':
                        response_data['progress'] = 0
                        response_data['message'] = 'Starting comparison...'
                        response_data['completed'] = False
                    else:
                        response_data['progress'] = 50
                        response_data['message'] = 'Comparing...'
                        response_data['completed'] = False
                        
            except Exception as e:
                response_data['progress'] = 0
                response_data['message'] = 'Checking status...'
                response_data['completed'] = False
        elif audio_file.pdf_comparison_completed:
            # Comparison already done
            response_data['completed'] = True
            response_data['progress'] = 100
        else:
            response_data['completed'] = False
            response_data['progress'] = 0
        
        return Response(response_data)


class SideBySideComparisonView(APIView):
    """
    GET: Get side-by-side comparison of transcription vs PDF
    Shows matching sections, missing content, extra content in a formatted view
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, audio_file_id):
        """Get side-by-side comparison"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Check if comparison has been done
        if not audio_file.pdf_comparison_completed:
            return Response({
                'success': False,
                'error': 'PDF comparison not yet performed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        results = audio_file.pdf_comparison_results or {}
        match_result = results.get('match_result', {})
        
        # Get texts
        transcription_text = audio_file.transcript_text
        pdf_section = match_result.get('matched_section', '')
        
        # Generate diff segments for side-by-side display
        from difflib import SequenceMatcher
        matcher = SequenceMatcher(None, transcription_text, pdf_section)
        
        # Get matching blocks
        matches = matcher.get_matching_blocks()
        
        # Build side-by-side segments
        segments = []
        trans_pos = 0
        pdf_pos = 0
        
        for match in matches:
            trans_start, pdf_start, size = match.a, match.b, match.size
            
            # Add unmatched transcription segment (extra content)
            if trans_pos < trans_start:
                segments.append({
                    'type': 'extra',  # In transcription but not in PDF
                    'transcription_text': transcription_text[trans_pos:trans_start],
                    'pdf_text': '',
                    'match_type': 'transcription_only'
                })
            
            # Add unmatched PDF segment (missing content)
            if pdf_pos < pdf_start:
                segments.append({
                    'type': 'missing',  # In PDF but not in transcription
                    'transcription_text': '',
                    'pdf_text': pdf_section[pdf_pos:pdf_start],
                    'match_type': 'pdf_only'
                })
            
            # Add matched segment
            if size > 0:
                segments.append({
                    'type': 'match',
                    'transcription_text': transcription_text[trans_start:trans_start + size],
                    'pdf_text': pdf_section[pdf_start:pdf_start + size],
                    'match_type': 'exact_match'
                })
            
            trans_pos = trans_start + size
            pdf_pos = pdf_start + size
        
        return Response({
            'success': True,
            'segments': segments,
            'statistics': results.get('statistics', {}),
            'match_confidence': match_result.get('confidence', 0),
            'ignored_sections': audio_file.pdf_ignored_sections or []
        })


class MarkIgnoredSectionsView(APIView):
    """
    POST: Mark sections of the transcription to ignore in comparison
    (e.g., "Narrated by Jane Doe", chapter titles, etc.)
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        """Mark sections to ignore"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Get ignored sections from request
        ignored_sections = request.data.get('ignored_sections', [])
        
        if not isinstance(ignored_sections, list):
            return Response({
                'success': False,
                'error': 'ignored_sections must be a list'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate each ignored section
        for section in ignored_sections:
            if not isinstance(section, dict) or 'text' not in section:
                return Response({
                    'success': False,
                    'error': 'Each ignored section must have a "text" field'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save ignored sections
        audio_file.pdf_ignored_sections = ignored_sections
        audio_file.save(update_fields=['pdf_ignored_sections'])
        
        # If comparison was already done, re-run it with ignored sections
        if audio_file.pdf_comparison_completed and request.data.get('recompare', True):
            try:
                task = ai_compare_transcription_to_pdf_task.delay(audio_file.id)
                audio_file.task_id = task.id
                audio_file.save(update_fields=['task_id'])
                
                return Response({
                    'success': True,
                    'message': 'Ignored sections saved, recomparing...',
                    'ignored_sections': ignored_sections,
                    'task_id': task.id
                })
            except Exception as e:
                return Response({
                    'success': False,
                    'error': f'Sections saved but recomparison failed: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': True,
            'message': 'Ignored sections saved',
            'ignored_sections': ignored_sections
        })
    
    def get(self, request, project_id, audio_file_id):
        """Get current ignored sections"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        return Response({
            'success': True,
            'ignored_sections': audio_file.pdf_ignored_sections or []
        })


class ResetPDFComparisonView(APIView):
    """
    POST: Reset PDF comparison results and start fresh
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        """Reset comparison results"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        # Clear comparison results
        audio_file.pdf_comparison_results = None
        audio_file.pdf_comparison_completed = False
        audio_file.pdf_ignored_sections = None
        audio_file.task_id = None
        audio_file.save(update_fields=[
            'pdf_comparison_results',
            'pdf_comparison_completed',
            'pdf_ignored_sections',
            'task_id'
        ])
        
        return Response({
            'success': True,
            'message': 'PDF comparison reset successfully'
        })


class MarkContentForDeletionView(APIView):
    """
    POST: Mark extra content for deletion based on timestamps
    Used when user wants to remove narrator info, chapter titles, etc. found by PDF comparison
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, project_id, audio_file_id):
        """Mark segments for deletion based on time range"""
        from ..models import TranscriptionSegment
        
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        audio_file = get_object_or_404(AudioFile, id=audio_file_id, project=project)
        
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')
        timestamps = request.data.get('timestamps', [])
        
        if start_time is None or end_time is None:
            return Response({
                'success': False,
                'error': 'start_time and end_time are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if audio file has transcription
        if not hasattr(audio_file, 'transcription'):
            return Response({
                'success': False,
                'error': 'Audio file must be transcribed first'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Find segments in the time range
            if timestamps:
                # Use specific segment IDs if provided
                segment_ids = [ts['segment_id'] for ts in timestamps if 'segment_id' in ts]
                segments = TranscriptionSegment.objects.filter(
                    audio_file=audio_file,
                    id__in=segment_ids
                )
            else:
                # Find segments overlapping the time range
                segments = TranscriptionSegment.objects.filter(
                    audio_file=audio_file,
                    start_time__lte=end_time,
                    end_time__gte=start_time
                )
            
            # Mark segments for deletion (is_kept=False)
            marked_count = segments.update(is_kept=False)
            
            return Response({
                'success': True,
                'message': f'Marked {marked_count} segment(s) for deletion',
                'segments_marked': marked_count
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Failed to mark segments for deletion: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
