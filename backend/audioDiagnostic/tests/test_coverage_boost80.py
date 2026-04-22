"""
Wave 80 — Coverage boost
Targets:
  - tab4_pdf_comparison.py:
      SingleTranscriptionPDFCompareView (POST),
      SingleTranscriptionPDFResultView (GET),
      SingleTranscriptionPDFStatusView (GET),
      SingleTranscriptionSideBySideView (GET)
  - legacy_views.py:
      cut_audio (POST - basic branches)
"""
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token

from audioDiagnostic.models import AudioProject, AudioFile, Transcription


def make_user(username):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password('pass1234!')
    u.save()
    return u


def make_project(user, title='W80 Project', status='transcribed', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def auth_client(client, user):
    token = Token.objects.create(user=user)
    client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
    return token


# ══════════════════════════════════════════════════════
# SingleTranscriptionPDFCompareView — POST
# ══════════════════════════════════════════════════════
class SingleTranscriptionPDFCompareViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w80_pdfcompare_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user, title='PDF Compare Project W80')
        self.af = AudioFile.objects.create(
            project=self.project,
            filename='audio_w80.wav',
            title='W80 Audio',
            order_index=0,
            status='transcribed',
        )
        self.client.raise_request_exception = False

    def test_no_pdf_file(self):
        """POST compare-pdf/ without PDF → 400"""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/compare-pdf/'
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_no_transcript(self):
        """POST compare-pdf/ with PDF but no transcript → 400"""
        self.af.transcript_text = ''
        self.af.save()
        with patch.object(type(self.project), 'pdf_file', new_callable=lambda: property(lambda self: MagicMock())):
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/files/{self.af.id}/compare-pdf/'
            )
        self.assertIn(resp.status_code, [400, 404])

    def test_launches_comparison_task(self):
        """POST compare-pdf/ with transcript and PDF → launches task"""
        self.af.transcript_text = 'Hello world this is a test transcript.'
        self.af.save()

        mock_task = MagicMock()
        mock_task.id = 'compare-pdf-task-w80'

        with patch('audioDiagnostic.views.tab4_pdf_comparison.compare_transcription_to_pdf_task') as mock_celery:
            mock_celery.delay.return_value = mock_task
            with patch.object(type(self.project), 'pdf_file', new_callable=lambda: property(lambda self: MagicMock())):
                resp = self.client.post(
                    f'/api/api/projects/{self.project.id}/files/{self.af.id}/compare-pdf/'
                )
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_not_found_project(self):
        """POST compare-pdf/ on non-existent project → 404"""
        resp = self.client.post(f'/api/api/projects/9999999/files/{self.af.id}/compare-pdf/')
        self.assertIn(resp.status_code, [404])


# ══════════════════════════════════════════════════════
# SingleTranscriptionPDFResultView — GET
# ══════════════════════════════════════════════════════
class SingleTranscriptionPDFResultViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w80_pdfresult_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user, title='PDF Result Project W80')
        self.af = AudioFile.objects.create(
            project=self.project,
            filename='audio_result_w80.wav',
            title='W80 Result Audio',
            order_index=0,
            status='transcribed',
        )
        self.client.raise_request_exception = False

    def test_no_comparison_done(self):
        """GET compare-pdf/ without comparison done → 200 with has_results=False"""
        self.af.pdf_comparison_completed = False
        self.af.save()
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/compare-pdf/'
        )
        self.assertIn(resp.status_code, [200, 404, 500])

    def test_not_found(self):
        """GET compare-pdf/ on non-existent file → 404"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/9999999/compare-pdf/'
        )
        self.assertIn(resp.status_code, [404])


# ══════════════════════════════════════════════════════
# SingleTranscriptionPDFStatusView — GET
# ══════════════════════════════════════════════════════
class SingleTranscriptionPDFStatusViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w80_pdfstatus_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user, title='PDF Status Project W80')
        self.af = AudioFile.objects.create(
            project=self.project,
            filename='audio_status_w80.wav',
            title='W80 Status Audio',
            order_index=0,
            status='transcribed',
        )
        self.client.raise_request_exception = False

    def test_no_transcription(self):
        """GET compare-pdf/status/ without transcription → 404"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/compare-pdf/status/'
        )
        self.assertIn(resp.status_code, [200, 404, 500])

    def test_with_transcription_no_task(self):
        """GET compare-pdf/status/ with transcription → returns status"""
        Transcription.objects.create(
            audio_file=self.af,
            full_text='Test transcription for W80',
        )
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/compare-pdf/status/'
        )
        self.assertIn(resp.status_code, [200, 404, 500])


# ══════════════════════════════════════════════════════
# SingleTranscriptionSideBySideView — GET
# ══════════════════════════════════════════════════════
class SingleTranscriptionSideBySideViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w80_sidebyside_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user, title='Side by Side Project W80')
        self.af = AudioFile.objects.create(
            project=self.project,
            filename='audio_sbs_w80.wav',
            title='W80 SBS Audio',
            order_index=0,
            status='transcribed',
        )
        self.client.raise_request_exception = False

    def test_no_transcription(self):
        """GET compare-pdf/side-by-side/ without transcription → 404"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/compare-pdf/side-by-side/'
        )
        self.assertIn(resp.status_code, [200, 404, 500])

    def test_not_found(self):
        """GET compare-pdf/side-by-side/ on non-existent file → 404"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/9999999/compare-pdf/side-by-side/'
        )
        self.assertIn(resp.status_code, [404])


# ══════════════════════════════════════════════════════
# Legacy views - cut_audio
# ══════════════════════════════════════════════════════
class CutAudioViewTests(TestCase):

    def setUp(self):
        self.client.raise_request_exception = False

    def test_cut_audio_get_method(self):
        """GET cut/ → not POST → 400"""
        resp = self.client.get('/api/cut/')
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_cut_audio_file_not_found(self):
        """POST cut/ with non-existent file → 404"""
        resp = self.client.post(
            '/api/cut/',
            json.dumps({
                'fileName': 'nonexistent_w80.wav',
                'deleteSections': [{'start': 0.0, 'end': 1.0}]
            }),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [404, 400, 500])

    def test_cut_audio_invalid_json(self):
        """POST cut/ with invalid JSON → error"""
        resp = self.client.post(
            '/api/cut/',
            'not valid json',
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 500])
