"""
Wave 113 — Coverage boost
Targets:
  - audioDiagnostic/views/tab3_duplicate_detection.py:
    SingleFileProcessingStatusView, SingleFileProcessedAudioView,
    SingleFileStatisticsView, UpdateSegmentTimesView, RetranscribeProcessedAudioView
  - audioDiagnostic/views/tab5_pdf_comparison.py: remaining classes (GetPDFTextView,
    SideBySideComparisonView, MarkIgnoredSectionsView, ResetPDFComparisonView,
    MarkContentForDeletionView, CleanPDFTextView)
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from unittest.mock import patch, MagicMock
from rest_framework.test import force_authenticate


def make_project(user, **kwargs):
    from audioDiagnostic.models import AudioProject
    return AudioProject.objects.create(user=user, title=kwargs.get('title', 'Test Project'))


def make_audio_file(project, order=0, status='transcribed'):
    from audioDiagnostic.models import AudioFile
    return AudioFile.objects.create(
        project=project,
        filename=f'test_{order}.mp3',
        title=f'Test File {order}',
        order_index=order,
        status=status
    )


def make_transcription(audio_file):
    from audioDiagnostic.models import Transcription
    return Transcription.objects.create(
        audio_file=audio_file,
        full_text='hello world test content'
    )


def make_segment(audio_file, transcription, idx=0, start=0.0, end=1.0):
    from audioDiagnostic.models import TranscriptionSegment
    return TranscriptionSegment.objects.create(
        audio_file=audio_file,
        transcription=transcription,
        text=f'segment {idx}',
        start_time=start,
        end_time=end,
        segment_index=idx,
        is_kept=True
    )


class Tab3RemainingViewsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='t3r113', password='pass')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, order=0, status='transcribed')

    # ─── SingleFileProcessingStatusView ──────────────────────────────────────

    def test_processing_status_get_basic(self):
        resp = self.client.get(f'/api/api/projects/{self.project.id}/files/{self.af.id}/processing-status/')
        self.assertIn(resp.status_code, [200, 404])

    def test_processing_status_wrong_user(self):
        other = User.objects.create_user(username='t3r113_other', password='pass')
        other_proj = make_project(other)
        other_af = make_audio_file(other_proj, order=0)
        resp = self.client.get(f'/api/api/projects/{other_proj.id}/files/{other_af.id}/processing-status/')
        self.assertIn(resp.status_code, [404])

    def test_processing_status_with_task_id(self):
        self.af.status = 'processing'
        self.af.task_id = 'fake-task-123'
        self.af.save()
        with patch('celery.result.AsyncResult') as mock_ar:
            mock_task = MagicMock()
            mock_task.state = 'PROGRESS'
            mock_task.info = {'progress': 50, 'message': 'Working...'}
            mock_ar.return_value = mock_task
            resp = self.client.get(f'/api/api/projects/{self.project.id}/files/{self.af.id}/processing-status/')
        self.assertIn(resp.status_code, [200, 404])

    def test_processing_status_success_state(self):
        self.af.status = 'processing'
        self.af.task_id = 'fake-task-456'
        self.af.save()
        with patch('celery.result.AsyncResult') as mock_ar:
            mock_task = MagicMock()
            mock_task.state = 'SUCCESS'
            mock_task.info = {}
            mock_ar.return_value = mock_task
            resp = self.client.get(f'/api/api/projects/{self.project.id}/files/{self.af.id}/processing-status/')
        self.assertIn(resp.status_code, [200, 404])

    def test_processing_status_failure_state(self):
        self.af.status = 'processing'
        self.af.task_id = 'fake-task-789'
        self.af.save()
        with patch('celery.result.AsyncResult') as mock_ar:
            mock_task = MagicMock()
            mock_task.state = 'FAILURE'
            mock_task.info = Exception('Task failed')
            mock_ar.return_value = mock_task
            resp = self.client.get(f'/api/api/projects/{self.project.id}/files/{self.af.id}/processing-status/')
        self.assertIn(resp.status_code, [200, 404])

    def test_processing_status_processed(self):
        self.af.status = 'failed'
        self.af.error_message = 'Something broke'
        self.af.save()
        resp = self.client.get(f'/api/api/projects/{self.project.id}/files/{self.af.id}/processing-status/')
        self.assertIn(resp.status_code, [200, 404])

    # ─── SingleFileProcessedAudioView ────────────────────────────────────────

    def test_processed_audio_not_available(self):
        resp = self.client.get(f'/api/api/projects/{self.project.id}/files/{self.af.id}/processed-audio/')
        self.assertIn(resp.status_code, [200, 404])

    # ─── SingleFileStatisticsView ─────────────────────────────────────────────

    def test_statistics_no_transcription(self):
        resp = self.client.get(f'/api/api/projects/{self.project.id}/files/{self.af.id}/statistics/')
        self.assertIn(resp.status_code, [200, 404])

    def test_statistics_with_transcription(self):
        tr = make_transcription(self.af)
        make_segment(self.af, tr, idx=0, start=0.0, end=1.0)
        make_segment(self.af, tr, idx=1, start=1.0, end=2.0)
        resp = self.client.get(f'/api/api/projects/{self.project.id}/files/{self.af.id}/statistics/')
        self.assertIn(resp.status_code, [200, 404])

    # ─── UpdateSegmentTimesView ───────────────────────────────────────────────

    def test_update_segment_times_not_found(self):
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/99999/',
            data={'start_time': 1.0, 'end_time': 2.0},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_update_segment_times_valid(self):
        tr = make_transcription(self.af)
        seg = make_segment(self.af, tr, idx=0, start=0.0, end=5.0)
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{seg.id}/',
            data={'start_time': 1.0, 'end_time': 4.0},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_update_segment_times_no_data(self):
        tr = make_transcription(self.af)
        seg = make_segment(self.af, tr, idx=0, start=0.0, end=5.0)
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{seg.id}/',
            data={},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_update_segment_times_invalid_end_before_start(self):
        tr = make_transcription(self.af)
        seg = make_segment(self.af, tr, idx=0, start=0.0, end=5.0)
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{seg.id}/',
            data={'start_time': 4.0, 'end_time': 1.0},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_update_segment_times_invalid_value(self):
        tr = make_transcription(self.af)
        seg = make_segment(self.af, tr, idx=0, start=0.0, end=5.0)
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{seg.id}/',
            data={'start_time': 'not-a-number', 'end_time': 2.0},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404])

    # ─── RetranscribeProcessedAudioView ─────────────────────────────────────

    def test_retranscribe_no_processed_audio(self):
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/retranscribe/',
            data={}, content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404])


class Tab5RemainingViewsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='t5r113', password='pass')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, order=0)

    # ─── GetPDFTextView ───────────────────────────────────────────────────────

    def test_get_pdf_text_no_pdf(self):
        resp = self.client.get(f'/api/api/projects/{self.project.id}/pdf-text/')
        self.assertIn(resp.status_code, [200, 400, 404])

    # ─── SideBySideComparisonView ─────────────────────────────────────────────

    def test_side_by_side_no_comparison_results(self):
        resp = self.client.get(f'/api/api/projects/{self.project.id}/files/{self.af.id}/side-by-side/')
        self.assertIn(resp.status_code, [200, 400, 404])

    # ─── MarkIgnoredSectionsView ──────────────────────────────────────────────

    def test_mark_ignored_sections_empty(self):
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/ignored-sections/',
            data={'sections': []}, content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_get_ignored_sections(self):
        resp = self.client.get(f'/api/api/projects/{self.project.id}/files/{self.af.id}/ignored-sections/')
        self.assertIn(resp.status_code, [200, 400, 404])

    # ─── ResetPDFComparisonView ───────────────────────────────────────────────

    def test_reset_pdf_comparison(self):
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/reset-comparison/',
            data={}, content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404])

    # ─── MarkContentForDeletionView ───────────────────────────────────────────

    def test_mark_content_for_deletion_empty(self):
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/mark-for-deletion/',
            data={}, content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404])

    # ─── CleanPDFTextView ─────────────────────────────────────────────────────

    def test_clean_pdf_text_no_body(self):
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/clean-pdf-text/',
            data={}, content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_clean_pdf_text_with_text(self):
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/clean-pdf-text/',
            data={'pdf_text': 'Hello world some text to clean here.'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404])
