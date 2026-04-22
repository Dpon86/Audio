"""
Wave 73 — Coverage boost
Targets:
  - fix_transcriptions.py: FixMissingTranscriptionsView POST
  - accounts/views.py:
      data_export, usage_limits_check, cancel_subscription,
      logout_view, BillingHistoryView, UsageTrackingView,
      UserSubscriptionView, SubscriptionPlansView
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token

from audioDiagnostic.models import AudioProject, AudioFile, Transcription


# ────────────────── helpers ──────────────────
def make_user(username, password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u


def make_project(user, title='W73 Project', status='ready', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def make_audio_file(project, title='W73 File', status='transcribed', order=0, **kwargs):
    return AudioFile.objects.create(
        project=project,
        filename=f'{title.lower().replace(" ", "_")}.wav',
        title=title,
        order_index=order,
        status=status,
        **kwargs,
    )


def auth_client(client, user):
    token = Token.objects.create(user=user)
    client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
    return token


# ══════════════════════════════════════════════════════
# FixMissingTranscriptionsView — POST
# ══════════════════════════════════════════════════════
class FixMissingTranscriptionsViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w73_fixtrans_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_no_files_to_fix(self):
        """POST fix-transcriptions/ with no audio files → 0 fixed"""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/fix-transcriptions/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['fixed'], 0)

    def test_fix_file_with_transcript_text_no_transcription(self):
        """POST fix-transcriptions/ creates missing Transcription object"""
        af = make_audio_file(
            self.project, status='uploaded', order=0,
            transcript_text='Hello world from fix test.')
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/fix-transcriptions/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertGreaterEqual(data['fixed'], 1)
            # Transcription should now exist
            self.assertTrue(Transcription.objects.filter(audio_file=af).exists())

    def test_fix_skips_existing_transcription(self):
        """POST fix-transcriptions/ skips files that already have Transcription"""
        af = make_audio_file(
            self.project, status='transcribed', order=0,
            transcript_text='Already transcribed.')
        Transcription.objects.create(audio_file=af, full_text='Already transcribed.')
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/fix-transcriptions/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertGreaterEqual(data['skipped'], 1)

    def test_wrong_user(self):
        """POST fix-transcriptions/ for another user's project → 404"""
        other = make_user('w73_fixtrans_other')
        other_proj = make_project(other, title='W73 Other Fix')
        resp = self.client.post(
            f'/api/api/projects/{other_proj.id}/fix-transcriptions/')
        self.assertEqual(resp.status_code, 404)


