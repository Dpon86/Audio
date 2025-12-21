"""
Celery task tests for audioDiagnostic.
Tests background tasks with mocks to avoid actual processing.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from unittest.mock import patch, MagicMock, call
from audioDiagnostic.models import AudioProject, AudioFile, TranscriptionSegment
from audioDiagnostic.tasks import (
    transcribe_all_project_audio_task,
    transcribe_audio_file_task,
    process_project_duplicates_task
)


class TranscriptionTaskTest(TestCase):
    """Test transcription-related Celery tasks"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user('testuser', 'test@example.com', 'pass')
        self.project = AudioProject.objects.create(
            user=self.user,
            title="Test Project",
            status="ready"
        )
        self.audio_file = AudioFile.objects.create(
            project=self.project,
            title="Chapter 1",
            filename="chapter1.mp3",
            order_index=0
        )
    
    @patch('audioDiagnostic.tasks.whisper.load_model')
    @patch('audioDiagnostic.tasks.ensure_ffmpeg_in_path')
    def test_transcribe_audio_file_task(self, mock_ffmpeg, mock_whisper):
        """Test transcribing a single audio file"""
        # Mock Whisper model
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            'text': 'This is a test transcription.',
            'segments': [
                {
                    'start': 0.0,
                    'end': 2.5,
                    'text': 'This is a test.',
                    'words': [
                        {'word': 'This', 'start': 0.0, 'end': 0.5},
                        {'word': 'is', 'start': 0.5, 'end': 0.7},
                        {'word': 'a', 'start': 0.7, 'end': 0.8},
                        {'word': 'test', 'start': 0.8, 'end': 1.2},
                    ]
                }
            ]
        }
        mock_whisper.return_value = mock_model
        
        # Run task
        result = transcribe_audio_file_task(self.audio_file.id)
        
        # Verify FFmpeg setup was called
        mock_ffmpeg.assert_called_once()
        
        # Verify Whisper was loaded and used
        mock_whisper.assert_called_once()
        mock_model.transcribe.assert_called_once()
        
        # Verify audio file was updated
        self.audio_file.refresh_from_db()
        self.assertEqual(self.audio_file.status, 'transcribed')
        self.assertIsNotNone(self.audio_file.transcript_text)
    
    @patch('audioDiagnostic.tasks.transcribe_audio_file_task.apply_async')
    def test_transcribe_all_project_audio_task(self, mock_apply_async):
        """Test transcribing all audio files in a project"""
        # Create multiple audio files
        AudioFile.objects.create(
            project=self.project,
            title="Chapter 2",
            filename="chapter2.mp3",
            order_index=1
        )
        
        # Run task
        result = transcribe_all_project_audio_task(self.project.id)
        
        # Verify individual transcription tasks were queued
        self.assertEqual(mock_apply_async.call_count, 2)
        
        # Verify project status was updated
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'transcribing')
    
    @patch('audioDiagnostic.tasks.whisper.load_model')
    @patch('audioDiagnostic.tasks.ensure_ffmpeg_in_path')
    def test_transcription_error_handling(self, mock_ffmpeg, mock_whisper):
        """Test transcription task handles errors gracefully"""
        # Mock Whisper to raise an error
        mock_whisper.side_effect = Exception("Whisper model failed")
        
        # Run task - should not raise exception
        result = transcribe_audio_file_task(self.audio_file.id)
        
        # Verify audio file status was updated to failed
        self.audio_file.refresh_from_db()
        self.assertEqual(self.audio_file.status, 'failed')
        self.assertIn('error', self.audio_file.error_message.lower())


