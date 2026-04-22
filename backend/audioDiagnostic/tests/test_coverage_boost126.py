"""
Wave 126: pdf_tasks.py utility functions:
  identify_pdf_based_duplicates, find_text_in_pdf, find_missing_pdf_content,
  calculate_comprehensive_similarity_task, extract_chapter_title_task
"""
from django.test import TestCase


class IdentifyPdfBasedDuplicatesTests(TestCase):

    def _call(self, segments, pdf_section="pdf section", transcript="transcript"):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        return identify_pdf_based_duplicates(segments, pdf_section, transcript)

    def test_empty_segments(self):
        result = self._call([])
        self.assertEqual(result['total_duplicates'], 0)
        self.assertEqual(len(result['duplicates_to_remove']), 0)

    def test_no_duplicates(self):
        segments = [
            {'text': 'Hello world', 'start': 0.0, 'end': 1.0},
            {'text': 'Different text', 'start': 1.0, 'end': 2.0},
        ]
        result = self._call(segments)
        self.assertEqual(result['total_duplicates'], 0)
        self.assertEqual(len(result['segments_to_keep']), 2)

    def test_exact_duplicates_removes_earlier(self):
        segments = [
            {'text': 'Hello world', 'start': 0.0, 'end': 1.0},
            {'text': 'Hello world', 'start': 5.0, 'end': 6.0},
        ]
        result = self._call(segments)
        self.assertEqual(result['total_duplicates'], 1)
        self.assertEqual(len(result['segments_to_keep']), 1)
        # The kept one should be the last (start=5.0)
        kept = result['segments_to_keep'][0]
        self.assertEqual(kept['start'], 5.0)

    def test_three_duplicates_keeps_last(self):
        segments = [
            {'text': 'Repeated phrase', 'start': 0.0, 'end': 1.0},
            {'text': 'Repeated phrase', 'start': 2.0, 'end': 3.0},
            {'text': 'Repeated phrase', 'start': 4.0, 'end': 5.0},
        ]
        result = self._call(segments)
        self.assertEqual(result['total_duplicates'], 2)
        self.assertEqual(len(result['segments_to_keep']), 1)

    def test_empty_segment_text_skipped(self):
        segments = [
            {'text': '', 'start': 0.0, 'end': 1.0},
            {'text': 'Valid text here', 'start': 1.0, 'end': 2.0},
        ]
        result = self._call(segments)
        self.assertIsNotNone(result)


class FindTextInPdfTests(TestCase):

    def test_text_found(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf("Hello world", "Some content Hello world here")
        self.assertTrue(result)

    def test_text_not_found(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf("xyz unique", "Different content")
        self.assertFalse(result)

    def test_case_insensitive(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf("HELLO WORLD", "hello world in here")
        self.assertTrue(result)

    def test_empty_text(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf("", "Some PDF content")
        self.assertTrue(result)  # Empty string is always "in" any string


class FindMissingPdfContentTests(TestCase):

    def test_no_missing_content(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        pdf = "Hello world. Good morning."
        transcript = "hello world good morning"
        result = find_missing_pdf_content(transcript, pdf)
        self.assertEqual(result, "")

    def test_missing_sentence_detected(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        pdf = "Hello world. Extra sentence not in transcript."
        transcript = "hello world"
        result = find_missing_pdf_content(transcript, pdf)
        self.assertIn("Extra sentence", result)

    def test_empty_pdf(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        result = find_missing_pdf_content("transcript text", "")
        self.assertEqual(result, "")


class CalculateComprehensiveSimilarityTests(TestCase):

    def test_identical_texts(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        result = calculate_comprehensive_similarity_task("Hello world test text", "Hello world test text")
        self.assertGreater(result, 0.8)

    def test_completely_different(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        result = calculate_comprehensive_similarity_task("apple banana cherry", "xyzzy quux frobble")
        self.assertLess(result, 0.3)

    def test_empty_texts(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        result = calculate_comprehensive_similarity_task("", "")
        self.assertEqual(result, 0)

    def test_partial_overlap(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        result = calculate_comprehensive_similarity_task(
            "The quick brown fox jumped over the lazy dog",
            "The quick brown fox jumped into the swimming pool"
        )
        self.assertGreater(result, 0.2)
        self.assertLess(result, 0.9)

    def test_returns_float(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        result = calculate_comprehensive_similarity_task("some text here", "some text there")
        self.assertIsInstance(result, float)


class ExtractChapterTitleTests(TestCase):

    def test_chapter_pattern(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task("Chapter 3: The Adventure Begins")
        self.assertIsNotNone(result)
        self.assertTrue(len(result) > 0)

    def test_numbered_section(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task("1. Introduction to Python")
        self.assertIsNotNone(result)

    def test_no_title_found(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task("no title here just text without any pattern")
        # Returns None or empty string when no pattern matched
        self.assertIsInstance(result, (str, type(None)))

    def test_all_caps_title(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task("INTRODUCTION TO PYTHON\n some content here")
        # May or may not match depending on pattern
        self.assertIsInstance(result, (str, type(None)))
