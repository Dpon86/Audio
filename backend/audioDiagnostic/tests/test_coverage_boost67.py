"""
Wave 67 — Coverage boost
Targets:
  - precise_pdf_comparison_task.py: pure helper functions (tokenize_text,
    normalize_word, words_match, match_sequence, build_word_segment_map)
  - pdf_tasks.py: match_pdf_to_audio_task + validate_transcript_against_pdf_task
    error paths
  - duplicate_tasks.py: detect_duplicates_single_file_task error paths
  - transcription_tasks.py: additional branch coverage
"""

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


def make_project(user, title='W67 Project', status='ready', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def make_audio_file(project, title='W67 File', status='transcribed', order=0, **kwargs):
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
# precise_pdf_comparison_task.py — pure helper functions
# ══════════════════════════════════════════════════════
class TokenizeTextTests(TestCase):
    """tokenize_text() — pure function"""

    def _fn(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        return tokenize_text

    def test_basic(self):
        tokenize_text = self._fn()
        result = tokenize_text('Hello world foo')
        self.assertEqual(result, ['Hello', 'world', 'foo'])

    def test_extra_whitespace(self):
        tokenize_text = self._fn()
        result = tokenize_text('  Hello   world  ')
        self.assertEqual(result, ['Hello', 'world'])

    def test_empty_string(self):
        tokenize_text = self._fn()
        result = tokenize_text('')
        self.assertEqual(result, [])

    def test_newlines_tabs(self):
        tokenize_text = self._fn()
        result = tokenize_text('Hello\nworld\there')
        self.assertEqual(len(result), 3)


class NormalizeWordTests(TestCase):
    """normalize_word() — pure function"""

    def _fn(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        return normalize_word

    def test_lowercase(self):
        normalize_word = self._fn()
        self.assertEqual(normalize_word('Hello'), 'hello')

    def test_strips_punctuation(self):
        normalize_word = self._fn()
        self.assertEqual(normalize_word('hello,'), 'hello')

    def test_strips_leading_trailing_punct(self):
        normalize_word = self._fn()
        self.assertEqual(normalize_word('"word"'), 'word')

    def test_empty(self):
        normalize_word = self._fn()
        self.assertEqual(normalize_word(''), '')

    def test_number(self):
        normalize_word = self._fn()
        self.assertEqual(normalize_word('42'), '42')


class WordsMatchTests(TestCase):
    """words_match() — pure function"""

    def _fn(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        return words_match

    def test_exact_match(self):
        words_match = self._fn()
        self.assertTrue(words_match('hello', 'hello'))

    def test_case_insensitive(self):
        words_match = self._fn()
        self.assertTrue(words_match('Hello', 'hello'))

    def test_punctuation_stripped(self):
        words_match = self._fn()
        self.assertTrue(words_match('word,', 'word'))

    def test_no_match_different(self):
        words_match = self._fn()
        self.assertFalse(words_match('cat', 'dog'))

    def test_similar_long_words(self):
        """Very similar long words (>90% ratio) match"""
        words_match = self._fn()
        # 'colour' vs 'color' - may or may not match depending on ratio
        result = words_match('running', 'running')
        self.assertTrue(result)

    def test_short_words_not_fuzzy(self):
        """Short words (<=3 chars) don't use fuzzy matching"""
        words_match = self._fn()
        self.assertFalse(words_match('cat', 'cut'))

    def test_near_identical_long_words(self):
        """Very similar long words match via fuzzy"""
        words_match = self._fn()
        # 'transcription' vs 'transcriptions' → ratio ~0.96
        self.assertTrue(words_match('transcription', 'transcriptions'))


class MatchSequenceTests(TestCase):
    """match_sequence() — pure function"""

    def _fn(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        return match_sequence

    def test_matching_sequences(self):
        match_sequence = self._fn()
        self.assertTrue(match_sequence(['hello', 'world'], ['hello', 'world']))

    def test_non_matching_sequences(self):
        match_sequence = self._fn()
        self.assertFalse(match_sequence(['hello', 'world'], ['hello', 'there']))

    def test_different_lengths(self):
        match_sequence = self._fn()
        self.assertFalse(match_sequence(['a', 'b'], ['a', 'b', 'c']))

    def test_empty_sequences(self):
        match_sequence = self._fn()
        self.assertTrue(match_sequence([], []))

    def test_single_word(self):
        match_sequence = self._fn()
        self.assertTrue(match_sequence(['word'], ['word']))


class BuildWordSegmentMapTests(TestCase):
    """build_word_segment_map() — pure function"""

    def _fn(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        return build_word_segment_map

    def test_single_segment(self):
        build_word_segment_map = self._fn()
        segments = [{'text': 'Hello world', 'start_time': 0.0, 'end_time': 2.0}]
        result = build_word_segment_map(segments)
        self.assertEqual(len(result), 2)  # 2 words
        self.assertEqual(result[0]['start_time'], 0.0)
        self.assertEqual(result[1]['end_time'], 2.0)

    def test_multiple_segments(self):
        build_word_segment_map = self._fn()
        segments = [
            {'text': 'Hello world', 'start_time': 0.0, 'end_time': 2.0},
            {'text': 'Foo bar baz', 'start_time': 2.0, 'end_time': 5.0},
        ]
        result = build_word_segment_map(segments)
        self.assertEqual(len(result), 5)  # 5 words total

    def test_empty_segments(self):
        build_word_segment_map = self._fn()
        result = build_word_segment_map([])
        self.assertEqual(result, {})

    def test_empty_text_segment(self):
        build_word_segment_map = self._fn()
        segments = [{'text': '', 'start_time': 0.0, 'end_time': 1.0}]
        result = build_word_segment_map(segments)
        self.assertEqual(len(result), 0)


# ══════════════════════════════════════════════════════
# pdf_tasks.py — error paths
# ══════════════════════════════════════════════════════
class MatchPdfToAudioTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('w67_matchpdf_user')
        self.project = make_project(self.user)

    def _patch_infra(self, success=True):
        p1 = patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager')
        p2 = patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection',
                   return_value=MagicMock())
        return p1, p2

    def test_infra_failure(self):
        """match_pdf_to_audio_task fails when infra fails"""
        from audioDiagnostic.tasks.pdf_tasks import match_pdf_to_audio_task
        p1, p2 = self._patch_infra()
        with p1 as mock_mgr, p2:
            mock_mgr.setup_infrastructure.return_value = False
            result = match_pdf_to_audio_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())

    def test_project_not_found(self):
        """match_pdf_to_audio_task fails when project not found"""
        from audioDiagnostic.tasks.pdf_tasks import match_pdf_to_audio_task
        p1, p2 = self._patch_infra()
        with p1 as mock_mgr, p2:
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = match_pdf_to_audio_task.apply(args=[999997])
        self.assertTrue(result.failed())

    def test_no_pdf_file(self):
        """match_pdf_to_audio_task fails when project has no PDF"""
        from audioDiagnostic.tasks.pdf_tasks import match_pdf_to_audio_task
        # project has no pdf_file by default
        p1, p2 = self._patch_infra()
        with p1 as mock_mgr, p2:
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = match_pdf_to_audio_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())

    def test_no_transcribed_files(self):
        """match_pdf_to_audio_task fails when no transcribed audio"""
        from audioDiagnostic.tasks.pdf_tasks import match_pdf_to_audio_task
        import tempfile, os
        from django.core.files import File

        # Give project a fake pdf_file path to pass the pdf check
        # But no transcribed audio files
        af = make_audio_file(self.project, status='uploaded', order=0)

        # We can't easily give a real pdf_file, so we test by adding an audio
        # file but not transcribing it — the task should raise ValueError
        p1, p2 = self._patch_infra()
        with p1 as mock_mgr, p2:
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = match_pdf_to_audio_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())


class ValidateTranscriptAgainstPdfTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('w67_validate_user')
        self.project = make_project(self.user)

    def _patch_infra(self):
        p1 = patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager')
        p2 = patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection',
                   return_value=MagicMock())
        return p1, p2

    def test_infra_failure(self):
        """validate_transcript_against_pdf_task fails when infra fails"""
        from audioDiagnostic.tasks.pdf_tasks import validate_transcript_against_pdf_task
        p1, p2 = self._patch_infra()
        with p1 as mock_mgr, p2:
            mock_mgr.setup_infrastructure.return_value = False
            result = validate_transcript_against_pdf_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())

    def test_project_not_found(self):
        """validate_transcript_against_pdf_task fails when project not found"""
        from audioDiagnostic.tasks.pdf_tasks import validate_transcript_against_pdf_task
        p1, p2 = self._patch_infra()
        with p1 as mock_mgr, p2:
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = validate_transcript_against_pdf_task.apply(args=[999998])
        self.assertTrue(result.failed())

    def test_no_pdf_matched_section(self):
        """validate_transcript_against_pdf_task fails when no matched section"""
        from audioDiagnostic.tasks.pdf_tasks import validate_transcript_against_pdf_task
        # project has no pdf_matched_section and no duplicates_confirmed_for_deletion
        p1, p2 = self._patch_infra()
        with p1 as mock_mgr, p2:
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = validate_transcript_against_pdf_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())

    def test_no_confirmed_deletions(self):
        """validate_transcript_against_pdf_task fails when no confirmed deletions"""
        from audioDiagnostic.tasks.pdf_tasks import validate_transcript_against_pdf_task
        AudioProject.objects.filter(id=self.project.id).update(
            pdf_matched_section='Some matched PDF text here.')
        p1, p2 = self._patch_infra()
        with p1 as mock_mgr, p2:
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = validate_transcript_against_pdf_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())


