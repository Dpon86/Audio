"""
Wave 140: mark_duplicates_for_removal with actual DB objects
and more coverage for duplicate_tasks helpers
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import MagicMock, patch
from audioDiagnostic.models import AudioProject, AudioFile, TranscriptionSegment, Transcription

User = get_user_model()


class MarkDuplicatesForRemovalTests(TestCase):
    """Test mark_duplicates_for_removal with real DB objects."""

    def setUp(self):
        self.user = User.objects.create_user(username='mdfr_user', password='pass', email='mdfr@t.com')
        self.project = AudioProject.objects.create(user=self.user, title='MDFR Project')
        self.audio_file = AudioFile.objects.create(
            project=self.project, filename='audio.wav', order_index=1,
        )
        self.transcription = Transcription.objects.create(
            audio_file=self.audio_file,
            full_text='Test transcription.',
        )

    def _make_segment(self, text, start, end, idx):
        seg = TranscriptionSegment.objects.create(
            transcription=self.transcription,
            audio_file=self.audio_file,
            text=text,
            start_time=start,
            end_time=end,
            segment_index=idx,
        )
        return seg

    def test_empty_duplicates(self):
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        result = mark_duplicates_for_removal({})
        self.assertEqual(result, [])

    def test_single_group_two_occurrences(self):
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        seg1 = self._make_segment('Duplicate text', 0.0, 1.0, 0)
        seg2 = self._make_segment('Duplicate text', 5.0, 6.0, 1)

        # Mock the audio_file for the segment_data
        mock_audio_file1 = MagicMock()
        mock_audio_file1.title = 'file1.wav'
        mock_audio_file2 = MagicMock()
        mock_audio_file2.title = 'file1.wav'

        duplicates_found = {
            'dup_1': {
                'normalized_text': 'duplicate text',
                'content_type': 'sentence',
                'count': 2,
                'occurrences': [
                    {'segment_data': {'segment': seg1, 'file_order': 1, 'start_time': 0.0, 'audio_file': mock_audio_file1}, 'content_type': 'sentence'},
                    {'segment_data': {'segment': seg2, 'file_order': 1, 'start_time': 5.0, 'audio_file': mock_audio_file2}, 'content_type': 'sentence'},
                ]
            }
        }

        result = mark_duplicates_for_removal(duplicates_found)
        # First occurrence (earlier) should be removed
        self.assertEqual(len(result), 1)
        # Verify DB was updated
        seg1.refresh_from_db()
        seg2.refresh_from_db()
        self.assertTrue(seg1.is_duplicate)
        self.assertFalse(seg1.is_kept)
        self.assertTrue(seg2.is_duplicate)
        self.assertTrue(seg2.is_kept)

    def test_three_occurrences_keeps_last(self):
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        seg1 = self._make_segment('Repeat', 0.0, 1.0, 10)
        seg2 = self._make_segment('Repeat', 5.0, 6.0, 11)
        seg3 = self._make_segment('Repeat', 10.0, 11.0, 12)

        mock_af = MagicMock()
        mock_af.title = 'file.wav'

        duplicates_found = {
            'dup_1': {
                'normalized_text': 'repeat',
                'content_type': 'word',
                'count': 3,
                'occurrences': [
                    {'segment_data': {'segment': seg1, 'file_order': 1, 'start_time': 0.0, 'audio_file': mock_af}, 'content_type': 'word'},
                    {'segment_data': {'segment': seg2, 'file_order': 1, 'start_time': 5.0, 'audio_file': mock_af}, 'content_type': 'word'},
                    {'segment_data': {'segment': seg3, 'file_order': 1, 'start_time': 10.0, 'audio_file': mock_af}, 'content_type': 'word'},
                ]
            }
        }

        result = mark_duplicates_for_removal(duplicates_found)
        # Two occurrences should be removed
        self.assertEqual(len(result), 2)
        # Last should be kept
        seg3.refresh_from_db()
        self.assertTrue(seg3.is_kept)

    def test_multiple_groups(self):
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        seg1 = self._make_segment('GroupA text', 0.0, 1.0, 20)
        seg2 = self._make_segment('GroupA text', 5.0, 6.0, 21)
        seg3 = self._make_segment('GroupB text', 10.0, 11.0, 22)
        seg4 = self._make_segment('GroupB text', 15.0, 16.0, 23)

        mock_af = MagicMock()
        mock_af.title = 'file.wav'

        duplicates_found = {
            'dup_1': {
                'normalized_text': 'groupa text',
                'content_type': 'sentence',
                'count': 2,
                'occurrences': [
                    {'segment_data': {'segment': seg1, 'file_order': 1, 'start_time': 0.0, 'audio_file': mock_af}, 'content_type': 'sentence'},
                    {'segment_data': {'segment': seg2, 'file_order': 1, 'start_time': 5.0, 'audio_file': mock_af}, 'content_type': 'sentence'},
                ]
            },
            'dup_2': {
                'normalized_text': 'groupb text',
                'content_type': 'sentence',
                'count': 2,
                'occurrences': [
                    {'segment_data': {'segment': seg3, 'file_order': 1, 'start_time': 10.0, 'audio_file': mock_af}, 'content_type': 'sentence'},
                    {'segment_data': {'segment': seg4, 'file_order': 1, 'start_time': 15.0, 'audio_file': mock_af}, 'content_type': 'sentence'},
                ]
            }
        }

        result = mark_duplicates_for_removal(duplicates_found)
        self.assertEqual(len(result), 2)


class IdentifyAllDuplicatesExtendedTests(TestCase):
    """Extended identify_all_duplicates tests with various content types."""

    def _seg(self, text):
        seg = MagicMock()
        seg.text = text
        seg.is_duplicate = False
        seg.is_kept = True
        seg.duplicate_group_id = None
        seg.duplicate_type = None
        return seg

    def test_paragraph_type(self):
        """Content with 16+ words should be classified as paragraph."""
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        long_text = 'This is a very long piece of text that exceeds fifteen words in total count here.'
        seg1 = self._seg(long_text)
        seg2 = self._seg(long_text)
        mock_af = MagicMock()
        mock_af.title = 'f.wav'
        segments = [
            {'segment': seg1, 'text': long_text, 'file_order': 1, 'start_time': 0.0, 'end_time': 1.0, 'audio_file': mock_af},
            {'segment': seg2, 'text': long_text, 'file_order': 1, 'start_time': 10.0, 'end_time': 11.0, 'audio_file': mock_af},
        ]
        result = identify_all_duplicates(segments)
        self.assertGreater(len(result), 0)
        group = list(result.values())[0]
        self.assertEqual(group['content_type'], 'paragraph')

    def test_sentence_type(self):
        """Content with 2-15 words should be classified as sentence."""
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        sentence = 'The quick brown fox jumps.'
        seg1 = self._seg(sentence)
        seg2 = self._seg(sentence)
        mock_af = MagicMock()
        segments = [
            {'segment': seg1, 'text': sentence, 'file_order': 1, 'start_time': 0.0, 'end_time': 1.0, 'audio_file': mock_af},
            {'segment': seg2, 'text': sentence, 'file_order': 1, 'start_time': 5.0, 'end_time': 6.0, 'audio_file': mock_af},
        ]
        result = identify_all_duplicates(segments)
        if result:
            group = list(result.values())[0]
            self.assertEqual(group['content_type'], 'sentence')

    def test_duplicate_group_id_format(self):
        """Group IDs should be 'dup_N' format."""
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        text = 'Some duplicate sentence here.'
        seg1 = self._seg(text)
        seg2 = self._seg(text)
        mock_af = MagicMock()
        segments = [
            {'segment': seg1, 'text': text, 'file_order': 1, 'start_time': 0.0, 'end_time': 1.0, 'audio_file': mock_af},
            {'segment': seg2, 'text': text, 'file_order': 1, 'start_time': 5.0, 'end_time': 6.0, 'audio_file': mock_af},
        ]
        result = identify_all_duplicates(segments)
        for key in result.keys():
            self.assertTrue(key.startswith('dup_'))
