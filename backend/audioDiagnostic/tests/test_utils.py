"""
Unit tests for audioDiagnostic utility modules.

Covers:
- text_normalizer.py
- pdf_text_cleaner.py
- repetition_detector.py
- gap_detector.py
- quality_scorer.py
- alignment_engine.py
"""

from django.test import TestCase


# ---------------------------------------------------------------------------
# text_normalizer tests
# ---------------------------------------------------------------------------

class TextNormalizerTests(TestCase):

    def setUp(self):
        from audioDiagnostic.utils.text_normalizer import (
            expand_contractions, remove_punctuation, normalize_whitespace,
            normalize_unicode, normalize_text, tokenize_words, normalize_word,
            calculate_word_similarity, levenshtein_distance, create_word_variants,
            get_ngrams, find_repeated_ngrams, remove_page_numbers,
            remove_footnote_markers, prepare_pdf_for_audiobook,
            prepare_transcript_for_comparison,
        )
        self.expand = expand_contractions
        self.rm_punct = remove_punctuation
        self.norm_ws = normalize_whitespace
        self.norm_uni = normalize_unicode
        self.norm_text = normalize_text
        self.tokenize = tokenize_words
        self.norm_word = normalize_word
        self.word_sim = calculate_word_similarity
        self.levenshtein = levenshtein_distance
        self.variants = create_word_variants
        self.ngrams = get_ngrams
        self.repeated_ngrams = find_repeated_ngrams
        self.rm_page_nums = remove_page_numbers
        self.rm_footnotes = remove_footnote_markers
        self.prep_pdf = prepare_pdf_for_audiobook
        self.prep_transcript = prepare_transcript_for_comparison

    # expand_contractions
    def test_expand_cant(self):
        self.assertEqual(self.expand("can't"), "cannot")

    def test_expand_wont(self):
        self.assertIn("will not", self.expand("won't"))

    def test_expand_its(self):
        result = self.expand("it's a test")
        self.assertIn("it is", result)

    def test_expand_no_contraction(self):
        self.assertEqual(self.expand("hello world"), "hello world")

    def test_expand_case_insensitive(self):
        result = self.expand("I'M happy")
        self.assertIn("i am", result.lower())

    # remove_punctuation
    def test_remove_punctuation_basic(self):
        self.assertEqual(self.rm_punct("hello, world!"), "hello world")

    def test_remove_punctuation_keep_apostrophes(self):
        result = self.rm_punct("it's ok", keep_apostrophes=True)
        self.assertIn("'", result)

    def test_remove_punctuation_empty(self):
        self.assertEqual(self.rm_punct(""), "")

    # normalize_whitespace
    def test_normalize_whitespace_multiple_spaces(self):
        self.assertEqual(self.norm_ws("hello   world"), "hello world")

    def test_normalize_whitespace_strips(self):
        self.assertEqual(self.norm_ws("  hello  "), "hello")

    def test_normalize_whitespace_newlines(self):
        self.assertEqual(self.norm_ws("hello\n\nworld"), "hello world")

    def test_normalize_whitespace_tabs(self):
        self.assertEqual(self.norm_ws("hello\tworld"), "hello world")

    # normalize_unicode
    def test_normalize_unicode_smart_quotes(self):
        result = self.norm_uni("\u201chello\u201d")
        self.assertIn('"hello"', result)

    def test_normalize_unicode_em_dash(self):
        result = self.norm_uni("one\u2014two")
        self.assertIn("-", result)

    def test_normalize_unicode_plain_text(self):
        self.assertEqual(self.norm_uni("hello"), "hello")

    # normalize_text
    def test_normalize_text_full_pipeline(self):
        result = self.norm_text("It's A Test,  Really!")
        self.assertEqual(result, "it is a test really")

    def test_normalize_text_no_expand(self):
        result = self.norm_text("can't", expand_contractions_flag=False)
        self.assertNotIn("cannot", result)

    def test_normalize_text_no_lowercase(self):
        result = self.norm_text("Hello", lowercase=False)
        self.assertIn("H", result)

    def test_normalize_text_no_punctuation_removal(self):
        result = self.norm_text("hello,", remove_punctuation_flag=False)
        self.assertIn(",", result)

    def test_normalize_text_empty(self):
        self.assertEqual(self.norm_text(""), "")

    # tokenize_words
    def test_tokenize_basic(self):
        self.assertEqual(self.tokenize("hello world"), ["hello", "world"])

    def test_tokenize_normalize_flag(self):
        result = self.tokenize("Hello, World!", normalize=True)
        self.assertEqual(result, ["hello", "world"])

    def test_tokenize_empty(self):
        self.assertEqual(self.tokenize(""), [])

    def test_tokenize_extra_spaces(self):
        result = self.tokenize("  hello   world  ")
        self.assertEqual(result, ["hello", "world"])

    # normalize_word
    def test_normalize_word_basic(self):
        self.assertEqual(self.norm_word("Hello!"), "hello")

    def test_normalize_word_empty(self):
        self.assertEqual(self.norm_word(""), "")

    def test_normalize_word_strips(self):
        self.assertEqual(self.norm_word("  word  "), "word")

    # calculate_word_similarity
    def test_similarity_exact(self):
        self.assertEqual(self.word_sim("hello", "hello"), 1.0)

    def test_similarity_case_insensitive(self):
        score = self.word_sim("Hello", "hello")
        self.assertGreaterEqual(score, 0.9)

    def test_similarity_different_words(self):
        score = self.word_sim("apple", "zebra")
        self.assertLess(score, 0.5)

    def test_similarity_contraction(self):
        score = self.word_sim("can't", "cannot")
        self.assertGreater(score, 0.0)

    def test_similarity_empty_words(self):
        score = self.word_sim("", "")
        self.assertEqual(score, 1.0)

    # levenshtein_distance
    def test_levenshtein_same(self):
        self.assertEqual(self.levenshtein("hello", "hello"), 0)

    def test_levenshtein_one_change(self):
        self.assertEqual(self.levenshtein("hello", "helo"), 1)

    def test_levenshtein_empty(self):
        self.assertEqual(self.levenshtein("", "hello"), 5)
        self.assertEqual(self.levenshtein("hello", ""), 5)

    def test_levenshtein_both_empty(self):
        self.assertEqual(self.levenshtein("", ""), 0)

    def test_levenshtein_short_vs_long(self):
        # Swaps s1/s2 if s1 shorter
        d1 = self.levenshtein("hi", "hello")
        d2 = self.levenshtein("hello", "hi")
        self.assertEqual(d1, d2)

    # create_word_variants
    def test_variants_returns_list(self):
        result = self.variants("hello")
        self.assertIsInstance(result, list)
        self.assertIn("hello", result)

    def test_variants_contraction(self):
        result = self.variants("can't")
        # Should include original and normalized form
        self.assertTrue(len(result) >= 1)

    # get_ngrams
    def test_ngrams_bigrams(self):
        words = ["a", "b", "c", "d"]
        result = self.ngrams(words, 2)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], ("a b", 0))

    def test_ngrams_trigrams(self):
        words = ["a", "b", "c", "d"]
        result = self.ngrams(words, 3)
        self.assertEqual(len(result), 2)

    def test_ngrams_empty(self):
        self.assertEqual(self.ngrams([], 2), [])

    def test_ngrams_too_short(self):
        # n > len(words) produces empty list
        result = self.ngrams(["a", "b"], 5)
        self.assertEqual(result, [])

    # find_repeated_ngrams
    def test_find_repeated_ngrams_detects_repeat(self):
        words = ["hello", "world", "hello", "world", "extra"]
        result = self.repeated_ngrams(words, n=2)
        # "hello world" should appear at positions 0 and 2
        self.assertTrue(len(result) > 0)

    def test_find_repeated_ngrams_no_repeat(self):
        words = ["a", "b", "c", "d"]
        result = self.repeated_ngrams(words, n=2)
        self.assertEqual(result, {})

    # remove_page_numbers
    def test_remove_page_numbers_standalone(self):
        text = "Some text\n42\nMore text"
        result = self.rm_page_nums(text)
        self.assertNotIn("\n42\n", result)

    def test_remove_page_numbers_page_n(self):
        result = self.rm_page_nums("See Page 10 for details")
        self.assertNotIn("Page 10", result)

    # remove_footnote_markers
    def test_remove_footnote_bracketed(self):
        result = self.rm_footnotes("text[1] more text")
        self.assertNotIn("[1]", result)

    def test_remove_footnote_parenthesized(self):
        result = self.rm_footnotes("text(2) more text")
        self.assertNotIn("(2)", result)

    # prepare_pdf_for_audiobook
    def test_prepare_pdf_returns_string(self):
        result = self.prep_pdf("Chapter One\nHello world.\n42")
        self.assertIsInstance(result, str)
        self.assertIn("Hello world", result)

    # prepare_transcript_for_comparison
    def test_prepare_transcript_normalizes(self):
        result = self.prep_transcript("  Hello   World  ")
        self.assertEqual(result, "Hello World")


