"""
Tests for audioDiagnostic/utils/access_control.py
Targets 140 stmts at 0% → target 80%+
"""
from django.test import TestCase, RequestFactory
from unittest.mock import MagicMock, patch, PropertyMock
from rest_framework.test import APIRequestFactory
from rest_framework import status

from audioDiagnostic.utils.access_control import (
    require_ai_feature,
    check_ai_cost_limit,
    track_ai_cost,
    get_user_ai_usage,
    require_subscription_tier,
    check_usage_limit,
)


def _make_user_with_subscription(username='u1', is_active=True, feature_value=True,
                                 plan_name='basic', ai_monthly_cost_limit=10.0,
                                 status_str='active'):
    """Helper: build a mock user with a subscription"""
    plan = MagicMock()
    plan.name = plan_name
    plan.display_name = plan_name.title()
    plan.ai_monthly_cost_limit = ai_monthly_cost_limit
    plan.ai_duplicate_detection = feature_value
    plan.ai_transcription = feature_value
    plan.ai_pdf_comparison = feature_value

    subscription = MagicMock()
    subscription.plan = plan
    subscription.is_active = is_active
    subscription.status = status_str

    user = MagicMock()
    user.id = 1
    user.username = username
    user.subscription = subscription

    return user


class RequireAiFeatureDecoratorTests(TestCase):
    """Tests for the @require_ai_feature decorator"""

    def _make_view(self, feature='ai_duplicate_detection'):
        @require_ai_feature(feature)
        def fake_view(request, *args, **kwargs):
            return 'SUCCESS'
        return fake_view

    def _make_request(self, user):
        request = MagicMock()
        request.user = user
        return request

    def test_user_without_subscription_returns_402(self):
        view = self._make_view()
        user = MagicMock()
        user.id = 99
        del user.subscription  # No subscription attribute
        # Simulate missing subscription attribute
        type(user).subscription = PropertyMock(side_effect=AttributeError)
        request = self._make_request(user)
        # MagicMock hasattr returns True by default; skip; just test the actual hasattr
        # Instead test via a real object
        class NoSubUser:
            id = 99
            username = 'nosubuser'
        request.user = NoSubUser()
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertTrue(response.data['upgrade_required'])

    def test_inactive_subscription_trialing_returns_402(self):
        view = self._make_view()
        user = _make_user_with_subscription(is_active=False, status_str='trialing')
        response = view(self._make_request(user))
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertIn('trial', response.data['error'].lower())

    def test_inactive_subscription_canceled_returns_402(self):
        view = self._make_view()
        user = _make_user_with_subscription(is_active=False, status_str='canceled')
        response = view(self._make_request(user))
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertIn('canceled', response.data['error'].lower())

    def test_inactive_subscription_past_due_returns_402(self):
        view = self._make_view()
        user = _make_user_with_subscription(is_active=False, status_str='past_due')
        response = view(self._make_request(user))
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertIn('payment', response.data['error'].lower())

    def test_inactive_subscription_unknown_status_returns_402(self):
        view = self._make_view()
        user = _make_user_with_subscription(is_active=False, status_str='suspended')
        response = view(self._make_request(user))
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_plan_missing_feature_returns_402(self):
        view = self._make_view('ai_duplicate_detection')
        user = _make_user_with_subscription(is_active=True, feature_value=False)
        user.subscription.plan.ai_duplicate_detection = False
        response = view(self._make_request(user))
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(response.data['feature'], 'ai_duplicate_detection')

    def test_plan_missing_ai_transcription_recommends_pro(self):
        view = self._make_view('ai_transcription')
        user = _make_user_with_subscription(is_active=True, feature_value=False)
        user.subscription.plan.ai_transcription = False
        response = view(self._make_request(user))
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(response.data['recommended_plan'], 'pro')

    def test_plan_missing_ai_pdf_comparison_recommends_pro(self):
        view = self._make_view('ai_pdf_comparison')
        user = _make_user_with_subscription(is_active=True, feature_value=False)
        user.subscription.plan.ai_pdf_comparison = False
        response = view(self._make_request(user))
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(response.data['recommended_plan'], 'pro')

    def test_plan_missing_unknown_feature_recommends_pro(self):
        view = self._make_view('unknown_feature')
        user = _make_user_with_subscription(is_active=True, feature_value=False)
        user.subscription.plan.unknown_feature = False
        response = view(self._make_request(user))
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(response.data['recommended_plan'], 'pro')

    def test_all_checks_pass_calls_view(self):
        view = self._make_view('ai_duplicate_detection')
        user = _make_user_with_subscription(is_active=True, feature_value=True)
        result = view(self._make_request(user))
        self.assertEqual(result, 'SUCCESS')


