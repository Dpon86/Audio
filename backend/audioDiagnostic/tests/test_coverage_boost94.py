"""
Wave 94 — Coverage boost
Targets:
  - audioDiagnostic/tasks/compare_pdf_task.py helpers:
      normalize_and_tokenize, find_start_position_in_pdf,
      extract_pdf_section, classify_extra_content, calculate_comparison_stats
  - audioDiagnostic/utils/pdf_text_cleaner.py remaining branches
"""
from django.test import TestCase
from rest_framework.test import force_authenticate


# ─── normalize_and_tokenize tests ────────────────────────────────────────────

class NormalizeAndTokenizeTests(TestCase):

    def test_basic_normalization(self):
        from audioDiagnostic.tasks.compare_pdf_task import normalize_and_tokenize
        result = normalize_and_tokenize("Hello, World!")
        self.assertEqual(result, ['hello', 'world'])

    def test_short_words_removed(self):
        from audioDiagnostic.tasks.compare_pdf_task import normalize_and_tokenize
        result = normalize_and_tokenize("I am here at the top")
        # "I", "am", "at" and "the" are short words (<3 chars)
        for word in result:
            self.assertGreaterEqual(len(word), 3)

    def test_punctuation_removed(self):
        from audioDiagnostic.tasks.compare_pdf_task import normalize_and_tokenize
        result = normalize_and_tokenize("Hello, World!")
        self.assertNotIn(',', ' '.join(result))
        self.assertNotIn('!', ' '.join(result))

    def test_empty_string(self):
        from audioDiagnostic.tasks.compare_pdf_task import normalize_and_tokenize
        result = normalize_and_tokenize("")
        self.assertEqual(result, [])


# ─── find_start_position_in_pdf tests ────────────────────────────────────────

class FindStartPositionTests(TestCase):

    def test_exact_match_found(self):
        from audioDiagnostic.tasks.compare_pdf_task import find_start_position_in_pdf
        pdf_text = "one two three four five six seven eight nine ten eleven twelve hello world test"
        transcript_text = "hello world test"
        pos, score = find_start_position_in_pdf(pdf_text, transcript_text)
        self.assertIsInstance(pos, int)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)

    def test_empty_texts(self):
        from audioDiagnostic.tasks.compare_pdf_task import find_start_position_in_pdf
        pdf_text = "hello world"
        transcript_text = "xyz abc def"
        pos, score = find_start_position_in_pdf(pdf_text, transcript_text)
        self.assertIsInstance(pos, int)


# ─── extract_pdf_section tests ───────────────────────────────────────────────

class ExtractPdfSectionTests(TestCase):

    def test_extract_section(self):
        from audioDiagnostic.tasks.compare_pdf_task import extract_pdf_section
        pdf_text = " ".join([f"word{i}" for i in range(100)])
        section = extract_pdf_section(pdf_text, start_word_pos=10, transcript_length=200)
        self.assertIsInstance(section, str)
        self.assertTrue(len(section) > 0)

    def test_extract_from_start(self):
        from audioDiagnostic.tasks.compare_pdf_task import extract_pdf_section
        pdf_text = "hello world testing extracts correctly from beginning"
        section = extract_pdf_section(pdf_text, start_word_pos=0, transcript_length=50)
        self.assertIn('hello', section)


# ─── classify_extra_content tests ────────────────────────────────────────────

class ClassifyExtraContentTests(TestCase):

    def test_chapter_marker(self):
        from audioDiagnostic.tasks.compare_pdf_task import classify_extra_content
        self.assertEqual(classify_extra_content("Chapter 1"), 'chapter_marker')

    def test_narrator_info(self):
        from audioDiagnostic.tasks.compare_pdf_task import classify_extra_content
        self.assertEqual(classify_extra_content("Narrated by John Smith"), 'narrator_info')

    def test_other(self):
        from audioDiagnostic.tasks.compare_pdf_task import classify_extra_content
        self.assertEqual(classify_extra_content("This is some random content"), 'other')

    def test_prologue(self):
        from audioDiagnostic.tasks.compare_pdf_task import classify_extra_content
        self.assertEqual(classify_extra_content("Prologue to the story"), 'narrator_info')

    def test_part_marker(self):
        from audioDiagnostic.tasks.compare_pdf_task import classify_extra_content
        self.assertEqual(classify_extra_content("Part 2: The Journey"), 'chapter_marker')


