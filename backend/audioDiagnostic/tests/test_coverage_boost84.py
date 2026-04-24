"""
Wave 84 — Coverage boost
Targets pure utility classes/functions in:
  - audioDiagnostic/utils/quality_scorer.py
    (ErrorDetail, QualitySegment, calculate_segment_quality,
     determine_segment_status, extract_errors, analyze_segments,
     calculate_overall_quality, determine_overall_status)
  - audioDiagnostic/utils/gap_detector.py
    (MissingSection, find_context_before_gap, find_context_after_gap,
     get_timestamp_context_for_gap)
  - audioDiagnostic/utils/production_report.py
    (ChecklistItem, ProductionReport, format_timestamp, format_timestamp_range)
"""
from django.test import TestCase
from rest_framework.test import force_authenticate


# ══════════════════════════════════════════════════════════════════
# quality_scorer.py
# ══════════════════════════════════════════════════════════════════

def _make_alignment_point(match_type='exact', pdf_word='word', transcript_word='word',
                          timestamp=None):
    from audioDiagnostic.utils.alignment_engine import AlignmentPoint
    return AlignmentPoint(
        pdf_word=pdf_word, pdf_index=0,
        transcript_word=transcript_word, transcript_index=0,
        match_type=match_type, match_score=1.0,
        timestamp=timestamp
    )


class ErrorDetailTests(TestCase):

    def test_to_dict(self):
        from audioDiagnostic.utils.quality_scorer import ErrorDetail
        e = ErrorDetail(
            error_type='mismatch', position=5,
            pdf_word='hello', transcript_word='world',
            timestamp={'start': 1.0, 'end': 2.0},
            context='some context'
        )
        d = e.to_dict()
        self.assertEqual(d['error_type'], 'mismatch')
        self.assertEqual(d['position'], 5)
        self.assertEqual(d['pdf_word'], 'hello')
        self.assertEqual(d['transcript_word'], 'world')

    def test_defaults_none(self):
        from audioDiagnostic.utils.quality_scorer import ErrorDetail
        e = ErrorDetail(error_type='missing', position=0)
        d = e.to_dict()
        self.assertIsNone(d['timestamp'])
        self.assertIsNone(d['context'])


class QualitySegmentTests(TestCase):

    def test_to_dict(self):
        from audioDiagnostic.utils.quality_scorer import QualitySegment, ErrorDetail
        err = ErrorDetail('mismatch', 0)
        seg = QualitySegment(
            segment_id=1, start_time=0.0, end_time=10.0,
            quality_score=0.9, status='needs_minor_edits',
            metrics={'total_words': 10}, errors=[err]
        )
        d = seg.to_dict()
        self.assertEqual(d['segment_id'], 1)
        self.assertEqual(d['quality_score'], 0.9)
        self.assertEqual(len(d['errors']), 1)

    def test_no_errors(self):
        from audioDiagnostic.utils.quality_scorer import QualitySegment
        seg = QualitySegment(
            segment_id=0, start_time=None, end_time=None,
            quality_score=1.0, status='production_ready',
            metrics={}, errors=[]
        )
        d = seg.to_dict()
        self.assertEqual(d['errors'], [])


class CalculateSegmentQualityTests(TestCase):

    def test_all_exact(self):
        from audioDiagnostic.utils.quality_scorer import calculate_segment_quality
        pts = [_make_alignment_point('exact') for _ in range(5)]
        self.assertAlmostEqual(calculate_segment_quality(pts), 1.0)

    def test_all_normalized(self):
        from audioDiagnostic.utils.quality_scorer import calculate_segment_quality
        pts = [_make_alignment_point('normalized') for _ in range(4)]
        self.assertAlmostEqual(calculate_segment_quality(pts), 0.95)

    def test_all_phonetic(self):
        from audioDiagnostic.utils.quality_scorer import calculate_segment_quality
        pts = [_make_alignment_point('phonetic') for _ in range(4)]
        self.assertAlmostEqual(calculate_segment_quality(pts), 0.8)

    def test_all_mismatch(self):
        from audioDiagnostic.utils.quality_scorer import calculate_segment_quality
        pts = [_make_alignment_point('mismatch') for _ in range(4)]
        self.assertAlmostEqual(calculate_segment_quality(pts), 0.0)

    def test_empty(self):
        from audioDiagnostic.utils.quality_scorer import calculate_segment_quality
        self.assertEqual(calculate_segment_quality([]), 0.0)

    def test_mixed(self):
        from audioDiagnostic.utils.quality_scorer import calculate_segment_quality
        pts = [
            _make_alignment_point('exact'),
            _make_alignment_point('mismatch'),
        ]
        score = calculate_segment_quality(pts)
        self.assertAlmostEqual(score, 0.5)


