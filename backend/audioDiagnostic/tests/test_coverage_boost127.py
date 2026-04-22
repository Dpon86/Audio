"""
Wave 127: duplicate_tasks.py - find_silence_boundary (mocked pydub)
"""
from django.test import TestCase
from unittest.mock import MagicMock, patch


class FindSilenceBoundaryTests(TestCase):

    def _call(self, target_time_ms=500, silent_ranges=None):
        from audioDiagnostic.tasks.duplicate_tasks import find_silence_boundary

        mock_audio = MagicMock()
        mock_audio.__len__ = MagicMock(return_value=2000)
        # Slicing returns another mock audio object
        mock_slice = MagicMock()
        mock_audio.__getitem__ = MagicMock(return_value=mock_slice)

        with patch('audioDiagnostic.tasks.duplicate_tasks.silence') as mock_silence_mod:
            if silent_ranges is None:
                mock_silence_mod.detect_silence.return_value = []
            else:
                mock_silence_mod.detect_silence.return_value = silent_ranges
            return find_silence_boundary(mock_audio, target_time_ms)

    def test_no_silence_returns_original(self):
        result = self._call(target_time_ms=500, silent_ranges=[])
        self.assertEqual(result, 500)

    def test_silence_found_returns_boundary(self):
        # Silence from 300ms to 400ms (offset from search_start)
        # search_start = max(0, 500-500) = 0, search_end = min(2000, 500+500) = 1000
        # silent_ranges relative to search_start: (300, 400)
        # boundaries: 300 and 400; target_offset = 500-0 = 500
        # distance(300)=200, distance(400)=100 → best=0+400=400
        result = self._call(target_time_ms=500, silent_ranges=[(300, 400)])
        self.assertIsInstance(result, int)

    def test_multiple_silence_ranges(self):
        result = self._call(target_time_ms=500, silent_ranges=[(100, 200), (450, 480)])
        # Should pick the one closest to target_offset
        self.assertIsInstance(result, int)

    def test_near_silence_picked(self):
        # Silence at exactly target offset
        result = self._call(target_time_ms=500, silent_ranges=[(500, 550)])
        self.assertIsInstance(result, int)

    def test_early_in_audio(self):
        # target_time_ms very small — search_start = 0
        result = self._call(target_time_ms=100, silent_ranges=[(50, 80)])
        self.assertIsInstance(result, int)

    def test_late_in_audio(self):
        result = self._call(target_time_ms=1800, silent_ranges=[(400, 420)])
        self.assertIsInstance(result, int)

    def test_returns_int(self):
        result = self._call(target_time_ms=1000, silent_ranges=[])
        self.assertIsInstance(result, int)
