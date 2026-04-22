"""
Wave 88 — Coverage boost
Targets:
  - accounts/serializers.py (UserRegistrationSerializer, SubscriptionPlanSerializer)
  - accounts/models.py (SubscriptionPlan, UserSubscription, UsageTracking model methods)
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class UserRegistrationSerializerTests(TestCase):

    def test_password_mismatch(self):
        from accounts.serializers import UserRegistrationSerializer
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'StrongPassword123!',
            'password_confirm': 'DifferentPassword456!',
        }
        s = UserRegistrationSerializer(data=data)
        self.assertFalse(s.is_valid())

    def test_email_already_registered(self):
        from accounts.serializers import UserRegistrationSerializer
        User.objects.create_user(username='existing', email='exists@example.com', password='pass123')
        data = {
            'username': 'newuser',
            'email': 'exists@example.com',
            'password': 'StrongPassword123!',
            'password_confirm': 'StrongPassword123!',
        }
        s = UserRegistrationSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('email', s.errors)

    def test_valid_registration(self):
        from accounts.serializers import UserRegistrationSerializer
        data = {
            'username': 'brandnewuser',
            'email': 'brand@new.com',
            'password': 'StrongPassword123!',
            'password_confirm': 'StrongPassword123!',
        }
        s = UserRegistrationSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_create_user(self):
        from accounts.serializers import UserRegistrationSerializer
        data = {
            'username': 'createme',
            'email': 'createme@test.com',
            'password': 'StrongPassword123!',
            'password_confirm': 'StrongPassword123!',
        }
        s = UserRegistrationSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        user = s.save()
        self.assertEqual(user.email, 'createme@test.com')
        self.assertFalse(hasattr(user, 'password_confirm'))


class SubscriptionPlanSerializerTests(TestCase):

    def setUp(self):
        from accounts.models import SubscriptionPlan
        self.plan = SubscriptionPlan.objects.create(
            name='basic',
            display_name='Basic Plan',
            description='Basic features',
            price_monthly=19.99,
            price_yearly=199.99,
            max_projects_per_month=5,
            max_audio_duration_minutes=60,
            max_file_size_mb=100,
            max_storage_gb=10,
        )

    def test_serialize_plan(self):
        from accounts.serializers import SubscriptionPlanSerializer
        s = SubscriptionPlanSerializer(self.plan)
        data = s.data
        self.assertEqual(data['name'], 'basic')
        self.assertIn('features', data)
        self.assertIsInstance(data['features'], list)

    def test_unlimited_projects_feature(self):
        from accounts.serializers import SubscriptionPlanSerializer
        from accounts.models import SubscriptionPlan
        plan = SubscriptionPlan.objects.create(
            name='unlimited', display_name='Unlimited', description='',
            price_monthly=99.99, price_yearly=999.99,
            max_projects_per_month=0,  # unlimited
            max_audio_duration_minutes=0,
            max_file_size_mb=500, max_storage_gb=100,
        )
        s = SubscriptionPlanSerializer(plan)
        features = s.data['features']
        features_str = ' '.join(features)
        self.assertIn('Unlimited', features_str)


class SubscriptionPlanModelTests(TestCase):

    def setUp(self):
        from accounts.models import SubscriptionPlan
        self.plan = SubscriptionPlan.objects.create(
            name='test_plan',
            display_name='Test Plan',
            description='Test',
            price_monthly=9.99,
            price_yearly=99.99,
            max_projects_per_month=3,
            max_audio_duration_minutes=30,
            max_file_size_mb=50,
            max_storage_gb=5,
        )

    def test_str_representation(self):
        self.assertIn('Test Plan', str(self.plan))

    def test_plan_fields(self):
        self.assertEqual(self.plan.price_monthly, 9.99)
        self.assertEqual(self.plan.max_projects_per_month, 3)


class UserSubscriptionModelTests(TestCase):

    def setUp(self):
        from accounts.models import SubscriptionPlan, UserSubscription
        self.user = User.objects.create_user(username='subtest', password='pass123')
        self.plan = SubscriptionPlan.objects.create(
            name='sub_plan', display_name='Sub Plan', description='',
            price_monthly=9.99, price_yearly=99.99,
            max_projects_per_month=3, max_audio_duration_minutes=30,
            max_file_size_mb=50, max_storage_gb=5,
        )
        self.sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='active',
        )

    def test_is_active(self):
        self.assertTrue(self.sub.is_active)

    def test_inactive_status(self):
        self.sub.status = 'canceled'
        self.sub.save()
        self.assertFalse(self.sub.is_active)

    def test_str_representation(self):
        s = str(self.sub)
        self.assertIsInstance(s, str)


class UsageTrackingModelTests(TestCase):

    def setUp(self):
        from accounts.models import SubscriptionPlan, UserSubscription, UsageTracking
        from datetime import date
        self.user = User.objects.create_user(username='usage_user', password='pass123')
        self.plan = SubscriptionPlan.objects.create(
            name='usage_plan', display_name='Usage Plan', description='',
            price_monthly=9.99, price_yearly=99.99,
            max_projects_per_month=5, max_audio_duration_minutes=60,
            max_file_size_mb=100, max_storage_gb=10,
        )
        self.sub = UserSubscription.objects.create(
            user=self.user, plan=self.plan, status='active'
        )
        today = date.today()
        self.usage = UsageTracking.objects.create(
            user=self.user,
            period_start=date(today.year, today.month, 1),
            period_end=today,
            projects_created=2,
            audio_minutes_processed=15.0,
        )

    def test_usage_fields(self):
        self.assertEqual(self.usage.projects_created, 2)
        self.assertAlmostEqual(float(self.usage.audio_minutes_processed), 15.0)

    def test_str_representation(self):
        s = str(self.usage)
        self.assertIsInstance(s, str)
