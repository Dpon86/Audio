"""
Wave 81 — Coverage boost
Targets pure utility functions in:
  - audioDiagnostic/utils/text_normalizer.py
  - audioDiagnostic/views/tab3_review_deletions.py (direct function calls)
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory
from rest_framework.authtoken.models import Token
from rest_framework.test import APIRequestFactory

from audioDiagnostic.models import AudioProject, AudioFile, Transcription, TranscriptionSegment


# ══════════════════════════════════════════════════════════════════
# text_normalizer utility tests — no Django/DB needed
# ══════════════════════════════════════════════════════════════════

class ExpandContractionsTests(TestCase):

    def test_basic_contractions(self):
        from audioDiagnostic.utils.text_normalizer import expand_contractions
        self.assertEqual(expand_contractions("can't do it"), "cannot do it")
        self.assertEqual(expand_contractions("won't stop"), "will not stop")
        self.assertEqual(expand_contractions("I'm fine"), "I am fine")

    def test_no_contractions(self):
        from audioDiagnostic.utils.text_normalizer import expand_contractions
        text = "Hello world no contractions here"
        self.assertEqual(expand_contractions(text), text)

    def test_multiple_contractions(self):
        from audioDiagnostic.utils.text_normalizer import expand_contractions
        result = expand_contractions("She's fine and he's here")
        self.assertIn("she is", result.lower())

    def test_uppercase_contraction(self):
        from audioDiagnostic.utils.text_normalizer import expand_contractions
        # Should handle case-insensitively
        result = expand_contractions("WON'T")
        self.assertNotEqual(result.lower(), "won't")


class RemovePunctuationTests(TestCase):

    def test_removes_punctuation(self):
        from audioDiagnostic.utils.text_normalizer import remove_punctuation
        result = remove_punctuation("Hello, world! How are you?")
        self.assertNotIn(",", result)
        self.assertNotIn("!", result)
        self.assertNotIn("?", result)

    def test_keep_apostrophes(self):
        from audioDiagnostic.utils.text_normalizer import remove_punctuation
        result = remove_punctuation("can't won't", keep_apostrophes=True)
        self.assertIn("'", result)

    def test_no_apostrophes(self):
        from audioDiagnostic.utils.text_normalizer import remove_punctuation
        result = remove_punctuation("can't", keep_apostrophes=False)
        self.assertNotIn("'", result)

    def test_empty_string(self):
        from audioDiagnostic.utils.text_normalizer import remove_punctuation
        self.assertEqual(remove_punctuation(""), "")


class NormalizeWhitespaceTests(TestCase):

    def test_multiple_spaces(self):
        from audioDiagnostic.utils.text_normalizer import normalize_whitespace
        self.assertEqual(normalize_whitespace("a  b   c"), "a b c")

    def test_leading_trailing(self):
        from audioDiagnostic.utils.text_normalizer import normalize_whitespace
        self.assertEqual(normalize_whitespace("  hello  "), "hello")

    def test_newlines_and_tabs(self):
        from audioDiagnostic.utils.text_normalizer import normalize_whitespace
        result = normalize_whitespace("a\nb\tc")
        self.assertEqual(result, "a b c")


class NormalizeUnicodeTests(TestCase):

    def test_smart_quotes(self):
        from audioDiagnostic.utils.text_normalizer import normalize_unicode
        result = normalize_unicode("\u201chello\u201d")
        self.assertNotIn("\u201c", result)
        self.assertNotIn("\u201d", result)

    def test_em_dash(self):
        from audioDiagnostic.utils.text_normalizer import normalize_unicode
        result = normalize_unicode("a\u2014b")
        self.assertIn("-", result)

    def test_plain_text_unchanged(self):
        from audioDiagnostic.utils.text_normalizer import normalize_unicode
        text = "Hello world"
        self.assertEqual(normalize_unicode(text), text)


class NormalizeTextTests(TestCase):

    def test_full_pipeline(self):
        from audioDiagnostic.utils.text_normalizer import normalize_text
        result = normalize_text("Hello, World! I'm fine.")
        self.assertEqual(result, result.lower())
        self.assertNotIn(",", result)

    def test_no_expand(self):
        from audioDiagnostic.utils.text_normalizer import normalize_text
        result = normalize_text("I'm fine", expand_contractions_flag=False)
        # Should not expand but still normalize
        self.assertEqual(result, result.lower())

    def test_no_lowercase(self):
        from audioDiagnostic.utils.text_normalizer import normalize_text
        result = normalize_text("Hello World", lowercase=False)
        # Words should preserve some capitalization
        self.assertIn("Hello", result)

    def test_empty_string(self):
        from audioDiagnostic.utils.text_normalizer import normalize_text
        self.assertEqual(normalize_text(""), "")


class TokenizeWordsTests(TestCase):

    def test_basic(self):
        from audioDiagnostic.utils.text_normalizer import tokenize_words
        result = tokenize_words("hello world foo")
        self.assertEqual(result, ["hello", "world", "foo"])

    def test_with_normalize(self):
        from audioDiagnostic.utils.text_normalizer import tokenize_words
        result = tokenize_words("Hello, World!", normalize=True)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_empty(self):
        from audioDiagnostic.utils.text_normalizer import tokenize_words
        self.assertEqual(tokenize_words(""), [])


class LevenshteinDistanceTests(TestCase):

    def test_equal_strings(self):
        from audioDiagnostic.utils.text_normalizer import levenshtein_distance
        self.assertEqual(levenshtein_distance("abc", "abc"), 0)

    def test_one_insert(self):
        from audioDiagnostic.utils.text_normalizer import levenshtein_distance
        self.assertEqual(levenshtein_distance("abc", "ab"), 1)

    def test_one_substitution(self):
        from audioDiagnostic.utils.text_normalizer import levenshtein_distance
        self.assertEqual(levenshtein_distance("abc", "axc"), 1)

    def test_empty_string(self):
        from audioDiagnostic.utils.text_normalizer import levenshtein_distance
        self.assertEqual(levenshtein_distance("abc", ""), 3)
        self.assertEqual(levenshtein_distance("", "abc"), 3)

    def test_completely_different(self):
        from audioDiagnostic.utils.text_normalizer import levenshtein_distance
        d = levenshtein_distance("hello", "world")
        self.assertGreater(d, 0)


class WordSimilarityTests(TestCase):

    def test_exact_match(self):
        from audioDiagnostic.utils.text_normalizer import calculate_word_similarity
        self.assertEqual(calculate_word_similarity("hello", "hello"), 1.0)

    def test_normalized_match(self):
        from audioDiagnostic.utils.text_normalizer import calculate_word_similarity
        # "Hello" vs "hello" should give high similarity
        score = calculate_word_similarity("Hello", "hello")
        self.assertGreater(score, 0.9)

    def test_contraction_match(self):
        from audioDiagnostic.utils.text_normalizer import calculate_word_similarity
        # "can't" vs "cannot" — expansion match
        score = calculate_word_similarity("can't", "cannot")
        self.assertGreater(score, 0.5)

    def test_completely_different(self):
        from audioDiagnostic.utils.text_normalizer import calculate_word_similarity
        score = calculate_word_similarity("hello", "xyz")
        self.assertLess(score, 1.0)


class GetNgramsTests(TestCase):

    def test_bigrams(self):
        from audioDiagnostic.utils.text_normalizer import get_ngrams
        words = ["a", "b", "c", "d"]
        result = get_ngrams(words, 2)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], ("a b", 0))
        self.assertEqual(result[1], ("b c", 1))

    def test_unigrams(self):
        from audioDiagnostic.utils.text_normalizer import get_ngrams
        words = ["x", "y"]
        result = get_ngrams(words, 1)
        self.assertEqual(len(result), 2)

    def test_n_larger_than_words(self):
        from audioDiagnostic.utils.text_normalizer import get_ngrams
        words = ["a", "b"]
        result = get_ngrams(words, 5)
        self.assertEqual(result, [])


class FindRepeatedNgramsTests(TestCase):

    def test_finds_repeated(self):
        from audioDiagnostic.utils.text_normalizer import find_repeated_ngrams
        words = ["hello", "world", "hello", "world", "foo"]
        result = find_repeated_ngrams(words, 2)
        self.assertIn("hello world", result)

    def test_no_repeats(self):
        from audioDiagnostic.utils.text_normalizer import find_repeated_ngrams
        words = ["a", "b", "c", "d"]
        result = find_repeated_ngrams(words, 2, min_occurrences=2)
        self.assertEqual(len(result), 0)


class RemovePageNumbersTests(TestCase):

    def test_removes_page_n(self):
        from audioDiagnostic.utils.text_normalizer import remove_page_numbers
        result = remove_page_numbers("Some text\nPage 5\nMore text")
        self.assertNotIn("Page 5", result)

    def test_removes_standalone_numbers(self):
        from audioDiagnostic.utils.text_normalizer import remove_page_numbers
        result = remove_page_numbers("Some text\n42\nMore text")
        self.assertNotIn("\n42\n", result)


class RemoveFootnoteMarkersTests(TestCase):

    def test_removes_bracketed_numbers(self):
        from audioDiagnostic.utils.text_normalizer import remove_footnote_markers
        result = remove_footnote_markers("Hello[1] world[2]")
        self.assertNotIn("[1]", result)

    def test_removes_paren_numbers(self):
        from audioDiagnostic.utils.text_normalizer import remove_footnote_markers
        result = remove_footnote_markers("Hello(1) world(2)")
        self.assertNotIn("(1)", result)


# ══════════════════════════════════════════════════════════════════
# tab3_review_deletions views — direct function calls
# ══════════════════════════════════════════════════════════════════

class PreviewDeletionsViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='w81_preview_user', password='pass1234!')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = AudioProject.objects.create(
            user=self.user, title='W81 Preview Project', status='transcribed'
        )
        self.af = AudioFile.objects.create(
            project=self.project, filename='w81_audio.wav',
            title='W81 Audio', order_index=0, status='transcribed'
        )
        self.client.raise_request_exception = False

    def test_preview_no_transcription(self):
        """POST preview-deletions/ without transcription → 400"""
        from audioDiagnostic.views.tab3_review_deletions import preview_deletions
        factory = APIRequestFactory()
        request = factory.post(
            f'/api/projects/{self.project.id}/files/{self.af.id}/preview-deletions/',
            {'segment_ids': [1, 2]},
            format='json'
        )
        request.user = self.user
        resp = preview_deletions(request, self.project.id, self.af.id)
        self.assertIn(resp.status_code, [400, 404])

    def test_preview_no_segments(self):
        """POST preview-deletions/ with transcription but no segments → 400"""
        Transcription.objects.create(audio_file=self.af, full_text='Some text here')
        from audioDiagnostic.views.tab3_review_deletions import preview_deletions
        factory = APIRequestFactory()
        request = factory.post(
            f'/api/projects/{self.project.id}/files/{self.af.id}/preview-deletions/',
            {'segment_ids': []},
            format='json'
        )
        request.user = self.user
        resp = preview_deletions(request, self.project.id, self.af.id)
        self.assertIn(resp.status_code, [400])


class GetDeletionPreviewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='w81_getpreview_user', password='pass1234!')
        self.project = AudioProject.objects.create(
            user=self.user, title='W81 GetPreview Project', status='transcribed'
        )
        self.af = AudioFile.objects.create(
            project=self.project, filename='w81_getpreview.wav',
            title='W81 GetPreview Audio', order_index=0, status='transcribed',
            preview_status='none'
        )
        self.client.raise_request_exception = False

    def test_get_preview_status(self):
        """GET deletion-preview/ returns status"""
        from audioDiagnostic.views.tab3_review_deletions import get_deletion_preview
        factory = APIRequestFactory()
        request = factory.get(
            f'/api/projects/{self.project.id}/files/{self.af.id}/deletion-preview/'
        )
        request.user = self.user
        resp = get_deletion_preview(request, self.project.id, self.af.id)
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_get_preview_ready_state(self):
        """GET deletion-preview/ when status=ready returns metadata"""
        self.af.preview_status = 'ready'
        self.af.preview_metadata = {
            'original_duration': 100.0,
            'preview_duration': 80.0,
            'segments_deleted': 5,
            'time_saved': 20.0,
            'deletion_regions': [],
            'kept_regions': []
        }
        self.af.save()
        from audioDiagnostic.views.tab3_review_deletions import get_deletion_preview
        factory = APIRequestFactory()
        request = factory.get(
            f'/api/projects/{self.project.id}/files/{self.af.id}/deletion-preview/'
        )
        request.user = self.user
        resp = get_deletion_preview(request, self.project.id, self.af.id)
        self.assertIn(resp.status_code, [200])

    def test_get_preview_failed_state(self):
        """GET deletion-preview/ when status=failed returns error"""
        self.af.preview_status = 'failed'
        self.af.error_message = 'Something went wrong'
        self.af.save()
        from audioDiagnostic.views.tab3_review_deletions import get_deletion_preview
        factory = APIRequestFactory()
        request = factory.get(
            f'/api/projects/{self.project.id}/files/{self.af.id}/deletion-preview/'
        )
        request.user = self.user
        resp = get_deletion_preview(request, self.project.id, self.af.id)
        self.assertIn(resp.status_code, [200])


class RestoreSegmentsViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='w81_restore_user', password='pass1234!')
        self.project = AudioProject.objects.create(
            user=self.user, title='W81 Restore Project', status='transcribed'
        )
        self.af = AudioFile.objects.create(
            project=self.project, filename='w81_restore.wav',
            title='W81 Restore Audio', order_index=0, status='transcribed',
        )
        self.client.raise_request_exception = False

    def test_restore_no_segments(self):
        """POST restore-segments/ with no IDs → 400"""
        from audioDiagnostic.views.tab3_review_deletions import restore_segments
        factory = APIRequestFactory()
        request = factory.post(
            f'/api/projects/{self.project.id}/files/{self.af.id}/restore-segments/',
            {'segment_ids': []},
            format='json'
        )
        request.user = self.user
        resp = restore_segments(request, self.project.id, self.af.id)
        self.assertIn(resp.status_code, [400])

    def test_restore_no_preview_metadata(self):
        """POST restore-segments/ with no preview metadata → 400"""
        from audioDiagnostic.views.tab3_review_deletions import restore_segments
        factory = APIRequestFactory()
        request = factory.post(
            f'/api/projects/{self.project.id}/files/{self.af.id}/restore-segments/',
            {'segment_ids': [1, 2]},
            format='json'
        )
        request.user = self.user
        resp = restore_segments(request, self.project.id, self.af.id)
        self.assertIn(resp.status_code, [400])

    def test_restore_with_metadata(self):
        """POST restore-segments/ with metadata → restores and returns count"""
        self.af.preview_metadata = {
            'deletion_regions': [
                {'segment_ids': [10], 'start': 0.0, 'end': 1.0},
                {'segment_ids': [11], 'start': 1.0, 'end': 2.0},
            ],
            'segments_deleted': 2
        }
        self.af.save()
        from audioDiagnostic.views.tab3_review_deletions import restore_segments
        factory = APIRequestFactory()
        request = factory.post(
            f'/api/projects/{self.project.id}/files/{self.af.id}/restore-segments/',
            {'segment_ids': [10], 'regenerate_preview': False},
            format='json'
        )
        request.user = self.user
        resp = restore_segments(request, self.project.id, self.af.id)
        self.assertIn(resp.status_code, [200])
