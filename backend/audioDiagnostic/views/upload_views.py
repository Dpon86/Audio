"""
Upload Views for audioDiagnostic app.
"""
from ._base import *

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

