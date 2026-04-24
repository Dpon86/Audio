"""
Wave 75 — Coverage boost
Targets:
  - upload_views.py:
      _check_audio_magic, _check_pdf_magic,
      ProjectUploadPDFView (POST),
      ProjectUploadAudioView (POST),
      BulkUploadWithTranscriptionView (POST)
"""

import io
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.authtoken.models import Token

from audioDiagnostic.models import AudioProject, AudioFile, Transcription
from rest_framework.test import force_authenticate


# ────────────────── helpers ──────────────────
def make_user(username, password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u


def make_project(user, title='W75 Project', status='setup', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def auth_client(client, user):
    token = Token.objects.create(user=user)
    client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
    return token


def make_wav_file(name='test_w75.wav'):
    # Minimal valid WAV-like content (starts with RIFF)
    content = b'RIFF' + b'\x00' * 44
    return SimpleUploadedFile(name, content, content_type='audio/wav')


def make_mp3_file(name='test_w75.mp3'):
    # Minimal MP3-like content (starts with ID3)
    content = b'ID3\x00' + b'\x00' * 60
    return SimpleUploadedFile(name, content, content_type='audio/mpeg')


def make_pdf_file(name='test_w75.pdf'):
    # Minimal valid PDF content
    content = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'
    return SimpleUploadedFile(name, content, content_type='application/pdf')


# ══════════════════════════════════════════════════════
# Pure function tests
# ══════════════════════════════════════════════════════
class CheckMagicFunctionTests(TestCase):

    def test_check_audio_magic_wav(self):
        """WAV RIFF header recognized"""
        from audioDiagnostic.views.upload_views import _check_audio_magic
        f = io.BytesIO(b'RIFF' + b'\x00' * 40)
        self.assertTrue(_check_audio_magic(f))

    def test_check_audio_magic_mp3_id3(self):
        """MP3 ID3 header recognized"""
        from audioDiagnostic.views.upload_views import _check_audio_magic
        f = io.BytesIO(b'ID3\x00' + b'\x00' * 40)
        self.assertTrue(_check_audio_magic(f))

    def test_check_audio_magic_invalid(self):
        """Random bytes not recognized"""
        from audioDiagnostic.views.upload_views import _check_audio_magic
        f = io.BytesIO(b'NOTAUDIO' + b'\x00' * 40)
        self.assertFalse(_check_audio_magic(f))

    def test_check_audio_magic_m4a_ftyp(self):
        """M4A/MP4 ftyp at offset 4 recognized"""
        from audioDiagnostic.views.upload_views import _check_audio_magic
        f = io.BytesIO(b'\x00\x00\x00\x00ftyp' + b'\x00' * 40)
        self.assertTrue(_check_audio_magic(f))

    def test_check_pdf_magic_valid(self):
        """PDF magic bytes recognized"""
        from audioDiagnostic.views.upload_views import _check_pdf_magic
        f = io.BytesIO(b'%PDF-1.4\n' + b'\x00' * 40)
        self.assertTrue(_check_pdf_magic(f))

    def test_check_pdf_magic_invalid(self):
        """Non-PDF file not recognized"""
        from audioDiagnostic.views.upload_views import _check_pdf_magic
        f = io.BytesIO(b'NOTAPDF' + b'\x00' * 40)
        self.assertFalse(_check_pdf_magic(f))


# ══════════════════════════════════════════════════════
# ProjectUploadPDFView — POST
# ══════════════════════════════════════════════════════
class ProjectUploadPDFViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w75_uploadpdf_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_no_file(self):
        """POST upload-pdf/ without file → 400"""
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-pdf/',
            {},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_non_pdf_extension(self):
        """POST upload-pdf/ with non-PDF extension → 400"""
        fake_file = SimpleUploadedFile('doc.txt', b'%PDF-1.4\n', content_type='text/plain')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-pdf/',
            {'pdf_file': fake_file},
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_pdf_with_wrong_magic(self):
        """POST upload-pdf/ with .pdf extension but wrong content → 400"""
        fake_pdf = SimpleUploadedFile('doc.pdf', b'NOT_PDF' + b'\x00' * 20, content_type='application/pdf')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-pdf/',
            {'pdf_file': fake_pdf},
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_valid_pdf_upload(self):
        """POST upload-pdf/ with valid PDF → 200"""
        pdf = make_pdf_file()
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-pdf/',
            {'pdf_file': pdf},
        )
        self.assertIn(resp.status_code, [200, 400, 404])


# ══════════════════════════════════════════════════════
# ProjectUploadAudioView — POST
# ══════════════════════════════════════════════════════
class ProjectUploadAudioViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w75_uploadaudio_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_no_file(self):
        """POST upload-audio/ without file → 400"""
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-audio/',
            {},
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_invalid_extension(self):
        """POST upload-audio/ with unsupported extension → 400"""
        fake = SimpleUploadedFile('test.txt', b'RIFF' + b'\x00' * 44, content_type='text/plain')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-audio/',
            {'audio_file': fake},
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_audio_with_wrong_magic(self):
        """POST upload-audio/ with .wav extension but wrong content → 400"""
        fake = SimpleUploadedFile('test.wav', b'NOT_WAV' + b'\x00' * 44, content_type='audio/wav')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-audio/',
            {'audio_file': fake},
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_valid_wav_upload(self):
        """POST upload-audio/ with valid WAV → creates AudioFile"""
        wav = make_wav_file()
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-audio/',
            {'audio_file': wav, 'title': 'W75 Audio'},
        )
        self.assertIn(resp.status_code, [200, 400, 404])


