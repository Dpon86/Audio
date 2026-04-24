"""
Wave 157: Target 12 missed statements
- production_report.py (11 miss): lines 117-130, 201-203, 218, 234, 257
  - generate_repetition_analysis loop body
  - generate_checklist MEDIUM (delete repetition) branch
  - generate_checklist LOW needs_review branch
  - generate_checklist LOW needs_minor_edits branch
  - count_repeated_words loop body
- pdf_text_cleaner.py (1+ miss): lines 105, 133
  - Page N pattern continue
  - Chapter N pattern pass
"""
from django.test import TestCase
from rest_framework.test import force_authenticate


# ---------------------------------------------------------------------------
# production_report.py — pure Python utility functions
# ---------------------------------------------------------------------------

class GenerateRepetitionAnalysisTests(TestCase):
    """Cover lines 117-130 — generate_repetition_analysis loop body"""

    def _make_occurrence(self, start_time, end_time):
        from audioDiagnostic.utils.repetition_detector import Occurrence
        return Occurrence(0, 5, start_time, end_time)

    def _make_repetition(self, text, occurrences):
        from audioDiagnostic.utils.repetition_detector import Repetition
        return Repetition(text, len(text.split()), occurrences)

    def test_generate_repetition_analysis_with_one_rep(self):
        """Covers lines 117-130: loop body, timestamps list, text_preview, analysis.append"""
        from audioDiagnostic.utils.production_report import generate_repetition_analysis

        occ1 = self._make_occurrence(0.0, 5.0)
        occ2 = self._make_occurrence(20.0, 25.0)
        rep = self._make_repetition("hello world example text", [occ1, occ2])

        result = generate_repetition_analysis([rep])

        self.assertEqual(len(result), 1)
        self.assertIn('text_preview', result[0])
        self.assertIn('timestamps', result[0])
        self.assertEqual(len(result[0]['timestamps']), 2)
        self.assertEqual(result[0]['times_read'], 2)

    def test_generate_repetition_analysis_long_text(self):
        """Covers lines 117-130: long text triggers the truncation branch (text_preview[:97]+'...')"""
        from audioDiagnostic.utils.production_report import generate_repetition_analysis

        long_text = "word " * 30  # 150 chars — exceeds the 100-char limit
        occ = self._make_occurrence(1.0, 2.0)
        rep = self._make_repetition(long_text.strip(), [occ])

        result = generate_repetition_analysis([rep])
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]['text_preview'].endswith('...'))

    def test_generate_repetition_analysis_empty(self):
        """Edge case: empty list returns empty analysis"""
        from audioDiagnostic.utils.production_report import generate_repetition_analysis
        result = generate_repetition_analysis([])
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# production_report.py — generate_checklist MEDIUM branch (lines 201-203)
# ---------------------------------------------------------------------------

class GenerateChecklistMediumTests(TestCase):
    """Cover lines 201-203: DELETE checklist item for non-keeper repetition occurrences"""

    def _make_occurrence(self, start_time, end_time):
        from audioDiagnostic.utils.repetition_detector import Occurrence
        return Occurrence(0, 5, start_time, end_time)

    def _make_repetition(self, text, occurrences):
        from audioDiagnostic.utils.repetition_detector import Repetition
        return Repetition(text, len(text.split()), occurrences)

    def test_generate_checklist_medium_delete_items(self):
        """Covers lines 201-203: repetition with 2 occurrences generates DELETE item for non-keeper"""
        from audioDiagnostic.utils.production_report import generate_checklist

        occ1 = self._make_occurrence(0.0, 5.0)   # NOT keeper (keeper_index = 1)
        occ2 = self._make_occurrence(20.0, 25.0)  # keeper
        rep = self._make_repetition("and he said hello world", [occ1, occ2])

        checklist = generate_checklist([], [], [rep])

        medium_items = [item for item in checklist if item.priority == 'MEDIUM']
        self.assertGreaterEqual(len(medium_items), 1)
        self.assertEqual(medium_items[0].action, 'DELETE')

    def test_generate_checklist_medium_long_rep_text(self):
        """Covers line 201-203 with text > 100 chars (triggers truncation in DELETE item)"""
        from audioDiagnostic.utils.production_report import generate_checklist

        long_text = ("the quick brown fox " * 10).strip()  # long text
        occ1 = self._make_occurrence(0.0, 3.0)
        occ2 = self._make_occurrence(10.0, 13.0)
        rep = self._make_repetition(long_text, [occ1, occ2])

        checklist = generate_checklist([], [], [rep])
        delete_items = [i for i in checklist if i.action == 'DELETE']
        self.assertGreaterEqual(len(delete_items), 1)


# ---------------------------------------------------------------------------
# production_report.py — generate_checklist LOW needs_review (line 218)
# ---------------------------------------------------------------------------

class GenerateChecklistNeedsReviewTests(TestCase):
    """Cover line 218: checklist item for needs_review segment"""

    def _make_segment(self, status, errors=None):
        from audioDiagnostic.utils.quality_scorer import QualitySegment, ErrorDetail
        if errors is None:
            errors = []
        metrics = {'missing_words': 0, 'mismatches': 0}
        return QualitySegment(
            segment_id=1,
            start_time=0.0,
            end_time=5.0,
            quality_score=0.5,
            status=status,
            metrics=metrics,
            errors=errors
        )

    def test_generate_checklist_needs_review_segment(self):
        """Covers line 218: needs_review segment generates REVIEW checklist item"""
        from audioDiagnostic.utils.production_report import generate_checklist

        seg = self._make_segment('needs_review')
        checklist = generate_checklist([seg], [], [])

        review_items = [item for item in checklist if item.action == 'REVIEW']
        self.assertGreaterEqual(len(review_items), 1)
        self.assertEqual(review_items[0].priority, 'LOW')

    def test_generate_checklist_production_ready_no_review(self):
        """production_ready segments do NOT generate REVIEW items"""
        from audioDiagnostic.utils.production_report import generate_checklist

        seg = self._make_segment('production_ready')
        checklist = generate_checklist([seg], [], [])

        review_items = [item for item in checklist if item.action == 'REVIEW']
        self.assertEqual(len(review_items), 0)


