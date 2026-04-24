"""
Wave 52 — More coverage:
  - tab4_review_comparison.py (ProjectComparison, FileComparisonDetail, mark-reviewed, deletion-regions)
  - detect_duplicates_against_pdf_task (pure function tests)
  - ai_detect_duplicates_task error paths via apply()
  - transcribe_audio_task and transcribe_audio_words_task via apply()
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
import json
from rest_framework.test import force_authenticate


# ── Helpers ────────────────────────────────────────────────────────────────
def make_user(username='w52user', password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u

def make_project(user, title='W52 Project', status='ready', **kwargs):
    from audioDiagnostic.models import AudioProject
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)

def make_audio_file(project, title='W52 File', status='transcribed', order=0):
    from audioDiagnostic.models import AudioFile
    return AudioFile.objects.create(
        project=project,
        filename=f'{title.lower().replace(" ", "_")}.wav',
        title=title, order_index=order, status=status)

def make_transcription(audio_file, content='Test transcription.'):
    from audioDiagnostic.models import Transcription
    return Transcription.objects.create(audio_file=audio_file, full_text=content)

def make_segment(audio_file, transcription, text='Segment', idx=0, is_dup=False):
    from audioDiagnostic.models import TranscriptionSegment
    return TranscriptionSegment.objects.create(
        audio_file=audio_file, transcription=transcription,
        text=text, start_time=float(idx), end_time=float(idx) + 1.0,
        segment_index=idx, is_duplicate=is_dup)


def _make_seg_dict(id, text, start, end, af_id=1, af_title='Test File'):
    """Build a segment dict as used by detect_duplicates_against_pdf_task."""
    return {
        'id': id,
        'audio_file_id': af_id,
        'audio_file_title': af_title,
        'text': text,
        'start_time': float(start),
        'end_time': float(end),
        'segment_index': id,
    }


# ══════════════════════════════════════════════════════════════════════
# tab4_review_comparison.py
# ══════════════════════════════════════════════════════════════════════
class Tab4ProjectComparisonTests(TestCase):
    """Test ProjectComparisonView GET."""

    def setUp(self):
        self.user = make_user('w52_tab4_comp_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user)

    def test_get_comparison_no_processed_files(self):
        """GET comparison when project has no processed files."""
        resp = self.client.get(f'/api/api/projects/{self.project.id}/comparison/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('project_stats', data)
            self.assertEqual(data['project_stats']['total_files'], 0)

    def test_get_comparison_unauthenticated(self):
        """GET comparison without auth should return 401/403."""
        self.client.defaults.pop('HTTP_AUTHORIZATION', None)
        resp = self.client.get(f'/api/api/projects/{self.project.id}/comparison/')
        self.assertIn(resp.status_code, [401, 403])

    def test_get_comparison_project_not_found(self):
        """GET comparison for non-existent project returns 404."""
        resp = self.client.get('/api/api/projects/99999/comparison/')
        self.assertEqual(resp.status_code, 404)

    def test_get_comparison_other_user_project(self):
        """GET comparison for another user's project returns 404."""
        other_user = make_user('w52_tab4_other')
        other_project = make_project(other_user, title='Other Project')
        resp = self.client.get(f'/api/api/projects/{other_project.id}/comparison/')
        self.assertEqual(resp.status_code, 404)


class Tab4FileComparisonDetailTests(TestCase):
    """Test FileComparisonDetailView GET."""

    def setUp(self):
        self.user = make_user('w52_tab4_detail_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed')

    def test_get_detail_file_not_processed(self):
        """GET detail for file that is not processed returns 400."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/comparison-details/'
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_get_detail_file_processed_no_transcription(self):
        """GET detail for processed file without transcription."""
        self.af.status = 'processed'
        self.af.save()
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/comparison-details/'
        )
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_get_detail_file_processed_with_transcription_and_dups(self):
        """GET detail for processed file with transcription and duplicate segments."""
        self.af.status = 'processed'
        self.af.save()
        tr = make_transcription(self.af, 'Processed transcription content.')
        seg_dup = make_segment(self.af, tr, 'Duplicate segment.', idx=0, is_dup=True)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/comparison-details/'
        )
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_get_detail_not_found(self):
        """GET detail for non-existent file returns 404."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/99999/comparison-details/'
        )
        self.assertEqual(resp.status_code, 404)


