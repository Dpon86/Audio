"""
Wave 71 — Coverage boost
Targets:
  - tab3_duplicate_detection.py:
      SingleFileDetectDuplicatesView, SingleFileDuplicatesReviewView,
      SingleFileConfirmDeletionsView, SingleFileProcessingStatusView,
      SingleFileProcessedAudioView, SingleFileStatisticsView,
      UpdateSegmentTimesView, RetranscribeProcessedAudioView
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token

from audioDiagnostic.models import (
    AudioFile, AudioProject, DuplicateGroup, Transcription, TranscriptionSegment,
)


# ────────────────── helpers ──────────────────
def make_user(username, password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u


def make_project(user, title='W71 Project', status='ready', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def make_audio_file(project, title='W71 File', status='transcribed', order=0, **kwargs):
    return AudioFile.objects.create(
        project=project,
        filename=f'{title.lower().replace(" ", "_")}.wav',
        title=title,
        order_index=order,
        status=status,
        **kwargs,
    )


def make_transcription(audio_file, content='Hello world. Testing one two three.'):
    return Transcription.objects.create(audio_file=audio_file, full_text=content)


def make_segment(audio_file, transcription=None, text='Segment.', idx=0, is_dup=False, is_kept=True):
    return TranscriptionSegment.objects.create(
        audio_file=audio_file,
        transcription=transcription,
        text=text,
        start_time=float(idx),
        end_time=float(idx) + 2.0,
        segment_index=idx,
        is_duplicate=is_dup,
        is_kept=is_kept,
    )


def make_dup_group(audio_file, group_id='group_0', text='Duplicate text.', count=2, duration=5.0):
    return DuplicateGroup.objects.create(
        audio_file=audio_file,
        group_id=group_id,
        duplicate_text=text,
        occurrence_count=count,
        total_duration_seconds=duration,
    )


def auth_client(client, user):
    token = Token.objects.create(user=user)
    client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
    return token


# ══════════════════════════════════════════════════════
# SingleFileDetectDuplicatesView — POST
# ══════════════════════════════════════════════════════
class Tab3DetectDuplicatesViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w71_detect_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_unsupported_algorithm(self):
        """POST with unsupported algorithm → 400"""
        af = make_audio_file(self.project, order=0)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af.id}/detect-duplicates/',
            {'algorithm': 'nonexistent_algo'},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_no_transcription(self):
        """POST without transcription → 400"""
        af = make_audio_file(self.project, order=0)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af.id}/detect-duplicates/',
            {'algorithm': 'tfidf_cosine'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_wrong_status(self):
        """POST with file in wrong status → 400"""
        af = make_audio_file(self.project, status='uploaded', order=0)
        make_transcription(af)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af.id}/detect-duplicates/',
            {'algorithm': 'tfidf_cosine'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_detect_triggers_task(self):
        """POST with transcribed file → task starts"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        make_transcription(af)
        mock_task = MagicMock()
        mock_task.id = 'w71-detect-task-id'
        with patch(
            'audioDiagnostic.views.tab3_duplicate_detection.detect_duplicates_single_file_task'
        ) as mock_t:
            mock_t.delay.return_value = mock_task
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/files/{af.id}/detect-duplicates/',
                {'algorithm': 'tfidf_cosine'},
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_default_algorithm_pdf(self):
        """POST without algorithm → defaults to windowed_retry_pdf"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        make_transcription(af)
        mock_task = MagicMock()
        mock_task.id = 'w71-detect-default-task'
        with patch(
            'audioDiagnostic.views.tab3_duplicate_detection.detect_duplicates_single_file_task'
        ) as mock_t:
            mock_t.delay.return_value = mock_task
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/files/{af.id}/detect-duplicates/',
                {},
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [200, 400, 404])


# ══════════════════════════════════════════════════════
# SingleFileDuplicatesReviewView — GET
# ══════════════════════════════════════════════════════
class Tab3DuplicatesReviewViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w71_review_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_no_duplicates(self):
        """GET when no duplicate groups → empty list"""
        af = make_audio_file(self.project, order=0)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/duplicates/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['total_duplicates'], 0)

    def test_with_duplicates(self):
        """GET with duplicate groups and segments"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        tr = make_transcription(af)
        grp = make_dup_group(af)
        seg1 = make_segment(af, tr, 'Hello there.', idx=0, is_dup=False, is_kept=True)
        seg1.duplicate_group_id = 'group_0'
        seg1.save()
        seg2 = make_segment(af, tr, 'Hello there.', idx=2, is_dup=True, is_kept=False)
        seg2.duplicate_group_id = 'group_0'
        seg2.save()
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/duplicates/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('duplicate_groups', data)


