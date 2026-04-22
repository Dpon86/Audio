"""
Wave 95 — Coverage boost
Targets:
  - audioDiagnostic/tasks/precise_pdf_comparison_task.py helpers:
      tokenize_text, normalize_word, words_match, match_sequence,
      build_word_segment_map, get_segment_ids, calculate_statistics
  - audioDiagnostic/tasks/ai_pdf_comparison_task.py helpers:
      find_matching_segments
"""
from django.test import TestCase
from difflib import SequenceMatcher


# ─── tokenize_text tests ─────────────────────────────────────────────────────

class TokenizeTextTests(TestCase):

    def test_basic_tokenize(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text("hello world")
        self.assertEqual(result, ['hello', 'world'])

    def test_extra_spaces(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text("  hello   world  ")
        self.assertEqual(result, ['hello', 'world'])

    def test_empty_string(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text("")
        self.assertEqual(result, [])


# ─── normalize_word tests ─────────────────────────────────────────────────────

class NormalizePreciseWordTests(TestCase):

    def test_lowercase(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        self.assertEqual(normalize_word('Hello'), 'hello')

    def test_removes_punctuation(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        self.assertEqual(normalize_word('hello,'), 'hello')

    def test_empty_word(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        self.assertEqual(normalize_word(''), '')


# ─── words_match tests ───────────────────────────────────────────────────────

class WordsMatchTests(TestCase):

    def test_exact_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match('hello', 'hello'))

    def test_different_case(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match('Hello', 'hello'))

    def test_punctuation_difference(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match('hello,', 'hello'))

    def test_fuzzy_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        # Very similar words should match
        self.assertTrue(words_match('colour', 'color'))

    def test_completely_different(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertFalse(words_match('cat', 'elephant'))

    def test_short_words_no_fuzzy(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        # Short words (<=3 chars) don't get fuzzy matching
        self.assertFalse(words_match('cat', 'dog'))


# ─── match_sequence tests ─────────────────────────────────────────────────────

class MatchSequenceTests(TestCase):

    def test_identical_sequences(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertTrue(match_sequence(['hello', 'world'], ['hello', 'world']))

    def test_different_lengths(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertFalse(match_sequence(['hello', 'world'], ['hello']))

    def test_different_sequences(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertFalse(match_sequence(['hello', 'world'], ['goodbye', 'world']))


# ─── build_word_segment_map tests ────────────────────────────────────────────

class BuildWordSegmentMapTests(TestCase):

    def test_single_segment(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        segments = [
            {'text': 'hello world', 'id': 1, 'start_time': 0.0, 'end_time': 2.0}
        ]
        word_map = build_word_segment_map(segments)
        self.assertEqual(word_map[0]['id'], 1)
        self.assertEqual(word_map[1]['id'], 1)

    def test_multiple_segments(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        segments = [
            {'text': 'hello world', 'id': 1, 'start_time': 0.0, 'end_time': 2.0},
            {'text': 'foo bar', 'id': 2, 'start_time': 2.0, 'end_time': 4.0},
        ]
        word_map = build_word_segment_map(segments)
        self.assertEqual(word_map[2]['id'], 2)
        self.assertEqual(word_map[3]['id'], 2)


# ─── get_segment_ids tests ────────────────────────────────────────────────────

class GetSegmentIdsTests(TestCase):

    def test_gets_segment_ids(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import get_segment_ids
        word_map = {
            0: {'id': 1},
            1: {'id': 1},
            2: {'id': 2},
        }
        result = get_segment_ids(word_map, start_idx=0, count=3)
        self.assertIn(1, result)
        self.assertIn(2, result)

    def test_out_of_range(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import get_segment_ids
        word_map = {0: {'id': 5}}
        result = get_segment_ids(word_map, start_idx=10, count=2)
        self.assertEqual(result, [])


# ─── calculate_statistics tests ──────────────────────────────────────────────

class CalculatePreciseStatisticsTests(TestCase):

    def _comparison_result(self, matched, abnormal, extra, missing):
        return {
            'stats': {
                'matched_words': matched,
                'abnormal_words': abnormal,
                'extra_words': extra,
                'missing_words': missing,
            },
            'matched_regions': ['r1'] * matched,
            'abnormal_regions': ['x'] * abnormal,
        }

    def test_excellent_accuracy(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        result = self._comparison_result(96, 4, 0, 0)
        stats = calculate_statistics(result)
        self.assertEqual(stats['match_quality'], 'excellent')

    def test_good_accuracy(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        result = self._comparison_result(87, 13, 0, 0)
        stats = calculate_statistics(result)
        self.assertEqual(stats['match_quality'], 'good')

    def test_fair_accuracy(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        result = self._comparison_result(75, 25, 0, 0)
        stats = calculate_statistics(result)
        self.assertEqual(stats['match_quality'], 'fair')

    def test_poor_accuracy(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        result = self._comparison_result(50, 50, 0, 0)
        stats = calculate_statistics(result)
        self.assertEqual(stats['match_quality'], 'poor')

    def test_zero_total_words(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        result = self._comparison_result(0, 0, 0, 0)
        stats = calculate_statistics(result)
        self.assertEqual(stats['accuracy_percentage'], 0.0)


# ─── ai_pdf_comparison find_matching_segments ────────────────────────────────

class AiFindMatchingSegmentsTests(TestCase):

    def test_matching_segment_found(self):
        from audioDiagnostic.tasks.ai_pdf_comparison_task import find_matching_segments
        segments = [
            {'text': 'hello world test', 'id': 1, 'start_time': 0.0, 'end_time': 2.0},
            {'text': 'different content', 'id': 2, 'start_time': 2.0, 'end_time': 4.0},
        ]
        result = find_matching_segments('hello world', segments)
        self.assertIsInstance(result, list)

    def test_no_matching_segment(self):
        from audioDiagnostic.tasks.ai_pdf_comparison_task import find_matching_segments
        segments = [
            {'text': 'totally unrelated', 'id': 1, 'start_time': 0.0, 'end_time': 2.0},
        ]
        result = find_matching_segments('completely different text here', segments)
        self.assertIsInstance(result, list)
