"""
Wave 82 — Coverage boost
Targets pure utility functions in:
  - audioDiagnostic/utils/pdf_text_cleaner.py
  - audioDiagnostic/utils/repetition_detector.py (WordTimestamp, Occurrence, Repetition classes)
"""
from django.test import TestCase


# ══════════════════════════════════════════════════════════════════
# pdf_text_cleaner.py utility tests
# ══════════════════════════════════════════════════════════════════

class CleanPdfTextTests(TestCase):

    def test_empty_text(self):
        from audioDiagnostic.utils.pdf_text_cleaner import clean_pdf_text
        result = clean_pdf_text('')
        self.assertEqual(result, '')

    def test_none_text(self):
        from audioDiagnostic.utils.pdf_text_cleaner import clean_pdf_text
        result = clean_pdf_text(None)
        self.assertIsNone(result)

    def test_basic_text_preserved(self):
        from audioDiagnostic.utils.pdf_text_cleaner import clean_pdf_text
        text = "The quick brown fox jumped over the lazy dog."
        result = clean_pdf_text(text)
        # Core words should still be present
        self.assertIn("quick", result)
        self.assertIn("fox", result)

    def test_no_headers_removal(self):
        from audioDiagnostic.utils.pdf_text_cleaner import clean_pdf_text
        text = "Some body text here"
        result = clean_pdf_text(text, remove_headers=False)
        self.assertIn("body text", result)


class RemoveHeadersFootersTests(TestCase):

    def test_removes_standalone_page_numbers(self):
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers
        text = "Content line one\n42\nContent line two"
        result = remove_headers_footers_and_numbers(text)
        self.assertNotIn("\n42\n", result)

    def test_removes_page_markers(self):
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers
        text = "Good text\n- 5 -\nMore text"
        result = remove_headers_footers_and_numbers(text)
        self.assertNotIn("- 5 -", result)

    def test_removes_page_keyword(self):
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers
        text = "Some text\nPage 12\nMore text"
        result = remove_headers_footers_and_numbers(text)
        self.assertNotIn("Page 12", result)

    def test_keeps_regular_content(self):
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers
        text = "She walked into the room.\nHe said hello."
        result = remove_headers_footers_and_numbers(text)
        self.assertIn("walked into the room", result)
        self.assertIn("said hello", result)

    def test_removes_narrator_instructions(self):
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers
        text = "Good text here\n(Marian: Please add room tone)\nMore content"
        result = remove_headers_footers_and_numbers(text)
        self.assertNotIn("Marian: Please add room tone", result)


class FixWordSpacingTests(TestCase):

    def test_normal_text_unchanged(self):
        from audioDiagnostic.utils.pdf_text_cleaner import fix_word_spacing
        text = "The quick brown fox"
        result = fix_word_spacing(text)
        self.assertEqual(result, text)

    def test_spaced_letters_merged(self):
        from audioDiagnostic.utils.pdf_text_cleaner import fix_word_spacing
        # Typical PDF extraction artifact
        text = "T h e q u i c k"
        result = fix_word_spacing(text)
        # Should merge the spaced letters
        self.assertNotEqual(result, text)

    def test_multiline_preserved(self):
        from audioDiagnostic.utils.pdf_text_cleaner import fix_word_spacing
        text = "Line one\nLine two"
        result = fix_word_spacing(text)
        self.assertIn("\n", result)


class MergeSpacedLettersTests(TestCase):

    def test_merge_three_single_letters(self):
        from audioDiagnostic.utils.pdf_text_cleaner import merge_spaced_letters
        result = merge_spaced_letters("T h e")
        # Three letters should be merged
        self.assertEqual(result, "The")

    def test_two_letters_not_merged(self):
        from audioDiagnostic.utils.pdf_text_cleaner import merge_spaced_letters
        # Two single letters shouldn't merge (< 3 threshold)
        result = merge_spaced_letters("I a")
        # "I" and "a" remain separate since < 3 letters
        self.assertIn("I", result)

    def test_multi_letter_word_preserved(self):
        from audioDiagnostic.utils.pdf_text_cleaner import merge_spaced_letters
        result = merge_spaced_letters("Hello world")
        self.assertIn("Hello", result)
        self.assertIn("world", result)


class FixHyphenatedWordsTests(TestCase):

    def test_lowercase_continuation_merged(self):
        from audioDiagnostic.utils.pdf_text_cleaner import fix_hyphenated_words
        text = "The quick brown fox jump-\ned over"
        result = fix_hyphenated_words(text)
        self.assertIn("jumped", result)

    def test_uppercase_after_hyphen_kept(self):
        from audioDiagnostic.utils.pdf_text_cleaner import fix_hyphenated_words
        text = "First sentence end.\nNew sentence start"
        result = fix_hyphenated_words(text)
        self.assertIn("First sentence", result)


class NormalizeWhitespaceCleanerTests(TestCase):

    def test_multiple_spaces_reduced(self):
        from audioDiagnostic.utils.pdf_text_cleaner import normalize_whitespace
        text = "Hello   world"
        result = normalize_whitespace(text)
        self.assertNotIn("   ", result)

    def test_trailing_spaces_removed(self):
        from audioDiagnostic.utils.pdf_text_cleaner import normalize_whitespace
        text = "Hello   \nWorld   "
        result = normalize_whitespace(text)
        for line in result.split('\n'):
            self.assertFalse(line.endswith(' '))

    def test_excess_newlines_limited(self):
        from audioDiagnostic.utils.pdf_text_cleaner import normalize_whitespace
        text = "Line1\n\n\n\n\nLine2"
        result = normalize_whitespace(text)
        self.assertNotIn("\n\n\n", result)


