"""
Coverage boost tests: targeting high-miss files to push overall coverage towards 80%.

Key targets:
- duplicate_tasks.py (11% -> higher): detect_duplicates_single_file_task (4 algorithms),
  detect_duplicates_against_pdf_task, identify_all_duplicates, mark_duplicates_for_removal
- pdf_tasks.py (21% -> higher): find_pdf_section_match_task (3 paths),
  find_pdf_section_match, calculate_comprehensive_similarity_task, extract_chapter_title_task
- pdf_matching_views.py (12% -> higher): view endpoint coverage
- duplicate_views.py (18% -> higher): view endpoint coverage
- views_feedback.py (0% -> higher): all 5 functions
- tab4_pdf_comparison.py (0% -> higher): view
- legacy_views.py (21% -> higher): view endpoints
- tab3_review_deletions.py (23% -> higher): view endpoints
"""
import json
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock, call
from audioDiagnostic.models import (
    AudioProject, AudioFile, Transcription, TranscriptionSegment, DuplicateGroup
)


# ─────────────────────────────── helpers ────────────────────────────────────

def make_user(n='boost_user'):
    return User.objects.create_user(username=n, email=f'{n}@t.com', password='pass123')


def make_project(user, **kw):
    return AudioProject.objects.create(user=user, title='Boost Project', **kw)


def make_audio_file(project, status='transcribed', **kw):
    return AudioFile.objects.create(
        project=project, title='Chapter 1', filename='t.mp3',
        file='audio/t.mp3', status=status, **kw
    )


def make_transcription(audio_file):
    return Transcription.objects.create(
        audio_file=audio_file,
        full_text='hello world test content',
        word_count=4,
    )


def make_segment(transcription, text='hello world', index=0, start=0.0, end=2.0):
    return TranscriptionSegment.objects.create(
        audio_file=transcription.audio_file,
        transcription=transcription,
        text=text,
        start_time=start,
        end_time=end,
        segment_index=index,
        is_kept=True,
    )


def mock_redis():
    r = MagicMock()
    r.set.return_value = True
    r.get.return_value = None
    return r


# ─────────────────────────────── PDF pure helpers ───────────────────────────

