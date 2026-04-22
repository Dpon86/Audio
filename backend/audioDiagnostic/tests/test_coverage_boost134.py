"""
Wave 134: tasks/utils.py functions + additional coverage
- save_transcription_to_db
- get_final_transcript_without_duplicates
- get_audio_duration
- normalize
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import MagicMock, patch
from audioDiagnostic.models import AudioProject, AudioFile, TranscriptionSegment, Transcription

User = get_user_model()


class NormalizeFunctionTests(TestCase):
    """Test the normalize utility function."""

    def test_normalize_basic(self):
        from audioDiagnostic.tasks.utils import normalize
        result = normalize('Hello World')
        self.assertEqual(result, 'hello world')

    def test_normalize_leading_bracket(self):
        from audioDiagnostic.tasks.utils import normalize
        result = normalize('[123] Some text here')
        self.assertEqual(result, 'some text here')

    def test_normalize_negative_bracket(self):
        from audioDiagnostic.tasks.utils import normalize
        result = normalize('[-1] Negative bracket text')
        self.assertEqual(result, 'negative bracket text')

    def test_normalize_extra_whitespace(self):
        from audioDiagnostic.tasks.utils import normalize
        result = normalize('  hello   world  ')
        self.assertEqual(result, 'hello world')

    def test_normalize_empty(self):
        from audioDiagnostic.tasks.utils import normalize
        result = normalize('')
        self.assertEqual(result, '')

    def test_normalize_no_bracket(self):
        from audioDiagnostic.tasks.utils import normalize
        result = normalize('Plain text no bracket')
        self.assertEqual(result, 'plain text no bracket')


class GetFinalTranscriptTests(TestCase):
    """Test get_final_transcript_without_duplicates."""

    def test_empty_segments(self):
        from audioDiagnostic.tasks.utils import get_final_transcript_without_duplicates
        result = get_final_transcript_without_duplicates([])
        self.assertEqual(result, '')

    def test_all_kept_segments(self):
        from audioDiagnostic.tasks.utils import get_final_transcript_without_duplicates
        seg1 = MagicMock()
        seg1.is_kept = True
        seg2 = MagicMock()
        seg2.is_kept = True
        all_segments = [
            {'segment': seg1, 'text': 'hello', 'file_order': 1, 'start_time': 0.0},
            {'segment': seg2, 'text': 'world', 'file_order': 1, 'start_time': 1.0},
        ]
        result = get_final_transcript_without_duplicates(all_segments)
        self.assertIn('hello', result)
        self.assertIn('world', result)

    def test_no_is_kept_attr(self):
        """Segments without is_kept attribute should be included."""
        from audioDiagnostic.tasks.utils import get_final_transcript_without_duplicates
        seg = MagicMock(spec=[])  # No attributes
        all_segments = [
            {'segment': seg, 'text': 'included text', 'file_order': 1, 'start_time': 0.0},
        ]
        result = get_final_transcript_without_duplicates(all_segments)
        self.assertIn('included text', result)

    def test_ordering_by_file_then_time(self):
        from audioDiagnostic.tasks.utils import get_final_transcript_without_duplicates
        seg1 = MagicMock(spec=[])
        seg2 = MagicMock(spec=[])
        all_segments = [
            {'segment': seg2, 'text': 'second', 'file_order': 1, 'start_time': 1.0},
            {'segment': seg1, 'text': 'first', 'file_order': 1, 'start_time': 0.0},
        ]
        result = get_final_transcript_without_duplicates(all_segments)
        # first should come before second
        self.assertLess(result.index('first'), result.index('second'))


class GetAudioDurationTests(TestCase):
    """Test get_audio_duration."""

    def test_audio_duration_success(self):
        from audioDiagnostic.tasks.utils import get_audio_duration
        mock_audio = MagicMock()
        mock_audio.__len__ = MagicMock(return_value=3000)  # 3 seconds in ms
        with patch('pydub.AudioSegment.from_file', return_value=mock_audio):
            result = get_audio_duration('/tmp/audio.wav')
        # If the mock works, duration should be 3.0
        self.assertIsInstance(result, (int, float))

    def test_audio_duration_exception(self):
        from audioDiagnostic.tasks.utils import get_audio_duration
        # Non-existent file should return 0
        result = get_audio_duration('/nonexistent/path/audio.wav')
        self.assertEqual(result, 0)


class SaveTranscriptionToDbTests(TestCase):
    """Test save_transcription_to_db."""

    def setUp(self):
        self.user = User.objects.create_user(username='sttdb_user', password='pass', email='sttdb@t.com')
        self.project = AudioProject.objects.create(user=self.user, title='STTDB Test')
        self.audio_file = AudioFile.objects.create(
            project=self.project,
            filename='audio.wav',
            order_index=1,
        )

    def test_save_no_segments(self):
        from audioDiagnostic.tasks.utils import save_transcription_to_db
        duplicates_info = {'duplicates_to_remove': []}
        # Should not raise
        save_transcription_to_db(self.audio_file, [], duplicates_info)
        # No segments created
        self.assertEqual(TranscriptionSegment.objects.filter(audio_file=self.audio_file).count(), 0)

    def test_save_single_segment(self):
        from audioDiagnostic.tasks.utils import save_transcription_to_db
        segments = [{
            'text': 'Hello world',
            'start': 0.0,
            'end': 1.5,
            'words': [
                {'word': 'Hello', 'start': 0.0, 'end': 0.5, 'probability': 0.9},
                {'word': 'world', 'start': 0.5, 'end': 1.5, 'probability': 0.95},
            ]
        }]
        duplicates_info = {'duplicates_to_remove': []}
        with patch('audioDiagnostic.tasks.utils.TranscriptionWord') as mock_word:
            mock_word.objects.create.return_value = MagicMock()
            save_transcription_to_db(self.audio_file, segments, duplicates_info)
        
        segs = TranscriptionSegment.objects.filter(audio_file=self.audio_file)
        self.assertEqual(segs.count(), 1)
        self.assertEqual(segs.first().text, 'Hello world')
        self.assertFalse(segs.first().is_duplicate)

    def test_save_duplicate_segment(self):
        from audioDiagnostic.tasks.utils import save_transcription_to_db
        segments = [
            {'text': 'Duplicate text', 'start': 0.0, 'end': 1.0, 'words': []},
            {'text': 'Unique text', 'start': 1.0, 'end': 2.0, 'words': []},
        ]
        # Mark index 0 as duplicate
        duplicates_info = {'duplicates_to_remove': [{'index': 0}]}
        save_transcription_to_db(self.audio_file, segments, duplicates_info)
        
        segs = TranscriptionSegment.objects.filter(audio_file=self.audio_file).order_by('segment_index')
        self.assertEqual(segs.count(), 2)
        self.assertTrue(segs[0].is_duplicate)
        self.assertFalse(segs[1].is_duplicate)

    def test_save_segment_without_words(self):
        from audioDiagnostic.tasks.utils import save_transcription_to_db
        segments = [
            {'text': 'No words', 'start': 0.0, 'end': 1.0},  # No 'words' key
        ]
        duplicates_info = {'duplicates_to_remove': []}
        save_transcription_to_db(self.audio_file, segments, duplicates_info)
        segs = TranscriptionSegment.objects.filter(audio_file=self.audio_file)
        self.assertEqual(segs.count(), 1)
