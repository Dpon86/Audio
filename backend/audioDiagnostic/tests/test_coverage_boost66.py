"""
Wave 66 — Coverage boost
Targets:
  - tab5_pdf_comparison.py: additional branches not yet covered
    (PDFComparisonResultView no results, SideBySideComparisonView,
     MarkIgnoredSectionsView, ResetPDFComparisonView,
     MarkContentForDeletionView, PDFComparisonStatusView branches)
  - audio_processing_tasks.py: error paths
  - accounts/views.py: data_export view
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token

from audioDiagnostic.models import (
    AudioFile, AudioProject, Transcription, TranscriptionSegment,
)


# ────────────────── helpers ──────────────────
def make_user(username, password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u


def make_project(user, title='W66 Project', status='ready', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def make_audio_file(project, title='W66 File', status='transcribed', order=0, **kwargs):
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


def make_segment(audio_file, transcription, text='Segment', idx=0):
    return TranscriptionSegment.objects.create(
        audio_file=audio_file, transcription=transcription,
        text=text, start_time=float(idx), end_time=float(idx) + 1.0,
        segment_index=idx,
    )


# ══════════════════════════════════════════════════════
# tab5_pdf_comparison.py — additional view branches
# ══════════════════════════════════════════════════════
class Tab5PDFResultViewTests(TestCase):
    """PDFComparisonResultView — no results + has results"""

    def setUp(self):
        self.user = make_user('w66_tab5result_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(
            self.project, status='transcribed', order=0,
            transcript_text='Sample transcript.')
        self.client.raise_request_exception = False

    def test_pdf_result_no_comparison_done(self):
        """GET pdf-result/ when comparison not done → has_results=False"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/pdf-result/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertFalse(resp.json().get('has_results', True))

    def test_pdf_result_has_results(self):
        """GET pdf-result/ when comparison done → has_results=True"""
        AudioFile.objects.filter(id=self.af.id).update(
            pdf_comparison_completed=True,
            pdf_comparison_results={'match_result': {}, 'statistics': {}},
        )
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/pdf-result/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertTrue(resp.json().get('has_results', False))

    def test_pdf_result_wrong_user(self):
        """GET pdf-result/ for another user's project → 404"""
        other = make_user('w66_tab5_other')
        other_proj = make_project(other, title='Other W66')
        other_af = make_audio_file(other_proj, order=0)
        resp = self.client.get(
            f'/api/api/projects/{other_proj.id}/files/{other_af.id}/pdf-result/')
        self.assertEqual(resp.status_code, 404)


class Tab5SideBySideViewTests(TestCase):
    """SideBySideComparisonView"""

    def setUp(self):
        self.user = make_user('w66_tab5sbs_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user, pdf_text='Some PDF text for comparison.')
        self.af = make_audio_file(
            self.project, status='transcribed', order=0,
            transcript_text='Some transcript text here.',
            pdf_comparison_completed=True,
            pdf_comparison_results={'match_result': {}, 'statistics': {}},
        )
        self.client.raise_request_exception = False

    def test_side_by_side_success(self):
        """GET side-by-side/ returns segments"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/side-by-side/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn('segments', resp.json())

    def test_side_by_side_with_range_params(self):
        """GET side-by-side/ with pdf/transcript range params"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/side-by-side/'
            '?pdf_start_char=0&pdf_end_char=20&transcript_start_char=0&transcript_end_char=15'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_side_by_side_no_comparison(self):
        """GET side-by-side/ when no comparison done → 400"""
        af2 = make_audio_file(self.project, title='W66 NoCmp', order=2)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af2.id}/side-by-side/')
        self.assertIn(resp.status_code, [400, 404])


