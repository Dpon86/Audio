"""
Wave 123: duplicate_tasks.py utility functions (357 miss, 66%)
identify_all_duplicates, mark_duplicates_for_removal, find_text_in_pdf
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import MagicMock

User = get_user_model()


class IdentifyAllDuplicatesTests(TestCase):

    def test_no_segments(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        result = identify_all_duplicates([])
        self.assertEqual(result, {})

    def test_no_duplicates(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        seg1 = MagicMock()
        seg1.text = "Hello world"
        seg2 = MagicMock()
        seg2.text = "Different content"
        all_segments = [
            {'text': 'Hello world', 'segment': seg1, 'file_order': 0, 'start_time': 0.0, 'end_time': 1.0, 'audio_file': MagicMock()},
            {'text': 'Different content', 'segment': seg2, 'file_order': 0, 'start_time': 2.0, 'end_time': 3.0, 'audio_file': MagicMock()},
        ]
        result = identify_all_duplicates(all_segments)
        self.assertEqual(len(result), 0)

    def test_duplicate_sentences(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        seg1 = MagicMock()
        seg2 = MagicMock()
        all_segments = [
            {'text': 'Hello world test', 'segment': seg1, 'file_order': 0, 'start_time': 0.0, 'end_time': 1.0, 'audio_file': MagicMock()},
            {'text': 'Different text', 'segment': MagicMock(), 'file_order': 0, 'start_time': 1.5, 'end_time': 2.5, 'audio_file': MagicMock()},
            {'text': 'Hello world test', 'segment': seg2, 'file_order': 0, 'start_time': 5.0, 'end_time': 6.0, 'audio_file': MagicMock()},
        ]
        result = identify_all_duplicates(all_segments)
        self.assertEqual(len(result), 1)
        # Verify the duplicate group has 2 occurrences
        group = list(result.values())[0]
        self.assertEqual(group['count'], 2)
        self.assertEqual(group['content_type'], 'sentence')  # 3 words = sentence

    def test_duplicate_words(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        all_segments = [
            {'text': 'Hello', 'segment': MagicMock(), 'file_order': 0, 'start_time': 0.0, 'end_time': 0.5, 'audio_file': MagicMock()},
            {'text': 'Hello', 'segment': MagicMock(), 'file_order': 0, 'start_time': 3.0, 'end_time': 3.5, 'audio_file': MagicMock()},
        ]
        result = identify_all_duplicates(all_segments)
        self.assertEqual(len(result), 1)
        group = list(result.values())[0]
        self.assertEqual(group['content_type'], 'word')

    def test_duplicate_paragraphs(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        long_text = ' '.join(['word'] * 20)  # 20 words = paragraph
        all_segments = [
            {'text': long_text, 'segment': MagicMock(), 'file_order': 0, 'start_time': 0.0, 'end_time': 10.0, 'audio_file': MagicMock()},
            {'text': long_text, 'segment': MagicMock(), 'file_order': 0, 'start_time': 15.0, 'end_time': 25.0, 'audio_file': MagicMock()},
        ]
        result = identify_all_duplicates(all_segments)
        self.assertEqual(len(result), 1)
        group = list(result.values())[0]
        self.assertEqual(group['content_type'], 'paragraph')

    def test_empty_text_skipped(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        all_segments = [
            {'text': '', 'segment': MagicMock(), 'file_order': 0, 'start_time': 0.0, 'end_time': 1.0, 'audio_file': MagicMock()},
            {'text': '  ', 'segment': MagicMock(), 'file_order': 0, 'start_time': 1.0, 'end_time': 2.0, 'audio_file': MagicMock()},
        ]
        result = identify_all_duplicates(all_segments)
        self.assertEqual(result, {})

    def test_case_insensitive_dedup(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        all_segments = [
            {'text': 'Hello World Test', 'segment': MagicMock(), 'file_order': 0, 'start_time': 0.0, 'end_time': 1.0, 'audio_file': MagicMock()},
            {'text': 'hello world test', 'segment': MagicMock(), 'file_order': 0, 'start_time': 5.0, 'end_time': 6.0, 'audio_file': MagicMock()},
        ]
        result = identify_all_duplicates(all_segments)
        # Normalized text should match
        self.assertEqual(len(result), 1)

    def test_multiple_duplicate_groups(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        all_segments = [
            {'text': 'Phrase one here', 'segment': MagicMock(), 'file_order': 0, 'start_time': 0.0, 'end_time': 1.0, 'audio_file': MagicMock()},
            {'text': 'Phrase two here', 'segment': MagicMock(), 'file_order': 0, 'start_time': 1.0, 'end_time': 2.0, 'audio_file': MagicMock()},
            {'text': 'Phrase one here', 'segment': MagicMock(), 'file_order': 0, 'start_time': 3.0, 'end_time': 4.0, 'audio_file': MagicMock()},
            {'text': 'Phrase two here', 'segment': MagicMock(), 'file_order': 0, 'start_time': 4.0, 'end_time': 5.0, 'audio_file': MagicMock()},
        ]
        result = identify_all_duplicates(all_segments)
        self.assertEqual(len(result), 2)


class MarkDuplicatesForRemovalTests(TestCase):

    def _make_seg(self, text, file_order, start_time):
        seg = MagicMock()
        seg.text = text
        seg.start_time = start_time
        seg.end_time = start_time + 1.0
        seg.is_duplicate = False
        seg.is_kept = False
        seg.duplicate_group_id = None
        seg.duplicate_type = None
        return seg

    def test_empty_duplicates(self):
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        result = mark_duplicates_for_removal({})
        self.assertEqual(result, [])

    def test_single_group_two_occurrences(self):
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        seg1 = self._make_seg('Hello world', 0, 0.0)
        seg2 = self._make_seg('Hello world', 0, 5.0)
        af_mock = MagicMock()
        af_mock.title = 'Test File'

        duplicates_found = {
            'dup_1': {
                'normalized_text': 'hello world',
                'content_type': 'sentence',
                'count': 2,
                'occurrences': [
                    {'segment_data': {'segment': seg1, 'file_order': 0, 'start_time': 0.0, 'audio_file': af_mock}},
                    {'segment_data': {'segment': seg2, 'file_order': 0, 'start_time': 5.0, 'audio_file': af_mock}},
                ]
            }
        }
        result = mark_duplicates_for_removal(duplicates_found)
        # First occurrence (start_time=0.0) should be removed, second (5.0) kept
        self.assertEqual(len(result), 1)
        self.assertTrue(seg2.is_kept)
        self.assertFalse(seg1.is_kept)
        self.assertTrue(seg1.is_duplicate)
        self.assertTrue(seg2.is_duplicate)

    def test_single_group_three_occurrences(self):
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        seg1 = self._make_seg('Test text here', 0, 0.0)
        seg2 = self._make_seg('Test text here', 0, 5.0)
        seg3 = self._make_seg('Test text here', 0, 10.0)
        af_mock = MagicMock()
        af_mock.title = 'Test File'

        duplicates_found = {
            'dup_1': {
                'normalized_text': 'test text here',
                'content_type': 'sentence',
                'count': 3,
                'occurrences': [
                    {'segment_data': {'segment': seg1, 'file_order': 0, 'start_time': 0.0, 'audio_file': af_mock}},
                    {'segment_data': {'segment': seg2, 'file_order': 0, 'start_time': 5.0, 'audio_file': af_mock}},
                    {'segment_data': {'segment': seg3, 'file_order': 0, 'start_time': 10.0, 'audio_file': af_mock}},
                ]
            }
        }
        result = mark_duplicates_for_removal(duplicates_found)
        # First two removed, last kept
        self.assertEqual(len(result), 2)
        self.assertTrue(seg3.is_kept)
        self.assertFalse(seg1.is_kept)
        self.assertFalse(seg2.is_kept)

    def test_multiple_groups(self):
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        seg1a = self._make_seg('First phrase', 0, 0.0)
        seg1b = self._make_seg('First phrase', 0, 3.0)
        seg2a = self._make_seg('Second phrase', 0, 1.0)
        seg2b = self._make_seg('Second phrase', 0, 4.0)
        af_mock = MagicMock()
        af_mock.title = 'Test'

        duplicates_found = {
            'dup_1': {
                'normalized_text': 'first phrase',
                'content_type': 'sentence',
                'count': 2,
                'occurrences': [
                    {'segment_data': {'segment': seg1a, 'file_order': 0, 'start_time': 0.0, 'audio_file': af_mock}},
                    {'segment_data': {'segment': seg1b, 'file_order': 0, 'start_time': 3.0, 'audio_file': af_mock}},
                ]
            },
            'dup_2': {
                'normalized_text': 'second phrase',
                'content_type': 'sentence',
                'count': 2,
                'occurrences': [
                    {'segment_data': {'segment': seg2a, 'file_order': 0, 'start_time': 1.0, 'audio_file': af_mock}},
                    {'segment_data': {'segment': seg2b, 'file_order': 0, 'start_time': 4.0, 'audio_file': af_mock}},
                ]
            }
        }
        result = mark_duplicates_for_removal(duplicates_found)
        self.assertEqual(len(result), 2)

    def test_group_id_and_type_set(self):
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        seg1 = self._make_seg('The duplicate sentence', 0, 0.0)
        seg2 = self._make_seg('The duplicate sentence', 0, 5.0)
        af_mock = MagicMock()
        af_mock.title = 'File'

        duplicates_found = {
            'dup_1': {
                'normalized_text': 'the duplicate sentence',
                'content_type': 'word',
                'count': 2,
                'occurrences': [
                    {'segment_data': {'segment': seg1, 'file_order': 0, 'start_time': 0.0, 'audio_file': af_mock}},
                    {'segment_data': {'segment': seg2, 'file_order': 0, 'start_time': 5.0, 'audio_file': af_mock}},
                ]
            }
        }
        mark_duplicates_for_removal(duplicates_found)
        self.assertEqual(seg1.duplicate_group_id, 'dup_1')
        self.assertEqual(seg1.duplicate_type, 'word')
        self.assertEqual(seg2.duplicate_group_id, 'dup_1')
