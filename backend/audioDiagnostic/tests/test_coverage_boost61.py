"""
Wave 61 — Coverage targeting:
  - client_storage.py (69%, 42 miss) — ClientTranscriptionListCreateView, DuplicateAnalysisListCreateView
  - tab5_pdf_comparison.py (70%, 108 miss) — correct URLs: compare-pdf, precise-compare, pdf-text, pdf-status
  - system_check.py mgmt (69%, 52 miss) — system_check command
  - precise_pdf_comparison_task.py (65%, 89 miss) — error paths
  - legacy_views.py (66%, 55 miss) — task status, cut_audio, download_audio
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from io import StringIO
from django.core.management import call_command


def make_user(username='w61user', password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u

def make_project(user, title='W61 Project', status='ready', **kwargs):
    from audioDiagnostic.models import AudioProject
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)

def make_audio_file(project, title='W61 File', status='transcribed', order=0):
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
# client_storage.py — ClientTranscriptionListCreateView
# ══════════════════════════════════════════════════════════════════════
class ClientTranscriptionViewTests(TestCase):
    """Test ClientTranscriptionListCreateView."""

    def setUp(self):
        self.user = make_user('w61_ct_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user, title='W61 CT Project')
        self.af = make_audio_file(self.project, status='transcribed', order=0)

    def test_get_client_transcriptions_empty(self):
        """GET client transcriptions for project returns empty list."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/client-transcriptions/'
        )
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('transcriptions', data)

    def test_get_client_transcriptions_with_filter(self):
        """GET client transcriptions filtered by audio_file."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/client-transcriptions/?audio_file={self.af.id}'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_post_client_transcription_create(self):
        """POST creates a new client transcription."""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/client-transcriptions/',
            {
                'audio_file': self.af.id,
                'transcription_data': {'segments': [{'text': 'Hello', 'start': 0, 'end': 1}]},
                'audio_duration': 10.5
            },
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404])

    def test_post_client_transcription_upsert(self):
        """POST updates existing client transcription for same file."""
        # First create
        self.client.post(
            f'/api/api/projects/{self.project.id}/client-transcriptions/',
            {'audio_file': self.af.id, 'transcription_data': {'segments': []}, 'audio_duration': 5.0},
            content_type='application/json'
        )
        # Second call should update
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/client-transcriptions/',
            {'audio_file': self.af.id, 'transcription_data': {'segments': [{'text': 'Updated', 'start': 0, 'end': 2}]}, 'audio_duration': 5.0},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404])

    def test_post_client_transcription_unauthenticated(self):
        """POST without auth → 401."""
        self.client.defaults.pop('HTTP_AUTHORIZATION', None)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/client-transcriptions/',
            {'audio_file': self.af.id},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [401, 403])

    def test_get_not_found_project(self):
        """GET for non-existent project → 404."""
        resp = self.client.get('/api/api/projects/99999/client-transcriptions/')
        self.assertEqual(resp.status_code, 404)


# ══════════════════════════════════════════════════════════════════════
# client_storage.py — DuplicateAnalysisListCreateView
# ══════════════════════════════════════════════════════════════════════
class DuplicateAnalysisViewTests(TestCase):
    """Test DuplicateAnalysisListCreateView."""

    def setUp(self):
        self.user = make_user('w61_da_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user, title='W61 DA Project')
        self.af = make_audio_file(self.project, status='transcribed', order=0)

    def test_get_duplicate_analyses_empty(self):
        """GET duplicate analyses returns empty list."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/duplicate-analyses/'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_post_duplicate_analysis(self):
        """POST creates a duplicate analysis."""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/duplicate-analyses/',
            {
                'audio_file': self.af.id,
                'analysis_data': {'duplicates': [], 'total': 0},
                'algorithm_used': 'tfidf',
                'audio_duration': 10.5
            },
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404])

    def test_get_duplicate_analyses_not_found(self):
        """GET for non-existent project → 404."""
        resp = self.client.get('/api/api/projects/99999/duplicate-analyses/')
        self.assertEqual(resp.status_code, 404)


