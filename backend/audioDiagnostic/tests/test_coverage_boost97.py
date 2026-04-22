"""
Wave 97 — Coverage boost
Targets:
  - accounts/webhooks.py handle_ helper functions
  - audioDiagnostic/utils/__init__.py (get_redis_host, other paths)
"""
from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock


# ─── handle_checkout_completed tests ─────────────────────────────────────────

class HandleCheckoutCompletedTests(TestCase):

    def setUp(self):
        from accounts.models import SubscriptionPlan, UserSubscription
        self.user = User.objects.create_user(username='webhook_user', password='pass123')
        self.plan = SubscriptionPlan.objects.create(
            name='basic',
            display_name='Basic Plan',
            description='Basic',
            price_monthly=9.99,
        )

    def test_checkout_creates_subscription(self):
        from accounts.webhooks import handle_checkout_completed
        session = {
            'metadata': {
                'user_id': str(self.user.id),
                'plan_id': str(self.plan.id),
                'billing_cycle': 'monthly',
            },
            'subscription': 'sub_test123',
            'customer': 'cus_test123',
        }
        # Should not raise
        handle_checkout_completed(session)
        from accounts.models import UserSubscription
        self.assertTrue(UserSubscription.objects.filter(user=self.user).exists())

    def test_checkout_updates_existing_subscription(self):
        from accounts.webhooks import handle_checkout_completed
        from accounts.models import UserSubscription
        UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='trialing',
            stripe_customer_id='cus_old',
        )
        session = {
            'metadata': {
                'user_id': str(self.user.id),
                'plan_id': str(self.plan.id),
                'billing_cycle': 'yearly',
            },
            'subscription': 'sub_new123',
            'customer': 'cus_test456',
        }
        handle_checkout_completed(session)
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, 'active')

    def test_checkout_user_not_found(self):
        from accounts.webhooks import handle_checkout_completed
        session = {
            'metadata': {'user_id': '999999', 'plan_id': '1'},
            'subscription': 'sub_xyz',
            'customer': 'cus_xyz',
        }
        # Should not raise, just log error
        handle_checkout_completed(session)


# ─── handle_subscription_created tests ───────────────────────────────────────

class HandleSubscriptionCreatedTests(TestCase):

    def setUp(self):
        from accounts.models import SubscriptionPlan, UserSubscription
        self.user = User.objects.create_user(username='subtest', password='pass123')
        self.plan = SubscriptionPlan.objects.create(
            name='pro',
            display_name='Pro Plan',
            description='Pro',
            price_monthly=19.99,
        )
        self.sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='trialing',
            stripe_customer_id='cus_created',
        )

    def test_subscription_created(self):
        from accounts.webhooks import handle_subscription_created
        import time
        now = time.time()
        subscription = {
            'customer': 'cus_created',
            'id': 'sub_created123',
            'current_period_start': int(now),
            'current_period_end': int(now) + 2592000,  # 30 days
        }
        handle_subscription_created(subscription)
        from accounts.models import UserSubscription
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.stripe_subscription_id, 'sub_created123')

    def test_subscription_created_no_customer(self):
        from accounts.webhooks import handle_subscription_created
        import time
        now = time.time()
        subscription = {
            'customer': 'cus_nonexistent',
            'id': 'sub_xyz',
            'current_period_start': int(now),
            'current_period_end': int(now) + 2592000,
        }
        # Should not raise
        handle_subscription_created(subscription)


# ─── handle_subscription_updated tests ───────────────────────────────────────