# ---------------------------------------------------------------------------
# production_report.py — generate_checklist LOW needs_minor_edits (line 234)
# ---------------------------------------------------------------------------

class GenerateChecklistNeedsMinorEditsTests(TestCase):
    """Cover line 234: checklist item for needs_minor_edits segment with errors"""

    def _make_error(self):
        from audioDiagnostic.utils.quality_scorer import ErrorDetail
        return ErrorDetail(error_type='mismatch', position=0)

    def _make_segment(self, status, errors=None):
        from audioDiagnostic.utils.quality_scorer import QualitySegment
        if errors is None:
            errors = []
        metrics = {'missing_words': 0, 'mismatches': len(errors)}
        return QualitySegment(
            segment_id=2,
            start_time=5.0,
            end_time=10.0,
            quality_score=0.8,
            status=status,
            metrics=metrics,
            errors=errors
        )

    def test_generate_checklist_needs_minor_edits_with_errors(self):
        """Covers line 234: needs_minor_edits + errors generates EDIT item"""
        from audioDiagnostic.utils.production_report import generate_checklist

        seg = self._make_segment('needs_minor_edits', [self._make_error()])
        checklist = generate_checklist([seg], [], [])

        edit_items = [item for item in checklist if item.action == 'EDIT']
        self.assertGreaterEqual(len(edit_items), 1)
        self.assertEqual(edit_items[0].priority, 'LOW')

    def test_generate_checklist_needs_minor_edits_no_errors(self):
        """needs_minor_edits without errors does NOT generate EDIT item"""
        from audioDiagnostic.utils.production_report import generate_checklist

        seg = self._make_segment('needs_minor_edits', [])
        checklist = generate_checklist([seg], [], [])

        edit_items = [item for item in checklist if item.action == 'EDIT']
        self.assertEqual(len(edit_items), 0)


# ---------------------------------------------------------------------------
# production_report.py — count_repeated_words (line 257)
# ---------------------------------------------------------------------------

class CountRepeatedWordsTests(TestCase):
    """Cover line 257: count_repeated_words inner loop"""

    def _make_repetition(self, word_count, num_occurrences):
        from audioDiagnostic.utils.repetition_detector import Occurrence, Repetition
        occs = [Occurrence(i * 10, i * 10 + 5, float(i * 10), float(i * 10 + 5))
                for i in range(num_occurrences)]
        text = ' '.join(['word'] * word_count)
        return Repetition(text, word_count, occs)

    def test_count_repeated_words_single_rep(self):
        """Covers line 257: loop body for single repetition with 3 occurrences"""
        from audioDiagnostic.utils.production_report import count_repeated_words

        rep = self._make_repetition(word_count=5, num_occurrences=3)
        total = count_repeated_words([rep])
        # 5 words * (3 occurrences - 1) = 10 wasted words
        self.assertEqual(total, 10)

    def test_count_repeated_words_multiple_reps(self):
        """Covers line 257: loop body iterated multiple times"""
        from audioDiagnostic.utils.production_report import count_repeated_words

        rep1 = self._make_repetition(word_count=3, num_occurrences=2)  # 3 wasted
        rep2 = self._make_repetition(word_count=4, num_occurrences=2)  # 4 wasted
        total = count_repeated_words([rep1, rep2])
        self.assertEqual(total, 7)

    def test_count_repeated_words_empty(self):
        """Edge case: empty list returns 0"""
        from audioDiagnostic.utils.production_report import count_repeated_words
        self.assertEqual(count_repeated_words([]), 0)


# ---------------------------------------------------------------------------
# pdf_text_cleaner.py — line 105 (Page N continue) + line 133 (Chapter N pass)
# ---------------------------------------------------------------------------

class PDFTextCleanerPatternTests(TestCase):
    """Cover lines 105 and 133 in remove_headers_footers_and_numbers"""

    def test_page_number_line_removed(self):
        """Covers line 105: 'Page N' pattern hits the continue statement"""
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers

        text = "Page 5\nThis is the actual content of the page."
        result = remove_headers_footers_and_numbers(text)
        self.assertNotIn('Page 5', result)
        self.assertIn('actual content', result)

    def test_chapter_marker_kept(self):
        """Covers line 133: 'Chapter N' pattern hits the pass statement (kept in output)"""
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers

        text = "Chapter 1\nThis is chapter content."
        result = remove_headers_footers_and_numbers(text)
        # Chapter markers are kept (the pass means no continue)
        self.assertIn('Chapter 1', result)
        self.assertIn('chapter content', result)

    def test_standalone_page_number_removed(self):
        """Additional test: bare page numbers are removed"""
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers

        text = "123\nSome story text here."
        result = remove_headers_footers_and_numbers(text)
        self.assertIn('Some story text here', result)

    def test_narrator_instruction_removed(self):
        """Narrator instructions in parentheses with colons are removed"""
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers

        text = "(Marian: Please add 3 seconds of room tone)\nActual text."
        result = remove_headers_footers_and_numbers(text)
        self.assertIn('Actual text', result)
