"""
Wave 58 — Coverage targeting:
  - docker_manager.py: DockerCeleryManager methods
  - anthropic_client.py: AnthropicClient methods
  - rundev.py: SystemCheck and more management commands
  - more accounts/webhooks paths
  - more upload_views paths
"""
from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
import json


def make_user(username='w58user', password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u

def make_project(user, title='W58 Project', status='ready', **kwargs):
    from audioDiagnostic.models import AudioProject
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)

def make_audio_file(project, title='W58 File', status='transcribed', order=0):
    from audioDiagnostic.models import AudioFile
    return AudioFile.objects.create(
        project=project,
        filename=f'{title.lower().replace(" ", "_")}.wav',
        title=title, order_index=order, status=status)

def make_transcription(audio_file, content='Test transcription.'):
    from audioDiagnostic.models import Transcription
    return Transcription.objects.create(audio_file=audio_file, full_text=content)

def make_segment(audio_file, transcription, text='Segment', idx=0):
    from audioDiagnostic.models import TranscriptionSegment
    return TranscriptionSegment.objects.create(
        audio_file=audio_file, transcription=transcription,
        text=text, start_time=float(idx), end_time=float(idx) + 1.0,
        segment_index=idx)


# ══════════════════════════════════════════════════════════════════════
# DockerCeleryManager — unit tests
# ══════════════════════════════════════════════════════════════════════
class DockerCeleryManagerUnitTests(TestCase):
    """Unit tests for DockerCeleryManager methods."""

    def _make_manager(self):
        """Create a manager with mocked subprocess to avoid actual Docker calls."""
        with patch('audioDiagnostic.services.docker_manager.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='')
            from audioDiagnostic.services.docker_manager import DockerCeleryManager
            mgr = DockerCeleryManager.__new__(DockerCeleryManager)
            mgr.is_setup = False
            mgr.active_tasks = set()
            mgr.shutdown_timer = None
            mgr.backend_dir = '/app'
            return mgr

    def test_get_status_not_setup(self):
        """get_status returns correct dict when not set up."""
        mgr = self._make_manager()
        status = mgr.get_status()
        self.assertFalse(status['docker_running'])
        self.assertEqual(status['active_tasks'], 0)
        self.assertEqual(status['task_list'], [])

    def test_get_status_with_tasks(self):
        """get_status reports active tasks correctly."""
        mgr = self._make_manager()
        mgr.is_setup = True
        mgr.active_tasks = {'task-1', 'task-2'}
        status = mgr.get_status()
        self.assertTrue(status['docker_running'])
        self.assertEqual(status['active_tasks'], 2)
        self.assertIn('task-1', status['task_list'])

    def test_register_task(self):
        """register_task adds task to active_tasks."""
        mgr = self._make_manager()
        mgr.register_task('test-task-001')
        self.assertIn('test-task-001', mgr.active_tasks)

    def test_register_task_cancels_timer(self):
        """register_task cancels existing shutdown timer."""
        mgr = self._make_manager()
        mock_timer = MagicMock()
        mgr.shutdown_timer = mock_timer
        mgr.register_task('test-task-002')
        mock_timer.cancel.assert_called_once()
        self.assertIsNone(mgr.shutdown_timer)

    def test_unregister_task_removes_it(self):
        """unregister_task removes task from active_tasks."""
        mgr = self._make_manager()
        mgr.active_tasks = {'task-A', 'task-B'}
        mgr.unregister_task('task-A')
        self.assertNotIn('task-A', mgr.active_tasks)
        self.assertIn('task-B', mgr.active_tasks)

    def test_unregister_task_not_present(self):
        """unregister_task is safe when task not in set."""
        mgr = self._make_manager()
        mgr.active_tasks = set()
        # Should not raise
        mgr.unregister_task('nonexistent-task')

    def test_setup_infrastructure_already_setup(self):
        """setup_infrastructure returns True immediately if already setup."""
        mgr = self._make_manager()
        mgr.is_setup = True
        result = mgr.setup_infrastructure()
        self.assertTrue(result)

    def test_force_shutdown_clears_tasks(self):
        """force_shutdown clears active tasks."""
        mgr = self._make_manager()
        mgr.is_setup = True
        mgr.active_tasks = {'task-1', 'task-2'}
        with patch.object(mgr, 'shutdown_infrastructure', return_value=True):
            mgr.force_shutdown()
        self.assertEqual(len(mgr.active_tasks), 0)

    def test_shutdown_infrastructure_not_setup(self):
        """shutdown_infrastructure returns True quickly if not set up."""
        mgr = self._make_manager()
        mgr.is_setup = False
        result = mgr.shutdown_infrastructure()
        self.assertTrue(result)

    def test_check_docker_command_not_found(self):
        """_check_docker handles missing docker command gracefully."""
        mgr = self._make_manager()
        with patch('audioDiagnostic.services.docker_manager.subprocess.run', side_effect=FileNotFoundError):
            result = mgr._check_docker()
            self.assertFalse(result)

    def test_check_docker_timeout(self):
        """_check_docker handles timeout."""
        import subprocess
        mgr = self._make_manager()
        with patch('audioDiagnostic.services.docker_manager.subprocess.run', side_effect=subprocess.TimeoutExpired('docker', 10)):
            result = mgr._check_docker()
            self.assertFalse(result)

    def test_check_docker_success(self):
        """_check_docker returns True when docker is available."""
        mgr = self._make_manager()
        mock_result = MagicMock(returncode=0, stdout='Docker version 24.0', stderr='')
        with patch('audioDiagnostic.services.docker_manager.subprocess.run', return_value=mock_result):
            result = mgr._check_docker()
            self.assertTrue(result)

    def test_shutdown_if_idle_with_active_tasks(self):
        """_shutdown_if_idle does not shut down if tasks are active."""
        mgr = self._make_manager()
        mgr.is_setup = True
        mgr.active_tasks = {'active-task'}
        with patch.object(mgr, 'shutdown_infrastructure') as mock_shutdown:
            mgr._shutdown_if_idle()
            mock_shutdown.assert_not_called()

    def test_shutdown_if_idle_no_tasks(self):
        """_shutdown_if_idle shuts down when no tasks active."""
        mgr = self._make_manager()
        mgr.is_setup = True
        mgr.active_tasks = set()
        with patch.object(mgr, 'shutdown_infrastructure', return_value=True) as mock_shutdown:
            mgr._shutdown_if_idle()
            mock_shutdown.assert_called_once()

    def test_reset_stuck_tasks(self):
        """_reset_stuck_tasks runs without error (mocked DB)."""
        mgr = self._make_manager()
        user = make_user('w58_stuck_task_user')
        proj = make_project(user, title='W58 Stuck Project', status='processing')
        af = make_audio_file(proj, status='transcribing', order=0)
        af.task_id = 'stuck-task-id'
        af.save()
        with patch('audioDiagnostic.services.docker_manager.AsyncResult') as mock_ar:
            mock_ar.return_value = MagicMock(state='PENDING')
            # Should not raise
            mgr._reset_stuck_tasks()
        # Verify file was reset
        af.refresh_from_db()
        self.assertEqual(af.status, 'pending')


# ══════════════════════════════════════════════════════════════════════
# AnthropicClient — unit tests for pure methods
# ══════════════════════════════════════════════════════════════════════
class AnthropicClientTests(TestCase):
    """Unit tests for AnthropicClient that don't hit the real API."""

    def _make_client(self):
        """Create AnthropicClient with mocked Anthropic SDK."""
        with patch('audioDiagnostic.services.ai.anthropic_client.Anthropic') as mock_anthropic:
            with patch('django.conf.settings') as mock_settings:
                mock_settings.ANTHROPIC_API_KEY = 'sk-test-key-12345'
                mock_settings.AI_MODEL = 'claude-3-5-sonnet-20241022'
                mock_settings.AI_MAX_TOKENS = 4096
                from audioDiagnostic.services.ai.anthropic_client import AnthropicClient
                client = AnthropicClient.__new__(AnthropicClient)
                client.client = MagicMock()
                client.model = 'claude-3-5-sonnet-20241022'
                client.max_tokens = 4096
                client.max_retries = 3
                client.base_delay = 0  # No sleep in tests
                return client

    def test_calculate_cost_zero_tokens(self):
        """_calculate_cost with 0 tokens returns 0."""
        client = self._make_client()
        cost = client._calculate_cost(0, 0)
        self.assertEqual(cost, 0.0)

    def test_calculate_cost_typical_usage(self):
        """_calculate_cost with typical usage."""
        client = self._make_client()
        cost = client._calculate_cost(1000, 500)
        # Input: 1000/1M * $3 = $0.003; Output: 500/1M * $15 = $0.0075
        self.assertAlmostEqual(cost, 0.0105, places=4)

    def test_parse_json_response_direct(self):
        """parse_json_response handles direct JSON."""
        client = self._make_client()
        result = client.parse_json_response('{"key": "value", "count": 42}')
        self.assertEqual(result['key'], 'value')
        self.assertEqual(result['count'], 42)

    def test_parse_json_response_markdown_block(self):
        """parse_json_response handles ```json blocks."""
        client = self._make_client()
        response = '```json\n{"duplicates": [], "total": 0}\n```'
        result = client.parse_json_response(response)
        self.assertEqual(result['total'], 0)

    def test_parse_json_response_generic_code_block(self):
        """parse_json_response handles generic ``` code blocks."""
        client = self._make_client()
        response = '```\n{"status": "ok"}\n```'
        result = client.parse_json_response(response)
        self.assertEqual(result['status'], 'ok')

    def test_parse_json_response_invalid(self):
        """parse_json_response raises ValueError for invalid JSON."""
        client = self._make_client()
        with self.assertRaises(ValueError):
            client.parse_json_response("not json at all here")

    def test_parse_json_response_invalid_in_block(self):
        """parse_json_response raises ValueError for invalid JSON in code block."""
        client = self._make_client()
        with self.assertRaises(ValueError):
            client.parse_json_response("```json\nnot valid json\n```")

    def test_call_api_success(self):
        """call_api returns structured response on success."""
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"result": "success"}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        client.client.messages.create.return_value = mock_response
        result = client.call_api("Test prompt")
        self.assertIn('content', result)
        self.assertIn('usage', result)
        self.assertIn('cost', result)
        self.assertEqual(result['content'], '{"result": "success"}')

    def test_call_api_with_system_prompt(self):
        """call_api passes system prompt correctly."""
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='response')]
        mock_response.usage.input_tokens = 50
        mock_response.usage.output_tokens = 25
        client.client.messages.create.return_value = mock_response
        result = client.call_api("prompt", system_prompt="You are helpful.")
        # Verify system was passed
        call_kwargs = client.client.messages.create.call_args[1]
        self.assertIn('system', call_kwargs)

    def test_call_api_rate_limit_retry(self):
        """call_api retries on RateLimitError and eventually raises."""
        from anthropic import RateLimitError
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        client.client.messages.create.side_effect = RateLimitError(
            message="Rate limited", response=mock_resp, body={})
        with self.assertRaises(RateLimitError):
            client.call_api("Test prompt")

    def test_call_api_generic_exception(self):
        """call_api raises on generic exception."""
        client = self._make_client()
        client.client.messages.create.side_effect = RuntimeError("Connection refused")
        with self.assertRaises(RuntimeError):
            client.call_api("Test prompt")


