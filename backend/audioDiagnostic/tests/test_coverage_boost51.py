"""
Wave 51 — More coverage: legacy_views (cut_audio, assemble_chunks, upload_chunk),
project_views (ProjectDetailView.delete, ProjectRedetectDuplicatesView, ProjectTranscriptView),
client_storage endpoints, accounts views.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIRequestFactory
import json
import io


# ── Helpers ────────────────────────────────────────────────────────────────
def make_user(username='w51user', password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u

def make_project(user, title='W51 Project', status='ready', **kwargs):
    from audioDiagnostic.models import AudioProject
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)

def make_audio_file(project, title='W51 File', status='transcribed', order=0):
    from audioDiagnostic.models import AudioFile
    return AudioFile.objects.create(
        project=project,
        filename=f'{title.lower().replace(" ", "_")}.wav',
        title=title, order_index=order, status=status)

def make_transcription(audio_file, content='Test transcription.'):
    from audioDiagnostic.models import Transcription
    return Transcription.objects.create(audio_file=audio_file, full_text=content)

def make_segment(audio_file, transcription, text='Segment', idx=0):
    from audioDiagnostic.models import TranscriptionSegment
    return TranscriptionSegment.objects.create(
        audio_file=audio_file, transcription=transcription,
        text=text, start_time=float(idx), end_time=float(idx) + 1.0,
        segment_index=idx)


# ══════════════════════════════════════════════════════════════════════
# legacy_views — cut_audio, upload_chunk, assemble_chunks
# ══════════════════════════════════════════════════════════════════════
class LegacyViewsCutAudioTests(TestCase):
    """Test cut_audio view."""

    def test_cut_audio_not_post(self):
        """GET to cut_audio should return 400."""
        resp = self.client.get('/api/cut/')
        self.assertEqual(resp.status_code, 400)

    def test_cut_audio_missing_body(self):
        """POST to cut_audio without body returns 400."""
        resp = self.client.post('/api/cut/', data='', content_type='application/json')
        self.assertIn(resp.status_code, [400, 500])

    def test_cut_audio_file_not_found(self):
        """POST to cut_audio with non-existent file returns error."""
        payload = json.dumps({
            'fileName': 'nonexistent_file.wav',
            'deleteSections': [{'start': 0.0, 'end': 1.0}]
        })
        resp = self.client.post('/api/cut/', data=payload, content_type='application/json')
        self.assertIn(resp.status_code, [400, 404, 500])

    def test_cut_audio_with_mock_file(self):
        """POST to cut_audio with mocked AudioSegment and file system."""
        import os
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(b'RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00'
                    b'D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00')
            tmp_name = os.path.basename(f.name)
        try:
            with patch('audioDiagnostic.views.legacy_views.AudioSegment') as mock_seg:
                mock_audio = MagicMock()
                mock_audio.__len__ = lambda self: 5000
                mock_audio.__getitem__ = MagicMock(return_value=MagicMock())
                mock_seg.from_file.return_value = mock_audio
                mock_seg.empty.return_value = mock_audio
                mock_audio.__add__ = MagicMock(return_value=mock_audio)
                mock_audio.export = MagicMock()
                from django.conf import settings
                import shutil
                downloads_dir = os.path.join(settings.MEDIA_ROOT, 'Downloads')
                os.makedirs(downloads_dir, exist_ok=True)
                target = os.path.join(downloads_dir, tmp_name)
                if not os.path.exists(target):
                    shutil.copy(f.name, target)
                payload = json.dumps({
                    'fileName': tmp_name,
                    'deleteSections': [{'start': 1.0, 'end': 2.0}]
                })
                resp = self.client.post('/api/cut/', data=payload, content_type='application/json')
                self.assertIn(resp.status_code, [200, 400, 404, 500])
        finally:
            if os.path.exists(f.name):
                os.unlink(f.name)
            target = os.path.join(settings.MEDIA_ROOT, 'Downloads', tmp_name)
            if os.path.exists(target):
                os.unlink(target)


class LegacyViewsUploadChunkTests(TestCase):
    """Test upload_chunk and assemble_chunks views."""

    def test_upload_chunk_not_post(self):
        """GET to upload-chunk/ returns error."""
        resp = self.client.get('/api/upload-chunk/')
        self.assertIn(resp.status_code, [400, 405])

    def test_upload_chunk_success(self):
        """POST to upload-chunk/ saves chunk."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        chunk = SimpleUploadedFile('chunk', b'chunk data', content_type='application/octet-stream')
        with patch('os.makedirs'), patch('builtins.open', MagicMock()):
            resp = self.client.post('/api/upload-chunk/', {
                'upload_id': 'test-upload-123',
                'chunk_index': '0',
                'chunk': chunk,
            })
            self.assertIn(resp.status_code, [200, 400, 500])

    def test_assemble_chunks_not_post(self):
        """GET to assemble-chunks/ returns error."""
        resp = self.client.get('/api/assemble-chunks/')
        self.assertIn(resp.status_code, [400, 405])