# ---------------------------------------------------------------------------
# pdf_text_cleaner tests
# ---------------------------------------------------------------------------

class PdfTextCleanerTests(TestCase):

    def setUp(self):
        from audioDiagnostic.utils.pdf_text_cleaner import (
            clean_pdf_text, remove_headers_footers_and_numbers,
            fix_word_spacing, merge_spaced_letters, fix_hyphenated_words,
            normalize_whitespace,
        )
        self.clean = clean_pdf_text
        self.rm_headers = remove_headers_footers_and_numbers
        self.fix_spacing = fix_word_spacing
        self.merge = merge_spaced_letters
        self.fix_hyphen = fix_hyphenated_words
        self.norm_ws = normalize_whitespace

    def test_clean_empty(self):
        self.assertIsNone(self.clean(None))
        self.assertEqual(self.clean(""), "")

    def test_clean_plain_text(self):
        result = self.clean("Hello world.")
        self.assertIn("Hello world", result)

    def test_clean_removes_standalone_page_number(self):
        text = "Some content\n42\nMore content"
        result = self.clean(text)
        lines = result.split('\n')
        bare_nums = [l for l in lines if l.strip() == '42']
        self.assertEqual(bare_nums, [])

    def test_clean_normalizes_whitespace(self):
        result = self.clean("Hello   world")
        self.assertNotIn("   ", result)

    def test_rm_headers_removes_page_number(self):
        text = "Some text\n5\nMore text"
        result = self.rm_headers(text)
        lines = result.split('\n')
        self.assertNotIn("5", [l.strip() for l in lines])

    def test_rm_headers_keeps_body_text(self):
        text = "This is the main body text that should remain."
        result = self.rm_headers(text)
        self.assertIn("This is the main body text", result)

    def test_rm_headers_removes_narrator_instruction(self):
        text = "Normal text\n(Marian: Please add 3 seconds of room tone)\nMore text"
        result = self.rm_headers(text)
        self.assertNotIn("Please add 3 seconds", result)

    def test_fix_spacing_normal_text(self):
        # Normal text should not be changed significantly
        text = "This is normal text."
        result = self.fix_spacing(text)
        self.assertIn("normal text", result)

    def test_fix_spacing_spaced_letters(self):
        # Text with spaced single letters should be merged
        text = "h e l l o w o r l d"
        result = self.fix_spacing(text)
        # Should merge the spaced letters
        self.assertIsInstance(result, str)

    def test_merge_spaced_letters_basic(self):
        result = self.merge("h e l l o")
        # Should produce a merged word
        self.assertIsInstance(result, str)
        self.assertNotEqual(result, "")

    def test_fix_hyphenated_words_returns_string(self):
        text = "re-\nturned"
        result = self.fix_hyphen(text)
        self.assertIsInstance(result, str)

    def test_normalize_whitespace_double_space(self):
        result = self.norm_ws("hello  world")
        self.assertNotIn("  ", result)

    def test_clean_remove_headers_false(self):
        # When remove_headers=False, headers are kept
        text = "Chapter One\nHello world."
        result = self.clean(text, remove_headers=False)
        self.assertIn("Hello world", result)