class DetermineSegmentStatusTests(TestCase):

    def test_production_ready(self):
        from audioDiagnostic.utils.quality_scorer import determine_segment_status
        result = determine_segment_status(0.97, missing_count=0, mismatch_count=0)
        self.assertEqual(result, 'production_ready')

    def test_needs_minor(self):
        from audioDiagnostic.utils.quality_scorer import determine_segment_status
        result = determine_segment_status(0.88, missing_count=0, mismatch_count=1)
        self.assertEqual(result, 'needs_minor_edits')

    def test_needs_review(self):
        from audioDiagnostic.utils.quality_scorer import determine_segment_status
        result = determine_segment_status(0.75, missing_count=0, mismatch_count=5)
        self.assertEqual(result, 'needs_review')

    def test_needs_rerecording(self):
        from audioDiagnostic.utils.quality_scorer import determine_segment_status
        result = determine_segment_status(0.5, missing_count=0, mismatch_count=20)
        self.assertEqual(result, 'needs_rerecording')

    def test_missing_content_minor(self):
        from audioDiagnostic.utils.quality_scorer import determine_segment_status
        result = determine_segment_status(0.9, missing_count=1, mismatch_count=0)
        self.assertEqual(result, 'needs_minor_edits')

    def test_missing_content_review(self):
        from audioDiagnostic.utils.quality_scorer import determine_segment_status
        result = determine_segment_status(0.75, missing_count=2, mismatch_count=0)
        self.assertEqual(result, 'needs_review')

    def test_missing_content_rerecording(self):
        from audioDiagnostic.utils.quality_scorer import determine_segment_status
        result = determine_segment_status(0.5, missing_count=10, mismatch_count=0)
        self.assertEqual(result, 'needs_rerecording')


class ExtractErrorsTests(TestCase):

    def test_extracts_mismatch(self):
        from audioDiagnostic.utils.quality_scorer import extract_errors
        segment = [
            _make_alignment_point('exact'),
            _make_alignment_point('mismatch', pdf_word='hello', transcript_word='world'),
            _make_alignment_point('exact'),
        ]
        full = segment[:]
        errors = extract_errors(segment, full, start_idx=0)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, 'mismatch')

    def test_no_errors(self):
        from audioDiagnostic.utils.quality_scorer import extract_errors
        segment = [_make_alignment_point('exact') for _ in range(3)]
        errors = extract_errors(segment, segment, start_idx=0)
        self.assertEqual(errors, [])

    def test_missing_and_extra(self):
        from audioDiagnostic.utils.quality_scorer import extract_errors
        segment = [
            _make_alignment_point('missing'),
            _make_alignment_point('extra'),
        ]
        errors = extract_errors(segment, segment, start_idx=0)
        self.assertEqual(len(errors), 2)