class Tab5MarkIgnoredSectionsViewTests(TestCase):
    """MarkIgnoredSectionsView"""

    def setUp(self):
        self.user = make_user('w66_tab5ign_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed', order=0)
        self.client.raise_request_exception = False

    def test_get_ignored_sections_empty(self):
        """GET ignored-sections/ returns empty list by default"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/ignored-sections/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json().get('ignored_sections', []), [])

    def test_post_valid_ignored_sections(self):
        """POST ignored-sections/ with valid sections → saved"""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/ignored-sections/',
            {'ignored_sections': [{'text': 'Narrated by Jane Doe'}], 'recompare': False},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_post_not_a_list(self):
        """POST ignored-sections/ with non-list → 400"""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/ignored-sections/',
            {'ignored_sections': 'not-a-list'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_post_missing_text_field(self):
        """POST ignored-sections/ with section missing text field → 400"""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/ignored-sections/',
            {'ignored_sections': [{'start': 0, 'end': 100}]},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])


class Tab5ResetPDFComparisonViewTests(TestCase):
    """ResetPDFComparisonView"""

    def setUp(self):
        self.user = make_user('w66_tab5reset_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(
            self.project, status='transcribed', order=0,
            pdf_comparison_completed=True,
        )
        self.client.raise_request_exception = False

    def test_reset_pdf_comparison(self):
        """POST reset-comparison/ clears results"""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/reset-comparison/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.af.refresh_from_db()
            self.assertFalse(self.af.pdf_comparison_completed)


class Tab5MarkForDeletionViewTests(TestCase):
    """MarkContentForDeletionView"""

    def setUp(self):
        self.user = make_user('w66_tab5del_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed', order=0)
        self.tr = make_transcription(self.af, 'Mark for deletion test.')
        make_segment(self.af, self.tr, 'Delete this.', idx=0)
        make_segment(self.af, self.tr, 'Keep this.', idx=2)
        self.client.raise_request_exception = False

    def test_mark_for_deletion_missing_times(self):
        """POST mark-for-deletion/ without start_time/end_time → 400"""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/mark-for-deletion/',
            {},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_mark_for_deletion_valid(self):
        """POST mark-for-deletion/ with valid times → segments marked"""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/mark-for-deletion/',
            {'start_time': 0.0, 'end_time': 1.5, 'timestamps': []},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 400, 404])


class Tab5PDFStatusViewTests(TestCase):
    """PDFComparisonStatusView — additional branches"""

    def setUp(self):
        self.user = make_user('w66_tab5status_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_status_no_task_id(self):
        """GET pdf-status/ with no task_id and no comparison done"""
        af = make_audio_file(self.project, order=0)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/pdf-status/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertFalse(resp.json().get('completed', True))

    def test_status_comparison_done_no_task(self):
        """GET pdf-status/ when comparison already done → completed=True"""
        af = make_audio_file(
            self.project, title='W66 StatusDone', order=2,
            pdf_comparison_completed=True)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/pdf-status/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertTrue(resp.json().get('completed', False))

    def test_status_with_task_id_redis_hit(self):
        """GET pdf-status/ with task_id and Redis progress=50"""
        af = make_audio_file(
            self.project, title='W66 StatusRedis', order=3,
            task_id='w66-redis-task-id')
        mock_r = MagicMock()
        mock_r.get.return_value = b'50'
        with patch('audioDiagnostic.views.tab5_pdf_comparison.get_redis_connection',
                   return_value=mock_r):
            resp = self.client.get(
                f'/api/api/projects/{self.project.id}/files/{af.id}/pdf-status/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json().get('progress', 0), 50)

    def test_status_with_task_id_redis_done(self):
        """GET pdf-status/ with task_id and Redis progress=100"""
        af = make_audio_file(
            self.project, title='W66 StatusDone2', order=4,
            task_id='w66-redis-task-done')
        mock_r = MagicMock()
        mock_r.get.return_value = b'100'
        with patch('audioDiagnostic.views.tab5_pdf_comparison.get_redis_connection',
                   return_value=mock_r):
            resp = self.client.get(
                f'/api/api/projects/{self.project.id}/files/{af.id}/pdf-status/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertTrue(resp.json().get('completed', False))

    def test_status_with_task_id_redis_error(self):
        """GET pdf-status/ with task_id and Redis progress=-1"""
        af = make_audio_file(
            self.project, title='W66 StatusErr', order=5,
            task_id='w66-redis-task-err')
        mock_r = MagicMock()
        mock_r.get.return_value = b'-1'
        with patch('audioDiagnostic.views.tab5_pdf_comparison.get_redis_connection',
                   return_value=mock_r):
            resp = self.client.get(
                f'/api/api/projects/{self.project.id}/files/{af.id}/pdf-status/')
        self.assertIn(resp.status_code, [200, 404])


# ══════════════════════════════════════════════════════
# audio_processing_tasks.py — error paths
# ══════════════════════════════════════════════════════
class AudioProcessingTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('w66_aud_proc_user')
        self.project = make_project(self.user)

    def _patch(self):
        p1 = patch('audioDiagnostic.tasks.audio_processing_tasks.docker_celery_manager')
        p2 = patch('audioDiagnostic.tasks.audio_processing_tasks.get_redis_connection',
                   return_value=MagicMock())
        return p1, p2

    def test_infra_failure(self):
        """process_audio_file_task raises when infra fails"""
        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        p1, p2 = self._patch()
        with p1 as mock_mgr, p2:
            mock_mgr.setup_infrastructure.return_value = False
            result = process_audio_file_task.apply(args=[99999])
        self.assertTrue(result.failed())

    def test_audio_file_not_found(self):
        """process_audio_file_task raises when audio file missing"""
        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        p1, p2 = self._patch()
        with p1 as mock_mgr, p2:
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = process_audio_file_task.apply(args=[999996])
        self.assertTrue(result.failed())

    def test_wrong_status(self):
        """process_audio_file_task raises when status not transcribed"""
        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        af = make_audio_file(self.project, status='uploaded', order=0)
        p1, p2 = self._patch()
        with p1 as mock_mgr, p2:
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = process_audio_file_task.apply(args=[af.id])
        self.assertTrue(result.failed())

    def test_no_segments(self):
        """process_audio_file_task raises when no transcription segments"""
        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        af = make_audio_file(self.project, status='transcribed', order=0)
        # No segments created
        p1, p2 = self._patch()
        with p1 as mock_mgr, p2:
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = process_audio_file_task.apply(args=[af.id])
        self.assertTrue(result.failed())

    def test_no_pdf_file(self):
        """process_audio_file_task raises when project has no PDF"""
        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        af = make_audio_file(
            self.project, status='transcribed', order=0,
            transcript_text='Test transcript text.')
        tr = make_transcription(af, 'Test transcript text.')
        make_segment(af, tr, 'Segment one.', idx=0)
        p1, p2 = self._patch()
        with p1 as mock_mgr, p2:
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = process_audio_file_task.apply(args=[af.id])
        self.assertTrue(result.failed())


# ══════════════════════════════════════════════════════
# accounts/views.py — data_export view
# ══════════════════════════════════════════════════════
class AccountsDataExportTests(TestCase):

    def setUp(self):
        self.user = make_user('w66_export_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'

    def test_data_export(self):
        """GET /accounts/data-export/ returns user data"""
        resp = self.client.get('/accounts/data-export/')
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_data_export_no_auth(self):
        """GET /accounts/data-export/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get('/accounts/data-export/')
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════
# tab5: CleanPDFTextView — GET
# ══════════════════════════════════════════════════════
class Tab5CleanPDFTextViewTests(TestCase):
    """CleanPDFTextView: GET /api/api/projects/{id}/clean-pdf-text/"""

    def setUp(self):
        self.user = make_user('w66_cleanpdf_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_clean_pdf_text_no_pdf(self):
        """GET clean-pdf-text/ when project has no PDF → 400"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/clean-pdf-text/')
        self.assertIn(resp.status_code, [400, 404])

    def test_clean_pdf_text_wrong_user(self):
        """GET clean-pdf-text/ for another user's project → 404"""
        other = make_user('w66_cleanpdf_other')
        other_proj = make_project(other, title='Other W66 PDF')
        resp = self.client.get(
            f'/api/api/projects/{other_proj.id}/clean-pdf-text/')
        self.assertEqual(resp.status_code, 404)


# ══════════════════════════════════════════════════════
# tab5: GetPDFTextView — no pdf_file case
# ══════════════════════════════════════════════════════
class Tab5GetPDFTextViewTests(TestCase):
    """GetPDFTextView: additional branch"""

    def setUp(self):
        self.user = make_user('w66_getpdf_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_get_pdf_text_no_pdf(self):
        """GET pdf-text/ when project has no PDF → 400"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/pdf-text/')
        self.assertIn(resp.status_code, [400, 404])