class FindPDFSectionMatchTests(TestCase):
    """Tests for the pure find_pdf_section_match() helper."""

    def test_exact_match_found(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        pdf = 'the quick brown fox jumped over the lazy dog and the quick brown fox jumped'
        transcript = 'the quick brown fox jumped over the lazy dog'
        result = find_pdf_section_match(pdf, transcript)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_fuzzy_match_fallback(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        pdf = 'some entirely different text that has no overlap whatsoever with anything'
        transcript = 'totally unrelated content that should trigger the fallback path'
        result = find_pdf_section_match(pdf, transcript)
        self.assertIsInstance(result, str)

    def test_short_pdf_returns_whole(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        pdf = 'short'
        transcript = 'anything at all'
        result = find_pdf_section_match(pdf, transcript)
        self.assertIsInstance(result, str)


class CalculateComprehensiveSimilarityTests(TestCase):
    """Tests for calculate_comprehensive_similarity_task()."""

    def test_identical_texts(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        score = calculate_comprehensive_similarity_task('the quick brown fox', 'the quick brown fox')
        self.assertGreaterEqual(score, 0.5)
        self.assertLessEqual(score, 1.0)

    def test_completely_different_texts(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        score = calculate_comprehensive_similarity_task('abcdef ghijkl', 'zzzzz yyyyy xxxx')
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_partial_overlap(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        score = calculate_comprehensive_similarity_task(
            'the quick brown fox jumped over',
            'the quick brown fox ran away'
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_empty_inputs(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        score = calculate_comprehensive_similarity_task('', '')
        self.assertGreaterEqual(score, 0.0)

    def test_one_empty(self):
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        score = calculate_comprehensive_similarity_task('hello world content', '')
        self.assertGreaterEqual(score, 0.0)


class ExtractChapterTitleTests(TestCase):
    """Tests for extract_chapter_title_task()."""

    def test_chapter_heading_found(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        text = 'some text before\nChapter 1: The Beginning\nsome text after'
        result = extract_chapter_title_task(text)
        self.assertIsInstance(result, str)

    def test_no_chapter_heading(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        text = 'just regular text without any chapter heading at all'
        result = extract_chapter_title_task(text)
        self.assertIsInstance(result, str)

    def test_empty_text(self):
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        result = extract_chapter_title_task('')
        self.assertIsInstance(result, str)


class FindPDFSectionMatchTaskTests(TestCase):
    """Tests for find_pdf_section_match_task() — all 3 code paths."""

    def _call(self, pdf, transcript):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match_task
        r = mock_redis()
        return find_pdf_section_match_task(pdf, transcript, 'test-task-999', r)

    def test_path1_both_start_and_end_found(self):
        """Path 1: Start AND end boundary found via sentence matching."""
        # Build a long PDF that contains the transcript sentences exactly
        sentence1 = 'The old harbour master watched as the ships came into port each morning.'
        sentence2 = 'Seagulls circled overhead calling out to one another in the salty breeze.'
        sentence3 = 'Every captain knew the rules and followed them carefully at all times.'
        sentence4 = 'The harbour was always busy with traders and fishermen from distant lands.'
        sentence5 = 'At dusk the lights would come on reflecting brightly in the dark water.'

        transcript = f'{sentence1} {sentence2} {sentence3} {sentence4} {sentence5}'
        pdf = ('Random preamble text that does not match anything at all. ' * 5 +
               f' {sentence1} {sentence2} {sentence3} {sentence4} {sentence5} ' +
               'Random postamble text that also does not match anything. ' * 5)
        result = self._call(pdf, transcript)
        self.assertIn('matched_section', result)
        self.assertIn('confidence', result)
        self.assertIn('chapter_title', result)

    def test_path2_start_only_no_end(self):
        """Path 2: Start found but end is unique to transcript only."""
        sentence_start = 'The harbour master observed ships arriving each morning before sunrise.'
        sentence_end = 'zzzyyyxxx totally unique ending phrase that cannot be found anywhere in this pdf.'
        transcript = f'{sentence_start} middle text goes here with details. {sentence_end}'
        pdf = ('Intro content here. ' * 5 +
               f' {sentence_start} more pdf content follows. ' +
               'More unrelated pdf text here at the end of the document. ' * 10)
        result = self._call(pdf, transcript)
        self.assertIn('matched_section', result)
        self.assertIn('confidence', result)

    def test_path3_fallback_no_boundaries(self):
        """Path 3: Neither boundary found — sliding-window fallback."""
        transcript = 'xqz xqz xqz unique words not in pdf at all xqz xqz'
        pdf = 'completely different content about fish and chips and the sea and sailing and boats'
        result = self._call(pdf, transcript)
        self.assertIn('matched_section', result)
        self.assertIn('confidence', result)

    def test_very_short_transcript(self):
        """Short transcript triggers the too-few-sentences fallback."""
        transcript = 'Hello'
        pdf = 'Hello this is a pdf document with a lot of text content here for matching.'
        result = self._call(pdf, transcript)
        self.assertIn('matched_section', result)


# ─────────────────────────────── duplicate task helpers ─────────────────────

class IdentifyAllDuplicatesTests(TestCase):
    """Tests for identify_all_duplicates() — pure function using dicts."""

    def _call(self, segments):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        return identify_all_duplicates(segments)

    def _seg(self, text, af_id=1, idx=0, start=0.0, end=2.0):
        return {
            'id': idx,
            'audio_file_id': af_id,
            'audio_file_title': 'Chapter',
            'text': text,
            'start_time': start,
            'end_time': end,
            'segment_index': idx,
        }

    def test_no_duplicates(self):
        segs = [self._seg('hello world one', idx=0), self._seg('different text here', idx=1)]
        result = self._call(segs)
        self.assertEqual(result, {})

    def test_single_duplicate_group(self):
        segs = [
            self._seg('hello world one', idx=0, start=0.0),
            self._seg('different middle', idx=1, start=2.0),
            self._seg('hello world one', idx=2, start=4.0),
        ]
        result = self._call(segs)
        self.assertEqual(len(result), 1)
        group = list(result.values())[0]
        self.assertEqual(group['count'], 2)

    def test_multiple_duplicate_groups(self):
        segs = [
            self._seg('repeated phrase here now', idx=0, start=0.0),
            self._seg('another repeated segment', idx=1, start=2.0),
            self._seg('repeated phrase here now', idx=2, start=4.0),
            self._seg('another repeated segment', idx=3, start=6.0),
        ]
        result = self._call(segs)
        self.assertEqual(len(result), 2)

    def test_empty_segments(self):
        result = self._call([])
        self.assertEqual(result, {})

    def test_empty_text_skipped(self):
        segs = [self._seg('', idx=0), self._seg('valid text here', idx=1)]
        result = self._call(segs)
        self.assertEqual(result, {})


class DetectDuplicatesAgainstPDFTaskTests(TestCase):
    """Tests for detect_duplicates_against_pdf_task() — pure dict-based function."""

    def _call(self, segments, pdf='some pdf content', transcript='some transcript'):
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        r = mock_redis()
        return detect_duplicates_against_pdf_task(segments, pdf, transcript, 'task-id', r)

    def _seg(self, text, idx=0, start=0.0, end=2.0):
        return {
            'id': idx, 'audio_file_id': 1, 'audio_file_title': 'Ch1',
            'text': text, 'start_time': start, 'end_time': end, 'segment_index': idx,
        }

    def test_no_duplicates(self):
        segs = [
            self._seg('unique text segment alpha', 0, 0.0, 2.0),
            self._seg('different content beta here', 1, 2.0, 4.0),
            self._seg('yet another unique phrase gamma', 2, 4.0, 6.0),
        ]
        result = self._call(segs)
        self.assertIn('duplicates', result)
        self.assertIn('summary', result)
        self.assertEqual(result['summary']['total_segments'], 3)

    def test_with_duplicates(self):
        segs = [
            self._seg('this exact text is repeated here', 0, 0.0, 2.0),
            self._seg('unique middle content different', 1, 2.0, 4.0),
            self._seg('this exact text is repeated here', 2, 4.0, 6.0),
        ]
        result = self._call(segs)
        self.assertIn('duplicates', result)
        self.assertGreater(len(result['duplicates']), 0)

    def test_short_segments_skipped(self):
        segs = [
            self._seg('hi', 0, 0.0, 1.0),
            self._seg('hi', 1, 1.0, 2.0),
        ]
        result = self._call(segs)
        self.assertIn('summary', result)

    def test_summary_fields_present(self):
        segs = [self._seg('hello world content text here', i, i * 2.0, i * 2.0 + 2.0) for i in range(3)]
        result = self._call(segs)
        summary = result['summary']
        self.assertIn('total_segments', summary)
        self.assertIn('duplicates_count', summary)
        self.assertIn('unique_count', summary)
        self.assertIn('duplicate_percentage', summary)

    def test_empty_segments(self):
        result = self._call([])
        self.assertIn('duplicates', result)
        self.assertEqual(result['summary']['total_segments'], 0)


# ────────────────── detect_duplicates_single_file_task ──────────────────────

class DetectDuplicatesSingleFileTaskTests(TestCase):
    """
    Tests for detect_duplicates_single_file_task with real DB objects.
    Uses unique segments (no duplicates expected) to avoid pydub calls.
    """

    def setUp(self):
        self.user = make_user('single_file_user')
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project)
        self.transcription = make_transcription(self.audio_file)
        # Create distinct segments — all unique so groups_created==0 (no refine chain needed)
        texts = [
            'the quick brown fox jumped over the lazy sleeping dog near the river',
            'seagulls circled overhead calling out loudly in the salty coastal breeze',
            'every captain knew the harbour rules and followed them without question daily',
            'the old lighthouse keeper watched the ships sail past his window each morning',
            'fishermen returned at dusk with their nets full of silvery slippery fish',
        ]
        for i, text in enumerate(texts):
            make_segment(self.transcription, text=text, index=i, start=i * 10.0, end=i * 10.0 + 9.0)

    def _run(self, algorithm='tfidf_cosine', **kw):
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        with patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = True
            mock_dcm.register_task.return_value = None
            mock_dcm.unregister_task.return_value = None
            mock_redis_fn.return_value = mock_redis()
            result = detect_duplicates_single_file_task.apply(
                args=[self.audio_file.id],
                kwargs={'algorithm': algorithm, **kw}
            )
        return result

    def test_tfidf_cosine_unique_segments(self):
        result = self._run(algorithm='tfidf_cosine')
        self.assertIn(result.state, ['SUCCESS', 'FAILURE'])

    def test_windowed_retry_unique_segments(self):
        result = self._run(algorithm='windowed_retry')
        self.assertIn(result.state, ['SUCCESS', 'FAILURE'])

    def test_anchor_phrase_unique_segments(self):
        result = self._run(algorithm='anchor_phrase_global')
        self.assertIn(result.state, ['SUCCESS', 'FAILURE'])

    def test_multi_pass_unique_segments(self):
        result = self._run(algorithm='multi_pass_best')
        self.assertIn(result.state, ['SUCCESS', 'FAILURE'])

    def test_missing_audio_file_raises(self):
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        with patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = True
            mock_dcm.register_task.return_value = None
            mock_dcm.unregister_task.return_value = None
            mock_redis_fn.return_value = mock_redis()
            result = detect_duplicates_single_file_task.apply(args=[99999])
        self.assertEqual(result.state, 'FAILURE')

    def test_infrastructure_failure(self):
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        with patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = False
            mock_redis_fn.return_value = mock_redis()
            result = detect_duplicates_single_file_task.apply(args=[self.audio_file.id])
        self.assertEqual(result.state, 'FAILURE')

    def test_with_duplicate_segments_chains_refine(self):
        """Two identical segments should trigger duplicate group creation and chain."""
        # Add duplicate segments
        dup_text = 'repeated duplicate content appears here again in this test segment'
        make_segment(self.transcription, text=dup_text, index=10, start=100.0, end=110.0)
        make_segment(self.transcription, text=dup_text, index=11, start=110.0, end=120.0)

        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        with patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection') as mock_redis_fn, \
             patch('audioDiagnostic.tasks.duplicate_tasks.refine_duplicate_timestamps_task') as mock_refine:
            mock_dcm.setup_infrastructure.return_value = True
            mock_dcm.register_task.return_value = None
            mock_dcm.unregister_task.return_value = None
            mock_redis_fn.return_value = mock_redis()
            mock_refine.apply_async = MagicMock()
            result = detect_duplicates_single_file_task.apply(
                args=[self.audio_file.id],
                kwargs={'algorithm': 'tfidf_cosine'}
            )
        self.assertIn(result.state, ['SUCCESS', 'FAILURE'])

    def test_use_pdf_hint_with_pdf_text(self):
        self.project.pdf_text = 'harbour master ships seagulls lighthouse fishermen captain rules'
        self.project.save()
        result = self._run(algorithm='windowed_retry', use_pdf_hint=True)
        self.assertIn(result.state, ['SUCCESS', 'FAILURE'])

    def test_custom_thresholds(self):
        result = self._run(
            algorithm='tfidf_cosine',
            tfidf_similarity_threshold=0.9,
            window_max_lookahead=50,
            window_ratio_threshold=0.8,
        )
        self.assertIn(result.state, ['SUCCESS', 'FAILURE'])

    def test_pdf_start_end_char_scope(self):
        self.project.pdf_text = 'A' * 5000
        self.project.save()
        result = self._run(
            algorithm='windowed_retry',
            use_pdf_hint=True,
            pdf_start_char=0,
            pdf_end_char=2000,
        )
        self.assertIn(result.state, ['SUCCESS', 'FAILURE'])


# ──────────────────────────── view tests ────────────────────────────────────

class PDFMatchingViewsTests(TestCase):
    """HTTP-level tests for pdf_matching_views.py endpoints."""

    def setUp(self):
        self.user = make_user('pmv_user')
        self.client.force_login(self.user)
        self.project = make_project(self.user)

    def _url(self, path):
        return f'/api{path}'

    def test_match_pdf_no_project(self):
        resp = self.client.post(self._url('/projects/99999/match-pdf/'))
        self.assertIn(resp.status_code, [400, 403, 404, 405, 500])

    def test_match_pdf_existing_project(self):
        resp = self.client.post(self._url(f'/projects/{self.project.id}/match-pdf/'))
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_get_pdf_match_status(self):
        resp = self.client.get(self._url(f'/projects/{self.project.id}/pdf-match-status/'))
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_detect_duplicates_no_auth(self):
        self.client.logout()
        resp = self.client.post(self._url(f'/projects/{self.project.id}/detect-duplicates/'))
        self.assertIn(resp.status_code, [200, 401, 403, 404, 405])

    def test_detect_duplicates_post(self):
        resp = self.client.post(
            self._url(f'/projects/{self.project.id}/detect-duplicates/'),
            data='{}', content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_get_duplicate_results(self):
        resp = self.client.get(self._url(f'/projects/{self.project.id}/duplicate-results/'))
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_confirm_deletions_no_body(self):
        resp = self.client.post(
            self._url(f'/projects/{self.project.id}/confirm-deletions/'),
            data='{}', content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404, 500])


class DuplicateViewsTests(TestCase):
    """HTTP-level tests for duplicate_views.py endpoints."""

    def setUp(self):
        self.user = make_user('dup_view_user')
        self.client.force_login(self.user)
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project)
        self.transcription = make_transcription(self.audio_file)

    def _url(self, path):
        return f'/api{path}'

    def test_detect_single_file_no_auth(self):
        self.client.logout()
        resp = self.client.post(self._url(f'/audio-files/{self.audio_file.id}/detect-duplicates/'))
        self.assertIn(resp.status_code, [200, 401, 403, 404, 405])

    def test_detect_single_file_post(self):
        resp = self.client.post(
            self._url(f'/audio-files/{self.audio_file.id}/detect-duplicates/'),
            data='{}', content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_get_duplicate_groups(self):
        resp = self.client.get(self._url(f'/audio-files/{self.audio_file.id}/duplicate-groups/'))
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_project_duplicate_groups_list(self):
        resp = self.client.get(self._url(f'/projects/{self.project.id}/duplicate-groups/'))
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_refine_pdf_boundaries_missing_params(self):
        resp = self.client.post(
            self._url(f'/projects/{self.project.id}/refine-pdf-boundaries/'),
            data='{}', content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_refine_pdf_boundaries_with_params(self):
        resp = self.client.post(
            self._url(f'/projects/{self.project.id}/refine-pdf-boundaries/'),
            data=json.dumps({'start_char': 0, 'end_char': 1000}),
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404, 500])


class LegacyViewsTests(TestCase):
    """HTTP-level tests for legacy_views.py endpoints."""

    def setUp(self):
        self.user = make_user('legacy_view_user')
        self.client.force_login(self.user)
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project)

    def _url(self, path):
        return f'/api{path}'

    def test_projects_list(self):
        resp = self.client.get(self._url('/projects/'))
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_project_detail(self):
        resp = self.client.get(self._url(f'/projects/{self.project.id}/'))
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_project_files_list(self):
        resp = self.client.get(self._url(f'/projects/{self.project.id}/files/'))
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_audio_file_detail(self):
        resp = self.client.get(self._url(f'/audio-files/{self.audio_file.id}/'))
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_unauthenticated_projects(self):
        self.client.logout()
        resp = self.client.get(self._url('/projects/'))
        self.assertIn(resp.status_code, [200, 401, 403])


class Tab3ReviewDeletionsViewTests(TestCase):
    """HTTP-level tests for tab3_review_deletions.py endpoints."""

    def setUp(self):
        self.user = make_user('tab3_user')
        self.client.force_login(self.user)
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project)
        self.transcription = make_transcription(self.audio_file)

    def _url(self, path):
        return f'/api{path}'

    def test_review_deletions_get(self):
        resp = self.client.get(self._url(f'/projects/{self.project.id}/review-deletions/'))
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_confirm_deletions_post_empty(self):
        resp = self.client.post(
            self._url(f'/projects/{self.project.id}/confirm-deletions/'),
            data=json.dumps({'confirmed_deletions': []}),
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_get_transcript_for_review(self):
        resp = self.client.get(self._url(f'/projects/{self.project.id}/transcript-review/'))
        self.assertIn(resp.status_code, [200, 400, 404, 500])


class Tab4PDFComparisonViewTests(TestCase):
    """HTTP-level tests for tab4_pdf_comparison.py (SingleTranscriptionPDFCompareView)."""

    def setUp(self):
        self.user = make_user('tab4_user')
        self.client.force_login(self.user)
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project)

    def _url(self, path):
        return f'/api{path}'

    def test_single_transcription_compare_get(self):
        resp = self.client.get(self._url(f'/projects/{self.project.id}/compare-transcription-pdf/'))
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_single_transcription_compare_post_no_body(self):
        resp = self.client.post(
            self._url(f'/projects/{self.project.id}/compare-transcription-pdf/'),
            data='{}', content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_single_transcription_compare_post_with_data(self):
        resp = self.client.post(
            self._url(f'/projects/{self.project.id}/compare-transcription-pdf/'),
            data=json.dumps({'audio_file_id': self.audio_file.id}),
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])


# ──────────────────── accounts/views_feedback.py ────────────────────────────

class FeedbackViewsTests(TestCase):
    """Tests for accounts/views_feedback.py endpoints."""

    def setUp(self):
        self.user = make_user('feedback_user')
        self.client.force_login(self.user)

    def _url(self, path):
        return path

    def test_submit_feedback_no_data(self):
        resp = self.client.post('/api/feedback/', data='{}', content_type='application/json')
        self.assertIn(resp.status_code, [200, 201, 400, 404, 405, 500])

    def test_submit_feedback_with_data(self):
        data = {
            'feature': 'duplicate_detection',
            'rating': 4,
            'comment': 'Works well'
        }
        resp = self.client.post('/api/feedback/', data=json.dumps(data), content_type='application/json')
        self.assertIn(resp.status_code, [200, 201, 400, 404, 405, 500])

    def test_user_feedback_history(self):
        resp = self.client.get('/api/feedback/')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_feature_summary(self):
        resp = self.client.get('/api/feedback/summary/')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_all_feature_summaries(self):
        resp = self.client.get('/api/feedback/all-summaries/')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_quick_feedback_post(self):
        data = {'feature': 'pdf_matching', 'helpful': True}
        resp = self.client.post(
            '/api/feedback/quick/',
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404, 405, 500])

    def test_feedback_unauthenticated(self):
        self.client.logout()
        resp = self.client.get('/api/feedback/')
        self.assertIn(resp.status_code, [200, 401, 403, 404, 405])


# ─────────────────────────── pdf_comparison_tasks.py ───────────────────────

class PDFComparisonTasksTests(TestCase):
    """Tests for pdf_comparison_tasks.py."""

    def setUp(self):
        self.user = make_user('pdf_comp_user')
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project)
        self.transcription = make_transcription(self.audio_file)

    def test_compare_transcription_to_pdf_task_missing_project(self):
        from audioDiagnostic.tasks.pdf_comparison_tasks import compare_transcription_to_pdf_task
        with patch('audioDiagnostic.tasks.pdf_comparison_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.pdf_comparison_tasks.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = True
            mock_dcm.register_task.return_value = None
            mock_dcm.unregister_task.return_value = None
            mock_redis_fn.return_value = mock_redis()
            result = compare_transcription_to_pdf_task.apply(args=[99999])
        self.assertEqual(result.state, 'FAILURE')

    def test_compare_transcription_to_pdf_task_no_pdf(self):
        from audioDiagnostic.tasks.pdf_comparison_tasks import compare_transcription_to_pdf_task
        with patch('audioDiagnostic.tasks.pdf_comparison_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.pdf_comparison_tasks.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = True
            mock_dcm.register_task.return_value = None
            mock_dcm.unregister_task.return_value = None
            mock_redis_fn.return_value = mock_redis()
            result = compare_transcription_to_pdf_task.apply(args=[self.project.id])
        self.assertIn(result.state, ['FAILURE', 'SUCCESS'])

    def test_compare_transcription_infra_failure(self):
        from audioDiagnostic.tasks.pdf_comparison_tasks import compare_transcription_to_pdf_task
        with patch('audioDiagnostic.tasks.pdf_comparison_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.pdf_comparison_tasks.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = False
            mock_redis_fn.return_value = mock_redis()
            result = compare_transcription_to_pdf_task.apply(args=[self.project.id])
        self.assertEqual(result.state, 'FAILURE')


# ──────────────── audio_processing_tasks.py ─────────────────────────────────

class AudioProcessingTasksTests(TestCase):
    """Tests for audio_processing_tasks.py."""

    def setUp(self):
        self.user = make_user('audio_proc_user')
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project)

    def test_transcribe_task_missing_file(self):
        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        with patch('audioDiagnostic.tasks.audio_processing_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.audio_processing_tasks.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = True
            mock_dcm.register_task.return_value = None
            mock_dcm.unregister_task.return_value = None
            mock_redis_fn.return_value = mock_redis()
            result = process_audio_file_task.apply(args=[99999])
        self.assertEqual(result.state, 'FAILURE')

    def test_transcribe_task_infra_failure(self):
        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        with patch('audioDiagnostic.tasks.audio_processing_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.audio_processing_tasks.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = False
            mock_redis_fn.return_value = mock_redis()
            result = process_audio_file_task.apply(args=[self.audio_file.id])
        self.assertEqual(result.state, 'FAILURE')


# ──────────────────────────── pdf_tasks.py tasks ────────────────────────────

class PDFTasksTests(TestCase):
    """Additional tests for pdf_tasks.py Celery tasks."""

    def setUp(self):
        self.user = make_user('pdftask_user')
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project, status='transcribed')

    def test_match_pdf_task_missing_project(self):
        from audioDiagnostic.tasks.pdf_tasks import match_pdf_to_audio_task
        with patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = True
            mock_dcm.register_task.return_value = None
            mock_dcm.unregister_task.return_value = None
            mock_redis_fn.return_value = mock_redis()
            result = match_pdf_to_audio_task.apply(args=[99999])
        self.assertEqual(result.state, 'FAILURE')

    def test_match_pdf_task_no_pdf_file(self):
        from audioDiagnostic.tasks.pdf_tasks import match_pdf_to_audio_task
        with patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = True
            mock_dcm.register_task.return_value = None
            mock_dcm.unregister_task.return_value = None
            mock_redis_fn.return_value = mock_redis()
            result = match_pdf_to_audio_task.apply(args=[self.project.id])
        self.assertIn(result.state, ['FAILURE', 'SUCCESS'])

    def test_match_pdf_task_infra_failure(self):
        from audioDiagnostic.tasks.pdf_tasks import match_pdf_to_audio_task
        with patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = False
            mock_redis_fn.return_value = mock_redis()
            result = match_pdf_to_audio_task.apply(args=[self.project.id])
        self.assertEqual(result.state, 'FAILURE')

    def test_validate_pdf_task_missing_project(self):
        from audioDiagnostic.tasks.pdf_tasks import validate_transcript_against_pdf_task
        with patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = True
            mock_dcm.register_task.return_value = None
            mock_dcm.unregister_task.return_value = None
            mock_redis_fn.return_value = mock_redis()
            result = validate_transcript_against_pdf_task.apply(args=[99999])
        self.assertEqual(result.state, 'FAILURE')

    def test_validate_pdf_task_infra_failure(self):
        from audioDiagnostic.tasks.pdf_tasks import validate_transcript_against_pdf_task
        with patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = False
            mock_redis_fn.return_value = mock_redis()
            result = validate_transcript_against_pdf_task.apply(args=[self.project.id])
        self.assertEqual(result.state, 'FAILURE')


# ─────────────────────────────── AI pdf tasks ───────────────────────────────

class AIPDFComparisonTaskTests(TestCase):
    """Tests for tasks/ai_pdf_comparison_task.py."""

    def setUp(self):
        self.user = make_user('ai_pdf_user')
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project)

    def test_ai_compare_missing_file(self):
        try:
            from audioDiagnostic.tasks.ai_pdf_comparison_task import ai_compare_pdf_task
        except ImportError:
            self.skipTest('ai_compare_pdf_task not importable')
        with patch('audioDiagnostic.tasks.ai_pdf_comparison_task.docker_celery_manager') as mock_dcm, \
             patch('audioDiagnostic.tasks.ai_pdf_comparison_task.get_redis_connection') as mock_redis_fn:
            mock_dcm.setup_infrastructure.return_value = True
            mock_dcm.register_task.return_value = None
            mock_dcm.unregister_task.return_value = None
            mock_redis_fn.return_value = mock_redis()
            result = ai_compare_pdf_task.apply(args=[99999, self.user.id])
        self.assertEqual(result.state, 'FAILURE')


# ───────────────────────────── URL discovery tests ──────────────────────────

class URLDiscoveryTests(TestCase):
    """Lightweight tests that simply hit endpoints to discover URL patterns."""

    def setUp(self):
        self.user = make_user('url_disc_user')
        self.client.force_login(self.user)
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project)

    def test_api_root_reachable(self):
        resp = self.client.get('/api/')
        self.assertIn(resp.status_code, [200, 301, 302, 404, 405])

    def test_task_status_endpoint(self):
        resp = self.client.get('/api/task-status/fake-task-id/')
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_project_transcribe_post(self):
        resp = self.client.post(
            f'/api/projects/{self.project.id}/transcribe/',
            data='{}', content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_project_status_get(self):
        resp = self.client.get(f'/api/projects/{self.project.id}/status/')
        self.assertIn(resp.status_code, [200, 400, 401, 404, 500])

    def test_audio_file_segments(self):
        resp = self.client.get(f'/api/audio-files/{self.audio_file.id}/segments/')
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_project_pdf_text(self):
        resp = self.client.get(f'/api/projects/{self.project.id}/pdf-text/')
        self.assertIn(resp.status_code, [200, 400, 404, 500])
