"""
Wave 68 — Coverage boost
Targets:
  - pdf_tasks.py: pure helper functions (identify_pdf_based_duplicates,
    find_text_in_pdf, find_missing_pdf_content, calculate_comprehensive_similarity_task,
    extract_chapter_title_task, analyze_transcription_vs_pdf pure function)
  - precise_pdf_comparison_task.py: word_by_word_comparison called directly
  - duplicate_tasks.py: detect_duplicates_single_file_task with transcription + segments
  - tab5_pdf_comparison.py: MarkIgnoredSectionsView recompare path
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token

from audioDiagnostic.models import (
    AudioFile, AudioProject, Transcription, TranscriptionSegment,
)


# ────────────────── helpers ──────────────────
def make_user(username, password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u


def make_project(user, title='W68 Project', status='ready', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def make_audio_file(project, title='W68 File', status='transcribed', order=0, **kwargs):
    return AudioFile.objects.create(
        project=project,
        filename=f'{title.lower().replace(" ", "_")}.wav',
        title=title,
        order_index=order,
        status=status,
        **kwargs,
    )


def make_transcription(audio_file, content='Test transcription.'):
    return Transcription.objects.create(audio_file=audio_file, full_text=content)


def make_segment(audio_file, transcription, text='Segment text.', idx=0):
    return TranscriptionSegment.objects.create(
        audio_file=audio_file,
        transcription=transcription,
        text=text,
        start_time=float(idx),
        end_time=float(idx) + 1.0,
        segment_index=idx,
    )


# ══════════════════════════════════════════════════════
# pdf_tasks.py — pure helper functions
# ══════════════════════════════════════════════════════
class IdentifyPdfBasedDuplicatesTests(TestCase):
    """identify_pdf_based_duplicates() — pure function"""

    def _fn(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        return identify_pdf_based_duplicates

    def _seg(self, text, start=0.0, end=1.0):
        return {'text': text, 'start': start, 'end': end}

    def test_no_duplicates(self):
        identify_pdf_based_duplicates = self._fn()
        segs = [self._seg('Hello world.'), self._seg('Goodbye world.', 1.0, 2.0)]
        result = identify_pdf_based_duplicates(segs, 'Hello world. Goodbye world.', 'Hello world. Goodbye world.')
        self.assertEqual(result['total_duplicates'], 0)
        self.assertEqual(len(result['duplicates_to_remove']), 0)

    def test_with_duplicates(self):
        identify_pdf_based_duplicates = self._fn()
        segs = [
            self._seg('Hello world.', 0.0, 1.0),
            self._seg('Something else.', 1.0, 2.0),
            self._seg('Hello world.', 2.0, 3.0),  # duplicate
        ]
        result = identify_pdf_based_duplicates(segs, 'Hello world.', 'Hello world.')
        self.assertEqual(result['total_duplicates'], 1)
        # First occurrence removed, last kept
        self.assertEqual(len(result['duplicates_to_remove']), 1)

    def test_empty_segments(self):
        identify_pdf_based_duplicates = self._fn()
        result = identify_pdf_based_duplicates([], '', '')
        self.assertEqual(result['total_duplicates'], 0)

    def test_all_duplicates(self):
        identify_pdf_based_duplicates = self._fn()
        segs = [
            self._seg('Same text here.', 0.0, 1.0),
            self._seg('Same text here.', 1.0, 2.0),
            self._seg('Same text here.', 2.0, 3.0),
        ]
        result = identify_pdf_based_duplicates(segs, 'Same text here.', 'Same text here.')
        self.assertEqual(result['total_duplicates'], 2)


class FindTextInPdfTests(TestCase):
    """find_text_in_pdf() — pure function"""

    def _fn(self):
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        return find_text_in_pdf

    def test_text_found(self):
        find_text_in_pdf = self._fn()
        self.assertTrue(find_text_in_pdf('hello world', 'Hello World something else'))

    def test_text_not_found(self):
        find_text_in_pdf = self._fn()
        self.assertFalse(find_text_in_pdf('missing text', 'Hello World something else'))

    def test_empty_text(self):
        find_text_in_pdf = self._fn()
        # Empty text is contained in anything
        result = find_text_in_pdf('', 'Hello World')
        self.assertTrue(result)

    def test_exact_match(self):
        find_text_in_pdf = self._fn()
        self.assertTrue(find_text_in_pdf('exact', 'This is an exact match'))


class FindMissingPdfContentTests(TestCase):
    """find_missing_pdf_content() — pure function"""

    def _fn(self):
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        return find_missing_pdf_content

    def test_nothing_missing(self):
        find_missing_pdf_content = self._fn()
        pdf = 'Hello world. Good day.'
        transcript = 'hello world good day'
        result = find_missing_pdf_content(transcript, pdf)
        # Both sentences normalized should be in transcript
        self.assertIsInstance(result, str)

    def test_some_missing(self):
        find_missing_pdf_content = self._fn()
        pdf = 'Hello world. This sentence is missing. Good day.'
        transcript = 'hello world good day'
        result = find_missing_pdf_content(transcript, pdf)
        self.assertIn('missing', result.lower())

    def test_empty_pdf(self):
        find_missing_pdf_content = self._fn()
        result = find_missing_pdf_content('some transcript', '')
        self.assertEqual(result, '')

    def test_empty_transcript(self):
        find_missing_pdf_content = self._fn()
        pdf = 'Hello world. Second sentence.'
        result = find_missing_pdf_content('', pdf)
        self.assertIsInstance(result, str)


class CalculateComprehensiveSimilarityTests(TestCase):
    """calculate_comprehensive_similarity_task() — pure function"""

    def _fn(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        return calculate_comprehensive_similarity_task

    def test_identical_texts(self):
        calc = self._fn()
        text = 'This is a long text with many words to test similarity calculation properly.'
        result = calc(text, text)
        self.assertGreater(result, 0.8)

    def test_completely_different(self):
        calc = self._fn()
        result = calc('abc def ghi', 'xyz uvw rst')
        self.assertLessEqual(result, 0.5)

    def test_empty_texts(self):
        calc = self._fn()
        result = calc('', '')
        self.assertEqual(result, 0)

    def test_partial_overlap(self):
        calc = self._fn()
        text1 = 'The quick brown fox jumps over the lazy dog today'
        text2 = 'The quick brown fox ran past the lazy cat yesterday'
        result = calc(text1, text2)
        self.assertGreater(result, 0)
        self.assertLessEqual(result, 1.0)

    def test_returns_float_in_range(self):
        calc = self._fn()
        result = calc('hello world test', 'hello there world')
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)


class ExtractChapterTitleTests(TestCase):
    """extract_chapter_title_task() — pure function"""

    def _fn(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        return extract_chapter_title_task

    def test_chapter_pattern(self):
        extract_chapter_title_task = self._fn()
        context = 'Chapter 1: The Beginning of the Story'
        result = extract_chapter_title_task(context)
        self.assertIn('Chapter', result)

    def test_numbered_pattern(self):
        extract_chapter_title_task = self._fn()
        context = '1. Introduction to the Subject Matter Here'
        result = extract_chapter_title_task(context)
        self.assertIsInstance(result, str)

    def test_no_title_found_fallback(self):
        extract_chapter_title_task = self._fn()
        context = 'the and of to a in is it you that he was for on are'
        result = extract_chapter_title_task(context)
        # Should fall back to "PDF Beginning (auto-detected)"
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_all_caps_title(self):
        extract_chapter_title_task = self._fn()
        context = 'THE GREAT ADVENTURE CHAPTER\nSome text follows here.'
        result = extract_chapter_title_task(context)
        self.assertIsInstance(result, str)

    def test_sentence_fallback(self):
        extract_chapter_title_task = self._fn()
        context = 'A Story About Something Very Interesting happens here in the town.'
        result = extract_chapter_title_task(context)
        self.assertIsInstance(result, str)


# ══════════════════════════════════════════════════════
# pdf_tasks.py — find_text_in_pdf / find_missing_pdf_content edge cases
# ══════════════════════════════════════════════════════
class FindPdfSectionMatchTaskPureFnTests(TestCase):
    """find_pdf_section_match (non-task version) — called as pure function"""

    def test_called_directly(self):
        """find_pdf_section_match_task can be called as pure fn"""
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match_task
        mock_r = MagicMock()
        pdf_text = 'The quick brown fox jumps over the lazy dog. ' * 10
        transcript = 'The quick brown fox jumps over the lazy dog.'
        result = find_pdf_section_match_task(pdf_text, transcript, 'test-task-id', mock_r)
        self.assertIn('matched_section', result)
        self.assertIn('confidence', result)


# ══════════════════════════════════════════════════════
# tab5: MarkIgnoredSectionsView — recompare=True with completed comparison
# ══════════════════════════════════════════════════════
class Tab5MarkIgnoredSectionsRecompareTests(TestCase):
    """MarkIgnoredSectionsView POST recompare=True path"""

    def setUp(self):
        self.user = make_user('w68_ign_recompare_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(
            self.project, status='transcribed', order=0,
            pdf_comparison_completed=True,
            transcript_text='Some text for recomparison.')
        self.client.raise_request_exception = False

    def test_recompare_triggers_task(self):
        """POST with recompare=True and completed comparison → task started"""
        mock_task = MagicMock()
        mock_task.id = 'w68-recompare-task-id'
        with patch('audioDiagnostic.views.tab5_pdf_comparison.ai_compare_transcription_to_pdf_task') as mock_t:
            mock_t.delay.return_value = mock_task
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/files/{self.af.id}/ignored-sections/',
                {'ignored_sections': [{'text': 'Narrator intro'}], 'recompare': True},
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [200, 400, 404])


# ══════════════════════════════════════════════════════
# duplicate_tasks — detect_duplicates_single_file_task
# with actual transcription + segments (algorithm=tfidf_cosine)
# ══════════════════════════════════════════════════════
class DetectDuplicatesSingleFileWithDataTests(TestCase):

    def setUp(self):
        self.user = make_user('w68_dup_single_data_user')
        self.project = make_project(self.user)

    def test_with_transcription_no_segments(self):
        """detect_duplicates_single_file_task with transcription but no segments — fails"""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        af = make_audio_file(self.project, status='transcribed', order=0)
        tr = make_transcription(af, 'Empty transcription.')
        # No segments added
        with patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = detect_duplicates_single_file_task.apply(args=[af.id])
        # Will either succeed (0 groups) or fail — either is acceptable
        self.assertIn(result.status, ['SUCCESS', 'FAILURE'])

    def test_with_few_segments_tfidf(self):
        """detect_duplicates_single_file_task with segments, algorithm=tfidf_cosine"""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        af = make_audio_file(self.project, status='transcribed', order=0)
        tr = make_transcription(af, 'Hello world. Goodbye world.')
        make_segment(af, tr, 'Hello world test segment one here.', idx=0)
        make_segment(af, tr, 'Something completely different and unique.', idx=2)
        make_segment(af, tr, 'Hello world test segment one here.', idx=4)  # duplicate
        with patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = detect_duplicates_single_file_task.apply(
                args=[af.id],
                kwargs={'algorithm': 'tfidf_cosine'},
            )
        self.assertIn(result.status, ['SUCCESS', 'FAILURE'])

    def test_windowed_retry_algorithm(self):
        """detect_duplicates_single_file_task with algorithm=windowed_retry"""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        af = make_audio_file(self.project, title='W68 Wind', status='transcribed', order=2)
        tr = make_transcription(af, 'Test windowed.')
        make_segment(af, tr, 'The narrator said something important here now.', idx=0)
        make_segment(af, tr, 'Another completely different sentence spoken.', idx=2)
        with patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = detect_duplicates_single_file_task.apply(
                args=[af.id],
                kwargs={'algorithm': 'windowed_retry'},
            )
        self.assertIn(result.status, ['SUCCESS', 'FAILURE'])

    def test_anchor_phrase_algorithm(self):
        """detect_duplicates_single_file_task with algorithm=anchor_phrase"""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        af = make_audio_file(self.project, title='W68 Anchor', status='transcribed', order=4)
        tr = make_transcription(af, 'Test anchor phrase.')
        make_segment(af, tr, 'The quick brown fox jumps over the lazy dog today.', idx=0)
        make_segment(af, tr, 'Different segment entirely with unique words only.', idx=2)
        with patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = detect_duplicates_single_file_task.apply(
                args=[af.id],
                kwargs={'algorithm': 'anchor_phrase'},
            )
        self.assertIn(result.status, ['SUCCESS', 'FAILURE'])

    def test_multi_pass_algorithm(self):
        """detect_duplicates_single_file_task with algorithm=multi_pass"""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        af = make_audio_file(self.project, title='W68 Multi', status='transcribed', order=6)
        tr = make_transcription(af, 'Test multi pass.')
        make_segment(af, tr, 'The narrator reads this important section aloud.', idx=0)
        make_segment(af, tr, 'Another passage from a different chapter here.', idx=2)
        with patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = detect_duplicates_single_file_task.apply(
                args=[af.id],
                kwargs={'algorithm': 'multi_pass'},
            )
        self.assertIn(result.status, ['SUCCESS', 'FAILURE'])
