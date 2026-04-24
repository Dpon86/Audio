"""
Wave 149: accounts/models_feedback.py - model methods, accounts/models.py remaining
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models_feedback import FeatureFeedback, FeatureFeedbackSummary
from accounts.models import SubscriptionPlan, UserSubscription
from rest_framework.test import force_authenticate

User = get_user_model()


class FeatureFeedbackModelTests(TestCase):
    """Test FeatureFeedback model methods."""

    def setUp(self):
        self.user = User.objects.create_user(username='fb149', password='pass', email='fb149@t.com')

    def _create_feedback(self, rating, worked=True):
        return FeatureFeedback.objects.create(
            user=self.user,
            feature='ai_duplicate_detection',
            rating=rating,
            worked_as_expected=worked,
        )

    def test_str_representation(self):
        fb = self._create_feedback(5, True)
        s = str(fb)
        self.assertIn('fb149', s)

    def test_is_positive_true(self):
        fb = self._create_feedback(5, True)
        self.assertTrue(fb.is_positive)

    def test_is_positive_false_low_rating(self):
        fb = self._create_feedback(3, True)
        self.assertFalse(fb.is_positive)

    def test_is_positive_false_not_worked(self):
        fb = self._create_feedback(5, False)
        self.assertFalse(fb.is_positive)

    def test_needs_attention_true_low_rating(self):
        fb = self._create_feedback(2, True)
        self.assertTrue(fb.needs_attention)

    def test_needs_attention_true_not_worked(self):
        fb = self._create_feedback(4, False)
        self.assertTrue(fb.needs_attention)

    def test_needs_attention_false(self):
        fb = self._create_feedback(4, True)
        self.assertFalse(fb.needs_attention)

    def test_rating_1(self):
        fb = self._create_feedback(1, False)
        self.assertTrue(fb.needs_attention)
        self.assertFalse(fb.is_positive)


class FeatureFeedbackSummaryModelTests(TestCase):
    """Test FeatureFeedbackSummary model."""

    def test_create_summary(self):
        summary = FeatureFeedbackSummary.objects.create(
            feature='transcription',
            total_responses=10,
            average_rating=4.2,
            positive_count=8,
            needs_attention_count=2,
        )
        self.assertEqual(summary.feature, 'transcription')
        self.assertEqual(summary.total_responses, 10)


class SubscriptionPlanModelTests(TestCase):
    """Test SubscriptionPlan model methods."""

    def test_plan_str(self):
        plan = SubscriptionPlan.objects.create(
            name='pro',
            display_name='Pro',
            description='Pro plan',
            price_monthly=9.99,
        )
        s = str(plan)
        self.assertIn('Pro', s)

    def test_plan_is_free(self):
        plan = SubscriptionPlan.objects.create(
            name='free_test',
            display_name='Free Test',
            description='Free plan',
            price_monthly=0,
        )
        # Just ensure it exists and can be accessed
        self.assertEqual(plan.price_monthly, 0)


class UserSubscriptionModelTests(TestCase):
    """Test UserSubscription model methods."""

    def setUp(self):
        self.user = User.objects.create_user(username='usub149', password='pass', email='usub149@t.com')
        self.plan = SubscriptionPlan.objects.create(
            name='test_plan149',
            display_name='Test Plan 149',
            description='Test',
            price_monthly=5.00,
        )

    def test_subscription_str(self):
        sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='active',
        )
        s = str(sub)
        self.assertIn('usub149', s)

    def test_is_active_property(self):
        sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='active',
        )
        self.assertTrue(sub.is_active)

    def test_is_trial_property(self):
        sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='trialing',
        )
        self.assertTrue(sub.is_trial)

    def test_is_not_active(self):
        sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='canceled',
        )
        self.assertFalse(sub.is_active)