class CheckAiCostLimitTests(TestCase):
    """Tests for check_ai_cost_limit()"""

    @patch('audioDiagnostic.utils.access_control.cache')
    def test_plan_has_zero_budget_not_allowed(self, mock_cache):
        user = _make_user_with_subscription(ai_monthly_cost_limit=0.0)
        allowed, remaining, msg = check_ai_cost_limit(user, 0.50)
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0.0)

    @patch('audioDiagnostic.utils.access_control.cache')
    def test_within_budget(self, mock_cache):
        mock_cache.get.return_value = 2.0
        user = _make_user_with_subscription(ai_monthly_cost_limit=10.0)
        allowed, remaining, msg = check_ai_cost_limit(user, 1.0)
        self.assertTrue(allowed)
        self.assertAlmostEqual(remaining, 8.0)

    @patch('audioDiagnostic.utils.access_control.cache')
    def test_exceeds_budget(self, mock_cache):
        mock_cache.get.return_value = 9.5
        user = _make_user_with_subscription(ai_monthly_cost_limit=10.0)
        allowed, remaining, msg = check_ai_cost_limit(user, 1.0)
        self.assertFalse(allowed)
        self.assertAlmostEqual(remaining, 0.5)
        self.assertIn('over limit', msg)

    def test_no_subscription_returns_error(self):
        class NoSubUser:
            id = 5
            username = 'nosub'
        allowed, remaining, msg = check_ai_cost_limit(NoSubUser(), 1.0)
        self.assertFalse(allowed)
        self.assertIn('subscription', msg.lower())

    @patch('audioDiagnostic.utils.access_control.cache')
    def test_unexpected_exception_returns_error(self, mock_cache):
        mock_cache.get.side_effect = Exception('boom')
        user = _make_user_with_subscription(ai_monthly_cost_limit=10.0)
        allowed, remaining, msg = check_ai_cost_limit(user, 1.0)
        self.assertFalse(allowed)
        self.assertIn('Error', msg)


class TrackAiCostTests(TestCase):
    """Tests for track_ai_cost()"""

    @patch('audioDiagnostic.utils.access_control.cache')
    def test_adds_cost_to_existing(self, mock_cache):
        mock_cache.get.return_value = 3.0
        user = MagicMock()
        user.id = 1
        user.username = 'tester'
        total = track_ai_cost(user, 2.0)
        self.assertAlmostEqual(total, 5.0)
        mock_cache.set.assert_called_once()

    @patch('audioDiagnostic.utils.access_control.cache')
    def test_adds_cost_from_zero(self, mock_cache):
        mock_cache.get.return_value = 0.0
        user = MagicMock()
        user.id = 2
        user.username = 'newuser'
        total = track_ai_cost(user, 1.5)
        self.assertAlmostEqual(total, 1.5)

    @patch('audioDiagnostic.utils.access_control.cache')
    def test_exception_returns_zero(self, mock_cache):
        mock_cache.get.side_effect = Exception('cache down')
        user = MagicMock()
        user.id = 3
        user.username = 'erruser'
        result = track_ai_cost(user, 0.5)
        self.assertEqual(result, 0.0)