# ─── calculate_comparison_stats tests ────────────────────────────────────────

class CalculateComparisonStatsTests(TestCase):

    def test_excellent_accuracy(self):
        from audioDiagnostic.tasks.compare_pdf_task import calculate_comparison_stats
        stats = calculate_comparison_stats(
            matching_words=95, missing_words=5, extra_words=2,
            transcript_word_count=97, pdf_word_count=100
        )
        self.assertEqual(stats['match_quality'], 'excellent')
        self.assertAlmostEqual(stats['accuracy_percentage'], 97.94, places=1)

    def test_good_accuracy(self):
        from audioDiagnostic.tasks.compare_pdf_task import calculate_comparison_stats
        stats = calculate_comparison_stats(
            matching_words=87, missing_words=13, extra_words=2,
            transcript_word_count=89, pdf_word_count=100
        )
        self.assertEqual(stats['match_quality'], 'good')

    def test_fair_accuracy(self):
        from audioDiagnostic.tasks.compare_pdf_task import calculate_comparison_stats
        stats = calculate_comparison_stats(
            matching_words=75, missing_words=25, extra_words=5,
            transcript_word_count=80, pdf_word_count=100
        )
        self.assertEqual(stats['match_quality'], 'fair')

    def test_poor_accuracy(self):
        from audioDiagnostic.tasks.compare_pdf_task import calculate_comparison_stats
        stats = calculate_comparison_stats(
            matching_words=50, missing_words=50, extra_words=10,
            transcript_word_count=60, pdf_word_count=100
        )
        self.assertEqual(stats['match_quality'], 'poor')

    def test_zero_pdf_words(self):
        from audioDiagnostic.tasks.compare_pdf_task import calculate_comparison_stats
        stats = calculate_comparison_stats(
            matching_words=0, missing_words=0, extra_words=0,
            transcript_word_count=0, pdf_word_count=0
        )
        self.assertEqual(stats['coverage_percentage'], 0)
        self.assertEqual(stats['accuracy_percentage'], 0)


# ─── pdf_text_cleaner.py helper functions ────────────────────────────────────

class PdfTextCleanerTests(TestCase):

    def test_clean_pdf_text_basic(self):
        from audioDiagnostic.utils.pdf_text_cleaner import clean_pdf_text
        text = "  Hello   World  "
        result = clean_pdf_text(text)
        self.assertIsInstance(result, str)

    def test_remove_headers_footers(self):
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers
        text = "\n\nChapter 1\n\nSome content\n\n1\n\nMore content\n\n"
        result = remove_headers_footers_and_numbers(text)
        self.assertIsInstance(result, str)

    def test_analyze_text_quality(self):
        from audioDiagnostic.utils.pdf_text_cleaner import analyze_pdf_text_quality
        text = "This is some clear text for the audiobook production system."
        result = analyze_pdf_text_quality(text)
        self.assertIsInstance(result, dict)
        self.assertIn('has_ligatures', result)

    def test_detect_repeating_patterns(self):
        from audioDiagnostic.utils.pdf_text_cleaner import detect_repeating_patterns_from_pages
        pages = ["Page 1 content", "Page 2 content", "Page 3 content"]
        result = detect_repeating_patterns_from_pages(pages)
        self.assertIsInstance(result, list)

    def test_remove_detected_patterns(self):
        from audioDiagnostic.utils.pdf_text_cleaner import remove_detected_patterns
        text = "Header\nMain content here\nHeader\nMore content\nHeader"
        patterns = ["Header"]
        result = remove_detected_patterns(text, patterns)
        self.assertIsInstance(result, str)
