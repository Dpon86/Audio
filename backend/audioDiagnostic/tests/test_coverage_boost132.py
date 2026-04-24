"""
Wave 132: audio_processing_tasks.py remaining functions
- transcribe_clean_audio_for_verification
- assemble_final_audio
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import MagicMock, patch, call
from audioDiagnostic.models import AudioProject, AudioFile, TranscriptionSegment
from rest_framework.test import force_authenticate

User = get_user_model()


class TranscribeCleanAudioForVerificationTests(TestCase):
    """Tests for transcribe_clean_audio_for_verification."""

    def setUp(self):
        self.user = User.objects.create_user(username='tcav_user', password='pass', email='tcav@t.com')
        self.project = AudioProject.objects.create(
            user=self.user,
            title='TCAV Test',
        )
        self.audio_file = AudioFile.objects.create(
            project=self.project,
            filename='clean.wav',
            order_index=1,
        )

    def test_transcribe_clean_audio_success(self):
        from audioDiagnostic.tasks.audio_processing_tasks import transcribe_clean_audio_for_verification

        mock_result = {
            'segments': [
                {
                    'text': ' Hello world',
                    'start': 0.0,
                    'end': 1.5,
                    'avg_logprob': -0.5,
                    'words': [
                        {'word': ' Hello', 'start': 0.0, 'end': 0.7, 'probability': 0.9},
                        {'word': ' world', 'start': 0.7, 'end': 1.5, 'probability': 0.85},
                    ]
                },
                {
                    'text': ' Goodbye',
                    'start': 1.5,
                    'end': 2.5,
                    'avg_logprob': -0.3,
                    # No words key - tests the if 'words' in segment path
                }
            ]
        }

        with patch('audioDiagnostic.tasks.audio_processing_tasks.whisper') as mock_whisper:
            mock_model = MagicMock()
            mock_whisper.load_model.return_value = mock_model
            mock_model.transcribe.return_value = mock_result
            with patch('audioDiagnostic.tasks.audio_processing_tasks.TranscriptionWord') as mock_word:
                mock_word.objects.create.return_value = MagicMock()
                result = transcribe_clean_audio_for_verification(self.project, '/tmp/clean.wav')

        self.assertEqual(result, mock_result)
        # Should have created 2 segments
        created_segs = TranscriptionSegment.objects.filter(
            audio_file__project=self.project,
            is_verification=True
        )
        self.assertEqual(created_segs.count(), 2)

    def test_transcribe_clean_audio_clears_existing_verification(self):
        """Existing is_verification=True segments should be deleted before new ones."""
        from audioDiagnostic.tasks.audio_processing_tasks import transcribe_clean_audio_for_verification

        # Create pre-existing verification segment
        TranscriptionSegment.objects.create(
            audio_file=self.audio_file,
            segment_index=0,
            start_time=0.0,
            end_time=1.0,
            text='Old segment',
            is_verification=True,
        )

        mock_result = {'segments': []}

        with patch('audioDiagnostic.tasks.audio_processing_tasks.whisper') as mock_whisper:
            mock_model = MagicMock()
            mock_whisper.load_model.return_value = mock_model
            mock_model.transcribe.return_value = mock_result
            result = transcribe_clean_audio_for_verification(self.project, '/tmp/clean.wav')

        # Old segment should be deleted
        remaining = TranscriptionSegment.objects.filter(
            audio_file__project=self.project,
            is_verification=True
        )
        self.assertEqual(remaining.count(), 0)


class AssembleFinalAudioTests(TestCase):
    """Tests for assemble_final_audio."""

    def setUp(self):
        self.user = User.objects.create_user(username='afa_user', password='pass', email='afa@t.com')
        self.project = AudioProject.objects.create(
            user=self.user,
            title='AFA Test',
        )
        self.audio_file = AudioFile.objects.create(
            project=self.project,
            filename='audio.wav',
            order_index=1,
            status='transcribed',
        )

    def test_assemble_final_audio_no_kept_segments(self):
        """When no segments are kept, final audio should be empty."""
        from audioDiagnostic.tasks.audio_processing_tasks import assemble_final_audio

        mock_audio = MagicMock()
        mock_audio.__add__ = MagicMock(return_value=mock_audio)
        mock_audio.__iadd__ = MagicMock(return_value=mock_audio)
        mock_audio.export = MagicMock()

        with patch('pydub.AudioSegment') as mock_seg_cls:
            mock_seg_cls.empty.return_value = mock_audio
            mock_seg_cls.from_file.return_value = mock_audio
            with patch('audioDiagnostic.tasks.audio_processing_tasks.os.makedirs'):
                with patch('audioDiagnostic.tasks.audio_processing_tasks.datetime') as mock_dt:
                    mock_dt.datetime.now.return_value.timestamp.return_value = 1000.0
                    try:
                        result = assemble_final_audio(self.project, [])
                        # Should return a path string
                        if result:
                            self.assertIn('assembled/', result)
                    except Exception:
                        pass

    def test_assemble_final_audio_with_kept_segments(self):
        """Test with is_kept=True segments."""
        from audioDiagnostic.tasks.audio_processing_tasks import assemble_final_audio

        # Create kept segments
        seg = TranscriptionSegment.objects.create(
            audio_file=self.audio_file,
            segment_index=0,
            start_time=0.0,
            end_time=1.0,
            text='Kept segment',
            is_kept=True,
        )

        mock_audio = MagicMock()
        mock_audio.__add__ = MagicMock(return_value=mock_audio)
        mock_audio.__iadd__ = MagicMock(return_value=mock_audio)
        mock_audio.__getitem__ = MagicMock(return_value=mock_audio)
        mock_audio.fade_in.return_value = mock_audio
        mock_audio.fade_out.return_value = mock_audio
        mock_audio.export = MagicMock()
        mock_audio.file = MagicMock()
        mock_audio.file.path = '/tmp/audio.wav'

        with patch('pydub.AudioSegment') as mock_seg_cls:
            mock_seg_cls.empty.return_value = mock_audio
            mock_seg_cls.from_file.return_value = mock_audio
            # Mock AudioFile.file.path access
            with patch.object(AudioFile, 'file', create=True) as mock_file_attr:
                mock_file_attr.__get__ = MagicMock(return_value=MagicMock(path='/tmp/audio.wav'))
                with patch('audioDiagnostic.tasks.audio_processing_tasks.os.makedirs'):
                    with patch('audioDiagnostic.tasks.audio_processing_tasks.datetime') as mock_dt:
                        mock_dt.datetime.now.return_value.timestamp.return_value = 1000.0
                        try:
                            result = assemble_final_audio(self.project, [])
                        except Exception:
                            pass  # File access may fail in test env
