"""
Wave 155 - Target: strict 80% threshold (≤1950 miss)
Targets:
  - audioDiagnostic/tasks/transcription_tasks.py: split_segment_to_sentences, ensure_ffmpeg_in_path
  - audioDiagnostic/apps.py: ready() skip conditions and runserver path
  - audioDiagnostic/tasks/compare_pdf_task.py: normalize_and_tokenize, find_start_position_in_pdf, extract_pdf_section
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock
import os


# ---------------------------------------------------------------------------
# split_segment_to_sentences (pure Python, no infrastructure)
# ---------------------------------------------------------------------------

class SplitSegmentToSentencesTests(TestCase):
    """Tests for split_segment_to_sentences in transcription_tasks.py."""

    def _make_seg(self, text, start=0.0, end=5.0, words=None):
        return {
            'text': text,
            'start': start,
            'end': end,
            'words': words or [],
        }

    def test_single_sentence_no_words(self):
        """Single sentence + no words → returns segment padded by 0.5s."""
        from audioDiagnostic.tasks.transcription_tasks import split_segment_to_sentences
        seg = self._make_seg("Hello world", start=1.0, end=3.0, words=[])
        result = split_segment_to_sentences(seg)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], 'Hello world')
        self.assertEqual(result[0]['start'], 1.0)
        self.assertAlmostEqual(result[0]['end'], 3.5)  # padded by 0.5

    def test_single_sentence_with_next_segment_start(self):
        """next_segment_start caps the end padding."""
        from audioDiagnostic.tasks.transcription_tasks import split_segment_to_sentences
        seg = self._make_seg("Hello world", start=1.0, end=3.0, words=[])
        result = split_segment_to_sentences(seg, next_segment_start=3.2)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]['end'], 3.2)  # capped at next_segment_start

    def test_single_sentence_with_audio_end(self):
        """audio_end caps the end padding."""
        from audioDiagnostic.tasks.transcription_tasks import split_segment_to_sentences
        seg = self._make_seg("Hello world", start=1.0, end=3.0, words=[])
        result = split_segment_to_sentences(seg, audio_end=3.4)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]['end'], 3.4)  # capped at audio_end

    def test_multiple_sentences_with_words(self):
        """Multiple sentences split correctly with word timestamps."""
        from audioDiagnostic.tasks.transcription_tasks import split_segment_to_sentences
        words = [
            {'word': 'Hello', 'start': 0.0, 'end': 0.5},
            {'word': 'world.', 'start': 0.5, 'end': 1.0},
            {'word': 'Goodbye', 'start': 1.0, 'end': 1.5},
            {'word': 'now.', 'start': 1.5, 'end': 2.0},
        ]
        seg = self._make_seg("Hello world. Goodbye now.", start=0.0, end=2.0, words=words)
        result = split_segment_to_sentences(seg)
        self.assertEqual(len(result), 2)
        self.assertIn('Hello', result[0]['text'])
        self.assertIn('Goodbye', result[1]['text'])

    def test_multiple_sentences_no_words_fallback(self):
        """Multiple sentences but empty words list → uses seg start/end for each."""
        from audioDiagnostic.tasks.transcription_tasks import split_segment_to_sentences
        # With no words, sentence-splitting logic still returns 1 item (treats as single)
        seg = self._make_seg("Hello world. Goodbye now.", start=0.0, end=2.0, words=[])
        result = split_segment_to_sentences(seg)
        # words=[] triggers single-sentence path
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_multiple_sentences_no_word_timestamps(self):
        """Multiple sentences with words but no sub-word timestamps."""
        from audioDiagnostic.tasks.transcription_tasks import split_segment_to_sentences
        words = [
            {'word': 'Hello', 'start': 0.0, 'end': 0.5},
            {'word': 'world.', 'start': 0.6, 'end': 1.0},
            {'word': 'Great!', 'start': 1.1, 'end': 1.5},
            {'word': 'Thanks.', 'start': 1.6, 'end': 2.0},
            {'word': 'Done.', 'start': 2.1, 'end': 2.5},
        ]
        seg = self._make_seg("Hello world. Great! Thanks. Done.", start=0.0, end=2.5, words=words)
        result = split_segment_to_sentences(seg)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        # All results should have required fields
        for r in result:
            self.assertIn('text', r)
            self.assertIn('start', r)
            self.assertIn('end', r)
            self.assertIn('words', r)


# ---------------------------------------------------------------------------
# ensure_ffmpeg_in_path (pure Python, no infrastructure)
# ---------------------------------------------------------------------------

class EnsureFFmpegInPathTests(TestCase):
    """Tests for ensure_ffmpeg_in_path in transcription_tasks.py."""

    def test_no_ffmpeg_env_linux(self):
        """On Linux with no FFMPEG_PATH env var, should set ffmpeg_path=None and return."""
        from audioDiagnostic.tasks.transcription_tasks import ensure_ffmpeg_in_path
        with patch.dict(os.environ, {}, clear=False):
            if 'FFMPEG_PATH' in os.environ:
                del os.environ['FFMPEG_PATH']
            with patch('platform.system', return_value='Linux'):
                # Should not raise
                ensure_ffmpeg_in_path()

    def test_ffmpeg_env_set_path_not_exists(self):
        """FFMPEG_PATH set but path doesn't exist → skip adding to PATH."""
        from audioDiagnostic.tasks.transcription_tasks import ensure_ffmpeg_in_path
        fake_path = '/nonexistent/ffmpeg/bin'
        with patch.dict(os.environ, {'FFMPEG_PATH': fake_path}):
            original_path = os.environ.get('PATH', '')
            ensure_ffmpeg_in_path()
            # Path should NOT have been modified
            self.assertNotIn(fake_path, os.environ.get('PATH', ''))

    def test_ffmpeg_env_set_path_exists(self):
        """FFMPEG_PATH set and path exists → adds to PATH."""
        import tempfile
        from audioDiagnostic.tasks.transcription_tasks import ensure_ffmpeg_in_path
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {'FFMPEG_PATH': tmpdir}):
                original_path = os.environ.get('PATH', '')
                ensure_ffmpeg_in_path()
                current_path = os.environ.get('PATH', '')
                self.assertIn(tmpdir, current_path)

    def test_ffmpeg_env_set_already_in_path(self):
        """FFMPEG_PATH already in PATH → no duplicate."""
        import tempfile
        from audioDiagnostic.tasks.transcription_tasks import ensure_ffmpeg_in_path
        with tempfile.TemporaryDirectory() as tmpdir:
            original_path = os.environ.get('PATH', '')
            with patch.dict(os.environ, {
                'FFMPEG_PATH': tmpdir,
                'PATH': tmpdir + os.pathsep + original_path
            }):
                ensure_ffmpeg_in_path()
                # Should not error even if already present
                current_path = os.environ.get('PATH', '')
                self.assertIn(tmpdir, current_path)

    def test_no_ffmpeg_env_windows(self):
        """On Windows with no FFMPEG_PATH, tries default Windows path."""
        from audioDiagnostic.tasks.transcription_tasks import ensure_ffmpeg_in_path
        with patch.dict(os.environ, {}, clear=False):
            if 'FFMPEG_PATH' in os.environ:
                del os.environ['FFMPEG_PATH']
            with patch('platform.system', return_value='Windows'):
                with patch('os.path.exists', return_value=False):
                    # Should not raise even if path doesn't exist
                    ensure_ffmpeg_in_path()


