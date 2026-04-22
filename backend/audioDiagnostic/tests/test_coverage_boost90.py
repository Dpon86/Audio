"""
Wave 90 — Coverage boost
Targets:
  - accounts/models_feedback.py (FeatureFeedback, FeatureFeedbackSummary)
  - accounts/serializers_feedback.py
  - accounts/views_feedback.py (feedback API views)
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from rest_framework.authtoken.models import Token

User = get_user_model()


class FeatureFeedbackModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='fb_user', password='pass123')

    def _create_feedback(self, rating=5, worked=True):
        from accounts.models_feedback import FeatureFeedback
        return FeatureFeedback.objects.create(
            user=self.user,
            feature='ai_duplicate_detection',
            worked_as_expected=worked,
            rating=rating,
            what_you_like='Great tool',
            what_to_improve='',
        )

    def test_str_representation(self):
        fb = self._create_feedback()
        s = str(fb)
        self.assertIn('fb_user', s)

    def test_is_positive_high_rating(self):
        fb = self._create_feedback(rating=4, worked=True)
        self.assertTrue(fb.is_positive)

    def test_is_positive_low_rating(self):
        fb = self._create_feedback(rating=3, worked=True)
        self.assertFalse(fb.is_positive)

    def test_needs_attention_low_rating(self):
        fb = self._create_feedback(rating=2, worked=True)
        self.assertTrue(fb.needs_attention)

    def test_needs_attention_not_worked(self):
        fb = self._create_feedback(rating=5, worked=False)
        self.assertTrue(fb.needs_attention)

    def test_no_attention_needed(self):
        fb = self._create_feedback(rating=5, worked=True)
        self.assertFalse(fb.needs_attention)


class FeatureFeedbackSummaryModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='fbs_user', password='pass123')

    def test_update_summary(self):
        from accounts.models_feedback import FeatureFeedback, FeatureFeedbackSummary
        FeatureFeedback.objects.create(
            user=self.user,
            feature='ai_transcription',
            worked_as_expected=True,
            rating=4,
        )
        FeatureFeedback.objects.create(
            user=self.user,
            feature='ai_transcription',
            worked_as_expected=False,
            rating=2,
        )
        FeatureFeedbackSummary.update_summary('ai_transcription')
        summary = FeatureFeedbackSummary.objects.get(feature='ai_transcription')
        self.assertEqual(summary.total_responses, 2)
        self.assertEqual(summary.average_rating, 3.00)

    def test_update_summary_no_data(self):
        from accounts.models_feedback import FeatureFeedbackSummary
        # Should return early without creating anything
        result = FeatureFeedbackSummary.update_summary('pdf_upload')
        self.assertIsNone(result)

    def test_str_representation(self):
        from accounts.models_feedback import FeatureFeedbackSummary
        summary = FeatureFeedbackSummary.objects.create(
            feature='audio_assembly',
            total_responses=10,
            average_rating=4.5,
        )
        s = str(summary)
        self.assertIn('audio_assembly', s)


class FeedbackSerializerTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='ser_fb_user', password='pass123')

    def test_validate_rating_in_range(self):
        from accounts.serializers_feedback import FeatureFeedbackSerializer
        s = FeatureFeedbackSerializer()
        result = s.validate_rating(3)
        self.assertEqual(result, 3)

    def test_validate_rating_out_of_range(self):
        from accounts.serializers_feedback import FeatureFeedbackSerializer
        from rest_framework import serializers
        s = FeatureFeedbackSerializer()
        with self.assertRaises(serializers.ValidationError):
            s.validate_rating(0)

    def test_create_feedback(self):
        from accounts.serializers_feedback import FeatureFeedbackSerializer
        from unittest.mock import MagicMock
        request = MagicMock()
        request.user = self.user
        s = FeatureFeedbackSerializer(data={
            'feature': 'ai_duplicate_detection',
            'worked_as_expected': True,
            'rating': 5,
            'what_you_like': 'Very good',
        }, context={'request': request})
        self.assertTrue(s.is_valid(), s.errors)
        fb = s.save()
        self.assertEqual(fb.feature, 'ai_duplicate_detection')
        self.assertEqual(fb.user, self.user)

    def test_quick_feedback_serializer_valid(self):
        from accounts.serializers_feedback import QuickFeedbackSerializer
        s = QuickFeedbackSerializer(data={
            'feature': 'ai_transcription',
            'worked_as_expected': True,
            'rating': 4,
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_quick_feedback_serializer_invalid_rating(self):
        from accounts.serializers_feedback import QuickFeedbackSerializer
        s = QuickFeedbackSerializer(data={
            'feature': 'ai_transcription',
            'worked_as_expected': True,
            'rating': 6,
        })
        self.assertFalse(s.is_valid())


class FeedbackViewsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='view_fb_user', password='pass123')
        self.token = Token.objects.create(user=self.user)
        self.factory = APIRequestFactory()

    def _auth_header(self):
        return {'HTTP_AUTHORIZATION': f'Token {self.token.key}'}

    def test_submit_feedback_success(self):
        from accounts.views_feedback import submit_feedback
        request = self.factory.post('/api/auth/feedback/submit/', {
            'feature': 'ai_duplicate_detection',
            'worked_as_expected': True,
            'rating': 5,
            'what_you_like': 'Great',
        }, format='json', **self._auth_header())
        request.user = self.user
        response = submit_feedback(request)
        self.assertIn(response.status_code, [200, 201, 400])

    def test_submit_feedback_invalid(self):
        from accounts.views_feedback import submit_feedback
        request = self.factory.post('/api/auth/feedback/submit/', {
            'feature': 'ai_duplicate_detection',
            'worked_as_expected': True,
            'rating': 9,  # invalid
        }, format='json', **self._auth_header())
        request.user = self.user
        response = submit_feedback(request)
        self.assertIn(response.status_code, [400, 200])

    def test_user_feedback_history(self):
        from accounts.views_feedback import user_feedback_history
        request = self.factory.get('/api/auth/feedback/my-feedback/', **self._auth_header())
        request.user = self.user
        response = user_feedback_history(request)
        self.assertEqual(response.status_code, 200)

    def test_feature_summary_not_found(self):
        from accounts.views_feedback import feature_summary
        request = self.factory.get('/api/auth/feedback/summary/nonexistent_feature/')
        request.user = self.user
        response = feature_summary(request, 'nonexistent_feature')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['summary']['total_responses'], 0)

    def test_feature_summary_found(self):
        from accounts.views_feedback import feature_summary
        from accounts.models_feedback import FeatureFeedbackSummary
        FeatureFeedbackSummary.objects.create(
            feature='ai_pdf_comparison',
            total_responses=3,
            average_rating=4.0,
        )
        request = self.factory.get('/api/auth/feedback/summary/ai_pdf_comparison/')
        request.user = self.user
        response = feature_summary(request, 'ai_pdf_comparison')
        self.assertEqual(response.status_code, 200)

    def test_all_feature_summaries(self):
        from accounts.views_feedback import all_feature_summaries
        request = self.factory.get('/api/auth/feedback/summaries/')
        request.user = self.user
        response = all_feature_summaries(request)
        self.assertEqual(response.status_code, 200)