class ProcessingTaskTest(TestCase):
    """Test audio processing Celery tasks"""
    
    def setUp(self):
        """Create test data with transcribed segments"""
        self.user = User.objects.create_user('testuser', 'test@example.com', 'pass')
        self.project = AudioProject.objects.create(
            user=self.user,
            title="Test Project",
            status="transcribed"
        )
        self.audio_file = AudioFile.objects.create(
            project=self.project,
            title="Chapter 1",
            filename="chapter1.mp3",
            status="transcribed",
            order_index=0
        )
        
        # Create transcription segments
        TranscriptionSegment.objects.create(
            audio_file=self.audio_file,
            text="This is the first sentence.",
            start_time=0.0,
            end_time=2.0,
            segment_index=0
        )
        TranscriptionSegment.objects.create(
            audio_file=self.audio_file,
            text="This is a duplicate sentence.",
            start_time=2.0,
            end_time=4.0,
            segment_index=1
        )
        TranscriptionSegment.objects.create(
            audio_file=self.audio_file,
            text="This is a duplicate sentence.",  # Duplicate
            start_time=10.0,
            end_time=12.0,
            segment_index=2
        )
    
    @patch('audioDiagnostic.tasks.pdfplumber.open')
    def test_process_project_duplicates_task(self, mock_pdf):
        """Test duplicate detection task"""
        # Mock PDF reading
        mock_pdf_obj = MagicMock()
        mock_pdf_obj.pages = [MagicMock()]
        mock_pdf_obj.pages[0].extract_text.return_value = "PDF text content"
        mock_pdf.__enter__.return_value = mock_pdf_obj
        
        # Run task
        result = process_project_duplicates_task(self.project.id)
        
        # Verify project status was updated
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'processing')
    
    @patch('audioDiagnostic.tasks.AudioSegment.from_file')
    def test_audio_assembly_task(self, mock_audio_segment):
        """Test assembling final audio from segments"""
        # Mock AudioSegment
        mock_segment = MagicMock()
        mock_audio_segment.return_value = mock_segment
        
        # This would test the audio assembly logic
        # Actual implementation depends on your task structure
        pass


class TaskErrorHandlingTest(TestCase):
    """Test error handling in Celery tasks"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'pass')
    
    def test_task_with_nonexistent_project(self):
        """Test task behavior with non-existent project ID"""
        # Task should handle gracefully - may raise DoesNotExist or return None
        try:
            result = transcribe_all_project_audio_task(99999)
        except AudioProject.DoesNotExist:
            # This is acceptable behavior
            pass
    
    def test_task_with_nonexistent_audio_file(self):
        """Test task behavior with non-existent audio file ID"""
        # Task should raise AudioFile.DoesNotExist or handle gracefully
        try:
            result = transcribe_audio_file_task(99999)
        except AudioFile.DoesNotExist:
            # This is expected and acceptable
            pass


class TaskRetryTest(TestCase):
    """Test Celery task retry logic"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'pass')
        self.project = AudioProject.objects.create(
            user=self.user,
            title="Test Project"
        )
        self.audio_file = AudioFile.objects.create(
            project=self.project,
            title="Chapter 1",
            filename="chapter1.mp3",
            order_index=0
        )
    
    @patch('audioDiagnostic.tasks.whisper.load_model')
    @patch('audioDiagnostic.tasks.ensure_ffmpeg_in_path')
    def test_task_retries_on_transient_error(self, mock_ffmpeg, mock_whisper):
        """Test that tasks retry on transient errors"""
        # Mock a transient error (e.g., network timeout)
        mock_whisper.side_effect = [
            ConnectionError("Network error"),  # First attempt fails
            MagicMock()  # Second attempt succeeds
        ]
        
        # This test would require Celery test configuration
        # to properly test retry behavior
        pass


class FFmpegIntegrationTest(TestCase):
    """Test FFmpeg path configuration"""
    
    @patch('audioDiagnostic.tasks.os.path.exists')
    @patch('audioDiagnostic.tasks.os.environ')
    def test_ensure_ffmpeg_in_path(self, mock_environ, mock_exists):
        """Test FFmpeg path setup"""
        from audioDiagnostic.tasks import ensure_ffmpeg_in_path
        
        mock_exists.return_value = True
        mock_environ.__getitem__ = MagicMock(return_value='')
        mock_environ.__setitem__ = MagicMock()
        
        # Test with environment variable
        with patch('audioDiagnostic.tasks.os.getenv') as mock_getenv:
            mock_getenv.return_value = 'C:\\ffmpeg\\bin'
            ensure_ffmpeg_in_path()
            
            # Verify path manipulation occurred
            # (Implementation depends on your actual function)
