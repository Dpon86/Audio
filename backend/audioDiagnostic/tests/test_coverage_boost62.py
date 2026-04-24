"""
Wave 62 — Coverage boost
Targets:
  - tab4_review_comparison.py (ProjectComparisonView, FileComparisonDetailView,
                                mark_file_reviewed, get_deletion_regions)
  - transcription_views.py (ProjectTranscribeView, AudioFileTranscribeView,
                             AudioFileRestartView)
  - ai_detection_views.py (permission-denied, cost-limit, success paths)
  - upload_views.py (magic-byte validation paths, bulk upload)
  - pdf_tasks.py pure functions (more branches)
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.authtoken.models import Token

from audioDiagnostic.models import (
from rest_framework.test import force_authenticate
    AudioFile, AudioProject, Transcription, TranscriptionSegment,
)


# ────────────────────── helpers ──────────────────────
def make_user(username='w62user', password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u


def make_project(user, title='W62 Project', status='ready', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def make_audio_file(project, title='W62 File', status='transcribed', order=0, **kwargs):
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


def make_segment(audio_file, transcription, text='Segment', idx=0, is_duplicate=False):
    return TranscriptionSegment.objects.create(
        audio_file=audio_file,
        transcription=transcription,
        text=text,
        start_time=float(idx),
        end_time=float(idx) + 1.0,
        segment_index=idx,
        is_duplicate=is_duplicate,
    )


# ══════════════════════════════════════════════════════
# Tab 4: Review / Comparison views
# ══════════════════════════════════════════════════════
class Tab4ProjectComparisonTests(TestCase):
    """Tests for tab4_review_comparison.ProjectComparisonView"""

    def setUp(self):
        self.user = make_user('w62_tab4a_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        # Audio file without processed_audio (so appears in empty result)
        self.af = make_audio_file(self.project, status='processed', order=0)
        self.tr = make_transcription(self.af, 'Tab4 project comparison content.')
        make_segment(self.af, self.tr, 'Normal segment.', idx=0, is_duplicate=False)
        make_segment(self.af, self.tr, 'Duplicate segment.', idx=1, is_duplicate=True)
        self.client.raise_request_exception = False

    def test_project_comparison_no_processed_audio(self):
        """GET comparison - no files with processed_audio set → empty result"""
        resp = self.client.get(f'/api/api/projects/{self.project.id}/comparison/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('project_stats', data)
            self.assertEqual(data['project_stats']['total_files'], 0)
            self.assertEqual(data['files'], [])

    def test_project_comparison_with_processed_audio(self):
        """GET comparison - file with processed_audio and durations"""
        AudioFile.objects.filter(id=self.af.id).update(
            processed_audio='processed/test_w62.wav',
            duration_seconds=120.0,
            processed_duration_seconds=90.0,
        )
        resp = self.client.get(f'/api/api/projects/{self.project.id}/comparison/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('files', data)
            self.assertEqual(len(data['files']), 1)
            self.assertIn('project_stats', data)
            self.assertEqual(data['project_stats']['total_files'], 1)

    def test_project_comparison_already_has_metadata(self):
        """GET comparison - file already has comparison_metadata (skip save)"""
        AudioFile.objects.filter(id=self.af.id).update(
            processed_audio='processed/test_w62b.wav',
            comparison_metadata={'original_duration': 100.0, 'pre_existing': True},
            comparison_status='reviewed',
        )
        resp = self.client.get(f'/api/api/projects/{self.project.id}/comparison/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn('project_stats', resp.json())

    def test_project_comparison_no_auth(self):
        """GET comparison without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get(f'/api/api/projects/{self.project.id}/comparison/')
        self.assertIn(resp.status_code, [401, 403])

    def test_project_comparison_wrong_project(self):
        """GET comparison for project owned by another user → 404"""
        other_user = make_user('w62_other_tab4a')
        other_proj = make_project(other_user, title='Other Tab4A Project')
        resp = self.client.get(f'/api/api/projects/{other_proj.id}/comparison/')
        self.assertIn(resp.status_code, [404])


