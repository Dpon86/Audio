"""
Wave 139: precise_pdf_comparison_task.py utility functions
- tokenize_text
- normalize_word
- words_match
- match_sequence
- build_word_segment_map
- save_matched_region / save_abnormal_region
- get_segment_ids
- calculate_statistics
"""
from django.test import TestCase


class TokenizeTextTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text('hello world')
        self.assertEqual(result, ['hello', 'world'])

    def test_extra_whitespace(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text('  hello   world  ')
        self.assertEqual(result, ['hello', 'world'])

    def test_empty(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text('')
        self.assertEqual(result, [])

    def test_single_word(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text('hello')
        self.assertEqual(result, ['hello'])

    def test_with_punctuation(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text('hello, world!')
        self.assertGreater(len(result), 0)


class NormalizeWordTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        self.assertEqual(normalize_word('Hello'), 'hello')

    def test_punctuation_removed(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        self.assertEqual(normalize_word('hello,'), 'hello')

    def test_all_punctuation(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        self.assertEqual(normalize_word('...'), '')

    def test_mixed(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        self.assertEqual(normalize_word("it's"), 'its')


class WordsMatchTests(TestCase):

    def test_exact_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match('hello', 'hello'))

    def test_case_insensitive(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match('Hello', 'hello'))

    def test_no_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertFalse(words_match('apple', 'orange'))

    def test_punctuation_ignored(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match('hello,', 'hello'))

    def test_very_similar_long_words(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        # 90%+ similarity for long words
        self.assertTrue(words_match('exploration', 'explorations'))

    def test_different_short_words(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertFalse(words_match('hi', 'bye'))


class MatchSequenceTests(TestCase):

    def test_matching(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertTrue(match_sequence(['hello', 'world'], ['hello', 'world']))

    def test_different_length(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertFalse(match_sequence(['hello'], ['hello', 'world']))

    def test_not_matching(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertFalse(match_sequence(['hello', 'world'], ['foo', 'bar']))

    def test_empty(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        self.assertTrue(match_sequence([], []))


class BuildWordSegmentMapTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        segments = [
            {'text': 'hello world', 'start_time': 0.0, 'end_time': 1.0, 'id': 1},
            {'text': 'foo bar baz', 'start_time': 1.0, 'end_time': 2.0, 'id': 2},
        ]
        word_map = build_word_segment_map(segments)
        self.assertEqual(word_map[0]['id'], 1)
        self.assertEqual(word_map[1]['id'], 1)
        self.assertEqual(word_map[2]['id'], 2)

    def test_empty_segments(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        result = build_word_segment_map([])
        self.assertEqual(result, {})


class SaveRegionTests(TestCase):

    def test_save_matched_region(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_matched_region
        word_to_segment = {
            0: {'start_time': 0.0, 'end_time': 1.0, 'id': 1},
            1: {'start_time': 0.5, 'end_time': 1.5, 'id': 1},
        }
        result = save_matched_region(['pdf1', 'pdf2'], ['trans1', 'trans2'], word_to_segment, 0)
        self.assertIsNotNone(result)
        self.assertEqual(result['word_count'], 2)
        self.assertEqual(result['start_time'], 0.0)
        self.assertEqual(result['end_time'], 1.5)

    def test_save_matched_region_empty(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_matched_region
        result = save_matched_region([], [], {}, 0)
        self.assertIsNone(result)

    def test_save_abnormal_region(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_abnormal_region
        word_to_segment = {
            0: {'start_time': 0.0, 'end_time': 1.0, 'id': 1},
        }
        result = save_abnormal_region(['word1'], word_to_segment, 0, reason='extra content')
        self.assertIsNotNone(result)
        self.assertEqual(result['reason'], 'extra content')

    def test_save_abnormal_region_empty(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_abnormal_region
        result = save_abnormal_region([], {}, 0)
        self.assertIsNone(result)

    def test_save_matched_region_no_segment(self):
        """Test save_matched_region with missing segment map entries."""
        from audioDiagnostic.tasks.precise_pdf_comparison_task import save_matched_region
        result = save_matched_region(['pdf'], ['word'], {}, 99)
        # Should handle missing key gracefully
        self.assertIsNotNone(result)
        self.assertIsNone(result['start_time'])


class GetSegmentIdsTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import get_segment_ids
        word_map = {
            0: {'id': 1},
            1: {'id': 1},
            2: {'id': 2},
        }
        result = get_segment_ids(word_map, 0, 3)
        self.assertIn(1, result)
        self.assertIn(2, result)

    def test_empty(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import get_segment_ids
        result = get_segment_ids({}, 0, 5)
        self.assertEqual(result, [])


class CalculateStatisticsTests(TestCase):

    def test_excellent_quality(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        comparison_result = {
            'stats': {
                'matched_words': 95,
                'abnormal_words': 3,
                'missing_words': 0,
                'extra_words': 2,
            },
            'matched_regions': [1, 2, 3],
            'abnormal_regions': [1],
            'missing_content': [],
            'extra_content': [],
        }
        result = calculate_statistics(comparison_result)
        self.assertEqual(result['match_quality'], 'excellent')
        self.assertGreater(result['accuracy_percentage'], 90)

    def test_good_quality(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        comparison_result = {
            'stats': {
                'matched_words': 87,
                'abnormal_words': 10,
                'missing_words': 2,
                'extra_words': 1,
            },
            'matched_regions': [1],
            'abnormal_regions': [1, 2],
            'missing_content': [],
            'extra_content': [],
        }
        result = calculate_statistics(comparison_result)
        self.assertEqual(result['match_quality'], 'good')

    def test_fair_quality(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        comparison_result = {
            'stats': {
                'matched_words': 75,
                'abnormal_words': 20,
                'missing_words': 5,
                'extra_words': 0,
            },
            'matched_regions': [],
            'abnormal_regions': [],
            'missing_content': ['a'],
            'extra_content': [],
        }
        result = calculate_statistics(comparison_result)
        self.assertEqual(result['match_quality'], 'fair')

    def test_poor_quality(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        comparison_result = {
            'stats': {
                'matched_words': 30,
                'abnormal_words': 60,
                'missing_words': 10,
                'extra_words': 0,
            },
            'matched_regions': [],
            'abnormal_regions': [1, 2, 3],
            'missing_content': [],
            'extra_content': ['x'],
        }
        result = calculate_statistics(comparison_result)
        self.assertEqual(result['match_quality'], 'poor')

    def test_zero_words(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics
        comparison_result = {
            'stats': {
                'matched_words': 0,
                'abnormal_words': 0,
                'missing_words': 0,
                'extra_words': 0,
            },
            'matched_regions': [],
            'abnormal_regions': [],
            'missing_content': [],
            'extra_content': [],
        }
        result = calculate_statistics(comparison_result)
        self.assertEqual(result['accuracy_percentage'], 0.0)
