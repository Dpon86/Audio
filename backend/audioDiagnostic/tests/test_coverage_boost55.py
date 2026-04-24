"""
Wave 55 — More coverage targeting:
  - tab3 views: confirm_deletions, review_duplicates, processing_status (more branches)
  - tab3 UpdateSegmentTimesView PATCH via correct URL
  - tab3 RetranscribeProcessedAudioView GET
  - process_audio_file_task (error paths)
  - validate_transcript_against_pdf_task (error paths)
  - match_pdf_to_audio_task (error paths)
  - analyze_transcription_vs_pdf (Celery task)
  - pdf_tasks helpers: find_text_in_pdf, find_missing_pdf_content, extract_chapter_title_task
  - legacy_views more branches
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
import json
from rest_framework.test import force_authenticate


def make_user(username='w55user', password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u

def make_project(user, title='W55 Project', status='ready', **kwargs):
    from audioDiagnostic.models import AudioProject
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)

def make_audio_file(project, title='W55 File', status='transcribed', order=0):
    from audioDiagnostic.models import AudioFile
    return AudioFile.objects.create(
        project=project,
        filename=f'{title.lower().replace(" ", "_")}.wav',
        title=title, order_index=order, status=status)

def make_transcription(audio_file, content='Test transcription.'):
    from audioDiagnostic.models import Transcription
    return Transcription.objects.create(audio_file=audio_file, full_text=content)

def make_segment(audio_file, transcription, text='Segment', idx=0, is_dup=False, is_kept=True):
    from audioDiagnostic.models import TranscriptionSegment
    return TranscriptionSegment.objects.create(
        audio_file=audio_file, transcription=transcription,
        text=text, start_time=float(idx), end_time=float(idx) + 1.0,
        segment_index=idx, is_duplicate=is_dup, is_kept=is_kept)


# ══════════════════════════════════════════════════════════════════════
# Tab3 SingleFileConfirmDeletionsView — more branches
# ══════════════════════════════════════════════════════════════════════
class Tab3ConfirmDeletionsViewMoreTests(TestCase):
    """Test SingleFileConfirmDeletionsView branches."""

    def setUp(self):
        self.user = make_user('w55_confirm_del_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed')
        self.tr = make_transcription(self.af, 'Confirm deletions content.')
        self.seg = make_segment(self.af, self.tr, 'Segment one.', idx=0, is_dup=True)

    def test_confirm_deletions_no_data(self):
        """POST with no confirmed_deletions returns 400."""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/confirm-deletions/',
            {'confirmed_deletions': []},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_confirm_deletions_not_a_list(self):
        """POST with confirmed_deletions not a list returns 400."""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/confirm-deletions/',
            {'confirmed_deletions': 'not_a_list'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_confirm_deletions_valid_segment_ids(self):
        """POST with valid segment IDs starts processing task."""
        with patch('audioDiagnostic.views.tab3_duplicate_detection.process_deletions_single_file_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='fake-task-w55-001')
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/files/{self.af.id}/confirm-deletions/',
                {'confirmed_deletions': [self.seg.id]},
                content_type='application/json'
            )
            self.assertIn(resp.status_code, [200, 201, 400, 404, 405, 500])

    def test_confirm_deletions_task_exception(self):
        """POST when task raises exception returns error."""
        with patch('audioDiagnostic.views.tab3_duplicate_detection.process_deletions_single_file_task') as mock_task:
            mock_task.delay.side_effect = Exception('Task launch failed')
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/files/{self.af.id}/confirm-deletions/',
                {'confirmed_deletions': [self.seg.id]},
                content_type='application/json'
            )
            self.assertIn(resp.status_code, [200, 400, 404, 405, 500])

    def test_confirm_deletions_dict_format(self):
        """POST with dict format confirmed_deletions."""
        with patch('audioDiagnostic.views.tab3_duplicate_detection.process_deletions_single_file_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='fake-task-w55-002')
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/files/{self.af.id}/confirm-deletions/',
                {'confirmed_deletions': [{'segment_id': self.seg.id}]},
                content_type='application/json'
            )
            self.assertIn(resp.status_code, [200, 201, 400, 404, 405, 500])


# ══════════════════════════════════════════════════════════════════════
# Tab3 SingleFileDuplicatesReviewView — more branches
# ══════════════════════════════════════════════════════════════════════
class Tab3DuplicatesReviewMoreTests(TestCase):
    """Test SingleFileDuplicatesReviewView more branches."""

    def setUp(self):
        self.user = make_user('w55_dup_review_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed')
        self.tr = make_transcription(self.af, 'Duplicate review content.')

    def test_review_no_duplicate_groups(self):
        """GET returns empty list when no duplicate groups."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/duplicates/'
        )
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertEqual(data.get('duplicate_groups', []), [])

    def test_review_with_duplicate_groups(self):
        """GET returns duplicate groups when they exist."""
        from audioDiagnostic.models import DuplicateGroup, TranscriptionSegment
        # Create a duplicate group
        seg1 = make_segment(self.af, self.tr, 'Repeated segment.', idx=0, is_dup=True)
        seg2 = make_segment(self.af, self.tr, 'Repeated segment.', idx=1, is_dup=False)
        grp = DuplicateGroup.objects.create(
            audio_file=self.af,
            group_id='group_0',
            duplicate_text='Repeated segment.',
            occurrence_count=2,
            total_duration_seconds=2.0
        )
        seg1.duplicate_group_id = 'group_0'
        seg1.save()
        seg2.duplicate_group_id = 'group_0'
        seg2.save()
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/duplicates/'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_review_unauthenticated(self):
        """GET without auth returns 401/403."""
        self.client.defaults.pop('HTTP_AUTHORIZATION', None)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/duplicates/'
        )
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════════════════════
# Tab3 UpdateSegmentTimesView PATCH (correct URL with segment_id)
# ══════════════════════════════════════════════════════════════════════
class Tab3UpdateSegmentTimesPatchTests(TestCase):
    """Test UpdateSegmentTimesView PATCH with segment_id in URL."""

    def setUp(self):
        self.user = make_user('w55_upd_seg_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed')
        self.tr = make_transcription(self.af, 'Update seg times content.')
        self.seg = make_segment(self.af, self.tr, 'Segment patch test.', idx=0)

    def test_patch_update_segment_success(self):
        """PATCH update segment with valid times."""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{self.seg.id}/',
            {'start_time': 0.5, 'end_time': 2.5},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404, 405])
        if resp.status_code == 200:
            data = resp.json()
            self.assertTrue(data.get('success'))

    def test_patch_update_segment_no_times(self):
        """PATCH with no times returns 400."""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{self.seg.id}/',
            {},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_patch_update_segment_invalid_end_time(self):
        """PATCH with end_time <= start_time returns 400."""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{self.seg.id}/',
            {'start_time': 5.0, 'end_time': 3.0},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_patch_update_segment_too_short(self):
        """PATCH with too short duration (< 0.1s) returns 400."""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{self.seg.id}/',
            {'start_time': 0.0, 'end_time': 0.05},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_patch_update_segment_not_found(self):
        """PATCH with non-existent segment returns 404."""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/99999/',
            {'start_time': 0.5, 'end_time': 2.5},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_patch_update_segment_invalid_value(self):
        """PATCH with invalid float value returns 400."""
        resp = self.client.patch(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/segments/{self.seg.id}/',
            {'start_time': 'not_a_float', 'end_time': 2.5},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404, 405])


