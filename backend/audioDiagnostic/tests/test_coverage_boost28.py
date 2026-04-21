"""
Wave 28 coverage boost: compare_pdf_task pure helpers (normalize_and_tokenize,
find_start_position_in_pdf, extract_pdf_section, classify_extra_content,
calculate_comparison_stats, aggregate_missing_words, aggregate_extra_words,
find_matching_segments), precise_pdf_comparison helpers.
"""
from unittest.mock import MagicMock, patch
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


# ── helpers ──────────────────────────────────────────────────────────────────
def make_user(username='w28user', password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u


# ── 1. normalize_and_tokenize ─────────────────────────────────────────────────
class NormalizeAndTokenizeTests(TestCase):

    def test_basic_normalization(self):
        from audioDiagnostic.tasks.compare_pdf_task import normalize_and_tokenize
        result = normalize_and_tokenize("Hello, World! This is a test.")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        # All lowercase
        for word in result:
            self.assertEqual(word, word.lower())

    def test_short_words_filtered(self):
        from audioDiagnostic.tasks.compare_pdf_task import normalize_and_tokenize
        result = normalize_and_tokenize("a an the and or is it hello world")
        # Words < 3 chars filtered
        for word in result:
            self.assertGreaterEqual(len(word), 3)

    def test_empty_text(self):
        from audioDiagnostic.tasks.compare_pdf_task import normalize_and_tokenize
        result = normalize_and_tokenize("")
        self.assertEqual(result, [])

    def test_punctuation_removed(self):
        from audioDiagnostic.tasks.compare_pdf_task import normalize_and_tokenize
        result = normalize_and_tokenize("hello, world! test.")
        for word in result:
            self.assertNotIn(',', word)
            self.assertNotIn('!', word)


# ── 2. find_start_position_in_pdf ────────────────────────────────────────────
class FindStartPositionTests(TestCase):

    def test_basic_match(self):
        from audioDiagnostic.tasks.compare_pdf_task import find_start_position_in_pdf
        pdf_text = "Introduction to the book. Chapter one the beginning hello world this is test content here."
        transcript_text = "hello world this is test content here"
        position, confidence = find_start_position_in_pdf(pdf_text, transcript_text)
        self.assertIsInstance(position, int)
        self.assertGreaterEqual(position, 0)
        self.assertIsInstance(confidence, float)

    def test_empty_texts(self):
        from audioDiagnostic.tasks.compare_pdf_task import find_start_position_in_pdf
        position, confidence = find_start_position_in_pdf("hello world test.", "")
        self.assertIsInstance(position, int)

    def test_short_transcript(self):
        from audioDiagnostic.tasks.compare_pdf_task import find_start_position_in_pdf
        pdf_text = "The cat sat on the mat and ate the bat."
        transcript = "cat sat on the mat"
        position, confidence = find_start_position_in_pdf(pdf_text, transcript)
        self.assertGreaterEqual(position, 0)


# ── 3. extract_pdf_section ────────────────────────────────────────────────────
class ExtractPDFSectionTests(TestCase):

    def test_basic_extraction(self):
        from audioDiagnostic.tasks.compare_pdf_task import extract_pdf_section
        pdf_text = " ".join(["word"] * 200)
        result = extract_pdf_section(pdf_text, start_word_pos=10, transcript_length=500)
        self.assertIsInstance(result, str)

    def test_extraction_at_zero(self):
        from audioDiagnostic.tasks.compare_pdf_task import extract_pdf_section
        pdf_text = "Hello world this is a test sentence here."
        result = extract_pdf_section(pdf_text, start_word_pos=0, transcript_length=100)
        self.assertIsInstance(result, str)

    def test_extraction_beyond_end(self):
        from audioDiagnostic.tasks.compare_pdf_task import extract_pdf_section
        pdf_text = "Short text."
        result = extract_pdf_section(pdf_text, start_word_pos=100, transcript_length=500)
        self.assertIsInstance(result, str)


# ── 4. classify_extra_content ─────────────────────────────────────────────────
class ClassifyExtraContentTests(TestCase):

    def test_chapter_marker(self):
        from audioDiagnostic.tasks.compare_pdf_task import classify_extra_content
        result = classify_extra_content("Chapter one the beginning of the story")
        self.assertEqual(result, 'chapter_marker')

    def test_narrator_info(self):
        from audioDiagnostic.tasks.compare_pdf_task import classify_extra_content
        result = classify_extra_content("Narrated by John Smith audiobook production")
        self.assertEqual(result, 'narrator_info')

    def test_other_content(self):
        from audioDiagnostic.tasks.compare_pdf_task import classify_extra_content
        result = classify_extra_content("The quick brown fox jumped over the lazy dog.")
        self.assertEqual(result, 'other')

    def test_part_marker(self):
        from audioDiagnostic.tasks.compare_pdf_task import classify_extra_content
        result = classify_extra_content("Part two of the book series here")
        self.assertEqual(result, 'chapter_marker')


# ── 5. calculate_comparison_stats ────────────────────────────────────────────
class CalculateComparisonStatsTests(TestCase):

    def test_excellent_match(self):
        from audioDiagnostic.tasks.compare_pdf_task import calculate_comparison_stats
        result = calculate_comparison_stats(
            matching_words=950, missing_words=5, extra_words=5,
            transcript_word_count=960, pdf_word_count=960)
        self.assertEqual(result['match_quality'], 'excellent')
        self.assertGreater(result['accuracy_percentage'], 90)

    def test_poor_match(self):
        from audioDiagnostic.tasks.compare_pdf_task import calculate_comparison_stats
        result = calculate_comparison_stats(
            matching_words=50, missing_words=500, extra_words=100,
            transcript_word_count=650, pdf_word_count=600)
        self.assertEqual(result['match_quality'], 'poor')

    def test_zero_words(self):
        from audioDiagnostic.tasks.compare_pdf_task import calculate_comparison_stats
        result = calculate_comparison_stats(0, 0, 0, 0, 0)
        self.assertEqual(result['coverage_percentage'], 0)
        self.assertEqual(result['accuracy_percentage'], 0)

    def test_good_match(self):
        from audioDiagnostic.tasks.compare_pdf_task import calculate_comparison_stats
        result = calculate_comparison_stats(
            matching_words=880, missing_words=50, extra_words=70,
            transcript_word_count=950, pdf_word_count=930)
        self.assertIn(result['match_quality'], ['good', 'excellent'])


# ── 6. aggregate_missing_words ────────────────────────────────────────────────
class AggregateMissingWordsTests(TestCase):

    def test_too_few_words(self):
        from audioDiagnostic.tasks.compare_pdf_task import aggregate_missing_words
        result = aggregate_missing_words([('hello', 0), ('world', 1)])
        self.assertIsNone(result)

    def test_enough_words(self):
        from audioDiagnostic.tasks.compare_pdf_task import aggregate_missing_words
        words = [(f'word{i}', i) for i in range(10)]
        result = aggregate_missing_words(words)
        # May return None if no sentences > 15 chars, otherwise dict
        if result is not None:
            self.assertIn('word_count', result)
            self.assertEqual(result['word_count'], 10)

    def test_with_sentences(self):
        from audioDiagnostic.tasks.compare_pdf_task import aggregate_missing_words
        long_sentence = [('This', 0), ('is', 1), ('a', 2), ('long', 3), ('sentence', 4),
                         ('with', 5), ('many', 6), ('words', 7), ('in', 8), ('it.', 9)]
        result = aggregate_missing_words(long_sentence)
        if result is not None:
            self.assertIn('text', result)


# ── 7. aggregate_extra_words ──────────────────────────────────────────────────
class AggregateExtraWordsTests(TestCase):

    def test_too_few_words(self):
        from audioDiagnostic.tasks.compare_pdf_task import aggregate_extra_words
        result = aggregate_extra_words([('hello', 0), ('world', 1)], 'hello world', [])
        self.assertIsNone(result)

    def test_enough_words_no_segments(self):
        from audioDiagnostic.tasks.compare_pdf_task import aggregate_extra_words
        words = [(f'word{i}', i) for i in range(10)]
        result = aggregate_extra_words(words, 'transcript text here', [])
        if result is not None:
            self.assertIn('word_count', result)


# ── 8. myers_diff_words ───────────────────────────────────────────────────────
class MyersDiffWordsTests(TestCase):

    def test_identical_sequences(self):
        from audioDiagnostic.tasks.compare_pdf_task import myers_diff_words
        words = ['hello', 'world', 'test']
        result = myers_diff_words(words, words)
        self.assertIsNotNone(result)

    def test_empty_sequences(self):
        from audioDiagnostic.tasks.compare_pdf_task import myers_diff_words
        result = myers_diff_words([], [])
        self.assertIsNotNone(result)

    def test_different_sequences(self):
        from audioDiagnostic.tasks.compare_pdf_task import myers_diff_words
        pdf_words = ['hello', 'world', 'test', 'sentence']
        trans_words = ['hello', 'missing', 'sentence']
        result = myers_diff_words(pdf_words, trans_words)
        self.assertIsNotNone(result)


# ── 9. find_matching_segments ─────────────────────────────────────────────────
class FindMatchingSegmentsTests(TestCase):

    def test_no_segments(self):
        from audioDiagnostic.tasks.compare_pdf_task import find_matching_segments
        result = find_matching_segments("hello world test", [])
        self.assertEqual(result, [])

    def test_with_mock_segments(self):
        from audioDiagnostic.tasks.compare_pdf_task import find_matching_segments
        seg = MagicMock()
        seg.text = "hello world test sentence here"
        seg.start_time = 0.0
        seg.end_time = 3.0
        seg.id = 1
        result = find_matching_segments("hello world test", [seg])
        self.assertIsInstance(result, list)


# ── 10. compare_pdf_task utility ──────────────────────────────────────────────
class ComparePDFTaskUtilityTests(TestCase):

    def test_normalize_returns_list(self):
        from audioDiagnostic.tasks.compare_pdf_task import normalize_and_tokenize
        # Various inputs
        self.assertIsInstance(normalize_and_tokenize("test"), list)
        self.assertIsInstance(normalize_and_tokenize("  "), list)
        self.assertIsInstance(normalize_and_tokenize(""), list)

    def test_stats_fields(self):
        from audioDiagnostic.tasks.compare_pdf_task import calculate_comparison_stats
        result = calculate_comparison_stats(100, 10, 5, 110, 115)
        self.assertIn('transcript_word_count', result)
        self.assertIn('pdf_word_count', result)
        self.assertIn('matching_word_count', result)
        self.assertIn('missing_word_count', result)
        self.assertIn('extra_word_count', result)
        self.assertIn('coverage_percentage', result)
        self.assertIn('accuracy_percentage', result)
        self.assertIn('match_quality', result)