class AnalyzeSegmentsTests(TestCase):

    def test_small_alignment(self):
        from audioDiagnostic.utils.quality_scorer import analyze_segments
        pts = [_make_alignment_point('exact') for _ in range(10)]
        segments = analyze_segments(pts, segment_size=5)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].quality_score, 1.0)
        self.assertEqual(segments[0].status, 'production_ready')

    def test_empty_alignment(self):
        from audioDiagnostic.utils.quality_scorer import analyze_segments
        segments = analyze_segments([])
        self.assertEqual(segments, [])

    def test_with_timestamps(self):
        from audioDiagnostic.utils.quality_scorer import analyze_segments
        ts = {'start': 1.0, 'end': 2.0}
        pts = [_make_alignment_point('exact', timestamp=ts) for _ in range(5)]
        segments = analyze_segments(pts, segment_size=5)
        self.assertEqual(segments[0].start_time, 1.0)


class CalculateOverallQualityTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.utils.quality_scorer import (
            calculate_overall_quality, QualitySegment
        )
        seg1 = QualitySegment(0, None, None, 1.0, 'production_ready', {}, [])
        seg2 = QualitySegment(1, None, None, 0.5, 'needs_review', {}, [])
        result = calculate_overall_quality([seg1, seg2])
        self.assertAlmostEqual(result, 0.75)

    def test_empty(self):
        from audioDiagnostic.utils.quality_scorer import calculate_overall_quality
        self.assertEqual(calculate_overall_quality([]), 0.0)


class DetermineOverallStatusTests(TestCase):

    def test_production_ready(self):
        from audioDiagnostic.utils.quality_scorer import (
            determine_overall_status, QualitySegment
        )
        segs = [QualitySegment(0, None, None, 1.0, 'production_ready', {}, [])]
        result = determine_overall_status(0.97, 0, segs)
        self.assertEqual(result, 'PRODUCTION READY ✓')

    def test_needs_minor_editing(self):
        from audioDiagnostic.utils.quality_scorer import (
            determine_overall_status, QualitySegment
        )
        segs = [QualitySegment(0, None, None, 0.88, 'needs_minor_edits', {}, [])]
        result = determine_overall_status(0.88, 0, segs)
        self.assertEqual(result, 'NEEDS MINOR EDITING')

    def test_missing_sections_triggers_significant_work(self):
        from audioDiagnostic.utils.quality_scorer import (
            determine_overall_status, QualitySegment
        )
        segs = [QualitySegment(0, None, None, 0.98, 'production_ready', {}, [])]
        result = determine_overall_status(0.98, missing_sections_count=2, segments=segs)
        self.assertEqual(result, 'NEEDS SIGNIFICANT WORK')

    def test_rerecording_triggers_significant_work(self):
        from audioDiagnostic.utils.quality_scorer import (
            determine_overall_status, QualitySegment
        )
        segs = [QualitySegment(0, None, None, 0.4, 'needs_rerecording', {}, [])]
        result = determine_overall_status(0.4, 0, segs)
        self.assertEqual(result, 'NEEDS SIGNIFICANT WORK')


# ══════════════════════════════════════════════════════════════════
# gap_detector.py
# ══════════════════════════════════════════════════════════════════

class MissingSectionTests(TestCase):

    def test_to_dict(self):
        from audioDiagnostic.utils.gap_detector import MissingSection
        ms = MissingSection(
            pdf_start_index=10, pdf_end_index=20,
            missing_text='hello world',
            word_count=2,
            context_before='before text',
            context_after='after text',
            estimated_duration='1:00',
            timestamp_context='After 5:00'
        )
        d = ms.to_dict()
        self.assertEqual(d['pdf_start_index'], 10)
        self.assertEqual(d['missing_text'], 'hello world')
        self.assertEqual(d['timestamp_context'], 'After 5:00')

    def test_no_timestamp(self):
        from audioDiagnostic.utils.gap_detector import MissingSection
        ms = MissingSection(0, 5, 'text', 1, '', '', '0:30')
        self.assertIsNone(ms.timestamp_context)


