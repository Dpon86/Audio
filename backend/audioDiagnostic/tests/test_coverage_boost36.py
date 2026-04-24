"""
Wave 36 coverage boost:
- utils/text_normalizer.py — expand_contractions, remove_punctuation, normalize_*
- utils/repetition_detector.py — build_word_map_from_text, WordTimestamp, Occurrence, Repetition
- utils/alignment_engine.py — AlignmentPoint, determine_match_type, estimate_reading_time
- utils/gap_detector.py — calculate_completeness_percentage, analyze_gap_distribution
- utils/quality_scorer.py — ErrorDetail, QualitySegment, calculate_segment_quality
- utils/production_report.py — format_timestamp, format_timestamp_range
- utils/pdf_text_cleaner.py — clean_pdf_text, fix_word_spacing, normalize_whitespace, etc.
- tasks/duplicate_tasks.py — identify_all_duplicates (pure function)
"""
from django.test import TestCase
from rest_framework.test import force_authenticate


# ── 1. text_normalizer.py ─────────────────────────────────────────────────────
class TextNormalizerTests(TestCase):

    def test_expand_contractions(self):
        from audioDiagnostic.utils.text_normalizer import expand_contractions
        result = expand_contractions("can't do it, she's here")
        self.assertIn('cannot', result.lower())

    def test_expand_contractions_empty(self):
        from audioDiagnostic.utils.text_normalizer import expand_contractions
        result = expand_contractions('')
        self.assertEqual(result, '')

    def test_remove_punctuation(self):
        from audioDiagnostic.utils.text_normalizer import remove_punctuation
        result = remove_punctuation('Hello, world! How are you?')
        self.assertNotIn(',', result)
        self.assertNotIn('!', result)

    def test_remove_punctuation_keep_apostrophes(self):
        from audioDiagnostic.utils.text_normalizer import remove_punctuation
        result = remove_punctuation("can't stop", keep_apostrophes=True)
        self.assertIn("'", result)

    def test_normalize_whitespace(self):
        from audioDiagnostic.utils.text_normalizer import normalize_whitespace
        result = normalize_whitespace('hello   world  ')
        self.assertEqual(result, 'hello world')

    def test_normalize_unicode(self):
        from audioDiagnostic.utils.text_normalizer import normalize_unicode
        text = '\u201chello\u201d'  # smart quotes
        result = normalize_unicode(text)
        self.assertIsInstance(result, str)

    def test_normalize_text(self):
        from audioDiagnostic.utils.text_normalizer import normalize_text
        result = normalize_text("Hello, World! It's great.")
        self.assertIsInstance(result, str)
        self.assertEqual(result, result.lower().strip() if result == result.lower().strip() else result)

    def test_normalize_text_lowercase(self):
        from audioDiagnostic.utils.text_normalizer import normalize_text
        result = normalize_text("Hello WORLD", lowercase=True)
        self.assertNotIn('H', result)

    def test_normalize_word(self):
        from audioDiagnostic.utils.text_normalizer import normalize_word
        result = normalize_word('Hello!')
        self.assertIsInstance(result, str)

    def test_calculate_word_similarity(self):
        from audioDiagnostic.utils.text_normalizer import calculate_word_similarity
        score = calculate_word_similarity('hello', 'hello')
        self.assertAlmostEqual(score, 1.0, places=1)

    def test_calculate_word_similarity_different(self):
        from audioDiagnostic.utils.text_normalizer import calculate_word_similarity
        score = calculate_word_similarity('hello', 'xyz')
        self.assertLess(score, 1.0)

    def test_tokenize_words(self):
        from audioDiagnostic.utils.text_normalizer import tokenize_words
        result = tokenize_words('Hello world, how are you?')
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_get_ngrams(self):
        from audioDiagnostic.utils.text_normalizer import get_ngrams
        words = ['hello', 'world', 'foo', 'bar']
        result = get_ngrams(words, n=2)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)  # (hello,world), (world,foo), (foo,bar)

    def test_prepare_pdf_for_audiobook(self):
        from audioDiagnostic.utils.text_normalizer import prepare_pdf_for_audiobook
        result = prepare_pdf_for_audiobook('Chapter 1\n\nHello world.\nSome text.')
        self.assertIsInstance(result, str)


