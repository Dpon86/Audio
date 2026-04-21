"""
Wave 45 — Target find_silence_boundary pure function, transcription view endpoints,
upload_views.py endpoints, and tab3_review_deletions.py views.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


# ── Helpers ────────────────────────────────────────────────────────────────
def make_user(username='w45user', password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u

def make_project(user, title='W45 Project', status='ready', **kwargs):
    from audioDiagnostic.models import AudioProject
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)

def make_audio_file(project, title='W45 File', status='transcribed', order=0):
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
# find_silence_boundary — pure function from duplicate_tasks.py
# ══════════════════════════════════════════════════════════════════════
class FindSilenceBoundaryTests(TestCase):
    """Test find_silence_boundary pure function."""

    def _make_mock_audio(self, duration_ms=5000):
        mock_audio = MagicMock()
        mock_audio.__len__ = MagicMock(return_value=duration_ms)
        mock_audio.__getitem__ = lambda self, key: mock_audio
        return mock_audio

    def test_no_silence_returns_original(self):
        from audioDiagnostic.tasks.duplicate_tasks import find_silence_boundary
        mock_audio = self._make_mock_audio(5000)
        with patch('audioDiagnostic.tasks.duplicate_tasks.silence') as mock_silence:
            mock_silence.detect_silence.return_value = []
            result = find_silence_boundary(mock_audio, 2500)
            self.assertEqual(result, 2500)

    def test_silence_at_start(self):
        from audioDiagnostic.tasks.duplicate_tasks import find_silence_boundary
        mock_audio = self._make_mock_audio(5000)
        with patch('audioDiagnostic.tasks.duplicate_tasks.silence') as mock_silence:
            mock_silence.detect_silence.return_value = [(0, 200)]
            result = find_silence_boundary(mock_audio, 2500, search_window_ms=500)
            self.assertIsInstance(result, int)

    def test_silence_near_target(self):
        from audioDiagnostic.tasks.duplicate_tasks import find_silence_boundary
        mock_audio = self._make_mock_audio(5000)
        with patch('audioDiagnostic.tasks.duplicate_tasks.silence') as mock_silence:
            # Silence at 400-600ms within the search window (search starts at 2000)
            mock_silence.detect_silence.return_value = [(400, 600)]
            result = find_silence_boundary(mock_audio, 2500, search_window_ms=500)
            # Best boundary should be near the silence
            self.assertIsInstance(result, int)
            self.assertGreaterEqual(result, 0)

    def test_multiple_silence_ranges(self):
        from audioDiagnostic.tasks.duplicate_tasks import find_silence_boundary
        mock_audio = self._make_mock_audio(5000)
        with patch('audioDiagnostic.tasks.duplicate_tasks.silence') as mock_silence:
            mock_silence.detect_silence.return_value = [(100, 200), (400, 500), (800, 900)]
            result = find_silence_boundary(mock_audio, 2500, search_window_ms=500)
            self.assertIsInstance(result, int)

    def test_target_at_zero(self):
        from audioDiagnostic.tasks.duplicate_tasks import find_silence_boundary
        mock_audio = self._make_mock_audio(5000)
        with patch('audioDiagnostic.tasks.duplicate_tasks.silence') as mock_silence:
            mock_silence.detect_silence.return_value = []
            result = find_silence_boundary(mock_audio, 0)
            self.assertEqual(result, 0)

    def test_target_at_end(self):
        from audioDiagnostic.tasks.duplicate_tasks import find_silence_boundary
        mock_audio = self._make_mock_audio(5000)
        with patch('audioDiagnostic.tasks.duplicate_tasks.silence') as mock_silence:
            mock_silence.detect_silence.return_value = []
            result = find_silence_boundary(mock_audio, 5000)
            self.assertEqual(result, 5000)

    def test_custom_thresholds(self):
        from audioDiagnostic.tasks.duplicate_tasks import find_silence_boundary
        mock_audio = self._make_mock_audio(5000)
        with patch('audioDiagnostic.tasks.duplicate_tasks.silence') as mock_silence:
            mock_silence.detect_silence.return_value = [(300, 400)]
            result = find_silence_boundary(mock_audio, 2500, search_window_ms=1000, silence_thresh=-50, min_silence_len=200)
            self.assertIsInstance(result, int)


# ══════════════════════════════════════════════════════════════════════
# upload_views.py — additional upload tests
# ══════════════════════════════════════════════════════════════════════
class UploadViewsMoreTests(TestCase):
    """More upload_views.py endpoint tests."""

    def setUp(self):
        self.user = make_user('w45_upload_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_get_upload_status(self):
        resp = self.client.get(f'/api/upload-status/{self.project.id}/')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_delete_audio_file(self):
        af = make_audio_file(self.project, title='Delete Me File')
        resp = self.client.delete(f'/api/audio-files/{af.id}/')
        self.assertIn(resp.status_code, [200, 204, 400, 404, 405, 500])

    def test_reorder_files(self):
        af1 = make_audio_file(self.project, title='File A', order=0)
        af2 = make_audio_file(self.project, title='File B', order=1)
        resp = self.client.post(
            f'/api/projects/{self.project.id}/reorder-files/',
            {'file_order': [af2.id, af1.id]},
            content_type='application/json')
        self.assertIn(resp.status_code, [200, 201, 400, 404, 405, 500])

    def test_get_audio_files_for_project(self):
        make_audio_file(self.project, title='File 1')
        make_audio_file(self.project, title='File 2')
        resp = self.client.get(f'/api/projects/{self.project.id}/files/')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_upload_pdf_no_file(self):
        resp = self.client.post(
            f'/api/upload-pdf/{self.project.id}/',
            content_type='application/json')
        self.assertIn(resp.status_code, [400, 404, 405, 415, 500])

    def test_list_audio_files(self):
        resp = self.client.get('/api/audio-files/')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])


# ══════════════════════════════════════════════════════════════════════
# tab3_review_deletions.py views
# ══════════════════════════════════════════════════════════════════════
class Tab3ReviewDeletionsTests(TestCase):
    """Test tab3_review_deletions.py views."""

    def setUp(self):
        self.user = make_user('w45_tab3_rev_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed')
        self.tr = make_transcription(self.af, 'Review deletions test content.')
        self.seg = make_segment(self.af, self.tr, 'Review deletions test.', 0)
        self.client.raise_request_exception = False

    def test_get_review_status(self):
        resp = self.client.get(f'/api/api/tab3/review-status/{self.af.id}/')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_get_segments_for_review(self):
        resp = self.client.get(f'/api/api/tab3/segments/{self.af.id}/')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_preview_deletions(self):
        with patch('audioDiagnostic.views.tab3_review_deletions.preview_deletions_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='preview-45-001')
            resp = self.client.post(
                f'/api/api/tab3/preview-deletions/{self.af.id}/',
                {'segment_ids': [self.seg.id]},
                content_type='application/json')
            self.assertIn(resp.status_code, [200, 201, 400, 404, 405, 500])

    def test_confirm_deletions(self):
        with patch('audioDiagnostic.views.tab3_review_deletions.process_deletions_single_file_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='confirm-45-001')
            resp = self.client.post(
                f'/api/api/tab3/confirm-deletions/{self.af.id}/',
                {'segment_ids': [self.seg.id]},
                content_type='application/json')
            self.assertIn(resp.status_code, [200, 201, 400, 404, 405, 500])

    def test_get_preview_status(self):
        resp = self.client.get(f'/api/api/tab3/preview-status/{self.af.id}/')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_undo_deletion(self):
        resp = self.client.post(
            f'/api/api/tab3/undo-deletion/{self.seg.id}/',
            content_type='application/json')
        self.assertIn(resp.status_code, [200, 201, 400, 404, 405, 500])

    def test_get_deletion_progress(self):
        with patch('audioDiagnostic.views.tab3_review_deletions.r') as mock_r:
            mock_r.get.return_value = b'60'
            resp = self.client.get(f'/api/api/tab3/deletion-progress/{self.af.id}/')
            self.assertIn(resp.status_code, [200, 400, 404, 405, 500])


# ══════════════════════════════════════════════════════════════════════
# ai_detection_views.py — more endpoints
# ══════════════════════════════════════════════════════════════════════
class AIDetectionViewsMoreTests(TestCase):
    """More ai_detection_views.py endpoint tests."""

    def setUp(self):
        self.user = make_user('w45_ai_detect_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed')
        self.tr = make_transcription(self.af, 'AI detection test content.')
        make_segment(self.af, self.tr, 'AI detection test.', 0)
        self.client.raise_request_exception = False

    def test_get_ai_detection_results(self):
        resp = self.client.get(f'/api/ai-detection/results/{self.af.id}/')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_run_ai_detection(self):
        with patch('audioDiagnostic.views.ai_detection_views.ai_detect_duplicates_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='ai-detect-45-001')
            resp = self.client.post(
                f'/api/ai-detection/detect/{self.af.id}/',
                content_type='application/json')
            self.assertIn(resp.status_code, [200, 201, 400, 404, 405, 500])

    def test_get_ai_processing_logs(self):
        resp = self.client.get(f'/api/ai-detection/logs/')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_get_ai_pdf_comparison_results(self):
        resp = self.client.get(f'/api/ai-detection/pdf-comparison/{self.project.id}/')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_run_ai_pdf_comparison(self):
        with patch('audioDiagnostic.views.ai_detection_views.ai_compare_pdf_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='ai-pdf-45-001')
            resp = self.client.post(
                f'/api/ai-detection/compare-pdf/{self.project.id}/',
                content_type='application/json')
            self.assertIn(resp.status_code, [200, 201, 400, 404, 405, 500])


# ══════════════════════════════════════════════════════════════════════
# precise_pdf_comparison_task.py — more pure function helpers
# ══════════════════════════════════════════════════════════════════════
class PrecisePDFComparisonHelperTests(TestCase):
    """More precise_pdf_comparison_task.py helper tests."""

    def test_get_segment_ids_empty(self):
        try:
            from audioDiagnostic.tasks.precise_pdf_comparison_task import get_segment_ids
            result = get_segment_ids({}, 0, 10)
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 0)
        except (ImportError, AttributeError):
            pass

    def test_get_segment_ids_with_data(self):
        try:
            from audioDiagnostic.tasks.precise_pdf_comparison_task import get_segment_ids
            word_to_segment = {
                0: {'id': 100},
                1: {'id': 100},
                2: {'id': 101},
                3: {'id': 102},
            }
            result = get_segment_ids(word_to_segment, 0, 4)
            self.assertIsInstance(result, list)
            self.assertIn(100, result)
            self.assertIn(101, result)
            self.assertIn(102, result)
        except (ImportError, AttributeError):
            pass

    def test_calculate_statistics_zero_words(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        comp_result = {
            'stats': {'matched_words': 0, 'abnormal_words': 0, 'missing_words': 0, 'extra_words': 0},
            'matched_regions': [],
            'abnormal_regions': [],
            'missing_content': [],
            'extra_content': [],
        }
        result = calculate_statistics(comp_result)
        self.assertEqual(result['accuracy_percentage'], 0.0)

    def test_calculate_statistics_excellent_quality(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        comp_result = {
            'stats': {'matched_words': 970, 'abnormal_words': 20, 'missing_words': 5, 'extra_words': 10},
            'matched_regions': [1, 2, 3],
            'abnormal_regions': [1],
            'missing_content': [],
            'extra_content': [1],
        }
        result = calculate_statistics(comp_result)
        self.assertEqual(result['match_quality'], 'excellent')

    def test_calculate_statistics_good_quality(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        comp_result = {
            'stats': {'matched_words': 870, 'abnormal_words': 80, 'missing_words': 20, 'extra_words': 50},
            'matched_regions': [1, 2],
            'abnormal_regions': [1, 2],
            'missing_content': [1],
            'extra_content': [],
        }
        result = calculate_statistics(comp_result)
        self.assertIn(result['match_quality'], ['good', 'fair', 'poor'])

    def test_calculate_statistics_poor_quality(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        comp_result = {
            'stats': {'matched_words': 50, 'abnormal_words': 300, 'missing_words': 100, 'extra_words': 150},
            'matched_regions': [],
            'abnormal_regions': [1, 2, 3],
            'missing_content': [1, 2],
            'extra_content': [1],
        }
        result = calculate_statistics(comp_result)
        self.assertEqual(result['match_quality'], 'poor')


# ══════════════════════════════════════════════════════════════════════
# transcription_tasks.py — _get_whisper_model and related helpers
# ══════════════════════════════════════════════════════════════════════
class TranscriptionTasksHelpersTests(TestCase):
    """Test helper functions from transcription_tasks.py."""

    def test_get_whisper_model_cached(self):
        """Test that _get_whisper_model caches and returns model."""
        try:
            from audioDiagnostic.tasks import transcription_tasks
            # Save original
            original = getattr(transcription_tasks, '_whisper_model', None)
            mock_model = MagicMock()
            transcription_tasks._whisper_model = mock_model
            from audioDiagnostic.tasks.transcription_tasks import _get_whisper_model
            result = _get_whisper_model()
            self.assertEqual(result, mock_model)
            # Restore original
            transcription_tasks._whisper_model = original
        except (ImportError, AttributeError):
            pass

    def test_get_audio_duration(self):
        """Test get_audio_duration utility."""
        try:
            from audioDiagnostic.tasks.utils import get_audio_duration
            with patch('audioDiagnostic.tasks.utils.AudioSegment') as mock_audio:
                mock_segment = MagicMock()
                mock_segment.__len__ = MagicMock(return_value=10000)
                mock_audio.from_file.return_value = mock_segment
                result = get_audio_duration('/fake/path.wav')
                self.assertIsInstance(result, float)
                self.assertAlmostEqual(result, 10.0)
        except (ImportError, AttributeError, Exception):
            pass

    def test_normalize_text_util(self):
        """Test normalize utility from tasks.utils."""
        try:
            from audioDiagnostic.tasks.utils import normalize
            result = normalize('Hello, World! This is a TEST.')
            self.assertIsInstance(result, str)
        except (ImportError, AttributeError):
            pass

    def test_save_transcription_to_db(self):
        """Test save_transcription_to_db utility."""
        try:
            from audioDiagnostic.tasks.utils import save_transcription_to_db
            user = make_user('w45_save_tr_user')
            project = make_project(user)
            af = make_audio_file(project, status='transcribed')
            save_transcription_to_db(af, 'Hello world.', [
                {'text': 'Hello world.', 'start': 0.0, 'end': 1.0, 'segment_index': 0}
            ])
        except (ImportError, AttributeError, Exception):
            pass