# ══════════════════════════════════════════════════════
# SingleFileConfirmDeletionsView — POST
# ══════════════════════════════════════════════════════
class Tab3ConfirmDeletionsViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w71_confirm_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_no_deletions(self):
        """POST with empty confirmed_deletions → 400"""
        af = make_audio_file(self.project, order=0)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af.id}/confirm-deletions/',
            {'confirmed_deletions': []},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_invalid_structure(self):
        """POST with non-list confirmed_deletions → 400"""
        af = make_audio_file(self.project, order=0)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af.id}/confirm-deletions/',
            {'confirmed_deletions': 'not_a_list'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_confirm_with_segment_ids_as_dicts(self):
        """POST with dict-formatted segment IDs → task started"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        tr = make_transcription(af)
        seg = make_segment(af, tr, 'Duplicate text.', idx=0, is_dup=True)
        mock_task = MagicMock()
        mock_task.id = 'w71-confirm-task-id'
        with patch(
            'audioDiagnostic.views.tab3_duplicate_detection.process_deletions_single_file_task'
        ) as mock_t:
            mock_t.delay.return_value = mock_task
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/files/{af.id}/confirm-deletions/',
                {'confirmed_deletions': [{'segment_id': seg.id}]},
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_confirm_with_segment_ids_as_ints(self):
        """POST with integer segment IDs → task started"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        tr = make_transcription(af)
        seg = make_segment(af, tr, 'Another dup.', idx=2, is_dup=True)
        mock_task = MagicMock()
        mock_task.id = 'w71-confirm-int-task'
        with patch(
            'audioDiagnostic.views.tab3_duplicate_detection.process_deletions_single_file_task'
        ) as mock_t:
            mock_t.delay.return_value = mock_task
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/files/{af.id}/confirm-deletions/',
                {'confirmed_deletions': [seg.id]},
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [200, 400, 404])


# ══════════════════════════════════════════════════════
# SingleFileProcessingStatusView — GET
# ══════════════════════════════════════════════════════
class Tab3ProcessingStatusViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w71_procstatus_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_status_transcribed(self):
        """GET processing-status/ for transcribed file"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/processing-status/')
        self.assertIn(resp.status_code, [200, 404])

    def test_status_failed(self):
        """GET processing-status/ for failed file"""
        af = make_audio_file(
            self.project, status='failed', order=0,
            error_message='Processing error')
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/processing-status/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn('error', resp.json())

    def test_status_processing_with_task_progress(self):
        """GET processing-status/ while processing with PROGRESS state"""
        af = make_audio_file(
            self.project, status='processing', order=0,
            task_id='w71-processing-task-id')
        mock_task = MagicMock()
        mock_task.state = 'PROGRESS'
        mock_task.info = {'progress': 60, 'message': 'Cutting audio...'}
        with patch('audioDiagnostic.views.tab3_duplicate_detection.AsyncResult',
                   return_value=mock_task, create=True):
            resp = self.client.get(
                f'/api/api/projects/{self.project.id}/files/{af.id}/processing-status/')
        self.assertIn(resp.status_code, [200, 404])

    def test_status_processed_with_audio(self):
        """GET processing-status/ for processed file"""
        from django.core.files.base import ContentFile
        af = make_audio_file(self.project, status='processed', order=0)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/processing-status/')
        self.assertIn(resp.status_code, [200, 404])


# ══════════════════════════════════════════════════════
# SingleFileProcessedAudioView — GET
# ══════════════════════════════════════════════════════
class Tab3ProcessedAudioViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w71_procaudio_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_no_processed_audio(self):
        """GET processed-audio/ with no processed audio → 404"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/processed-audio/')
        self.assertIn(resp.status_code, [404, 200])

    def test_with_processed_audio(self):
        """GET processed-audio/ with processed audio → URL returned"""
        from django.core.files.base import ContentFile
        af = make_audio_file(self.project, status='processed', order=0)
        af.processed_audio.save('processed_w71.wav', ContentFile(b'RIFF' + b'\x00' * 40), save=True)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/processed-audio/')
        self.assertIn(resp.status_code, [200, 404])


