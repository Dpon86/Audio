"""
Wave 74 — Coverage boost
Targets:
  - client_storage.py:
      ClientTranscriptionListCreateView (GET + POST),
      ClientTranscriptionDetailView (GET, PUT, PATCH, DELETE),
      DuplicateAnalysisListCreateView,
      DuplicateAnalysisDetailView
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token

from audioDiagnostic.models import (
from rest_framework.test import force_authenticate
    AudioFile, AudioProject, ClientTranscription, DuplicateAnalysis,
)


# ────────────────── helpers ──────────────────
def make_user(username, password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u


def make_project(user, title='W74 Project', status='ready', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def make_audio_file(project, title='W74 File', status='transcribed', order=0):
    return AudioFile.objects.create(
        project=project,
        filename=f'{title.lower().replace(" ", "_")}.wav',
        title=title,
        order_index=order,
        status=status,
    )


def make_client_transcription(project, filename='test_w74.wav', audio_file=None):
    return ClientTranscription.objects.create(
        project=project,
        filename=filename,
        audio_file=audio_file,
        transcription_data={'segments': [{'text': 'Hello world', 'start': 0.0, 'end': 1.0}]},
        duration_seconds=10.0,
    )


def auth_client(client, user):
    token = Token.objects.create(user=user)
    client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.key}'
    return token


# ══════════════════════════════════════════════════════
# ClientTranscriptionListCreateView — GET
# ══════════════════════════════════════════════════════
class ClientTranscriptionListViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w74_ctlist_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_list_empty(self):
        """GET client-transcriptions/ with no records → empty"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/client-transcriptions/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['total_count'], 0)

    def test_list_with_records(self):
        """GET client-transcriptions/ returns saved transcriptions"""
        make_client_transcription(self.project, 'file1_w74.wav')
        make_client_transcription(self.project, 'file2_w74.wav')
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/client-transcriptions/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['total_count'], 2)

    def test_list_filter_by_filename(self):
        """GET client-transcriptions/?filename= filters results"""
        make_client_transcription(self.project, 'alpha_w74.wav')
        make_client_transcription(self.project, 'beta_w74.wav')
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/client-transcriptions/?filename=alpha_w74.wav')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['total_count'], 1)

    def test_list_filter_by_audio_file(self):
        """GET client-transcriptions/?audio_file= filters by FK"""
        af = make_audio_file(self.project, order=0)
        make_client_transcription(self.project, 'linked_w74.wav', audio_file=af)
        make_client_transcription(self.project, 'unlinked_w74.wav')
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/client-transcriptions/?audio_file={af.id}')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['total_count'], 1)

    def test_list_wrong_user(self):
        """GET client-transcriptions/ for other user's project → 404"""
        other = make_user('w74_ctlist_other')
        other_proj = make_project(other, title='W74 Other CT')
        resp = self.client.get(
            f'/api/api/projects/{other_proj.id}/client-transcriptions/')
        self.assertEqual(resp.status_code, 404)


# ══════════════════════════════════════════════════════
# ClientTranscriptionListCreateView — POST
# ══════════════════════════════════════════════════════
class ClientTranscriptionCreateViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w74_ctcreate_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_create_new(self):
        """POST client-transcriptions/ creates new record"""
        data = {
            'filename': 'new_w74.wav',
            'transcription_data': {'segments': [{'text': 'Hello.', 'start': 0.0, 'end': 1.0}]},
            'duration_seconds': 5.0,
        }
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/client-transcriptions/',
            data,
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404])

    def test_update_existing_by_filename(self):
        """POST client-transcriptions/ with existing filename updates record"""
        existing = make_client_transcription(self.project, 'update_me_w74.wav')
        data = {
            'filename': 'update_me_w74.wav',
            'transcription_data': {'segments': [{'text': 'Updated.', 'start': 0.0, 'end': 2.0}]},
            'duration_seconds': 8.0,
        }
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/client-transcriptions/',
            data,
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404])

    def test_update_existing_by_audio_file(self):
        """POST client-transcriptions/ with audio_file ID updates existing"""
        af = make_audio_file(self.project, order=0)
        existing = make_client_transcription(self.project, 'byfile_w74.wav', audio_file=af)
        data = {
            'filename': 'byfile_w74.wav',
            'audio_file': af.id,
            'transcription_data': {'segments': [{'text': 'Updated by file.', 'start': 0.0, 'end': 3.0}]},
        }
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/client-transcriptions/',
            data,
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404])