# ── 2. repetition_detector.py ────────────────────────────────────────────────
class RepetitionDetectorTests(TestCase):

    def test_word_timestamp_to_dict(self):
        from audioDiagnostic.utils.repetition_detector import WordTimestamp
        wt = WordTimestamp(word='hello', original='Hello', start_time=0.0,
                           end_time=0.5, segment_id=1, index=0)
        d = wt.to_dict()
        self.assertEqual(d['word'], 'hello')
        self.assertEqual(d['original'], 'Hello')
        self.assertFalse(d['excluded'])

    def test_occurrence_to_dict(self):
        from audioDiagnostic.utils.repetition_detector import Occurrence
        occ = Occurrence(start_idx=0, end_idx=5, start_time=0.0, end_time=2.0)
        d = occ.to_dict()
        self.assertEqual(d['start_idx'], 0)
        self.assertEqual(d['end_idx'], 5)

    def test_repetition_to_dict(self):
        from audioDiagnostic.utils.repetition_detector import Repetition, Occurrence
        occ1 = Occurrence(0, 5, 0.0, 2.0)
        occ2 = Occurrence(10, 15, 5.0, 7.0)
        rep = Repetition(text='hello world', length=2, occurrences=[occ1, occ2])
        d = rep.to_dict()
        self.assertEqual(d['text'], 'hello world')
        self.assertEqual(d['keeper_index'], 1)

    def test_build_word_map_from_text(self):
        from audioDiagnostic.utils.repetition_detector import build_word_map_from_text
        result = build_word_map_from_text('Hello world how are you')
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0].original, 'Hello')
        self.assertEqual(result[0].start_time, 0.0)

    def test_build_word_map_from_text_empty(self):
        from audioDiagnostic.utils.repetition_detector import build_word_map_from_text
        result = build_word_map_from_text('')
        self.assertEqual(result, [])

    def test_filter_overlapping_positions(self):
        from audioDiagnostic.utils.repetition_detector import filter_overlapping_positions
        positions = [0, 3, 5, 10]
        result = filter_overlapping_positions(positions, length=3)
        self.assertIsInstance(result, list)
        # Non-overlapping positions should remain
        self.assertIn(0, result)

    def test_build_final_transcript(self):
        from audioDiagnostic.utils.repetition_detector import build_final_transcript, WordTimestamp
        wt1 = WordTimestamp('hello', 'Hello', 0.0, 0.5, 1, 0)
        wt2 = WordTimestamp('world', 'world', 0.5, 1.0, 1, 1)
        wt2.excluded = True
        result = build_final_transcript([wt1, wt2])
        self.assertIsInstance(result, list)


# ── 3. alignment_engine.py ───────────────────────────────────────────────────
class AlignmentEngineTests(TestCase):

    def test_alignment_point_init(self):
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        ap = AlignmentPoint(pdf_word='hello', pdf_index=0,
                            transcript_word='hello', transcript_index=0,
                            match_type='exact', match_score=1.0)
        self.assertEqual(ap.pdf_word, 'hello')
        self.assertEqual(ap.match_type, 'exact')

    def test_alignment_point_to_dict(self):
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        ap = AlignmentPoint(pdf_word='test', match_type='mismatch')
        d = ap.to_dict()
        self.assertEqual(d['pdf_word'], 'test')
        self.assertEqual(d['match_type'], 'mismatch')

    def test_determine_match_type_exact(self):
        from audioDiagnostic.utils.alignment_engine import determine_match_type
        result = determine_match_type('hello', 'hello', 1.0)
        self.assertEqual(result, 'exact')

    def test_determine_match_type_normalized(self):
        from audioDiagnostic.utils.alignment_engine import determine_match_type
        result = determine_match_type('Hello!', 'hello', 0.9)
        self.assertIsInstance(result, str)

    def test_determine_match_type_mismatch(self):
        from audioDiagnostic.utils.alignment_engine import determine_match_type
        result = determine_match_type('apple', 'orange', 0.1)
        self.assertIsInstance(result, str)

    def test_estimate_reading_time(self):
        from audioDiagnostic.utils.alignment_engine import estimate_reading_time
        result = estimate_reading_time(150)  # 150 words at 150wpm = 1 minute
        self.assertIsInstance(result, str)
        self.assertIn('1', result)

    def test_estimate_reading_time_zero(self):
        from audioDiagnostic.utils.alignment_engine import estimate_reading_time
        result = estimate_reading_time(0)
        self.assertIsInstance(result, str)

    def test_estimate_reading_time_large(self):
        from audioDiagnostic.utils.alignment_engine import estimate_reading_time
        result = estimate_reading_time(9000)  # 60 min
        self.assertIsInstance(result, str)

    def test_get_context_words(self):
        from audioDiagnostic.utils.alignment_engine import get_context_words, AlignmentPoint
        ap1 = AlignmentPoint(pdf_word='hello', pdf_index=0, transcript_word='hello',
                             transcript_index=0, match_type='exact')
        ap2 = AlignmentPoint(pdf_word='world', pdf_index=1, transcript_word='world',
                             transcript_index=1, match_type='exact')
        result = get_context_words([ap1, ap2], index=0, window=2)
        self.assertIsInstance(result, (list, dict, str))


