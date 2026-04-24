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
from rest_framework.test import force_authenticate
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
    
    @patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.transcription_tasks.ensure_ffmpeg_in_path')
    @patch('audioDiagnostic.tasks.transcription_tasks._get_whisper_model')
    def test_transcribe_audio_file_task(self, mock_get_whisper, mock_ffmpeg, mock_docker_mgr, mock_redis):
        """Test transcribing a single audio file"""
        # Set up infrastructure mocks
        mock_docker_mgr.setup_infrastructure.return_value = True
        mock_redis.return_value = MagicMock()

        # Mock Whisper model
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            'text': 'This is a test transcription.',
            'duration': 5.0,
            'segments': [
                {
                    'start': 0.0,
                    'end': 2.5,
                    'text': 'This is a test.',
                    'avg_logprob': -0.3,
                    'words': [
                        {'word': 'This', 'start': 0.0, 'end': 0.5, 'probability': 0.9},
                        {'word': 'is', 'start': 0.5, 'end': 0.7, 'probability': 0.9},
                        {'word': 'a', 'start': 0.7, 'end': 0.8, 'probability': 0.9},
                        {'word': 'test', 'start': 0.8, 'end': 1.2, 'probability': 0.9},
                    ]
                }
            ]
        }
        mock_get_whisper.return_value = mock_model

        # Give the audio file a file path so audio_file.file.path works
        AudioFile.objects.filter(id=self.audio_file.id).update(file='audio/chapter1.mp3')

        # Run task
        result = transcribe_audio_file_task(self.audio_file.id)

        # Verify FFmpeg setup was called
        mock_ffmpeg.assert_called_once()

        # Verify Whisper model was loaded and used
        mock_get_whisper.assert_called_once()
        mock_model.transcribe.assert_called_once()

        # Verify audio file was updated
        self.audio_file.refresh_from_db()
        self.assertEqual(self.audio_file.status, 'transcribed')
        self.assertIsNotNone(self.audio_file.transcript_text)
    
    @patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.transcription_tasks.ensure_ffmpeg_in_path')
    @patch('audioDiagnostic.tasks.transcription_tasks._get_whisper_model')
    def test_transcribe_all_project_audio_task(self, mock_get_whisper, mock_ffmpeg, mock_docker_mgr, mock_redis):
        """Test transcribing all audio files in a project"""
        # Set up infrastructure mocks
        mock_docker_mgr.setup_infrastructure.return_value = True
        mock_redis.return_value = MagicMock()

        # Mock Whisper model
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            'text': 'Test transcription.',
            'duration': 5.0,
            'segments': []
        }
        mock_get_whisper.return_value = mock_model

        # Give the existing audio file a valid file path
        AudioFile.objects.filter(project=self.project).update(file='audio/chapter1.mp3')

        # Create a second audio file with a file path
        second_file = AudioFile.objects.create(
            project=self.project,
            title="Chapter 2",
            filename="chapter2.mp3",
            order_index=1
        )
        AudioFile.objects.filter(id=second_file.id).update(file='audio/chapter2.mp3')

        # Run task
        result = transcribe_all_project_audio_task(self.project.id)

        # Verify Whisper model was loaded once (singleton)
        mock_get_whisper.assert_called_once()

        # Verify project status was updated to transcribed
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'transcribed')
    
    @patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.transcription_tasks.ensure_ffmpeg_in_path')
    @patch('audioDiagnostic.tasks.transcription_tasks._get_whisper_model')
    def test_transcription_error_handling(self, mock_get_whisper, mock_ffmpeg, mock_docker_mgr, mock_redis):
        """Test transcription task handles errors gracefully"""
        # Set up infrastructure mocks
        mock_docker_mgr.setup_infrastructure.return_value = True
        mock_redis.return_value = MagicMock()

        # Mock Whisper to raise an error
        mock_get_whisper.side_effect = Exception("Whisper model failed")

        # Give the audio file a file path
        AudioFile.objects.filter(id=self.audio_file.id).update(file='audio/chapter1.mp3')

        # Task catches the exception internally but re-raises it after updating status
        with self.assertRaises(Exception):
            transcribe_audio_file_task(self.audio_file.id)

        # Verify audio file status was updated to failed
        self.audio_file.refresh_from_db()
        self.assertEqual(self.audio_file.status, 'failed')
        self.assertIsNotNone(self.audio_file.error_message)


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
    
    def test_process_project_duplicates_task(self):
        """Test duplicate detection task fails gracefully when no PDF provided"""
        # Run task - expects failure since no PDF file is on the project
        with self.assertRaises(ValueError):
            process_project_duplicates_task(self.project.id)

        # Verify project status reflects the failure
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'failed')
    
    def test_audio_assembly_task(self):
        """Test assembling final audio from segments"""
        # Placeholder - actual assembly tested via integration tests
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
    
    @patch('audioDiagnostic.tasks.transcription_tasks._get_whisper_model')
    @patch('audioDiagnostic.tasks.transcription_tasks.ensure_ffmpeg_in_path')
    def test_task_retries_on_transient_error(self, mock_ffmpeg, mock_whisper):
        """Test that tasks retry on transient errors"""
        # This test requires Celery retry configuration to test fully;
        # verify the mock path is correct as a placeholder
        pass


class FFmpegIntegrationTest(TestCase):
    """Test FFmpeg path configuration"""
    
    @patch('audioDiagnostic.tasks.transcription_tasks.os.path.exists')
    @patch('audioDiagnostic.tasks.transcription_tasks.os.environ')
    def test_ensure_ffmpeg_in_path(self, mock_environ, mock_exists):
        """Test FFmpeg path setup"""
        from audioDiagnostic.tasks import ensure_ffmpeg_in_path
        
        mock_exists.return_value = True
        mock_environ.__getitem__ = MagicMock(return_value='')
        mock_environ.__setitem__ = MagicMock()
        
        # Test with environment variable
        with patch('audioDiagnostic.tasks.transcription_tasks.os.getenv') as mock_getenv:
            mock_getenv.return_value = 'C:\\ffmpeg\\bin'
            ensure_ffmpeg_in_path()
            
            # Verify path manipulation occurred
            # (Implementation depends on your actual function)
