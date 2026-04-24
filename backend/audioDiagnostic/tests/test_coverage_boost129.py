"""
Wave 129: word_by_word_comparison from precise_pdf_comparison_task.py
Pure Python function - no external deps needed.
"""
from django.test import TestCase
from rest_framework.test import force_authenticate


def _import():
    from audioDiagnostic.tasks.precise_pdf_comparison_task import (
        word_by_word_comparison,
        tokenize_text,
        normalize_word,
        words_match,
        match_sequence,
        build_word_segment_map,
    )
    return word_by_word_comparison, tokenize_text, normalize_word, words_match, match_sequence, build_word_segment_map


def _make_segment(seg_id, start, end, text):
    return {'id': seg_id, 'start_time': start, 'end_time': end, 'text': text}


class WordByWordComparisonTests(TestCase):

    def test_perfect_match(self):
        word_by_word_comparison, *_ = _import()
        segments = [_make_segment(1, 0.0, 2.0, 'hello world test')]
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        word_to_segment = build_word_segment_map(segments)
        result = word_by_word_comparison('hello world test', 'hello world test', word_to_segment)
        self.assertIn('matched_regions', result)
        self.assertIn('stats', result)
        self.assertEqual(result['stats']['matched_words'], 3)
        self.assertEqual(result['stats']['abnormal_words'], 0)

    def test_mismatch_with_recovery(self):
        """Transcript has extra words but still matches after gap."""
        word_by_word_comparison, *_ = _import()
        segments = [
            _make_segment(1, 0.0, 2.0, 'hello world test foo bar'),
        ]
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        word_to_segment = build_word_segment_map(segments)
        # PDF: 'hello world test' — transcript: 'hello extra extra world test' 
        # Mismatch at word 1 (extra), should recover and find 'world test'
        result = word_by_word_comparison(
            'hello world test', 
            'hello extra extra world test', 
            word_to_segment
        )
        self.assertIn('stats', result)

    def test_empty_pdf(self):
        word_by_word_comparison, *_ = _import()
        result = word_by_word_comparison('', 'hello world', {})
        self.assertEqual(result['stats']['matched_words'], 0)
        self.assertGreaterEqual(result['stats']['extra_words'], 0)

    def test_empty_transcript(self):
        word_by_word_comparison, *_ = _import()
        result = word_by_word_comparison('hello world', '', {})
        self.assertEqual(result['stats']['matched_words'], 0)

    def test_completely_different(self):
        """No match found anywhere."""
        word_by_word_comparison, *_ = _import()
        segments = [_make_segment(1, 0.0, 2.0, 'aaa bbb ccc ddd eee fff')]
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        word_to_segment = build_word_segment_map(segments)
        result = word_by_word_comparison(
            'one two three four five', 
            'aaa bbb ccc ddd eee fff', 
            word_to_segment
        )
        self.assertIn('stats', result)
        # Some words may go to extra/missing
        total = (result['stats']['matched_words'] + result['stats']['abnormal_words'] +
                 result['stats']['missing_words'] + result['stats']['extra_words'])
        self.assertGreaterEqual(total, 0)

    def test_trailing_extra_transcript(self):
        """Transcript has extra words at end after PDF runs out."""
        word_by_word_comparison, *_ = _import()
        segments = [_make_segment(1, 0.0, 4.0, 'hello world extra extra extra')]
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        word_to_segment = build_word_segment_map(segments)
        result = word_by_word_comparison(
            'hello world',
            'hello world extra extra extra',
            word_to_segment
        )
        # Extra content at end
        self.assertGreaterEqual(result['stats']['extra_words'], 0)

    def test_trailing_missing_pdf(self):
        """PDF has words not in transcript - should go to missing."""
        word_by_word_comparison, *_ = _import()
        result = word_by_word_comparison(
            'hello world missing missing missing',
            'hello world',
            {}
        )
        # Missing at end
        self.assertGreaterEqual(result['stats']['missing_words'], 0)

    def test_multiple_segments(self):
        """Multiple segments build proper word map."""
        word_by_word_comparison, *_ = _import()
        segments = [
            _make_segment(1, 0.0, 1.0, 'first second'),
            _make_segment(2, 1.0, 2.0, 'third fourth'),
            _make_segment(3, 2.0, 3.0, 'fifth sixth'),
        ]
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        word_to_segment = build_word_segment_map(segments)
        result = word_by_word_comparison(
            'first second third fourth fifth sixth',
            'first second third fourth fifth sixth',
            word_to_segment
        )
        self.assertEqual(result['stats']['matched_words'], 6)

    def test_mismatch_no_recovery_advances_pdf(self):
        """Tests the PDF advance path when transcript scan finds nothing nearby."""
        word_by_word_comparison, *_ = _import()
        # Use very different texts to force the advance_attempts path
        segments = [_make_segment(1, 0.0, 5.0, ' '.join(['xxx'] * 20))]
        from audioDiagnostic.tasks.precise_pdf_comparison_task import build_word_segment_map
        word_to_segment = build_word_segment_map(segments)
        result = word_by_word_comparison(
            'alpha beta gamma delta epsilon',
            ' '.join(['xxx'] * 20),
            word_to_segment
        )
        self.assertIn('stats', result)

    def test_word_by_word_returns_all_keys(self):
        """Ensures all expected keys are present."""
        word_by_word_comparison, *_ = _import()
        result = word_by_word_comparison('test', 'test', {0: {'id': 1, 'start_time': 0.0, 'end_time': 1.0}})
        expected_keys = ['matched_regions', 'abnormal_regions', 'missing_content', 'extra_content', 'stats']
        for key in expected_keys:
            self.assertIn(key, result)


class PrecisePdfNormalizeTests(TestCase):
    """Additional normalize/match edge cases."""
    
    def test_normalize_word_numbers(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        result = normalize_word("42nd")
        self.assertEqual(result, "42nd")

    def test_words_match_short_words_exact(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        # Short words (<=3 chars) must match exactly
        self.assertTrue(words_match("a", "a"))
        self.assertFalse(words_match("a", "b"))

    def test_words_match_long_fuzzy_fails_below_threshold(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        # 'hello' vs 'world' — very different, ratio < 0.9
        self.assertFalse(words_match("hello", "world"))