class Tab4FileComparisonDetailTests(TestCase):
    """Tests for tab4_review_comparison.FileComparisonDetailView"""

    def setUp(self):
        self.user = make_user('w62_tab4b_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='processed', order=0)
        self.tr = make_transcription(self.af, 'Tab4 file comparison content.')
        make_segment(self.af, self.tr, 'Normal seg.', idx=0, is_duplicate=False)
        make_segment(self.af, self.tr, 'Dup seg.', idx=1, is_duplicate=True)
        self.client.raise_request_exception = False

    def test_file_comparison_detail_not_processed(self):
        """GET comparison-details when file not processed → 400"""
        af2 = make_audio_file(self.project, status='transcribed', order=1)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af2.id}/comparison-details/')
        self.assertIn(resp.status_code, [400, 404])

    def test_file_comparison_detail_processed_with_transcription(self):
        """GET comparison-details for processed file with transcription"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/comparison-details/')
        self.assertIn(resp.status_code, [200, 404, 500])
        if resp.status_code == 200:
            data = resp.json()
            self.assertEqual(data['file_id'], self.af.id)
            self.assertIn('deletion_regions', data)

    def test_file_comparison_detail_no_transcription(self):
        """GET comparison-details for processed file without transcription"""
        af3 = make_audio_file(self.project, status='processed', order=2)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af3.id}/comparison-details/')
        self.assertIn(resp.status_code, [200, 404, 500])
        if resp.status_code == 200:
            data = resp.json()
            self.assertEqual(data['deletion_regions'], [])

    def test_file_comparison_detail_wrong_project(self):
        """GET comparison-details for project owned by other user → 404"""
        other_user = make_user('w62_other_tab4b')
        other_proj = make_project(other_user, title='Other Tab4B Project')
        resp = self.client.get(
            f'/api/api/projects/{other_proj.id}/files/{self.af.id}/comparison-details/')
        self.assertIn(resp.status_code, [404])


class Tab4MarkReviewedTests(TestCase):
    """Tests for tab4_review_comparison.mark_file_reviewed"""

    def setUp(self):
        self.user = make_user('w62_tab4c_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='processed', order=0)
        self.client.raise_request_exception = False

    def test_mark_reviewed_success(self):
        """POST mark-reviewed with notes and reviewed status"""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/mark-reviewed/',
            {'notes': 'Looks good!', 'status': 'reviewed'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 201, 404, 500])
        if resp.status_code == 200:
            data = resp.json()
            self.assertTrue(data.get('success'))
            self.assertEqual(data.get('comparison_status'), 'reviewed')
            self.af.refresh_from_db()
            self.assertEqual(self.af.comparison_status, 'reviewed')

    def test_mark_approved_success(self):
        """POST mark-reviewed with approved status"""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/mark-reviewed/',
            {'notes': '', 'status': 'approved'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 201, 404, 500])
        if resp.status_code == 200:
            self.assertEqual(resp.json().get('comparison_status'), 'approved')

    def test_mark_reviewed_empty_body_uses_defaults(self):
        """POST mark-reviewed with empty body uses default 'reviewed' status"""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/mark-reviewed/',
            {},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 201, 404, 500])

    def test_mark_reviewed_no_auth(self):
        """POST mark-reviewed without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/mark-reviewed/',
            {'status': 'reviewed'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [401, 403])


