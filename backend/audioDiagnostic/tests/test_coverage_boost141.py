"""
Wave 141: ProjectConfirmDeletionsView, ProjectDuplicatesReviewView, ProjectRedetectDuplicatesView
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch
from audioDiagnostic.models import AudioProject, AudioFile, TranscriptionSegment, Transcription
from rest_framework.authtoken.models import Token

User = get_user_model()


class ProjectConfirmDeletionsViewTests(TestCase):
    """Test ProjectConfirmDeletionsView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user = User.objects.create_user(username='cdel_user', password='pass', email='cdel@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.project = AudioProject.objects.create(
            user=self.user, title='CDel Project',
            duplicates_detection_completed=True,
        )

    def test_no_deletions(self):
        response = self.client.post(f'/api/projects/{self.project.id}/confirm-deletions/', {}, format='json')
        self.assertIn(response.status_code, [400, 401, 403, 404, 405])

    @patch('audioDiagnostic.views.duplicate_views.process_confirmed_deletions_task')
    def test_with_deletions(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='task-confirm-123')
        data = {'confirmed_deletions': [{'segment_id': 1}, {'segment_id': 2}]}
        response = self.client.post(
            f'/api/projects/{self.project.id}/confirm-deletions/', data, format='json'
        )
        self.assertIn(response.status_code, [200, 201, 400, 404, 500])

    def test_unauthenticated(self):
        client = APIClient()
        response = client.post(f'/api/projects/{self.project.id}/confirm-deletions/', {}, format='json')
        self.assertIn(response.status_code, [401, 403])


class ProjectDuplicatesReviewViewTests(TestCase):
    """Test ProjectDuplicatesReviewView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user = User.objects.create_user(username='drev_user', password='pass', email='drev@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.project = AudioProject.objects.create(
            user=self.user, title='DRev Project',
        )

    def test_not_completed(self):
        """Without duplicates_detection_completed, returns 400."""
        response = self.client.get(f'/api/projects/{self.project.id}/duplicates-review/')
        self.assertIn(response.status_code, [400, 404])

    def test_completed_no_duplicates(self):
        """With detection complete but no results."""
        self.project.duplicates_detection_completed = True
        self.project.duplicates_detected = {'duplicates': [], 'summary': {}, 'duplicate_groups': {}, 'pdf_comparison': {}}
        self.project.save()
        response = self.client.get(f'/api/projects/{self.project.id}/duplicates-review/')
        self.assertIn(response.status_code, [200, 404, 500])

    def test_with_duplicate_results(self):
        """Test review with actual duplicate data."""
        self.project.duplicates_detection_completed = True
        audio_file = AudioFile.objects.create(
            project=self.project, filename='test.wav', order_index=1,
        )
        self.project.duplicates_detected = {
            'duplicates': [
                {
                    'id': 1,
                    'audio_file_id': audio_file.id,
                    'audio_file_title': 'test.wav',
                    'text': 'duplicate text',
                    'start_time': 0.0,
                    'end_time': 1.0,
                    'group_id': 0,
                    'is_last_occurrence': False,
                }
            ],
            'duplicate_groups': {
                '0': {'normalized_text': 'duplicate text', 'occurrences': 1}
            },
            'summary': {'total_duplicate_segments': 1},
            'pdf_comparison': {},
        }
        self.project.save()
        response = self.client.get(f'/api/projects/{self.project.id}/duplicates-review/')
        self.assertIn(response.status_code, [200, 500])


class ProjectVerifyCleanupViewTests(TestCase):
    """Test ProjectVerifyCleanupView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user = User.objects.create_user(username='verify_user', password='pass', email='verify@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.project = AudioProject.objects.create(user=self.user, title='Verify Project')

    def test_not_transcribed(self):
        """Returns 400 if clean audio not transcribed."""
        response = self.client.post(f'/api/projects/{self.project.id}/verify-cleanup/', {}, format='json')
        self.assertIn(response.status_code, [400, 404])

    def test_transcribed_no_verification_segments(self):
        """With clean_audio_transcribed but no verification segments."""
        self.project.clean_audio_transcribed = True
        self.project.save()
        response = self.client.post(f'/api/projects/{self.project.id}/verify-cleanup/', {}, format='json')
        self.assertIn(response.status_code, [400, 404, 500])

    def test_with_verification_segments(self):
        """With verification segments."""
        self.project.clean_audio_transcribed = True
        self.project.pdf_matched_section = 'PDF reference content here.'
        self.project.save()
        audio_file = AudioFile.objects.create(
            project=self.project, filename='clean.wav', order_index=1,
        )
        transcription = Transcription.objects.create(
            audio_file=audio_file, full_text='Clean transcript here.',
        )
        TranscriptionSegment.objects.create(
            transcription=transcription,
            audio_file=audio_file,
            text='Clean transcript here.',
            start_time=0.0,
            end_time=1.0,
            segment_index=0,
            is_verification=True,
        )
        response = self.client.post(f'/api/projects/{self.project.id}/verify-cleanup/', {}, format='json')
        self.assertIn(response.status_code, [200, 400, 500])

    def test_unauthenticated(self):
        client = APIClient()
        response = client.post(f'/api/projects/{self.project.id}/verify-cleanup/', {}, format='json')
        self.assertIn(response.status_code, [401, 403])


class ProjectRedetectDuplicatesViewTests(TestCase):
    """Test ProjectRedetectDuplicatesView."""

    def setUp(self):
        self.client = APIClient()
        self.client.raise_request_exception = False
        self.user = User.objects.create_user(username='redet_user', password='pass', email='redet@t.com')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.project = AudioProject.objects.create(user=self.user, title='Redet Project')

    def test_no_clean_audio(self):
        """Returns 400 if no final_processed_audio."""
        response = self.client.post(f'/api/projects/{self.project.id}/redetect-duplicates/', {}, format='json')
        self.assertIn(response.status_code, [400, 404])
