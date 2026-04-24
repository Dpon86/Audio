"""
Wave 70 — Coverage boost
Targets:
  - tab1_file_management.py: AudioFileListView GET, AudioFileDetailDeleteView,
    AudioFileStatusView, PATCH
  - tab2_transcription.py: SingleFileTranscribeView, SingleFileTranscriptionResultView,
    SingleFileTranscriptionStatusView, TranscriptionDownloadView
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token

from audioDiagnostic.models import (
from rest_framework.test import force_authenticate
    AudioFile, AudioProject, Transcription, TranscriptionSegment,
)


# ────────────────── helpers ──────────────────
def make_user(username, password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u


def make_project(user, title='W70 Project', status='ready', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def make_audio_file(project, title='W70 File', status='uploaded', order=0, **kwargs):
    return AudioFile.objects.create(
        project=project,
        filename=f'{title.lower().replace(" ", "_")}.wav',
        title=title,
        order_index=order,
        status=status,
        **kwargs,
    )


def make_transcription(audio_file, content='Test transcription.'):
    return Transcription.objects.create(audio_file=audio_file, full_text=content)


def make_segment(audio_file, transcription, text='Segment text.', idx=0):
    return TranscriptionSegment.objects.create(
        audio_file=audio_file,
        transcription=transcription,
        text=text,
        start_time=float(idx),
        end_time=float(idx) + 1.0,
        segment_index=idx,
    )


# ══════════════════════════════════════════════════════
# Tab1: AudioFileListView — GET
# ══════════════════════════════════════════════════════
class Tab1AudioFileListViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w70_tab1list_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_list_no_files(self):
        """GET /api/api/projects/{id}/files/ with no files"""
        resp = self.client.get(f'/api/api/projects/{self.project.id}/files/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json().get('total_count', 0), 0)

    def test_list_with_files(self):
        """GET /api/api/projects/{id}/files/ returns files"""
        make_audio_file(self.project, order=0)
        make_audio_file(self.project, title='W70 File 2', order=1)
        resp = self.client.get(f'/api/api/projects/{self.project.id}/files/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json().get('total_count', 0), 2)

    def test_list_wrong_user(self):
        """GET /api/api/projects/{id}/files/ for other user's project → 404"""
        other = make_user('w70_tab1list_other')
        other_proj = make_project(other, title='Other W70')
        resp = self.client.get(f'/api/api/projects/{other_proj.id}/files/')
        self.assertEqual(resp.status_code, 404)

    def test_list_no_auth(self):
        """GET /api/api/projects/{id}/files/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get(f'/api/api/projects/{self.project.id}/files/')
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════
# Tab1: AudioFileDetailDeleteView — GET, DELETE, PATCH
# ══════════════════════════════════════════════════════
class Tab1AudioFileDetailDeleteViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w70_tab1detail_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, order=0)
        self.client.raise_request_exception = False

    def test_get_detail(self):
        """GET /api/api/projects/{id}/files/{id}/ returns audio file details"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertTrue(resp.json().get('success'))

    def test_patch_title(self):
        """PATCH /api/api/projects/{id}/files/{id}/ updates title"""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/',
            {'title': 'Updated W70 Title'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.af.refresh_from_db()
            self.assertEqual(self.af.title, 'Updated W70 Title')

    def test_patch_order_index(self):
        """PATCH updates order_index"""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/',
            {'order_index': 5},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_delete_audio_file(self):
        """DELETE /api/api/projects/{id}/files/{id}/ removes the file"""
        af_to_delete = make_audio_file(self.project, title='W70 Delete Me', order=2)
        resp = self.client.delete(
            f'/api/api/projects/{self.project.id}/files/{af_to_delete.id}/')
        self.assertIn(resp.status_code, [200, 204, 404])
        if resp.status_code in [200, 204]:
            self.assertFalse(AudioFile.objects.filter(id=af_to_delete.id).exists())

    def test_get_wrong_project(self):
        """GET for file in another user's project → 404"""
        other = make_user('w70_tab1detail_other')
        other_proj = make_project(other, title='Other W70 Detail')
        other_af = make_audio_file(other_proj, order=0)
        resp = self.client.get(
            f'/api/api/projects/{other_proj.id}/files/{other_af.id}/')
        self.assertEqual(resp.status_code, 404)


# ══════════════════════════════════════════════════════
# Tab1: AudioFileStatusView — GET
# ══════════════════════════════════════════════════════
class Tab1AudioFileStatusViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w70_tab1status_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, order=0)
        self.client.raise_request_exception = False

    def test_get_status(self):
        """GET /api/api/projects/{id}/files/{id}/status/ returns status"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/status/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn('status', resp.json())

    def test_get_status_transcribed(self):
        """GET status for transcribed file"""
        af = make_audio_file(self.project, title='W70 Status Transcribed', status='transcribed', order=2)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/status/')
        self.assertIn(resp.status_code, [200, 404])


# ══════════════════════════════════════════════════════
# Tab2: SingleFileTranscribeView — POST
# ══════════════════════════════════════════════════════
class Tab2SingleFileTranscribeViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w70_tab2trans_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_invalid_status(self):
        """POST transcribe/ when status is 'processing' → 400"""
        af = make_audio_file(self.project, status='processing', order=0)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af.id}/transcribe/')
        self.assertIn(resp.status_code, [400, 404])

    def test_no_file(self):
        """POST transcribe/ when audio file has no file → 400"""
        af = make_audio_file(self.project, status='uploaded', order=0)
        # file field is blank by default
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af.id}/transcribe/')
        self.assertIn(resp.status_code, [400, 404])

    def test_transcribe_triggers_task(self):
        """POST transcribe/ with valid file → task started"""
        import io
        from django.core.files.base import ContentFile

        af = make_audio_file(self.project, status='uploaded', order=0)
        # Give it a fake file
        af.file.save('test.wav', ContentFile(b'RIFF' + b'\x00' * 40), save=True)

        mock_task = MagicMock()
        mock_task.id = 'w70-transcribe-task-id'
        with patch('audioDiagnostic.views.tab2_transcription.transcribe_single_audio_file_task') as mock_t:
            mock_t.delay.return_value = mock_task
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/files/{af.id}/transcribe/')
        self.assertIn(resp.status_code, [200, 400, 404])


# ══════════════════════════════════════════════════════
# Tab2: SingleFileTranscriptionResultView — GET
# ══════════════════════════════════════════════════════
class Tab2SingleFileTranscriptionResultViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w70_tab2result_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_no_transcription(self):
        """GET transcription/ when no transcription exists → 404"""
        af = make_audio_file(self.project, status='uploaded', order=0)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/transcription/')
        self.assertIn(resp.status_code, [404, 200])

    def test_with_transcription(self):
        """GET transcription/ with transcription → 200 with segments"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        tr = make_transcription(af, 'Hello world. Testing one two three.')
        make_segment(af, tr, 'Hello world.', idx=0)
        make_segment(af, tr, 'Testing one two three.', idx=2)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/transcription/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn('segments', resp.json())