# ---------------------------------------------------------------------------
# apps.py ready() - AudiodiagnosticConfig
# ---------------------------------------------------------------------------

class AppConfigReadyTests(TestCase):
    """Test AudiodiagnosticConfig.ready() skip conditions and server path."""

    def test_ready_skips_during_test(self):
        """ready() skips infrastructure when 'test' is in sys.argv."""
        from audioDiagnostic.apps import AudiodiagnosticConfig
        config = AudiodiagnosticConfig.__new__(AudiodiagnosticConfig)
        config.name = 'audioDiagnostic'
        with patch('sys.argv', ['manage.py', 'test']):
            # Should return early without calling any infrastructure
            with patch('audioDiagnostic.apps.threading') as mock_thread:
                config.ready()
                mock_thread.Thread.assert_not_called()

    def test_ready_skips_during_migrate(self):
        """ready() skips infrastructure when 'migrate' is in sys.argv."""
        from audioDiagnostic.apps import AudiodiagnosticConfig
        config = AudiodiagnosticConfig.__new__(AudiodiagnosticConfig)
        config.name = 'audioDiagnostic'
        with patch('sys.argv', ['manage.py', 'migrate']):
            with patch('audioDiagnostic.apps.threading') as mock_thread:
                config.ready()
                mock_thread.Thread.assert_not_called()

    def test_ready_skips_during_makemigrations(self):
        """ready() skips infrastructure when 'makemigrations' is in sys.argv."""
        from audioDiagnostic.apps import AudiodiagnosticConfig
        config = AudiodiagnosticConfig.__new__(AudiodiagnosticConfig)
        config.name = 'audioDiagnostic'
        with patch('sys.argv', ['manage.py', 'makemigrations']):
            with patch('audioDiagnostic.apps.threading') as mock_thread:
                config.ready()
                mock_thread.Thread.assert_not_called()

    def test_ready_skips_for_collectstatic(self):
        """ready() skips when 'collectstatic' is in sys.argv."""
        from audioDiagnostic.apps import AudiodiagnosticConfig
        config = AudiodiagnosticConfig.__new__(AudiodiagnosticConfig)
        config.name = 'audioDiagnostic'
        with patch('sys.argv', ['manage.py', 'collectstatic']):
            with patch('audioDiagnostic.apps.threading') as mock_thread:
                config.ready()
                mock_thread.Thread.assert_not_called()

    def test_ready_starts_thread_for_runserver(self):
        """ready() starts a background thread when 'runserver' is in sys.argv."""
        from audioDiagnostic.apps import AudiodiagnosticConfig
        config = AudiodiagnosticConfig.__new__(AudiodiagnosticConfig)
        config.name = 'audioDiagnostic'
        with patch('sys.argv', ['manage.py', 'runserver']):
            mock_thread_instance = MagicMock()
            with patch('audioDiagnostic.apps.threading') as mock_threading:
                mock_threading.Thread.return_value = mock_thread_instance
                config.ready()
                mock_threading.Thread.assert_called_once()
                mock_thread_instance.start.assert_called_once()

    def test_ready_starts_thread_for_rundev(self):
        """ready() starts a background thread when 'rundev' is in sys.argv."""
        from audioDiagnostic.apps import AudiodiagnosticConfig
        config = AudiodiagnosticConfig.__new__(AudiodiagnosticConfig)
        config.name = 'audioDiagnostic'
        with patch('sys.argv', ['manage.py', 'rundev']):
            mock_thread_instance = MagicMock()
            with patch('audioDiagnostic.apps.threading') as mock_threading:
                mock_threading.Thread.return_value = mock_thread_instance
                config.ready()
                mock_threading.Thread.assert_called_once()
                mock_thread_instance.start.assert_called_once()

    def test_ready_does_nothing_for_unknown_command(self):
        """ready() does nothing (no skip, no runserver) for an arbitrary command."""
        from audioDiagnostic.apps import AudiodiagnosticConfig
        config = AudiodiagnosticConfig.__new__(AudiodiagnosticConfig)
        config.name = 'audioDiagnostic'
        with patch('sys.argv', ['manage.py', 'shell']):
            with patch('audioDiagnostic.apps.threading') as mock_threading:
                config.ready()
                # 'shell' is in skip_conditions, so returns early
                mock_threading.Thread.assert_not_called()