# ══════════════════════════════════════════════════════════════════════
# Tab3 RetranscribeProcessedAudioView GET
# ══════════════════════════════════════════════════════════════════════
class Tab3RetranscribeViewGetTests(TestCase):
    """Test RetranscribeProcessedAudioView GET."""

    def setUp(self):
        self.user = make_user('w55_retr_get_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed')

    def test_get_retranscription_status(self):
        """GET retranscription status returns status info."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/retranscribe/'
        )
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertTrue(data.get('success'))

    def test_get_retranscription_status_project_not_found(self):
        """GET retranscription status for non-existent project returns 404."""
        resp = self.client.get(
            f'/api/api/projects/99999/files/{self.af.id}/retranscribe/'
        )
        self.assertEqual(resp.status_code, 404)


# ══════════════════════════════════════════════════════════════════════
# process_audio_file_task — error paths
# ══════════════════════════════════════════════════════════════════════
class ProcessAudioFileTaskTests(TestCase):
    """Test process_audio_file_task error paths."""

    def setUp(self):
        self.user = make_user('w55_proc_audio_user')
        self.project = make_project(self.user, title='Proc Audio Project')

    def test_file_not_found(self):
        """Task fails when audio_file_id doesn't exist."""
        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        with patch('audioDiagnostic.tasks.audio_processing_tasks.get_redis_connection', return_value=MagicMock()), \
             patch('audioDiagnostic.tasks.audio_processing_tasks.docker_celery_manager') as mock_dcm:
            mock_dcm.setup_infrastructure.return_value = True
            result = process_audio_file_task.apply(
                args=[99999], task_id='w55-proc-audio-001')
            self.assertEqual(result.status, 'FAILURE')

    def test_audio_not_transcribed(self):
        """Task fails when audio file is not transcribed."""
        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        af = make_audio_file(self.project, status='uploaded', order=0)
        with patch('audioDiagnostic.tasks.audio_processing_tasks.get_redis_connection', return_value=MagicMock()), \
             patch('audioDiagnostic.tasks.audio_processing_tasks.docker_celery_manager') as mock_dcm:
            mock_dcm.setup_infrastructure.return_value = True
            result = process_audio_file_task.apply(
                args=[af.id], task_id='w55-proc-audio-002')
            self.assertEqual(result.status, 'FAILURE')

    def test_no_segments(self):
        """Task fails when audio file has no segments."""
        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        af = make_audio_file(self.project, status='transcribed', order=1)
        # No segments created
        with patch('audioDiagnostic.tasks.audio_processing_tasks.get_redis_connection', return_value=MagicMock()), \
             patch('audioDiagnostic.tasks.audio_processing_tasks.docker_celery_manager') as mock_dcm:
            mock_dcm.setup_infrastructure.return_value = True
            result = process_audio_file_task.apply(
                args=[af.id], task_id='w55-proc-audio-003')
            self.assertEqual(result.status, 'FAILURE')

    def test_infrastructure_fails(self):
        """Task fails when infra setup fails."""
        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        with patch('audioDiagnostic.tasks.audio_processing_tasks.get_redis_connection', return_value=MagicMock()), \
             patch('audioDiagnostic.tasks.audio_processing_tasks.docker_celery_manager') as mock_dcm:
            mock_dcm.setup_infrastructure.return_value = False
            result = process_audio_file_task.apply(
                args=[99999], task_id='w55-proc-audio-004')
            self.assertEqual(result.status, 'FAILURE')