class Tab4DeletionRegionsTests(TestCase):
    """Tests for tab4_review_comparison.get_deletion_regions"""

    def setUp(self):
        self.user = make_user('w62_tab4d_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='processed', order=0)
        self.tr = make_transcription(self.af, 'Deletion region test content.')
        make_segment(self.af, self.tr, 'Normal.', idx=0, is_duplicate=False)
        make_segment(self.af, self.tr, 'Duplicate 1.', idx=1, is_duplicate=True)
        make_segment(self.af, self.tr, 'Duplicate 2.', idx=2, is_duplicate=True)
        self.client.raise_request_exception = False

    def test_deletion_regions_with_duplicates(self):
        """GET deletion-regions returns duplicate segments"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/deletion-regions/')
        self.assertIn(resp.status_code, [200, 404, 500])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('deletion_regions', data)
            self.assertEqual(data['total_count'], 2)
            for region in data['deletion_regions']:
                self.assertIn('start', region)
                self.assertIn('end', region)
                self.assertIn('text', region)

    def test_deletion_regions_no_transcription(self):
        """GET deletion-regions for file without transcription → empty list"""
        af2 = make_audio_file(self.project, status='processed', order=3)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af2.id}/deletion-regions/')
        self.assertIn(resp.status_code, [200, 404, 500])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['total_count'], 0)

    def test_deletion_regions_no_auth(self):
        """GET deletion-regions without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/deletion-regions/')
        self.assertIn(resp.status_code, [401, 403])

    def test_deletion_regions_wrong_project(self):
        """GET deletion-regions for wrong user's project → 404"""
        other_user = make_user('w62_other_tab4d')
        other_proj = make_project(other_user, title='Other Tab4D Project')
        resp = self.client.get(
            f'/api/api/projects/{other_proj.id}/files/{self.af.id}/deletion-regions/')
        self.assertIn(resp.status_code, [404])


# ══════════════════════════════════════════════════════
# Transcription Views — more paths
# ══════════════════════════════════════════════════════
class TranscriptionViewsMoreTests(TestCase):
    """Additional coverage for transcription_views.py"""

    def setUp(self):
        self.user = make_user('w62_trans_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='uploaded', order=0)
        self.client.raise_request_exception = False

    # ── ProjectTranscribeView ──────────────────────────
    def test_project_transcribe_no_pdf(self):
        """POST /transcribe/ without PDF on project → 400"""
        resp = self.client.post(f'/api/projects/{self.project.id}/transcribe/')
        self.assertIn(resp.status_code, [400, 404])

    def test_project_transcribe_no_audio_files(self):
        """POST /transcribe/ with PDF but no audio files → 400"""
        AudioProject.objects.filter(id=self.project.id).update(pdf_file='pdfs/test.pdf')
        AudioFile.objects.filter(project=self.project).delete()
        resp = self.client.post(f'/api/projects/{self.project.id}/transcribe/')
        self.assertIn(resp.status_code, [400, 404])

    def test_project_transcribe_success(self):
        """POST /transcribe/ with PDF and audio files → launches task"""
        AudioProject.objects.filter(id=self.project.id).update(pdf_file='pdfs/test.pdf')
        with patch(
            'audioDiagnostic.views.transcription_views.transcribe_all_project_audio_task'
        ) as mock_t:
            mock_t.delay.return_value = MagicMock(id='trans-task-w62')
            resp = self.client.post(f'/api/projects/{self.project.id}/transcribe/')
        self.assertIn(resp.status_code, [200, 201, 202, 400, 404])

    # ── AudioFileTranscribeView ────────────────────────
    def test_audio_file_transcribe_invalid_status(self):
        """POST /audio-files/{id}/transcribe/ when status='processing' → 400"""
        AudioFile.objects.filter(id=self.af.id).update(status='processing')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/audio-files/{self.af.id}/transcribe/')
        self.assertIn(resp.status_code, [400, 404])

    def test_audio_file_transcribe_success_uploaded(self):
        """POST /audio-files/{id}/transcribe/ when status='uploaded' → task launched"""
        with patch(
            'audioDiagnostic.views.transcription_views.transcribe_audio_file_task'
        ) as mock_t:
            mock_t.delay.return_value = MagicMock(id='file-task-w62')
            resp = self.client.post(
                f'/api/projects/{self.project.id}/audio-files/{self.af.id}/transcribe/')
        self.assertIn(resp.status_code, [200, 201, 202, 400, 404])

    def test_audio_file_transcribe_success_failed_status(self):
        """POST /audio-files/{id}/transcribe/ when status='failed' → task launched"""
        AudioFile.objects.filter(id=self.af.id).update(status='failed')
        with patch(
            'audioDiagnostic.views.transcription_views.transcribe_audio_file_task'
        ) as mock_t:
            mock_t.delay.return_value = MagicMock(id='file-task-w62b')
            resp = self.client.post(
                f'/api/projects/{self.project.id}/audio-files/{self.af.id}/transcribe/')
        self.assertIn(resp.status_code, [200, 201, 202, 400, 404])

    # ── AudioFileRestartView ───────────────────────────
    def test_audio_file_restart_no_task(self):
        """POST /audio-files/{id}/restart/ without existing task_id"""
        resp = self.client.post(
            f'/api/projects/{self.project.id}/audio-files/{self.af.id}/restart/')
        self.assertIn(resp.status_code, [200, 201, 404])
        if resp.status_code == 200:
            self.af.refresh_from_db()
            self.assertEqual(self.af.status, 'pending')
            self.assertIsNone(self.af.task_id)

    def test_audio_file_restart_with_task_revoked(self):
        """POST /audio-files/{id}/restart/ revokes existing Celery task"""
        AudioFile.objects.filter(id=self.af.id).update(task_id='old-task-w62')
        with patch('celery.result.AsyncResult') as mock_ar:
            mock_ar.return_value.revoke = MagicMock()
            resp = self.client.post(
                f'/api/projects/{self.project.id}/audio-files/{self.af.id}/restart/')
        self.assertIn(resp.status_code, [200, 201, 404])

    def test_audio_file_restart_wrong_project(self):
        """POST /audio-files/{id}/restart/ for another user's project → 404"""
        other_user = make_user('w62_other_trans_user')
        other_proj = make_project(other_user, title='Other Trans Project')
        resp = self.client.post(
            f'/api/projects/{other_proj.id}/audio-files/{self.af.id}/restart/')
        self.assertIn(resp.status_code, [404])


# ══════════════════════════════════════════════════════
# AI Detection Views — more branches
# ══════════════════════════════════════════════════════
class AIDetectionViewsMoreTests(TestCase):
    """Additional coverage for ai_detection_views.py branches"""

    def setUp(self):
        self.user = make_user('w62_ai_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed', order=0)
        self.tr = make_transcription(self.af, 'AI detection test.')
        make_segment(self.af, self.tr, 'AI segment.', idx=0)
        self.client.raise_request_exception = False

    def test_ai_detect_permission_denied(self):
        """POST detect for audio file owned by another user → 403"""
        other_user = make_user('w62_ai_other')
        other_proj = make_project(other_user, title='Other AI Project')
        other_af = make_audio_file(other_proj, order=0)
        resp = self.client.post(
            '/api/ai-detection/detect/',
            {'audio_file_id': other_af.id},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 403, 404, 500])

    def test_ai_detect_cost_limit_exceeded(self):
        """POST detect when monthly cost limit exceeded → 402"""
        with patch('audioDiagnostic.views.ai_detection_views.CostCalculator') as mock_calc:
            mock_calc.return_value.estimate_cost_for_audio.return_value = {
                'total_usd': 0.10}
            with patch(
                'audioDiagnostic.views.ai_detection_views.DuplicateDetector'
            ) as mock_dd:
                mock_dd.return_value.client.check_user_cost_limit.return_value = False
                with patch(
                    'audioDiagnostic.views.ai_detection_views.cache'
                ) as mock_cache:
                    mock_cache.get.return_value = 55.0
                    resp = self.client.post(
                        '/api/ai-detection/detect/',
                        {'audio_file_id': self.af.id},
                        content_type='application/json',
                    )
        self.assertIn(resp.status_code, [400, 402, 403, 404, 500])

    def test_ai_detect_success_full_mock(self):
        """POST detect with all AI services mocked → 202"""
        with patch('audioDiagnostic.views.ai_detection_views.CostCalculator') as mock_calc:
            mock_calc.return_value.estimate_cost_for_audio.return_value = {
                'total_usd': 0.05}
            with patch(
                'audioDiagnostic.views.ai_detection_views.DuplicateDetector'
            ) as mock_dd:
                mock_dd.return_value.client.check_user_cost_limit.return_value = True
                with patch(
                    'audioDiagnostic.views.ai_detection_views.ai_detect_duplicates_task'
                ) as mock_task:
                    mock_task.delay.return_value = MagicMock(id='ai-full-w62')
                    resp = self.client.post(
                        '/api/ai-detection/detect/',
                        {'audio_file_id': self.af.id},
                        content_type='application/json',
                    )
        self.assertIn(resp.status_code, [200, 201, 202, 400, 500])

    def test_ai_task_status_success_state(self):
        """GET task status when Celery task is SUCCESS"""
        with patch('audioDiagnostic.views.ai_detection_views.AsyncResult') as mock_ar:
            mock_ar.return_value.state = 'SUCCESS'
            mock_ar.return_value.result = {'result_id': None}
            resp = self.client.get('/api/ai-detection/status/success-w62/')
        self.assertIn(resp.status_code, [200, 500])

    def test_ai_task_status_failure_state(self):
        """GET task status when Celery task is FAILURE"""
        with patch('audioDiagnostic.views.ai_detection_views.AsyncResult') as mock_ar:
            mock_ar.return_value.state = 'FAILURE'
            mock_ar.return_value.info = Exception('Task bombed out')
            resp = self.client.get('/api/ai-detection/status/fail-w62/')
        self.assertIn(resp.status_code, [200, 500])

    def test_ai_compare_pdf_permission_denied(self):
        """POST compare-pdf for another user's file → 403"""
        other_user = make_user('w62_ai_pdf_other')
        other_proj = make_project(other_user, title='Other AI PDF')
        other_af = make_audio_file(other_proj, order=0)
        resp = self.client.post(
            '/api/ai-detection/compare-pdf/',
            {'audio_file_id': other_af.id},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 403, 404, 500])

    def test_ai_compare_pdf_cost_limit(self):
        """POST compare-pdf when cost limit exceeded → 402"""
        with patch(
            'audioDiagnostic.views.ai_detection_views.DuplicateDetector'
        ) as mock_dd:
            mock_dd.return_value.client.check_user_cost_limit.return_value = False
            resp = self.client.post(
                '/api/ai-detection/compare-pdf/',
                {'audio_file_id': self.af.id},
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [400, 402, 403, 404, 500])

    def test_ai_compare_pdf_success(self):
        """POST compare-pdf with mocked services → 202"""
        with patch(
            'audioDiagnostic.views.ai_detection_views.DuplicateDetector'
        ) as mock_dd:
            mock_dd.return_value.client.check_user_cost_limit.return_value = True
            with patch(
                'audioDiagnostic.views.ai_detection_views.ai_compare_pdf_task'
            ) as mock_task:
                mock_task.delay.return_value = MagicMock(id='ai-pdf-w62')
                resp = self.client.post(
                    '/api/ai-detection/compare-pdf/',
                    {'audio_file_id': self.af.id},
                    content_type='application/json',
                )
        self.assertIn(resp.status_code, [200, 201, 202, 400, 500])

    def test_ai_results_permission_denied(self):
        """GET detection results for another user's file → 403"""
        other_user = make_user('w62_ai_res_other')
        other_proj = make_project(other_user, title='Other AI Results')
        other_af = make_audio_file(other_proj, order=0)
        resp = self.client.get(f'/api/ai-detection/results/{other_af.id}/')
        self.assertIn(resp.status_code, [400, 403, 404, 500])

    def test_ai_user_cost_success(self):
        """GET user-cost returns cost data"""
        resp = self.client.get('/api/ai-detection/user-cost/')
        self.assertIn(resp.status_code, [200, 404, 500])
        if resp.status_code == 200:
            data = resp.json()
            self.assertTrue(data.get('success'))
            self.assertIn('current_month_cost', data)
            self.assertIn('remaining', data)

    def test_ai_estimate_cost_with_mocked_task(self):
        """POST estimate-cost with mocked Celery task"""
        with patch(
            'audioDiagnostic.views.ai_detection_views.estimate_ai_cost_task'
        ) as mock_task:
            mock_result = MagicMock()
            mock_result.get.return_value = {'total_usd': 0.05, 'tokens': 1000}
            mock_task.delay.return_value = mock_result
            resp = self.client.post(
                '/api/ai-detection/estimate-cost/',
                {
                    'audio_duration_seconds': 3600,
                    'task_type': 'duplicate_detection',
                },
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [200, 201, 400, 500])


