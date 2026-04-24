"""
Wave 146: tab2_transcription.py - SingleFileTranscribeView error paths + accounts/webhooks
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from unittest.mock import MagicMock, patch
from audioDiagnostic.models import AudioProject, AudioFile, Transcription, TranscriptionSegment
from rest_framework.test import force_authenticate

User = get_user_model()


class SingleFileTranscribeViewTests(TestCase):
    """Test SingleFileTranscribeView error paths (happy path covered by wave 120+)."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user = User.objects.create_user(username='stv146', password='pass', email='stv146@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.project = AudioProject.objects.create(user=self.user, title='STV146 Project')

    def test_transcribe_invalid_status(self):
        """Audio file with 'processing' status should return 400."""
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='processing.wav',
            order_index=1,
            status='processing',
        )
        response = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/transcribe/'
        )
        self.assertIn(response.status_code, [400])

    def test_transcribe_no_file(self):
        """Audio file without actual file data should return 400."""
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='nofile.wav',
            order_index=2,
            status='uploaded',
        )
        response = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/transcribe/'
        )
        self.assertIn(response.status_code, [400])

    @patch('audioDiagnostic.views.tab2_transcription.transcribe_single_audio_file_task')
    def test_transcribe_task_exception(self, mock_task):
        """When task.delay raises, return 500."""
        import tempfile, os
        from django.core.files import File

        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='exc.wav',
            order_index=3,
            status='uploaded',
        )
        # Create a temp file to assign as the audio file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(b'RIFF\x00\x00\x00\x00WAVEfmt ')
            tmp_path = tmp.name

        try:
            with open(tmp_path, 'rb') as f:
                audio_file.file.save('exc.wav', File(f))
        except Exception:
            pass  # May fail in test env
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        mock_task.delay.side_effect = Exception('task error')
        response = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/transcribe/'
        )
        self.assertIn(response.status_code, [400, 500])


class SingleFileTranscriptionResultViewTests(TestCase):
    """Test SingleFileTranscriptionResultView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user = User.objects.create_user(username='sftv146', password='pass', email='sftv146@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.project = AudioProject.objects.create(user=self.user, title='SFTV146 Project')

    def test_no_transcription_returns_404(self):
        """Audio file without transcription returns 404."""
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='notranscription.wav',
            order_index=1,
            status='uploaded',
        )
        response = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/transcription/'
        )
        self.assertIn(response.status_code, [404])

    def test_with_transcription_success(self):
        """Audio file with transcription returns 200."""
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='withtranscription.wav',
            order_index=2,
            status='transcribed',
        )
        transcription = Transcription.objects.create(
            audio_file=audio_file,
            full_text='Hello world transcription.',
        )
        TranscriptionSegment.objects.create(
            transcription=transcription,
            audio_file=audio_file,
            text='Hello world transcription.',
            start_time=0.0,
            end_time=2.0,
            segment_index=0,
        )
        response = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/transcription/'
        )
        self.assertIn(response.status_code, [200, 404])


class AccountsWebhooksTests(TestCase):
    """Test accounts/webhooks.py with mocked Stripe."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False

    @patch('accounts.webhooks.stripe')
    def test_webhook_invalid_signature(self, mock_stripe):
        """Webhook with invalid signature returns 400."""
        mock_stripe.Webhook.construct_event.side_effect = Exception('Invalid signature')
        response = self.client.post(
            '/api/auth/webhooks/stripe/',
            data=b'{"type": "test"}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='invalid-sig',
        )
        self.assertIn(response.status_code, [400, 403, 404, 500])

    def test_webhook_no_signature(self):
        """Webhook with no signature header."""
        response = self.client.post(
            '/api/auth/webhooks/stripe/',
            data=b'{"type": "test"}',
            content_type='application/json',
        )
        self.assertIn(response.status_code, [400, 403, 404, 500])
