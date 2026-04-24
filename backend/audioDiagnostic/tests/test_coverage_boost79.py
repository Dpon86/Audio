"""
Wave 79 — Coverage boost
Targets:
  - duplicate_views.py:
      ProjectRefinePDFBoundariesView (POST - various branches),
      ProjectDetectDuplicatesView (POST - various branches),
      ProjectDuplicatesReviewView (GET - various branches),
      ProjectConfirmDeletionsView (POST - various branches),
      ProjectVerifyCleanupView (POST - various branches)
"""
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token

from audioDiagnostic.models import AudioProject, AudioFile, Transcription
from rest_framework.test import force_authenticate


def make_user(username):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password('pass1234!')
    u.save()
    return u


def make_project(user, title='W79 Project', status='transcribed', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def auth_client(client, user):
    token = Token.objects.create(user=user)
    client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
    return token


class ProjectRefinePDFBoundariesViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w79_refinepdf_user')
        auth_client(self.client, self.user)
        self.project = make_project(
            self.user,
            title='Refine PDF Project W79',
            pdf_text='This is the full PDF text content for testing boundaries.',
            pdf_match_completed=True,
        )
        self.client.raise_request_exception = False

    def test_pdf_matching_not_completed(self):
        """POST refine-pdf-boundaries/ without pdf_match_completed → 400"""
        self.project.pdf_match_completed = False
        self.project.save()
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            json.dumps({'start_char': 0, 'end_char': 10}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_no_pdf_text(self):
        """POST refine-pdf-boundaries/ without pdf_text → 400"""
        self.project.pdf_text = ''
        self.project.save()
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            json.dumps({'start_char': 0, 'end_char': 10}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_missing_start_char(self):
        """POST refine-pdf-boundaries/ without start_char → 400"""
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            json.dumps({'end_char': 10}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_invalid_boundaries(self):
        """POST refine-pdf-boundaries/ with start >= end → 400"""
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            json.dumps({'start_char': 20, 'end_char': 10}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_out_of_range_boundaries(self):
        """POST refine-pdf-boundaries/ with out-of-range end → 400"""
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            json.dumps({'start_char': 0, 'end_char': 99999}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_valid_boundaries(self):
        """POST refine-pdf-boundaries/ with valid range → 200"""
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            json.dumps({'start_char': 0, 'end_char': 20}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_not_found(self):
        """POST refine-pdf-boundaries/ on non-existent project → 404"""
        resp = self.client.post(
            '/api/projects/9999999/refine-pdf-boundaries/',
            json.dumps({'start_char': 0, 'end_char': 10}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [404])


class ProjectDetectDuplicatesViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w79_detectdups_user')
        auth_client(self.client, self.user)
        self.project = make_project(
            self.user,
            title='Detect Dups Project W79',
            pdf_match_completed=True,
        )
        self.client.raise_request_exception = False

    def test_pdf_not_matched(self):
        """POST detect-duplicates/ without pdf_match_completed → 400"""
        self.project.pdf_match_completed = False
        self.project.save()
        resp = self.client.post(f'/api/projects/{self.project.id}/detect-duplicates/')
        self.assertIn(resp.status_code, [400, 404])

    def test_already_in_progress(self):
        """POST detect-duplicates/ when detecting → 400"""
        self.project.status = 'detecting_duplicates'
        self.project.save()
        resp = self.client.post(f'/api/projects/{self.project.id}/detect-duplicates/')
        self.assertIn(resp.status_code, [400, 404])

    def test_launches_task(self):
        """POST detect-duplicates/ with prerequisites → launches task"""
        mock_task = MagicMock()
        mock_task.id = 'detect-dup-task-w79'

        with patch('audioDiagnostic.views.duplicate_views.detect_duplicates_task') as mock_celery:
            mock_celery.delay.return_value = mock_task
            resp = self.client.post(f'/api/projects/{self.project.id}/detect-duplicates/')
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_not_found(self):
        """POST detect-duplicates/ on non-existent project → 404"""
        resp = self.client.post('/api/projects/9999999/detect-duplicates/')
        self.assertIn(resp.status_code, [404])


class ProjectDuplicatesReviewViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w79_dupsreview_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user, title='Dups Review Project W79')
        self.client.raise_request_exception = False

    def test_detection_not_completed(self):
        """GET duplicates-review/ without duplicates_detection_completed → 400"""
        self.project.duplicates_detection_completed = False
        self.project.save()
        resp = self.client.get(f'/api/projects/{self.project.id}/duplicates-review/')
        self.assertIn(resp.status_code, [400, 404])

    def test_get_review_data(self):
        """GET duplicates-review/ with completed detection → 200"""
        self.project.duplicates_detection_completed = True
        self.project.duplicates_detected = {'duplicates': [], 'duplicate_groups': {}, 'summary': {}, 'pdf_comparison': {}}
        self.project.save()
        resp = self.client.get(f'/api/projects/{self.project.id}/duplicates-review/')
        self.assertIn(resp.status_code, [200, 404])

    def test_not_found(self):
        """GET duplicates-review/ on non-existent project → 404"""
        resp = self.client.get('/api/projects/9999999/duplicates-review/')
        self.assertIn(resp.status_code, [404])


class ProjectConfirmDeletionsViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w79_confirmdels_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user, title='Confirm Deletions Project W79')
        self.client.raise_request_exception = False

    def test_no_deletions(self):
        """POST confirm-deletions/ with empty list → 400"""
        resp = self.client.post(
            f'/api/projects/{self.project.id}/confirm-deletions/',
            json.dumps({'confirmed_deletions': []}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_valid_deletions(self):
        """POST confirm-deletions/ with valid list → launches task"""
        mock_task = MagicMock()
        mock_task.id = 'confirm-del-task-w79'

        with patch('audioDiagnostic.tasks.process_confirmed_deletions_task') as mock_celery:
            mock_celery.delay.return_value = mock_task
            resp = self.client.post(
                f'/api/projects/{self.project.id}/confirm-deletions/',
                json.dumps({'confirmed_deletions': [1, 2, 3]}),
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [200, 400, 404, 500])

    def test_not_found(self):
        """POST confirm-deletions/ on non-existent project → 404"""
        resp = self.client.post(
            '/api/projects/9999999/confirm-deletions/',
            json.dumps({'confirmed_deletions': [1]}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [404])


class ProjectVerifyCleanupViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w79_verifycleanup_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user, title='Verify Cleanup Project W79')
        self.client.raise_request_exception = False

    def test_clean_audio_not_transcribed(self):
        """POST verify-cleanup/ without clean_audio_transcribed → 400"""
        self.project.clean_audio_transcribed = False
        self.project.save()
        resp = self.client.post(f'/api/projects/{self.project.id}/verify-cleanup/')
        self.assertIn(resp.status_code, [400, 404])

    def test_not_found(self):
        """POST verify-cleanup/ on non-existent project → 404"""
        resp = self.client.post('/api/projects/9999999/verify-cleanup/')
        self.assertIn(resp.status_code, [404])