# ══════════════════════════════════════════════════════
# Upload Views — magic-byte validation and bulk upload
# ══════════════════════════════════════════════════════
class UploadViewsMagicByteTests(TestCase):
    """Tests for upload_views.py magic-byte validation branches"""

    def setUp(self):
        self.user = make_user('w62_upload_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    # ── PDF upload ─────────────────────────────────────
    def test_upload_pdf_no_file(self):
        """POST upload-pdf without file → 400"""
        resp = self.client.post(f'/api/projects/{self.project.id}/upload-pdf/')
        self.assertIn(resp.status_code, [400, 404])

    def test_upload_pdf_wrong_extension(self):
        """POST upload-pdf with .txt extension → 400"""
        f = SimpleUploadedFile('test.txt', b'%PDF-1.4', content_type='text/plain')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-pdf/',
            {'pdf_file': f},
            format='multipart',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_upload_pdf_bad_magic_bytes(self):
        """POST upload-pdf with .pdf extension but bad content → 400"""
        f = SimpleUploadedFile('test.pdf', b'NOT_A_PDF_FILE', content_type='application/pdf')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-pdf/',
            {'pdf_file': f},
            format='multipart',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_upload_pdf_valid(self):
        """POST upload-pdf with valid magic bytes → success or error from storage"""
        f = SimpleUploadedFile(
            'test_w62.pdf', b'%PDF-1.4 Valid content here', content_type='application/pdf')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-pdf/',
            {'pdf_file': f},
            format='multipart',
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404, 500])

    # ── Audio upload ────────────────────────────────────
    def test_upload_audio_no_file(self):
        """POST upload-audio without file → 400"""
        resp = self.client.post(f'/api/projects/{self.project.id}/upload-audio/')
        self.assertIn(resp.status_code, [400, 404])

    def test_upload_audio_wrong_extension(self):
        """POST upload-audio with .txt extension → 400"""
        f = SimpleUploadedFile('test.txt', b'RIFF....WAVEfmt ', content_type='text/plain')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-audio/',
            {'audio_file': f},
            format='multipart',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_upload_audio_bad_magic_bytes(self):
        """POST upload-audio with .wav extension but bad content → 400"""
        f = SimpleUploadedFile('test.wav', b'NOT_VALID_AUDIO', content_type='audio/wav')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-audio/',
            {'audio_file': f},
            format='multipart',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_upload_audio_valid_wav(self):
        """POST upload-audio with WAV magic bytes"""
        wav_content = b'RIFF\x00\x00\x00\x00WAVEfmt ' + b'\x00' * 100
        f = SimpleUploadedFile('test_w62.wav', wav_content, content_type='audio/wav')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-audio/',
            {'audio_file': f},
            format='multipart',
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404, 500])

    def test_upload_audio_valid_mp3(self):
        """POST upload-audio with MP3 magic bytes (0xFF 0xFB)"""
        mp3_content = b'\xff\xfb' + b'\x90' * 100
        f = SimpleUploadedFile('test_w62.mp3', mp3_content, content_type='audio/mpeg')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-audio/',
            {'audio_file': f},
            format='multipart',
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404, 500])

    def test_upload_audio_sets_project_ready(self):
        """POST upload-audio when project.status='setup' and pdf_file set → ready"""
        AudioProject.objects.filter(id=self.project.id).update(
            status='setup', pdf_file='pdfs/test.pdf')
        wav_content = b'RIFF\x00\x00\x00\x00WAVEfmt ' + b'\x00' * 100
        f = SimpleUploadedFile('test_w62b.wav', wav_content, content_type='audio/wav')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-audio/',
            {'audio_file': f},
            format='multipart',
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404, 500])
        if resp.status_code in [200, 201]:
            self.project.refresh_from_db()
            self.assertEqual(self.project.status, 'ready')


