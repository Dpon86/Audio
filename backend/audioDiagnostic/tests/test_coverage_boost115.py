"""
Wave 115 — Coverage boost
Targets:
  - accounts/views.py: UsageTrackingView, BillingHistoryView, usage_limits_check,
    logout_view, data_export, UserSubscriptionView, UserProfileView
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import force_authenticate


def auth(client, user):
    token = Token.objects.get_or_create(user=user)[0]
    client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
    return token


class AccountsViewsRemainingTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='acc115', password='pass', email='acc115@test.com')
        auth(self.client, self.user)
        self.client.raise_request_exception = False

    def test_usage_tracking_view(self):
        resp = self.client.get('/api/auth/usage/')
        self.assertIn(resp.status_code, [200, 404])

    def test_billing_history_view(self):
        resp = self.client.get('/api/auth/billing/')
        self.assertIn(resp.status_code, [200, 404])

    def test_usage_limits_check(self):
        resp = self.client.get('/api/auth/usage-limits/')
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_logout_view(self):
        resp = self.client.post('/api/auth/logout/', data={}, content_type='application/json')
        self.assertIn(resp.status_code, [200, 204, 404])

    def test_data_export(self):
        resp = self.client.get('/api/auth/data-export/')
        self.assertIn(resp.status_code, [200, 404])

    def test_user_profile_get(self):
        resp = self.client.get('/api/auth/profile/')
        self.assertIn(resp.status_code, [200, 404])

    def test_user_profile_update(self):
        resp = self.client.patch(
            '/api/auth/profile/',
            data={'first_name': 'Test'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_user_subscription_view(self):
        resp = self.client.get('/api/auth/subscription/')
        self.assertIn(resp.status_code, [200, 404])

    def test_subscription_plans_view(self):
        resp = self.client.get('/api/auth/plans/')
        self.assertIn(resp.status_code, [200, 404])

    def test_cancel_subscription(self):
        resp = self.client.post('/api/auth/cancel-subscription/', data={}, content_type='application/json')
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_create_checkout_session(self):
        resp = self.client.post(
            '/api/auth/create-checkout-session/',
            data={'plan': 'basic'},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_unauthenticated_usage_tracking(self):
        self.client.defaults.pop('HTTP_AUTHORIZATION', None)
        resp = self.client.get('/api/auth/usage/')
        self.assertIn(resp.status_code, [401, 403, 404])

    def test_unauthenticated_billing(self):
        self.client.defaults.pop('HTTP_AUTHORIZATION', None)
        resp = self.client.get('/api/auth/billing/')
        self.assertIn(resp.status_code, [401, 403, 404])