class HandleSubscriptionUpdatedTests(TestCase):

    def setUp(self):
        from accounts.models import SubscriptionPlan, UserSubscription
        self.user = User.objects.create_user(username='subupdated', password='pass123')
        self.plan = SubscriptionPlan.objects.create(
            name='enterprise',
            display_name='Enterprise Plan',
            description='Enterprise',
            price_monthly=49.99,
        )
        self.sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='active',
            stripe_customer_id='cus_updated',
            stripe_subscription_id='sub_updated123',
        )

    def test_subscription_updated_to_past_due(self):
        from accounts.webhooks import handle_subscription_updated
        import time
        now = time.time()
        subscription = {
            'id': 'sub_updated123',
            'status': 'past_due',
            'current_period_start': int(now),
            'current_period_end': int(now) + 2592000,
        }
        handle_subscription_updated(subscription)
        from accounts.models import UserSubscription
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, 'past_due')

    def test_subscription_updated_not_found(self):
        from accounts.webhooks import handle_subscription_updated
        import time
        now = time.time()
        subscription = {
            'id': 'sub_notexist',
            'status': 'active',
            'current_period_start': int(now),
            'current_period_end': int(now) + 2592000,
        }
        # Should not raise
        handle_subscription_updated(subscription)


# ─── handle_subscription_cancelled tests ────────────────────────────────────

class HandleSubscriptionCancelledTests(TestCase):

    def setUp(self):
        from accounts.models import SubscriptionPlan, UserSubscription
        self.user = User.objects.create_user(username='subcancelled', password='pass123')
        self.plan = SubscriptionPlan.objects.create(
            name='free',
            display_name='Free Plan',
            description='Free',
            price_monthly=0.00,
        )
        self.sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='active',
            stripe_subscription_id='sub_cancel123',
        )

    def test_subscription_cancelled(self):
        from accounts.webhooks import handle_subscription_cancelled
        handle_subscription_cancelled({'id': 'sub_cancel123'})
        from accounts.models import UserSubscription
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, 'canceled')

    def test_subscription_cancelled_not_found(self):
        from accounts.webhooks import handle_subscription_cancelled
        handle_subscription_cancelled({'id': 'sub_doesnotexist'})
        # Should not raise


# ─── handle_payment_succeeded tests ──────────────────────────────────────────

class HandlePaymentSucceededTests(TestCase):

    def setUp(self):
        from accounts.models import SubscriptionPlan, UserSubscription
        self.user = User.objects.create_user(username='paysucc', password='pass123')
        self.plan = SubscriptionPlan.objects.create(
            name='basic',
            display_name='Basic Plan',
            description='Basic',
            price_monthly=9.99,
        )
        self.sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='active',
            stripe_customer_id='cus_paysucc',
        )

    def test_payment_succeeded(self):
        from accounts.webhooks import handle_payment_succeeded
        invoice = {
            'customer': 'cus_paysucc',
            'amount_paid': 999,  # $9.99 in cents
            'currency': 'usd',
            'id': 'inv_test123',
        }
        handle_payment_succeeded(invoice)
        from accounts.models import BillingHistory
        self.assertTrue(BillingHistory.objects.filter(user=self.user).exists())


# ─── handle_payment_failed tests ─────────────────────────────────────────────

class HandlePaymentFailedTests(TestCase):

    def setUp(self):
        from accounts.models import SubscriptionPlan, UserSubscription
        self.user = User.objects.create_user(username='payfail', password='pass123')
        self.plan = SubscriptionPlan.objects.create(
            name='basic',
            display_name='Basic Plan',
            description='Basic',
            price_monthly=9.99,
        )
        self.sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='active',
            stripe_customer_id='cus_payfail',
        )

    def test_payment_failed(self):
        from accounts.webhooks import handle_payment_failed
        invoice = {
            'customer': 'cus_payfail',
            'amount_due': 999,
            'currency': 'usd',
            'id': 'inv_fail123',
        }
        handle_payment_failed(invoice)
        from accounts.models import UserSubscription
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual(sub.status, 'past_due')


# ─── get_redis_host tests ─────────────────────────────────────────────────────

class GetRedisHostTests(TestCase):

    def test_get_redis_host_returns_string(self):
        from audioDiagnostic.utils import get_redis_host
        result = get_redis_host()
        self.assertIn(result, ['redis', 'localhost'])