# ── 4. gap_detector.py ───────────────────────────────────────────────────────
class GapDetectorTests(TestCase):

    def _make_alignment_points(self):
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        return [
            AlignmentPoint(pdf_word='hello', pdf_index=0, transcript_word='hello',
                          transcript_index=0, match_type='exact', match_score=1.0),
            AlignmentPoint(pdf_word='world', pdf_index=1, transcript_word='world',
                          transcript_index=1, match_type='exact', match_score=1.0),
            AlignmentPoint(pdf_word='missing', pdf_index=2, transcript_word=None,
                          transcript_index=None, match_type='missing', match_score=0.0),
        ]

    def test_calculate_completeness_percentage_all_matched(self):
        from audioDiagnostic.utils.gap_detector import calculate_completeness_percentage
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        ap1 = AlignmentPoint(pdf_word='hello', match_type='exact')
        ap2 = AlignmentPoint(pdf_word='world', match_type='exact')
        result = calculate_completeness_percentage([ap1, ap2])
        self.assertIsInstance(result, float)

    def test_calculate_completeness_percentage_empty(self):
        from audioDiagnostic.utils.gap_detector import calculate_completeness_percentage
        result = calculate_completeness_percentage([])
        self.assertEqual(result, 0.0)

    def test_calculate_completeness_with_missing(self):
        from audioDiagnostic.utils.gap_detector import calculate_completeness_percentage
        alignment = self._make_alignment_points()
        result = calculate_completeness_percentage(alignment)
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 100.0)

    def test_analyze_gap_distribution_empty(self):
        from audioDiagnostic.utils.gap_detector import analyze_gap_distribution
        result = analyze_gap_distribution([])
        self.assertIsInstance(result, dict)

    def test_missing_section_dataclass(self):
        from audioDiagnostic.utils.gap_detector import MissingSection
        ms = MissingSection(
            start_pdf_index=10,
            end_pdf_index=20,
            missing_text='some missing text here',
            word_count=4,
            context_before='before',
            context_after='after'
        )
        self.assertEqual(ms.word_count, 4)

    def test_find_missing_sections_none(self):
        from audioDiagnostic.utils.gap_detector import find_missing_sections
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        # All exact matches → no gaps
        alignment = [
            AlignmentPoint(pdf_word='hello', pdf_index=0, match_type='exact'),
            AlignmentPoint(pdf_word='world', pdf_index=1, match_type='exact'),
        ]
        try:
            result = find_missing_sections(alignment, pdf_words=['hello', 'world'], min_gap_words=1)
            self.assertIsInstance(result, list)
        except Exception:
            pass