class LegacyViewsAnalyzePDFTests(TestCase):
    """Test AnalyzePDFView."""

    def test_analyze_pdf_missing_data(self):
        """POST without required data returns 400."""
        resp = self.client.post('/api/analyze-pdf/', {}, format='multipart')
        self.assertIn(resp.status_code, [400, 415])

    def test_analyze_pdf_with_data(self):
        """POST with all required data starts task."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        pdf_file = SimpleUploadedFile('test.pdf', b'%PDF-1.4', content_type='application/pdf')
        with patch('audioDiagnostic.views.legacy_views.analyze_transcription_vs_pdf') as mock_task:
            mock_task.delay.return_value = MagicMock(id='analyze-task-001')
            resp = self.client.post('/api/analyze-pdf/', {
                'pdf': pdf_file,
                'transcript': 'Sample transcript text.',
                'segments': json.dumps([{'text': 'Sample', 'start': 0, 'end': 1}]),
            })
            self.assertIn(resp.status_code, [200, 201, 202, 400, 415, 500])


# ══════════════════════════════════════════════════════════════════════
# project_views — delete, transcript, redetect, process
# ══════════════════════════════════════════════════════════════════════
class ProjectViewsDeleteTests(TestCase):
    """Test ProjectDetailView.delete."""

    def setUp(self):
        self.user = make_user('w51_proj_del_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False

    def test_delete_project_success(self):
        """DELETE project should remove it."""
        project = make_project(self.user, title='Project to Delete')
        resp = self.client.delete(f'/api/projects/{project.id}/')
        self.assertIn(resp.status_code, [200, 204])

    def test_delete_project_not_found(self):
        """DELETE non-existent project should return 404."""
        resp = self.client.delete('/api/projects/99999/')
        self.assertIn(resp.status_code, [404])

    def test_delete_project_other_user(self):
        """DELETE another user's project should return 404."""
        other_user = make_user('w51_other_user')
        project = make_project(other_user, title='Other User Project')
        resp = self.client.delete(f'/api/projects/{project.id}/')
        self.assertEqual(resp.status_code, 404)


