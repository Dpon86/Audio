"""
Wave 125: find_pdf_section_match + find_pdf_section_match_task (pure functions with mocked Redis)
"""
from django.test import TestCase
from unittest.mock import MagicMock
from rest_framework.test import force_authenticate


class FindPdfSectionMatchTests(TestCase):

    def _call(self, pdf_text, transcript):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        return find_pdf_section_match(pdf_text, transcript)

    def test_exact_match_at_start(self):
        pdf = "The quick brown fox jumped over the lazy dog. More text follows."
        transcript = "The quick brown fox jumped"
        result = self._call(pdf, transcript)
        self.assertIn("quick brown fox", result.lower())

    def test_no_match_returns_fallback(self):
        pdf = "Something entirely different content here."
        transcript = "Completely unrelated transcript text here"
        result = self._call(pdf, transcript)
        # Returns fallback (first part of PDF)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_fuzzy_match(self):
        pdf = "Chapter one begins with some interesting content about nature and animals."
        transcript = "Chapter one begins with interesting content about nature"
        result = self._call(pdf, transcript)
        self.assertIsInstance(result, str)

    def test_short_transcript(self):
        pdf = "A" * 500
        transcript = "A" * 10
        result = self._call(pdf, transcript)
        self.assertIsInstance(result, str)


class FindPdfSectionMatchTaskTests(TestCase):

    def _call(self, pdf_text, transcript, task_id="test-id"):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match_task
        mock_r = MagicMock()
        return find_pdf_section_match_task(pdf_text, transcript, task_id, mock_r)

    def test_complete_boundary_match(self):
        # PDF contains both start and end sentences from transcript
        transcript = ("The quick brown fox jumped over the lazy dog. "
                      "Hello world this is a test sentence. "
                      "Final ending phrase completes the section.")
        pdf = ("Some preamble before the content. "
               "The quick brown fox jumped over the lazy dog. "
               "Hello world this is a test sentence. "
               "Middle content that fills the pdf nicely. "
               "Final ending phrase completes the section. "
               "More content after.")
        result = self._call(pdf, transcript)
        self.assertIn('matched_section', result)
        self.assertIn('confidence', result)

    def test_start_boundary_only(self):
        # PDF contains start but not end
        transcript = ("The quick brown fox jumped over the lazy dog. "
                      "Some middle content appears in the text. "
                      "A unique ending phrase xyz abc def.")
        pdf = ("The quick brown fox jumped over the lazy dog. "
               "Some middle content appears in the text. "
               "Completely different ending here.")
        result = self._call(pdf, transcript)
        self.assertIn('matched_section', result)
        self.assertIn('match_type', result)

    def test_fallback_no_match(self):
        # PDF has nothing from transcript
        transcript = ("xyz unique phrase that matches nothing whatsoever. "
                      "Another completely different sentence here. "
                      "And yet more unique content here.")
        pdf = ("apple banana cherry date elderberry. "
               "Fruit salad recipe ingredients. "
               "Mix together and serve cold.")
        result = self._call(pdf, transcript)
        self.assertIn('matched_section', result)
        self.assertIn('match_type', result)
        self.assertIn('confidence', result)

    def test_short_transcript_fallback(self):
        # Only one sentence in transcript → too few
        transcript = "Just one sentence."
        pdf = "Some pdf content that is unrelated."
        result = self._call(pdf, transcript)
        self.assertIn('matched_section', result)

    def test_redis_called(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match_task
        mock_r = MagicMock()
        find_pdf_section_match_task("PDF content here.", "Transcript here.", "task-1", mock_r)
        mock_r.set.assert_called()

    def test_result_structure(self):
        transcript = ("First sentence of the transcript here. "
                      "Second sentence follows naturally. "
                      "Third ending completes it.")
        pdf = "Content that is completely unrelated to the transcript."
        result = self._call(pdf, transcript)
        # Should always return a dict with certain keys
        self.assertIsInstance(result, dict)
        self.assertIn('matched_section', result)
        self.assertIn('confidence', result)
        self.assertIn('match_type', result)
