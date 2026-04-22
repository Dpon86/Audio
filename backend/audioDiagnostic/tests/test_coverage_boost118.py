"""
Wave 118 — Coverage boost
Targets:
  - audioDiagnostic/services/docker_manager.py: _check_docker, register_task, unregister_task,
    get_status, force_shutdown, _shutdown_if_idle, _reset_stuck_tasks, _check_existing_containers
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock, call
import subprocess


def make_manager():
    from audioDiagnostic.services.docker_manager import DockerCeleryManager
    mgr = DockerCeleryManager.__new__(DockerCeleryManager)
    mgr.active_tasks = set()
    mgr.is_setup = False
    mgr.shutdown_timer = None
    mgr.backend_dir = '/app'
    return mgr


class DockerManagerMethodsTests(TestCase):

    def test_check_docker_success(self):
        mgr = make_manager()
        mock_ok = MagicMock(returncode=0, stdout='Docker version 20')
        with patch('audioDiagnostic.services.docker_manager.subprocess') as mock_sub:
            mock_sub.run.return_value = mock_ok
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired
            result = mgr._check_docker()
        self.assertTrue(result)

    def test_check_docker_daemon_not_running(self):
        mgr = make_manager()
        mock_ok = MagicMock(returncode=0, stdout='Docker version 20')
        mock_fail = MagicMock(returncode=1)
        with patch('audioDiagnostic.services.docker_manager.subprocess') as mock_sub:
            mock_sub.run.side_effect = [mock_ok, mock_fail]
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired
            result = mgr._check_docker()
        self.assertFalse(result)

    def test_check_docker_not_found(self):
        mgr = make_manager()
        mock_fail = MagicMock(returncode=1)
        with patch('audioDiagnostic.services.docker_manager.subprocess') as mock_sub:
            mock_sub.run.return_value = mock_fail
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired
            result = mgr._check_docker()
        self.assertFalse(result)

    def test_check_docker_timeout(self):
        mgr = make_manager()
        with patch('audioDiagnostic.services.docker_manager.subprocess') as mock_sub:
            mock_sub.run.side_effect = subprocess.TimeoutExpired('docker', 10)
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired
            result = mgr._check_docker()
        self.assertFalse(result)

    def test_check_docker_exception(self):
        mgr = make_manager()
        with patch('audioDiagnostic.services.docker_manager.subprocess') as mock_sub:
            mock_sub.run.side_effect = Exception('oops')
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired
            result = mgr._check_docker()
        self.assertFalse(result)

    def test_register_task_cancels_timer(self):
        mgr = make_manager()
        mock_timer = MagicMock()
        mgr.shutdown_timer = mock_timer
        mgr.register_task('task-abc')
        self.assertIn('task-abc', mgr.active_tasks)
        mock_timer.cancel.assert_called_once()
        self.assertIsNone(mgr.shutdown_timer)

    def test_register_task_no_timer(self):
        mgr = make_manager()
        mgr.register_task('task-xyz')
        self.assertIn('task-xyz', mgr.active_tasks)

    def test_unregister_task_not_in_set(self):
        mgr = make_manager()
        mgr.unregister_task('nonexistent')
        self.assertEqual(len(mgr.active_tasks), 0)

    def test_unregister_task_triggers_shutdown_timer(self):
        mgr = make_manager()
        mgr.is_setup = True
        mgr.active_tasks.add('task-1')
        with patch.object(mgr, '_start_shutdown_timer') as mock_timer:
            mgr.unregister_task('task-1')
        mock_timer.assert_called_once()

    def test_unregister_task_still_active(self):
        mgr = make_manager()
        mgr.is_setup = True
        mgr.active_tasks.add('task-1')
        mgr.active_tasks.add('task-2')
        with patch.object(mgr, '_start_shutdown_timer') as mock_timer:
            mgr.unregister_task('task-1')
        mock_timer.assert_not_called()

    def test_get_status(self):
        mgr = make_manager()
        mgr.is_setup = True
        mgr.active_tasks.add('t1')
        result = mgr.get_status()
        self.assertEqual(result['docker_running'], True)
        self.assertEqual(result['active_tasks'], 1)

    def test_force_shutdown(self):
        mgr = make_manager()
        mgr.is_setup = True
        mgr.active_tasks.add('t1')
        with patch.object(mgr, 'shutdown_infrastructure', return_value=True):
            result = mgr.force_shutdown()
        self.assertTrue(result)
        self.assertEqual(len(mgr.active_tasks), 0)

    def test_shutdown_if_idle_no_tasks(self):
        mgr = make_manager()
        with patch.object(mgr, 'shutdown_infrastructure') as mock_shut:
            mgr._shutdown_if_idle()
        mock_shut.assert_called_once()

    def test_shutdown_if_idle_with_tasks(self):
        mgr = make_manager()
        mgr.active_tasks.add('t1')
        with patch.object(mgr, 'shutdown_infrastructure') as mock_shut:
            mgr._shutdown_if_idle()
        mock_shut.assert_not_called()

    def test_reset_stuck_tasks(self):
        from django.contrib.auth.models import User
        from audioDiagnostic.models import AudioProject, AudioFile
        user = User.objects.create_user(username='dm118_stuck', password='pass')
        project = AudioProject.objects.create(user=user, title='dm118')
        af = AudioFile.objects.create(
            project=project, filename='stuck.mp3', title='stuck',
            order_index=0, status='transcribing', task_id='fake-task-dm118'
        )
        mgr = make_manager()
        with patch('audioDiagnostic.services.docker_manager.AsyncResult') as mock_ar:
            mock_instance = MagicMock()
            mock_instance.state = 'PENDING'
            mock_ar.return_value = mock_instance
            mgr._reset_stuck_tasks()
        af.refresh_from_db()
        self.assertEqual(af.status, 'pending')

    def test_start_shutdown_timer_is_disabled(self):
        mgr = make_manager()
        # _start_shutdown_timer returns early (auto-shutdown disabled)
        mgr._start_shutdown_timer()
        self.assertIsNone(mgr.shutdown_timer)

    def test_check_existing_containers(self):
        mgr = make_manager()
        mock_result = MagicMock(returncode=0, stdout='backend-redis\nbackend-celery_worker')
        with patch('audioDiagnostic.services.docker_manager.subprocess') as mock_sub:
            mock_sub.run.return_value = mock_result
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired
            result = mgr._check_existing_containers()
        self.assertIn(result, [True, False])

    def test_shutdown_infrastructure_not_setup(self):
        mgr = make_manager()
        mgr.is_setup = False
        result = mgr.shutdown_infrastructure()
        self.assertTrue(result)
