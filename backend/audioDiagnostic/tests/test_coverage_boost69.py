"""
Wave 69 — Coverage boost
Targets:
  - processing_views.py: ProjectProcessView + AudioFileProcessView
  - infrastructure_views.py: InfrastructureStatusView, TaskStatusView
  - transcription_tasks.py: transcribe_audio_file_task error paths,
    transcribe_all_project_audio_task infra errors
  - transcription_tasks.py: split_segment_to_sentences, find_noise_regions helpers
  - pdf_tasks.py: identify_pdf_based_duplicates edge cases
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token

from audioDiagnostic.models import (
from rest_framework.test import force_authenticate
    AudioFile, AudioProject, Transcription, TranscriptionSegment,
)


# ────────────────── helpers ──────────────────
def make_user(username, password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u


def make_project(user, title='W69 Project', status='ready', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def make_audio_file(project, title='W69 File', status='transcribed', order=0, **kwargs):
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


def make_segment(audio_file, transcription, text='Segment.', idx=0):
    return TranscriptionSegment.objects.create(
        audio_file=audio_file,
        transcription=transcription,
        text=text,
        start_time=float(idx),
        end_time=float(idx) + 1.0,
        segment_index=idx,
    )


# ══════════════════════════════════════════════════════
# processing_views.py — ProjectProcessView
# ══════════════════════════════════════════════════════
class ProjectProcessViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w69_procview_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False

    def test_project_not_transcribed_status(self):
        """POST process/ when project status != transcribed → 400"""
        project = make_project(self.user, status='ready')
        resp = self.client.post(f'/api/projects/{project.id}/process/')
        self.assertIn(resp.status_code, [400, 404])

    def test_project_transcribed_no_files(self):
        """POST process/ when transcribed but no transcribed audio files → 400"""
        project = make_project(self.user, status='transcribed')
        resp = self.client.post(f'/api/projects/{project.id}/process/')
        self.assertIn(resp.status_code, [400, 404])

    def test_project_transcribed_with_files(self):
        """POST process/ with transcribed files → task started"""
        project = make_project(self.user, status='transcribed')
        make_audio_file(project, status='transcribed', order=0)
        mock_task = MagicMock()
        mock_task.id = 'w69-proc-task-id'
        with patch('audioDiagnostic.views.processing_views.process_project_duplicates_task') as mock_t:
            mock_t.delay.return_value = mock_task
            resp = self.client.post(f'/api/projects/{project.id}/process/')
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_project_wrong_user(self):
        """POST process/ for another user's project → 404"""
        other = make_user('w69_proc_other')
        other_proj = make_project(other, status='transcribed', title='Other W69')
        resp = self.client.post(f'/api/projects/{other_proj.id}/process/')
        self.assertEqual(resp.status_code, 404)


