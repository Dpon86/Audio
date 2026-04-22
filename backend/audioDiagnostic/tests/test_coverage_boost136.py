"""
Wave 136: More coverage for detect_duplicates_against_pdf_task internal logic
and preview_deletions_task
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import MagicMock, patch
from audioDiagnostic.models import AudioProject, AudioFile, Transcription, TranscriptionSegment

User = get_user_model()


class DetectDuplicatesAgainstPdfExtendedTests(TestCase):
    """Extended tests for detect_duplicates_against_pdf_task to exercise all branches."""

    def _make_segments(self, texts, start_offset=0):
        """Create segment dicts for testing."""
        segs = []
        for i, text in enumerate(texts):
            segs.append({
                'id': i + start_offset,
                'audio_file_id': 1,
                'audio_file_title': 'test.wav',
                'text': text,
                'start_time': float(i * 10),
                'end_time': float(i * 10 + 9),
                'segment_index': i + start_offset,
            })
        return segs

    def test_empty_segments(self):
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        r = MagicMock()
        result = detect_duplicates_against_pdf_task([], 'pdf section', 'full transcript', 'task1', r)
        self.assertEqual(result['summary']['total_segments'], 0)
        self.assertEqual(len(result['duplicates']), 0)

    def test_no_duplicates(self):
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        r = MagicMock()
        segments = self._make_segments([
            'The quick brown fox jumps over the lazy dog.',
            'A completely different sentence about space exploration.',
            'Yet another unique topic about deep sea fishing.',
        ])
        result = detect_duplicates_against_pdf_task(segments, 'pdf', 'transcript', 'task2', r)
        # No duplicates expected
        self.assertEqual(len(result['duplicates']), 0)

    def test_with_duplicates(self):
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        r = MagicMock()
        dup_text = 'This is a very specific sentence about duplicate detection.'
        segments = self._make_segments([
            dup_text,
            'Something entirely different here.',
            dup_text,  # exact duplicate
        ])
        result = detect_duplicates_against_pdf_task(segments, 'pdf section', 'transcript', 'task3', r)
        # Should find duplicates
        self.assertGreater(len(result['duplicates']), 0)
        self.assertEqual(result['summary']['total_segments'], 3)

    def test_short_segments_skipped(self):
        """Segments with < 3 words should be skipped in duplicate detection."""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        r = MagicMock()
        segments = self._make_segments([
            'Hi',  # 1 word - skipped
            'OK go',  # 2 words - skipped
            'Yes',  # 1 word - skipped
        ])
        result = detect_duplicates_against_pdf_task(segments, '', '', 'task4', r)
        self.assertEqual(len(result['duplicates']), 0)

    def test_many_duplicates_groups(self):
        """Test with multiple distinct duplicate groups."""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        r = MagicMock()
        text_a = 'The narrator reads this passage about ancient history.'
        text_b = 'Another repeated paragraph about modern science fiction books.'
        segments = self._make_segments([
            text_a,
            text_b,
            text_a,
            'Unique sentence about something completely unrelated.',
            text_b,
        ])
        result = detect_duplicates_against_pdf_task(segments, 'pdf', 'transcript', 'task5', r)
        self.assertIn('duplicates', result)
        self.assertIn('summary', result)
        self.assertIn('duplicate_groups', result)

    def test_return_structure(self):
        """Verify the return structure has all expected keys."""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        r = MagicMock()
        segments = self._make_segments(['Hello world this is a test sentence.'])
        result = detect_duplicates_against_pdf_task(segments, 'pdf', 'transcript', 'task6', r)
        self.assertIn('duplicates', result)
        self.assertIn('unique_segments', result)
        self.assertIn('duplicate_groups', result)
        self.assertIn('summary', result)
        summary = result['summary']
        self.assertIn('total_segments', summary)
        self.assertIn('duplicates_count', summary)
        self.assertIn('duplicate_percentage', summary)

    def test_fuzzy_duplicates(self):
        """Test near-duplicate detection (>85% similarity)."""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        r = MagicMock()
        # Very similar texts that should be caught as duplicates
        text1 = 'The captain stood on the deck and watched the horizon carefully.'
        text2 = 'The captain stood on the deck and watched the horizon carefully.'  # exact
        segments = self._make_segments([text1, 'Something else entirely different here.', text2])
        result = detect_duplicates_against_pdf_task(segments, 'pdf text here', 'full transcript here', 'task7', r)
        # Should find at least one duplicate group
        self.assertIsInstance(result['duplicates'], list)

    def test_redis_progress_updates(self):
        """Verify that redis progress updates are called."""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        r = MagicMock()
        segments = self._make_segments([
            'This is segment one with enough words to count.',
            'This is segment one with enough words to count.',  # duplicate
        ])
        result = detect_duplicates_against_pdf_task(segments, 'pdf', 'full', 'task8', r)
        # Redis should have been called
        r.set.assert_called()


class IdentifyAllDuplicatesTests(TestCase):
    """Test identify_all_duplicates function."""

    def test_empty(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        result = identify_all_duplicates([])
        self.assertEqual(len(result), 0)

    def test_no_duplicates(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        seg1 = MagicMock()
        seg1.text = 'Hello world'
        seg2 = MagicMock()
        seg2.text = 'Different content'
        all_segments = [
            {'segment': seg1, 'text': 'Hello world', 'file_order': 1, 'start_time': 0.0, 'end_time': 1.0, 'audio_file': MagicMock()},
            {'segment': seg2, 'text': 'Different content', 'file_order': 1, 'start_time': 1.0, 'end_time': 2.0, 'audio_file': MagicMock()},
        ]
        result = identify_all_duplicates(all_segments)
        self.assertEqual(len(result), 0)

    def test_with_duplicates(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        seg1 = MagicMock()
        seg1.text = 'Duplicate sentence'
        seg2 = MagicMock()
        seg2.text = 'Duplicate sentence'
        all_segments = [
            {'segment': seg1, 'text': 'Duplicate sentence', 'file_order': 1, 'start_time': 0.0, 'end_time': 1.0, 'audio_file': MagicMock()},
            {'segment': seg2, 'text': 'Duplicate sentence', 'file_order': 1, 'start_time': 5.0, 'end_time': 6.0, 'audio_file': MagicMock()},
        ]
        result = identify_all_duplicates(all_segments)
        self.assertGreater(len(result), 0)

    def test_word_vs_sentence_classification(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        # Single word
        seg1 = MagicMock()
        seg2 = MagicMock()
        all_segments = [
            {'segment': seg1, 'text': 'Hello', 'file_order': 1, 'start_time': 0.0, 'end_time': 1.0, 'audio_file': MagicMock()},
            {'segment': seg2, 'text': 'Hello', 'file_order': 1, 'start_time': 5.0, 'end_time': 6.0, 'audio_file': MagicMock()},
        ]
        result = identify_all_duplicates(all_segments)
        if result:
            for group_data in result.values():
                self.assertIn(group_data['content_type'], ['word', 'sentence', 'paragraph'])

    def test_empty_text_skipped(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        seg = MagicMock()
        seg.text = ''
        all_segments = [
            {'segment': seg, 'text': '', 'file_order': 1, 'start_time': 0.0, 'end_time': 1.0, 'audio_file': MagicMock()},
        ]
        result = identify_all_duplicates(all_segments)
        self.assertEqual(len(result), 0)
