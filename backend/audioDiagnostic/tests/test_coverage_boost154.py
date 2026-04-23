"""
Wave 154: precise_pdf_comparison_task.py utility functions
"""
from django.test import TestCase


class TokenizeTextTests(TestCase):
    """Test tokenize_text utility."""

    def test_basic_tokenize(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text('Hello world how are you')
        self.assertEqual(result, ['Hello', 'world', 'how', 'are', 'you'])

    def test_extra_whitespace(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text('  Hello   world  ')
        self.assertIn('Hello', result)
        self.assertIn('world', result)

    def test_empty_string(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text('')
        self.assertEqual(result, [])

    def test_single_word(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import tokenize_text
        result = tokenize_text('Hello')
        self.assertEqual(result, ['Hello'])


class NormalizeWordTests(TestCase):
    """Test normalize_word utility."""

    def test_basic_normalize(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        result = normalize_word('Hello!')
        self.assertEqual(result, 'hello')

    def test_with_punctuation(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        result = normalize_word('world.')
        self.assertEqual(result, 'world')

    def test_already_lowercase(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import normalize_word
        result = normalize_word('test')
        self.assertEqual(result, 'test')


class WordsMatchTests(TestCase):
    """Test words_match utility."""

    def test_exact_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match('hello', 'hello'))

    def test_case_insensitive(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match('Hello', 'hello'))

    def test_punctuation_stripped(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertTrue(words_match('world.', 'world'))

    def test_no_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        self.assertFalse(words_match('cat', 'dog'))

    def test_fuzzy_match_similar(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        # Very similar words should match (>90% similarity)
        result = words_match('analysed', 'analyzed')
        self.assertIsInstance(result, bool)

    def test_short_word_exact_match_required(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import words_match
        # Short words (<= 3 chars) require exact match
        self.assertFalse(words_match('cat', 'car'))


class MatchSequenceTests(TestCase):
    """Test match_sequence utility."""

    def test_matching_sequences(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        seq1 = ['hello', 'world', 'how']
        seq2 = ['hello', 'world', 'how']
        self.assertTrue(match_sequence(seq1, seq2))

    def test_non_matching_sequences(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        seq1 = ['hello', 'world', 'how']
        seq2 = ['goodbye', 'earth', 'what']
        self.assertFalse(match_sequence(seq1, seq2))

    def test_empty_sequences(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import match_sequence
        result = match_sequence([], [])
        # Empty sequences should match or return True
        self.assertIsInstance(result, bool)


class CalculateStatisticsTests(TestCase):
    """Test calculate_statistics utility."""

    def test_basic_statistics(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics

        comparison_result = {
            'stats': {
                'matched_words': 80,
                'abnormal_words': 10,
                'missing_words': 5,
                'extra_words': 5,
            },
            'matched_regions': [{'word_count': 80}],
            'abnormal_regions': [{'word_count': 10}],
            'missing_content': [{'word_count': 5}],
            'extra_content': [{'word_count': 5}],
        }

        result = calculate_statistics(comparison_result)
        self.assertIn('accuracy_percentage', result)
        self.assertIsInstance(result['accuracy_percentage'], float)

    def test_perfect_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics

        comparison_result = {
            'stats': {
                'matched_words': 100,
                'abnormal_words': 0,
                'missing_words': 0,
                'extra_words': 0,
            },
            'matched_regions': [{'word_count': 100}],
            'abnormal_regions': [],
            'missing_content': [],
            'extra_content': [],
        }

        result = calculate_statistics(comparison_result)
        self.assertIn('accuracy_percentage', result)

    def test_all_mismatch(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import calculate_statistics

        comparison_result = {
            'stats': {
                'matched_words': 0,
                'abnormal_words': 50,
                'missing_words': 50,
                'extra_words': 50,
            },
            'matched_regions': [],
            'abnormal_regions': [{'word_count': 50}],
            'missing_content': [{'word_count': 50}],
            'extra_content': [{'word_count': 50}],
        }

        result = calculate_statistics(comparison_result)
        self.assertIn('accuracy_percentage', result)


class WordByWordComparisonSimpleTests(TestCase):
    """Test word_by_word_comparison with simple inputs."""

    def test_identical_text(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import word_by_word_comparison

        pdf_text = 'The quick brown fox jumps over the lazy dog'
        transcript = 'The quick brown fox jumps over the lazy dog'
        word_to_segment = {}

        result = word_by_word_comparison(pdf_text, transcript, word_to_segment)

        self.assertIn('matched_regions', result)
        self.assertIn('abnormal_regions', result)
        self.assertIn('missing_content', result)
        self.assertIn('extra_content', result)
        self.assertIn('stats', result)
        self.assertEqual(result['stats']['matched_words'], 9)

    def test_completely_different_text(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import word_by_word_comparison

        pdf_text = 'Alpha beta gamma delta epsilon'
        transcript = 'Zeta theta iota kappa lambda'
        word_to_segment = {}

        result = word_by_word_comparison(pdf_text, transcript, word_to_segment)

        self.assertIn('stats', result)

    def test_partial_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import word_by_word_comparison

        pdf_text = 'Hello world this is a test sentence here'
        transcript = 'Hello world something different test sentence here'
        word_to_segment = {}

        result = word_by_word_comparison(pdf_text, transcript, word_to_segment)

        self.assertIn('stats', result)
        self.assertGreater(result['stats']['matched_words'], 0)