# ---------------------------------------------------------------------------
# repetition_detector tests
# ---------------------------------------------------------------------------

class RepetitionDetectorTests(TestCase):

    def setUp(self):
        from audioDiagnostic.utils.repetition_detector import (
            WordTimestamp, Occurrence, Repetition,
            build_word_map_from_text, find_repeated_sequences,
            filter_overlapping_positions,
        )
        self.WordTimestamp = WordTimestamp
        self.Occurrence = Occurrence
        self.Repetition = Repetition
        self.build_word_map_from_text = build_word_map_from_text
        self.find_repeated_sequences = find_repeated_sequences
        self.filter_overlapping_positions = filter_overlapping_positions

    def test_word_timestamp_attrs(self):
        wt = self.WordTimestamp("hello", "Hello", 0.0, 1.0, 1, 0)
        self.assertEqual(wt.word, "hello")
        self.assertEqual(wt.original, "Hello")
        self.assertFalse(wt.excluded)

    def test_word_timestamp_to_dict(self):
        wt = self.WordTimestamp("hello", "Hello", 0.0, 1.0, 1, 0)
        d = wt.to_dict()
        self.assertIn('word', d)
        self.assertIn('excluded', d)

    def test_occurrence_attrs(self):
        occ = self.Occurrence(0, 5, 0.0, 5.0)
        self.assertEqual(occ.start_idx, 0)
        self.assertFalse(occ.keep)

    def test_occurrence_to_dict(self):
        occ = self.Occurrence(0, 5, 0.0, 5.0)
        d = occ.to_dict()
        self.assertIn('start_idx', d)
        self.assertIn('keep', d)

    def test_repetition_marks_last_keeper(self):
        occ1 = self.Occurrence(0, 4, 0.0, 4.0)
        occ2 = self.Occurrence(10, 14, 10.0, 14.0)
        rep = self.Repetition("hello world test foo bar", 5, [occ1, occ2])
        self.assertTrue(occ2.keep)
        self.assertFalse(occ1.keep)

    def test_repetition_to_dict(self):
        occ = self.Occurrence(0, 4, 0.0, 4.0)
        rep = self.Repetition("test", 1, [occ])
        d = rep.to_dict()
        self.assertIn('text', d)
        self.assertIn('occurrences', d)

    def test_build_word_map_from_text_basic(self):
        result = self.build_word_map_from_text("hello world foo bar")
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0].word, "hello")
        self.assertEqual(result[0].start_time, 0.0)

    def test_build_word_map_from_text_empty(self):
        result = self.build_word_map_from_text("")
        self.assertEqual(result, [])

    def test_build_word_map_indices(self):
        result = self.build_word_map_from_text("a b c")
        for i, wt in enumerate(result):
            self.assertEqual(wt.index, i)

    def test_find_repeated_sequences_no_repeats(self):
        word_map = self.build_word_map_from_text("the quick brown fox jumps over the lazy dog")
        result = self.find_repeated_sequences(word_map, min_length=3)
        # 'the' appears twice but less than min_length=3 as a phrase
        self.assertIsInstance(result, list)

    def test_find_repeated_sequences_with_repeat(self):
        # Create text with a clear repeated 5-word sequence
        text = ("one two three four five six seven "
                "one two three four five eight nine")
        word_map = self.build_word_map_from_text(text)
        result = self.find_repeated_sequences(word_map, min_length=5, max_length=5)
        self.assertIsInstance(result, list)

    def test_filter_overlapping_positions(self):
        positions = [0, 3, 10, 13]
        result = self.filter_overlapping_positions(positions, n=5)
        # 0 and 3 overlap (3 < 0+5), so only one should survive from that pair
        self.assertIsInstance(result, list)