class FindContextBeforeGapTests(TestCase):

    def _alignment(self):
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        words = ['one', 'two', 'three', 'four', 'five']
        return [
            AlignmentPoint(pdf_word=w, pdf_index=i, match_type='exact')
            for i, w in enumerate(words)
        ]

    def test_gets_words_before(self):
        from audioDiagnostic.utils.gap_detector import find_context_before_gap
        alignment = self._alignment()
        context = find_context_before_gap(alignment, gap_start_idx=3, context_words=2)
        # Should have words before index 3 (two, three)
        self.assertIn('two', context)

    def test_empty_alignment(self):
        from audioDiagnostic.utils.gap_detector import find_context_before_gap
        context = find_context_before_gap([], gap_start_idx=0)
        self.assertEqual(context, '')


class FindContextAfterGapTests(TestCase):

    def _alignment(self):
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        words = ['one', 'two', 'three', 'four', 'five']
        return [
            AlignmentPoint(pdf_word=w, pdf_index=i, match_type='exact')
            for i, w in enumerate(words)
        ]

    def test_gets_words_after(self):
        from audioDiagnostic.utils.gap_detector import find_context_after_gap
        alignment = self._alignment()
        context = find_context_after_gap(alignment, gap_end_idx=1, context_words=2)
        # Should have words after index 1 (three, four)
        self.assertIn('three', context)

    def test_end_of_alignment(self):
        from audioDiagnostic.utils.gap_detector import find_context_after_gap
        alignment = self._alignment()
        context = find_context_after_gap(alignment, gap_end_idx=4, context_words=5)
        self.assertEqual(context, '')


class GetTimestampContextForGapTests(TestCase):

    def test_both_timestamps(self):
        from audioDiagnostic.utils.gap_detector import get_timestamp_context_for_gap
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        alignment = [
            AlignmentPoint(pdf_word='a', match_type='exact', timestamp={'start': 900.0, 'end': 932.0}),
            AlignmentPoint(pdf_word=None, match_type='missing'),  # gap
            AlignmentPoint(pdf_word='b', match_type='exact', timestamp={'start': 990.0, 'end': 1005.0}),
        ]
        result = get_timestamp_context_for_gap(alignment, gap_start_idx=1, gap_end_idx=1)
        self.assertIsNotNone(result)
        self.assertIn('After', result)

    def test_no_timestamps(self):
        from audioDiagnostic.utils.gap_detector import get_timestamp_context_for_gap
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        alignment = [
            AlignmentPoint(pdf_word='a', match_type='exact'),
            AlignmentPoint(pdf_word='b', match_type='extra'),
        ]
        result = get_timestamp_context_for_gap(alignment, gap_start_idx=1, gap_end_idx=1)
        self.assertIsNone(result)


# ══════════════════════════════════════════════════════════════════
# production_report.py
# ══════════════════════════════════════════════════════════════════

class ChecklistItemTests(TestCase):

    def test_to_dict(self):
        from audioDiagnostic.utils.production_report import ChecklistItem
        item = ChecklistItem(
            priority='CRITICAL', action='RECORD',
            description='Missing section',
            timestamp='5:00', text='some text',
            context={'pdf_index': 5}
        )
        d = item.to_dict()
        self.assertEqual(d['priority'], 'CRITICAL')
        self.assertEqual(d['action'], 'RECORD')
        self.assertIsNone(d.get('nonexistent'))

    def test_defaults_none(self):
        from audioDiagnostic.utils.production_report import ChecklistItem
        item = ChecklistItem('LOW', 'REVIEW', 'Check this')
        d = item.to_dict()
        self.assertIsNone(d['timestamp'])
        self.assertIsNone(d['text'])


class FormatTimestampTests(TestCase):

    def test_under_one_hour(self):
        from audioDiagnostic.utils.production_report import format_timestamp
        result = format_timestamp(90.0)  # 1:30
        self.assertEqual(result, '1:30')

    def test_over_one_hour(self):
        from audioDiagnostic.utils.production_report import format_timestamp
        result = format_timestamp(3661.0)  # 1:01:01
        self.assertEqual(result, '1:01:01')

    def test_zero(self):
        from audioDiagnostic.utils.production_report import format_timestamp
        result = format_timestamp(0.0)
        self.assertEqual(result, '0:00')