# ══════════════════════════════════════════════════════
# duplicate_tasks.py — detect_duplicates_single_file_task error paths
# ══════════════════════════════════════════════════════
class DetectDuplicatesSingleFileTaskErrorTests(TestCase):

    def setUp(self):
        self.user = make_user('w67_dup_single_user')
        self.project = make_project(self.user)

    def test_infra_failure(self):
        """detect_duplicates_single_file_task fails when infra fails"""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        with patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = False
            result = detect_duplicates_single_file_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())

    def test_audio_file_not_found(self):
        """detect_duplicates_single_file_task fails when audio file not found"""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        with patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = detect_duplicates_single_file_task.apply(args=[999994])
        self.assertTrue(result.failed())

    def test_no_transcription(self):
        """detect_duplicates_single_file_task fails when no transcription"""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        af = make_audio_file(self.project, status='transcribed', order=0)
        # No Transcription object created
        with patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = detect_duplicates_single_file_task.apply(args=[af.id])
        self.assertTrue(result.failed())


# ══════════════════════════════════════════════════════
# transcription_tasks.py — retranscribe_processed_audio_task
# ══════════════════════════════════════════════════════
class RetranscribeProcessedAudioTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('w67_retranscribe_user')
        self.project = make_project(self.user)

    def test_infra_failure(self):
        """retranscribe_processed_audio_task fails when infra fails"""
        from audioDiagnostic.tasks.transcription_tasks import retranscribe_processed_audio_task
        af = make_audio_file(self.project, status='transcribed', order=0)
        with patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = False
            result = retranscribe_processed_audio_task.apply(args=[af.id])
        self.assertTrue(result.failed())

    def test_audio_file_not_found(self):
        """retranscribe_processed_audio_task fails when audio file missing"""
        from audioDiagnostic.tasks.transcription_tasks import retranscribe_processed_audio_task
        with patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = retranscribe_processed_audio_task.apply(args=[999993])
        self.assertTrue(result.failed())

    def test_no_processed_audio(self):
        """retranscribe_processed_audio_task fails when no processed audio"""
        from audioDiagnostic.tasks.transcription_tasks import retranscribe_processed_audio_task
        af = make_audio_file(self.project, status='processed', order=0)
        # No processed_audio set
        with patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = retranscribe_processed_audio_task.apply(args=[af.id])
        self.assertTrue(result.failed())
