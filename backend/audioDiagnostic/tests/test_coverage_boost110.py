"""
Wave 110 — Coverage boost
Targets:
  - audioDiagnostic/tasks/precise_pdf_comparison_task.py: all pure utility functions
    (tokenize_text, normalize_word, words_match, match_sequence, build_word_segment_map,
     save_matched_region, save_abnormal_region, get_segment_ids, calculate_statistics)
"""
from django.test import TestCase


# ─── precise_pdf_comparison_task.py pure utilities ───────────────────────────

class TokenizeTextTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text("Hello world test")
        self.assertEqual(result, ['Hello', 'world', 'test'])

    def test_extra_whitespace(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text("  hello   world  ")
        self.assertEqual(result, ['hello', 'world'])

    def test_empty(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text("")
        self.assertEqual(result, [])

    def test_single_word(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text("hello")
        self.assertEqual(result, ['hello'])


class NormalizeWordTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        result = normalize_word("Hello")
        self.assertEqual(result, 'hello')

    def test_with_punctuation(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        result = normalize_word("world!")
        self.assertEqual(result, 'world')

    def test_with_comma(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        result = normalize_word("test,")
        self.assertEqual(result, 'test')


class WordsMatchTests(TestCase):

    def test_exact_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match("hello", "hello"))

    def test_case_insensitive(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match("Hello", "hello"))

    def test_punctuation_stripped(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match("world!", "world"))

    def test_no_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertFalse(words_match("apple", "orange"))

    def test_similar_words_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        # Very similar long words should match (>90% similarity)
        self.assertTrue(words_match("running", "runing"))  # ~93% similar

    def test_short_words_no_fuzzy(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        # Short words (<=3 chars) won't fuzzy match
        self.assertFalse(words_match("cat", "bat"))


class MatchSequenceTests(TestCase):

    def test_matching_sequences(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertTrue(match_sequence(['hello', 'world'], ['hello', 'world']))

    def test_different_length(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertFalse(match_sequence(['hello'], ['hello', 'world']))

    def test_different_content(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertFalse(match_sequence(['hello', 'world'], ['foo', 'bar']))

    def test_empty_sequences(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertTrue(match_sequence([], []))


class BuildWordSegmentMapTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        segments = [
            {'text': 'hello world', 'start_time': 0.0, 'end_time': 1.0, 'id': 1},
            {'text': 'foo bar', 'start_time': 1.0, 'end_time': 2.0, 'id': 2},
        ]
        result = build_word_segment_map(segments)
        self.assertIn(0, result)
        self.assertIn(1, result)
        self.assertIn(2, result)
        self.assertIn(3, result)
        self.assertEqual(result[0]['id'], 1)
        self.assertEqual(result[2]['id'], 2)

    def test_empty_segments(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        result = build_word_segment_map([])
        self.assertEqual(result, {})


class SaveMatchedRegionTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_matched_region
        word_to_segment = {
            0: {'start_time': 0.0, 'end_time': 0.5, 'id': 1},
            1: {'start_time': 0.5, 'end_time': 1.0, 'id': 1},
        }
        result = save_matched_region(['pdf_word'], ['hello', 'world'], word_to_segment, 0)
        self.assertIsNotNone(result)
        self.assertEqual(result['word_count'], 2)
        self.assertEqual(result['start_time'], 0.0)

    def test_empty_trans_words_returns_none(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_matched_region
        result = save_matched_region([], [], {}, 0)
        self.assertIsNone(result)

    def test_segment_not_found(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_matched_region
        result = save_matched_region(['pdf'], ['word'], {}, 99)
        self.assertIsNotNone(result)
        self.assertIsNone(result['start_time'])


class SaveAbnormalRegionTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_abnormal_region
        word_to_segment = {
            0: {'start_time': 1.0, 'end_time': 2.0, 'id': 5},
        }
        result = save_abnormal_region(['extra', 'word'], word_to_segment, 0, reason='extra')
        self.assertIsNotNone(result)
        self.assertEqual(result['reason'], 'extra')
        self.assertEqual(result['word_count'], 2)

    def test_empty_returns_none(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_abnormal_region
        result = save_abnormal_region([], {}, 0)
        self.assertIsNone(result)


class GetSegmentIdsTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import get_segment_ids
        word_to_segment = {
            0: {'id': 10},
            1: {'id': 10},
            2: {'id': 20},
        }
        result = get_segment_ids(word_to_segment, 0, 3)
        self.assertIn(10, result)
        self.assertIn(20, result)

    def test_missing_range(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import get_segment_ids
        result = get_segment_ids({}, 0, 5)
        self.assertEqual(result, [])


class CalculateStatisticsTests(TestCase):

    def _make_result(self, matched=80, abnormal=10, extra=5, missing=5):
        return {
            'stats': {
                'matched_words': matched,
                'abnormal_words': abnormal,
                'extra_words': extra,
                'missing_words': missing,
            },
            'matched_regions': [1, 2, 3],
            'abnormal_regions': [1],
            'missing_content': [],
            'extra_content': []
        }

    def test_excellent_quality(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        result = calculate_statistics(self._make_result(matched=98, abnormal=1, extra=0, missing=1))
        self.assertEqual(result['match_quality'], 'excellent')

    def test_good_quality(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        result = calculate_statistics(self._make_result(matched=88, abnormal=7, extra=3, missing=2))
        self.assertEqual(result['match_quality'], 'good')

    def test_fair_quality(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        result = calculate_statistics(self._make_result(matched=75, abnormal=15, extra=5, missing=5))
        self.assertEqual(result['match_quality'], 'fair')

    def test_poor_quality(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        result = calculate_statistics(self._make_result(matched=30, abnormal=40, extra=15, missing=15))
        self.assertEqual(result['match_quality'], 'poor')

    def test_zero_words(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        result = calculate_statistics(self._make_result(matched=0, abnormal=0, extra=0, missing=0))
        self.assertEqual(result['accuracy_percentage'], 0.0)

    def test_all_keys_present(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        result = calculate_statistics(self._make_result())
        expected_keys = [
            'total_transcript_words', 'matched_words', 'abnormal_words',
            'missing_words', 'extra_words', 'accuracy_percentage',
            'match_quality', 'matched_regions_count', 'abnormal_regions_count',
            'missing_sections_count', 'extra_sections_count'
        ]
        for key in expected_keys:
            self.assertIn(key, result)
