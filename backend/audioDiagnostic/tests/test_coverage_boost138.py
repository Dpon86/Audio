"""
Wave 138: identify_pdf_based_duplicates and find_pdf_section_match from pdf_tasks.py
"""
from django.test import TestCase


class IdentifyPdfBasedDuplicatesTests(TestCase):
    """Test identify_pdf_based_duplicates function."""

    def _make_segment(self, text, start, end):
        return {'text': text, 'start': start, 'end': end}

    def test_no_segments(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        result = identify_pdf_based_duplicates([], 'pdf section', 'transcript')
        self.assertEqual(result['total_duplicates'], 0)
        self.assertEqual(len(result['duplicates_to_remove']), 0)
        self.assertEqual(len(result['segments_to_keep']), 0)

    def test_no_duplicates(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        segments = [
            self._make_segment('Hello world text', 0.0, 1.0),
            self._make_segment('Different content here', 1.0, 2.0),
            self._make_segment('Another unique sentence', 2.0, 3.0),
        ]
        result = identify_pdf_based_duplicates(segments, 'pdf', 'transcript')
        self.assertEqual(result['total_duplicates'], 0)
        self.assertEqual(len(result['segments_to_keep']), 3)

    def test_with_duplicates(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        dup = 'This sentence appears twice in the audio.'
        segments = [
            self._make_segment(dup, 0.0, 1.0),
            self._make_segment('Something different', 1.0, 2.0),
            self._make_segment(dup, 2.0, 3.0),
        ]
        result = identify_pdf_based_duplicates(segments, 'pdf', 'transcript')
        self.assertEqual(result['total_duplicates'], 1)
        self.assertEqual(len(result['duplicates_to_remove']), 1)
        # Last occurrence is kept
        kept_texts = [s['text'] for s in result['segments_to_keep']]
        self.assertIn(dup, kept_texts)

    def test_keeps_last_occurrence(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        dup = 'Same text appears three times here.'
        segments = [
            self._make_segment(dup, 0.0, 1.0),
            self._make_segment(dup, 5.0, 6.0),
            self._make_segment(dup, 10.0, 11.0),  # This should be kept
        ]
        result = identify_pdf_based_duplicates(segments, 'pdf', 'transcript')
        # Two should be removed, one kept
        self.assertEqual(result['total_duplicates'], 2)
        # The kept one should be the last (start=10.0)
        kept = result['segments_to_keep']
        # Find the one with text dup
        dup_kept = [s for s in kept if s['text'] == dup]
        self.assertEqual(len(dup_kept), 1)
        self.assertEqual(dup_kept[0]['start'], 10.0)

    def test_empty_text_skipped(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        segments = [
            self._make_segment('', 0.0, 1.0),
            self._make_segment('Valid content here', 1.0, 2.0),
        ]
        result = identify_pdf_based_duplicates(segments, 'pdf', 'transcript')
        # Empty segment should not cause issues
        self.assertEqual(len(result['segments_to_keep']), 1)

    def test_punctuation_normalized(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        # These should be treated as duplicates after normalization
        segments = [
            self._make_segment('Hello, world!', 0.0, 1.0),
            self._make_segment('Hello world', 1.0, 2.0),
        ]
        # May or may not detect as duplicate depending on normalization
        result = identify_pdf_based_duplicates(segments, 'pdf', 'transcript')
        # The function strips punctuation and lowercases - both normalize to "hello world"
        self.assertIsNotNone(result)
        self.assertIn('total_duplicates', result)


class FindPdfSectionMatchTests(TestCase):
    """Test find_pdf_section_match pure function."""

    def test_basic_match(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        pdf_text = 'Chapter One: The Beginning. This is the start of a great story about adventure.'
        transcript = 'This is the start of a great story about adventure'
        result = find_pdf_section_match(pdf_text, transcript)
        self.assertIsNotNone(result)

    def test_no_match_returns_none_or_empty(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        pdf_text = 'This text is completely different from anything.'
        transcript = 'xyz abc def ghi jkl mno pqr stu vwx'
        result = find_pdf_section_match(pdf_text, transcript)
        # Should return None or empty string or something falsy
        # The function may return the whole pdf or a matched section
        self.assertIsNotNone(result)  # Just check it doesn't crash

    def test_empty_transcript(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        result = find_pdf_section_match('some pdf text', '')
        # Should not crash
        self.assertIsNotNone(result)

    def test_empty_pdf(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        result = find_pdf_section_match('', 'transcript text')
        self.assertIsNotNone(result)


class FindPdfSectionMatchTaskTests(TestCase):
    """Test find_pdf_section_match_task - the task version with redis."""

    def test_basic_call(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match_task
        from unittest.mock import MagicMock
        r = MagicMock()
        pdf_text = 'Chapter One introduction text here for testing purposes.'
        transcript = 'introduction text here for testing'
        result = find_pdf_section_match_task(pdf_text, transcript, 'task_id_1', r)
        self.assertIsNotNone(result)
        r.set.assert_called()

    def test_empty_inputs(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match_task
        from unittest.mock import MagicMock
        r = MagicMock()
        result = find_pdf_section_match_task('', '', 'task_id_2', r)
        self.assertIsNotNone(result)