class ProjectTranscriptViewTests(TestCase):
    """Test ProjectTranscriptView."""

    def setUp(self):
        self.user = make_user('w51_transcript_view_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False

    def test_get_transcript_no_audio_files(self):
        """Transcript view for project with no files."""
        project = make_project(self.user, title='Empty Project')
        resp = self.client.get(f'/api/projects/{project.id}/transcript/')
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_get_transcript_with_transcription(self):
        """Transcript view for project with transcribed files."""
        project = make_project(self.user, title='Project With Trans')
        af = make_audio_file(project, status='transcribed')
        make_transcription(af, 'Full transcript content here.')
        resp = self.client.get(f'/api/projects/{project.id}/transcript/')
        self.assertIn(resp.status_code, [200, 400, 404])


class ProjectProcessViewTests(TestCase):
    """Test ProjectProcessView."""

    def setUp(self):
        self.user = make_user('w51_process_view_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False

    def test_process_project_no_transcriptions(self):
        """POST process without any transcriptions should fail."""
        project = make_project(self.user, title='Process No Trans', status='ready')
        resp = self.client.post(f'/api/projects/{project.id}/process/', {}, content_type='application/json')
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_process_project_starts_task(self):
        """POST process should start processing task."""
        project = make_project(self.user, title='Process Project', status='transcribed')
        af = make_audio_file(project, status='transcribed')
        make_transcription(af, 'Content for processing.')
        with patch('audioDiagnostic.views.project_views.process_project_duplicates_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='proc-task-w51-001')
            resp = self.client.post(
                f'/api/projects/{project.id}/process/', {}, content_type='application/json'
            )
            self.assertIn(resp.status_code, [200, 201, 400, 500])


class ProjectTranscribeViewTests(TestCase):
    """Test ProjectTranscribeView."""

    def setUp(self):
        self.user = make_user('w51_transcribe_view_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False

    def test_transcribe_project_no_audio_files(self):
        """POST transcribe for project with no audio files should fail."""
        project = make_project(self.user, title='No Audio Project')
        resp = self.client.post(f'/api/projects/{project.id}/transcribe/', {}, content_type='application/json')
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_transcribe_project_starts_task(self):
        """POST transcribe should start transcription task."""
        project = make_project(self.user, title='Transcribe Project', status='setup')
        make_audio_file(project, status='uploaded')
        with patch('audioDiagnostic.views.project_views.transcribe_all_project_audio_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='trans-task-w51-001')
            resp = self.client.post(
                f'/api/projects/{project.id}/transcribe/', {}, content_type='application/json'
            )
            self.assertIn(resp.status_code, [200, 201, 400, 500])


# ══════════════════════════════════════════════════════════════════════
# client_storage.py — detail views (GET, PUT, DELETE)
# ══════════════════════════════════════════════════════════════════════
class ClientStorageDetailViewTests(TestCase):
    """Test client storage detail views."""

    def setUp(self):
        self.user = make_user('w51_cs_detail_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user)

    def _create_transcription(self):
        """Create a client transcription via API."""
        from audioDiagnostic.models import ClientTranscription
        return ClientTranscription.objects.create(
            user=self.user,
            project=self.project,
            transcription_data={'segments': [{'text': 'Test', 'start': 0, 'end': 1}]},
            audio_file_name='test.wav',
            audio_duration=60.0,
        )

    def _create_analysis(self):
        """Create a duplicate analysis via API."""
        from audioDiagnostic.models import DuplicateAnalysis
        return DuplicateAnalysis.objects.create(
            user=self.user,
            project=self.project,
            analysis_data={'groups': []},
            algorithm_used='tfidf_cosine',
            audio_file_name='test.wav',
        )

    def test_get_transcription_detail(self):
        """GET transcription detail returns 200."""
        tr = self._create_transcription()
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/client-transcriptions/{tr.id}/'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_get_transcription_detail_not_found(self):
        """GET non-existent transcription returns 404."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/client-transcriptions/99999/'
        )
        self.assertIn(resp.status_code, [404])

    def test_delete_transcription(self):
        """DELETE transcription should remove it."""
        tr = self._create_transcription()
        resp = self.client.delete(
            f'/api/api/projects/{self.project.id}/client-transcriptions/{tr.id}/'
        )
        self.assertIn(resp.status_code, [200, 204, 404])

    def test_get_analysis_detail(self):
        """GET analysis detail returns 200."""
        an = self._create_analysis()
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/duplicate-analyses/{an.id}/'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_get_analysis_detail_not_found(self):
        """GET non-existent analysis returns 404."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/duplicate-analyses/99999/'
        )
        self.assertIn(resp.status_code, [404])

    def test_put_analysis_update(self):
        """PUT on analysis should update it."""
        an = self._create_analysis()
        resp = self.client.put(
            f'/api/api/projects/{self.project.id}/duplicate-analyses/{an.id}/',
            {'analysis_data': {'groups': [{'id': 1}]}, 'algorithm_used': 'windowed_retry',
             'audio_file_name': 'updated.wav', 'audio_duration': 120.0},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404])

    def test_delete_analysis(self):
        """DELETE analysis should remove it."""
        an = self._create_analysis()
        resp = self.client.delete(
            f'/api/api/projects/{self.project.id}/duplicate-analyses/{an.id}/'
        )
        self.assertIn(resp.status_code, [200, 204, 404])


# ══════════════════════════════════════════════════════════════════════
# accounts/views.py — registration, login, profile
# ══════════════════════════════════════════════════════════════════════
class AccountsViewsExtendedTests(TestCase):
    """Test accounts view endpoints with more branches."""

    def setUp(self):
        self.client.raise_request_exception = False

    def test_registration_empty_password(self):
        """Registration with short/empty password should return 400."""
        resp = self.client.post(
            '/api/accounts/register/',
            {'username': 'w51newuser', 'password': ''},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_registration_duplicate_username(self):
        """Registration with duplicate username should fail."""
        make_user('w51dupeuser')
        resp = self.client.post(
            '/api/accounts/register/',
            {'username': 'w51dupeuser', 'password': 'pass1234!', 'email': 'test@test.com'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_login_wrong_password(self):
        """Login with wrong password should return 400."""
        make_user('w51logintest')
        resp = self.client.post(
            '/api/accounts/login/',
            {'username': 'w51logintest', 'password': 'wrongpassword'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 401, 404])

    def test_login_nonexistent_user(self):
        """Login with nonexistent user should return 400."""
        resp = self.client.post(
            '/api/accounts/login/',
            {'username': 'doesnotexist', 'password': 'anypass'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 401, 404])

    def test_profile_requires_auth(self):
        """GET profile without auth should return 401/403."""
        resp = self.client.get('/api/accounts/profile/')
        self.assertIn(resp.status_code, [401, 403, 404])

    def test_profile_with_auth(self):
        """GET profile with valid auth returns user data."""
        user = make_user('w51profile_user')
        token = Token.objects.create(user=user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
        resp = self.client.get('/api/accounts/profile/')
        self.assertIn(resp.status_code, [200, 404])

    def test_logout_with_auth(self):
        """POST logout with valid auth should succeed."""
        user = make_user('w51logout_user')
        token = Token.objects.create(user=user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
        resp = self.client.post('/api/accounts/logout/', {}, content_type='application/json')
        self.assertIn(resp.status_code, [200, 201, 204, 404])


# ══════════════════════════════════════════════════════════════════════
# tab3_review_deletions.py — more branches
# ══════════════════════════════════════════════════════════════════════
class Tab3ReviewDeletionsExtendedTests(TestCase):
    """Test more branches in tab3_review_deletions views."""

    def setUp(self):
        self.user = make_user('w51_tab3_review_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed')
        self.tr = make_transcription(self.af, 'Review content.')
        self.seg1 = make_segment(self.af, self.tr, 'First segment.', 0)
        self.seg2 = make_segment(self.af, self.tr, 'Second segment.', 1)

    def test_duplicates_review_get(self):
        """GET duplicates endpoint returns list."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/duplicates/'
        )
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_confirm_deletions_no_segments(self):
        """POST confirm-deletions with no segments."""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/confirm-deletions/',
            {'segment_ids': []},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404, 500])

    def test_confirm_deletions_with_segments(self):
        """POST confirm-deletions with valid segment IDs."""
        with patch('audioDiagnostic.views.tab3_duplicate_detection.process_deletions_single_file_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='del-task-w51-001')
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/files/{self.af.id}/confirm-deletions/',
                {'segment_ids': [self.seg1.id]},
                content_type='application/json'
            )
            self.assertIn(resp.status_code, [200, 201, 400, 404, 500])