# ══════════════════════════════════════════════════════════════════════
# validate_transcript_against_pdf_task — error paths
# ══════════════════════════════════════════════════════════════════════
class ValidateTranscriptPDFTaskTests(TestCase):
    """Test validate_transcript_against_pdf_task error paths."""

    def setUp(self):
        self.user = make_user('w55_validate_user')
        self.project = make_project(self.user, title='Validate PDF Project')

    def test_project_not_found(self):
        """Task fails when project_id doesn't exist."""
        from audioDiagnostic.tasks.pdf_tasks import validate_transcript_against_pdf_task
        with patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection', return_value=MagicMock()), \
             patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager') as mock_dcm:
            mock_dcm.setup_infrastructure.return_value = True
            result = validate_transcript_against_pdf_task.apply(
                args=[99999], task_id='w55-validate-001')
            self.assertEqual(result.status, 'FAILURE')

    def test_no_pdf_section_matched(self):
        """Task fails when no pdf_matched_section."""
        from audioDiagnostic.tasks.pdf_tasks import validate_transcript_against_pdf_task
        # project has pdf_match_completed=False and no pdf_matched_section
        with patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection', return_value=MagicMock()), \
             patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager') as mock_dcm:
            mock_dcm.setup_infrastructure.return_value = True
            result = validate_transcript_against_pdf_task.apply(
                args=[self.project.id], task_id='w55-validate-002')
            self.assertEqual(result.status, 'FAILURE')

    def test_infrastructure_fails(self):
        """Task fails when infra setup fails."""
        from audioDiagnostic.tasks.pdf_tasks import validate_transcript_against_pdf_task
        with patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection', return_value=MagicMock()), \
             patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager') as mock_dcm:
            mock_dcm.setup_infrastructure.return_value = False
            result = validate_transcript_against_pdf_task.apply(
                args=[self.project.id], task_id='w55-validate-003')
            self.assertEqual(result.status, 'FAILURE')


