from django.urls import path
from .views import *
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

def homepage(request):
    return HttpResponse("Welcome to the Audio Repetitive Detection API!")

urlpatterns = [
    path('', homepage, name='homepage'),
    path('upload-chunk/', upload_chunk, name='audio-upload-chunk'),
    path('assemble-chunks/', assemble_chunks, name='audio-assemble-chunks'),
    path('status/words/<str:task_id>/', AudioTaskStatusWordsView.as_view(), name='audio-status-words'),
    path('status/sentences/<str:task_id>/', AudioTaskStatusSentencesView.as_view(), name='audio-status-sentences'),
    path('status/<str:task_id>/', AudioTaskStatusSentencesView.as_view(), name='audio-status'),
    path('download/<str:filename>/', download_audio, name='download_audio'),
    path("cut/", cut_audio, name="cut_audio"),
    path('n8n/transcribe/', N8NTranscribeView.as_view(), name='transcribe_audio'),
    path('status/n8n/words/<str:task_id>/', TranscriptionStatusWordsView.as_view(), name='transcription-status-words'),
    path('analyze-pdf/', AnalyzePDFView.as_view(), name='analyze-pdf'),

    ]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)