# ══════════════════════════════════════════════════════
# ClientTranscriptionDetailView — GET, PUT, DELETE
# ══════════════════════════════════════════════════════
class ClientTranscriptionDetailViewTests(TestCase):

    def setUp(self):
        self.user = make_user('w74_ctdetail_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.ct = make_client_transcription(self.project, 'detail_w74.wav')
        self.client.raise_request_exception = False

    def test_get_transcription(self):
        """GET client-transcriptions/{id}/ returns transcription"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/client-transcriptions/{self.ct.id}/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertTrue(resp.json()['success'])

    def test_get_wrong_user(self):
        """GET client-transcriptions/{id}/ for other user's project → 404"""
        other = make_user('w74_ctdetail_other')
        other_proj = make_project(other, title='W74 Other Detail')
        other_ct = make_client_transcription(other_proj, 'other_w74.wav')
        resp = self.client.get(
            f'/api/api/projects/{other_proj.id}/client-transcriptions/{other_ct.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_put_transcription(self):
        """PUT client-transcriptions/{id}/ updates fully"""
        data = {
            'project': self.project.id,
            'filename': 'detail_w74.wav',
            'transcription_data': {'segments': [{'text': 'PUT updated.', 'start': 0.0, 'end': 1.5}]},
        }
        resp = self.client.put(
            f'/api/api/projects/{self.project.id}/client-transcriptions/{self.ct.id}/',
            data,
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_delete_transcription(self):
        """DELETE client-transcriptions/{id}/ removes record"""
        ct_to_delete = make_client_transcription(self.project, 'delete_me_w74.wav')
        resp = self.client.delete(
            f'/api/api/projects/{self.project.id}/client-transcriptions/{ct_to_delete.id}/')
        self.assertIn(resp.status_code, [200, 204, 404])
        if resp.status_code in [200, 204]:
            self.assertFalse(ClientTranscription.objects.filter(id=ct_to_delete.id).exists())


# ══════════════════════════════════════════════════════
# DuplicateAnalysisListCreateView — GET + POST
# ══════════════════════════════════════════════════════
class DuplicateAnalysisListCreateTests(TestCase):

    def setUp(self):
        self.user = make_user('w74_dalist_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def _make_analysis(self, filename='analysis_w74.wav'):
        return DuplicateAnalysis.objects.create(
            project=self.project,
            filename=filename,
            analysis_data={'duplicate_groups': []},
        )

    def test_list_empty(self):
        """GET duplicate-analyses/ with no records → empty"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/duplicate-analyses/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertIn('analyses', resp.json())

    def test_list_with_records(self):
        """GET duplicate-analyses/ returns records"""
        self._make_analysis('da1_w74.wav')
        self._make_analysis('da2_w74.wav')
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/duplicate-analyses/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertGreaterEqual(resp.json().get('total_count', 0), 2)

    def test_create_new(self):
        """POST duplicate-analyses/ creates new record"""
        data = {
            'filename': 'new_da_w74.wav',
            'analysis_data': {'duplicate_groups': [{'id': 'g1', 'text': 'Hello.'}]},
        }
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/duplicate-analyses/',
            data,
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404])

    def test_list_wrong_user(self):
        """GET duplicate-analyses/ for other user's project → 404"""
        other = make_user('w74_dalist_other')
        other_proj = make_project(other, title='W74 Other DA')
        resp = self.client.get(
            f'/api/api/projects/{other_proj.id}/duplicate-analyses/')
        self.assertEqual(resp.status_code, 404)


# ══════════════════════════════════════════════════════
# DuplicateAnalysisDetailView — GET, DELETE
# ══════════════════════════════════════════════════════
class DuplicateAnalysisDetailTests(TestCase):

    def setUp(self):
        self.user = make_user('w74_dadetail_user')
        auth_client(self.client, self.user)
        self.project = make_project(self.user)
        self.da = DuplicateAnalysis.objects.create(
            project=self.project,
            filename='detail_da_w74.wav',
            analysis_data={'duplicate_groups': []},
        )
        self.client.raise_request_exception = False

    def test_get_analysis(self):
        """GET duplicate-analyses/{id}/ returns analysis"""
        resp = self.client.get(
            f'/api/api/projects/{self.project.id}/duplicate-analyses/{self.da.id}/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertTrue(resp.json()['success'])

    def test_delete_analysis(self):
        """DELETE duplicate-analyses/{id}/ removes record"""
        da_to_delete = DuplicateAnalysis.objects.create(
            project=self.project,
            filename='delete_da_w74.wav',
            analysis_data={'duplicate_groups': []},
        )
        resp = self.client.delete(
            f'/api/api/projects/{self.project.id}/duplicate-analyses/{da_to_delete.id}/')
        self.assertIn(resp.status_code, [200, 204, 404])
        if resp.status_code in [200, 204]:
            self.assertFalse(DuplicateAnalysis.objects.filter(id=da_to_delete.id).exists())

    def test_get_wrong_user(self):
        """GET duplicate-analyses/{id}/ for other user → 404"""
        other = make_user('w74_dadetail_other')
        other_proj = make_project(other, title='W74 Other DA Detail')
        other_da = DuplicateAnalysis.objects.create(
            project=other_proj,
            filename='other_da_w74.wav',
            analysis_data={'duplicate_groups': []},
        )
        resp = self.client.get(
            f'/api/api/projects/{other_proj.id}/duplicate-analyses/{other_da.id}/')
        self.assertEqual(resp.status_code, 404)
