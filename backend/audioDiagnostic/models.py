from django.db import models
from django.contrib.auth.models import User

class AudioProject(models.Model):
    STATUS_CHOICES = [
        ('setup', 'Setup'),                    # PDF uploaded, waiting for audio files
        ('uploading', 'Uploading Audio'),      # Audio files being uploaded
        ('ready', 'Ready to Transcribe'),      # All files uploaded, ready to start
        ('transcribing', 'Transcribing'),      # Transcribing all audio files
        ('transcribed', 'Transcribed'),        # All files transcribed, ready to process
        ('processing', 'Processing'),          # Analyzing duplicates and creating final audio
        ('completed', 'Completed'),            # Final processed audio ready
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    pdf_file = models.FileField(upload_to='pdfs/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='setup')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Iterative cleaning - link to parent project
    parent_project = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='iterations')
    iteration_number = models.IntegerField(default=0)  # 0 = original, 1 = first iteration, etc.
    
    # Project-level results after processing all audio files
    pdf_text = models.TextField(null=True, blank=True)  # Extracted PDF text
    combined_transcript = models.TextField(null=True, blank=True)  # All transcripts combined
    final_processed_audio = models.FileField(upload_to='assembled/', null=True, blank=True)
    
    # Analysis results
    total_duplicates_found = models.IntegerField(default=0)
    missing_content = models.TextField(null=True, blank=True)  # PDF content not found in audio
    processing_summary = models.JSONField(null=True, blank=True)  # Detailed results
    
    # PDF Matching Results (Step 1)
    pdf_matched_section = models.TextField(null=True, blank=True)  # Matched PDF section text
    pdf_match_confidence = models.FloatField(null=True, blank=True)  # Confidence score 0-1
    pdf_chapter_title = models.CharField(max_length=200, null=True, blank=True)  # e.g. "Chapter 1"
    pdf_match_completed = models.BooleanField(default=False)  # Step 1 completion status
    pdf_match_start_char = models.IntegerField(null=True, blank=True)  # Character position where match starts
    pdf_match_end_char = models.IntegerField(null=True, blank=True)  # Character position where match ends
    
    # Duplicate Detection Results (Step 2)
    duplicates_detected = models.JSONField(null=True, blank=True)  # List of detected duplicates
    duplicates_detection_completed = models.BooleanField(default=False)  # Step 2 completion status
    
    # User Review Results (Step 3)
    duplicates_confirmed_for_deletion = models.JSONField(null=True, blank=True)  # User-confirmed deletions
    
    # Duration Tracking
    original_audio_duration = models.FloatField(null=True, blank=True)  # Total duration of all original audio (seconds)
    final_audio_duration = models.FloatField(null=True, blank=True)  # Duration of processed audio after deletions (seconds)
    duration_deleted = models.FloatField(null=True, blank=True)  # Total duration of deleted segments (seconds)
    
    # Post-Processing Verification (Step 4)
    clean_audio_transcribed = models.BooleanField(default=False)  # Clean audio transcription completed
    verification_completed = models.BooleanField(default=False)  # Verification comparison completed
    verification_results = models.JSONField(null=True, blank=True)  # Comparison results vs PDF
    
    # PDF Word-by-Word Validation (Step 5)
    pdf_validation_completed = models.BooleanField(default=False)  # PDF validation completed
    pdf_validation_results = models.JSONField(null=True, blank=True)  # Statistics: matched_words, unmatched_pdf_words, etc.
    pdf_validation_html = models.TextField(null=True, blank=True)  # Rendered HTML with color-coded highlights
    
    error_message = models.TextField(null=True, blank=True)
    
    # Book information
    description = models.TextField(null=True, blank=True)
    total_chapters = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),  # Common filter pattern
            models.Index(fields=['user', '-created_at']),  # List user's projects
            models.Index(fields=['status', '-created_at']),  # Filter by status
            models.Index(fields=['parent_project']),  # Iteration lookup
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    @property
    def audio_files_count(self):
        return self.audio_files.count()
    
    @property
    def processed_files_count(self):
        return self.audio_files.filter(status='completed').count()