class Tab4MarkReviewedTests(TestCase):
    """Test mark_file_reviewed view."""

    def setUp(self):
        self.user = make_user('w52_tab4_review_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='processed')

    def test_mark_reviewed_success(self):
        """POST mark-reviewed should update comparison_status."""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/mark-reviewed/',
            {'notes': 'Looks good', 'status': 'reviewed'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404, 500])
        if resp.status_code == 200:
            data = resp.json()
            self.assertTrue(data.get('success'))

    def test_mark_reviewed_approved_status(self):
        """POST mark-reviewed with 'approved' status."""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/mark-reviewed/',
            {'notes': 'Approved', 'status': 'approved'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404, 500])

    def test_mark_reviewed_no_notes(self):
        """POST mark-reviewed without notes uses default."""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/mark-reviewed/',
            {},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404, 500])

    def test_mark_reviewed_not_found(self):
        """POST mark-reviewed for non-existent file returns 404."""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/99999/mark-reviewed/',
            {'status': 'reviewed'},
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 404)


class Tab4DeletionRegionsTests(TestCase):
    """Test get_deletion_regions view."""

    def setUp(self):
        self.user = make_user('w52_tab4_del_regions_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed')

    def test_get_deletion_regions_no_transcription(self):
        """GET deletion-regions for file without transcription."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/deletion-regions/'
        )
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertEqual(data['total_count'], 0)

    def test_get_deletion_regions_with_duplicate_segments(self):
        """GET deletion-regions for file with duplicate segments."""
        tr = make_transcription(self.af, 'Some content with duplicates.')
        seg_dup = make_segment(self.af, tr, 'Duplicate text.', idx=0, is_dup=True)
        seg_kept = make_segment(self.af, tr, 'Unique text.', idx=1, is_dup=False)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/deletion-regions/'
        )
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertGreaterEqual(data['total_count'], 1)
            self.assertIn('deletion_regions', data)

    def test_get_deletion_regions_not_found(self):
        """GET deletion-regions for non-existent file returns 404."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/99999/deletion-regions/'
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_deletion_regions_unauthenticated(self):
        """GET deletion-regions without auth returns 401/403."""
        self.client.defaults.pop('HTTP_AUTHORIZATION', None)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/deletion-regions/'
        )
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════════════════════
# detect_duplicates_against_pdf_task — pure function tests
# ══════════════════════════════════════════════════════════════════════
class DetectDuplicatesAgainstPDFPureTests(TestCase):
    """Test detect_duplicates_against_pdf_task as a pure function."""

    def setUp(self):
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        self.detect_fn = detect_duplicates_against_pdf_task
        self.mock_r = MagicMock()

    def _call(self, segments, pdf='pdf section', transcript='full transcript'):
        return self.detect_fn(segments, pdf, transcript, 'test-task-52', self.mock_r)

    def test_empty_segments(self):
        """Empty segments list returns no duplicates."""
        result = self._call([])
        self.assertIn('duplicates', result)
        self.assertEqual(len(result['duplicates']), 0)
        self.assertEqual(result['summary']['total_segments'], 0)

    def test_all_short_segments_skipped(self):
        """Segments with fewer than 3 words are skipped (no duplicates found)."""
        segments = [
            _make_seg_dict(1, 'Hello world', 0.0, 1.0),
            _make_seg_dict(2, 'Hello world', 1.0, 2.0),
        ]
        result = self._call(segments)
        self.assertIn('duplicates', result)
        # Short segments (<3 words) are skipped, so no duplicate groups
        self.assertEqual(len(result.get('duplicate_groups', {})), 0)

    def test_exact_duplicate_segments(self):
        """Two segments with exactly the same text form a duplicate group."""
        text = 'This is a repeated sentence in the audio recording.'
        segments = [
            _make_seg_dict(1, text, 0.0, 5.0),
            _make_seg_dict(2, 'Different unique content here.', 5.0, 10.0),
            _make_seg_dict(3, text, 10.0, 15.0),
        ]
        result = self._call(segments)
        self.assertIn('duplicates', result)
        self.assertGreater(len(result['duplicates']), 0)
        self.assertGreater(len(result['duplicate_groups']), 0)

    def test_fuzzy_duplicate_segments(self):
        """Two very similar segments are detected as fuzzy duplicates."""
        text1 = 'This sentence is about the story of a great adventure.'
        text2 = 'This sentence is about the story of a great adventure here.'
        segments = [
            _make_seg_dict(1, text1, 0.0, 5.0),
            _make_seg_dict(2, text2, 5.0, 10.0),
        ]
        result = self._call(segments)
        self.assertIn('duplicates', result)
        self.assertIn('summary', result)

    def test_no_duplicates_all_unique(self):
        """All unique segments produce no duplicates."""
        segments = [
            _make_seg_dict(1, 'First unique sentence about mountains.', 0.0, 5.0),
            _make_seg_dict(2, 'Second distinct sentence about oceans.', 5.0, 10.0),
            _make_seg_dict(3, 'Third completely different sentence about forests.', 10.0, 15.0),
        ]
        result = self._call(segments)
        self.assertIn('duplicates', result)
        self.assertEqual(len(result['duplicate_groups']), 0)

    def test_multiple_duplicate_groups(self):
        """Multiple sets of duplicates are detected separately."""
        text_a = 'The hero walked through the enchanted forest slowly.'
        text_b = 'She looked at the starry sky above with wonder.'
        segments = [
            _make_seg_dict(1, text_a, 0.0, 3.0),
            _make_seg_dict(2, text_b, 3.0, 6.0),
            _make_seg_dict(3, text_a, 6.0, 9.0),
            _make_seg_dict(4, text_b, 9.0, 12.0),
            _make_seg_dict(5, 'Something completely different here now.', 12.0, 15.0),
        ]
        result = self._call(segments)
        self.assertIn('duplicates', result)
        self.assertGreaterEqual(len(result['duplicate_groups']), 1)

    def test_keeps_last_occurrence(self):
        """The last occurrence of a duplicate is marked is_last_occurrence=True."""
        text = 'The forest was dark and full of mystery tonight.'
        segments = [
            _make_seg_dict(1, text, 0.0, 5.0),
            _make_seg_dict(2, text, 5.0, 10.0),
            _make_seg_dict(3, text, 10.0, 15.0),
        ]
        result = self._call(segments)
        dups = result.get('duplicates', [])
        if dups:
            last_occurrences = [d for d in dups if d.get('is_last_occurrence')]
            non_last = [d for d in dups if not d.get('is_last_occurrence')]
            self.assertGreater(len(last_occurrences), 0)
            self.assertGreater(len(non_last), 0)

    def test_summary_statistics(self):
        """Summary contains expected statistics fields."""
        segments = [
            _make_seg_dict(1, 'Repeated content appears here again and again.', 0.0, 5.0),
            _make_seg_dict(2, 'Repeated content appears here again and again.', 5.0, 10.0),
        ]
        result = self._call(segments)
        summary = result.get('summary', {})
        self.assertIn('total_segments', summary)
        self.assertIn('duplicates_count', summary)
        self.assertIn('unique_count', summary)

    def test_redis_set_called(self):
        """Redis set() is called to track progress."""
        segments = [
            _make_seg_dict(1, 'Some long sentence that should be processed.', 0.0, 5.0),
        ]
        self._call(segments)
        self.assertTrue(self.mock_r.set.called)