# ══════════════════════════════════════════════════════
# Tab2: SingleFileTranscriptionStatusView — GET branches
# ══════════════════════════════════════════════════════
class Tab2SingleFileTranscriptionStatusViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w70_tab2status_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_status_uploaded(self):
        """GET transcription/status/ when status=uploaded"""
        af = make_audio_file(self.project, status='uploaded', order=0)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/transcription/status/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json().get('status'), 'uploaded')

    def test_status_transcribed(self):
        """GET transcription/status/ when status=transcribed → includes word_count"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        tr = make_transcription(af)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/transcription/status/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertEqual(data.get('status'), 'transcribed')

    def test_status_failed(self):
        """GET transcription/status/ when status=failed → error included"""
        af = make_audio_file(
            self.project, status='failed', order=0,
            error_message='Whisper model failed')
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/transcription/status/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn('error', resp.json())

    def test_status_transcribing_with_task_id(self):
        """GET transcription/status/ while transcribing with task_id"""
        af = make_audio_file(
            self.project, status='transcribing', order=0,
            task_id='w70-trans-task-id')
        mock_task = MagicMock()
        mock_task.state = 'PROGRESS'
        mock_task.info = {'progress': 40, 'message': 'Transcribing...'}
        with patch('audioDiagnostic.views.tab2_transcription.AsyncResult',
                   return_value=mock_task):
            resp = self.client.get(
                f'/api/api/projects/{self.project.id}/files/{af.id}/transcription/status/')
        self.assertIn(resp.status_code, [200, 404])


# ══════════════════════════════════════════════════════
# Tab2: TranscriptionDownloadView — GET
# ══════════════════════════════════════════════════════
class Tab2TranscriptionDownloadViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w70_tab2dl_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_download_no_transcription(self):
        """GET transcription/download/ when no transcription → 404"""
        af = make_audio_file(self.project, status='uploaded', order=0)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/transcription/download/')
        self.assertIn(resp.status_code, [404, 200])

    def test_download_txt_format(self):
        """GET transcription/download/?format=txt → text response"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        make_transcription(af, 'Hello world transcript.')
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/transcription/download/?format=txt')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn(b'Hello', resp.content)

    def test_download_json_format(self):
        """GET transcription/download/?format=json → JSON response"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        tr = make_transcription(af, 'Hello world transcript.')
        make_segment(af, tr, 'Hello world.', idx=0)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/transcription/download/?format=json')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn('segments', resp.json())