class AudioFile(models.Model):
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),           # File uploaded, waiting for transcription
        ('transcribing', 'Transcribing'),   # Being transcribed
        ('transcribed', 'Transcribed'),     # Transcription complete
        ('processing', 'Processing'),       # Processing duplicates
        ('processed', 'Processed'),         # Duplicates removed, clean audio ready
        ('failed', 'Failed'),
    ]
    
    project = models.ForeignKey(AudioProject, on_delete=models.CASCADE, related_name='audio_files')
    title = models.CharField(max_length=200)  # e.g., "Chapter 1", "Section 2.3"  
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='audio/')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    task_id = models.CharField(max_length=100, null=True, blank=True)
    
    # New fields for tab-based architecture
    duration_seconds = models.FloatField(null=True, blank=True)  # Audio duration
    processed_duration_seconds = models.FloatField(null=True, blank=True)  # Processed audio duration after duplicate removal
    file_size_bytes = models.BigIntegerField(null=True, blank=True)  # File size
    format = models.CharField(max_length=10, null=True, blank=True)  # mp3, wav, m4a, etc.
    processed_audio = models.FileField(upload_to='processed/', null=True, blank=True)  # Clean audio after duplicate removal
    
    # Preview/Review fields for Tab 3 (Review Deletions)
    preview_audio = models.FileField(upload_to='previews/', null=True, blank=True)  # Preview audio with deletions applied
    preview_status = models.CharField(
        max_length=20,
        choices=[
            ('none', 'None'),
            ('generating', 'Generating'),
            ('ready', 'Ready'),
            ('failed', 'Failed'),
        ],
        default='none'
    )
    preview_generated_at = models.DateTimeField(null=True, blank=True)
    preview_metadata = models.JSONField(null=True, blank=True)  # Stores deletion_regions, stats, etc.
    
    # Tab 4 Review/Comparison fields (Post-Processing Analysis)
    comparison_status = models.CharField(
        max_length=20,
        choices=[
            ('none', 'Not Compared'),
            ('pending', 'Pending Review'),
            ('reviewed', 'Reviewed'),
            ('approved', 'Approved'),
        ],
        default='none'
    )
    comparison_metadata = models.JSONField(null=True, blank=True)  # Stores deletion regions, stats for comparison
    reviewed_at = models.DateTimeField(null=True, blank=True)  # When file was reviewed
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_files')
    comparison_notes = models.TextField(null=True, blank=True)  # User notes about the comparison
    
    # Tab 5 PDF Comparison fields
    pdf_comparison_results = models.JSONField(null=True, blank=True)  # Full comparison results (match, missing, extra, stats)
    pdf_comparison_completed = models.BooleanField(default=False)  # Whether comparison has been done
    pdf_ignored_sections = models.JSONField(null=True, blank=True)  # List of text sections to ignore (narrator, chapter titles, etc.)
    
    # Legacy transcription field (kept for backwards compatibility)
    transcript_text = models.TextField(null=True, blank=True)
    original_duration = models.FloatField(null=True, blank=True)  # seconds (legacy)
    error_message = models.TextField(null=True, blank=True)
    
    # Order and organization (important for proper sequencing)
    order_index = models.IntegerField(default=0)
    chapter_number = models.IntegerField(null=True, blank=True)
    section_number = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_processed_at = models.DateTimeField(null=True, blank=True)  # When last processed
    
    class Meta:
        ordering = ['order_index', 'created_at']
        unique_together = ['project', 'order_index']
        indexes = [
            models.Index(fields=['project', 'status']),  # Common filter pattern
            models.Index(fields=['project', 'order_index']),  # Ordering files
            models.Index(fields=['status']),  # Status filtering
        ]
    
    def __str__(self):
        return f"{self.project.title} - {self.title}"
    
    @property
    def has_transcription(self):
        # Check both new Transcription model and legacy field
        return hasattr(self, 'transcription') or bool(self.transcript_text)
    
    @property
    def has_processed_audio(self):
        return bool(self.processed_audio)

class Transcription(models.Model):
    """One transcription per audio file - Created in Tab 2"""
    audio_file = models.OneToOneField(AudioFile, on_delete=models.CASCADE, related_name='transcription')
    full_text = models.TextField()
    word_count = models.IntegerField(default=0)
    confidence_score = models.FloatField(null=True, blank=True)  # Average confidence
    created_at = models.DateTimeField(auto_now_add=True)
    
    # PDF matching results (from Tab 4)
    matched_pdf_section = models.TextField(null=True, blank=True)
    pdf_start_page = models.IntegerField(null=True, blank=True)
    pdf_end_page = models.IntegerField(null=True, blank=True)
    pdf_match_percentage = models.FloatField(null=True, blank=True)
    pdf_match_confidence = models.FloatField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['audio_file']),
        ]
    
    def __str__(self):
        return f"Transcription for {self.audio_file.filename}"