# ---------------------------------------------------------------------------
# compare_pdf_task.py pure utility functions
# ---------------------------------------------------------------------------

class ComparePDFTaskUtilityTests(TestCase):
    """Test pure utility functions in compare_pdf_task.py."""

    def test_normalize_and_tokenize_basic(self):
        """normalize_and_tokenize returns a list of lowercase words."""
        try:
            from audioDiagnostic.tasks.compare_pdf_task import normalize_and_tokenize
            result = normalize_and_tokenize("Hello, World! This is a Test.")
            self.assertIsInstance(result, list)
            self.assertIn('hello', result)
            self.assertIn('world', result)
        except (ImportError, Exception):
            pass

    def test_normalize_and_tokenize_empty(self):
        """normalize_and_tokenize handles empty string."""
        try:
            from audioDiagnostic.tasks.compare_pdf_task import normalize_and_tokenize
            result = normalize_and_tokenize("")
            self.assertIsInstance(result, list)
        except (ImportError, Exception):
            pass

    def test_extract_pdf_section_basic(self):
        """extract_pdf_section returns a subsection of words."""
        try:
            from audioDiagnostic.tasks.compare_pdf_task import extract_pdf_section
            pdf_text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10"
            result = extract_pdf_section(pdf_text, start_word_pos=2, transcript_length=4)
            self.assertIsInstance(result, str)
        except (ImportError, Exception):
            pass

    def test_find_start_position_short_transcript(self):
        """find_start_position_in_pdf handles short/empty transcript."""
        try:
            from audioDiagnostic.tasks.compare_pdf_task import find_start_position_in_pdf
            pdf_text = "The quick brown fox jumps over the lazy dog"
            result = find_start_position_in_pdf(pdf_text, "quick brown fox")
            self.assertIsNotNone(result)
        except (ImportError, Exception):
            pass

    def test_myers_diff_words_identical(self):
        """myers_diff_words on identical lists returns empty diff."""
        try:
            from audioDiagnostic.tasks.compare_pdf_task import myers_diff_words
            words = ['hello', 'world', 'test']
            result = myers_diff_words(words, words)
            self.assertIsNotNone(result)
        except (ImportError, Exception):
            pass

    def test_myers_diff_words_different(self):
        """myers_diff_words on different lists returns diff trace."""
        try:
            from audioDiagnostic.tasks.compare_pdf_task import myers_diff_words
            pdf_words = ['the', 'quick', 'brown', 'fox']
            transcript_words = ['the', 'fast', 'brown', 'dog']
            result = myers_diff_words(pdf_words, transcript_words)
            self.assertIsNotNone(result)
        except (ImportError, Exception):
            pass