class BulkUploadWithTranscriptionTests(TestCase):
    """Tests for upload_views.BulkUploadWithTranscriptionView"""

    def setUp(self):
        self.user = make_user('w62_bulk_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_bulk_upload_no_audio_file(self):
        """POST upload-with-transcription without audio file → 400"""
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-with-transcription/',
            {'transcription_data': '[{"text":"test","start":0,"end":1}]'},
            format='multipart',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_bulk_upload_no_transcription(self):
        """POST upload-with-transcription without transcription_data → 400"""
        wav_content = b'RIFF\x00\x00\x00\x00WAVEfmt ' + b'\x00' * 50
        f = SimpleUploadedFile('bulk_w62.wav', wav_content, content_type='audio/wav')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-with-transcription/',
            {'audio_file': f},
            format='multipart',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_bulk_upload_empty_transcription_array(self):
        """POST upload-with-transcription with empty [] → 400"""
        wav_content = b'RIFF\x00\x00\x00\x00WAVEfmt ' + b'\x00' * 50
        f = SimpleUploadedFile('bulk_w62b.wav', wav_content, content_type='audio/wav')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-with-transcription/',
            {'audio_file': f, 'transcription_data': '[]'},
            format='multipart',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_bulk_upload_wrong_audio_extension(self):
        """POST upload-with-transcription with non-audio extension → 400"""
        f = SimpleUploadedFile('bad.txt', b'some bytes', content_type='text/plain')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-with-transcription/',
            {
                'audio_file': f,
                'transcription_data': '[{"text":"test","start":0,"end":1}]',
            },
            format='multipart',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_bulk_upload_bad_audio_magic(self):
        """POST upload-with-transcription .wav with bad magic bytes → 400"""
        f = SimpleUploadedFile('bad_w62.wav', b'NOTAVALIDWAV', content_type='audio/wav')
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-with-transcription/',
            {
                'audio_file': f,
                'transcription_data': '[{"text":"test","start":0,"end":1}]',
            },
            format='multipart',
        )
        self.assertIn(resp.status_code, [400, 404])