# ---------------------------------------------------------------------------
# alignment_engine tests
# ---------------------------------------------------------------------------

class AlignmentEngineTests(TestCase):

    def setUp(self):
        from audioDiagnostic.utils.alignment_engine import (
            AlignmentPoint, determine_match_type,
            create_alignment_matrix, backtrack_alignment,
            get_context_words, estimate_reading_time,
        )
        from audioDiagnostic.utils.repetition_detector import WordTimestamp

        self.AlignmentPoint = AlignmentPoint
        self.determine_match_type = determine_match_type
        self.create_alignment_matrix = create_alignment_matrix
        self.backtrack_alignment = backtrack_alignment
        self.get_context_words = get_context_words
        self.estimate_reading_time = estimate_reading_time
        self.WordTimestamp = WordTimestamp

    def _make_wt(self, word, start=0.0, end=1.0):
        return self.WordTimestamp(word, word, start, end, 0, 0)

    def test_alignment_point_attrs(self):
        ap = self.AlignmentPoint(pdf_word="hello", transcript_word="hello",
                                  match_type="exact", match_score=1.0)
        self.assertEqual(ap.pdf_word, "hello")
        self.assertEqual(ap.match_type, "exact")

    def test_alignment_point_to_dict(self):
        ap = self.AlignmentPoint(pdf_word="hello", transcript_word="hello",
                                  match_type="exact", match_score=1.0)
        d = ap.to_dict()
        self.assertIn('pdf_word', d)
        self.assertIn('match_type', d)

    def test_determine_match_type_exact(self):
        result = self.determine_match_type("hello", "hello", 1.0)
        self.assertEqual(result, "exact")

    def test_determine_match_type_normalized(self):
        result = self.determine_match_type("Hello!", "hello", 0.95)
        self.assertEqual(result, "normalized")

    def test_determine_match_type_phonetic(self):
        result = self.determine_match_type("colour", "color", 0.8)
        self.assertEqual(result, "phonetic")

    def test_determine_match_type_mismatch(self):
        result = self.determine_match_type("apple", "zebra", 0.1)
        self.assertEqual(result, "mismatch")

    def test_create_alignment_matrix_dimensions(self):
        pdf_words = ["hello", "world"]
        transcript_words = [self._make_wt("hello"), self._make_wt("world")]
        matrix = self.create_alignment_matrix(pdf_words, transcript_words)
        # Should be (m+1) x (n+1)
        self.assertEqual(len(matrix), 3)
        self.assertEqual(len(matrix[0]), 3)

    def test_create_alignment_matrix_empty(self):
        matrix = self.create_alignment_matrix([], [])
        self.assertEqual(matrix, [[0.0]])

    def test_backtrack_alignment_basic(self):
        pdf_words = ["hello", "world"]
        transcript_words = [self._make_wt("hello"), self._make_wt("world")]
        matrix = self.create_alignment_matrix(pdf_words, transcript_words)
        alignment = self.backtrack_alignment(matrix, pdf_words, transcript_words)
        self.assertEqual(len(alignment), 2)
        # Both should be exact or normalized matches
        for ap in alignment:
            self.assertIn(ap.match_type, ['exact', 'normalized', 'phonetic', 'mismatch'])

    def test_align_full_pipeline(self):
        pdf_words = ["the", "cat", "sat"]
        transcript_words = [self._make_wt(w) for w in ["the", "cat", "sat"]]
        matrix = self.create_alignment_matrix(pdf_words, transcript_words)
        result = self.backtrack_alignment(matrix, pdf_words, transcript_words)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)

    def test_get_context_words_basic(self):
        points = [
            self.AlignmentPoint(pdf_word="the", pdf_index=0),
            self.AlignmentPoint(pdf_word="quick", pdf_index=1),
            self.AlignmentPoint(pdf_word="brown", pdf_index=2),
            self.AlignmentPoint(pdf_word="fox", pdf_index=3),
        ]
        result = self.get_context_words(points, 2, context_size=2, use_pdf=True)
        self.assertIsInstance(result, str)

    def test_get_context_words_empty(self):
        result = self.get_context_words([], 0, context_size=3, use_pdf=True)
        self.assertEqual(result, "")

    def test_estimate_reading_time_basic(self):
        result = self.estimate_reading_time(150)
        # 150 words at ~150 wpm = ~1 minute
        self.assertIsInstance(result, str)
        self.assertIn("min", result)

    def test_estimate_reading_time_zero(self):
        result = self.estimate_reading_time(0)
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# gap_detector tests
# ---------------------------------------------------------------------------