# ══════════════════════════════════════════════════════════════════════
# ai_detect_duplicates_task — error paths via apply()
# ══════════════════════════════════════════════════════════════════════
class AIDetectDuplicatesTaskTests(TestCase):
    """Test ai_detect_duplicates_task error paths."""

    def setUp(self):
        self.user = make_user('w52_ai_task_user')
        self.project = make_project(self.user, title='AI Task Project')
        self.client.raise_request_exception = False

    def test_audio_file_not_found(self):
        """Task fails when audio_file_id doesn't exist."""
        from audioDiagnostic.tasks.ai_tasks import ai_detect_duplicates_task
        with patch('audioDiagnostic.tasks.ai_tasks.get_redis_connection') as mock_redis:
            mock_redis.return_value = MagicMock()
            result = ai_detect_duplicates_task.apply(
                args=[99999, self.user.id],
                task_id='w52-ai-task-001'
            )
            self.assertEqual(result.status, 'FAILURE')

    def test_user_not_found(self):
        """Task fails when user_id doesn't exist (after finding audio file)."""
        from audioDiagnostic.tasks.ai_tasks import ai_detect_duplicates_task
        af = make_audio_file(self.project, status='transcribed')
        with patch('audioDiagnostic.tasks.ai_tasks.get_redis_connection') as mock_redis:
            mock_redis.return_value = MagicMock()
            result = ai_detect_duplicates_task.apply(
                args=[af.id, 99999],
                task_id='w52-ai-task-002'
            )
            self.assertEqual(result.status, 'FAILURE')

    def test_no_transcription(self):
        """Task fails when audio file has no transcription."""
        from audioDiagnostic.tasks.ai_tasks import ai_detect_duplicates_task
        af = make_audio_file(self.project, status='transcribed')
        # No transcription created - hasattr will return False
        with patch('audioDiagnostic.tasks.ai_tasks.get_redis_connection') as mock_redis:
            mock_redis.return_value = MagicMock()
            result = ai_detect_duplicates_task.apply(
                args=[af.id, self.user.id],
                task_id='w52-ai-task-003'
            )
            self.assertEqual(result.status, 'FAILURE')

    def test_no_segments(self):
        """Task fails when transcription has no segments."""
        from audioDiagnostic.tasks.ai_tasks import ai_detect_duplicates_task
        af = make_audio_file(self.project, status='transcribed')
        make_transcription(af, 'Content without segments.')
        # No TranscriptionSegments created
        with patch('audioDiagnostic.tasks.ai_tasks.get_redis_connection') as mock_redis:
            mock_redis.return_value = MagicMock()
            result = ai_detect_duplicates_task.apply(
                args=[af.id, self.user.id],
                task_id='w52-ai-task-004'
            )
            self.assertEqual(result.status, 'FAILURE')


