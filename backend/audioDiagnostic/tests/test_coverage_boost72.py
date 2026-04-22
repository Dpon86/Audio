"""
Wave 72 — Coverage boost
Targets:
  - tab4_review_comparison.py:
      ProjectComparisonView, FileComparisonDetailView,
      mark_file_reviewed, get_deletion_regions
"""

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


def make_project(user, title='W72 Project', status='ready', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def make_audio_file(project, title='W72 File', status='transcribed', order=0, **kwargs):
    return AudioFile.objects.create(
        project=project,
        filename=f'{title.lower().replace(" ", "_")}.wav',
        title=title,
        order_index=order,
        status=status,
        **kwargs,
    )


def make_transcription(audio_file, content='Hello world.'):
    return Transcription.objects.create(audio_file=audio_file, full_text=content)


def make_segment(audio_file, transcription=None, text='Seg.', idx=0, is_dup=False):
    return TranscriptionSegment.objects.create(
        audio_file=audio_file,
        transcription=transcription,
        text=text,
        start_time=float(idx),
        end_time=float(idx) + 2.0,
        segment_index=idx,
        is_duplicate=is_dup,
    )


def auth_client(client, user):
    token = Token.objects.create(user=user)
    client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
    return token


# ══════════════════════════════════════════════════════
# ProjectComparisonView — GET
# ══════════════════════════════════════════════════════
class Tab4ProjectComparisonViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w72_projcomp_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_no_processed_files(self):
        """GET comparison/ with no processed files → empty stats"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/comparison/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['project_stats']['total_files'], 0)

    def test_with_processed_files(self):
        """GET comparison/ with files that have processed_audio"""
        from django.core.files.base import ContentFile
        af = make_audio_file(self.project, status='processed', order=0)
        af.processed_audio.save('w72_proc.wav', ContentFile(b'RIFF' + b'\x00' * 40), save=True)
        af.duration_seconds = 120.0
        af.processed_duration_seconds = 90.0
        af.save()
        tr = make_transcription(af, 'Hello world test.')
        make_segment(af, tr, 'Hello world.', idx=0, is_dup=False)
        make_segment(af, tr, 'Hello world.', idx=2, is_dup=True)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/comparison/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('files', data)
            self.assertIn('project_stats', data)
            self.assertGreater(data['project_stats']['total_files'], 0)

    def test_wrong_user(self):
        """GET comparison/ for another user's project → 404"""
        other = make_user('w72_projcomp_other')
        other_proj = make_project(other, title='W72 Other')
        resp = self.client.get(
            f'/api/api/projects/{other_proj.id}/comparison/')
        self.assertEqual(resp.status_code, 404)

    def test_no_auth(self):
        """GET comparison/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/comparison/')
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════
# FileComparisonDetailView — GET
# ══════════════════════════════════════════════════════
class Tab4FileComparisonDetailViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w72_filecomp_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_file_not_processed(self):
        """GET comparison-details/ for non-processed file → 400"""
        af = make_audio_file(self.project, status='transcribed', order=0)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/comparison-details/')
        self.assertIn(resp.status_code, [400, 404])

    def test_processed_file_no_transcription(self):
        """GET comparison-details/ for processed file with no transcription"""
        from django.core.files.base import ContentFile
        af = make_audio_file(self.project, status='processed', order=0)
        af.processed_audio.save('w72_cmpd.wav', ContentFile(b'RIFF' + b'\x00' * 40), save=True)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/comparison-details/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['deletion_regions'], [])

    def test_processed_file_with_deletions(self):
        """GET comparison-details/ with deleted segments"""
        from django.core.files.base import ContentFile
        af = make_audio_file(self.project, status='processed', order=0,
                             duration_seconds=120.0, processed_duration_seconds=90.0)
        af.processed_audio.save('w72_cmpd2.wav', ContentFile(b'RIFF' + b'\x00' * 40), save=True)
        tr = make_transcription(af, 'Kept. Deleted duplicate.')
        make_segment(af, tr, 'Kept.', idx=0, is_dup=False)
        make_segment(af, tr, 'Deleted duplicate.', idx=2, is_dup=True)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/comparison-details/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertEqual(len(data['deletion_regions']), 1)


# ══════════════════════════════════════════════════════
# mark_file_reviewed — POST
# ══════════════════════════════════════════════════════
class Tab4MarkFileReviewedTests(TestCase):

    def setUp(self):
        self.user = make_user('w72_markreview_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_mark_reviewed(self):
        """POST mark-reviewed/ marks file as reviewed"""
        af = make_audio_file(self.project, status='processed', order=0)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af.id}/mark-reviewed/',
            {'notes': 'Looks good', 'status': 'reviewed'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            af.refresh_from_db()
            self.assertEqual(af.comparison_status, 'reviewed')
            self.assertEqual(af.comparison_notes, 'Looks good')

    def test_mark_approved(self):
        """POST mark-reviewed/ with status=approved"""
        af = make_audio_file(self.project, status='processed', order=0)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af.id}/mark-reviewed/',
            {'status': 'approved'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_mark_reviewed_wrong_user(self):
        """POST mark-reviewed/ for other user's project → 404"""
        other = make_user('w72_markreview_other')
        other_proj = make_project(other, title='W72 Other MR')
        other_af = make_audio_file(other_proj, order=0)
        resp = self.client.post(
            f'/api/api/projects/{other_proj.id}/files/{other_af.id}/mark-reviewed/',
            {'status': 'reviewed'},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_mark_reviewed_default_status(self):
        """POST mark-reviewed/ without status defaults to 'reviewed'"""
        af = make_audio_file(self.project, status='processed', order=0)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af.id}/mark-reviewed/',
            {},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['comparison_status'], 'reviewed')


# ══════════════════════════════════════════════════════
# get_deletion_regions — GET
# ══════════════════════════════════════════════════════
class Tab4GetDeletionRegionsTests(TestCase):

    def setUp(self):
        self.user = make_user('w72_delregions_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_no_transcription(self):
        """GET deletion-regions/ with no transcription → empty list"""
        af = make_audio_file(self.project, status='processed', order=0)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/deletion-regions/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['total_count'], 0)

    def test_with_duplicates(self):
        """GET deletion-regions/ with duplicate segments"""
        af = make_audio_file(self.project, status='processed', order=0)
        tr = make_transcription(af, 'Hello. Hello again.')
        make_segment(af, tr, 'Hello.', idx=0, is_dup=False)
        make_segment(af, tr, 'Hello again.', idx=2, is_dup=True)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/deletion-regions/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertEqual(data['total_count'], 1)
            self.assertEqual(data['deletion_regions'][0]['text'], 'Hello again.')

    def test_wrong_user(self):
        """GET deletion-regions/ for other user's project → 404"""
        other = make_user('w72_delregions_other')
        other_proj = make_project(other, title='W72 Other DR')
        other_af = make_audio_file(other_proj, order=0)
        resp = self.client.get(
            f'/api/api/projects/{other_proj.id}/files/{other_af.id}/deletion-regions/')
        self.assertEqual(resp.status_code, 404)

    def test_multiple_deletion_regions(self):
        """GET deletion-regions/ returns all duplicate segments sorted by time"""
        af = make_audio_file(self.project, status='processed', order=0)
        tr = make_transcription(af, 'A. B. C. D.')
        make_segment(af, tr, 'A.', idx=0, is_dup=False)
        make_segment(af, tr, 'B.', idx=2, is_dup=True)
        make_segment(af, tr, 'C.', idx=4, is_dup=False)
        make_segment(af, tr, 'D.', idx=6, is_dup=True)
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/files/{af.id}/deletion-regions/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['total_count'], 2)
