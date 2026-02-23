"""
Split tasks module for audioDiagnostic app.
Organized by domain for better maintainability.
"""

# Transcription tasks
from .transcription_tasks import (
    ensure_ffmpeg_in_path,
    transcribe_all_project_audio_task,
    transcribe_audio_file_task,
    transcribe_audio_task,
    transcribe_audio_words_task,
    split_segment_to_sentences,
    find_noise_regions,
    transcribe_single_audio_file_task,  # NEW: Tab 2 individual file transcription
    retranscribe_processed_audio_task,  # NEW: Tab 4 re-transcribe processed audio
)

# Duplicate detection and processing tasks
from .duplicate_tasks import (
    process_project_duplicates_task,
    detect_duplicates_task,
    process_confirmed_deletions_task,
    identify_all_duplicates,
    mark_duplicates_for_removal,
    detect_duplicates_against_pdf_task,
    detect_duplicates_single_file_task,  # NEW: Tab 3 individual file duplicate detection
    process_deletions_single_file_task,  # NEW: Tab 3 generate clean audio
    refine_duplicate_timestamps_task,  # NEW: Tab 3 refine timestamps at silence boundaries
)

# PDF matching and validation tasks
from .pdf_tasks import (
    match_pdf_to_audio_task,
    analyze_transcription_vs_pdf,
    validate_transcript_against_pdf_task,
    find_pdf_section_match,
    find_pdf_section_match_task,
    identify_pdf_based_duplicates,
    find_text_in_pdf,
    find_missing_pdf_content,
    calculate_comprehensive_similarity_task,
    extract_chapter_title_task,
)

# PDF comparison tasks (Tab 4 - old)
from .pdf_comparison_tasks import (
    compare_transcription_to_pdf_task as compare_transcription_to_pdf_task_old,  # OLD: Tab 4 PDF comparison
    batch_compare_transcriptions_to_pdf_task,  # NEW: Tab 4 batch comparison
)

# PDF comparison tasks (Tab 5 - new)
from .compare_pdf_task import (
    compare_transcription_to_pdf_task,  # NEW: Tab 5 PDF comparison (algorithmic)
)

# AI-powered PDF comparison tasks (Tab 5 - AI version)
from .ai_pdf_comparison_task import (
    ai_compare_transcription_to_pdf_task,  # NEW: Tab 5 AI-powered PDF comparison
)

# Audiobook production analysis (Tab 5 - Production Analysis)
from .audiobook_production_task import (
    audiobook_production_analysis_task,  # NEW: Comprehensive audiobook quality analysis
    get_audiobook_analysis_progress,
    get_audiobook_report_summary,
)

# Audio processing tasks
from .audio_processing_tasks import (
    process_audio_file_task,
    generate_processed_audio,
    generate_clean_audio,
    transcribe_clean_audio_for_verification,
    assemble_final_audio,
)

# Utility functions
from .utils import (
    save_transcription_to_db,
    get_final_transcript_without_duplicates,
    get_audio_duration,
    normalize,
)

__all__ = [
    # Transcription tasks
    'ensure_ffmpeg_in_path',
    'transcribe_all_project_audio_task',
    'transcribe_audio_file_task',
    'transcribe_audio_task',
    'transcribe_audio_words_task',
    'split_segment_to_sentences',
    'find_noise_regions',
    'transcribe_single_audio_file_task',  # NEW
    
    # Duplicate tasks
    'process_project_duplicates_task',
    'detect_duplicates_task',
    'process_confirmed_deletions_task',
    'identify_all_duplicates',
    'mark_duplicates_for_removal',
    'detect_duplicates_against_pdf_task',
    'detect_duplicates_single_file_task',  # NEW
    'process_deletions_single_file_task',  # NEW
    'refine_duplicate_timestamps_task',  # NEW
    
    # PDF tasks
    'match_pdf_to_audio_task',
    'analyze_transcription_vs_pdf',
    'validate_transcript_against_pdf_task',
    'find_pdf_section_match',
    'find_pdf_section_match_task',
    'identify_pdf_based_duplicates',
    'find_text_in_pdf',
    'find_missing_pdf_content',
    'calculate_comprehensive_similarity_task',
    'extract_chapter_title_task',
    
    # PDF comparison tasks (NEW)
    'compare_transcription_to_pdf_task',
    'ai_compare_transcription_to_pdf_task',  # NEW: AI-powered comparison
    'batch_compare_transcriptions_to_pdf_task',
    
    # Audiobook production analysis (NEW)
    'audiobook_production_analysis_task',
    'get_audiobook_analysis_progress',
    'get_audiobook_report_summary',
    
    # Audio processing tasks
    'process_audio_file_task',
    'generate_processed_audio',
    'generate_clean_audio',
    'transcribe_clean_audio_for_verification',
    'assemble_final_audio',
    
    # Utilities
    'save_transcription_to_db',
    'get_final_transcript_without_duplicates',
    'get_audio_duration',
    'normalize',
]