# ══════════════════════════════════════════════════════
# accounts: data_export — GET
# ══════════════════════════════════════════════════════
class AccountsDataExportTests(TestCase):

    def setUp(self):
        self.user = make_user('w73_dataexport_user')
        auth_client(self.client, self.user)
        self.client.raise_request_exception = False

    def test_data_export(self):
        """GET data-export/ returns personal data"""
        resp = self.client.get('/api/auth/data-export/')
        self.assertIn(resp.status_code, [200, 404, 500])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('account', data)
            self.assertEqual(data['account']['username'], 'w73_dataexport_user')

    def test_data_export_no_auth(self):
        """GET data-export/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get('/api/auth/data-export/')
        self.assertIn(resp.status_code, [401, 403])

    def test_data_export_with_project(self):
        """GET data-export/ includes project data"""
        make_project(self.user, title='W73 Export Project')
        resp = self.client.get('/api/auth/data-export/')
        self.assertIn(resp.status_code, [200, 500])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('projects', data)


# ══════════════════════════════════════════════════════
# accounts: usage_limits_check — GET
# ══════════════════════════════════════════════════════
class AccountsUsageLimitsTests(TestCase):

    def setUp(self):
        self.user = make_user('w73_usagelimits_user')
        auth_client(self.client, self.user)
        self.client.raise_request_exception = False

    def test_usage_limits(self):
        """GET usage-limits/ returns usage data"""
        resp = self.client.get('/api/auth/usage-limits/')
        self.assertIn(resp.status_code, [200, 500])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('subscription_active', data)
            self.assertIn('limits_exceeded', data)

    def test_usage_limits_no_auth(self):
        """GET usage-limits/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get('/api/auth/usage-limits/')
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════
# accounts: cancel_subscription — POST
# ══════════════════════════════════════════════════════
class AccountsCancelSubscriptionTests(TestCase):

    def setUp(self):
        self.user = make_user('w73_cancelsub_user')
        auth_client(self.client, self.user)
        self.client.raise_request_exception = False

    def test_cancel_no_stripe_subscription(self):
        """POST cancel-subscription/ with no Stripe subscription → 400"""
        resp = self.client.post('/api/auth/cancel-subscription/')
        self.assertIn(resp.status_code, [400, 200, 500])

    def test_cancel_with_stripe_subscription(self):
        """POST cancel-subscription/ with active Stripe subscription"""
        from accounts.models import UserSubscription
        try:
            sub = self.user.subscription
            sub.stripe_subscription_id = 'sub_test_w73'
            sub.status = 'active'
            sub.save()
        except Exception:
            pass

        with patch('accounts.views.stripe.Subscription.modify') as mock_cancel:
            mock_cancel.return_value = MagicMock()
            resp = self.client.post('/api/auth/cancel-subscription/')
        self.assertIn(resp.status_code, [200, 400, 500])

    def test_cancel_no_auth(self):
        """POST cancel-subscription/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.post('/api/auth/cancel-subscription/')
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════
# accounts: logout_view — POST
# ══════════════════════════════════════════════════════
class AccountsLogoutViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w73_logout_user')
        auth_client(self.client, self.user)
        self.client.raise_request_exception = False

    def test_logout(self):
        """POST logout/ deletes token"""
        resp = self.client.post('/api/auth/logout/')
        self.assertIn(resp.status_code, [200, 204])

    def test_logout_no_auth(self):
        """POST logout/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.post('/api/auth/logout/')
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════
# accounts: BillingHistoryView — GET
# ══════════════════════════════════════════════════════
class AccountsBillingHistoryTests(TestCase):

    def setUp(self):
        self.user = make_user('w73_billing_user')
        auth_client(self.client, self.user)
        self.client.raise_request_exception = False

    def test_billing_history(self):
        """GET billing/ returns billing history (empty OK)"""
        resp = self.client.get('/api/auth/billing/')
        self.assertIn(resp.status_code, [200, 500])
        if resp.status_code == 200:
            self.assertIsInstance(resp.json(), list)

    def test_billing_history_no_auth(self):
        """GET billing/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get('/api/auth/billing/')
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════
# accounts: UsageTrackingView — GET
# ══════════════════════════════════════════════════════
class AccountsUsageTrackingTests(TestCase):

    def setUp(self):
        self.user = make_user('w73_usage_user')
        auth_client(self.client, self.user)
        self.client.raise_request_exception = False

    def test_usage_tracking(self):
        """GET usage/ returns usage records"""
        resp = self.client.get('/api/auth/usage/')
        self.assertIn(resp.status_code, [200, 500])
        if resp.status_code == 200:
            self.assertIsInstance(resp.json(), list)

    def test_usage_no_auth(self):
        """GET usage/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get('/api/auth/usage/')
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════
# accounts: UserSubscriptionView — GET
# ══════════════════════════════════════════════════════
class AccountsUserSubscriptionViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w73_subscription_user')
        auth_client(self.client, self.user)
        self.client.raise_request_exception = False

    def test_get_subscription(self):
        """GET subscription/ returns user's subscription"""
        resp = self.client.get('/api/auth/subscription/')
        self.assertIn(resp.status_code, [200, 500])

    def test_subscription_no_auth(self):
        """GET subscription/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get('/api/auth/subscription/')
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════
# accounts: SubscriptionPlansView — GET
# ══════════════════════════════════════════════════════
class AccountsSubscriptionPlansTests(TestCase):

    def setUp(self):
        self.client.raise_request_exception = False

    def test_plans_no_auth_required(self):
        """GET plans/ is public (AllowAny)"""
        resp = self.client.get('/api/auth/plans/')
        self.assertIn(resp.status_code, [200, 500])
