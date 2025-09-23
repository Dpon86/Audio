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

from django.http import JsonResponse, FileResponse, Http404, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils.decorators import method_decorator



from .tasks import *
from celery.result import AsyncResult
from pydub import AudioSegment



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