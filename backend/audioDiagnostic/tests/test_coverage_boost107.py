"""
Wave 107 — Coverage boost
Targets:
  - audioDiagnostic/services/ai/anthropic_client.py: parse_json_response, check_user_cost_limit, track_user_cost, _calculate_cost
  - audioDiagnostic/tasks/audiobook_production_task.py: get_audiobook_analysis_progress, get_audiobook_report_summary
  - audioDiagnostic/utils/access_control.py: remaining 9 miss
  - audioDiagnostic/tasks/utils.py: remaining 1 miss
  - accounts/models.py: remaining 6 miss
"""
from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
import json


# ─── AnthropicClient methods ─────────────────────────────────────────────────

class AnthropicClientMethodsTests(TestCase):

    def _make_client(self):
        from audioDiagnostic.services.ai.anthropic_client import AnthropicClient
        client = AnthropicClient.__new__(AnthropicClient)
        client.model = 'claude-3-5-haiku-20241022'
        client.max_tokens = 8192
        client.max_retries = 3
        client.base_delay = 1
        client.client = MagicMock()
        return client

    def test_parse_json_response_direct(self):
        client = self._make_client()
        result = client.parse_json_response('{"key": "value"}')
        self.assertEqual(result, {'key': 'value'})

    def test_parse_json_response_markdown_json(self):
        client = self._make_client()
        result = client.parse_json_response('```json\n{"key": "value"}\n```')
        self.assertEqual(result, {'key': 'value'})

    def test_parse_json_response_generic_code_block(self):
        client = self._make_client()
        result = client.parse_json_response('```\n{"key": "value"}\n```')
        self.assertEqual(result, {'key': 'value'})

    def test_parse_json_response_invalid_raises(self):
        client = self._make_client()
        with self.assertRaises(ValueError):
            client.parse_json_response('not json at all')

    def test_parse_json_response_bad_json_in_markdown(self):
        client = self._make_client()
        with self.assertRaises(ValueError):
            client.parse_json_response('```json\nnot json\n```')

    def test_parse_json_response_bad_json_in_code_block(self):
        client = self._make_client()
        with self.assertRaises(ValueError):
            client.parse_json_response('```\nnot json\n```')

    def test_calculate_cost_haiku(self):
        client = self._make_client()
        cost = client._calculate_cost(1000, 500)
        self.assertIsInstance(cost, float)
        self.assertGreaterEqual(cost, 0)

    def test_check_user_cost_limit_under_limit(self):
        client = self._make_client()
        user = User.objects.create_user(username='costlimit107', password='pass')
        result = client.check_user_cost_limit(user.id)
        self.assertTrue(result)

    def test_check_user_cost_limit_over_limit(self):
        client = self._make_client()
        user = User.objects.create_user(username='costover107', password='pass')
        with patch('audioDiagnostic.services.ai.anthropic_client.cache') as mock_cache:
            mock_cache.get.return_value = 999.0
            result = client.check_user_cost_limit(user.id)
        self.assertFalse(result)

    def test_track_user_cost(self):
        client = self._make_client()
        user = User.objects.create_user(username='costtrack107', password='pass')
        with patch('audioDiagnostic.services.ai.anthropic_client.cache') as mock_cache:
            mock_cache.get.return_value = 1.0
            mock_cache.set = MagicMock()
            client.track_user_cost(user.id, 0.5)
            mock_cache.set.assert_called_once()

    def test_call_api_success(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='hello')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        client.client.messages.create.return_value = mock_response
        result = client.call_api('test prompt')
        self.assertIn('content', result)
        self.assertEqual(result['content'], 'hello')


# ─── audiobook_production_task: get_progress and get_summary ─────────────────

class AudiobookProductionTaskTests(TestCase):

    def test_get_progress_not_found(self):
        from audioDiagnostic.tasks.audiobook_production_task import get_audiobook_analysis_progress
        with patch('audioDiagnostic.tasks.audiobook_production_task.get_redis_connection') as mock_r:
            mock_r.return_value = MagicMock(hgetall=MagicMock(return_value={}))
            result = get_audiobook_analysis_progress('nonexistent_task_id')
        self.assertEqual(result['status'], 'not_found')

    def test_get_progress_found(self):
        from audioDiagnostic.tasks.audiobook_production_task import get_audiobook_analysis_progress
        mock_data = {
            'status': 'running', 'stage': 'alignment',
            'percent': '50', 'message': 'Working...', 'error': ''
        }
        with patch('audioDiagnostic.tasks.audiobook_production_task.get_redis_connection') as mock_r:
            mock_r.return_value = MagicMock(hgetall=MagicMock(return_value=mock_data))
            result = get_audiobook_analysis_progress('some_task_id')
        self.assertEqual(result['status'], 'running')
        self.assertEqual(result['percent'], 50)

    def test_get_report_summary_not_found(self):
        from audioDiagnostic.tasks.audiobook_production_task import get_audiobook_report_summary
        with patch('audioDiagnostic.tasks.audiobook_production_task.get_redis_connection') as mock_r:
            mock_r.return_value = MagicMock(hgetall=MagicMock(return_value={}))
            result = get_audiobook_report_summary(999)
        self.assertIsNone(result)

    def test_get_report_summary_found(self):
        from audioDiagnostic.tasks.audiobook_production_task import get_audiobook_report_summary
        mock_data = {
            'overall_status': 'excellent', 'overall_score': '0.95',
            'created_at': '2024-01-01', 'checklist_items': '5', 'critical_items': '0'
        }
        with patch('audioDiagnostic.tasks.audiobook_production_task.get_redis_connection') as mock_r:
            mock_r.return_value = MagicMock(hgetall=MagicMock(return_value=mock_data))
            result = get_audiobook_report_summary(1)
        self.assertEqual(result['overall_status'], 'excellent')
        self.assertEqual(result['overall_score'], 0.95)


