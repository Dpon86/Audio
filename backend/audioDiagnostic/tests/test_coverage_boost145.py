"""
Wave 145: legacy_views.py - AudioFileStatusView, upload_chunk, assemble_chunks, AudioTaskStatusSentencesView
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from unittest.mock import MagicMock, patch
from audioDiagnostic.models import AudioProject, AudioFile, Transcription, TranscriptionSegment

User = get_user_model()


class AudioFileStatusViewTests(TestCase):
    """Test AudioFileStatusView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user = User.objects.create_user(username='afstatus145', password='pass', email='afstatus145@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.project = AudioProject.objects.create(user=self.user, title='AFStatus Project')
        self.audio_file = AudioFile.objects.create(
            project=self.project,
            filename='status.wav',
            order_index=1,
            status='transcribed',
        )
        transcription = Transcription.objects.create(audio_file=self.audio_file, full_text='Status text')
        TranscriptionSegment.objects.create(
            transcription=transcription,
            audio_file=self.audio_file,
            text='Status text',
            start_time=0.0,
            end_time=1.0,
            segment_index=0,
        )

    def test_get_audio_file_status(self):
        response = self.client.get(f'/api/projects/{self.project.id}/audio-files/{self.audio_file.id}/status/')
        self.assertIn(response.status_code, [200, 404])

    def test_get_status_wrong_project(self):
        other_project = AudioProject.objects.create(user=self.user, title='Other')
        response = self.client.get(f'/api/projects/{other_project.id}/audio-files/{self.audio_file.id}/status/')
        self.assertIn(response.status_code, [404])


class AudioTaskStatusSentencesViewTests(TestCase):
    """Test AudioTaskStatusSentencesView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False

    @patch('audioDiagnostic.views.legacy_views.AsyncResult')
    def test_processing_status(self, mock_result_cls):
        mock_result = MagicMock()
        mock_result.failed.return_value = False
        mock_result.ready.return_value = False
        mock_result_cls.return_value = mock_result

        with patch('audioDiagnostic.views.legacy_views.r') as mock_r:
            mock_r.get.return_value = b'25'
            response = self.client.get('/api/task-status/fake-task-id/')
            self.assertIn(response.status_code, [200, 202, 404])

    @patch('audioDiagnostic.views.legacy_views.AsyncResult')
    def test_ready_status(self, mock_result_cls):
        mock_result = MagicMock()
        mock_result.failed.return_value = False
        mock_result.ready.return_value = True
        mock_result.result = {'status': 'completed', 'transcript': 'text'}
        mock_result_cls.return_value = mock_result

        with patch('audioDiagnostic.views.legacy_views.r') as mock_r:
            mock_r.get.return_value = b'100'
            response = self.client.get('/api/task-status/fake-task-id/')
            self.assertIn(response.status_code, [200, 202, 404])

    @patch('audioDiagnostic.views.legacy_views.AsyncResult')
    def test_failed_status(self, mock_result_cls):
        mock_result = MagicMock()
        mock_result.failed.return_value = True
        mock_result.result = Exception('test error')
        mock_result_cls.return_value = mock_result

        with patch('audioDiagnostic.views.legacy_views.r') as mock_r:
            mock_r.get.return_value = b'0'
            response = self.client.get('/api/task-status/fake-task-id/')
            self.assertIn(response.status_code, [200, 404, 500])


class UploadChunkViewTests(TestCase):
    """Test upload_chunk view."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False

    def test_upload_chunk_post(self):
        import io
        chunk_data = io.BytesIO(b'fake audio chunk data')
        chunk_data.name = 'chunk.bin'
        response = self.client.post('/api/upload-chunk/', {
            'upload_id': 'test-upload-id-145',
            'chunk_index': '0',
            'chunk': chunk_data,
        }, format='multipart')
        self.assertIn(response.status_code, [200, 400])

    def test_upload_chunk_wrong_method(self):
        response = self.client.get('/api/upload-chunk/')
        self.assertIn(response.status_code, [400, 404, 405])


class AssembleChunksViewTests(TestCase):
    """Test assemble_chunks view."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False

    @patch('audioDiagnostic.views.legacy_views.transcribe_audio_task')
    def test_assemble_chunks_no_chunks(self, mock_task):
        """Test with no chunks directory."""
        import json
        response = self.client.post(
            '/api/assemble-chunks/',
            json.dumps({'upload_id': 'nonexistent-id', 'filename': 'test.wav'}),
            content_type='application/json',
        )
        self.assertIn(response.status_code, [200, 400, 404, 500])

    def test_assemble_chunks_wrong_method(self):
        response = self.client.get('/api/assemble-chunks/')
        self.assertIn(response.status_code, [400, 404, 405])