class GetUserAiUsageTests(TestCase):
    """Tests for get_user_ai_usage()"""

    @patch('audioDiagnostic.utils.access_control.cache')
    def test_returns_usage_dict(self, mock_cache):
        mock_cache.get.return_value = 3.5
        user = _make_user_with_subscription(ai_monthly_cost_limit=10.0)
        result = get_user_ai_usage(user)
        self.assertIn('current_usage', result)
        self.assertIn('monthly_limit', result)
        self.assertIn('remaining', result)
        self.assertIn('usage_percentage', result)
        self.assertIn('month', result)
        self.assertAlmostEqual(result['current_usage'], 3.5)
        self.assertAlmostEqual(result['monthly_limit'], 10.0)
        self.assertAlmostEqual(result['remaining'], 6.5)

    @patch('audioDiagnostic.utils.access_control.cache')
    def test_zero_monthly_limit_usage_percentage(self, mock_cache):
        mock_cache.get.return_value = 0.0
        user = _make_user_with_subscription(ai_monthly_cost_limit=0.0)
        result = get_user_ai_usage(user)
        self.assertEqual(result['usage_percentage'], 0.0)

    def test_exception_returns_default_dict(self):
        class NoSubUser:
            id = 9
            username = 'nosubber'
        result = get_user_ai_usage(NoSubUser())
        self.assertEqual(result['current_usage'], 0.0)
        self.assertEqual(result['plan_name'], 'Unknown')


class RequireSubscriptionTierTests(TestCase):
    """Tests for @require_subscription_tier"""

    def _make_view(self, tier='basic'):
        @require_subscription_tier(tier)
        def fake_view(request, *args, **kwargs):
            return 'SUCCESS'
        return fake_view

    def _make_request(self, user):
        request = MagicMock()
        request.user = user
        return request

    def test_no_subscription_returns_402(self):
        view = self._make_view('basic')

        class NoSubUser:
            id = 1
            username = 'nosubber'

        request = self._make_request(NoSubUser())
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_sufficient_tier_passes(self):
        view = self._make_view('basic')
        user = _make_user_with_subscription(plan_name='pro')
        result = view(self._make_request(user))
        self.assertEqual(result, 'SUCCESS')

    def test_exact_tier_passes(self):
        view = self._make_view('basic')
        user = _make_user_with_subscription(plan_name='basic')
        result = view(self._make_request(user))
        self.assertEqual(result, 'SUCCESS')

    def test_insufficient_tier_returns_402(self):
        view = self._make_view('pro')
        user = _make_user_with_subscription(plan_name='basic')
        user.subscription.plan.name = 'basic'
        response = view(self._make_request(user))
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertIn('required_tier', response.data)


class CheckUsageLimitTests(TestCase):
    """Tests for check_usage_limit()"""

    def _make_user(self, max_projects=10):
        plan = MagicMock()
        plan.max_projects_per_month = max_projects
        plan.max_audio_duration_minutes = 60
        plan.max_storage_gb = 2

        subscription = MagicMock()
        subscription.plan = plan

        user = MagicMock()
        user.id = 1
        user.subscription = subscription
        return user

    @patch('audioDiagnostic.utils.access_control.UsageTracking', create=True)
    @patch('audioDiagnostic.utils.access_control.timezone', create=True)
    def test_unknown_metric_returns_error(self, mock_tz, mock_ut):
        """check_usage_limit with an unknown metric key returns False"""
        mock_tz.now.return_value = MagicMock()
        usage = MagicMock()
        usage.projects_created = 0
        mock_ut.objects.get_or_create.return_value = (usage, True)

        user = self._make_user()
        allowed, current, limit, msg = check_usage_limit(user, 'unknown_metric')
        self.assertFalse(allowed)
        self.assertIn('Unknown metric', msg)

    def test_exception_returns_error(self):
        """When an exception occurs, returns (False, 0, 0, error_msg)"""
        class BadUser:
            id = 2
            subscription = None  # Will raise AttributeError

        allowed, current, limit, msg = check_usage_limit(BadUser(), 'projects')
        self.assertFalse(allowed)