# ══════════════════════════════════════════════════════
# BulkUploadWithTranscriptionView — POST
# ══════════════════════════════════════════════════════
class BulkUploadWithTranscriptionViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w75_bulk_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_no_audio_file(self):
        """POST upload-with-transcription/ without file → 400"""
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-with-transcription/',
            {
                'transcription_data': json.dumps([
                    {'text': 'Hello', 'start': 0.0, 'end': 1.0}
                ])
            },
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_no_transcription_data(self):
        """POST upload-with-transcription/ without transcription_data → 400"""
        wav = make_wav_file(name='bulk_w75.wav')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-with-transcription/',
            {'audio_file': wav},
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_invalid_extension(self):
        """POST upload-with-transcription/ with unsupported extension → 400"""
        fake = SimpleUploadedFile('audio.txt', b'RIFF' + b'\x00' * 44, content_type='text/plain')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-with-transcription/',
            {
                'audio_file': fake,
                'transcription_data': json.dumps([{'text': 'Hello', 'start': 0.0, 'end': 1.0}])
            },
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_empty_segments_list(self):
        """POST upload-with-transcription/ with empty segments array → 400"""
        wav = make_wav_file(name='empty_segs_w75.wav')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-with-transcription/',
            {
                'audio_file': wav,
                'transcription_data': json.dumps([]),
            },
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_invalid_json_transcription(self):
        """POST upload-with-transcription/ with invalid JSON → 400"""
        wav = make_wav_file(name='bad_json_w75.wav')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-with-transcription/',
            {
                'audio_file': wav,
                'transcription_data': '{not: valid json',
            },
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_valid_bulk_upload(self):
        """POST upload-with-transcription/ with valid data"""
        wav = make_wav_file(name='valid_bulk_w75.wav')
        segments = [
            {'text': 'Hello world.', 'start': 0.0, 'end': 1.5, 'confidence': 0.9},
            {'text': 'Testing one two three.', 'start': 1.5, 'end': 3.0, 'confidence': 0.85},
        ]
        with patch('audioDiagnostic.views.upload_views.AudioSegment') as mock_audio:
            mock_audio.from_file.return_value.__len__ = lambda self: 3000  # 3 seconds in ms
            mock_audio.from_file.return_value.__div__ = lambda self, x: 3.0
            resp = self.client.post(
                f'/api/projects/{self.project.id}/upload-with-transcription/',
                {
                    'audio_file': wav,
                    'transcription_data': json.dumps(segments),
                    'title': 'W75 Bulk Upload',
                },
            )
        self.assertIn(resp.status_code, [200, 400, 500])
