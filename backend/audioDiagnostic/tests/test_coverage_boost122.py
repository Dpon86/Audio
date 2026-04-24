"""
Wave 122: pdf_tasks.py pure utility functions (195 miss, 60%)
All pure functions, no infrastructure/DB needed.
"""
from django.test import TestCase
from rest_framework.test import force_authenticate


class PdfTasksUtilsTests(TestCase):

    def test_find_pdf_section_match_exact(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        pdf_text = "This is the introduction. Hello world this is chapter one. More content here."
        transcript = "Hello world this is chapter one"
        result = find_pdf_section_match(pdf_text, transcript)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_find_pdf_section_match_fuzzy(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        pdf_text = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
                    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam.")
        transcript = "this text is not in the pdf at all whatsoever"
        result = find_pdf_section_match(pdf_text, transcript)
        self.assertIsInstance(result, str)

    def test_find_pdf_section_match_fallback(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        pdf_text = "A" * 2000
        transcript = "B" * 500
        result = find_pdf_section_match(pdf_text, transcript)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_identify_pdf_based_duplicates_no_dupes(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        segments = [
            {'text': 'Hello world', 'start': 0.0, 'end': 1.0},
            {'text': 'Something different', 'start': 1.5, 'end': 2.5},
        ]
        result = identify_pdf_based_duplicates(segments, "pdf text", "transcript text")
        self.assertEqual(result['total_duplicates'], 0)
        self.assertEqual(len(result['segments_to_keep']), 2)

    def test_identify_pdf_based_duplicates_with_dupes(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        segments = [
            {'text': 'Hello world', 'start': 0.0, 'end': 1.0},
            {'text': 'Different text', 'start': 1.5, 'end': 2.0},
            {'text': 'Hello world', 'start': 3.0, 'end': 4.0},
        ]
        result = identify_pdf_based_duplicates(segments, "pdf text", "transcript text")
        self.assertEqual(result['total_duplicates'], 1)
        # The kept one should be the LAST occurrence (start=3.0)
        kept_starts = [s['start'] for s in result['segments_to_keep']]
        self.assertIn(3.0, kept_starts)
        self.assertNotIn(0.0, kept_starts)

    def test_identify_pdf_based_duplicates_empty_segments(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        result = identify_pdf_based_duplicates([], "", "")
        self.assertEqual(result['total_duplicates'], 0)

    def test_identify_pdf_based_duplicates_empty_text(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        segments = [
            {'text': '', 'start': 0.0, 'end': 1.0},
            {'text': '   ', 'start': 1.0, 'end': 2.0},
        ]
        result = identify_pdf_based_duplicates(segments, "", "")
        # Empty segments should be skipped
        self.assertEqual(result['total_duplicates'], 0)

    def test_find_text_in_pdf_found(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        self.assertTrue(find_text_in_pdf("hello world", "This is hello world text."))

    def test_find_text_in_pdf_not_found(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        self.assertFalse(find_text_in_pdf("missing phrase", "The PDF has different content."))

    def test_find_text_in_pdf_case_insensitive(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        self.assertTrue(find_text_in_pdf("Hello World", "the hello world is here"))

    def test_find_missing_pdf_content_none_missing(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        transcript = "This is a sentence. Another sentence here."
        pdf_text = "This is a sentence. Another sentence here."
        result = find_missing_pdf_content(transcript, pdf_text)
        self.assertEqual(result, "")

    def test_find_missing_pdf_content_with_missing(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        transcript = "Only part one"
        pdf_text = "Only part one. But this sentence is missing. Also this one."
        result = find_missing_pdf_content(transcript, pdf_text)
        self.assertIsInstance(result, str)

    def test_calculate_comprehensive_similarity_identical(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        text = "The quick brown fox jumps over the lazy dog"
        result = calculate_comprehensive_similarity_task(text, text)
        self.assertGreater(result, 0.8)

    def test_calculate_comprehensive_similarity_different(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        text1 = "Hello world this is a test sentence"
        text2 = "Completely different content without overlap"
        result = calculate_comprehensive_similarity_task(text1, text2)
        self.assertLess(result, 0.5)

    def test_calculate_comprehensive_similarity_partial(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        text1 = "The quick brown fox jumps over the lazy dog in the park"
        text2 = "The quick brown fox runs through the garden nearby"
        result = calculate_comprehensive_similarity_task(text1, text2)
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)

    def test_calculate_comprehensive_similarity_empty(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        result = calculate_comprehensive_similarity_task("", "some text")
        self.assertIsInstance(result, float)

    def test_extract_chapter_title_chapter_pattern(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        text = "Chapter 1: Introduction to Audio Processing\nThis chapter covers..."
        result = extract_chapter_title_task(text)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_extract_chapter_title_numbered_section(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        text = "1. Overview of the System\nThis section explains..."
        result = extract_chapter_title_task(text)
        self.assertIsInstance(result, str)

    def test_extract_chapter_title_fallback(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        text = "the text starts here. and continues with this sentence that is reasonable length."
        result = extract_chapter_title_task(text)
        self.assertIsInstance(result, str)

    def test_extract_chapter_title_no_match(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        # Very short text with no pattern
        result = extract_chapter_title_task("x")
        self.assertIsInstance(result, str)

    def test_extract_chapter_title_section_pattern(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        text = "Section 2.3: Advanced Topics in Processing"
        result = extract_chapter_title_task(text)
        self.assertIsInstance(result, str)
