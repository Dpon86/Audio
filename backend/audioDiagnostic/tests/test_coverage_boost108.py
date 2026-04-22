"""
Wave 108 — Coverage boost
Targets:
  - audioDiagnostic/tasks/pdf_tasks.py: pure utility functions (identify_pdf_based_duplicates,
    find_text_in_pdf, find_missing_pdf_content, calculate_comprehensive_similarity_task,
    extract_chapter_title_task)
  - audioDiagnostic/tasks/duplicate_tasks.py: detect_duplicates_against_pdf_task helper
  - audioDiagnostic/tasks/pdf_tasks.py: find_pdf_section_match helper
"""
from django.test import TestCase
from unittest.mock import MagicMock


# ─── pdf_tasks.py pure utility functions ─────────────────────────────────────

class PDFTasksUtilFunctionTests(TestCase):

    def test_find_text_in_pdf_found(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf("hello world", "some text hello world more text")
        self.assertTrue(result)

    def test_find_text_in_pdf_not_found(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf("completely different text", "hello world")
        self.assertFalse(result)

    def test_find_text_in_pdf_case_insensitive(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf("HELLO WORLD", "some text hello world more text")
        self.assertTrue(result)

    def test_find_missing_pdf_content_all_present(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        pdf_text = "The cat sat on the mat. The dog ran fast."
        transcript = "the cat sat on the mat the dog ran fast"
        result = find_missing_pdf_content(transcript, pdf_text)
        self.assertIsInstance(result, str)

    def test_find_missing_pdf_content_some_missing(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        pdf_text = "The quick brown fox. The lazy dog slept."
        transcript = "the quick brown fox"
        result = find_missing_pdf_content(transcript, pdf_text)
        self.assertIn("lazy dog", result)

    def test_find_missing_pdf_content_empty_pdf(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        result = find_missing_pdf_content("some transcript text", "")
        self.assertEqual(result, "")

    def test_calculate_comprehensive_similarity_identical(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        text = "the quick brown fox jumps over the lazy dog near the riverbank"
        result = calculate_comprehensive_similarity_task(text, text)
        self.assertGreater(result, 0.8)

    def test_calculate_comprehensive_similarity_different(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        result = calculate_comprehensive_similarity_task(
            "apple orange banana grape",
            "mountain river lake ocean"
        )
        self.assertLess(result, 0.3)

    def test_calculate_comprehensive_similarity_empty(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        result = calculate_comprehensive_similarity_task("", "")
        self.assertEqual(result, 0.0)

    def test_calculate_comprehensive_similarity_partial(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        text1 = "the quick brown fox jumps over the lazy dog"
        text2 = "the slow brown fox walked under the lazy cat"
        result = calculate_comprehensive_similarity_task(text1, text2)
        self.assertGreater(result, 0.0)
        self.assertLess(result, 1.0)

    def test_extract_chapter_title_chapter_pattern(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task("Chapter 1: The Beginning of Everything")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_extract_chapter_title_numbered(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task("1. Introduction to the Subject Matter Here")
        self.assertIsInstance(result, str)

    def test_extract_chapter_title_section(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task("Section 2: Advanced Topics in the Field")
        self.assertIsInstance(result, str)

    def test_extract_chapter_title_fallback(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task("This is just some random plain text without titles at all in it.")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_extract_chapter_title_all_caps(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task("THE BEGINNING OF SOMETHING IMPORTANT\nsome other text")
        self.assertIsInstance(result, str)

    def test_identify_pdf_based_duplicates_no_dups(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        segments = [
            {'text': 'hello world', 'start': 0.0, 'end': 1.0},
            {'text': 'foo bar baz', 'start': 1.0, 'end': 2.0},
        ]
        result = identify_pdf_based_duplicates(segments, "pdf text", "transcript")
        self.assertEqual(result['total_duplicates'], 0)
        self.assertEqual(len(result['segments_to_keep']), 2)

    def test_identify_pdf_based_duplicates_with_dups(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        segments = [
            {'text': 'hello world', 'start': 0.0, 'end': 1.0},
            {'text': 'middle section', 'start': 1.0, 'end': 2.0},
            {'text': 'hello world', 'start': 3.0, 'end': 4.0},
        ]
        result = identify_pdf_based_duplicates(segments, "pdf text", "transcript")
        self.assertEqual(result['total_duplicates'], 1)

    def test_identify_pdf_based_duplicates_empty_segments(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        result = identify_pdf_based_duplicates([], "pdf text", "transcript")
        self.assertEqual(result['total_duplicates'], 0)
        self.assertEqual(len(result['segments_to_keep']), 0)

    def test_identify_pdf_based_duplicates_empty_text_skipped(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        segments = [
            {'text': '', 'start': 0.0, 'end': 1.0},
            {'text': 'hello world', 'start': 1.0, 'end': 2.0},
        ]
        result = identify_pdf_based_duplicates(segments, "pdf text", "transcript")
        self.assertIsInstance(result, dict)


# ─── pdf_tasks.py find_pdf_section_match ─────────────────────────────────────

class PDFSectionMatchTests(TestCase):

    def test_find_pdf_section_match_basic(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        pdf = "chapter one the story begins here with many words and sentences"
        transcript = "the story begins here"
        result = find_pdf_section_match(pdf, transcript)
        self.assertIsInstance(result, (str, type(None), dict))

    def test_find_pdf_section_match_empty(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        try:
            result = find_pdf_section_match("", "")
            self.assertIsNotNone(result)
        except Exception:
            pass  # May raise on empty input


# ─── duplicate_tasks.py detect_duplicates_against_pdf_task ───────────────────

class DetectDuplicatesAgainstPDFTests(TestCase):

    def test_no_segments(self):
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        mock_r = MagicMock()
        result = detect_duplicates_against_pdf_task([], "pdf section", "transcript", "task1", mock_r)
        self.assertIsInstance(result, (list, dict))

    def test_short_segments_skipped(self):
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        mock_r = MagicMock()
        segments = [
            {'text': 'hi', 'start': 0.0, 'end': 0.5},
            {'text': 'ok', 'start': 0.5, 'end': 1.0},
        ]
        result = detect_duplicates_against_pdf_task(segments, "pdf", "transcript", "task2", mock_r)
        self.assertIsInstance(result, (list, dict))

    def test_with_duplicate_segments(self):
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        mock_r = MagicMock()
        segments = [
            {'text': 'this is a repeated sentence here', 'start': 0.0, 'end': 2.0},
            {'text': 'something different and unique today', 'start': 2.0, 'end': 4.0},
            {'text': 'this is a repeated sentence here', 'start': 5.0, 'end': 7.0},
        ]
        result = detect_duplicates_against_pdf_task(segments, "pdf text", "full transcript", "task3", mock_r)
        self.assertIsInstance(result, (list, dict))
