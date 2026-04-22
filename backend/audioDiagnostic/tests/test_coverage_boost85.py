"""
Wave 85 — Coverage boost
Targets pure utility classes in:
  - audioDiagnostic/tasks/transcription_utils.py
    (TimestampAligner, TranscriptionPostProcessor, MemoryManager)
"""
from django.test import TestCase


# ══════════════════════════════════════════════════════════════════
# TimestampAligner
# ══════════════════════════════════════════════════════════════════

class TimestampAlignerAlignTests(TestCase):

    def _make_seg(self, start, end, text):
        return {'start': start, 'end': end, 'text': text}

    def test_empty_returns_empty(self):
        from audioDiagnostic.tasks.transcription_utils import TimestampAligner
        result = TimestampAligner.align_timestamps([], 60.0)
        self.assertEqual(result, [])

    def test_extends_short_segment(self):
        from audioDiagnostic.tasks.transcription_utils import TimestampAligner
        # 5 words, min duration ~0.75s; current duration is 0.1s
        seg = self._make_seg(0.0, 0.1, 'hello world this is short')
        result = TimestampAligner.align_timestamps([seg], audio_duration=60.0)
        self.assertGreater(result[0]['end'] - result[0]['start'], 0.1)

    def test_no_extension_for_long_enough(self):
        from audioDiagnostic.tasks.transcription_utils import TimestampAligner
        # 2 words, min ~0.3s; already 2s
        seg = self._make_seg(0.0, 2.0, 'hello world')
        result = TimestampAligner.align_timestamps([seg], audio_duration=60.0)
        self.assertAlmostEqual(result[0]['start'], 0.0)
        self.assertAlmostEqual(result[0]['end'], 2.0)

    def test_overlap_fix(self):
        from audioDiagnostic.tasks.transcription_utils import TimestampAligner
        # seg1 ends at 5.0 but seg2 starts at 3.0 — overlap
        seg1 = self._make_seg(0.0, 5.0, 'hello world test phrase now')
        seg2 = self._make_seg(3.0, 6.0, 'next words here ok done')
        result = TimestampAligner.align_timestamps([seg1, seg2], audio_duration=60.0)
        self.assertLessEqual(result[0]['end'], result[1]['start'] + 0.01)

    def test_sentence_start_adjustment(self):
        from audioDiagnostic.tasks.transcription_utils import TimestampAligner
        # Second segment starts with capital = sentence start
        seg1 = self._make_seg(0.0, 1.0, 'hello world')
        seg2 = self._make_seg(2.0, 3.0, 'New sentence starts here now')
        result = TimestampAligner.align_timestamps([seg1, seg2], audio_duration=60.0)
        # Should not raise; start should be adjusted
        self.assertLessEqual(result[1]['start'], 2.0)

    def test_empty_text_segments_skipped(self):
        from audioDiagnostic.tasks.transcription_utils import TimestampAligner
        seg1 = self._make_seg(0.0, 1.0, '')
        seg2 = self._make_seg(1.0, 2.0, 'hello world')
        result = TimestampAligner.align_timestamps([seg1, seg2], audio_duration=60.0)
        # Only seg2 should remain (empty text skipped)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], 'hello world')

    def test_capped_at_audio_duration(self):
        from audioDiagnostic.tasks.transcription_utils import TimestampAligner
        # Very short audio; segment would extend beyond duration
        seg = self._make_seg(0.5, 0.6, 'hello world this phrase is long enough')
        result = TimestampAligner.align_timestamps([seg], audio_duration=1.0)
        self.assertLessEqual(result[0]['end'], 1.0)


class TimestampAlignerSilenceTests(TestCase):

    def test_silence_padding_removed(self):
        from audioDiagnostic.tasks.transcription_utils import TimestampAligner
        segs = [
            {'start': 0.0, 'end': 3.0, 'text': 'hello'},
            {'start': 5.0, 'end': 8.0, 'text': 'world'},
        ]
        result = TimestampAligner.remove_silence_padding(segs, padding=0.1)
        self.assertAlmostEqual(result[0]['start'], 0.1)
        self.assertAlmostEqual(result[0]['end'], 2.9)

    def test_short_segment_not_trimmed(self):
        from audioDiagnostic.tasks.transcription_utils import TimestampAligner
        # Duration (0.15) < padding*2 (0.2) → not trimmed
        segs = [{'start': 0.0, 'end': 0.15, 'text': 'hi'}]
        result = TimestampAligner.remove_silence_padding(segs, padding=0.1)
        self.assertAlmostEqual(result[0]['start'], 0.0)
        self.assertAlmostEqual(result[0]['end'], 0.15)


# ══════════════════════════════════════════════════════════════════
# TranscriptionPostProcessor
# ══════════════════════════════════════════════════════════════════

class TranscriptionPostProcessorTests(TestCase):

    def setUp(self):
        from audioDiagnostic.tasks.transcription_utils import TranscriptionPostProcessor
        self.pp = TranscriptionPostProcessor()

    def test_process_pipeline(self):
        text = 'hello hello hello world'
        result = self.pp.process(text)
        # Should remove the triple repetition
        self.assertNotIn('hello hello hello', result)

    def test_remove_triple_word_repetitions(self):
        result = self.pp.remove_repetitions('the the the cat sat')
        self.assertNotIn('the the the', result)
        self.assertIn('the', result)

    def test_remove_triple_two_word_repetitions(self):
        result = self.pp.remove_repetitions('hello world hello world hello world done')
        self.assertNotIn('hello world hello world hello world', result)

    def test_remove_triple_three_word_repetitions(self):
        result = self.pp.remove_repetitions('one two three one two three one two three end')
        # should be collapsed
        occurrences = result.count('one two three')
        self.assertLessEqual(occurrences, 1)

    def test_fix_punctuation_space_before(self):
        result = self.pp.fix_punctuation('hello , world')
        self.assertNotIn(' ,', result)

    def test_fix_multiple_marks(self):
        result = self.pp.fix_punctuation('hello!!!')
        self.assertNotIn('!!!', result)

    def test_fix_capitalization(self):
        result = self.pp.fix_capitalization('hello world. another sentence')
        self.assertTrue(result[0].isupper())

    def test_fix_capitalization_empty(self):
        result = self.pp.fix_capitalization('')
        self.assertEqual(result, '')

    def test_normalize_spacing(self):
        result = self.pp.normalize_spacing('hello   world  ')
        self.assertEqual(result, 'hello world')

    def test_mark_filler_words(self):
        result = self.pp.mark_filler_words('um I need to like go')
        self.assertIn('[um]', result)
        self.assertIn('[like]', result)

    def test_remove_filler_words(self):
        result = self.pp.remove_filler_words('Um I need to go uh there')
        self.assertNotIn('um', result.lower())
        self.assertNotIn('uh', result.lower())

    def test_normalize_spacing_no_side_effects(self):
        result = self.pp.normalize_spacing('single')
        self.assertEqual(result, 'single')


# ══════════════════════════════════════════════════════════════════
# MemoryManager
# ══════════════════════════════════════════════════════════════════

class MemoryManagerTests(TestCase):

    def test_cleanup_runs(self):
        from audioDiagnostic.tasks.transcription_utils import MemoryManager
        # Should not raise
        MemoryManager.cleanup()