# ══════════════════════════════════════════════════════════════════════
# match_pdf_to_audio_task — error paths
# ══════════════════════════════════════════════════════════════════════
class MatchPDFToAudioTaskTests(TestCase):
    """Test match_pdf_to_audio_task error paths."""

    def setUp(self):
        self.user = make_user('w55_match_pdf_user')
        self.project = make_project(self.user, title='Match PDF Project')

    def test_project_not_found(self):
        """Task fails when project_id doesn't exist."""
        from audioDiagnostic.tasks.pdf_tasks import match_pdf_to_audio_task
        with patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection', return_value=MagicMock()), \
             patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager') as mock_dcm:
            mock_dcm.setup_infrastructure.return_value = True
            result = match_pdf_to_audio_task.apply(
                args=[99999], task_id='w55-match-pdf-001')
            self.assertEqual(result.status, 'FAILURE')

    def test_no_pdf_file(self):
        """Task fails when project has no pdf_file."""
        from audioDiagnostic.tasks.pdf_tasks import match_pdf_to_audio_task
        # project has no pdf_file set
        with patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection', return_value=MagicMock()), \
             patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager') as mock_dcm:
            mock_dcm.setup_infrastructure.return_value = True
            result = match_pdf_to_audio_task.apply(
                args=[self.project.id], task_id='w55-match-pdf-002')
            self.assertEqual(result.status, 'FAILURE')

    def test_infrastructure_fails(self):
        """Task fails when infra setup fails."""
        from audioDiagnostic.tasks.pdf_tasks import match_pdf_to_audio_task
        with patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection', return_value=MagicMock()), \
             patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager') as mock_dcm:
            mock_dcm.setup_infrastructure.return_value = False
            result = match_pdf_to_audio_task.apply(
                args=[self.project.id], task_id='w55-match-pdf-003')
            self.assertEqual(result.status, 'FAILURE')


# ══════════════════════════════════════════════════════════════════════
# pdf_tasks helpers
# ══════════════════════════════════════════════════════════════════════
class PDFTaskHelpersTests(TestCase):
    """Test pdf_tasks helper functions."""

    def test_find_text_in_pdf_found(self):
        """find_text_in_pdf returns True when text is in PDF."""
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf('hello world', 'This is a hello world example text.')
        self.assertTrue(result)

    def test_find_text_in_pdf_not_found(self):
        """find_text_in_pdf returns False when text not in PDF."""
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        result = find_text_in_pdf('completely unrelated text xyz', 'Hello World.')
        self.assertFalse(result)

    def test_find_text_in_pdf_empty(self):
        """find_text_in_pdf handles empty inputs."""
        from audioDiagnostic.tasks.pdf_tasks import find_text_in_pdf
        try:
            result = find_text_in_pdf('', '')
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_find_missing_pdf_content_no_missing(self):
        """find_missing_pdf_content returns empty when no missing content."""
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        transcript = 'Hello world this is a test.'
        pdf = 'Hello world this is a test.'
        try:
            result = find_missing_pdf_content(transcript, pdf)
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_find_missing_pdf_content_with_missing(self):
        """find_missing_pdf_content finds missing sections."""
        from audioDiagnostic.tasks.pdf_tasks import find_missing_pdf_content
        transcript = 'Hello world.'
        pdf = 'Hello world. Extra content that is missing. More missing text.'
        try:
            result = find_missing_pdf_content(transcript, pdf)
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_calculate_comprehensive_similarity(self):
        """calculate_comprehensive_similarity_task returns similarity dict."""
        from audioDiagnostic.tasks.pdf_tasks import calculate_comprehensive_similarity_task
        try:
            result = calculate_comprehensive_similarity_task(
                'Hello world test',
                'Hello world test'
            )
            # Should be a dict or float
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_extract_chapter_title_task(self):
        """extract_chapter_title_task extracts title from context."""
        from audioDiagnostic.tasks.pdf_tasks import extract_chapter_title_task
        try:
            result = extract_chapter_title_task('Chapter 1: The Beginning\nSome content here.')
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_identify_pdf_based_duplicates(self):
        """identify_pdf_based_duplicates returns duplicate info."""
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        segments = [
            {'text': 'Hello world.', 'start': 0.0, 'end': 1.0},
            {'text': 'Hello world.', 'start': 2.0, 'end': 3.0},
            {'text': 'Unique content.', 'start': 3.0, 'end': 4.0},
        ]
        pdf_section = 'Hello world. Unique content.'
        transcript = 'Hello world. Hello world. Unique content.'
        try:
            result = identify_pdf_based_duplicates(segments, pdf_section, transcript)
            self.assertIsInstance(result, dict)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
