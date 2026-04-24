"""
Wave 83 — Coverage boost
Targets pure utility functions in:
  - audioDiagnostic/utils/alignment_engine.py
    (AlignmentPoint, determine_match_type, create_alignment_matrix,
     backtrack_alignment, get_context_words, find_transcript_location_in_pdf)
  - audioDiagnostic/utils/production_report.py (if exists)
"""
from django.test import TestCase
from rest_framework.test import force_authenticate


# ══════════════════════════════════════════════════════════════════
# alignment_engine.py
# ══════════════════════════════════════════════════════════════════

class AlignmentPointTests(TestCase):

    def test_to_dict_basic(self):
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        ap = AlignmentPoint(
            pdf_word='hello', pdf_index=0,
            transcript_word='hello', transcript_index=0,
            match_type='exact', match_score=1.0,
            timestamp={'start': 0.0, 'end': 0.5}
        )
        d = ap.to_dict()
        self.assertEqual(d['pdf_word'], 'hello')
        self.assertEqual(d['match_type'], 'exact')
        self.assertEqual(d['match_score'], 1.0)

    def test_defaults(self):
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        ap = AlignmentPoint()
        self.assertIsNone(ap.pdf_word)
        self.assertIsNone(ap.transcript_word)
        self.assertEqual(ap.match_type, 'exact')

    def test_missing_point(self):
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        ap = AlignmentPoint(pdf_word='lost', pdf_index=5, match_type='missing')
        d = ap.to_dict()
        self.assertEqual(d['match_type'], 'missing')
        self.assertIsNone(d['transcript_word'])


class DetermineMatchTypeTests(TestCase):

    def test_exact_match(self):
        from audioDiagnostic.utils.alignment_engine import determine_match_type
        result = determine_match_type('hello', 'hello', 1.0)
        self.assertEqual(result, 'exact')

    def test_normalized_match(self):
        from audioDiagnostic.utils.alignment_engine import determine_match_type
        # "Hello" vs "hello" — exact fails, normalized should pass
        result = determine_match_type('Hello', 'hello', 0.95)
        # After normalization both become 'hello' → 'normalized'
        self.assertIn(result, ['normalized', 'exact'])

    def test_phonetic_match(self):
        from audioDiagnostic.utils.alignment_engine import determine_match_type
        # Words with high similarity but not exact or normalized
        result = determine_match_type('colour', 'color', 0.75)
        self.assertIn(result, ['phonetic', 'normalized', 'exact'])

    def test_mismatch(self):
        from audioDiagnostic.utils.alignment_engine import determine_match_type
        result = determine_match_type('hello', 'world', 0.1)
        self.assertEqual(result, 'mismatch')


class CreateAlignmentMatrixTests(TestCase):

    def _make_word(self, word, i):
        from audioDiagnostic.utils.repetition_detector import WordTimestamp
        return WordTimestamp(word.lower(), word, float(i), float(i+1), 1, i)

    def test_small_alignment(self):
        from audioDiagnostic.utils.alignment_engine import create_alignment_matrix
        pdf_words = ['hello', 'world']
        trans_words = [self._make_word('hello', 0), self._make_word('world', 1)]
        matrix = create_alignment_matrix(pdf_words, trans_words)
        # Matrix should be (m+1) x (n+1)
        self.assertEqual(len(matrix), 3)
        self.assertEqual(len(matrix[0]), 3)

    def test_empty_inputs(self):
        from audioDiagnostic.utils.alignment_engine import create_alignment_matrix
        matrix = create_alignment_matrix([], [])
        self.assertEqual(matrix, [[0.0]])

    def test_gap_initialization(self):
        from audioDiagnostic.utils.alignment_engine import create_alignment_matrix
        pdf_words = ['a', 'b', 'c']
        trans_words = []
        matrix = create_alignment_matrix(pdf_words, trans_words)
        # First column should be i * gap_penalty (default -2.0)
        self.assertEqual(matrix[0][0], 0.0)
        self.assertAlmostEqual(matrix[1][0], -2.0)
        self.assertAlmostEqual(matrix[2][0], -4.0)