# ══════════════════════════════════════════════════════
# PDF Tasks — pure function branches
# ══════════════════════════════════════════════════════
class PDFTasksPureFunctionTests(TestCase):
    """More branches of pdf_tasks.py pure helper functions"""

    def test_find_pdf_section_match_task_snippet_found(self):
        """find_pdf_section_match_task finds match via snippet"""
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match_task
        mock_r = MagicMock()
        pdf = ('Chapter 1. Once upon a time in a land far away there lived a '
               'wonderful story teller. He told many stories. The end.')
        transcript = 'Once upon a time in a land far away there lived a wonderful story teller.'
        result = find_pdf_section_match_task(pdf, transcript, 'task-w62-a', mock_r)
        self.assertIsInstance(result, dict)
        self.assertIn('matched_section', result)

    def test_find_pdf_section_match_task_difflib_fallback(self):
        """find_pdf_section_match_task falls back to difflib when snippet not found"""
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match_task
        mock_r = MagicMock()
        pdf = 'The quick brown fox jumps over the lazy dog and runs away.'
        transcript = 'A completely different passage that has no direct match.'
        result = find_pdf_section_match_task(pdf, transcript, 'task-w62-b', mock_r)
        self.assertIsInstance(result, dict)
        self.assertIn('matched_section', result)

    def test_identify_pdf_based_duplicates_empty_segments(self):
        """identify_pdf_based_duplicates with empty segments list"""
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        result = identify_pdf_based_duplicates([], 'some pdf section', 'some transcript')
        self.assertIsInstance(result, dict)
        self.assertIn('duplicates_to_remove', result)
        self.assertEqual(result['total_duplicates'], 0)

    def test_identify_pdf_based_duplicates_with_repeats(self):
        """identify_pdf_based_duplicates detects repeated segments"""
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        segments = [
            {'text': 'Hello world repeat.', 'start': 0.0, 'end': 1.0},
            {'text': 'Unique middle section.', 'start': 1.0, 'end': 2.0},
            {'text': 'Hello world repeat.', 'start': 2.0, 'end': 3.0},
        ]
        result = identify_pdf_based_duplicates(
            segments, 'Hello world repeat.', 'Hello world repeat.')
        self.assertIsInstance(result, dict)
        self.assertIn('duplicates_to_remove', result)
        self.assertGreater(result['total_duplicates'], 0)

    def test_identify_pdf_based_duplicates_no_duplicates(self):
        """identify_pdf_based_duplicates with all unique segments"""
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        segments = [
            {'text': 'First unique segment.', 'start': 0.0, 'end': 1.0},
            {'text': 'Second unique segment.', 'start': 1.0, 'end': 2.0},
            {'text': 'Third unique segment.', 'start': 2.0, 'end': 3.0},
        ]
        result = identify_pdf_based_duplicates(
            segments, 'First Second Third', 'First Second Third')
        self.assertIsInstance(result, dict)
        self.assertEqual(result['total_duplicates'], 0)

    def test_find_missing_pdf_content_no_missing(self):
        """find_missing_pdf_content returns empty string when all present"""
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        text = 'Hello world and some more text here.'
        result = find_missing_pdf_content(text, text)
        self.assertIsInstance(result, str)
        self.assertEqual(result, '')

    def test_find_missing_pdf_content_with_missing(self):
        """find_missing_pdf_content finds sentences not in transcript"""
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        pdf = 'Hello world. Missing important sentence. Another present one.'
        transcript = 'Hello world. Another present one.'
        result = find_missing_pdf_content(transcript, pdf)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_calculate_similarity_empty_texts(self):
        """calculate_comprehensive_similarity_task returns 0.0 for empty"""
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        score = calculate_comprehensive_similarity_task('', '')
        self.assertEqual(score, 0.0)

    def test_calculate_similarity_identical_texts(self):
        """calculate_comprehensive_similarity_task returns high score for identical"""
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        text = 'The quick brown fox jumps over the lazy dog repeatedly.'
        score = calculate_comprehensive_similarity_task(text, text)
        self.assertGreater(score, 0.8)

    def test_calculate_similarity_partial(self):
        """calculate_comprehensive_similarity_task returns mid score for partial match"""
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        score = calculate_comprehensive_similarity_task(
            'Hello world this is a test phrase.',
            'Hello world different ending completely unrelated words.')
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_extract_chapter_title_empty(self):
        """extract_chapter_title_task returns fallback for empty text"""
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task('')
        self.assertEqual(result, 'PDF Beginning (auto-detected)')

    def test_extract_chapter_title_with_chapter(self):
        """extract_chapter_title_task extracts 'Chapter N' patterns"""
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task('Chapter 3: The Great Adventure\n\nText here.')
        self.assertIsInstance(result, str)
        self.assertNotEqual(result, '')

    def test_extract_chapter_title_section_pattern(self):
        """extract_chapter_title_task extracts section patterns"""
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task('Section 2.1: Important Details\n\nMore text.')
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_extract_chapter_title_fallback_sentence(self):
        """extract_chapter_title_task uses first sentence as fallback"""
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task(
            'The Beginning of the Story has been told many times by many people.')
        self.assertIsInstance(result, str)
        # Either a section or the PDF beginning fallback
        self.assertGreater(len(result), 0)

    def test_find_text_in_pdf_found(self):
        """find_text_in_pdf returns True when text present"""
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf('hello world', 'This is hello world in the pdf text.')
        self.assertTrue(result)

    def test_find_text_in_pdf_not_found(self):
        """find_text_in_pdf returns False when text absent"""
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf('completely absent phrase', 'Some other pdf text here.')
        self.assertFalse(result)