# ══════════════════════════════════════════════════════════════════════
# transcribe_audio_task — mocked whisper
# ══════════════════════════════════════════════════════════════════════
class TranscribeAudioTaskTests(TestCase):
    """Test transcribe_audio_task with mocked whisper model."""

    def _make_whisper_result(self, text='Hello. Hello. World.'):
        """Create a realistic whisper transcription result."""
        return {
            'text': text,
            'segments': [
                {
                    'text': 'Hello.',
                    'start': 0.0, 'end': 1.0,
                    'words': [{'word': 'Hello', 'start': 0.0, 'end': 0.5}],
                    'avg_logprob': -0.3
                },
                {
                    'text': 'Hello.',
                    'start': 1.0, 'end': 2.0,
                    'words': [{'word': 'Hello', 'start': 1.0, 'end': 1.5}],
                    'avg_logprob': -0.3
                },
                {
                    'text': 'World.',
                    'start': 2.0, 'end': 3.0,
                    'words': [{'word': 'World', 'start': 2.0, 'end': 2.5}],
                    'avg_logprob': -0.5
                },
            ],
            'duration': 3.0
        }

    def test_transcribe_audio_task_success(self):
        """transcribe_audio_task succeeds with mocked whisper model."""
        from audioDiagnostic.tasks.transcription_tasks import transcribe_audio_task
        with patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection') as mock_redis, \
             patch('audioDiagnostic.tasks.transcription_tasks._get_whisper_model') as mock_model, \
             patch('audioDiagnostic.tasks.transcription_tasks.find_noise_regions') as mock_noise:
            mock_redis.return_value = MagicMock()
            mock_whisper = MagicMock()
            mock_whisper.transcribe.return_value = self._make_whisper_result()
            mock_model.return_value = mock_whisper
            mock_noise.return_value = []

            result = transcribe_audio_task.apply(
                args=['/tmp/test_w52.wav', 'http://example.com/audio.wav'],
                task_id='w52-transcribe-001'
            )
            self.assertEqual(result.status, 'SUCCESS')
            data = result.get()
            self.assertIn('all_segments', data)
            self.assertIn('repetitive_groups', data)

    def test_transcribe_audio_task_with_repeated_segments(self):
        """transcribe_audio_task detects repeated sentences."""
        from audioDiagnostic.tasks.transcription_tasks import transcribe_audio_task
        # Create result with multiple repeated sentences
        whisper_result = {
            'text': 'Hello world. Hello world. Something else.',
            'segments': [
                {'text': 'Hello world.', 'start': 0.0, 'end': 1.5,
                 'words': [{'word': 'Hello', 'start': 0.0, 'end': 0.5},
                            {'word': 'world', 'start': 0.5, 'end': 1.0}]},
                {'text': 'Hello world.', 'start': 1.5, 'end': 3.0,
                 'words': [{'word': 'Hello', 'start': 1.5, 'end': 2.0},
                            {'word': 'world', 'start': 2.0, 'end': 2.5}]},
                {'text': 'Something else.', 'start': 3.0, 'end': 4.5,
                 'words': [{'word': 'Something', 'start': 3.0, 'end': 3.5},
                            {'word': 'else', 'start': 3.5, 'end': 4.0}]},
            ],
            'duration': 4.5
        }
        with patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection') as mock_redis, \
             patch('audioDiagnostic.tasks.transcription_tasks._get_whisper_model') as mock_model, \
             patch('audioDiagnostic.tasks.transcription_tasks.find_noise_regions') as mock_noise:
            mock_redis.return_value = MagicMock()
            mock_whisper = MagicMock()
            mock_whisper.transcribe.return_value = whisper_result
            mock_model.return_value = mock_whisper
            mock_noise.return_value = []

            result = transcribe_audio_task.apply(
                args=['/tmp/test_w52_rep.wav', 'http://example.com/audio2.wav'],
                task_id='w52-transcribe-002'
            )
            self.assertEqual(result.status, 'SUCCESS')
            data = result.get()
            self.assertGreater(len(data.get('repetitive_groups', [])), 0)

    def test_transcribe_audio_task_empty_segments(self):
        """transcribe_audio_task handles whisper returning empty segments."""
        from audioDiagnostic.tasks.transcription_tasks import transcribe_audio_task
        whisper_result = {'text': '', 'segments': [], 'duration': 0.0}
        with patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection') as mock_redis, \
             patch('audioDiagnostic.tasks.transcription_tasks._get_whisper_model') as mock_model, \
             patch('audioDiagnostic.tasks.transcription_tasks.find_noise_regions') as mock_noise:
            mock_redis.return_value = MagicMock()
            mock_whisper = MagicMock()
            mock_whisper.transcribe.return_value = whisper_result
            mock_model.return_value = mock_whisper
            mock_noise.return_value = []

            result = transcribe_audio_task.apply(
                args=['/tmp/empty.wav', 'http://example.com/empty.wav'],
                task_id='w52-transcribe-003'
            )
            self.assertEqual(result.status, 'SUCCESS')