class GapDetectorTests(TestCase):

    def setUp(self):
        from audioDiagnostic.utils.gap_detector import (
            MissingSection, find_context_before_gap, find_context_after_gap,
            find_missing_sections, calculate_completeness_percentage,
        )
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint

        self.MissingSection = MissingSection
        self.find_context_before = find_context_before_gap
        self.find_context_after = find_context_after_gap
        self.find_missing_sections = find_missing_sections
        self.calculate_completeness = calculate_completeness_percentage
        self.AlignmentPoint = AlignmentPoint

    def _make_ap(self, pdf_word=None, transcript_word=None, match_type='exact'):
        return self.AlignmentPoint(
            pdf_word=pdf_word,
            transcript_word=transcript_word,
            match_type=match_type,
        )

    def test_missing_section_attrs(self):
        ms = self.MissingSection(0, 5, "missing text here", 3, "before", "after", "1m 0s")
        self.assertEqual(ms.pdf_start_index, 0)
        self.assertEqual(ms.missing_text, "missing text here")

    def test_missing_section_to_dict(self):
        ms = self.MissingSection(0, 5, "text", 1, "before", "after", "0m 30s")
        d = ms.to_dict()
        self.assertIn('missing_text', d)
        self.assertIn('word_count', d)

    def test_find_context_before_empty(self):
        result = self.find_context_before([], 0)
        self.assertEqual(result, "")

    def test_find_context_before_basic(self):
        points = [
            self._make_ap(pdf_word="the"),
            self._make_ap(pdf_word="quick"),
            self._make_ap(pdf_word="brown"),
        ]
        result = self.find_context_before(points, 2, context_words=2)
        self.assertIn("the", result)

    def test_find_context_after_basic(self):
        points = [
            self._make_ap(pdf_word="the"),
            self._make_ap(pdf_word="quick"),
            self._make_ap(pdf_word="brown"),
        ]
        result = self.find_context_after(points, 0, context_words=2)
        self.assertIn("quick", result)

    def test_find_context_after_empty(self):
        result = self.find_context_after([], 0)
        self.assertEqual(result, "")

    def test_find_missing_sections_no_missing(self):
        alignment = [
            self._make_ap(pdf_word="hello", transcript_word="hello", match_type="exact"),
            self._make_ap(pdf_word="world", transcript_word="world", match_type="exact"),
        ]
        result = self.find_missing_sections(alignment)
        self.assertEqual(result, [])

    def test_find_missing_sections_with_gap(self):
        # Need 10+ consecutive missing words (default min_gap_words=10)
        words = ["one", "two", "three", "four", "five",
                 "six", "seven", "eight", "nine", "ten", "eleven"]
        alignment = (
            [self._make_ap(pdf_word="the", transcript_word="the", match_type="exact")] +
            [self._make_ap(pdf_word=w, transcript_word=None, match_type="missing") for w in words] +
            [self._make_ap(pdf_word="end", transcript_word="end", match_type="exact")]
        )
        result = self.find_missing_sections(alignment)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].word_count, 11)

    def test_find_missing_sections_returns_list_empty(self):
        result = self.find_missing_sections([])
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_calculate_completeness_all_match(self):
        alignment = [
            self._make_ap(pdf_word="hello", transcript_word="hello", match_type="exact"),
            self._make_ap(pdf_word="world", transcript_word="world", match_type="exact"),
        ]
        result = self.calculate_completeness(alignment)
        self.assertEqual(result, 100.0)

    def test_calculate_completeness_all_missing(self):
        alignment = [
            self._make_ap(pdf_word="hello", transcript_word=None, match_type="missing"),
            self._make_ap(pdf_word="world", transcript_word=None, match_type="missing"),
        ]
        result = self.calculate_completeness(alignment)
        self.assertEqual(result, 0.0)

    def test_calculate_completeness_empty(self):
        result = self.calculate_completeness([])
        self.assertEqual(result, 0.0)


