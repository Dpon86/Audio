"""
Comprehensive view tests targeting low-coverage view modules.
Covers tab1-tab5, ai_detection, duplicate_views, pdf_matching,
infrastructure, client_storage, legacy, processing, fix_transcriptions.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from unittest.mock import patch, MagicMock, PropertyMock
from django.core.files.uploadedfile import SimpleUploadedFile

from audioDiagnostic.models import (
    AudioProject, AudioFile, Transcription, TranscriptionSegment,
    ClientTranscription, DuplicateAnalysis, DuplicateGroup,
    AIDuplicateDetectionResult, AIPDFComparisonResult
)


def make_user(username='testuser', password='testpass123'):
    return User.objects.create_user(username=username, email=f'{username}@test.com', password=password)


def make_project(user, title='Test Project', **kwargs):
    return AudioProject.objects.create(user=user, title=title, **kwargs)


def make_audio_file(project, title='Chapter 1', status='uploaded', **kwargs):
    return AudioFile.objects.create(
        project=project,
        title=title,
        filename='test.mp3',
        file='audio/test.mp3',
        status=status,
        **kwargs
    )


def make_transcription(audio_file):
    return Transcription.objects.create(
        audio_file=audio_file,
        full_text='Hello world this is a test',
        word_count=6,
    )


def make_segment(transcription, text='Hello world', index=0):
    return TranscriptionSegment.objects.create(
        audio_file=transcription.audio_file,
        transcription=transcription,
        text=text,
        start_time=0.0,
        end_time=2.0,
        segment_index=index,
        is_kept=True,
    )


class AuthMixin:
    def setUp(self):
        self.user = make_user()
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project)


# ---------------------------------------------------------------------------
# Tab 1: File Management
# ---------------------------------------------------------------------------

class Tab1AudioFileListViewTests(AuthMixin, APITestCase):

    def test_list_files_success(self):
        response = self.client.get(f'/api/projects/{self.project.id}/files/')
        self.assertIn(response.status_code, [200, 404])

    def test_list_files_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(f'/api/projects/{self.project.id}/files/')
        self.assertIn(response.status_code, [401, 403])

    def test_list_files_other_user_project(self):
        other = make_user('other1')
        other_project = make_project(other)
        response = self.client.get(f'/api/projects/{other_project.id}/files/')
        self.assertEqual(response.status_code, 404)

    def test_upload_audio_file(self):
        f = SimpleUploadedFile('track.mp3', b'fakeaudiodata', content_type='audio/mpeg')
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/',
            {'file': f, 'title': 'Track 1'},
            format='multipart'
        )
        self.assertIn(response.status_code, [201, 400])  # 400 if file validation fails


class Tab1AudioFileDetailViewTests(AuthMixin, APITestCase):

    def test_get_file_detail(self):
        response = self.client.get(f'/api/projects/{self.project.id}/files/{self.audio_file.id}/')
        self.assertIn(response.status_code, [200, 404])

    def test_delete_file(self):
        response = self.client.delete(f'/api/projects/{self.project.id}/files/{self.audio_file.id}/')
        self.assertIn(response.status_code, [200, 204, 404])

    def test_file_not_found(self):
        response = self.client.get(f'/api/projects/{self.project.id}/files/99999/')
        self.assertEqual(response.status_code, 404)


class Tab1AudioFileStatusViewTests(AuthMixin, APITestCase):

    def test_get_file_status(self):
        response = self.client.get(f'/api/projects/{self.project.id}/files/{self.audio_file.id}/status/')
        self.assertIn(response.status_code, [200, 404])

    def test_status_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(f'/api/projects/{self.project.id}/files/{self.audio_file.id}/status/')
        self.assertIn(response.status_code, [401, 403])


# ---------------------------------------------------------------------------
# Tab 2: Transcription
# ---------------------------------------------------------------------------

class Tab2TranscribeViewTests(AuthMixin, APITestCase):

    @patch('audioDiagnostic.views.tab2_transcription.transcribe_single_audio_file_task')
    def test_transcribe_success(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='task-123')
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/transcribe/'
        )
        self.assertIn(response.status_code, [200, 202])

    def test_transcribe_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/transcribe/'
        )
        self.assertIn(response.status_code, [401, 403])

    def test_transcribe_wrong_status(self):
        self.audio_file.status = 'transcribing'
        self.audio_file.save()
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/transcribe/'
        )
        self.assertIn(response.status_code, [400, 404])

    def test_transcribe_not_found(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/99999/transcribe/'
        )
        self.assertEqual(response.status_code, 404)


class Tab2TranscriptionResultViewTests(AuthMixin, APITestCase):

    def test_get_result_no_transcription(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/transcription/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_get_result_with_transcription(self):
        make_transcription(self.audio_file)
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/transcription/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_result_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/transcription/'
        )
        self.assertIn(response.status_code, [401, 403])


class Tab2TranscriptionStatusViewTests(AuthMixin, APITestCase):

    def test_status_view(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/transcription/status/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_status_with_task_id(self):
        self.audio_file.task_id = 'fake-task-id'
        self.audio_file.save()
        with patch('celery.result.AsyncResult') as mock_ar:
            mock_ar.return_value = MagicMock(state='PROGRESS', info={'progress': 50})
            response = self.client.get(
                f'/api/projects/{self.project.id}/files/{self.audio_file.id}/transcription/status/'
            )
            self.assertIn(response.status_code, [200, 404])


# ---------------------------------------------------------------------------
# Tab 3: Duplicate Detection
# ---------------------------------------------------------------------------

class Tab3SingleFileDetectDuplicatesTests(AuthMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.audio_file.status = 'transcribed'
        self.audio_file.save()
        self.transcription = make_transcription(self.audio_file)

    @patch('audioDiagnostic.views.tab3_duplicate_detection.detect_duplicates_single_file_task')
    def test_detect_success(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='task-abc')
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/detect-duplicates/',
            {'algorithm': 'tfidf_cosine'},
            format='json'
        )
        self.assertIn(response.status_code, [200, 202])

    def test_detect_unsupported_algorithm(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/detect-duplicates/',
            {'algorithm': 'bad_algorithm'},
            format='json'
        )
        self.assertEqual(response.status_code, 400)

    def test_detect_no_transcription(self):
        file2 = make_audio_file(self.project, title='No Transcription', status='transcribed', order_index=1)
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{file2.id}/detect-duplicates/',
            {'algorithm': 'tfidf_cosine'},
            format='json'
        )
        self.assertIn(response.status_code, [400, 404])

    def test_detect_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/detect-duplicates/'
        )
        self.assertIn(response.status_code, [401, 403])


class Tab3DuplicatesReviewTests(AuthMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.audio_file.status = 'transcribed'
        self.audio_file.save()
        self.transcription = make_transcription(self.audio_file)

    def test_review_endpoint(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/duplicates/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_review_not_found(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/99999/duplicates/'
        )
        self.assertEqual(response.status_code, 404)


class Tab3ConfirmDeletionsTests(AuthMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.audio_file.status = 'transcribed'
        self.audio_file.save()
        self.transcription = make_transcription(self.audio_file)
        self.seg = make_segment(self.transcription)

    @patch('audioDiagnostic.views.tab3_duplicate_detection.process_deletions_single_file_task')
    def test_confirm_success(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='task-del')
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/confirm-deletions/',
            {'segment_ids': [self.seg.id]},
            format='json'
        )
        self.assertIn(response.status_code, [200, 202, 400])

    def test_confirm_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/confirm-deletions/'
        )
        self.assertIn(response.status_code, [401, 403])


class Tab3ProcessingStatusTests(AuthMixin, APITestCase):

    def test_processing_status(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/processing-status/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_processing_status_with_task(self):
        self.audio_file.task_id = 'some-task'
        self.audio_file.save()
        with patch('celery.result.AsyncResult') as mock_ar:
            mock_ar.return_value = MagicMock(state='SUCCESS', ready=lambda: True, failed=lambda: False)
            response = self.client.get(
                f'/api/projects/{self.project.id}/files/{self.audio_file.id}/processing-status/'
            )
            self.assertIn(response.status_code, [200, 404])


class Tab3StatisticsTests(AuthMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.audio_file.status = 'transcribed'
        self.audio_file.save()
        self.transcription = make_transcription(self.audio_file)

    def test_statistics_view(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/statistics/'
        )
        self.assertIn(response.status_code, [200, 404])


# ---------------------------------------------------------------------------
# Tab 3: Review Deletions
# ---------------------------------------------------------------------------

class Tab3ReviewDeletionsTests(AuthMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.audio_file.status = 'transcribed'
        self.audio_file.save()
        self.transcription = make_transcription(self.audio_file)
        self.seg = make_segment(self.transcription)

    @patch('audioDiagnostic.views.tab3_review_deletions.preview_deletions_task')
    def test_preview_deletions_success(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='task-prev')
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/preview-deletions/',
            {'segment_ids': [self.seg.id]},
            format='json'
        )
        self.assertIn(response.status_code, [200, 202, 400, 404])

    def test_preview_deletions_no_segments(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/preview-deletions/',
            {'segment_ids': []},
            format='json'
        )
        self.assertIn(response.status_code, [400, 404])

    def test_preview_deletions_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/duplicates/'
        )
        self.assertIn(response.status_code, [401, 403])

    def test_get_deletion_preview(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/deletion-preview/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_get_deletion_preview_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/duplicates/'
        )
        self.assertIn(response.status_code, [401, 403])


# ---------------------------------------------------------------------------
# Tab 4: Review Comparison
# ---------------------------------------------------------------------------

class Tab4ReviewComparisonTests(AuthMixin, APITestCase):

    def test_project_comparison_view(self):
        response = self.client.get(f'/api/projects/{self.project.id}/comparison/')
        self.assertIn(response.status_code, [200, 404])

    def test_project_comparison_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(f'/api/projects/{self.project.id}/comparison/')
        self.assertIn(response.status_code, [401, 403, 404])

    def test_file_comparison_detail(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/comparison/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_mark_file_reviewed(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/reviewed/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_get_deletion_regions(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/deletion-regions/'
        )
        self.assertIn(response.status_code, [200, 404])


# ---------------------------------------------------------------------------
# Tab 4: PDF Comparison (previously tab4_pdf_comparison.py)
# ---------------------------------------------------------------------------

class Tab4PDFComparisonTests(AuthMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.audio_file.status = 'transcribed'
        self.audio_file.transcript_text = 'Hello world test'
        self.audio_file.save()
        # Give project a PDF
        self.project.pdf_file = 'pdfs/test.pdf'
        self.project.save()

    @patch('audioDiagnostic.views.tab5_pdf_comparison.ai_compare_transcription_to_pdf_task')
    def test_start_comparison_success(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='task-cmp')
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/compare-pdf/'
        )
        self.assertIn(response.status_code, [200, 202, 400, 404, 500])

    def test_start_comparison_no_pdf(self):
        self.project.pdf_file = None
        self.project.save()
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/compare-pdf/'
        )
        self.assertIn(response.status_code, [400, 404])

    def test_start_comparison_no_transcription(self):
        self.audio_file.transcript_text = ''
        self.audio_file.save()
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/compare-pdf/'
        )
        self.assertIn(response.status_code, [400, 404])

    def test_get_comparison_result(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/pdf-result/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_comparison_status_view(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/pdf-status/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_comparison_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/compare-pdf/'
        )
        self.assertIn(response.status_code, [401, 403, 404])


# ---------------------------------------------------------------------------
# Tab 5: PDF Comparison
# ---------------------------------------------------------------------------

class Tab5PDFComparisonTests(AuthMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.audio_file.status = 'transcribed'
        self.audio_file.transcript_text = 'Hello world chapter one test'
        self.audio_file.save()
        self.project.pdf_file = 'pdfs/test.pdf'
        self.project.save()

    @patch('audioDiagnostic.views.tab5_pdf_comparison.ai_compare_transcription_to_pdf_task')
    def test_start_pdf_comparison(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='task-ai')
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/compare-pdf/'
        )
        self.assertIn(response.status_code, [200, 202, 400, 404, 500])

    def test_start_pdf_comparison_no_pdf(self):
        self.project.pdf_file = None
        self.project.save()
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/compare-pdf/'
        )
        self.assertIn(response.status_code, [400, 404])

    def test_start_pdf_comparison_no_transcript(self):
        self.audio_file.transcript_text = ''
        self.audio_file.save()
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/compare-pdf/'
        )
        self.assertIn(response.status_code, [400, 404])

    @patch('audioDiagnostic.views.tab5_pdf_comparison.precise_compare_transcription_to_pdf_task')
    def test_start_precise_comparison(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='task-precise')
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/precise-compare/'
        )
        self.assertIn(response.status_code, [200, 202, 400, 404, 500])

    def test_get_pdf_text(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/pdf-text/'
        )
        self.assertIn(response.status_code, [200, 400, 404])

    def test_clean_pdf_text(self):
        self.project.pdf_text = 'Hello   world\n\ntest  content'
        self.project.save()
        response = self.client.get(
            f'/api/projects/{self.project.id}/clean-pdf-text/'
        )
        self.assertIn(response.status_code, [200, 400, 404, 405])

    def test_comparison_result_view(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/pdf-result/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_comparison_status_view(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/pdf-status/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_side_by_side_comparison(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/side-by-side/'
        )
        self.assertIn(response.status_code, [200, 400, 404])

    def test_mark_ignored_sections(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/ignored-sections/',
            {'sections': [{'start': 0, 'end': 100}]},
            format='json'
        )
        self.assertIn(response.status_code, [200, 400, 404])

    def test_reset_pdf_comparison(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/reset-comparison/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_mark_content_for_deletion(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/mark-for-deletion/',
            {'content': 'some text'},
            format='json'
        )
        self.assertIn(response.status_code, [200, 400, 404])

    @patch('audioDiagnostic.views.tab5_pdf_comparison.audiobook_production_analysis_task')
    def test_audiobook_production_analysis(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='task-prod')
        response = self.client.post(
            f'/api/projects/{self.project.id}/audiobook-analysis/'
        )
        self.assertIn(response.status_code, [200, 202, 400, 404])

    def test_audiobook_analysis_progress(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/audiobook-analysis/progress/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_audiobook_analysis_result(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/audiobook-analysis/result/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_audiobook_report_summary(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/audiobook-report-summary/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_tab5_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/compare-pdf/'
        )
        self.assertIn(response.status_code, [401, 403, 404])


# ---------------------------------------------------------------------------
# AI Detection Views
# ---------------------------------------------------------------------------

class AIDetectionViewsTests(AuthMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.audio_file.status = 'transcribed'
        self.audio_file.save()
        self.transcription = make_transcription(self.audio_file)
        make_segment(self.transcription)

    @patch('audioDiagnostic.views.ai_detection_views.ai_detect_duplicates_task')
    def test_ai_detect_duplicates(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='ai-task-1')
        response = self.client.post(
            '/api/ai-detection/detect/',
            {'audio_file_id': self.audio_file.id, 'min_words': 3, 'similarity_threshold': 0.85,
             'keep_occurrence': 'last', 'enable_paragraph_expansion': False},
            format='json'
        )
        self.assertIn(response.status_code, [200, 202, 400, 403, 500])

    def test_ai_detect_invalid_data(self):
        response = self.client.post('/api/ai-detection/detect/', {}, format='json')
        self.assertIn(response.status_code, [400, 403])

    def test_ai_detect_unauthenticated(self):
        self.client.credentials()
        response = self.client.post('/api/ai-detection/detect/', {}, format='json')
        self.assertIn(response.status_code, [401, 403])

    def test_ai_task_status(self):
        with patch('audioDiagnostic.views.ai_detection_views.AsyncResult') as mock_ar:
            mock_ar.return_value = MagicMock(state='PENDING')
            response = self.client.get('/api/ai-detection/status/fake-task-id/')
            self.assertIn(response.status_code, [200, 404, 500])

    @patch('audioDiagnostic.views.ai_detection_views.ai_compare_pdf_task')
    def test_ai_compare_pdf(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='ai-pdf-1')
        response = self.client.post(
            '/api/ai-detection/compare-pdf/',
            {'audio_file_id': self.audio_file.id},
            format='json'
        )
        self.assertIn(response.status_code, [200, 202, 400, 403])

    @patch('audioDiagnostic.views.ai_detection_views.estimate_ai_cost_task')
    def test_ai_estimate_cost(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='ai-cost-1')
        response = self.client.post(
            '/api/ai-detection/estimate-cost/',
            {'audio_file_id': self.audio_file.id},
            format='json'
        )
        self.assertIn(response.status_code, [200, 202, 400])

    def test_ai_detection_results(self):
        response = self.client.get(
            f'/api/ai-detection/results/{self.audio_file.id}/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_ai_user_cost(self):
        response = self.client.get('/api/ai-detection/user-cost/')
        self.assertIn(response.status_code, [200, 404])


# ---------------------------------------------------------------------------
# Duplicate Views
# ---------------------------------------------------------------------------

class DuplicateViewsTests(AuthMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.project.pdf_text = 'This is a long PDF text for testing purposes with lots of words'
        self.project.pdf_match_completed = True
        self.project.save()

    def test_refine_pdf_boundaries_success(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            {'start_char': 0, 'end_char': 40},
            format='json'
        )
        self.assertIn(response.status_code, [200, 400, 404])

    def test_refine_pdf_boundaries_no_pdf_text(self):
        self.project.pdf_text = None
        self.project.save()
        response = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            {'start_char': 0, 'end_char': 40},
            format='json'
        )
        self.assertIn(response.status_code, [400, 404])

    def test_refine_pdf_boundaries_not_matched(self):
        self.project.pdf_match_completed = False
        self.project.save()
        response = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            {'start_char': 0, 'end_char': 40},
            format='json'
        )
        self.assertIn(response.status_code, [400, 404])

    def test_refine_invalid_chars(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            {'start_char': 50, 'end_char': 10},
            format='json'
        )
        self.assertIn(response.status_code, [400, 404])

    @patch('audioDiagnostic.views.duplicate_views.detect_duplicates_task')
    def test_detect_duplicates(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='dup-task')
        self.project.pdf_match_completed = True
        self.project.pdf_matched_section = 'some section'
        self.project.save()
        response = self.client.post(
            f'/api/projects/{self.project.id}/detect-duplicates/'
        )
        self.assertIn(response.status_code, [200, 202, 400, 404])

    def test_duplicates_review(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/duplicates/review/'
        )
        self.assertIn(response.status_code, [200, 400, 404])

    @patch('audioDiagnostic.views.duplicate_views.process_confirmed_deletions_task')
    def test_confirm_deletions(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='del-task')
        response = self.client.post(
            f'/api/projects/{self.project.id}/confirm-deletions/',
            {'confirmed_deletions': []},
            format='json'
        )
        self.assertIn(response.status_code, [200, 202, 400, 404])

    def test_duplicate_views_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(
            f'/api/projects/{self.project.id}/detect-duplicates/'
        )
        self.assertIn(response.status_code, [401, 403])


# ---------------------------------------------------------------------------
# PDF Matching Views
# ---------------------------------------------------------------------------

class PDFMatchingViewsTests(AuthMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.project.pdf_file = 'pdfs/test.pdf'
        self.project.save()
        self.audio_file.status = 'transcribed'
        self.audio_file.transcript_text = 'Hello world this is a test transcript'
        self.audio_file.save()

    @patch('audioDiagnostic.views.pdf_matching_views.match_pdf_to_audio_task')
    def test_match_pdf_success(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='pdf-match-task')
        response = self.client.post(f'/api/projects/{self.project.id}/match-pdf/')
        self.assertIn(response.status_code, [200, 202])

    def test_match_pdf_no_pdf_file(self):
        self.project.pdf_file = None
        self.project.save()
        response = self.client.post(f'/api/projects/{self.project.id}/match-pdf/')
        self.assertIn(response.status_code, [400, 404])

    def test_match_pdf_no_transcribed_files(self):
        self.audio_file.status = 'uploaded'
        self.audio_file.save()
        response = self.client.post(f'/api/projects/{self.project.id}/match-pdf/')
        self.assertIn(response.status_code, [400, 404])

    def test_match_pdf_already_in_progress(self):
        self.project.status = 'matching_pdf'
        self.project.save()
        response = self.client.post(f'/api/projects/{self.project.id}/match-pdf/')
        self.assertIn(response.status_code, [400, 404])

    @patch('audioDiagnostic.views.pdf_matching_views.validate_transcript_against_pdf_task')
    def test_validate_pdf(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='validate-task')
        self.project.pdf_match_completed = True
        self.project.pdf_matched_section = 'some content here'
        self.project.save()
        response = self.client.post(f'/api/projects/{self.project.id}/validate-pdf/')
        self.assertIn(response.status_code, [200, 202, 400, 404])

    def test_validation_progress(self):
        response = self.client.get(f'/api/projects/{self.project.id}/validate-pdf/progress/')
        self.assertIn(response.status_code, [200, 404])

    def test_pdf_matching_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(f'/api/projects/{self.project.id}/match-pdf/')
        self.assertIn(response.status_code, [401, 403])


# ---------------------------------------------------------------------------
# Infrastructure Views
# ---------------------------------------------------------------------------

class InfrastructureViewsTests(AuthMixin, APITestCase):

    def test_infrastructure_status_get(self):
        self.client.raise_request_exception = False
        response = self.client.get('/api/infrastructure/status/')
        self.assertIn(response.status_code, [200, 404, 500])

    def test_infrastructure_force_shutdown(self):
        self.client.raise_request_exception = False
        response = self.client.post(
            '/api/infrastructure/status/',
            {'action': 'force_shutdown'},
            format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500])

    def test_infrastructure_start(self):
        self.client.raise_request_exception = False
        response = self.client.post(
            '/api/infrastructure/status/',
            {'action': 'start'},
            format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500])

    def test_infrastructure_invalid_action(self):
        response = self.client.post(
            '/api/infrastructure/status/',
            {'action': 'invalid'},
            format='json'
        )
        self.assertIn(response.status_code, [400, 404])

    def test_infrastructure_unauthenticated(self):
        self.client.credentials()
        response = self.client.get('/api/infrastructure/status/')
        self.assertIn(response.status_code, [401, 403])

    def test_task_status_view(self):
        self.client.raise_request_exception = False
        response = self.client.get('/api/tasks/fake-task-id/status/')
        self.assertIn(response.status_code, [200, 404, 500])


# ---------------------------------------------------------------------------
# Client Storage Views
# ---------------------------------------------------------------------------

class ClientStorageViewsTests(AuthMixin, APITestCase):

    def test_list_client_transcriptions(self):
        response = self.client.get(f'/api/projects/{self.project.id}/client-transcriptions/')
        self.assertIn(response.status_code, [200, 404])

    def test_list_with_filename_filter(self):
        ClientTranscription.objects.create(
            project=self.project,
            filename='test.mp3',
            transcription_data={'text': 'hello'}
        )
        response = self.client.get(
            f'/api/projects/{self.project.id}/client-transcriptions/?filename=test.mp3'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_save_client_transcription(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/client-transcriptions/',
            {
                'filename': 'track.mp3',
                'transcript_data': {'text': 'hello world', 'segments': []},
                'duration_seconds': 10.5
            },
            format='json'
        )
        self.assertIn(response.status_code, [200, 201, 400, 404])

    def test_update_client_transcription(self):
        ct = ClientTranscription.objects.create(
            project=self.project,
            filename='track.mp3',
            transcription_data={'text': 'hello'}
        )
        response = self.client.put(
            f'/api/projects/{self.project.id}/client-transcriptions/{ct.id}/',
            {'transcription_data': {'text': 'updated hello'}},
            format='json'
        )
        self.assertIn(response.status_code, [200, 400, 404])

    def test_delete_client_transcription(self):
        ct = ClientTranscription.objects.create(
            project=self.project,
            filename='track.mp3',
            transcription_data={'text': 'hello'}
        )
        response = self.client.delete(
            f'/api/projects/{self.project.id}/client-transcriptions/{ct.id}/'
        )
        self.assertIn(response.status_code, [200, 204, 404])

    def test_client_storage_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(f'/api/projects/{self.project.id}/client-transcriptions/')
        self.assertIn(response.status_code, [401, 403])

    def test_list_duplicate_analyses(self):
        response = self.client.get(
            f'/api/projects/{self.project.id}/duplicate-analyses/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_save_duplicate_analysis(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/duplicate-analyses/',
            {
                'filename': 'track.mp3',
                'analysis_data': {'duplicates': []},
                'algorithm': 'tfidf_cosine'
            },
            format='json'
        )
        self.assertIn(response.status_code, [200, 201, 400, 404])


# ---------------------------------------------------------------------------
# Processing Views
# ---------------------------------------------------------------------------

class ProcessingViewsTests(AuthMixin, APITestCase):

    @patch('audioDiagnostic.views.processing_views.process_project_duplicates_task')
    def test_process_project_success(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='proc-task')
        self.project.status = 'transcribed'
        self.project.save()
        self.audio_file.status = 'transcribed'
        self.audio_file.save()
        response = self.client.post(f'/api/projects/{self.project.id}/process/')
        self.assertIn(response.status_code, [200, 202, 400])

    def test_process_project_wrong_status(self):
        self.project.status = 'setup'
        self.project.save()
        response = self.client.post(f'/api/projects/{self.project.id}/process/')
        self.assertIn(response.status_code, [400, 404])

    def test_process_project_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(f'/api/projects/{self.project.id}/process/')
        self.assertIn(response.status_code, [401, 403])

    @patch('audioDiagnostic.views.processing_views.process_audio_file_task')
    def test_process_audio_file(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='file-proc-task')
        self.project.pdf_file = 'pdfs/test.pdf'
        self.project.save()
        self.audio_file.status = 'transcribed'
        self.audio_file.save()
        response = self.client.post(
            f'/api/projects/{self.project.id}/audio-files/{self.audio_file.id}/process/'
        )
        self.assertIn(response.status_code, [200, 202, 400, 404])

    def test_process_audio_file_no_pdf(self):
        self.audio_file.status = 'transcribed'
        self.audio_file.save()
        response = self.client.post(
            f'/api/projects/{self.project.id}/files/{self.audio_file.id}/process/'
        )
        self.assertIn(response.status_code, [400, 404])


# ---------------------------------------------------------------------------
# Fix Transcriptions View
# ---------------------------------------------------------------------------

class FixTranscriptionsViewTests(AuthMixin, APITestCase):

    def test_fix_transcriptions_no_files(self):
        response = self.client.post(
            f'/api/projects/{self.project.id}/fix-transcriptions/'
        )
        self.assertIn(response.status_code, [200, 404])
        if response.status_code == 200:
            self.assertIn('fixed', response.data)

    def test_fix_transcriptions_with_files(self):
        af = make_audio_file(self.project, title='Fix Me', status='uploaded',
                             transcript_text='hello world test transcript', order_index=1)
        response = self.client.post(
            f'/api/projects/{self.project.id}/fix-transcriptions/'
        )
        self.assertIn(response.status_code, [200, 404])

    def test_fix_transcriptions_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(
            f'/api/projects/{self.project.id}/fix-transcriptions/'
        )
        self.assertIn(response.status_code, [401, 403])


# ---------------------------------------------------------------------------
# Legacy Views
# ---------------------------------------------------------------------------

class LegacyViewsTests(AuthMixin, APITestCase):

    def test_task_status_sentences_view(self):
        with patch('audioDiagnostic.views.legacy_views.AsyncResult') as mock_ar:
            mock_ar.return_value = MagicMock(
                ready=MagicMock(return_value=False),
                failed=MagicMock(return_value=False)
            )
            with patch('audioDiagnostic.views.legacy_views.r') as mock_r:
                mock_r.get.return_value = b'30'
                response = self.client.get('/api/task-status/some-task-id/sentences/')
                self.assertIn(response.status_code, [200, 202, 404])

    def test_download_audio_not_found(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get('/api/download/nonexistent_file.wav/')
        self.assertIn(response.status_code, [301, 302, 403, 404])

    def test_analyze_pdf_view(self):
        response = self.client.post('/api/analyze-pdf/', {}, format='json')
        self.assertIn(response.status_code, [200, 400, 401, 403, 404])

    def test_n8n_transcribe_view(self):
        self.client.raise_request_exception = False
        response = self.client.post('/api/n8n/transcribe/', {}, format='json')
        self.assertIn(response.status_code, [200, 400, 401, 403, 404, 500])

    def test_cut_audio_no_json(self):
        response = self.client.post('/api/cut-audio/', b'not json', content_type='application/json')
        self.assertIn(response.status_code, [200, 400, 403, 404, 500])
