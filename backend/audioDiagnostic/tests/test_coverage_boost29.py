"""
Wave 29 coverage boost: precise_pdf_comparison_task helpers (tokenize_text,
normalize_word, words_match, match_sequence, build_word_segment_map,
save_matched_region, save_abnormal_region, get_segment_ids, calculate_statistics),
plus more serializers, management command helpers.
"""
from unittest.mock import MagicMock, patch
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import force_authenticate


# ── helpers ──────────────────────────────────────────────────────────────────
def make_user(username='w29user', password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u


# ── 1. tokenize_text ──────────────────────────────────────────────────────────
class TokenizeTextTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text("Hello, world! This is a test.")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_empty(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text("")
        self.assertEqual(result, [])

    def test_extra_whitespace(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text("  hello   world  ")
        self.assertGreater(len(result), 0)

    def test_preserves_words(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text("alpha beta gamma")
        self.assertIn('alpha', result)
        self.assertIn('beta', result)


# ── 2. normalize_word ─────────────────────────────────────────────────────────
class NormalizeWordTests(TestCase):

    def test_lowercase(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        self.assertEqual(normalize_word("HELLO"), "hello")

    def test_remove_punctuation(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        self.assertEqual(normalize_word("hello,"), "hello")
        self.assertEqual(normalize_word("world!"), "world")

    def test_empty(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        result = normalize_word("")
        self.assertEqual(result, "")

    def test_apostrophe(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        result = normalize_word("it's")
        self.assertIsInstance(result, str)


# ── 3. words_match ────────────────────────────────────────────────────────────
class WordsMatchTests(TestCase):

    def test_exact_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match("hello", "hello"))

    def test_different_case(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match("Hello", "hello"))

    def test_with_punctuation(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match("hello,", "hello"))

    def test_very_different(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertFalse(words_match("hello", "world"))

    def test_fuzzy_similar(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        # "colour" vs "color" — 90%+ similar
        result = words_match("colour", "color")
        self.assertIsInstance(result, bool)

    def test_short_words_no_fuzzy(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        # Short words: no fuzzy
        result = words_match("cat", "bat")
        self.assertFalse(result)


# ── 4. match_sequence ─────────────────────────────────────────────────────────
class MatchSequenceTests(TestCase):

    def test_identical_sequences(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertTrue(match_sequence(["hello", "world"], ["hello", "world"]))

    def test_different_length(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertFalse(match_sequence(["hello"], ["hello", "world"]))

    def test_mismatched(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertFalse(match_sequence(["hello", "world"], ["hello", "there"]))

    def test_empty_sequences(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertTrue(match_sequence([], []))


# ── 5. build_word_segment_map ─────────────────────────────────────────────────
class BuildWordSegmentMapTests(TestCase):

    def test_empty_segments(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        result = build_word_segment_map([])
        self.assertEqual(result, {})

    def test_single_segment(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        segments = [{'text': 'hello world', 'start_time': 0.0, 'end_time': 1.0, 'id': 1}]
        result = build_word_segment_map(segments)
        self.assertIn(0, result)
        self.assertIn(1, result)
        self.assertEqual(result[0]['id'], 1)

    def test_multiple_segments(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        segments = [
            {'text': 'hello world', 'start_time': 0.0, 'end_time': 1.0, 'id': 1},
            {'text': 'goodbye world', 'start_time': 1.0, 'end_time': 2.0, 'id': 2},
        ]
        result = build_word_segment_map(segments)
        self.assertEqual(len(result), 4)  # 4 words total


# ── 6. save_matched_region ────────────────────────────────────────────────────
class SaveMatchedRegionTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_matched_region
        word_to_segment = {
            0: {'start_time': 0.0, 'end_time': 1.0, 'id': 1},
            1: {'start_time': 1.0, 'end_time': 2.0, 'id': 1},
        }
        result = save_matched_region(
            ['hello', 'world'], ['hello', 'world'], word_to_segment, 0)
        self.assertIsNotNone(result)
        self.assertIn('text', result)
        self.assertIn('word_count', result)

    def test_empty_trans_words(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_matched_region
        result = save_matched_region([], [], {}, 0)
        self.assertIsNone(result)

    def test_no_segment_for_word(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_matched_region
        result = save_matched_region(['hello'], ['hello'], {}, 0)
        self.assertIsNotNone(result)
        self.assertIsNone(result['start_time'])


# ── 7. save_abnormal_region ───────────────────────────────────────────────────
class SaveAbnormalRegionTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_abnormal_region
        word_to_segment = {
            0: {'start_time': 0.0, 'end_time': 1.0, 'id': 1},
        }
        result = save_abnormal_region(['extra'], word_to_segment, 0, reason='duplicate')
        self.assertIsNotNone(result)
        self.assertIn('reason', result)
        self.assertEqual(result['reason'], 'duplicate')

    def test_empty(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_abnormal_region
        result = save_abnormal_region([], {}, 0)
        self.assertIsNone(result)


# ── 8. calculate_statistics ───────────────────────────────────────────────────
class CalculateStatisticsTests(TestCase):

    def test_excellent_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        comparison = {
            'stats': {'matched_words': 950, 'abnormal_words': 10, 'extra_words': 5, 'missing_words': 5},
            'matched_regions': [1, 2, 3],
            'abnormal_regions': [],
            'missing_content': [],
            'extra_content': [],
        }
        result = calculate_statistics(comparison)
        self.assertEqual(result['match_quality'], 'excellent')
        self.assertGreater(result['accuracy_percentage'], 90)

    def test_poor_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        comparison = {
            'stats': {'matched_words': 100, 'abnormal_words': 500, 'extra_words': 200, 'missing_words': 50},
            'matched_regions': [],
            'abnormal_regions': [1, 2],
            'missing_content': [1],
            'extra_content': [],
        }
        result = calculate_statistics(comparison)
        self.assertIn(result['match_quality'], ['poor', 'fair'])

    def test_zero_words(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        comparison = {
            'stats': {'matched_words': 0, 'abnormal_words': 0, 'extra_words': 0, 'missing_words': 0},
            'matched_regions': [],
            'abnormal_regions': [],
            'missing_content': [],
            'extra_content': [],
        }
        result = calculate_statistics(comparison)
        self.assertEqual(result['accuracy_percentage'], 0.0)


# ── 9. get_segment_ids ────────────────────────────────────────────────────────
class GetSegmentIdsTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import get_segment_ids
        word_to_segment = {
            0: {'id': 1},
            1: {'id': 1},
            2: {'id': 2},
        }
        result = get_segment_ids(word_to_segment, 0, 3)
        self.assertIn(1, result)
        self.assertIn(2, result)

    def test_empty_range(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import get_segment_ids
        result = get_segment_ids({}, 0, 0)
        self.assertEqual(result, [])

    def test_missing_words(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import get_segment_ids
        result = get_segment_ids({}, 10, 5)
        self.assertEqual(result, [])


# ── 10. More serializers coverage ─────────────────────────────────────────────
class SerializersMoreTests(TestCase):

    def test_audio_project_serializer_basic(self):
        from audioDiagnostic.serializers import AudioProjectSerializer
        user = make_user('w29_serial_user')
        from audioDiagnostic.models import AudioProject
        project = AudioProject.objects.create(user=user, title='Test Serial', status='ready')
        serializer = AudioProjectSerializer(project)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('title', data)
        self.assertEqual(data['title'], 'Test Serial')

    def test_audio_file_serializer_basic(self):
        from audioDiagnostic.serializers import AudioFileSerializer
        user = make_user('w29_serial2_user')
        from audioDiagnostic.models import AudioProject, AudioFile
        project = AudioProject.objects.create(user=user, title='Test2', status='ready')
        af = AudioFile.objects.create(
            project=project, filename='test.wav', title='Test File',
            order_index=0, status='uploaded')
        serializer = AudioFileSerializer(af)
        data = serializer.data
        self.assertIn('id', data)

    def test_transcription_serializer_basic(self):
        from audioDiagnostic.serializers import TranscriptionSerializer
        user = make_user('w29_serial3_user')
        from audioDiagnostic.models import AudioProject, AudioFile, Transcription
        project = AudioProject.objects.create(user=user, title='Test3', status='ready')
        af = AudioFile.objects.create(
            project=project, filename='test.wav', title='Test File',
            order_index=0, status='uploaded')
        tr = Transcription.objects.create(audio_file=af, full_text='Test transcription text.')
        serializer = TranscriptionSerializer(tr)
        data = serializer.data
        self.assertIn('id', data)
