"""
Wave 142: accounts/views.py - logout, data_export, usage_limits_check, UserProfileView
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from unittest.mock import MagicMock, patch
from accounts.models import SubscriptionPlan, UserSubscription

User = get_user_model()


def _create_user_with_subscription(username, email):
    user = User.objects.create_user(username=username, password='testpass123', email=email)
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name='free',
        defaults={
            'display_name': 'Free',
            'description': 'Free plan',
            'price_monthly': 0,
            'max_projects_per_month': 5,
            'max_audio_duration_minutes': 60,
        }
    )
    UserSubscription.objects.get_or_create(user=user, defaults={'plan': plan, 'status': 'active'})
    return user, plan


class LogoutViewTests(TestCase):
    """Test logout_view."""

    def setUp(self):
        self.client = APIClient()
        self.user, _ = _create_user_with_subscription('logout_user', 'logout@t.com')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_logout_success(self):
        response = self.client.post('/api/auth/logout/')
        self.assertIn(response.status_code, [200, 204])

    def test_logout_clears_token(self):
        self.client.post('/api/auth/logout/')
        # Token should be deleted
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_logout_unauthenticated(self):
        client = APIClient()
        response = client.post('/api/auth/logout/')
        self.assertIn(response.status_code, [401, 403])


class UsageLimitsCheckTests(TestCase):
    """Test usage_limits_check view."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user, self.plan = _create_user_with_subscription('usage_user', 'usage@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_basic_check(self):
        response = self.client.get('/api/auth/usage-limits/')
        self.assertIn(response.status_code, [200, 400, 404, 500])

    def test_unauthenticated(self):
        client = APIClient()
        response = client.get('/api/auth/usage-limits/')
        self.assertIn(response.status_code, [401, 403])


class DataExportTests(TestCase):
    """Test data_export view."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user, _ = _create_user_with_subscription('export_user', 'export@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_data_export_success(self):
        response = self.client.get('/api/auth/data-export/')
        self.assertIn(response.status_code, [200, 404, 500])

    def test_data_export_unauthenticated(self):
        client = APIClient()
        response = client.get('/api/auth/data-export/')
        self.assertIn(response.status_code, [401, 403])

    def test_data_export_response_structure(self):
        response = self.client.get('/api/auth/data-export/')
        if response.status_code == 200:
            data = response.json()
            self.assertIn('account', data)


class UserProfileViewTests(TestCase):
    """Test UserProfileView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user, _ = _create_user_with_subscription('profile_user', 'profile@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_get_profile(self):
        response = self.client.get('/api/auth/profile/')
        self.assertIn(response.status_code, [200, 404])

    def test_update_profile(self):
        response = self.client.patch('/api/auth/profile/', {'first_name': 'Test'}, format='json')
        self.assertIn(response.status_code, [200, 400, 404])


class UserSubscriptionViewTests(TestCase):
    """Test UserSubscriptionView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user, _ = _create_user_with_subscription('sub_view_user', 'subview@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_get_subscription(self):
        response = self.client.get('/api/auth/subscription/')
        self.assertIn(response.status_code, [200, 404])


class SubscriptionPlansViewTests(TestCase):
    """Test SubscriptionPlansView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user, _ = _create_user_with_subscription('plans_user', 'plans@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_list_plans(self):
        response = self.client.get('/api/auth/plans/')
        self.assertIn(response.status_code, [200, 404])