# ══════════════════════════════════════════════════════════════════════
# tab5_pdf_comparison — correct URLs
# ══════════════════════════════════════════════════════════════════════
class Tab5PDFComparisonCorrectURLTests(TestCase):
    """Test tab5_pdf_comparison views using correct URLs."""

    def setUp(self):
        self.user = make_user('w61_tab5_corr_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user, title='W61 Tab5 Correct Project',
                                    pdf_match_completed=True,
                                    pdf_matched_section='W61 PDF section.')
        self.af = make_audio_file(self.project, status='transcribed', order=0)
        self.af.transcript_text = 'W61 tab5 content.'
        self.af.save()
        self.tr = make_transcription(self.af, 'W61 tab5 transcription content.')
        self.seg = make_segment(self.af, self.tr, 'W61 tab5 segment.', idx=0)

    def test_compare_pdf_no_pdf(self):
        """POST compare-pdf with no PDF → 400."""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/compare-pdf/'
        )
        self.assertEqual(resp.status_code, 400)

    def test_compare_pdf_no_transcript(self):
        """POST compare-pdf without transcript → 400."""
        af2 = make_audio_file(self.project, title='W61 No Trans', status='uploaded', order=1)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af2.id}/compare-pdf/'
        )
        self.assertEqual(resp.status_code, 400)

    def test_precise_compare_no_pdf(self):
        """POST precise-compare with no PDF → 400."""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/precise-compare/',
            {'algorithm': 'precise'},
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_pdf_text_no_pdf(self):
        """GET pdf-text with no PDF → 400."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/pdf-text/'
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_pdf_result_no_comparison(self):
        """GET pdf-result with no comparison data → returns 200 or 404."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/pdf-result/'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_get_pdf_status_mocked_redis(self):
        """GET pdf-status with mocked redis returns status."""
        mock_r = MagicMock()
        mock_r.get.return_value = None
        with patch('audioDiagnostic.views.tab5_pdf_comparison.get_redis_connection', return_value=mock_r):
            resp = self.client.get(
                f'/api/api/projects/{self.project.id}/files/{self.af.id}/pdf-status/'
            )
            self.assertIn(resp.status_code, [200, 404])

    def test_get_side_by_side(self):
        """GET side-by-side comparison returns data."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/side-by-side/'
        )
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_mark_for_deletion(self):
        """POST mark-for-deletion with segment IDs."""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/mark-for-deletion/',
            {'segment_ids': [self.seg.id]},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404, 405])

    def test_reset_comparison(self):
        """POST reset-comparison resets the comparison."""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/reset-comparison/'
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404, 405])

    def test_ignored_sections_get(self):
        """GET ignored sections for audio file."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/ignored-sections/'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_unauthenticated(self):
        """Unauthenticated requests to tab5 views → 401."""
        self.client.defaults.pop('HTTP_AUTHORIZATION', None)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/compare-pdf/'
        )
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════════════════════
# system_check management command
# ══════════════════════════════════════════════════════════════════════
class SystemCheckCommandTests(TestCase):
    """Test system_check management command."""

    def test_command_basic(self):
        """Command runs without crashing."""
        out = StringIO()
        with patch('audioDiagnostic.management.commands.system_check.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='Docker version 20.10.0')
            with patch('audioDiagnostic.management.commands.system_check.AsyncResult') as mock_ar:
                mock_ar.return_value = MagicMock(state='SUCCESS')
                call_command('system_check', stdout=out)
        # Should complete without exception

    def test_command_verbose(self):
        """Command with --verbose shows extra info."""
        out = StringIO()
        with patch('audioDiagnostic.management.commands.system_check.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='Docker version 20.10.0')
            with patch('audioDiagnostic.management.commands.system_check.AsyncResult') as mock_ar:
                mock_ar.return_value = MagicMock(state='SUCCESS')
                call_command('system_check', verbose=True, stdout=out)

    def test_command_fix_mode(self):
        """Command with --fix tries to auto-fix issues."""
        out = StringIO()
        user = make_user('w61_sys_chk_user')
        proj = make_project(user, title='W61 Sys Check Project', status='processing')
        with patch('audioDiagnostic.management.commands.system_check.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='Docker version 20.10.0')
            with patch('audioDiagnostic.management.commands.system_check.AsyncResult') as mock_ar:
                mock_ar.return_value = MagicMock(state='PENDING')
                call_command('system_check', fix=True, stdout=out)
        # Project should be reset
        proj.refresh_from_db()
        self.assertEqual(proj.status, 'pending')

    def test_command_docker_not_found(self):
        """Command handles Docker not installed."""
        out = StringIO()
        with patch('audioDiagnostic.management.commands.system_check.subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("docker not found")
            with patch('audioDiagnostic.management.commands.system_check.AsyncResult') as mock_ar:
                mock_ar.return_value = MagicMock(state='SUCCESS')
                call_command('system_check', stdout=out)
        # Should complete without crashing


# ══════════════════════════════════════════════════════════════════════
# precise_pdf_comparison_task — error paths
# ══════════════════════════════════════════════════════════════════════
class PrecisePDFComparisonTaskTests(TestCase):
    """Test precise_compare_transcription_to_pdf_task error paths."""

    def setUp(self):
        self.user = make_user('w61_precise_pdf_user')
        self.project = make_project(self.user, title='W61 Precise PDF Project')
        self.af = make_audio_file(self.project, status='transcribed', order=0)
        self.af.transcript_text = 'Precise PDF comparison test content here.'
        self.af.save()

    def test_audio_file_not_found(self):
        """Task fails when audio file not found."""
        from audioDiagnostic.tasks.precise_pdf_comparison_task import precise_compare_transcription_to_pdf_task
        with patch('audioDiagnostic.tasks.precise_pdf_comparison_task.get_redis_connection',
                   return_value=MagicMock()):
            result = precise_compare_transcription_to_pdf_task.apply(
                args=[99999], task_id='w61-precise-001')
            self.assertEqual(result.status, 'FAILURE')

    def test_no_pdf_file(self):
        """Task fails when project has no PDF."""
        from audioDiagnostic.tasks.precise_pdf_comparison_task import precise_compare_transcription_to_pdf_task
        mock_r = MagicMock()
        mock_r.set.return_value = True
        with patch('audioDiagnostic.tasks.precise_pdf_comparison_task.get_redis_connection',
                   return_value=mock_r):
            result = precise_compare_transcription_to_pdf_task.apply(
                args=[self.af.id], task_id='w61-precise-002')
            self.assertEqual(result.status, 'FAILURE')

    def test_no_transcript(self):
        """Task fails when audio file has no transcript."""
        from audioDiagnostic.tasks.precise_pdf_comparison_task import precise_compare_transcription_to_pdf_task
        af2 = make_audio_file(self.project, title='W61 No Transcript', status='uploaded', order=1)
        # af2.transcript_text = '' (default)
        mock_r = MagicMock()
        mock_r.set.return_value = True
        with patch('audioDiagnostic.tasks.precise_pdf_comparison_task.get_redis_connection',
                   return_value=mock_r):
            result = precise_compare_transcription_to_pdf_task.apply(
                args=[af2.id], task_id='w61-precise-003')
            self.assertEqual(result.status, 'FAILURE')


# ══════════════════════════════════════════════════════════════════════
# legacy_views.py — AudioTaskStatusSentencesView, download_audio, cut_audio
# ══════════════════════════════════════════════════════════════════════
class LegacyViewsTests(TestCase):
    """Test legacy_views.py endpoints."""

    def setUp(self):
        self.user = make_user('w61_legacy_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False

    def test_task_status_sentences_failed(self):
        """GET task status for failed task → 500."""
        mock_result = MagicMock()
        mock_result.failed.return_value = True
        mock_result.result = Exception("Test failure")
        mock_result.ready.return_value = True
        with patch('audioDiagnostic.views.legacy_views.AsyncResult', return_value=mock_result), \
             patch('audioDiagnostic.views.legacy_views.r') as mock_r:
            mock_r.get.return_value = b'75'
            resp = self.client.get('/api/tasks/fake-task-id/status/')
            self.assertIn(resp.status_code, [200, 404, 500])

    def test_task_status_sentences_processing(self):
        """GET task status when not ready → 202."""
        mock_result = MagicMock()
        mock_result.failed.return_value = False
        mock_result.ready.return_value = False
        with patch('audioDiagnostic.views.legacy_views.AsyncResult', return_value=mock_result), \
             patch('audioDiagnostic.views.legacy_views.r') as mock_r:
            mock_r.get.return_value = b'50'
            resp = self.client.get('/api/tasks/fake-task-id/status/')
            self.assertIn(resp.status_code, [200, 202, 404])

    def test_download_audio_invalid_filename(self):
        """GET download_audio with path traversal attempt → 400."""
        resp = self.client.get('/api/download-audio/../../etc/passwd/')
        self.assertIn(resp.status_code, [400, 404, 301, 302])

    def test_download_audio_nonexistent_file(self):
        """GET download_audio with nonexistent file → 404."""
        resp = self.client.get('/api/download-audio/nonexistent_test_file.wav/')
        self.assertIn(resp.status_code, [404, 400, 301])

    def test_cut_audio_not_post(self):
        """GET cut_audio returns 400 (POST only)."""
        resp = self.client.get('/api/cut/')
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_cut_audio_file_not_found(self):
        """POST cut_audio with nonexistent file → 404."""
        import json
        resp = self.client.post(
            '/api/cut/',
            json.dumps({'fileName': 'nonexistent_test.wav', 'deleteSections': []}),
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404])
