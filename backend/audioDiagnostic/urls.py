from django.urls import path
from .views import *
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

def homepage(request):
    return HttpResponse("Welcome to the Audio Repetitive Detection API!")

urlpatterns = [
    path('', homepage, name='homepage'),
    
    # New Project-Based API
    path('projects/', ProjectListCreateView.as_view(), name='project-list-create'),
    path('projects/<int:project_id>/', ProjectDetailView.as_view(), name='project-detail'),
    path('projects/<int:project_id>/upload-pdf/', ProjectUploadPDFView.as_view(), name='project-upload-pdf'),
    path('projects/<int:project_id>/upload-audio/', ProjectUploadAudioView.as_view(), name='project-upload-audio'),
    path('projects/<int:project_id>/transcribe/', ProjectTranscribeView.as_view(), name='project-transcribe'),
    path('projects/<int:project_id>/process/', ProjectProcessView.as_view(), name='project-process'),
    path('projects/<int:project_id>/status/', ProjectStatusView.as_view(), name='project-status'),
    path('projects/<int:project_id>/download/', ProjectDownloadView.as_view(), name='project-download'),
    
    # Step-by-Step Processing API
    path('projects/<int:project_id>/match-pdf/', ProjectMatchPDFView.as_view(), name='project-match-pdf'),
    path('projects/<int:project_id>/detect-duplicates/', ProjectDetectDuplicatesView.as_view(), name='project-detect-duplicates'),
    path('projects/<int:project_id>/duplicates/', ProjectDuplicatesReviewView.as_view(), name='project-duplicates-review'),
    path('projects/<int:project_id>/confirm-deletions/', ProjectConfirmDeletionsView.as_view(), name='project-confirm-deletions'),
    
    # Audio File Management
    path('projects/<int:project_id>/audio-files/', AudioFileListView.as_view(), name='audio-file-list'),
    path('projects/<int:project_id>/audio-files/<int:audio_file_id>/', AudioFileDetailView.as_view(), name='audio-file-detail'),
    path('projects/<int:project_id>/audio-files/<int:audio_file_id>/transcribe/', AudioFileTranscribeView.as_view(), name='audio-file-transcribe'),
    path('projects/<int:project_id>/audio-files/<int:audio_file_id>/restart/', AudioFileRestartView.as_view(), name='audio-file-restart'),
    path('projects/<int:project_id>/audio-files/<int:audio_file_id>/process/', AudioFileProcessView.as_view(), name='audio-file-process'),
    path('projects/<int:project_id>/audio-files/<int:audio_file_id>/status/', AudioFileStatusView.as_view(), name='audio-file-status'),
    path('projects/<int:project_id>/transcript/', ProjectTranscriptView.as_view(), name='project-transcript'),
    
    # Infrastructure Management
    path('infrastructure/status/', InfrastructureStatusView.as_view(), name='infrastructure-status'),
    
    # Task Status Checking (prevents timeouts)
    path('tasks/<str:task_id>/status/', TaskStatusView.as_view(), name='task-status'),
    
    # Legacy endpoints (kept for backward compatibility)
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