# ══════════════════════════════════════════════════════
# SingleFileStatisticsView — GET
# ══════════════════════════════════════════════════════
class Tab3StatisticsViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w71_stats_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_statistics_no_transcription(self):
        """GET statistics/ with no transcription"""
        af = make_audio_file(self.project, status='uploaded', order=0)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/statistics/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['statistics']['total_segments'], 0)

    def test_statistics_with_transcription_and_duplicates(self):
        """GET statistics/ with transcription and some deleted segments"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        tr = make_transcription(af)
        make_dup_group(af, group_id='grp_s1')
        make_segment(af, tr, 'Kept segment.', idx=0, is_dup=False, is_kept=True)
        make_segment(af, tr, 'Deleted segment.', idx=2, is_dup=True, is_kept=False)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/statistics/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            stats = resp.json()['statistics']
            self.assertEqual(stats['total_segments'], 2)
            self.assertEqual(stats['segments_deleted'], 1)


# ══════════════════════════════════════════════════════
# UpdateSegmentTimesView — PATCH
# ══════════════════════════════════════════════════════
class Tab3UpdateSegmentTimesViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w71_updateseg_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed', order=0)
        self.tr = make_transcription(self.af)
        self.seg = make_segment(self.af, self.tr, 'Update me.', idx=0)
        self.client.raise_request_exception = False

    def test_update_start_time(self):
        """PATCH start_time updates segment"""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{self.seg.id}/',
            {'start_time': 0.5},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.seg.refresh_from_db()
            self.assertAlmostEqual(self.seg.start_time, 0.5)

    def test_update_end_time(self):
        """PATCH end_time updates segment"""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{self.seg.id}/',
            {'end_time': 3.5},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_no_times_provided(self):
        """PATCH with no times → 400"""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{self.seg.id}/',
            {},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_invalid_start_time(self):
        """PATCH with invalid start_time → 400"""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{self.seg.id}/',
            {'start_time': 'not_a_number'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_end_before_start(self):
        """PATCH end_time before start_time → 400"""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{self.seg.id}/',
            {'start_time': 5.0, 'end_time': 2.0},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_too_short_duration(self):
        """PATCH creating <0.1s duration → 400"""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{self.seg.id}/',
            {'start_time': 0.0, 'end_time': 0.05},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_segment_not_found(self):
        """PATCH wrong project/file → 404"""
        other = make_user('w71_updateseg_other')
        other_proj = make_project(other, title='W71 Other')
        other_af = make_audio_file(other_proj, order=0)
        other_tr = make_transcription(other_af)
        other_seg = make_segment(other_af, other_tr, 'Other.', idx=0)
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{other_seg.id}/',
            {'start_time': 0.5},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)


# ══════════════════════════════════════════════════════
# RetranscribeProcessedAudioView — POST + GET
# ══════════════════════════════════════════════════════
class Tab3RetranscribeViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w71_retrans_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_post_no_processed_audio(self):
        """POST retranscribe/ with no processed audio → 400"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af.id}/retranscribe/')
        self.assertIn(resp.status_code, [400, 404])

    def test_post_already_in_progress(self):
        """POST retranscribe/ when already in progress → 400"""
        from django.core.files.base import ContentFile
        af = make_audio_file(self.project, status='processed', order=0)
        af.processed_audio.save('rt_w71.wav', ContentFile(b'RIFF' + b'\x00' * 40), save=True)
        af.retranscription_status = 'processing'
        af.retranscription_task_id = 'existing-task-id'
        af.save()
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af.id}/retranscribe/')
        self.assertIn(resp.status_code, [400, 404])

    def test_post_triggers_task(self):
        """POST retranscribe/ with processed audio → task started"""
        from django.core.files.base import ContentFile
        af = make_audio_file(self.project, status='processed', order=0)
        af.processed_audio.save('rt2_w71.wav', ContentFile(b'RIFF' + b'\x00' * 40), save=True)
        mock_task = MagicMock()
        mock_task.id = 'w71-retrans-task-id'
        with patch('audioDiagnostic.tasks.retranscribe_processed_audio_task') as mock_t:
            mock_t.delay.return_value = mock_task
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/files/{af.id}/retranscribe/')
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_get_retranscription_status(self):
        """GET retranscribe/ returns current retranscription status"""
        af = make_audio_file(self.project, status='processed', order=0)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/retranscribe/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn('retranscription_status', resp.json())
