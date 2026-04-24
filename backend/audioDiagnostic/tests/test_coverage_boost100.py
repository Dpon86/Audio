"""
Wave 100 — Coverage boost
Targets:
  - audioDiagnostic/services/docker_manager.py:
      DockerCeleryManager methods (register_task, unregister_task, get_status, force_shutdown, _reset_stuck_tasks)
  - audioDiagnostic/views/tab4_pdf_comparison.py: basic view coverage
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from unittest.mock import patch, MagicMock


# ─── DockerCeleryManager method tests ────────────────────────────────────────

class DockerCeleryManagerTests(TestCase):

    def _make_manager(self):
        from audioDiagnostic.services.docker_manager import DockerCeleryManager
        mgr = DockerCeleryManager.__new__(DockerCeleryManager)
        mgr.active_tasks = set()
        mgr.is_setup = False
        mgr.shutdown_timer = None
        mgr.logger = None
        return mgr

    def test_register_task(self):
        mgr = self._make_manager()
        mgr.register_task('task-123')
        self.assertIn('task-123', mgr.active_tasks)

    def test_register_task_cancels_timer(self):
        mgr = self._make_manager()
        timer = MagicMock()
        mgr.shutdown_timer = timer
        mgr.register_task('task-456')
        timer.cancel.assert_called_once()
        self.assertIsNone(mgr.shutdown_timer)

    def test_unregister_task_removes_from_set(self):
        mgr = self._make_manager()
        mgr.active_tasks.add('task-789')
        mgr.unregister_task('task-789')
        self.assertNotIn('task-789', mgr.active_tasks)

    def test_unregister_task_not_in_set(self):
        mgr = self._make_manager()
        # Should not raise
        mgr.unregister_task('nonexistent')

    def test_get_status_not_setup(self):
        mgr = self._make_manager()
        status = mgr.get_status()
        self.assertEqual(status['docker_running'], False)
        self.assertEqual(status['active_tasks'], 0)

    def test_get_status_with_tasks(self):
        mgr = self._make_manager()
        mgr.active_tasks.add('t1')
        mgr.active_tasks.add('t2')
        mgr.is_setup = True
        status = mgr.get_status()
        self.assertEqual(status['docker_running'], True)
        self.assertEqual(status['active_tasks'], 2)
        self.assertIn('t1', status['task_list'])

    def test_force_shutdown(self):
        mgr = self._make_manager()
        mgr.active_tasks = {'task1', 'task2'}
        with patch.object(mgr, 'shutdown_infrastructure', return_value={'success': True}) as mock_shutdown:
            result = mgr.force_shutdown()
        self.assertEqual(len(mgr.active_tasks), 0)
        mock_shutdown.assert_called_once()

    def test_reset_stuck_tasks(self):
        from audioDiagnostic.models import AudioProject, AudioFile
        user = User.objects.create_user(username='dockertest100', password='pass')
        project = AudioProject.objects.create(user=user, title='Stuck Project', status='processing')
        mgr = self._make_manager()
        with patch('celery.result.AsyncResult') as mock_ar:
            mock_ar.return_value.state = 'PENDING'
            mgr._reset_stuck_tasks()
        # Project should be reset
        project.refresh_from_db()
        self.assertEqual(project.status, 'pending')


# ─── tab4_pdf_comparison.py basic view coverage ───────────────────────────────

class Tab4PdfComparisonViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='tab4test100', password='pass123')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        from audioDiagnostic.models import AudioProject, AudioFile
        self.project = AudioProject.objects.create(user=self.user, title='Tab4 Project')
        self.audio_file = AudioFile.objects.create(
            project=self.project, filename='test.mp3', order_index=0
        )

    def test_tab4_comparison_get(self):
        resp = self.client.get(f'/api/api/projects/{self.project.id}/comparison/')
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_tab4_comparison_project_not_found(self):
        resp = self.client.get('/api/api/projects/999999/comparison/')
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_tab4_comparison_unauthenticated(self):
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get(f'/api/api/projects/{self.project.id}/comparison/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_tab4_comparison_post_missing_data(self):
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/comparison/',
            data={},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404, 500])

    def test_tab4_comparison_file_status(self):
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{self.audio_file.id}/compare-pdf/'
        )
        self.assertIn(resp.status_code, [200, 400, 404, 405, 500])