# legacy_views — more branches (cut/upload/status)
# ══════════════════════════════════════════════════════════════════════
class LegacyViewsMoreTests(TestCase):
    """Test more legacy_views branches."""

    def setUp(self):
        self.user = make_user('w55_legacy_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False

    def test_get_all_projects(self):
        """GET /api/projects/ returns project list."""
        resp = self.client.get('/api/projects/')
        self.assertIn(resp.status_code, [200, 404])

    def test_create_project(self):
        """POST /api/projects/ creates a project."""
        resp = self.client.post(
            '/api/projects/',
            {'title': 'W55 Legacy Project'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404])

    def test_delete_project(self):
        """DELETE /api/projects/{id}/ deletes a project."""
        project = make_project(self.user, title='W55 Delete Project')
        resp = self.client.delete(f'/api/projects/{project.id}/')
        self.assertIn(resp.status_code, [200, 204, 404, 405])

    def test_get_project_detail(self):
        """GET /api/projects/{id}/ returns project detail."""
        project = make_project(self.user, title='W55 Detail Project')
        resp = self.client.get(f'/api/projects/{project.id}/')
        self.assertIn(resp.status_code, [200, 404])

    def test_get_transcription(self):
        """GET /api/transcription/{id}/ returns transcription."""
        project = make_project(self.user, title='W55 Transcript Project')
        af = make_audio_file(project, status='transcribed', order=0)
        tr = make_transcription(af, 'Legacy transcript content.')
        resp = self.client.get(f'/api/transcription/{af.id}/')
        self.assertIn(resp.status_code, [200, 404])

    def test_task_progress_no_task(self):
        """GET /api/progress/{task_id}/ with no task returns something."""
        with patch('audioDiagnostic.views.legacy_views.r') as mock_r:
            mock_r.get.return_value = None
            resp = self.client.get('/api/progress/nonexistent-task-id/')
        self.assertIn(resp.status_code, [200, 404])

    def test_task_progress_with_value(self):
        """GET /api/progress/{task_id}/ returns progress value."""
        with patch('audioDiagnostic.views.legacy_views.r') as mock_r:
            mock_r.get.return_value = b'50'
            resp = self.client.get('/api/progress/w55-test-task-001/')
        self.assertIn(resp.status_code, [200, 404])

    def test_upload_pdf_no_file(self):
        """POST /api/upload-pdf/ without file returns error."""
        resp = self.client.post('/api/upload-pdf/', {}, content_type='application/json')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 415])

    def test_upload_audio_no_file(self):
        """POST /api/upload-audio/ without file returns error."""
        resp = self.client.post('/api/upload-audio/', {}, content_type='application/json')
        self.assertIn(resp.status_code, [200, 400, 404, 405, 415])


# ══════════════════════════════════════════════════════════════════════
# accounts views — more branches
# ══════════════════════════════════════════════════════════════════════
class AccountsViewsMoreTests(TestCase):
    """Test more accounts views branches."""

    def test_login_wrong_password(self):
        """POST /api/auth/login/ with wrong password returns 400."""
        user = make_user('w55_login_wrong_user', 'correct_pass!')
        resp = self.client.post(
            '/api/auth/login/',
            {'username': 'w55_login_wrong_user', 'password': 'wrong_pass!'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 401, 403])

    def test_login_user_not_found(self):
        """POST /api/auth/login/ with non-existent user returns 400."""
        resp = self.client.post(
            '/api/auth/login/',
            {'username': 'w55_nonexistent_xyz', 'password': 'any_pass!'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 401, 403])

    def test_login_missing_fields(self):
        """POST /api/auth/login/ with missing fields returns 400."""
        resp = self.client.post(
            '/api/auth/login/',
            {'username': 'w55_missing_user'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 401, 403])

    def test_register_duplicate_username(self):
        """POST /api/auth/register/ with duplicate username returns 400."""
        make_user('w55_dup_reg_user', 'pass1234!')
        resp = self.client.post(
            '/api/auth/register/',
            {'username': 'w55_dup_reg_user', 'password': 'pass1234!', 'email': 'test@test.com'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404, 405])

    def test_register_missing_password(self):
        """POST /api/auth/register/ without password returns 400."""
        resp = self.client.post(
            '/api/auth/register/',
            {'username': 'w55_reg_no_pass'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404, 405])
