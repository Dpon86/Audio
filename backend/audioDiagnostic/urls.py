from django.urls import path
from .views import (
    # Project CRUD
    ProjectListCreateView, ProjectDetailView, ProjectTranscriptView,
    ProjectStatusView, ProjectDownloadView,
    # Uploads
    ProjectUploadPDFView, ProjectUploadAudioView,
    # Transcription
    ProjectTranscribeView, AudioFileListView, AudioFileDetailView,
    AudioFileTranscribeView, AudioFileRestartView,
    AudioTaskStatusWordsView, TranscriptionStatusWordsView,
    # Processing
    ProjectProcessView, AudioFileProcessView,
    # Duplicates
    ProjectDetectDuplicatesView, ProjectDuplicatesReviewView,
    ProjectConfirmDeletionsView, ProjectVerifyCleanupView,
    ProjectRedetectDuplicatesView, ProjectRefinePDFBoundariesView,
    # PDF Matching
    ProjectMatchPDFView, ProjectValidatePDFView, ProjectValidationProgressView,
    # Infrastructure
    InfrastructureStatusView, TaskStatusView,
    # Legacy
    upload_chunk, assemble_chunks, download_audio, cut_audio,
    AnalyzePDFView, N8NTranscribeView, AudioTaskStatusSentencesView,
)
# Tab-based architecture views
from .views.tab1_file_management import (
    AudioFileListView as Tab1AudioFileListView,
    AudioFileDetailDeleteView,
    AudioFileStatusView as Tab1AudioFileStatusView,
)
from .views.tab2_transcription import (
    SingleFileTranscribeView,
    SingleFileTranscriptionResultView,
    SingleFileTranscriptionStatusView,
    TranscriptionDownloadView,
)
from .views.tab3_duplicate_detection import (
    SingleFileDetectDuplicatesView,
    SingleFileDuplicatesReviewView,
    SingleFileConfirmDeletionsView,
    SingleFileProcessingStatusView,
    SingleFileProcessedAudioView,
    SingleFileStatisticsView,
)
from .views.tab4_pdf_comparison import (
    SingleTranscriptionPDFCompareView,
    SingleTranscriptionPDFResultView,
    SingleTranscriptionPDFStatusView,
    SingleTranscriptionSideBySideView,
    SingleTranscriptionRetryComparisonView,
)
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
    path('projects/<int:project_id>/verify-cleanup/', ProjectVerifyCleanupView.as_view(), name='project-verify-cleanup'),
    path('projects/<int:project_id>/validate-against-pdf/', ProjectValidatePDFView.as_view(), name='project-validate-pdf'),
    path('projects/<int:project_id>/validation-progress/<str:task_id>/', ProjectValidationProgressView.as_view(), name='project-validation-progress'),
    
    # Iterative Cleaning API (Step 6 - Create child project)
    path('projects/<int:project_id>/create-iteration/', ProjectRedetectDuplicatesView.as_view(), name='project-create-iteration'),
    
    # Audio File Management
    path('projects/<int:project_id>/audio-files/', AudioFileListView.as_view(), name='audio-file-list'),
    path('projects/<int:project_id>/audio-files/<int:audio_file_id>/', AudioFileDetailView.as_view(), name='audio-file-detail'),
    path('projects/<int:project_id>/audio-files/<int:audio_file_id>/transcribe/', AudioFileTranscribeView.as_view(), name='audio-file-transcribe'),
    path('projects/<int:project_id>/audio-files/<int:audio_file_id>/restart/', AudioFileRestartView.as_view(), name='audio-file-restart'),
    path('projects/<int:project_id>/audio-files/<int:audio_file_id>/process/', AudioFileProcessView.as_view(), name='audio-file-process'),
    path('projects/<int:project_id>/transcript/', ProjectTranscriptView.as_view(), name='project-transcript'),
    
    # ============================================================================
    # TAB-BASED ARCHITECTURE ENDPOINTS
    # ============================================================================
    # Tab 1: File Management Hub
    path('api/projects/<int:project_id>/files/', Tab1AudioFileListView.as_view(), name='tab1-audio-files'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/', AudioFileDetailDeleteView.as_view(), name='tab1-audio-file-detail'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/status/', Tab1AudioFileStatusView.as_view(), name='tab1-audio-file-status'),
    
    # Tab 2: Transcription
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/transcribe/', SingleFileTranscribeView.as_view(), name='tab2-transcribe'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/transcription/', SingleFileTranscriptionResultView.as_view(), name='tab2-transcription-result'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/transcription/status/', SingleFileTranscriptionStatusView.as_view(), name='tab2-transcription-status'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/transcription/download/', TranscriptionDownloadView.as_view(), name='tab2-transcription-download'),
    
    # Tab 3: Duplicate Detection
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/detect-duplicates/', SingleFileDetectDuplicatesView.as_view(), name='tab3-detect-duplicates'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/duplicates/', SingleFileDuplicatesReviewView.as_view(), name='tab3-duplicates-review'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/confirm-deletions/', SingleFileConfirmDeletionsView.as_view(), name='tab3-confirm-deletions'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/processing-status/', SingleFileProcessingStatusView.as_view(), name='tab3-processing-status'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/processed-audio/', SingleFileProcessedAudioView.as_view(), name='tab3-processed-audio'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/statistics/', SingleFileStatisticsView.as_view(), name='tab3-statistics'),
    
    # Tab 4: PDF Comparison
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/compare-pdf/', SingleTranscriptionPDFCompareView.as_view(), name='tab4-compare-pdf'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/pdf-result/', SingleTranscriptionPDFResultView.as_view(), name='tab4-pdf-result'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/pdf-status/', SingleTranscriptionPDFStatusView.as_view(), name='tab4-pdf-status'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/side-by-side/', SingleTranscriptionSideBySideView.as_view(), name='tab4-side-by-side'),
    path('api/projects/<int:project_id>/files/<int:audio_file_id>/retry-comparison/', SingleTranscriptionRetryComparisonView.as_view(), name='tab4-retry-comparison'),
    
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