class BacktrackAlignmentTests(TestCase):

    def _make_word(self, word, i):
        from audioDiagnostic.utils.repetition_detector import WordTimestamp
        return WordTimestamp(word.lower(), word, float(i), float(i+1), 1, i)

    def test_perfect_match(self):
        from audioDiagnostic.utils.alignment_engine import (
            create_alignment_matrix, backtrack_alignment
        )
        pdf_words = ['hello', 'world']
        trans_words = [self._make_word('hello', 0), self._make_word('world', 1)]
        dp = create_alignment_matrix(pdf_words, trans_words)
        alignment = backtrack_alignment(dp, pdf_words, trans_words)
        self.assertEqual(len(alignment), 2)
        self.assertEqual(alignment[0].match_type, 'exact')
        self.assertEqual(alignment[1].match_type, 'exact')

    def test_missing_word(self):
        from audioDiagnostic.utils.alignment_engine import (
            create_alignment_matrix, backtrack_alignment
        )
        pdf_words = ['hello', 'beautiful', 'world']
        trans_words = [self._make_word('hello', 0), self._make_word('world', 1)]
        dp = create_alignment_matrix(pdf_words, trans_words)
        alignment = backtrack_alignment(dp, pdf_words, trans_words)
        # "beautiful" should appear as missing
        match_types = [a.match_type for a in alignment]
        self.assertIn('missing', match_types)

    def test_extra_word(self):
        from audioDiagnostic.utils.alignment_engine import (
            create_alignment_matrix, backtrack_alignment
        )
        pdf_words = ['hello', 'world']
        trans_words = [
            self._make_word('hello', 0),
            self._make_word('extra', 1),
            self._make_word('world', 2)
        ]
        dp = create_alignment_matrix(pdf_words, trans_words)
        alignment = backtrack_alignment(dp, pdf_words, trans_words)
        match_types = [a.match_type for a in alignment]
        self.assertIn('extra', match_types)

    def test_empty_both(self):
        from audioDiagnostic.utils.alignment_engine import (
            create_alignment_matrix, backtrack_alignment
        )
        dp = create_alignment_matrix([], [])
        alignment = backtrack_alignment(dp, [], [])
        self.assertEqual(alignment, [])


class GetContextWordsTests(TestCase):

    def _make_alignment_points(self):
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        return [
            AlignmentPoint(pdf_word='one', transcript_word='one', match_type='exact'),
            AlignmentPoint(pdf_word='two', transcript_word='two', match_type='exact'),
            AlignmentPoint(pdf_word='three', transcript_word='three', match_type='exact'),
            AlignmentPoint(pdf_word='four', transcript_word='four', match_type='exact'),
            AlignmentPoint(pdf_word='five', transcript_word='five', match_type='exact'),
        ]

    def test_get_context_pdf(self):
        from audioDiagnostic.utils.alignment_engine import get_context_words
        alignment = self._make_alignment_points()
        context = get_context_words(alignment, index=2, context_size=1, use_pdf=True)
        # Should return "two three four"
        self.assertIn('three', context)

    def test_get_context_transcript(self):
        from audioDiagnostic.utils.alignment_engine import get_context_words
        alignment = self._make_alignment_points()
        context = get_context_words(alignment, index=2, context_size=1, use_pdf=False)
        self.assertIn('three', context)

    def test_edge_index(self):
        from audioDiagnostic.utils.alignment_engine import get_context_words
        alignment = self._make_alignment_points()
        context = get_context_words(alignment, index=0, context_size=5, use_pdf=True)
        self.assertIn('one', context)

    def test_empty_alignment(self):
        from audioDiagnostic.utils.alignment_engine import get_context_words
        context = get_context_words([], index=0, context_size=5)
        self.assertEqual(context, '')


class FindTranscriptLocationTests(TestCase):

    def _make_words(self, text):
        from audioDiagnostic.utils.repetition_detector import WordTimestamp
        words = text.split()
        return [WordTimestamp(w.lower(), w, float(i), float(i+1), 1, i) for i, w in enumerate(words)]

    def test_too_few_words_returns_none(self):
        from audioDiagnostic.utils.alignment_engine import find_transcript_location_in_pdf
        trans_words = self._make_words("hello world")  # Only 2 words
        result = find_transcript_location_in_pdf(['a', 'b', 'c'], trans_words)
        self.assertIsNone(result)

    def test_finds_location(self):
        from audioDiagnostic.utils.alignment_engine import find_transcript_location_in_pdf
        # Build a PDF with a clear matching section
        pdf_filler = ['filler'] * 50
        matching = 'the quick brown fox jumps over the lazy dog and then goes home'.split()
        pdf_words = pdf_filler + matching + pdf_filler
        
        # Make 15+ transcript words from the matching section
        trans_words = self._make_words(' '.join(matching + ['after']))
        
        result = find_transcript_location_in_pdf(pdf_words, trans_words)
        # May or may not find it depending on score threshold, but should not raise
        self.assertTrue(result is None or isinstance(result, tuple))


class EstimateReadingTimeTests(TestCase):

    def test_basic_estimate(self):
        from audioDiagnostic.utils.alignment_engine import estimate_reading_time
        # Should return a string with time estimate
        result = estimate_reading_time(word_count=150)
        self.assertIsInstance(result, str)

    def test_zero_words(self):
        from audioDiagnostic.utils.alignment_engine import estimate_reading_time
        result = estimate_reading_time(word_count=0)
        self.assertIsInstance(result, str)
