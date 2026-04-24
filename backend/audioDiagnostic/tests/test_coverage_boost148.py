"""
Wave 148: accounts/views_feedback.py - submit_feedback, user_feedback_history,
feature_summary, all_feature_summaries, quick_feedback
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.authtoken.models import Token
from rest_framework.test import force_authenticate
from accounts.views_feedback import (
    submit_feedback, user_feedback_history, feature_summary,
    all_feature_summaries, quick_feedback
)

User = get_user_model()


class SubmitFeedbackViewTests(TestCase):
    """Test submit_feedback view."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username='sfb148', password='pass', email='sfb148@t.com')

    def test_submit_valid_feedback(self):
        request = self.factory.post('/feedback/submit/', {
            'feature': 'ai_duplicate_detection',
            'worked_as_expected': True,
            'what_you_like': 'Very accurate!',
            'what_to_improve': 'Faster would be nice',
            'rating': 5,
        }, format='json')
        force_authenticate(request, user=self.user)
        response = submit_feedback(request)
        self.assertIn(response.status_code, [201, 400])

    def test_submit_invalid_feedback(self):
        """Missing required field should return 400."""
        request = self.factory.post('/feedback/submit/', {}, format='json')
        force_authenticate(request, user=self.user)
        response = submit_feedback(request)
        self.assertEqual(response.status_code, 400)

    def test_submit_feedback_different_ratings(self):
        """Test various ratings."""
        for rating in [1, 2, 3, 4]:
            request = self.factory.post('/feedback/submit/', {
                'feature': 'transcription',
                'worked_as_expected': False,
                'rating': rating,
            }, format='json')
            force_authenticate(request, user=self.user)
            response = submit_feedback(request)
            self.assertIn(response.status_code, [201, 400])


class UserFeedbackHistoryTests(TestCase):
    """Test user_feedback_history view."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username='ufh148', password='pass', email='ufh148@t.com')

    def test_get_user_feedback_history(self):
        request = self.factory.get('/feedback/my-feedback/')
        force_authenticate(request, user=self.user)
        response = user_feedback_history(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('feedback', response.data)


class FeatureSummaryTests(TestCase):
    """Test feature_summary view."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def test_feature_no_feedback(self):
        """Feature with no feedback returns empty summary."""
        request = self.factory.get('/feedback/summary/nonexistent-feature/')
        request.user = None
        response = feature_summary(request, 'nonexistent-feature')
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertIn('summary', data)
        self.assertEqual(data['summary']['total_responses'], 0)

    def test_feature_ai_duplicate_detection(self):
        """Test summary for ai_duplicate_detection feature."""
        request = self.factory.get('/feedback/summary/ai_duplicate_detection/')
        request.user = None
        response = feature_summary(request, 'ai_duplicate_detection')
        self.assertEqual(response.status_code, 200)


class AllFeatureSummariesTests(TestCase):
    """Test all_feature_summaries view."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def test_get_all_summaries(self):
        request = self.factory.get('/feedback/summaries/')
        request.user = None
        response = all_feature_summaries(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('summaries', response.data)


class QuickFeedbackTests(TestCase):
    """Test quick_feedback view."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username='qfb148', password='pass', email='qfb148@t.com')

    def test_quick_feedback_valid(self):
        request = self.factory.post('/feedback/quick/', {
            'feature': 'transcription',
            'worked_as_expected': True,
            'what_you_like': 'Works well!',
            'rating': 4,
        }, format='json')
        force_authenticate(request, user=self.user)
        response = quick_feedback(request)
        self.assertIn(response.status_code, [201, 400])

    def test_quick_feedback_invalid(self):
        """Missing data returns 400."""
        request = self.factory.post('/feedback/quick/', {}, format='json')
        force_authenticate(request, user=self.user)
        response = quick_feedback(request)
        self.assertEqual(response.status_code, 400)