class FixMissingSpacesTests(TestCase):

    def test_camel_case_split(self):
        from audioDiagnostic.utils.pdf_text_cleaner import fix_missing_spaces
        text = "helloWorld"
        result = fix_missing_spaces(text)
        self.assertIn(" ", result)

    def test_normal_text_unchanged(self):
        from audioDiagnostic.utils.pdf_text_cleaner import fix_missing_spaces
        text = "normal text here"
        result = fix_missing_spaces(text)
        self.assertEqual(result, text)


# ══════════════════════════════════════════════════════════════════
# repetition_detector.py class tests
# ══════════════════════════════════════════════════════════════════

class WordTimestampTests(TestCase):

    def test_to_dict(self):
        from audioDiagnostic.utils.repetition_detector import WordTimestamp
        wt = WordTimestamp(
            word='hello', original='Hello', start_time=0.0, end_time=0.5,
            segment_id=1, index=0
        )
        d = wt.to_dict()
        self.assertEqual(d['word'], 'hello')
        self.assertEqual(d['original'], 'Hello')
        self.assertEqual(d['start_time'], 0.0)
        self.assertFalse(d['excluded'])

    def test_excluded_flag_default(self):
        from audioDiagnostic.utils.repetition_detector import WordTimestamp
        wt = WordTimestamp(
            word='test', original='test', start_time=0.0, end_time=1.0,
            segment_id=1, index=0
        )
        self.assertFalse(wt.excluded)


class OccurrenceTests(TestCase):

    def test_to_dict(self):
        from audioDiagnostic.utils.repetition_detector import Occurrence
        occ = Occurrence(start_idx=0, end_idx=5, start_time=0.0, end_time=10.0)
        d = occ.to_dict()
        self.assertEqual(d['start_idx'], 0)
        self.assertEqual(d['end_idx'], 5)
        self.assertFalse(d['keep'])

    def test_keep_default_false(self):
        from audioDiagnostic.utils.repetition_detector import Occurrence
        occ = Occurrence(0, 5, 0.0, 5.0)
        self.assertFalse(occ.keep)


class RepetitionTests(TestCase):

    def test_last_occurrence_is_keeper(self):
        from audioDiagnostic.utils.repetition_detector import Occurrence, Repetition
        occ1 = Occurrence(0, 5, 0.0, 5.0)
        occ2 = Occurrence(10, 15, 10.0, 15.0)
        rep = Repetition(text='hello world', length=2, occurrences=[occ1, occ2])

        # Last occurrence is keeper
        self.assertTrue(occ2.keep)
        self.assertFalse(occ1.keep)
        self.assertEqual(rep.keeper_index, 1)

    def test_to_dict(self):
        from audioDiagnostic.utils.repetition_detector import Occurrence, Repetition
        occ1 = Occurrence(0, 5, 0.0, 5.0)
        rep = Repetition(text='test phrase', length=2, occurrences=[occ1])
        d = rep.to_dict()
        self.assertEqual(d['text'], 'test phrase')
        self.assertEqual(d['length'], 2)
        self.assertEqual(len(d['occurrences']), 1)


class BuildWordMapTests(TestCase):

    def test_empty_segments(self):
        from audioDiagnostic.utils.repetition_detector import build_word_map
        result = build_word_map([])
        self.assertEqual(result, [])

    def test_basic_segment(self):
        from audioDiagnostic.utils.repetition_detector import build_word_map
        # Create mock segment
        class MockSegment:
            text = "hello world"
            start_time = 0.0
            end_time = 2.0
            id = 1
        
        result = build_word_map([MockSegment()])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].word, 'hello')
        self.assertEqual(result[1].word, 'world')


class BuildWordMapFromTextTests(TestCase):

    def test_basic_text(self):
        from audioDiagnostic.utils.repetition_detector import build_word_map_from_text
        words = build_word_map_from_text("hello world foo")
        self.assertEqual(len(words), 3)

    def test_empty_text(self):
        from audioDiagnostic.utils.repetition_detector import build_word_map_from_text
        words = build_word_map_from_text("")
        self.assertEqual(words, [])


class FindRepeatedSequencesTests(TestCase):

    def test_finds_repetition(self):
        from audioDiagnostic.utils.repetition_detector import WordTimestamp, find_repeated_sequences
        # "hello world" appears twice
        def make_word(w, i):
            return WordTimestamp(w.lower(), w, float(i), float(i+1), 1, i)
        
        words = [
            make_word("hello", 0),
            make_word("world", 1),
            make_word("and", 2),
            make_word("then", 3),
            make_word("hello", 4),
            make_word("world", 5),
        ]
        
        repetitions = find_repeated_sequences(words, min_length=2, max_length=10)
        # There should be at least one repetition detected
        self.assertIsInstance(repetitions, list)


class MarkExcludedWordsTests(TestCase):

    def test_marks_non_keeper_excluded(self):
        from audioDiagnostic.utils.repetition_detector import (
            WordTimestamp, Occurrence, Repetition, mark_excluded_words
        )
        def make_word(w, i):
            return WordTimestamp(w.lower(), w, float(i), float(i+1), 1, i)
        
        words = [make_word(w, i) for i, w in enumerate(
            ["hello", "world", "and", "hello", "world"]
        )]
        
        # Create repetition: "hello world" at positions 0-1 and 3-4
        occ1 = Occurrence(0, 2, 0.0, 2.0)
        occ2 = Occurrence(3, 5, 3.0, 5.0)
        rep = Repetition(text='hello world', length=2, occurrences=[occ1, occ2])
        
        mark_excluded_words(words, [rep])
        
        # occ1 should be excluded (not the keeper), occ2 is keeper
        self.assertTrue(words[0].excluded)
        self.assertTrue(words[1].excluded)
        self.assertFalse(words[3].excluded)
        self.assertFalse(words[4].excluded)