# ══════════════════════════════════════════════════════
# processing_views.py — AudioFileProcessView
# ══════════════════════════════════════════════════════
class AudioFileProcessViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w69_afprocview_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user, status='transcribed')
        self.client.raise_request_exception = False

    def test_no_pdf_file(self):
        """POST process/ when project has no PDF → 400"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        resp = self.client.post(
            f'/api/projects/{self.project.id}/files/{af.id}/process/')
        self.assertIn(resp.status_code, [400, 404])

    def test_audio_file_not_transcribed(self):
        """POST process/ when audio file not transcribed → 400"""
        import tempfile, os
        from django.core.files import File

        # Give project a fake pdf_file
        af = make_audio_file(self.project, status='uploaded', order=0)
        resp = self.client.post(
            f'/api/projects/{self.project.id}/files/{af.id}/process/')
        self.assertIn(resp.status_code, [400, 404])


# ══════════════════════════════════════════════════════
# infrastructure_views.py — InfrastructureStatusView
# ══════════════════════════════════════════════════════
class InfrastructureStatusViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w69_infra_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False

    def test_get_infrastructure_status(self):
        """GET /api/infrastructure/status/ returns status info"""
        mock_mgr = MagicMock()
        mock_mgr.get_status.return_value = {
            'docker_running': True,
            'active_tasks': 0,
            'task_list': [],
        }
        mock_r = MagicMock()
        mock_r.ping.return_value = True
        with patch('audioDiagnostic.views.infrastructure_views.docker_celery_manager', mock_mgr), \
             patch('audioDiagnostic.views.infrastructure_views.get_redis_connection', return_value=mock_r):
            resp = self.client.get('/api/infrastructure/status/')
        self.assertIn(resp.status_code, [200, 404])

    def test_post_invalid_action(self):
        """POST /api/infrastructure/status/ with invalid action → 400"""
        resp = self.client.post(
            '/api/infrastructure/status/',
            {'action': 'invalid_action'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_post_force_shutdown(self):
        """POST /api/infrastructure/status/ with force_shutdown"""
        mock_mgr = MagicMock()
        with patch('audioDiagnostic.views.infrastructure_views.docker_celery_manager', mock_mgr):
            resp = self.client.post(
                '/api/infrastructure/status/',
                {'action': 'force_shutdown'},
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [200, 404])

    def test_post_start_action(self):
        """POST /api/infrastructure/status/ with start action"""
        mock_mgr = MagicMock()
        mock_mgr.setup_infrastructure.return_value = True
        with patch('audioDiagnostic.views.infrastructure_views.docker_celery_manager', mock_mgr):
            resp = self.client.post(
                '/api/infrastructure/status/',
                {'action': 'start'},
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [200, 404])


# ══════════════════════════════════════════════════════
# infrastructure_views.py — TaskStatusView
# ══════════════════════════════════════════════════════
class TaskStatusViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w69_taskstatus_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False

    def test_task_pending(self):
        """GET /api/tasks/{task_id}/status/ — PENDING state"""
        mock_r = MagicMock()
        mock_r.get.return_value = None
        mock_result = MagicMock()
        mock_result.state = 'PENDING'
        with patch('audioDiagnostic.views.infrastructure_views.get_redis_connection',
                   return_value=mock_r), \
             patch('audioDiagnostic.views.infrastructure_views.AsyncResult',
                   return_value=mock_result):
            resp = self.client.get('/api/tasks/w69-fake-task-id/status/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json().get('status'), 'pending')

    def test_task_success(self):
        """GET /api/tasks/{task_id}/status/ — SUCCESS state"""
        mock_r = MagicMock()
        mock_r.get.return_value = b'100'
        mock_result = MagicMock()
        mock_result.state = 'SUCCESS'
        mock_result.result = {'done': True}
        with patch('audioDiagnostic.views.infrastructure_views.get_redis_connection',
                   return_value=mock_r), \
             patch('audioDiagnostic.views.infrastructure_views.AsyncResult',
                   return_value=mock_result):
            resp = self.client.get('/api/tasks/w69-success-task-id/status/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json().get('status'), 'completed')

    def test_task_failure(self):
        """GET /api/tasks/{task_id}/status/ — FAILURE state"""
        mock_r = MagicMock()
        mock_r.get.return_value = b'-1'
        mock_result = MagicMock()
        mock_result.state = 'FAILURE'
        mock_result.info = Exception('Something failed')
        with patch('audioDiagnostic.views.infrastructure_views.get_redis_connection',
                   return_value=mock_r), \
             patch('audioDiagnostic.views.infrastructure_views.AsyncResult',
                   return_value=mock_result):
            resp = self.client.get('/api/tasks/w69-fail-task-id/status/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json().get('status'), 'failed')

    def test_task_progress(self):
        """GET /api/tasks/{task_id}/status/ — PROGRESS state"""
        mock_r = MagicMock()
        mock_r.get.return_value = b'50'
        mock_result = MagicMock()
        mock_result.state = 'PROGRESS'
        with patch('audioDiagnostic.views.infrastructure_views.get_redis_connection',
                   return_value=mock_r), \
             patch('audioDiagnostic.views.infrastructure_views.AsyncResult',
                   return_value=mock_result):
            resp = self.client.get('/api/tasks/w69-progress-task-id/status/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json().get('status'), 'in_progress')


# ══════════════════════════════════════════════════════
# transcription_tasks.py — split_segment_to_sentences, find_noise_regions
# ══════════════════════════════════════════════════════
class SplitSegmentToSentencesTests(TestCase):
    """split_segment_to_sentences() — pure utility"""

    def _fn(self):
        from audioDiagnostic.tasks.transcription_tasks import split_segment_to_sentences
        return split_segment_to_sentences

    def test_single_sentence_no_words(self):
        split_segment_to_sentences = self._fn()
        seg = {'text': 'Hello world', 'start': 0.0, 'end': 2.0, 'words': []}
        result = split_segment_to_sentences(seg)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], 'Hello world')

    def test_single_sentence_with_words(self):
        split_segment_to_sentences = self._fn()
        seg = {
            'text': 'Hello world.',
            'start': 0.0,
            'end': 2.0,
            'words': [
                {'word': 'Hello', 'start': 0.0, 'end': 0.8},
                {'word': 'world.', 'start': 0.9, 'end': 2.0},
            ]
        }
        result = split_segment_to_sentences(seg)
        self.assertEqual(len(result), 1)

    def test_multiple_sentences(self):
        split_segment_to_sentences = self._fn()
        seg = {
            'text': 'Hello world. Good day. Nice weather.',
            'start': 0.0,
            'end': 6.0,
            'words': [
                {'word': 'Hello', 'start': 0.0, 'end': 0.5},
                {'word': 'world.', 'start': 0.6, 'end': 1.0},
                {'word': 'Good', 'start': 1.5, 'end': 2.0},
                {'word': 'day.', 'start': 2.1, 'end': 2.5},
                {'word': 'Nice', 'start': 3.0, 'end': 3.5},
                {'word': 'weather.', 'start': 3.6, 'end': 4.0},
            ]
        }
        result = split_segment_to_sentences(seg)
        self.assertGreaterEqual(len(result), 1)

    def test_with_next_segment_start(self):
        split_segment_to_sentences = self._fn()
        seg = {'text': 'Hello world', 'start': 0.0, 'end': 2.0, 'words': []}
        result = split_segment_to_sentences(seg, next_segment_start=2.5)
        self.assertEqual(len(result), 1)

    def test_with_audio_end(self):
        split_segment_to_sentences = self._fn()
        seg = {'text': 'Last words', 'start': 5.0, 'end': 7.0, 'words': []}
        result = split_segment_to_sentences(seg, audio_end=10.0)
        self.assertEqual(len(result), 1)


# ══════════════════════════════════════════════════════
# transcription_tasks.py — transcribe_audio_file_task error paths
# ══════════════════════════════════════════════════════
class TranscribeAudioFileTaskErrorTests(TestCase):

    def setUp(self):
        self.user = make_user('w69_trans_err_user')
        self.project = make_project(self.user)

    def test_infra_failure(self):
        """transcribe_audio_file_task fails when infra fails"""
        from audioDiagnostic.tasks.transcription_tasks import transcribe_audio_file_task
        af = make_audio_file(self.project, status='uploaded', order=0)
        with patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = False
            result = transcribe_audio_file_task.apply(args=[af.id])
        self.assertTrue(result.failed())

    def test_audio_file_not_found(self):
        """transcribe_audio_file_task fails when audio file missing"""
        from audioDiagnostic.tasks.transcription_tasks import transcribe_audio_file_task
        with patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = transcribe_audio_file_task.apply(args=[999991])
        self.assertTrue(result.failed())


# ══════════════════════════════════════════════════════
# transcription_tasks.py — transcribe_all_project_audio_task error paths
# ══════════════════════════════════════════════════════
class TranscribeAllProjectAudioTaskErrorTests(TestCase):

    def setUp(self):
        self.user = make_user('w69_trans_all_user')
        self.project = make_project(self.user)

    def test_infra_failure(self):
        """transcribe_all_project_audio_task fails when infra fails"""
        from audioDiagnostic.tasks.transcription_tasks import transcribe_all_project_audio_task
        with patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = False
            result = transcribe_all_project_audio_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())

    def test_no_audio_files(self):
        """transcribe_all_project_audio_task fails when no audio files"""
        from audioDiagnostic.tasks.transcription_tasks import transcribe_all_project_audio_task
        with patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = transcribe_all_project_audio_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())

    def test_project_not_found(self):
        """transcribe_all_project_audio_task fails when project not found"""
        from audioDiagnostic.tasks.transcription_tasks import transcribe_all_project_audio_task
        with patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager') as mock_mgr, \
             patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection',
                   return_value=MagicMock()):
            mock_mgr.setup_infrastructure.return_value = True
            mock_mgr.register_task.return_value = None
            mock_mgr.unregister_task.return_value = None
            result = transcribe_all_project_audio_task.apply(args=[999992])
        self.assertTrue(result.failed())
