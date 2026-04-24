"""
Wave 124: duplicate_tasks.py detect_duplicates_against_pdf_task (pure, uses mocked Redis)
"""
from django.test import TestCase
from unittest.mock import MagicMock
from rest_framework.test import force_authenticate


def _make_seg(text, start, end, idx=None, file_id=1):
    return {
        'id': idx or id(text),
        'text': text,
        'start_time': start,
        'end_time': end,
        'segment_index': idx or 0,
        'audio_file_id': file_id,
        'audio_file_title': 'TestFile',
    }


class DetectDuplicatesAgainstPdfTests(TestCase):

    def _call(self, segments):
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        mock_r = MagicMock()
        return detect_duplicates_against_pdf_task(
            segments, "pdf section text", "full transcript text", "task-id-123", mock_r
        )

    def test_empty_segments(self):
        result = self._call([])
        self.assertEqual(result['summary']['total_segments'], 0)
        self.assertEqual(result['summary']['duplicates_count'], 0)

    def test_no_duplicates(self):
        segments = [
            _make_seg('Hello world test sentence', 0.0, 1.0, 1),
            _make_seg('Something completely different', 2.0, 3.0, 2),
            _make_seg('Another unique sentence here', 4.0, 5.0, 3),
        ]
        result = self._call(segments)
        self.assertEqual(result['summary']['total_segments'], 3)
        self.assertEqual(len(result['duplicates']), 0)
        self.assertEqual(len(result['unique_segments']), 3)

    def test_short_segments_skipped(self):
        # Segments with <3 words should be skipped for duplicate check
        segments = [
            _make_seg('Hi', 0.0, 0.5, 1),
            _make_seg('Hi', 1.0, 1.5, 2),
            _make_seg('The quick brown fox', 2.0, 3.0, 3),
        ]
        result = self._call(segments)
        # Short segments 'Hi' should not be detected as duplicates
        self.assertEqual(len(result['duplicates']), 0)

    def test_exact_duplicates_detected(self):
        # Two identical segments (>2 words)
        segments = [
            _make_seg('Hello world this is a test', 0.0, 1.0, 1),
            _make_seg('Something different here', 2.0, 3.0, 2),
            _make_seg('Hello world this is a test', 5.0, 6.0, 3),
        ]
        result = self._call(segments)
        self.assertGreater(len(result['duplicates']), 0)
        # Should have 1 duplicate group
        self.assertGreater(result['summary']['unique_duplicate_groups'], 0)

    def test_last_occurrence_kept(self):
        # Check that 'is_last_occurrence' is True for the last one
        segments = [
            _make_seg('The same text appears here', 0.0, 1.0, 1),
            _make_seg('The same text appears here', 5.0, 6.0, 2),
        ]
        result = self._call(segments)
        if result['duplicates']:
            # One of the duplicates should be marked as last occurrence
            last_occ_flags = [d['is_last_occurrence'] for d in result['duplicates']]
            self.assertIn(True, last_occ_flags)
            self.assertIn(False, last_occ_flags)

    def test_duplicate_percentage_calculated(self):
        segments = [
            _make_seg('Repeated segment one two three', 0.0, 1.0, 1),
            _make_seg('Repeated segment one two three', 2.0, 3.0, 2),
            _make_seg('Repeated segment one two three', 4.0, 5.0, 3),
        ]
        result = self._call(segments)
        self.assertGreaterEqual(result['summary']['duplicate_percentage'], 0)
        self.assertLessEqual(result['summary']['duplicate_percentage'], 100)

    def test_result_structure(self):
        segments = [_make_seg('Test segment content', 0.0, 1.0, 1)]
        result = self._call(segments)
        self.assertIn('duplicates', result)
        self.assertIn('unique_segments', result)
        self.assertIn('duplicate_groups', result)
        self.assertIn('summary', result)
        summary = result['summary']
        self.assertIn('total_segments', summary)
        self.assertIn('duplicates_count', summary)
        self.assertIn('unique_count', summary)
        self.assertIn('duplicate_percentage', summary)
        self.assertIn('total_duplicate_time', summary)
        self.assertIn('total_unique_time', summary)

    def test_multiple_duplicate_groups(self):
        segments = [
            _make_seg('First repeated phrase here', 0.0, 1.0, 1),
            _make_seg('Second repeated phrase now', 1.0, 2.0, 2),
            _make_seg('First repeated phrase here', 3.0, 4.0, 3),
            _make_seg('Second repeated phrase now', 4.0, 5.0, 4),
        ]
        result = self._call(segments)
        self.assertGreaterEqual(result['summary']['unique_duplicate_groups'], 1)

    def test_redis_progress_updated(self):
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        mock_r = MagicMock()
        segments = [
            _make_seg('Test phrase one two three', 0.0, 1.0, 1),
            _make_seg('Another test sentence here', 2.0, 3.0, 2),
        ]
        detect_duplicates_against_pdf_task(segments, "pdf", "transcript", "task-abc", mock_r)
        # Redis set should have been called
        mock_r.set.assert_called()

    def test_duplicate_info_fields(self):
        segments = [
            _make_seg('The same content over again', 0.0, 1.0, 1),
            _make_seg('The same content over again', 5.0, 6.0, 2),
        ]
        result = self._call(segments)
        if result['duplicates']:
            dup = result['duplicates'][0]
            # Check expected fields exist
            self.assertIn('is_duplicate', dup)
            self.assertIn('is_last_occurrence', dup)
            self.assertIn('occurrence_number', dup)
            self.assertIn('total_occurrences', dup)
            self.assertIn('group_id', dup)
