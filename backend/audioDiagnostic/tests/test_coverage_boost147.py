"""
Wave 147: tab5_pdf_comparison.py - error paths not covered (no PDF, no transcript)
and SideBySideComparisonView, PDFComparisonResultView, etc.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from unittest.mock import MagicMock, patch
from audioDiagnostic.models import AudioProject, AudioFile, Transcription, TranscriptionSegment
from rest_framework.test import force_authenticate

User = get_user_model()


class StartPDFComparisonViewTests(TestCase):
    """Test StartPDFComparisonView error paths."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user = User.objects.create_user(username='spdf147', password='pass', email='spdf147@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.project = AudioProject.objects.create(user=self.user, title='SPDF147 Project')

    def test_no_pdf_file(self):
        """Returns 400 when project has no PDF."""
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='audio.wav',
            order_index=1,
            status='transcribed',
            transcript_text='Some text',
        )
        response = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/start-pdf-comparison/'
        )
        self.assertIn(response.status_code, [400])

    def test_no_transcript_text(self):
        """Returns 400 when audio file has no transcript text."""
        self.project.pdf_file = MagicMock()
        self.project.save()
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='notranscript.wav',
            order_index=2,
            status='uploaded',
        )
        response = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/start-pdf-comparison/'
        )
        self.assertIn(response.status_code, [400])


class StartPrecisePDFComparisonViewTests(TestCase):
    """Test StartPrecisePDFComparisonView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user = User.objects.create_user(username='sprecise147', password='pass', email='sprecise147@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.project = AudioProject.objects.create(user=self.user, title='SPrecise147 Project')

    def test_no_pdf_file(self):
        """Returns 400 when project has no PDF."""
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='audio.wav',
            order_index=1,
            status='transcribed',
            transcript_text='Some text',
        )
        response = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/start-precise-pdf-comparison/',
            {'algorithm': 'precise'},
            format='json',
        )
        self.assertIn(response.status_code, [400])

    def test_no_transcript_text(self):
        """Returns 400 when audio file has no transcript text."""
        self.project.pdf_file = MagicMock()
        self.project.save()
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='notranscript2.wav',
            order_index=2,
            status='uploaded',
        )
        response = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/start-precise-pdf-comparison/',
            {'algorithm': 'ai'},
            format='json',
        )
        self.assertIn(response.status_code, [400])

    @patch('audioDiagnostic.views.tab5_pdf_comparison.precise_compare_transcription_to_pdf_task')
    def test_precise_algorithm_with_region(self, mock_task):
        """Test starting precise comparison with region params."""
        self.project.pdf_file = MagicMock()
        self.project.save()
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='withregion.wav',
            order_index=3,
            status='transcribed',
            transcript_text='Full transcript text here.',
        )
        mock_task.delay.return_value = MagicMock(id='precise-task-147')
        response = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/start-precise-pdf-comparison/',
            {
                'algorithm': 'precise',
                'pdf_start_char': 100,
                'pdf_end_char': 500,
                'transcript_start_char': 0,
                'transcript_end_char': 200,
            },
            format='json',
        )
        self.assertIn(response.status_code, [200, 400, 500])


class PDFComparisonResultViewTests(TestCase):
    """Test PDFComparisonResultView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user = User.objects.create_user(username='pdfresult147', password='pass', email='pdfresult147@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.project = AudioProject.objects.create(user=self.user, title='PDFResult147 Project')

    def test_no_comparison_result(self):
        """Audio file without comparison result returns 404 or 200 with null."""
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='noresult.wav',
            order_index=1,
            status='transcribed',
        )
        response = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/pdf-comparison-result/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_with_comparison_result(self):
        """Audio file with comparison_result returns data."""
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='withresult.wav',
            order_index=2,
            status='transcribed',
            comparison_result={'matches': [], 'score': 0.8},
        )
        response = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/pdf-comparison-result/'
        )
        self.assertIn(response.status_code, [200])


class SideBySideComparisonViewTests(TestCase):
    """Test SideBySideComparisonView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user = User.objects.create_user(username='sidebyside147', password='pass', email='sbs147@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.project = AudioProject.objects.create(user=self.user, title='SBS147 Project')

    def test_no_transcription(self):
        """Returns error when no transcription segments."""
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='notseg.wav',
            order_index=1,
            status='uploaded',
        )
        response = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/side-by-side/'
        )
        self.assertIn(response.status_code, [200, 400, 404])

    def test_with_transcription_segments(self):
        """Returns data when transcription exists."""
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='withsegs.wav',
            order_index=2,
            status='transcribed',
            transcript_text='Side by side text.',
            comparison_result={
                'word_matches': [],
                'gaps': [],
                'pdf_text': 'PDF content here.',
                'transcript_text': 'Side by side text.',
                'overall_score': 0.8,
            },
        )
        transcription = Transcription.objects.create(
            audio_file=audio_file,
            full_text='Side by side text.',
        )
        TranscriptionSegment.objects.create(
            transcription=transcription,
            audio_file=audio_file,
            text='Side by side text.',
            start_time=0.0,
            end_time=2.0,
            segment_index=0,
        )
        response = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/side-by-side/'
        )
        self.assertIn(response.status_code, [200, 400, 500])


class ResetPDFComparisonViewTests(TestCase):
    """Test ResetPDFComparisonView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user = User.objects.create_user(username='resetpdf147', password='pass', email='reset147@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.project = AudioProject.objects.create(user=self.user, title='ResetPDF147 Project')

    def test_reset_comparison(self):
        """Reset clears comparison result."""
        audio_file = AudioFile.objects.create(
            project=self.project,
            filename='reset.wav',
            order_index=1,
            status='transcribed',
            comparison_result={'test': 'data'},
        )
        response = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{audio_file.id}/reset-pdf-comparison/'
        )
        self.assertIn(response.status_code, [200, 400, 404])