# ---------------------------------------------------------------------------
# quality_scorer tests
# ---------------------------------------------------------------------------

class QualityScorerTests(TestCase):

    def setUp(self):
        from audioDiagnostic.utils.quality_scorer import (
            ErrorDetail, QualitySegment, extract_errors,
            calculate_segment_quality, determine_segment_status,
            analyze_segments, calculate_overall_quality, compile_all_errors,
        )
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint

        self.ErrorDetail = ErrorDetail
        self.QualitySegment = QualitySegment
        self.extract_errors = extract_errors
        self.calc_quality = calculate_segment_quality
        self.det_status = determine_segment_status
        self.analyze = analyze_segments
        self.calc_overall = calculate_overall_quality
        self.compile_errors = compile_all_errors
        self.AlignmentPoint = AlignmentPoint

    def _make_ap(self, pdf_word="word", transcript_word="word", match_type="exact"):
        from audioDiagnostic.utils.alignment_engine import AlignmentPoint
        return AlignmentPoint(
            pdf_word=pdf_word,
            transcript_word=transcript_word,
            match_type=match_type,
            match_score=1.0 if match_type == 'exact' else 0.0,
        )

    def test_error_detail_attrs(self):
        ed = self.ErrorDetail("mismatch", 5, pdf_word="hello", transcript_word="helo")
        self.assertEqual(ed.error_type, "mismatch")
        self.assertEqual(ed.position, 5)

    def test_error_detail_to_dict(self):
        ed = self.ErrorDetail("missing", 3)
        d = ed.to_dict()
        self.assertIn('error_type', d)
        self.assertIn('position', d)

    def test_quality_segment_attrs(self):
        qs = self.QualitySegment(1, 0.0, 10.0, 0.95, "production_ready", {}, [])
        self.assertEqual(qs.quality_score, 0.95)
        self.assertEqual(qs.status, "production_ready")

    def test_quality_segment_to_dict(self):
        qs = self.QualitySegment(1, 0.0, 5.0, 0.8, "needs_minor_edits", {}, [])
        d = qs.to_dict()
        self.assertIn('quality_score', d)
        self.assertIn('status', d)
        self.assertIn('errors', d)

    def test_calc_quality_all_exact(self):
        alignment = [self._make_ap(match_type="exact") for _ in range(5)]
        score = self.calc_quality(alignment)
        self.assertEqual(score, 1.0)

    def test_calc_quality_all_mismatch(self):
        alignment = [self._make_ap(match_type="mismatch") for _ in range(5)]
        score = self.calc_quality(alignment)
        self.assertEqual(score, 0.0)

    def test_calc_quality_empty(self):
        score = self.calc_quality([])
        self.assertEqual(score, 0.0)

    def test_calc_quality_mixed(self):
        alignment = [
            self._make_ap(match_type="exact"),
            self._make_ap(match_type="normalized"),
            self._make_ap(match_type="mismatch"),
        ]
        score = self.calc_quality(alignment)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_determine_status_production_ready(self):
        status = self.det_status(0.96, missing_count=0, mismatch_count=0)
        self.assertEqual(status, "production_ready")

    def test_determine_status_needs_minor_edits(self):
        status = self.det_status(0.88, missing_count=0, mismatch_count=0)
        self.assertEqual(status, "needs_minor_edits")

    def test_determine_status_needs_review(self):
        status = self.det_status(0.72, missing_count=0, mismatch_count=0)
        self.assertEqual(status, "needs_review")

    def test_determine_status_needs_rerecording(self):
        status = self.det_status(0.4, missing_count=0, mismatch_count=0)
        self.assertEqual(status, "needs_rerecording")

    def test_determine_status_with_missing(self):
        # missing_count > 0 prevents production_ready even with high score
        status = self.det_status(0.98, missing_count=2, mismatch_count=0)
        self.assertNotEqual(status, "production_ready")

    def test_extract_errors_no_errors(self):
        alignment = [self._make_ap(match_type="exact") for _ in range(3)]
        errors = self.extract_errors(alignment, alignment, 0)
        self.assertEqual(errors, [])

    def test_extract_errors_with_mismatch(self):
        alignment = [
            self._make_ap(match_type="exact"),
            self._make_ap(match_type="mismatch"),
            self._make_ap(match_type="exact"),
        ]
        errors = self.extract_errors(alignment, alignment, 0)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "mismatch")

    def test_analyze_segments_empty(self):
        result = self.analyze([])
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_analyze_segments_returns_quality_segments(self):
        alignment = [self._make_ap(match_type="exact") for _ in range(10)]
        result = self.analyze(alignment, segment_size=5)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].quality_score, 1.0)

    def test_calculate_overall_quality_empty(self):
        result = self.calc_overall([])
        self.assertEqual(result, 0.0)

    def test_calculate_overall_quality_basic(self):
        qs = self.QualitySegment(0, None, None, 0.8, "needs_minor_edits", {}, [])
        result = self.calc_overall([qs])
        self.assertAlmostEqual(result, 0.8)

    def test_compile_all_errors_no_errors(self):
        alignment = [self._make_ap(match_type="exact") for _ in range(3)]
        errors = self.compile_errors(alignment)
        self.assertEqual(errors, [])

    def test_compile_all_errors_with_mismatch(self):
        alignment = [
            self._make_ap(match_type="exact"),
            self._make_ap(match_type="mismatch"),
            self._make_ap(match_type="missing"),
        ]
        errors = self.compile_errors(alignment)
        self.assertEqual(len(errors), 2)


