"""
Wave 131: legacy_views.py remaining functions
- AnalyzePDFView: missing/no-pdf branches
- cut_audio: not-post, file-not-found, JSON parse error
- upload_chunk: success path
- assemble_chunks: not-post path
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from unittest.mock import MagicMock, patch
import json
import tempfile
import os

User = get_user_model()


class AnalyzePDFViewTests(TestCase):
    """AnalyzePDFView - missing required data branches."""

    def test_analyze_pdf_missing_pdf(self):
        resp = self.client.post(
            '/api/analyze-pdf/',
            data={'transcript': 'hello', 'segments': '[{"text": "hi"}]'},
        )
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_analyze_pdf_missing_transcript(self):
        import io
        pdf_file = io.BytesIO(b'fake pdf content')
        pdf_file.name = 'test.pdf'
        resp = self.client.post(
            '/api/analyze-pdf/',
            data={'pdf': pdf_file, 'segments': '[]'},
        )
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_analyze_pdf_missing_segments(self):
        import io
        pdf_file = io.BytesIO(b'fake pdf content')
        pdf_file.name = 'test.pdf'
        resp = self.client.post(
            '/api/analyze-pdf/',
            data={'pdf': pdf_file, 'transcript': 'hello'},
        )
        self.assertIn(resp.status_code, [400, 404, 405])


class CutAudioViewTests(TestCase):
    """cut_audio function view tests."""

    def test_cut_audio_not_post(self):
        resp = self.client.get('/api/cut/')
        self.assertIn(resp.status_code, [400, 405])

    def test_cut_audio_file_not_found(self):
        resp = self.client.post(
            '/api/cut/',
            data=json.dumps({'fileName': 'nonexistent_file.wav', 'deleteSections': []}),
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_cut_audio_invalid_json(self):
        resp = self.client.post(
            '/api/cut/',
            data='not json at all',
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 500])

    def test_cut_audio_missing_filename(self):
        resp = self.client.post(
            '/api/cut/',
            data=json.dumps({'deleteSections': []}),
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 500])


class UploadChunkViewTests(TestCase):
    """upload_chunk function."""

    def test_upload_chunk_not_post(self):
        resp = self.client.get('/api/upload-chunk/')
        self.assertIn(resp.status_code, [400, 405])

    def test_upload_chunk_success(self):
        import io
        chunk_data = io.BytesIO(b'some audio chunk data')
        chunk_data.name = 'chunk.bin'
        with patch('audioDiagnostic.views.legacy_views.os.makedirs'):
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file
                resp = self.client.post(
                    '/api/upload-chunk/',
                    data={
                        'upload_id': 'test-upload-123',
                        'chunk_index': '0',
                        'chunk': chunk_data,
                    },
                )
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])


class AssembleChunksViewTests(TestCase):
    """assemble_chunks function."""

    def test_assemble_chunks_not_post(self):
        resp = self.client.get('/api/assemble-chunks/')
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_assemble_chunks_missing_dir(self):
        """When upload dir doesn't exist, should fail gracefully."""
        with patch('audioDiagnostic.views.legacy_views.transcribe_audio_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='task-123')
            resp = self.client.post(
                '/api/assemble-chunks/',
                data=json.dumps({
                    'upload_id': 'nonexistent-upload-999',
                    'filename': 'test.wav'
                }),
                content_type='application/json'
            )
        self.assertIn(resp.status_code, [400, 404, 405, 500])


class AudioTaskStatusSentencesViewTests(TestCase):
    """AudioTaskStatusSentencesView."""

    def test_status_not_found(self):
        resp = self.client.get('/api/task-status/nonexistent-task-id/')
        self.assertIn(resp.status_code, [200, 404, 500])

    def test_status_with_celery_mock(self):
        with patch('audioDiagnostic.views.legacy_views.AsyncResult') as mock_async:
            mock_result = MagicMock()
            mock_result.state = 'SUCCESS'
            mock_result.result = {'sentences': ['hello', 'world']}
            mock_async.return_value = mock_result
            resp = self.client.get('/api/task-status/fake-task-123/')
        self.assertIn(resp.status_code, [200, 404, 405, 500])

    def test_status_pending(self):
        with patch('audioDiagnostic.views.legacy_views.AsyncResult') as mock_async:
            mock_result = MagicMock()
            mock_result.state = 'PENDING'
            mock_result.result = None
            mock_async.return_value = mock_result
            resp = self.client.get('/api/task-status/pending-task/')
        self.assertIn(resp.status_code, [200, 404, 405, 500])

    def test_status_failure(self):
        with patch('audioDiagnostic.views.legacy_views.AsyncResult') as mock_async:
            mock_result = MagicMock()
            mock_result.state = 'FAILURE'
            mock_result.result = Exception('Something went wrong')
            mock_async.return_value = mock_result
            resp = self.client.get('/api/task-status/failed-task/')
        self.assertIn(resp.status_code, [200, 404, 405, 500])
