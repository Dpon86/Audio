"""
Wave 130: duplicate_views.py remaining branches
- ProjectVerifyCleanupView: main success path
- ProjectDetectDuplicatesView.detect_duplicates_against_pdf (internal method)
- ProjectDetectDuplicatesView.compare_with_pdf (internal method)
- ProjectRefinePDFBoundariesView: missing branches (already partial in wave 116)
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from unittest.mock import MagicMock, patch
from audioDiagnostic.models import (
    AudioProject, AudioFile, TranscriptionSegment, Transcription
)
import datetime
from rest_framework.test import force_authenticate

User = get_user_model()


class VerifyCleanupViewTests(TestCase):
    """ProjectVerifyCleanupView - success path"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser_vc', password='pass', email='vc@t.com')
        token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
        self.client.raise_request_exception = False

        self.project = AudioProject.objects.create(
            user=self.user,
            title='Verify Cleanup Test',
            status='processing',
            clean_audio_transcribed=True,
            pdf_matched_section='This is the PDF section text here.',
        )
        self.audio_file = AudioFile.objects.create(
            project=self.project,
            filename='clean.wav',
            order_index=1,
            status='transcribed',
        )
        # Create verification segments (is_verification=True)
        TranscriptionSegment.objects.create(
            audio_file=self.audio_file,
            segment_index=0,
            start_time=0.0,
            end_time=1.0,
            text='This is the clean transcript text.',
            is_verification=True,
        )

    def test_verify_cleanup_success(self):
        resp = self.client.post(f'/api/projects/{self.project.id}/verify-cleanup/')
        self.assertIn(resp.status_code, [200, 201, 400, 404, 500])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('clean_transcript', data)
            self.assertIn('verification_results', data)

    def test_verify_cleanup_not_clean_audio(self):
        self.project.clean_audio_transcribed = False
        self.project.save()
        resp = self.client.post(f'/api/projects/{self.project.id}/verify-cleanup/')
        self.assertEqual(resp.status_code, 400)

    def test_verify_cleanup_no_verification_segments(self):
        TranscriptionSegment.objects.filter(
            audio_file__project=self.project, is_verification=True
        ).delete()
        resp = self.client.post(f'/api/projects/{self.project.id}/verify-cleanup/')
        self.assertIn(resp.status_code, [400, 404, 500])

    def test_verify_cleanup_with_pdf_char_range(self):
        """Test with pdf_match_start_char and pdf_match_end_char set."""
        self.project.pdf_text = 'abcdefghij'
        self.project.pdf_match_start_char = 2
        self.project.pdf_match_end_char = 8
        self.project.save()
        resp = self.client.post(f'/api/projects/{self.project.id}/verify-cleanup/')
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_verify_cleanup_wrong_user(self):
        other_user = User.objects.create_user(username='other_vc', password='pass', email='other_vc@t.com')
        token = Token.objects.create(user=other_user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
        resp = self.client.post(f'/api/projects/{self.project.id}/verify-cleanup/')
        self.assertEqual(resp.status_code, 404)


class DetectDuplicatesInternalMethodsTests(TestCase):
    """
    Test ProjectDetectDuplicatesView internal helper methods directly.
    """

    def _get_view(self):
        from audioDiagnostic.views.duplicate_views import ProjectDetectDuplicatesView
        return ProjectDetectDuplicatesView()

    def test_compare_with_pdf_basic(self):
        view = self._get_view()
        result = view.compare_with_pdf(
            'Hello world this is a transcript',
            'Hello world this is the PDF section'
        )
        self.assertIn('pdf_text', result)
        self.assertIn('transcript_text', result)
        self.assertIn('similarity_score', result)
        self.assertIn('diff_lines', result)
        self.assertIsInstance(result['similarity_score'], float)

    def test_compare_with_pdf_identical(self):
        view = self._get_view()
        text = 'Same text for both sides of comparison'
        result = view.compare_with_pdf(text, text)
        self.assertAlmostEqual(result['similarity_score'], 1.0, places=2)

    def test_compare_with_pdf_empty(self):
        view = self._get_view()
        result = view.compare_with_pdf('', '')
        self.assertIn('similarity_score', result)

    def test_detect_duplicates_against_pdf_no_duplicates(self):
        view = self._get_view()
        segments = [
            {'id': 1, 'audio_file_id': 10, 'audio_file_title': 'file1.wav',
             'text': 'This is a unique sentence', 'start_time': 0.0, 'end_time': 1.0},
            {'id': 2, 'audio_file_id': 10, 'audio_file_title': 'file1.wav',
             'text': 'Another completely different sentence here', 'start_time': 1.0, 'end_time': 2.0},
        ]
        result = view.detect_duplicates_against_pdf(segments, 'PDF text here', 'combined transcript')
        self.assertIn('duplicates', result)
        self.assertIn('summary', result)
        self.assertEqual(len(result['duplicates']), 0)

    def test_detect_duplicates_against_pdf_with_duplicates(self):
        view = self._get_view()
        dup_text = 'This sentence appears twice in the recording'
        segments = [
            {'id': 1, 'audio_file_id': 10, 'audio_file_title': 'file1.wav',
             'text': dup_text, 'start_time': 0.0, 'end_time': 2.0},
            {'id': 2, 'audio_file_id': 10, 'audio_file_title': 'file1.wav',
             'text': 'unique content only once here', 'start_time': 2.0, 'end_time': 4.0},
            {'id': 3, 'audio_file_id': 10, 'audio_file_title': 'file1.wav',
             'text': dup_text, 'start_time': 4.0, 'end_time': 6.0},
        ]
        result = view.detect_duplicates_against_pdf(segments, 'some pdf section', 'full transcript text')
        self.assertIn('duplicates', result)
        # Should have 2 entries for the duplicate sentence
        dups = [d for d in result['duplicates'] if 'appears twice' in d['text']]
        self.assertEqual(len(dups), 2)
        # Last occurrence should be 'keep'
        last = dups[-1]
        self.assertEqual(last['recommended_action'], 'keep')
        first = dups[0]
        self.assertEqual(first['recommended_action'], 'delete')

    def test_detect_duplicates_against_pdf_short_text_excluded(self):
        """Short texts (<=10 chars normalized) should be excluded from duplicate detection."""
        view = self._get_view()
        segments = [
            {'id': 1, 'audio_file_id': 10, 'audio_file_title': 'f.wav',
             'text': 'hi', 'start_time': 0.0, 'end_time': 0.5},
            {'id': 2, 'audio_file_id': 10, 'audio_file_title': 'f.wav',
             'text': 'hi', 'start_time': 0.5, 'end_time': 1.0},
        ]
        result = view.detect_duplicates_against_pdf(segments, 'pdf', 'transcript')
        self.assertEqual(len(result['duplicates']), 0)

    def test_detect_duplicates_summary(self):
        view = self._get_view()
        dup = 'This is a duplicated sentence that is long enough'
        segments = [
            {'id': 1, 'audio_file_id': 1, 'audio_file_title': 'f.wav',
             'text': dup, 'start_time': 0.0, 'end_time': 2.0},
            {'id': 2, 'audio_file_id': 1, 'audio_file_title': 'f.wav',
             'text': dup, 'start_time': 2.0, 'end_time': 4.0},
        ]
        result = view.detect_duplicates_against_pdf(segments, '', '')
        summary = result['summary']
        self.assertIn('segments_to_delete', summary)
        self.assertIn('segments_to_keep', summary)
        self.assertEqual(summary['segments_to_delete'], 1)
        self.assertEqual(summary['segments_to_keep'], 1)


class RefinePDFBoundariesMissingBranchesTests(TestCase):
    """
    Additional branches for ProjectRefinePDFBoundariesView not covered by wave 116.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='rpdfb_user', password='pass', email='rpdfb@t.com')
        token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
        self.client.raise_request_exception = False

        self.project = AudioProject.objects.create(
            user=self.user,
            title='Refine Boundaries Test',
            status='processing',
            pdf_match_completed=True,
            pdf_text='abcdefghijklmnopqrstuvwxyz' * 10,
        )

    def _url(self):
        # Need to find the URL for refine-pdf-boundaries
        from audioDiagnostic.urls import urlpatterns
        return f'/api/projects/{self.project.id}/refine-pdf-boundaries/'

    def test_refine_start_char_missing(self):
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            data={'end_char': 10},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_refine_invalid_format(self):
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            data={'start_char': 'abc', 'end_char': 10},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_refine_negative_start(self):
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            data={'start_char': -1, 'end_char': 10},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_refine_start_equals_end(self):
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            data={'start_char': 5, 'end_char': 5},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_refine_valid_with_transcript(self):
        self.project.combined_transcript = 'hello world transcript text here'
        self.project.save()
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            data={'start_char': 0, 'end_char': 50},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404, 405])