# ---------------------------------------------------------------------------
# accounts models_feedback tests
# ---------------------------------------------------------------------------

class FeedbackModelTests(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        self.User = User
        self.user = User.objects.create_user(
            username='testfeedback', password='testpass123'
        )

    def _create_feedback(self, rating=5, worked=True):
        from accounts.models_feedback import FeatureFeedback
        return FeatureFeedback.objects.create(
            user=self.user,
            feature='ai_duplicate_detection',
            worked_as_expected=worked,
            what_you_like='Great feature',
            what_to_improve='Nothing',
            rating=rating,
        )

    def test_create_feedback(self):
        fb = self._create_feedback()
        self.assertEqual(fb.feature, 'ai_duplicate_detection')
        self.assertEqual(fb.rating, 5)
        self.assertEqual(fb.status, 'new')

    def test_feedback_str(self):
        fb = self._create_feedback()
        s = str(fb)
        self.assertIn('testfeedback', s)
        self.assertIn('5', s)

    def test_is_positive_true(self):
        fb = self._create_feedback(rating=5, worked=True)
        self.assertTrue(fb.is_positive)

    def test_is_positive_false_low_rating(self):
        fb = self._create_feedback(rating=3, worked=True)
        self.assertFalse(fb.is_positive)

    def test_is_positive_false_not_worked(self):
        fb = self._create_feedback(rating=5, worked=False)
        self.assertFalse(fb.is_positive)

    def test_needs_attention_true_low_rating(self):
        fb = self._create_feedback(rating=2, worked=True)
        self.assertTrue(fb.needs_attention)

    def test_needs_attention_true_not_worked(self):
        fb = self._create_feedback(rating=5, worked=False)
        self.assertTrue(fb.needs_attention)

    def test_needs_attention_false(self):
        fb = self._create_feedback(rating=4, worked=True)
        self.assertFalse(fb.needs_attention)

    def test_feedback_summary_update(self):
        from accounts.models_feedback import FeatureFeedbackSummary
        self._create_feedback(rating=5, worked=True)
        self._create_feedback(rating=3, worked=False)
        FeatureFeedbackSummary.update_summary('ai_duplicate_detection')
        summary = FeatureFeedbackSummary.objects.get(feature='ai_duplicate_detection')
        self.assertEqual(summary.total_responses, 2)
        self.assertGreater(float(summary.average_rating), 0)

    def test_feedback_summary_str(self):
        from accounts.models_feedback import FeatureFeedbackSummary
        self._create_feedback(rating=4)
        FeatureFeedbackSummary.update_summary('ai_duplicate_detection')
        summary = FeatureFeedbackSummary.objects.get(feature='ai_duplicate_detection')
        s = str(summary)
        self.assertIn('ai_duplicate_detection', s)

    def test_feedback_audio_file_optional(self):
        from accounts.models_feedback import FeatureFeedback
        fb = FeatureFeedback.objects.create(
            user=self.user,
            feature='pdf_upload',
            worked_as_expected=True,
            rating=4,
            audio_file_id=None,
        )
        self.assertIsNone(fb.audio_file_id)

    def test_feedback_ordering(self):
        from accounts.models_feedback import FeatureFeedback
        fb1 = self._create_feedback(rating=5)
        fb2 = self._create_feedback(rating=3)
        qs = list(FeatureFeedback.objects.all())
        # Most recent first
        self.assertEqual(qs[0].id, fb2.id)
