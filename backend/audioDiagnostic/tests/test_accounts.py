"""
Tests for accounts app (views.py, serializers.py).
Placed in audioDiagnostic/tests/ so they are discovered by
  python manage.py test audioDiagnostic.tests
Coverage source includes 'accounts' so these run counts towards accounts/ files.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from unittest.mock import patch, MagicMock
from datetime import timedelta

from accounts.models import SubscriptionPlan, UserSubscription, UsageTracking, BillingHistory, UserProfile
from accounts.serializers import (
    UserRegistrationSerializer, UserProfileSerializer,
    SubscriptionPlanSerializer, UserSubscriptionSerializer,
    UsageTrackingSerializer, BillingHistorySerializer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_free_plan():
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name='free',
        defaults={
            'display_name': 'Free Trial',
            'description': 'Free 7-day trial',
            'price_monthly': 0,
            'max_projects_per_month': 3,
            'max_audio_duration_minutes': 60,
            'max_file_size_mb': 50,
            'max_storage_gb': 1,
        }
    )
    return plan


def _create_basic_plan():
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name='basic',
        defaults={
            'display_name': 'Basic Plan',
            'description': 'Basic plan',
            'price_monthly': 19.99,
            'max_projects_per_month': 0,
            'max_audio_duration_minutes': 0,
            'max_file_size_mb': 500,
            'max_storage_gb': 10,
        }
    )
    return plan


def _register_user(client, username='testuser', email='test@example.com'):
    return client.post('/api/auth/register/', {
        'username': username,
        'email': email,
        'password': 'Str0ngPass#1',
        'password_confirm': 'Str0ngPass#1',
    }, format='json')


# ---------------------------------------------------------------------------
# Registration serializer tests
# ---------------------------------------------------------------------------

class UserRegistrationSerializerTests(TestCase):
    def test_valid_registration(self):
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'Str0ngPass#1',
            'password_confirm': 'Str0ngPass#1',
        }
        s = UserRegistrationSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_passwords_do_not_match(self):
        data = {
            'username': 'newuser2',
            'email': 'new2@example.com',
            'password': 'Str0ngPass#1',
            'password_confirm': 'WrongPass#1',
        }
        s = UserRegistrationSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('non_field_errors', s.errors)

    def test_email_already_registered(self):
        User.objects.create_user('existing', 'exists@example.com', 'Pass123!')
        data = {
            'username': 'newname',
            'email': 'exists@example.com',
            'password': 'Str0ngPass#1',
            'password_confirm': 'Str0ngPass#1',
        }
        s = UserRegistrationSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('email', s.errors)

    def test_create_makes_user(self):
        data = {
            'username': 'createme',
            'email': 'createme@example.com',
            'password': 'Str0ngPass#1',
            'password_confirm': 'Str0ngPass#1',
        }
        s = UserRegistrationSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        user = s.save()
        self.assertEqual(user.username, 'createme')
        self.assertTrue(user.check_password('Str0ngPass#1'))

    def test_weak_password_rejected(self):
        data = {
            'username': 'weakpass',
            'email': 'weak@example.com',
            'password': '123',
            'password_confirm': '123',
        }
        s = UserRegistrationSerializer(data=data)
        self.assertFalse(s.is_valid())


# ---------------------------------------------------------------------------
# SubscriptionPlanSerializer tests
# ---------------------------------------------------------------------------

class SubscriptionPlanSerializerTests(TestCase):
    def setUp(self):
        self.plan = _create_free_plan()

    def test_serializer_includes_features(self):
        s = SubscriptionPlanSerializer(self.plan)
        data = s.data
        self.assertIn('features', data)
        self.assertIsInstance(data['features'], list)
        self.assertTrue(len(data['features']) > 0)

    def test_unlimited_projects_message(self):
        plan = _create_basic_plan()
        plan.max_projects_per_month = 0
        plan.save()
        s = SubscriptionPlanSerializer(plan)
        features = s.data['features']
        self.assertTrue(any('Unlimited' in f for f in features))

    def test_limited_projects_message(self):
        self.plan.max_projects_per_month = 5
        self.plan.save()
        s = SubscriptionPlanSerializer(self.plan)
        features = s.data['features']
        self.assertTrue(any('5 projects' in f for f in features))

    def test_priority_processing_feature(self):
        plan = _create_basic_plan()
        plan.priority_processing = True
        plan.save()
        s = SubscriptionPlanSerializer(plan)
        features = s.data['features']
        self.assertTrue(any('Priority' in f for f in features))

    def test_api_access_feature(self):
        plan = _create_basic_plan()
        plan.api_access = True
        plan.save()
        s = SubscriptionPlanSerializer(plan)
        features = s.data['features']
        self.assertTrue(any('API' in f for f in features))

    def test_custom_branding_feature(self):
        plan = _create_basic_plan()
        plan.custom_branding = True
        plan.save()
        s = SubscriptionPlanSerializer(plan)
        features = s.data['features']
        self.assertTrue(any('branding' in f.lower() for f in features))


# ---------------------------------------------------------------------------
# BillingHistorySerializer tests
# ---------------------------------------------------------------------------

class BillingHistorySerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('billtest', 'bill@test.com', 'pass')

    def test_formatted_amount_gbp(self):
        b = BillingHistory.objects.create(
            user=self.user,
            transaction_type='charge',
            amount=19.99,
            currency='GBP',
            description='Monthly subscription',
        )
        s = BillingHistorySerializer(b)
        self.assertEqual(s.data['formatted_amount'], '£19.99')

    def test_formatted_amount_usd(self):
        b = BillingHistory.objects.create(
            user=self.user,
            transaction_type='charge',
            amount=9.99,
            currency='USD',
            description='Test charge',
        )
        s = BillingHistorySerializer(b)
        self.assertEqual(s.data['formatted_amount'], '$9.99')

    def test_formatted_amount_eur(self):
        b = BillingHistory.objects.create(
            user=self.user,
            transaction_type='charge',
            amount=5.00,
            currency='EUR',
            description='Euro charge',
        )
        s = BillingHistorySerializer(b)
        self.assertEqual(s.data['formatted_amount'], '€5.00')

    def test_formatted_amount_unknown_currency(self):
        b = BillingHistory.objects.create(
            user=self.user,
            transaction_type='charge',
            amount=3.00,
            currency='JPY',
            description='Yen charge',
        )
        s = BillingHistorySerializer(b)
        # Falls back to currency code as symbol
        self.assertEqual(s.data['formatted_amount'], 'JPY3.00')


# ---------------------------------------------------------------------------
# UsageTrackingSerializer tests
# ---------------------------------------------------------------------------

class UsageTrackingSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('usagetest', 'usage@test.com', 'pass')

    def test_period_month_format(self):
        now = timezone.now()
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        u = UsageTracking.objects.create(
            user=self.user,
            period_start=period_start,
            period_end=period_start + timedelta(days=31),
        )
        s = UsageTrackingSerializer(u)
        # Should be like "January 2025"
        self.assertIn('period_month', s.data)
        # Verify it's a valid month string
        import calendar
        months = list(calendar.month_name)[1:]
        self.assertTrue(any(m in s.data['period_month'] for m in months))


# ---------------------------------------------------------------------------
# UserProfileSerializer tests
# ---------------------------------------------------------------------------

class UserProfileSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('proftest', 'prof@test.com', 'pass',
                                              first_name='John', last_name='Doe')
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_read_profile(self):
        s = UserProfileSerializer(self.profile)
        data = s.data
        self.assertEqual(data['username'], 'proftest')
        self.assertEqual(data['email'], 'prof@test.com')
        self.assertEqual(data['first_name'], 'John')
        self.assertEqual(data['last_name'], 'Doe')

    def test_update_profile(self):
        s = UserProfileSerializer(self.profile, data={
            'first_name': 'Jane',
            'last_name': 'Smith',
        }, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Jane')
        self.assertEqual(self.user.last_name, 'Smith')


# ---------------------------------------------------------------------------
# Account API endpoint tests
# ---------------------------------------------------------------------------

class AccountRegistrationAPITests(APITestCase):
    """Test registration, login, logout endpoints"""

    def setUp(self):
        _create_free_plan()

    @patch('accounts.views.stripe')
    def test_register_success(self, mock_stripe):
        mock_stripe.Customer.create.return_value = MagicMock(id='cus_test123')
        response = _register_user(self.client)
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

    @patch('accounts.views.stripe')
    def test_register_duplicate_email(self, mock_stripe):
        mock_stripe.Customer.create.return_value = MagicMock(id='cus_test123')
        _register_user(self.client, username='first', email='same@example.com')
        response = _register_user(self.client, username='second', email='same@example.com')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('accounts.views.stripe')
    def test_register_sets_auth_cookie(self, mock_stripe):
        mock_stripe.Customer.create.return_value = MagicMock(id='cus_test456')
        response = _register_user(self.client, username='cookieuser', email='cookie@example.com')
        if response.status_code in [200, 201]:
            self.assertIn('auth_token', response.cookies)

    @patch('accounts.views.stripe')
    def test_login_success(self, mock_stripe):
        mock_stripe.Customer.create.return_value = MagicMock(id='cus_test789')
        User.objects.create_user('logintest', 'login@example.com', 'Str0ngPass#1')
        response = self.client.post('/api/auth/login/', {
            'username': 'logintest',
            'password': 'Str0ngPass#1',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)

    def test_login_wrong_credentials(self):
        User.objects.create_user('badlogin', 'bad@example.com', 'Str0ngPass#1')
        response = self.client.post('/api/auth/login/', {
            'username': 'badlogin',
            'password': 'WrongPassword',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('accounts.views.stripe')
    def test_logout_clears_cookie(self, mock_stripe):
        mock_stripe.Customer.create.return_value = MagicMock(id='cus_logout')
        user = User.objects.create_user('logouttest', 'logout@example.com', 'Str0ngPass#1')
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.post('/api/auth/logout/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)


class AccountProfileAPITests(APITestCase):
    """Test profile and subscription endpoints"""

    def setUp(self):
        self.plan = _create_free_plan()
        self.user = User.objects.create_user('profileuser', 'profile@example.com', 'pass',
                                              first_name='Alice', last_name='Wonder')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_get_profile(self):
        UserProfile.objects.get_or_create(user=self.user)
        response = self.client.get('/api/auth/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_subscription_plans(self):
        response = self.client.get('/api/auth/plans/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_get_subscription_unauthenticated(self):
        self.client.credentials()
        response = self.client.get('/api/auth/subscription/')
        self.assertIn(response.status_code, [401, 403])

    def test_data_export_returns_export(self):
        response = self.client.get('/api/auth/data-export/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('account', response.data)
        self.assertIn('export_generated_at', response.data)
        # password hash must not be in response
        self.assertNotIn('password', str(response.data))

    def test_usage_tracking_endpoint(self):
        response = self.client.get('/api/auth/usage/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_billing_history_endpoint(self):
        response = self.client.get('/api/auth/billing/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AccountSubscriptionAPITests(APITestCase):
    """Tests for subscription management endpoints"""

    def setUp(self):
        self.plan = _create_free_plan()
        self.user = User.objects.create_user('subuser', 'sub@example.com', 'pass')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.subscription, _ = UserSubscription.objects.get_or_create(
            user=self.user,
            defaults={
                'plan': self.plan,
                'status': 'active',
                'trial_end': timezone.now() + timedelta(days=7),
            }
        )

    def test_get_subscription(self):
        response = self.client.get('/api/auth/subscription/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('accounts.views.stripe')
    def test_checkout_no_plan_id(self, mock_stripe):
        response = self.client.post('/api/auth/checkout/', {}, format='json')
        self.assertIn(response.status_code, [400, 404])

    @patch('accounts.views.stripe')
    def test_cancel_subscription_no_stripe_id(self, mock_stripe):
        response = self.client.post('/api/auth/cancel-subscription/')
        # No stripe subscription ID means error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('accounts.views.stripe')
    def test_cancel_subscription_with_stripe_id(self, mock_stripe):
        mock_stripe.Subscription.modify.return_value = MagicMock()
        self.subscription.stripe_subscription_id = 'sub_test123'
        self.subscription.save()
        response = self.client.post('/api/auth/cancel-subscription/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

    def test_usage_limits_check_endpoint(self):
        response = self.client.get('/api/auth/usage-limits/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('subscription_active', response.data)
        self.assertIn('limits_exceeded', response.data)