class DuplicateGroup(models.Model):
    """Track duplicate groups for a single audio file - Tab 3"""
    audio_file = models.ForeignKey(AudioFile, on_delete=models.CASCADE, related_name='duplicate_groups')
    group_id = models.CharField(max_length=100)
    duplicate_text = models.TextField()
    occurrence_count = models.IntegerField()
    total_duration_seconds = models.FloatField()  # Time saved if all removed
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['audio_file', 'group_id']),
        ]
    
    def __str__(self):
        return f"Duplicate Group {self.group_id} in {self.audio_file.filename}"

class TranscriptionSegment(models.Model):
    # Support both legacy (audio_file) and new (transcription) relationships
    audio_file = models.ForeignKey(AudioFile, on_delete=models.CASCADE, related_name='segments', null=True, blank=True)
    transcription = models.ForeignKey(Transcription, on_delete=models.CASCADE, related_name='segments', null=True, blank=True)
    
    text = models.TextField()
    start_time = models.FloatField()  # seconds from start of THIS audio file
    end_time = models.FloatField()    # seconds from start of THIS audio file  
    
    # Verification flag to distinguish clean audio transcription
    is_verification = models.BooleanField(default=False)  # True if from clean/processed audio
    
    # Duplicate detection results (filled during processing phase)
    is_duplicate = models.BooleanField(default=False)
    duplicate_type = models.CharField(max_length=20, choices=[
        ('word', 'Word Repetition'),
        ('sentence', 'Sentence Repetition'), 
        ('paragraph', 'Paragraph Repetition'),
        ('none', 'Not a Duplicate')
    ], default='none')
    is_kept = models.BooleanField(default=True)  # False if this occurrence should be removed
    duplicate_group_id = models.CharField(max_length=100, null=True, blank=True)  # Groups same content together
    
    # PDF matching
    pdf_match_found = models.BooleanField(default=False)
    pdf_match_confidence = models.FloatField(null=True, blank=True)
    
    confidence_score = models.FloatField(null=True, blank=True)
    segment_index = models.IntegerField()  # Original order in transcription
    
    class Meta:
        ordering = ['segment_index']
        indexes = [
            models.Index(fields=['audio_file', 'segment_index']),  # Common query pattern
            models.Index(fields=['audio_file', 'start_time']),  # Time-based queries
            models.Index(fields=['duplicate_group_id']),  # Duplicate grouping
            models.Index(fields=['is_duplicate']),  # Filter duplicates
        ]
    
    def __str__(self):
        return f"{self.audio_file.title} - Segment {self.segment_index}: {self.text[:50]}..."

class TranscriptionWord(models.Model):
    segment = models.ForeignKey(TranscriptionSegment, on_delete=models.CASCADE, related_name='words')
    audio_file = models.ForeignKey(AudioFile, on_delete=models.CASCADE, related_name='words', null=True, blank=True)
    word = models.CharField(max_length=100)
    start_time = models.FloatField()  # seconds from start of THIS audio file
    end_time = models.FloatField()    # seconds from start of THIS audio file
    confidence = models.FloatField(null=True, blank=True)
    word_index = models.IntegerField()  # Order within segment
    
    class Meta:
        ordering = ['word_index']
        indexes = [
            models.Index(fields=['segment', 'word_index']),  # Ordering words
            models.Index(fields=['audio_file', 'start_time']),  # Time-based queries
        ]
    
    def __str__(self):
        return f"{self.word} ({self.start_time:.2f}s)"

class ProcessingResult(models.Model):
    """Tracks the results of processing all audio files in a project together"""
    project = models.OneToOneField(AudioProject, on_delete=models.CASCADE, related_name='processing_result')
    
    # Processing statistics
    total_segments_processed = models.IntegerField(default=0)
    duplicates_removed = models.IntegerField(default=0)
    words_removed = models.IntegerField(default=0)
    sentences_removed = models.IntegerField(default=0)
    paragraphs_removed = models.IntegerField(default=0)
    
    # Time savings
    original_total_duration = models.FloatField(default=0)  # seconds
    final_duration = models.FloatField(default=0)  # seconds
    time_saved = models.FloatField(default=0)  # seconds
    
    # Content analysis
    pdf_coverage_percentage = models.FloatField(null=True, blank=True)  # How much of PDF was read
    missing_content_count = models.IntegerField(default=0)  # PDF sentences not found in audio
    
    # Results
    processing_log = models.JSONField(null=True, blank=True)  # Detailed processing steps
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Processing Result for {self.project.title}"