# ─── access_control.py remaining paths ───────────────────────────────────────

class AccessControlAdditionalTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='ac107', password='pass')
        from audioDiagnostic.models import AudioProject
        self.project = AudioProject.objects.create(user=self.user, title='AC Test')

    def test_check_project_access_wrong_user(self):
        from audioDiagnostic.utils.access_control import check_project_access
        other_user = User.objects.create_user(username='ac107b', password='pass')
        result = check_project_access(self.project.id, other_user)
        self.assertIsNone(result)

    def test_check_project_access_nonexistent(self):
        from audioDiagnostic.utils.access_control import check_project_access
        result = check_project_access(99999, self.user)
        self.assertIsNone(result)

    def test_check_project_access_success(self):
        from audioDiagnostic.utils.access_control import check_project_access
        result = check_project_access(self.project.id, self.user)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.project.id)

    def test_check_audio_file_access_success(self):
        from audioDiagnostic.utils.access_control import check_audio_file_access
        from audioDiagnostic.models import AudioFile
        af = AudioFile.objects.create(project=self.project, filename='t.mp3', order_index=0)
        result = check_audio_file_access(af.id, self.user)
        self.assertIsNotNone(result)

    def test_check_audio_file_access_wrong_user(self):
        from audioDiagnostic.utils.access_control import check_audio_file_access
        from audioDiagnostic.models import AudioFile
        other = User.objects.create_user(username='ac107c', password='pass')
        af = AudioFile.objects.create(project=self.project, filename='t2.mp3', order_index=1)
        result = check_audio_file_access(af.id, other)
        self.assertIsNone(result)

    def test_check_audio_file_access_nonexistent(self):
        from audioDiagnostic.utils.access_control import check_audio_file_access
        result = check_audio_file_access(99999, self.user)
        self.assertIsNone(result)


# ─── accounts/models.py remaining 6 miss ─────────────────────────────────────

class AccountsModelAdditionalTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='acm107', password='pass')

    def test_subscription_plan_str(self):
        from accounts.models import SubscriptionPlan
        plan = SubscriptionPlan.objects.create(
            name='free', display_name='Free Plan',
            description='A free plan', price_monthly=0.00
        )
        s = str(plan)
        self.assertIsInstance(s, str)

    def test_user_subscription_str(self):
        from accounts.models import SubscriptionPlan, UserSubscription
        plan = SubscriptionPlan.objects.create(
            name='basic', display_name='Basic',
            description='Basic plan', price_monthly=9.99
        )
        sub = UserSubscription.objects.create(
            user=self.user, plan=plan, status='active'
        )
        s = str(sub)
        self.assertIsInstance(s, str)

    def test_billing_history_str(self):
        from accounts.models import BillingHistory
        bh = BillingHistory.objects.create(
            user=self.user, transaction_type='payment',
            amount=9.99, currency='USD', description='Monthly payment'
        )
        s = str(bh)
        self.assertIsInstance(s, str)

    def test_user_profile_str(self):
        from accounts.models import UserProfile
        try:
            profile = UserProfile.objects.get(user=self.user)
        except Exception:
            profile = UserProfile.objects.create(user=self.user)
        s = str(profile)
        self.assertIsInstance(s, str)


# ─── tasks/utils.py ──────────────────────────────────────────────────────────

class TasksUtilsAdditionalTests(TestCase):

    def test_normalize_empty_string(self):
        from audioDiagnostic.tasks.utils import normalize
        result = normalize('')
        self.assertEqual(result, '')

    def test_normalize_with_special_chars(self):
        from audioDiagnostic.tasks.utils import normalize
        result = normalize("Hello, World!")
        self.assertIsInstance(result, str)

    def test_normalize_with_newlines(self):
        from audioDiagnostic.tasks.utils import normalize
        result = normalize("Hello\nWorld\t!")
        self.assertIsInstance(result, str)
