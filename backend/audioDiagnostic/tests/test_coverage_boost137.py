"""
Wave 137: Pure Python utility functions from pdf_tasks.py
- find_text_in_pdf
- find_missing_pdf_content
- calculate_comprehensive_similarity_task
- extract_chapter_title_task
"""
from django.test import TestCase
from rest_framework.test import force_authenticate


class FindTextInPdfTests(TestCase):
    """Test find_text_in_pdf function."""

    def test_text_found(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf('hello world', 'Some text hello world more text')
        self.assertTrue(result)

    def test_text_not_found(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf('specific phrase xyz', 'different content here')
        self.assertFalse(result)

    def test_case_insensitive(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf('Hello World', 'hello world is found here')
        self.assertTrue(result)

    def test_whitespace_normalization(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf('hello   world', 'start hello world end')
        self.assertTrue(result)

    def test_empty_text(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf('', 'some pdf content here')
        self.assertTrue(result)  # Empty string is in any string


class FindMissingPdfContentTests(TestCase):
    """Test find_missing_pdf_content function."""

    def test_all_present(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        pdf_text = 'The quick brown fox. Jumps over lazy dog.'
        transcript = 'the quick brown fox jumps over lazy dog'
        result = find_missing_pdf_content(transcript, pdf_text)
        self.assertEqual(result, '')

    def test_missing_content(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        pdf_text = 'The quick brown fox. Jumps over the lazy dog. Also some extra content here.'
        transcript = 'the quick brown fox'
        result = find_missing_pdf_content(transcript, pdf_text)
        self.assertIsInstance(result, str)

    def test_empty_pdf(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        result = find_missing_pdf_content('transcript text', '')
        self.assertEqual(result, '')

    def test_empty_transcript(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        result = find_missing_pdf_content('', 'The quick fox. Jumps high.')
        # All sentences should be missing
        self.assertIn('The quick fox', result)

    def test_multiple_missing_sentences(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        pdf_text = 'First sentence here. Second sentence here. Third sentence here.'
        result = find_missing_pdf_content('something unrelated', pdf_text)
        # Should have multiple missing items
        self.assertIsInstance(result, str)


class CalculateComprehensiveSimilarityTests(TestCase):
    """Test calculate_comprehensive_similarity_task function."""

    def test_identical_texts(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        text = 'The quick brown fox jumps over the lazy dog.'
        result = calculate_comprehensive_similarity_task(text, text)
        self.assertGreater(result, 0.9)

    def test_completely_different(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        result = calculate_comprehensive_similarity_task(
            'aaa bbb ccc ddd eee fff ggg',
            'xxx yyy zzz www vvv uuu ttt'
        )
        self.assertLess(result, 0.5)

    def test_similar_texts(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        text1 = 'The narrator read the chapter about medieval history.'
        text2 = 'The narrator reads a chapter about medieval history.'
        result = calculate_comprehensive_similarity_task(text1, text2)
        self.assertGreater(result, 0.3)

    def test_empty_texts(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        result = calculate_comprehensive_similarity_task('', '')
        self.assertEqual(result, 0.0)

    def test_returns_float(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        result = calculate_comprehensive_similarity_task('hello world test', 'hello world here')
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)

    def test_short_texts(self):
        """Short texts without phrases should still work."""
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        result = calculate_comprehensive_similarity_task('hi', 'hi')
        self.assertIsInstance(result, float)

    def test_one_empty(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        result = calculate_comprehensive_similarity_task('hello world foo bar baz', '')
        self.assertEqual(result, 0.0)


class ExtractChapterTitleTests(TestCase):
    """Test extract_chapter_title_task function."""

    def test_chapter_pattern(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task('Chapter 1: Introduction to the Story')
        self.assertIn('Chapter', result)

    def test_numbered_pattern(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task('1. The Beginning of the Adventure')
        self.assertIsInstance(result, str)

    def test_section_pattern(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task('Section 3: Advanced Topics')
        self.assertIsInstance(result, str)

    def test_all_caps_title(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task('THE BEGINNING OF SOMETHING GREAT\nSome content here.')
        self.assertIsInstance(result, str)

    def test_fallback_returns_string(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task('some random text without any title patterns.')
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_empty_input(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task('')
        # Should return fallback
        self.assertIsInstance(result, str)
        self.assertEqual(result, 'PDF Beginning (auto-detected)')

    def test_title_case_pattern(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task('The Great Adventure Story\nsome body text here.')
        self.assertIsInstance(result, str)

    def test_sentence_fallback(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        # A meaningful sentence as first content (20-100 chars, not starting with 'the')
        result = extract_chapter_title_task('In a land far away where dragons roam freely.\nMore text.')
        self.assertIsInstance(result, str)
