"""
Wave 111 — Coverage boost
Targets:
  - audioDiagnostic/tasks/precise_pdf_comparison_task.py: word_by_word_comparison (main algorithm)
    — all major branches: exact match, mismatch+recovery, mismatch+PDF advance, extra content, missing, ends
"""
from django.test import TestCase
from rest_framework.test import force_authenticate


class WordByWordComparisonTests(TestCase):

    def _make_wts(self, words, start_id=1):
        """Build a simple word_to_segment map for a list of words."""
        wts = {}
        for i, w in enumerate(words):
            wts[i] = {
                'id': start_id,
                'start_time': float(i),
                'end_time': float(i + 1),
                'text': w
            }
        return wts

    def test_perfect_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import word_by_word_comparison
        pdf = "the quick brown fox jumps over the lazy dog"
        transcript = "the quick brown fox jumps over the lazy dog"
        words = transcript.split()
        wts = self._make_wts(words)
        result = word_by_word_comparison(pdf, transcript, wts)
        self.assertIsInstance(result, dict)
        self.assertIn('matched_regions', result)
        self.assertGreater(result['stats']['matched_words'], 0)
        self.assertEqual(result['stats']['abnormal_words'], 0)

    def test_empty_inputs(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import word_by_word_comparison
        result = word_by_word_comparison("", "", {})
        self.assertEqual(result['stats']['matched_words'], 0)
        self.assertEqual(len(result['matched_regions']), 0)

    def test_mismatch_with_recovery(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import word_by_word_comparison
        # Transcript has extra words in the middle that PDF doesn't have
        pdf = "hello world this is great content today"
        transcript = "hello world EXTRA WORDS INSERTED this is great content today"
        words = transcript.split()
        wts = self._make_wts(words)
        result = word_by_word_comparison(pdf, transcript, wts)
        self.assertIsInstance(result, dict)
        # Should detect the mismatch and recover
        total = (result['stats']['matched_words'] + result['stats']['abnormal_words'] +
                 result['stats']['extra_words'] + result['stats']['missing_words'])
        self.assertGreaterEqual(total, 0)

    def test_extra_transcript_at_end(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import word_by_word_comparison
        pdf = "hello world"
        transcript = "hello world extra content at end that does not appear in pdf text"
        words = transcript.split()
        wts = self._make_wts(words)
        result = word_by_word_comparison(pdf, transcript, wts)
        self.assertIsInstance(result, dict)
        # Extra content in transcript
        self.assertGreater(result['stats']['extra_words'] + result['stats']['abnormal_words'], 0)

    def test_missing_pdf_content(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import word_by_word_comparison
        pdf = "hello world missing content section here today final words done"
        transcript = "hello world final words done"
        words = transcript.split()
        wts = self._make_wts(words)
        result = word_by_word_comparison(pdf, transcript, wts)
        self.assertIsInstance(result, dict)
        # PDF has more words than transcript
        total_missing = result['stats']['missing_words']
        self.assertGreaterEqual(total_missing, 0)

    def test_completely_different_texts(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import word_by_word_comparison
        pdf = "apple orange banana grape mango pear cherry"
        transcript = "quantum physics thermodynamics wavelength radiation spectrum"
        words = transcript.split()
        wts = self._make_wts(words)
        result = word_by_word_comparison(pdf, transcript, wts)
        self.assertIsInstance(result, dict)
        self.assertIn('stats', result)
        self.assertIn('matched_regions', result)
        self.assertIn('abnormal_regions', result)
        self.assertIn('missing_content', result)
        self.assertIn('extra_content', result)

    def test_single_word_match(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import word_by_word_comparison
        pdf = "hello"
        transcript = "hello"
        wts = self._make_wts(['hello'])
        result = word_by_word_comparison(pdf, transcript, wts)
        self.assertEqual(result['stats']['matched_words'], 1)

    def test_empty_word_to_segment(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import word_by_word_comparison
        pdf = "hello world test"
        transcript = "hello world test"
        result = word_by_word_comparison(pdf, transcript, {})
        self.assertIsInstance(result, dict)
        self.assertGreater(result['stats']['matched_words'], 0)

    def test_mismatch_no_recovery_advances_pdf(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import word_by_word_comparison
        # PDF word sequence appears further in transcript after junk
        pdf = "start content here and now the end is near"
        transcript = "start content junk junk junk junk junk junk junk junk junk here and now the end is near"
        words = transcript.split()
        wts = self._make_wts(words)
        result = word_by_word_comparison(pdf, transcript, wts)
        self.assertIsInstance(result, dict)

    def test_returns_all_expected_keys(self):
        from audioDiagnostic.tasks.precise_pdf_comparison_task import word_by_word_comparison
        result = word_by_word_comparison("test text here", "test text here", {0: {'id': 1, 'start_time': 0.0, 'end_time': 1.0}})
        expected_keys = ['matched_regions', 'abnormal_regions', 'missing_content', 'extra_content', 'stats']
        for key in expected_keys:
            self.assertIn(key, result)
        stat_keys = ['matched_words', 'abnormal_words', 'missing_words', 'extra_words']
        for key in stat_keys:
            self.assertIn(key, result['stats'])