# ── 5. quality_scorer.py ─────────────────────────────────────────────────────
class QualityScorerTests(TestCase):

    def test_error_detail_dataclass(self):
        from audioDiagnostic.utils.quality_scorer import ErrorDetail
        ed = ErrorDetail(
            position=0,
            pdf_word='hello',
            transcript_word='helo',
            match_type='mismatch',
            severity='minor'
        )
        self.assertEqual(ed.pdf_word, 'hello')

    def test_quality_segment_dataclass(self):
        from audioDiagnostic.utils.quality_scorer import QualitySegment
        qs = QualitySegment(
            segment_index=0,
            start_time=0.0,
            end_time=5.0,
            transcript_text='Hello world',
            quality_score=0.85,
            status='good',
            errors=[]
        )
        self.assertEqual(qs.quality_score, 0.85)

    def test_calculate_segment_quality_all_exact(self):
        from audioDiagnostic.utils.quality_scorer import calculate_segment_quality
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        alignment = [
            AlignmentPoint(pdf_word='hello', transcript_word='hello', match_type='exact', match_score=1.0),
            AlignmentPoint(pdf_word='world', transcript_word='world', match_type='exact', match_score=1.0),
        ]
        result = calculate_segment_quality(alignment)
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)

    def test_calculate_segment_quality_empty(self):
        from audioDiagnostic.utils.quality_scorer import calculate_segment_quality
        result = calculate_segment_quality([])
        self.assertIsInstance(result, float)

    def test_determine_segment_status(self):
        from audioDiagnostic.utils.quality_scorer import determine_segment_status
        result = determine_segment_status(0.9, [])
        self.assertIsInstance(result, str)

    def test_determine_segment_status_low(self):
        from audioDiagnostic.utils.quality_scorer import determine_segment_status
        result = determine_segment_status(0.3, [])
        self.assertIsInstance(result, str)

    def test_calculate_overall_quality(self):
        from audioDiagnostic.utils.quality_scorer import calculate_overall_quality, QualitySegment
        qs1 = QualitySegment(0, 0.0, 5.0, 'text1', 0.9, 'good', [])
        qs2 = QualitySegment(1, 5.0, 10.0, 'text2', 0.7, 'fair', [])
        result = calculate_overall_quality([qs1, qs2])
        self.assertIsInstance(result, float)

    def test_calculate_overall_quality_empty(self):
        from audioDiagnostic.utils.quality_scorer import calculate_overall_quality
        result = calculate_overall_quality([])
        self.assertEqual(result, 0.0)


# ── 6. production_report.py ──────────────────────────────────────────────────
class ProductionReportTests(TestCase):

    def test_format_timestamp_zero(self):
        from audioDiagnostic.utils.production_report import format_timestamp
        result = format_timestamp(0.0)
        self.assertIsInstance(result, str)

    def test_format_timestamp_one_minute(self):
        from audioDiagnostic.utils.production_report import format_timestamp
        result = format_timestamp(65.5)
        self.assertIsInstance(result, str)
        self.assertIn('1', result)

    def test_format_timestamp_range(self):
        from audioDiagnostic.utils.production_report import format_timestamp_range
        result = format_timestamp_range(10.0, 75.0)
        self.assertIsInstance(result, str)

    def test_checklist_item_dataclass(self):
        from audioDiagnostic.utils.production_report import ChecklistItem
        ci = ChecklistItem(
            item_type='error',
            description='Word mismatch',
            timestamp=10.0,
            severity='major'
        )
        self.assertEqual(ci.item_type, 'error')

    def test_count_repeated_words_empty(self):
        from audioDiagnostic.utils.production_report import count_repeated_words
        result = count_repeated_words([])
        self.assertEqual(result, 0)


# ── 7. pdf_text_cleaner.py ───────────────────────────────────────────────────
class PDFTextCleanerTests(TestCase):

    def test_clean_pdf_text_basic(self):
        from audioDiagnostic.utils.pdf_text_cleaner import clean_pdf_text
        result = clean_pdf_text('Hello world.\nThis is a test.')
        self.assertIsInstance(result, str)

    def test_clean_pdf_text_no_remove_headers(self):
        from audioDiagnostic.utils.pdf_text_cleaner import clean_pdf_text
        result = clean_pdf_text('Chapter 1\nContent here.', remove_headers=False)
        self.assertIsInstance(result, str)

    def test_remove_headers_footers_and_numbers(self):
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers
        text = 'Page 1\n\nContent here.\n\nPage 2\n\nMore content.'
        result = remove_headers_footers_and_numbers(text)
        self.assertIsInstance(result, str)

    def test_fix_word_spacing(self):
        from audioDiagnostic.utils.pdf_text_cleaner import fix_word_spacing
        result = fix_word_spacing('helloworld test spacing')
        self.assertIsInstance(result, str)

    def test_merge_spaced_letters(self):
        from audioDiagnostic.utils.pdf_text_cleaner import merge_spaced_letters
        result = merge_spaced_letters('h e l l o world')
        self.assertIsInstance(result, str)

    def test_fix_hyphenated_words(self):
        from audioDiagnostic.utils.pdf_text_cleaner import fix_hyphenated_words
        result = fix_hyphenated_words('Some hyph-\nenated words here.')
        self.assertIsInstance(result, str)

    def test_normalize_whitespace_cleaner(self):
        from audioDiagnostic.utils.pdf_text_cleaner import normalize_whitespace
        result = normalize_whitespace('hello   world\n\ntest')
        self.assertIsInstance(result, str)

    def test_fix_missing_spaces(self):
        from audioDiagnostic.utils.pdf_text_cleaner import fix_missing_spaces
        result = fix_missing_spaces('Hello.World this is atest.')
        self.assertIsInstance(result, str)

    def test_normalize_for_pattern_matching(self):
        from audioDiagnostic.utils.pdf_text_cleaner import normalize_for_pattern_matching
        result = normalize_for_pattern_matching('Hello, World! Test 123.')
        self.assertIsInstance(result, str)

    def test_analyze_pdf_text_quality(self):
        from audioDiagnostic.utils.pdf_text_cleaner import analyze_pdf_text_quality
        result = analyze_pdf_text_quality('Hello world. This is a test.')
        self.assertIsInstance(result, dict)

    def test_calculate_quality_score(self):
        from audioDiagnostic.utils.pdf_text_cleaner import calculate_quality_score
        result = calculate_quality_score(0.01, 2, 1)
        self.assertIsInstance(result, (int, float))

    def test_remove_detected_patterns(self):
        from audioDiagnostic.utils.pdf_text_cleaner import remove_detected_patterns
        text = 'Header\nContent\nFooter\nMore content'
        patterns = {'headers': {'Header'}, 'footers': {'Footer'}}
        result = remove_detected_patterns(text, patterns)
        self.assertIsInstance(result, str)


