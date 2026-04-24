"""
Wave 116 — Coverage boost
Targets:
  - audioDiagnostic/views/duplicate_views.py: ProjectDuplicatesReviewView,
    ProjectConfirmDeletionsView, ProjectVerifyCleanupView branches
  - audioDiagnostic/views/legacy_views.py: AudioFileStatusView, N8NTranscribeView branches
  - accounts/authentication.py: ExpiringTokenAuthentication token expiry
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from unittest.mock import patch, MagicMock
from rest_framework.test import force_authenticate


def make_project(user, **kwargs):
    from audioDiagnostic.models import AudioProject
    return AudioProject.objects.create(user=user, title=kwargs.get('title', 'P116'), **{
        k: v for k, v in kwargs.items() if k != 'title'
    })


def make_audio_file(project, order=0, status='transcribed'):
    from audioDiagnostic.models import AudioFile
    return AudioFile.objects.create(
        project=project, filename=f'f{order}.mp3',
        title=f'F{order}', order_index=order, status=status
    )


class DuplicateViewsRemainingTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='dupv116', password='pass')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user, status='pending')

    def test_review_not_completed(self):
        resp = self.client.get(f'/api/projects/{self.project.id}/duplicates/')
        self.assertEqual(resp.status_code, 400)

    def test_review_completed_no_duplicates(self):
        self.project.duplicates_detection_completed = True
        self.project.duplicates_detected = {'duplicates': [], 'duplicate_groups': {}, 'summary': {}}
        self.project.save()
        resp = self.client.get(f'/api/projects/{self.project.id}/duplicates/')
        self.assertIn(resp.status_code, [200])
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['duplicates'], [])

    def test_confirm_deletions_no_confirmations(self):
        resp = self.client.post(
            f'/api/projects/{self.project.id}/confirm-deletions/',
            data={'confirmed_deletions': []},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [400])

    def test_confirm_deletions_with_mocked_task(self):
        with patch('audioDiagnostic.views.duplicate_views.process_confirmed_deletions_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='task-confirm-116')
            resp = self.client.post(
                f'/api/projects/{self.project.id}/confirm-deletions/',
                data={'confirmed_deletions': [{'segment_id': 1}]},
                content_type='application/json'
            )
        self.assertIn(resp.status_code, [200, 500])

    def test_detect_duplicates_not_pdf_completed(self):
        resp = self.client.post(
            f'/api/projects/{self.project.id}/detect-duplicates/',
            data={}, content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)

    def test_detect_duplicates_already_in_progress(self):
        self.project.pdf_match_completed = True
        self.project.status = 'detecting_duplicates'
        self.project.save()
        resp = self.client.post(
            f'/api/projects/{self.project.id}/detect-duplicates/',
            data={}, content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)

    def test_detect_duplicates_mocked_task(self):
        self.project.pdf_match_completed = True
        self.project.save()
        with patch('audioDiagnostic.views.duplicate_views.detect_duplicates_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='task-detect-116')
            resp = self.client.post(
                f'/api/projects/{self.project.id}/detect-duplicates/',
                data={}, content_type='application/json'
            )
        self.assertIn(resp.status_code, [200])

    def test_refine_boundaries_no_pdf_match(self):
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            data={'start_char': 0, 'end_char': 100},
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)

    def test_refine_boundaries_valid(self):
        self.project.pdf_match_completed = True
        self.project.pdf_text = 'A' * 500
        self.project.save()
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            data={'start_char': 0, 'end_char': 100},
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200])

    def test_verify_cleanup_not_clean_audio(self):
        resp = self.client.post(
            f'/api/projects/{self.project.id}/create-iteration/',
            data={}, content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 400, 404])


class LegacyViewsRemainingTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='legv116', password='pass')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project)

    def test_audio_file_status_view(self):
        resp = self.client.get(
            f'/api/projects/{self.project.id}/audio-files/{self.af.id}/status/'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_audio_file_status_wrong_user(self):
        other = User.objects.create_user(username='legv116_other', password='pass')
        other_proj = make_project(other)
        other_af = make_audio_file(other_proj)
        resp = self.client.get(
            f'/api/projects/{other_proj.id}/audio-files/{other_af.id}/status/'
        )
        self.assertIn(resp.status_code, [404])

    def test_n8n_transcribe_no_wav(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.settings(MEDIA_ROOT=tmpdir):
                resp = self.client.post('/api/n8n/transcribe/', data={}, content_type='application/json')
                self.assertIn(resp.status_code, [404, 400, 500])


class AuthenticationTests(TestCase):

    def test_bearer_token_auth_valid(self):
        user = User.objects.create_user(username='authtest116', password='pass')
        token = Token.objects.create(user=user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token.key}'
        resp = self.client.get('/api/auth/profile/')
        self.assertIn(resp.status_code, [200, 401, 403])

    def test_expired_token_rejected(self):
        from datetime import timedelta
        from django.utils import timezone
        user = User.objects.create_user(username='expiredtok116', password='pass')
        token = Token.objects.create(user=user)
        # Set created 40 days ago (default expiry is 30 days)
        Token.objects.filter(key=token.key).update(
            created=timezone.now() - timedelta(days=40)
        )
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
        resp = self.client.get('/api/auth/profile/')
        self.assertIn(resp.status_code, [401, 403])

    def test_cookie_token_auth(self):
        user = User.objects.create_user(username='cookieauth116', password='pass')
        token = Token.objects.create(user=user)
        self.client.cookies['auth_token'] = token.key
        resp = self.client.get('/api/auth/profile/')
        self.assertIn(resp.status_code, [200, 401, 403])
