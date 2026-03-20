"""
Upload Views for audioDiagnostic app.
"""
from ._base import *
from rest_framework.parsers import JSONParser
from pydub import AudioSegment

class ProjectUploadPDFView(APIView):
    """
    POST: Upload PDF file for project
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [UploadRateThrottle]
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


class ProjectUploadAudioView(APIView):
    """
    POST: Upload audio file for project
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [UploadRateThrottle]
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
        from audioDiagnostic.models import AudioFile
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


class BulkUploadWithTranscriptionView(APIView):
    """
    POST: Upload audio file with pre-computed transcription from client-side processing.
    
    This endpoint is designed for workflows where transcription is performed locally
    in the browser (e.g., using Whisper.js) but server-side assembly is needed.
    
    Request format:
    - audio_file: The audio file (multipart/form-data)
    - transcription_data: JSON string or object containing transcription segments
    - order_index: (optional) Order index for the file
    - title: (optional) Title for the audio file
    
    Transcription data format:
    [
        {
            "text": "Segment text",
            "start": 0.0,
            "end": 2.5,
            "confidence": 0.95,
            "words": [  # Optional
                {"word": "text", "start": 0.0, "end": 0.3, "confidence": 0.96},
                ...
            ]
        },
        ...
    ]
    """
    authentication_classes = [SessionAuthentication, TokenAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [UploadRateThrottle]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, project_id):
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        try:
            # Get audio file
            audio_file = request.FILES.get('audio_file')
            if not audio_file:
                return Response({'error': 'No audio file provided'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Validate audio file type
            allowed_extensions = ['.wav', '.mp3', '.m4a', '.flac', '.ogg']
            if not any(audio_file.name.lower().endswith(ext) for ext in allowed_extensions):
                return Response({'error': 'Invalid audio file format'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Get transcription data (JSON string or object)
            transcription_data = request.data.get('transcription_data')
            if not transcription_data:
                return Response({'error': 'No transcription data provided'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Parse transcription JSON if string
            if isinstance(transcription_data, str):
                segments = json.loads(transcription_data)
            else:
                segments = transcription_data
            
            if not isinstance(segments, list) or len(segments) == 0:
                return Response({'error': 'Transcription data must be a non-empty array'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Get optional parameters
            title = request.data.get('title', audio_file.name)
            order_index = int(request.data.get('order_index', project.audio_files.count()))
            
            # Create AudioFile record
            audio_obj = AudioFile.objects.create(
                project=project,
                file=audio_file,
                filename=audio_file.name,
                title=title,
                status='transcribed',  # Already transcribed client-side
                order_index=order_index
            )
            
            # Get duration from audio file
            try:
                audio_segment = AudioSegment.from_file(audio_obj.file.path)
                audio_obj.duration = len(audio_segment) / 1000.0  # Convert ms to seconds
                audio_obj.original_duration = audio_obj.duration
            except Exception as e:
                logger.warning(f"Could not extract audio duration: {e}")
                # Try to get duration from transcription data
                if segments:
                    audio_obj.duration = max(seg['end'] for seg in segments)
                    audio_obj.original_duration = audio_obj.duration
            
            audio_obj.save()
            
            # Create TranscriptionSegment records from client data
            transcript_text = []
            segments_created = 0
            words_created = 0
            
            for idx, segment in enumerate(segments):
                # Validate segment structure
                if not all(key in segment for key in ['text', 'start', 'end']):
                    logger.warning(f"Segment {idx} missing required fields, skipping")
                    continue
                
                seg_obj = TranscriptionSegment.objects.create(
                    audio_file=audio_obj,
                    text=segment['text'],
                    start_time=float(segment['start']),
                    end_time=float(segment['end']),
                    segment_index=idx,
                    confidence_score=float(segment.get('confidence', 0.0)),
                    is_duplicate=False,
                    is_kept=True
                )
                transcript_text.append(segment['text'])
                segments_created += 1
                
                # Create words if provided
                if 'words' in segment and isinstance(segment['words'], list):
                    for word_idx, word_data in enumerate(segment['words']):
                        if not all(key in word_data for key in ['word', 'start', 'end']):
                            continue
                        
                        TranscriptionWord.objects.create(
                            audio_file=audio_obj,
                            segment=seg_obj,
                            word=word_data['word'],
                            start_time=float(word_data['start']),
                            end_time=float(word_data['end']),
                            confidence=float(word_data.get('confidence', 0.0)),
                            word_index=word_idx
                        )
                        words_created += 1
            
            # Save full transcript
            audio_obj.transcript_text = ' '.join(transcript_text)
            audio_obj.save()
            
            # Create Transcription record for duplicate detection compatibility
            # This is required by Tab 3 duplicate detection which checks hasattr(audio_file, 'transcription')
            avg_confidence = sum(float(seg.get('confidence', 0.0)) for seg in segments) / len(segments) if segments else 0.0
            word_count = sum(len(seg['text'].split()) for seg in segments)
            
            from ..models import Transcription
            Transcription.objects.create(
                audio_file=audio_obj,
                full_text=audio_obj.transcript_text,
                word_count=word_count,
                confidence_score=avg_confidence
            )
            
            # Update project status if appropriate
            if project.status == 'setup':
                project.status = 'transcribing'
                project.save()
            
            logger.info(f"Bulk upload completed: {audio_obj.filename} with {segments_created} segments and {words_created} words")
            
            return Response({
                'success': True,
                'audio_file_id': audio_obj.id,
                'filename': audio_obj.filename,
                'title': audio_obj.title,
                'segments_count': segments_created,
                'words_count': words_created,
                'duration': audio_obj.duration,
                'status': audio_obj.status
            })
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in transcription_data: {str(e)}")
            return Response({'error': f'Invalid JSON format: {str(e)}'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Bulk upload failed: {str(e)}", exc_info=True)
            return Response({'error': f'Upload failed: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

