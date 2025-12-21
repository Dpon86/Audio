"""
Split views module for audioDiagnostic app.
Organized by domain for better maintainability.
"""

# Project CRUD operations
from .project_views import (
    ProjectListCreateView,
    ProjectDetailView,
    ProjectTranscriptView,
    ProjectStatusView,
    ProjectDownloadView
)

# Upload operations (PDF and Audio)
from .upload_views import (
    ProjectUploadPDFView,
    ProjectUploadAudioView
)

# Transcription operations
from .transcription_views import (
    ProjectTranscribeView,
    AudioFileListView,
    AudioFileDetailView,
    AudioFileTranscribeView,
    AudioFileRestartView,
    AudioTaskStatusWordsView,
    TranscriptionStatusWordsView,
)

# Duplicate detection and cleanup
from .duplicate_views import (
    ProjectDetectDuplicatesView,
    ProjectDuplicatesReviewView,
    ProjectConfirmDeletionsView,
    ProjectVerifyCleanupView,
    ProjectRedetectDuplicatesView,
    ProjectRefinePDFBoundariesView
)

# PDF matching and validation
from .pdf_matching_views import (
    ProjectMatchPDFView,
    ProjectValidatePDFView,
    ProjectValidationProgressView
)

# Processing operations
from .processing_views import (
    ProjectProcessView,
    AudioFileProcessView
)

# Infrastructure and task status
from .infrastructure_views import (
    InfrastructureStatusView,
    TaskStatusView
)

# Legacy endpoints (kept for backward compatibility)
from .legacy_views import (
    upload_chunk,
    assemble_chunks,
    download_audio,
    cut_audio,
    AnalyzePDFView,
    N8NTranscribeView,
    AudioTaskStatusSentencesView,
)

__all__ = [
    # Project views
    'ProjectListCreateView',
    'ProjectDetailView',
    'ProjectTranscriptView',
    'ProjectStatusView',
    'ProjectDownloadView',
    
    # Upload views
    'ProjectUploadPDFView',
    'ProjectUploadAudioView',
    
    # Transcription views
    'ProjectTranscribeView',
    'AudioFileListView',
    'AudioFileDetailView',
    'AudioFileTranscribeView',
    'AudioFileRestartView',
    'AudioTaskStatusWordsView',
    'TranscriptionStatusWordsView',
    
    # Duplicate views
    'ProjectDetectDuplicatesView',
    'ProjectDuplicatesReviewView',
    'ProjectConfirmDeletionsView',
    'ProjectVerifyCleanupView',
    'ProjectRedetectDuplicatesView',
    'ProjectRefinePDFBoundariesView',
    
    # PDF matching views
    'ProjectMatchPDFView',
    'ProjectValidatePDFView',
    'ProjectValidationProgressView',
    
    # Processing views
    'ProjectProcessView',
    'AudioFileProcessView',
    
    # Infrastructure views
    'InfrastructureStatusView',
    'TaskStatusView',
    
    # Legacy views
    'upload_chunk',
    'assemble_chunks',
    'download_audio',
    'cut_audio',
    'AnalyzePDFView',
    'N8NTranscribeView',
    'AudioTaskStatusSentencesView',
]