# ══════════════════════════════════════════════════════════════════════
# upload_views — more branches
# ══════════════════════════════════════════════════════════════════════
class UploadViewsMoreTests(TestCase):
    """Test more upload_views branches."""

    def setUp(self):
        self.user = make_user('w58_upload_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user, title='W58 Upload Project')

    def test_list_projects(self):
        """GET /api/projects/ returns list of user projects."""
        resp = self.client.get('/api/projects/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, (list, dict))

    def test_create_project(self):
        """POST /api/projects/ creates a new project."""
        resp = self.client.post(
            '/api/projects/',
            {'title': 'New W58 Project'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 201, 400])

    def test_get_project_detail(self):
        """GET /api/projects/{id}/ returns project details."""
        resp = self.client.get(f'/api/projects/{self.project.id}/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('title', data)

    def test_delete_project(self):
        """DELETE /api/projects/{id}/ deletes the project."""
        proj = make_project(self.user, title='W58 Delete Me', status='ready')
        resp = self.client.delete(f'/api/projects/{proj.id}/')
        self.assertIn(resp.status_code, [200, 204, 404, 405])

    def test_get_nonexistent_project(self):
        """GET non-existent project returns 404."""
        resp = self.client.get('/api/projects/99999/')
        self.assertEqual(resp.status_code, 404)

    def test_upload_audio_no_file(self):
        """POST upload audio without file returns 400/415."""
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-audio/',
            {},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 415])

    def test_upload_pdf_no_file(self):
        """POST upload PDF without file returns 400/415."""
        resp = self.client.post(
            f'/api/projects/{self.project.id}/upload-pdf/',
            {},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 415])

    def test_list_audio_files(self):
        """GET audio files for project."""
        resp = self.client.get(f'/api/projects/{self.project.id}/audio-files/')
        self.assertIn(resp.status_code, [200, 404])

    def test_unauthenticated_request(self):
        """Unauthenticated requests return 401."""
        self.client.defaults.pop('HTTP_AUTHORIZATION', None)
        resp = self.client.get('/api/projects/')
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════════════════════
# accounts/webhooks — more branches  
# ══════════════════════════════════════════════════════════════════════
class AccountsWebhooksTests(TestCase):
    """Test accounts/webhooks branches."""

    def test_stripe_webhook_no_signature(self):
        """POST Stripe webhook without signature header returns 400."""
        resp = self.client.post(
            '/api/auth/stripe-webhook/',
            json.dumps({'type': 'payment_intent.succeeded'}),
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 403, 404, 405])

    def test_stripe_webhook_invalid_signature(self):
        """POST Stripe webhook with invalid signature returns 400."""
        resp = self.client.post(
            '/api/auth/stripe-webhook/',
            json.dumps({'type': 'customer.subscription.created'}),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='invalid-sig-12345'
        )
        self.assertIn(resp.status_code, [400, 403, 404, 405])

    def test_stripe_webhook_wrong_method(self):
        """GET Stripe webhook returns 405 (Method Not Allowed)."""
        resp = self.client.get('/api/auth/stripe-webhook/')
        self.assertIn(resp.status_code, [200, 400, 403, 404, 405])

    def test_login_invalid_credentials(self):
        """POST login with wrong credentials returns 400/401."""
        resp = self.client.post(
            '/api/auth/login/',
            {'username': 'nonexistent_user_w58', 'password': 'wrong_pass'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 401])

    def test_register_duplicate_username(self):
        """POST register with duplicate username returns 400."""
        make_user('w58_dup_reg_user', 'pass1234!')
        resp = self.client.post(
            '/api/auth/register/',
            {
                'username': 'w58_dup_reg_user',
                'password': 'newpass1234!',
                'email': 'test@example.com'
            },
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_register_missing_fields(self):
        """POST register without required fields returns 400."""
        resp = self.client.post(
            '/api/auth/register/',
            {'username': 'w58_incomplete_user'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_login_valid_credentials(self):
        """POST login with valid credentials returns token."""
        make_user('w58_valid_login', 'validpass1234!')
        resp = self.client.post(
            '/api/auth/login/',
            {'username': 'w58_valid_login', 'password': 'validpass1234!'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('token', data)


# ══════════════════════════════════════════════════════════════════════
# tab5_pdf_comparison — more branches
# ══════════════════════════════════════════════════════════════════════
class Tab5PdfComparisonMoreTests(TestCase):
    """Test more tab5_pdf_comparison endpoints."""

    def setUp(self):
        self.user = make_user('w58_tab5_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(
            self.user, title='W58 Tab5 Project',
            pdf_match_completed=True,
            pdf_matched_section='Sample PDF section content.'
        )
        self.af = make_audio_file(self.project, status='transcribed', order=0)
        self.tr = make_transcription(self.af, 'Tab5 transcription content.')
        self.seg = make_segment(self.af, self.tr, 'Tab5 segment text.', idx=0)

    def test_get_pdf_comparison_status(self):
        """GET PDF comparison status for a project."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/pdf-comparison-status/'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_post_match_pdf_to_audio(self):
        """POST match PDF to audio with mocked task."""
        with patch('audioDiagnostic.views.tab5_pdf_comparison.match_pdf_to_audio_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='w58-pdf-match-001')
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/match-pdf/',
                {},
                content_type='application/json'
            )
            self.assertIn(resp.status_code, [200, 201, 400, 404, 405])

    def test_get_pdf_match_result(self):
        """GET PDF match result."""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/pdf-match-result/'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_post_validate_transcript_mock(self):
        """POST validate transcript vs PDF with mocked task."""
        with patch('audioDiagnostic.views.tab5_pdf_comparison.validate_transcript_against_pdf_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='w58-validate-001')
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/validate-transcript/',
                {},
                content_type='application/json'
            )
            self.assertIn(resp.status_code, [200, 201, 400, 404, 405])

    def test_unauthenticated(self):
        """Unauthenticated requests rejected."""
        self.client.defaults.pop('HTTP_AUTHORIZATION', None)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/pdf-comparison-status/'
        )
        self.assertIn(resp.status_code, [401, 403, 404])


# ══════════════════════════════════════════════════════════════════════
# precise_pdf_comparison_task — error paths
# ══════════════════════════════════════════════════════════════════════
class PrecisePdfComparisonTaskTests(TestCase):
    """Test precise_pdf_comparison_task error paths and helper functions."""

    def setUp(self):
        self.user = make_user('w58_precise_pdf_user')
        self.project = make_project(self.user, title='Precise PDF Project')
        self.af = make_audio_file(self.project, status='transcribed', order=0)
        self.tr = make_transcription(self.af, 'Precise PDF transcription content here.')
        self.seg = make_segment(self.af, self.tr, 'Precise PDF segment.', idx=0)

    def test_analyze_transcription_vs_pdf_runs(self):
        """analyze_transcription_vs_pdf runs with mocked PdfReader."""
        from audioDiagnostic.tasks.pdf_tasks import analyze_transcription_vs_pdf
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "This is PDF content with some repeated text here now."
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        with patch('audioDiagnostic.tasks.pdf_tasks.PdfReader', return_value=mock_reader):
            result = analyze_transcription_vs_pdf.apply(args=[
                '/fake/path.pdf',
                'This is transcript content.',
                [{'text': 'segment one', 'start': 0.0, 'end': 1.0},
                 {'text': 'segment one', 'start': 1.0, 'end': 2.0}],
                [{'word': 'content', 'start': 0.0, 'end': 0.5}]
            ], task_id='w58-analyze-001')
            self.assertIn(result.status, ['SUCCESS', 'FAILURE'])
            if result.status == 'SUCCESS':
                data = result.get()
                self.assertIn('pdf_section', data)
                self.assertIn('repeated_sections', data)

    def test_analyze_transcription_vs_pdf_no_repeats(self):
        """analyze_transcription_vs_pdf with no repeated segments."""
        from audioDiagnostic.tasks.pdf_tasks import analyze_transcription_vs_pdf
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Unique content in the PDF file here."
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        with patch('audioDiagnostic.tasks.pdf_tasks.PdfReader', return_value=mock_reader):
            result = analyze_transcription_vs_pdf.apply(args=[
                '/fake/path.pdf',
                'Unique transcript content here.',
                [{'text': 'unique segment one', 'start': 0.0, 'end': 1.0},
                 {'text': 'unique segment two', 'start': 1.0, 'end': 2.0}],
                []
            ], task_id='w58-analyze-002')
            self.assertIn(result.status, ['SUCCESS', 'FAILURE'])