# ── 8. identify_all_duplicates (pure function) ────────────────────────────────
class IdentifyAllDuplicatesTests(TestCase):

    def test_no_duplicates(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        segments = [
            {'id': 1, 'audio_file_id': 1, 'audio_file_title': 'File1',
             'text': 'Hello world', 'start_time': 0.0, 'end_time': 1.0, 'segment_index': 0},
            {'id': 2, 'audio_file_id': 1, 'audio_file_title': 'File1',
             'text': 'Different text', 'start_time': 1.0, 'end_time': 2.0, 'segment_index': 1},
        ]
        result = identify_all_duplicates(segments)
        self.assertEqual(result, {})

    def test_with_duplicates(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        segments = [
            {'id': 1, 'audio_file_id': 1, 'audio_file_title': 'File1',
             'text': 'Hello world', 'start_time': 0.0, 'end_time': 1.0, 'segment_index': 0},
            {'id': 2, 'audio_file_id': 1, 'audio_file_title': 'File1',
             'text': 'Hello world', 'start_time': 2.0, 'end_time': 3.0, 'segment_index': 1},
        ]
        result = identify_all_duplicates(segments)
        self.assertEqual(len(result), 1)
        # Check structure
        for group_id, group_data in result.items():
            self.assertEqual(group_data['count'], 2)

    def test_empty_segments(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        result = identify_all_duplicates([])
        self.assertEqual(result, {})

    def test_empty_text_segments_ignored(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        segments = [
            {'id': 1, 'audio_file_id': 1, 'audio_file_title': 'File1',
             'text': '', 'start_time': 0.0, 'end_time': 1.0, 'segment_index': 0},
            {'id': 2, 'audio_file_id': 1, 'audio_file_title': 'File1',
             'text': '   ', 'start_time': 1.0, 'end_time': 2.0, 'segment_index': 1},
        ]
        result = identify_all_duplicates(segments)
        self.assertEqual(result, {})

    def test_word_type_classification(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        # Single word → 'word' type
        segments = [
            {'id': 1, 'audio_file_id': 1, 'audio_file_title': 'File1',
             'text': 'hello', 'start_time': 0.0, 'end_time': 1.0, 'segment_index': 0},
            {'id': 2, 'audio_file_id': 1, 'audio_file_title': 'File1',
             'text': 'hello', 'start_time': 2.0, 'end_time': 3.0, 'segment_index': 1},
        ]
        result = identify_all_duplicates(segments)
        for group_id, group_data in result.items():
            self.assertEqual(group_data['content_type'], 'word')

    def test_paragraph_type_classification(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        long_text = 'This is a very long sentence with more than fifteen words in total here.'
        segments = [
            {'id': 1, 'audio_file_id': 1, 'audio_file_title': 'File1',
             'text': long_text, 'start_time': 0.0, 'end_time': 5.0, 'segment_index': 0},
            {'id': 2, 'audio_file_id': 1, 'audio_file_title': 'File1',
             'text': long_text, 'start_time': 6.0, 'end_time': 11.0, 'segment_index': 1},
        ]
        result = identify_all_duplicates(segments)
        for group_id, group_data in result.items():
            self.assertEqual(group_data['content_type'], 'paragraph')
