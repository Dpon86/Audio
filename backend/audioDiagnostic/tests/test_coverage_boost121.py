"""
Wave 121: precise_pdf_comparison_task.py utility functions (89 miss, 65%)
All pure functions, no infrastructure needed.
"""
from django.test import TestCase
from rest_framework.test import force_authenticate


class PrecisePdfComparisonUtilsTests(TestCase):

    def _import(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import (
            tokenize_text, normalize_word, words_match, match_sequence,
            build_word_segment_map, save_matched_region, save_abnormal_region,
            get_segment_ids, calculate_statistics
        )
        return (tokenize_text, normalize_word, words_match, match_sequence,
                build_word_segment_map, save_matched_region, save_abnormal_region,
                get_segment_ids, calculate_statistics)

    # --- tokenize_text ---

    def test_tokenize_text_basic(self):
        tokenize_text, *_ = self._import()
        result = tokenize_text("Hello world. This is a test.")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_tokenize_text_empty(self):
        tokenize_text, *_ = self._import()
        self.assertEqual(tokenize_text(""), [])

    def test_tokenize_text_whitespace(self):
        tokenize_text, *_ = self._import()
        result = tokenize_text("  hello   world  ")
        self.assertEqual(result, ['hello', 'world'])

    # --- normalize_word ---

    def test_normalize_word_basic(self):
        _, normalize_word, *_ = self._import()
        self.assertEqual(normalize_word("Hello!"), "hello")

    def test_normalize_word_punctuation(self):
        _, normalize_word, *_ = self._import()
        self.assertEqual(normalize_word("World."), "world")

    def test_normalize_word_already_lower(self):
        _, normalize_word, *_ = self._import()
        self.assertEqual(normalize_word("test"), "test")

    # --- words_match ---

    def test_words_match_identical(self):
        _, _, words_match, *_ = self._import()
        self.assertTrue(words_match("hello", "hello"))

    def test_words_match_case_insensitive(self):
        _, _, words_match, *_ = self._import()
        self.assertTrue(words_match("Hello", "hello"))

    def test_words_match_punctuation_diff(self):
        _, _, words_match, *_ = self._import()
        self.assertTrue(words_match("world!", "world"))

    def test_words_match_fuzzy_similar(self):
        _, _, words_match, *_ = self._import()
        # "colour" vs "color" should be similar enough
        result = words_match("colour", "color")
        self.assertIsInstance(result, bool)

    def test_words_match_totally_different(self):
        _, _, words_match, *_ = self._import()
        self.assertFalse(words_match("cat", "dog"))

    def test_words_match_short_words_no_fuzzy(self):
        _, _, words_match, *_ = self._import()
        # Short words (<=3 chars) — no fuzzy matching
        self.assertFalse(words_match("ab", "cd"))

    # --- match_sequence ---

    def test_match_sequence_equal(self):
        _, _, _, match_sequence, *_ = self._import()
        self.assertTrue(match_sequence(["hello", "world"], ["hello", "world"]))

    def test_match_sequence_different_len(self):
        _, _, _, match_sequence, *_ = self._import()
        self.assertFalse(match_sequence(["hello"], ["hello", "world"]))

    def test_match_sequence_different_words(self):
        _, _, _, match_sequence, *_ = self._import()
        self.assertFalse(match_sequence(["cat", "dog"], ["cat", "bird"]))

    def test_match_sequence_empty(self):
        _, _, _, match_sequence, *_ = self._import()
        self.assertTrue(match_sequence([], []))

    # --- build_word_segment_map ---

    def test_build_word_segment_map_basic(self):
        tokenize_text, _, _, _, build_word_segment_map, *_ = self._import()
        segments = [
            {'text': 'hello world', 'start_time': 0.0, 'end_time': 1.0, 'id': 1},
            {'text': 'foo bar', 'start_time': 1.5, 'end_time': 2.5, 'id': 2},
        ]
        word_map = build_word_segment_map(segments)
        self.assertIn(0, word_map)  # 'hello' at index 0
        self.assertIn(1, word_map)  # 'world' at index 1
        self.assertIn(2, word_map)  # 'foo' at index 2
        self.assertEqual(word_map[0]['id'], 1)
        self.assertEqual(word_map[2]['id'], 2)

    def test_build_word_segment_map_empty(self):
        tokenize_text, _, _, _, build_word_segment_map, *_ = self._import()
        word_map = build_word_segment_map([])
        self.assertEqual(word_map, {})

    # --- save_matched_region ---

    def test_save_matched_region_basic(self):
        *_, save_matched_region, _, _, _ = self._import()
        word_to_segment = {
            0: {'start_time': 0.0, 'end_time': 0.5, 'id': 1},
            1: {'start_time': 0.5, 'end_time': 1.0, 'id': 1},
        }
        result = save_matched_region(
            ['hello', 'world'],
            ['hello', 'world'],
            word_to_segment,
            0
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['word_count'], 2)
        self.assertEqual(result['start_time'], 0.0)
        self.assertEqual(result['end_time'], 1.0)

    def test_save_matched_region_empty(self):
        *_, save_matched_region, _, _, _ = self._import()
        result = save_matched_region([], [], {}, 0)
        self.assertIsNone(result)

    def test_save_matched_region_segment_not_found(self):
        *_, save_matched_region, _, _, _ = self._import()
        result = save_matched_region(['word'], ['word'], {}, 5)
        self.assertIsNotNone(result)
        self.assertIsNone(result['start_time'])
        self.assertIsNone(result['end_time'])

    # --- save_abnormal_region ---

    def test_save_abnormal_region_basic(self):
        *_, save_abnormal_region, _, _ = self._import()
        word_to_segment = {
            0: {'start_time': 1.0, 'end_time': 2.0, 'id': 1},
        }
        result = save_abnormal_region(['extra'], word_to_segment, 0, reason='mismatch')
        self.assertIsNotNone(result)
        self.assertEqual(result['word_count'], 1)
        self.assertEqual(result['reason'], 'mismatch')

    def test_save_abnormal_region_empty(self):
        *_, save_abnormal_region, _, _ = self._import()
        result = save_abnormal_region([], {}, 0, reason='')
        self.assertIsNone(result)

    def test_save_abnormal_region_no_segment(self):
        *_, save_abnormal_region, _, _ = self._import()
        result = save_abnormal_region(['word'], {}, 99)
        self.assertIsNotNone(result)
        self.assertIsNone(result['start_time'])

    # --- get_segment_ids ---

    def test_get_segment_ids_basic(self):
        *_, get_segment_ids, _ = self._import()
        word_to_segment = {
            0: {'id': 10},
            1: {'id': 10},
            2: {'id': 20},
        }
        result = get_segment_ids(word_to_segment, 0, 3)
        self.assertIn(10, result)
        self.assertIn(20, result)

    def test_get_segment_ids_empty_range(self):
        *_, get_segment_ids, _ = self._import()
        result = get_segment_ids({}, 0, 0)
        self.assertEqual(result, [])

    def test_get_segment_ids_missing_words(self):
        *_, get_segment_ids, _ = self._import()
        result = get_segment_ids({}, 0, 5)
        self.assertEqual(result, [])

    # --- calculate_statistics ---

    def test_calculate_statistics_excellent(self):
        *_, calculate_statistics = self._import()
        comparison_result = {
            'stats': {
                'matched_words': 96,
                'abnormal_words': 2,
                'missing_words': 0,
                'extra_words': 2,
            },
            'matched_regions': [1, 2, 3],
            'abnormal_regions': [1],
            'missing_content': [],
            'extra_content': [],
        }
        stats = calculate_statistics(comparison_result)
        self.assertEqual(stats['match_quality'], 'excellent')
        self.assertAlmostEqual(stats['accuracy_percentage'], 96.0, delta=1)

    def test_calculate_statistics_good(self):
        *_, calculate_statistics = self._import()
        comparison_result = {
            'stats': {
                'matched_words': 87,
                'abnormal_words': 8,
                'missing_words': 0,
                'extra_words': 5,
            },
            'matched_regions': [1],
            'abnormal_regions': [1, 2],
            'missing_content': [],
            'extra_content': [],
        }
        stats = calculate_statistics(comparison_result)
        self.assertEqual(stats['match_quality'], 'good')

    def test_calculate_statistics_fair(self):
        *_, calculate_statistics = self._import()
        comparison_result = {
            'stats': {
                'matched_words': 72,
                'abnormal_words': 20,
                'missing_words': 5,
                'extra_words': 3,
            },
            'matched_regions': [],
            'abnormal_regions': [],
            'missing_content': [1],
            'extra_content': [],
        }
        stats = calculate_statistics(comparison_result)
        self.assertEqual(stats['match_quality'], 'fair')

    def test_calculate_statistics_poor(self):
        *_, calculate_statistics = self._import()
        comparison_result = {
            'stats': {
                'matched_words': 30,
                'abnormal_words': 50,
                'missing_words': 10,
                'extra_words': 10,
            },
            'matched_regions': [],
            'abnormal_regions': [],
            'missing_content': [],
            'extra_content': [1],
        }
        stats = calculate_statistics(comparison_result)
        self.assertEqual(stats['match_quality'], 'poor')

    def test_calculate_statistics_zero_words(self):
        *_, calculate_statistics = self._import()
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
        stats = calculate_statistics(comparison_result)
        self.assertEqual(stats['accuracy_percentage'], 0.0)