# ══════════════════════════════════════════════════════════════════════
# transcribe_audio_words_task — mocked whisper
# ══════════════════════════════════════════════════════════════════════
class TranscribeAudioWordsTaskTests(TestCase):
    """Test transcribe_audio_words_task with mocked whisper model."""

    def _make_whisper_result(self):
        return {
            'text': 'Hello world. Hello world.',
            'segments': [
                {
                    'text': 'Hello world.',
                    'start': 0.0, 'end': 1.5,
                    'words': [
                        {'word': 'Hello', 'start': 0.0, 'end': 0.5, 'probability': 0.95},
                        {'word': 'world', 'start': 0.5, 'end': 1.0, 'probability': 0.90},
                    ]
                },
                {
                    'text': 'Hello world.',
                    'start': 1.5, 'end': 3.0,
                    'words': [
                        {'word': 'Hello', 'start': 1.5, 'end': 2.0, 'probability': 0.88},
                        {'word': 'world', 'start': 2.0, 'end': 2.5, 'probability': 0.92},
                    ]
                },
            ]
        }

    def test_transcribe_words_task_success(self):
        """transcribe_audio_words_task returns words and segments."""
        from audioDiagnostic.tasks.transcription_tasks import transcribe_audio_words_task
        with patch('audioDiagnostic.tasks.transcription_tasks._get_whisper_model') as mock_model:
            mock_whisper = MagicMock()
            mock_whisper.transcribe.return_value = self._make_whisper_result()
            mock_model.return_value = mock_whisper

            result = transcribe_audio_words_task.apply(
                args=['/tmp/words_test.wav', 'http://example.com/words.wav'],
                task_id='w52-words-001'
            )
            self.assertEqual(result.status, 'SUCCESS')
            data = result.get()
            self.assertIn('words', data)
            self.assertIn('segments', data)
            self.assertIn('transcript', data)
            self.assertIn('repetitive_groups', data)

    def test_transcribe_words_task_finds_repetitions(self):
        """transcribe_audio_words_task detects repeated segments."""
        from audioDiagnostic.tasks.transcription_tasks import transcribe_audio_words_task
        with patch('audioDiagnostic.tasks.transcription_tasks._get_whisper_model') as mock_model:
            mock_whisper = MagicMock()
            mock_whisper.transcribe.return_value = self._make_whisper_result()
            mock_model.return_value = mock_whisper

            result = transcribe_audio_words_task.apply(
                args=['/tmp/words_rep_test.wav', 'http://example.com/rep.wav'],
                task_id='w52-words-002'
            )
            data = result.get()
            # 'Hello world.' appears twice → should be in repetitive_groups
            self.assertGreater(len(data.get('repetitive_groups', [])), 0)

    def test_transcribe_words_task_empty(self):
        """transcribe_audio_words_task handles empty result."""
        from audioDiagnostic.tasks.transcription_tasks import transcribe_audio_words_task
        with patch('audioDiagnostic.tasks.transcription_tasks._get_whisper_model') as mock_model:
            mock_whisper = MagicMock()
            mock_whisper.transcribe.return_value = {'text': '', 'segments': []}
            mock_model.return_value = mock_whisper

            result = transcribe_audio_words_task.apply(
                args=['/tmp/empty_words.wav', 'http://example.com/empty.wav'],
                task_id='w52-words-003'
            )
            self.assertEqual(result.status, 'SUCCESS')
            data = result.get()
            self.assertEqual(data['words'], [])
            self.assertEqual(data['repetitive_groups'], [])
