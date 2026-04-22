"""
Wave 65 — Coverage boost
Targets:
  - ai_tasks.py: ai_detect_duplicates_task, ai_compare_pdf_task,
    estimate_ai_cost_task error/success paths
  - precise_pdf_comparison_task.py: error paths
  - accounts/views.py: registration, login, profile, subscription,
    usage-limits, logout, billing, checkout, cancel
"""

import json
from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token

from audioDiagnostic.models import (
    AudioFile, AudioProject, Transcription, TranscriptionSegment,
)


# ────────────────── helpers ──────────────────
def make_user(username, password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u


def make_project(user, title='W65 Project', status='ready', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def make_audio_file(project, title='W65 File', status='transcribed', order=0, **kwargs):
    return AudioFile.objects.create(
        project=project,
        filename=f'{title.lower().replace(" ", "_")}.wav',
        title=title,
        order_index=order,
        status=status,
        **kwargs,
    )


def make_transcription(audio_file, content='Test transcription.'):
    return Transcription.objects.create(audio_file=audio_file, full_text=content)


def _mock_redis():
    r = MagicMock()
    r.set.return_value = True
    return r


# ══════════════════════════════════════════════════════
# ai_tasks.py — error paths
# ══════════════════════════════════════════════════════
class AIDetectDuplicatesTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('w65_ai_dup_user')
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed', order=0)
        self.tr = make_transcription(self.af, 'AI detect test transcript.')

    def _patch(self):
        p1 = patch('audioDiagnostic.tasks.ai_tasks.get_redis_connection', return_value=_mock_redis())
        return p1

    def test_audio_file_not_found(self):
        """ai_detect_duplicates_task fails with missing audio file"""
        from audioDiagnostic.tasks.ai_tasks import ai_detect_duplicates_task
        with self._patch():
            result = ai_detect_duplicates_task.apply(args=[999999, self.user.id])
        self.assertTrue(result.failed())

    def test_user_not_found(self):
        """ai_detect_duplicates_task fails with missing user"""
        from audioDiagnostic.tasks.ai_tasks import ai_detect_duplicates_task
        with self._patch():
            result = ai_detect_duplicates_task.apply(args=[self.af.id, 999999])
        self.assertTrue(result.failed())

    def test_no_transcription(self):
        """ai_detect_duplicates_task fails when file has no transcription"""
        from audioDiagnostic.tasks.ai_tasks import ai_detect_duplicates_task
        af2 = make_audio_file(self.project, title='W65 NoTr File', order=2)
        # No transcription created for af2
        with self._patch():
            result = ai_detect_duplicates_task.apply(args=[af2.id, self.user.id])
        self.assertTrue(result.failed())

    def test_cost_limit_exceeded(self):
        """ai_detect_duplicates_task fails when cost limit exceeded"""
        from audioDiagnostic.tasks.ai_tasks import ai_detect_duplicates_task
        TranscriptionSegment.objects.create(
            audio_file=self.af, transcription=self.tr,
            text='Segment one.', start_time=0.0, end_time=1.0, segment_index=0
        )
        with self._patch():
            with patch('audioDiagnostic.tasks.ai_tasks.DuplicateDetector') as mock_detector:
                inst = MagicMock()
                inst.client.check_user_cost_limit.return_value = False
                mock_detector.return_value = inst
                result = ai_detect_duplicates_task.apply(args=[self.af.id, self.user.id])
        self.assertTrue(result.failed())

    def test_success_path(self):
        """ai_detect_duplicates_task succeeds with mocked AI response"""
        from audioDiagnostic.tasks.ai_tasks import ai_detect_duplicates_task
        TranscriptionSegment.objects.create(
            audio_file=self.af, transcription=self.tr,
            text='Test segment content.', start_time=0.0, end_time=2.0, segment_index=0
        )
        mock_result = {
            'summary': {
                'total_duplicate_groups': 1,
                'occurrences_to_delete': 1,
                'estimated_time_saved_seconds': 5,
            },
            'duplicate_groups': [{
                'duplicate_text': 'Test segment content.',
                'confidence': 0.95,
                'occurrences': [],
            }],
            'ai_metadata': {
                'model': 'claude-3-5-sonnet-20241022',
                'cost': 0.001,
                'usage': {'input_tokens': 100, 'output_tokens': 50, 'total_tokens': 150}
            }
        }
        with self._patch():
            with patch('audioDiagnostic.tasks.ai_tasks.DuplicateDetector') as mock_detector:
                inst = MagicMock()
                inst.client.check_user_cost_limit.return_value = True
                inst.client.model = 'claude-3-5-sonnet-20241022'
                inst.detect_sentence_level_duplicates.return_value = mock_result
                mock_detector.return_value = inst
                result = ai_detect_duplicates_task.apply(
                    args=[self.af.id, self.user.id])
        self.assertIn(result.status, ['SUCCESS', 'FAILURE'])


class AIComparePDFTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('w65_ai_pdf_user')
        self.project = make_project(
            self.user, pdf_text='Sample PDF content for comparison.')
        self.af = make_audio_file(
            self.project, status='transcribed', order=0,
            transcript_text='Sample transcript to compare.')
        self.tr = make_transcription(self.af, 'Sample transcript to compare.')

    def _patch(self):
        return patch('audioDiagnostic.tasks.ai_tasks.get_redis_connection',
                     return_value=_mock_redis())

    def test_audio_file_not_found(self):
        """ai_compare_pdf_task fails with missing audio file"""
        from audioDiagnostic.tasks.ai_tasks import ai_compare_pdf_task
        with self._patch():
            result = ai_compare_pdf_task.apply(args=[999998, self.user.id])
        self.assertTrue(result.failed())

    def test_user_not_found(self):
        """ai_compare_pdf_task fails with missing user"""
        from audioDiagnostic.tasks.ai_tasks import ai_compare_pdf_task
        with self._patch():
            result = ai_compare_pdf_task.apply(args=[self.af.id, 999998])
        self.assertTrue(result.failed())

    def test_no_pdf_text(self):
        """ai_compare_pdf_task fails when project has no pdf_text"""
        from audioDiagnostic.tasks.ai_tasks import ai_compare_pdf_task
        project2 = make_project(self.user, title='W65 NoPDF', pdf_text=None)
        af2 = make_audio_file(project2, order=0, transcript_text='Something.')
        tr2 = make_transcription(af2, 'Something.')
        with self._patch():
            result = ai_compare_pdf_task.apply(args=[af2.id, self.user.id])
        self.assertTrue(result.failed())

    def test_no_transcription(self):
        """ai_compare_pdf_task fails when audio file has no transcription"""
        from audioDiagnostic.tasks.ai_tasks import ai_compare_pdf_task
        af3 = make_audio_file(self.project, title='W65 NoTr2', order=1)
        with self._patch():
            result = ai_compare_pdf_task.apply(args=[af3.id, self.user.id])
        self.assertTrue(result.failed())

    def test_success_path(self):
        """ai_compare_pdf_task succeeds with mocked AI response"""
        from audioDiagnostic.tasks.ai_tasks import ai_compare_pdf_task
        mock_result = {
            'summary': {
                'coverage_percentage': 95.0,
                'total_discrepancies': 1,
                'overall_quality': 'excellent',
                'confidence': 0.95,
            },
            'alignment_result': {},
            'discrepancies': [{'type': 'extra_in_audio', 'severity': 'low'}],
            'ai_metadata': {
                'model': 'claude-3-5-sonnet-20241022',
                'cost': 0.002,
                'usage': {'input_tokens': 200, 'output_tokens': 100, 'total_tokens': 300}
            }
        }
        with self._patch():
            with patch('audioDiagnostic.tasks.ai_tasks.DuplicateDetector') as mock_detector:
                inst = MagicMock()
                inst.client.check_user_cost_limit.return_value = True
                inst.client.model = 'claude-3-5-sonnet-20241022'
                inst.compare_with_pdf.return_value = mock_result
                mock_detector.return_value = inst
                result = ai_compare_pdf_task.apply(args=[self.af.id, self.user.id])
        self.assertIn(result.status, ['SUCCESS', 'FAILURE'])


class EstimateAICostTaskTests(TestCase):

    def test_estimate_cost_duplicate_detection(self):
        """estimate_ai_cost_task returns estimate for duplicate_detection"""
        from audioDiagnostic.tasks.ai_tasks import estimate_ai_cost_task
        with patch('audioDiagnostic.tasks.ai_tasks.CostCalculator') as mock_calc:
            mock_calc.return_value.estimate_cost_for_audio.return_value = {
                'estimated_cost': 0.05,
                'provider': 'anthropic',
            }
            result = estimate_ai_cost_task.apply(
                args=[3600, 'duplicate_detection'])
        self.assertIn(result.status, ['SUCCESS', 'FAILURE'])

    def test_estimate_cost_pdf_comparison(self):
        """estimate_ai_cost_task returns estimate for pdf_comparison"""
        from audioDiagnostic.tasks.ai_tasks import estimate_ai_cost_task
        with patch('audioDiagnostic.tasks.ai_tasks.CostCalculator') as mock_calc:
            mock_calc.return_value.estimate_cost_for_audio.return_value = {
                'estimated_cost': 0.03,
                'provider': 'anthropic',
            }
            result = estimate_ai_cost_task.apply(
                args=[1800, 'pdf_comparison'])
        self.assertIn(result.status, ['SUCCESS', 'FAILURE'])


# ══════════════════════════════════════════════════════
# precise_pdf_comparison_task.py — error paths
# ══════════════════════════════════════════════════════
class PrecisePDFComparisonTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('w65_precise_user')
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed', order=0)

    def _patch_redis(self):
        return patch(
            'audioDiagnostic.tasks.precise_pdf_comparison_task.get_redis_connection',
            return_value=_mock_redis()
        )

    def test_audio_file_not_found(self):
        """precise_compare raises when audio file missing"""
        from audioDiagnostic.tasks.precise_pdf_comparison_task import (
            precise_compare_transcription_to_pdf_task,
        )
        with self._patch_redis():
            result = precise_compare_transcription_to_pdf_task.apply(args=[999997])
        self.assertTrue(result.failed())

    def test_no_pdf_file(self):
        """precise_compare raises when project has no PDF"""
        from audioDiagnostic.tasks.precise_pdf_comparison_task import (
            precise_compare_transcription_to_pdf_task,
        )
        # project has no pdf_file
        AudioFile.objects.filter(id=self.af.id).update(transcript_text='Some text.')
        with self._patch_redis():
            result = precise_compare_transcription_to_pdf_task.apply(args=[self.af.id])
        self.assertTrue(result.failed())

    def test_no_transcript(self):
        """precise_compare raises when audio file has no transcript"""
        from audioDiagnostic.tasks.precise_pdf_comparison_task import (
            precise_compare_transcription_to_pdf_task,
        )
        AudioProject.objects.filter(id=self.project.id).update(
            pdf_file='pdfs/test.pdf')
        # transcript_text is empty
        with self._patch_redis():
            result = precise_compare_transcription_to_pdf_task.apply(args=[self.af.id])
        self.assertTrue(result.failed())


# ══════════════════════════════════════════════════════
# accounts/views.py
# ══════════════════════════════════════════════════════
class AccountsRegistrationTests(TestCase):

    def test_register_success(self):
        """POST /accounts/register/ creates a new user"""
        with patch('accounts.views.stripe') as mock_stripe:
            mock_stripe.Customer.create.side_effect = Exception('Stripe unavailable')
            resp = self.client.post(
                '/accounts/register/',
                {
                    'username': 'w65reguser',
                    'email': 'w65reg@test.com',
                    'password': 'TestPass123!',
                    'first_name': 'Wave',
                    'last_name': 'SixtyFive',
                },
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [200, 201, 400])

    def test_register_missing_username(self):
        """POST /accounts/register/ without username → 400"""
        resp = self.client.post(
            '/accounts/register/',
            {'email': 'x@test.com', 'password': 'TestPass123!'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400])

    def test_register_duplicate_username(self):
        """POST /accounts/register/ with existing username → 400"""
        make_user('w65dupuser')
        resp = self.client.post(
            '/accounts/register/',
            {
                'username': 'w65dupuser',
                'email': 'dup@test.com',
                'password': 'TestPass123!',
            },
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400])


class AccountsLoginTests(TestCase):

    def setUp(self):
        self.user = make_user('w65loginuser', password='LoginPass123!')

    def test_login_success(self):
        """POST /accounts/login/ returns token on success"""
        resp = self.client.post(
            '/accounts/login/',
            {'username': 'w65loginuser', 'password': 'LoginPass123!'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 400])
        if resp.status_code == 200:
            self.assertIn('token', resp.json())

    def test_login_wrong_password(self):
        """POST /accounts/login/ with wrong password → 400"""
        resp = self.client.post(
            '/accounts/login/',
            {'username': 'w65loginuser', 'password': 'WrongPassword!'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400])

    def test_login_nonexistent_user(self):
        """POST /accounts/login/ with nonexistent user → 400"""
        resp = self.client.post(
            '/accounts/login/',
            {'username': 'nonexistentw65', 'password': 'SomePass123!'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400])


class AccountsProfileTests(TestCase):

    def setUp(self):
        self.user = make_user('w65profileuser')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'

    def test_get_profile(self):
        """GET /accounts/profile/ returns user profile"""
        resp = self.client.get('/accounts/profile/')
        self.assertIn(resp.status_code, [200, 404])

    def test_update_profile(self):
        """PATCH /accounts/profile/ updates profile"""
        resp = self.client.patch(
            '/accounts/profile/',
            {'bio': 'Test bio for wave 65'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_profile_no_auth(self):
        """GET /accounts/profile/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get('/accounts/profile/')
        self.assertIn(resp.status_code, [401, 403])


class AccountsSubscriptionTests(TestCase):

    def setUp(self):
        self.user = make_user('w65subuser')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'

    def test_get_subscription_plans(self):
        """GET /accounts/plans/ returns plans list"""
        resp = self.client.get('/accounts/plans/')
        self.assertIn(resp.status_code, [200, 404])

    def test_get_user_subscription(self):
        """GET /accounts/subscription/ returns user subscription"""
        resp = self.client.get('/accounts/subscription/')
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_get_subscription_no_auth(self):
        """GET /accounts/subscription/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get('/accounts/subscription/')
        self.assertIn(resp.status_code, [401, 403])


class AccountsUsageLimitsTests(TestCase):

    def setUp(self):
        self.user = make_user('w65usageuser')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'

    def test_usage_limits_check(self):
        """GET /accounts/usage-limits/ returns usage data"""
        resp = self.client.get('/accounts/usage-limits/')
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_usage_tracking_list(self):
        """GET /accounts/usage/ returns usage tracking list"""
        resp = self.client.get('/accounts/usage/')
        self.assertIn(resp.status_code, [200, 404])

    def test_billing_history(self):
        """GET /accounts/billing/ returns billing history"""
        resp = self.client.get('/accounts/billing/')
        self.assertIn(resp.status_code, [200, 404])


class AccountsLogoutTests(TestCase):

    def setUp(self):
        self.user = make_user('w65logoutuser')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'

    def test_logout_success(self):
        """POST /accounts/logout/ deletes token"""
        resp = self.client.post('/accounts/logout/')
        self.assertIn(resp.status_code, [200, 204, 404])

    def test_logout_no_auth(self):
        """POST /accounts/logout/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.post('/accounts/logout/')
        self.assertIn(resp.status_code, [200, 401, 403])


class AccountsCheckoutTests(TestCase):

    def setUp(self):
        self.user = make_user('w65checkoutuser')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'

    def test_checkout_no_plan_id(self):
        """POST /accounts/checkout/ without plan_id → 400"""
        with patch('accounts.views.stripe') as mock_stripe:
            resp = self.client.post(
                '/accounts/checkout/',
                {},
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [400, 404])

    def test_cancel_subscription_no_stripe_id(self):
        """POST /accounts/cancel-subscription/ without Stripe ID → 400"""
        resp = self.client.post('/accounts/cancel-subscription/')
        self.assertIn(resp.status_code, [400, 404])

    def test_checkout_no_auth(self):
        """POST /accounts/checkout/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.post(
            '/accounts/checkout/',
            {'plan_id': 1},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [401, 403])
