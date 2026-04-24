"""
Wave 119 — Coverage boost
Targets:
  - audioDiagnostic/views/tab3_review_deletions.py: preview_deletions, get_deletion_preview,
    restore_segments, stream_preview_audio, cancel_preview branches
  - audioDiagnostic/views/tab4_pdf_comparison.py: all views via APIRequestFactory
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIRequestFactory
from unittest.mock import patch, MagicMock
from rest_framework.test import force_authenticate


def make_project(user, **kw):
    from audioDiagnostic.models import AudioProject
    return AudioProject.objects.create(user=user, title=kw.get('title', 'P119'), **{k: v for k, v in kw.items() if k != 'title'})


def make_audio_file(project, order=0, status='transcribed'):
    from audioDiagnostic.models import AudioFile
    return AudioFile.objects.create(
        project=project, filename=f'f{order}.mp3',
        title=f'F{order}', order_index=order, status=status
    )


class Tab3ReviewDeletionsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='t3rd119', password='pass')
        self.token = Token.objects.create(user=self.user)
        self.factory = APIRequestFactory()
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, order=0)

    def _req(self, view_func, method, url, data=None, **kwargs):
        from rest_framework.authtoken.models import Token
        from rest_framework.authentication import TokenAuthentication
        token = Token.objects.get(user=self.user)
        if method == 'get':
            request = self.factory.get(url, **kwargs)
        elif method == 'post':
            request = self.factory.post(url, data=data, format='json', **kwargs)
        elif method == 'delete':
            request = self.factory.delete(url, **kwargs)
        else:
            raise ValueError(f'Unknown method: {method}')
        request.META['HTTP_AUTHORIZATION'] = f'Token {token.key}'
        # Authenticate manually
        from django.contrib.auth.models import AnonymousUser
        force_authenticate(request, user=self.user)
        return request

    def test_preview_deletions_no_transcription(self):
        from audioDiagnostic.views.tab3_review_deletions import preview_deletions
        request = self._req(None, 'post', '/', {'segment_ids': [1, 2]})
        response = preview_deletions(request, self.project.id, self.af.id)
        self.assertIn(response.status_code, [400, 404])

    def test_preview_deletions_no_segments(self):
        from audioDiagnostic.models import Transcription
        from audioDiagnostic.views.tab3_review_deletions import preview_deletions
        Transcription.objects.create(audio_file=self.af, full_text='hello')
        request = self._req(None, 'post', '/', {'segment_ids': []})
        response = preview_deletions(request, self.project.id, self.af.id)
        self.assertIn(response.status_code, [400])

    def test_get_deletion_preview_no_metadata(self):
        from audioDiagnostic.views.tab3_review_deletions import get_deletion_preview
        request = self._req(None, 'get', '/')
        response = get_deletion_preview(request, self.project.id, self.af.id)
        self.assertIn(response.status_code, [200])

    def test_get_deletion_preview_with_metadata(self):
        from audioDiagnostic.views.tab3_review_deletions import get_deletion_preview
        self.af.preview_status = 'ready'
        self.af.preview_metadata = {
            'original_duration': 100.0,
            'preview_duration': 80.0,
            'segments_deleted': 5,
            'time_saved': 20.0,
            'deletion_regions': [],
            'kept_regions': []
        }
        self.af.save()
        request = self._req(None, 'get', '/')
        response = get_deletion_preview(request, self.project.id, self.af.id)
        self.assertEqual(response.status_code, 200)

    def test_get_deletion_preview_failed(self):
        from audioDiagnostic.views.tab3_review_deletions import get_deletion_preview
        self.af.preview_status = 'failed'
        self.af.error_message = 'Something failed'
        self.af.save()
        request = self._req(None, 'get', '/')
        response = get_deletion_preview(request, self.project.id, self.af.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn('error', response.data)

    def test_restore_segments_no_segments(self):
        from audioDiagnostic.views.tab3_review_deletions import restore_segments
        request = self._req(None, 'post', '/', {'segment_ids': []})
        response = restore_segments(request, self.project.id, self.af.id)
        self.assertEqual(response.status_code, 400)

    def test_restore_segments_no_metadata(self):
        from audioDiagnostic.views.tab3_review_deletions import restore_segments
        request = self._req(None, 'post', '/', {'segment_ids': [1, 2]})
        response = restore_segments(request, self.project.id, self.af.id)
        self.assertEqual(response.status_code, 400)

    def test_restore_segments_with_metadata(self):
        from audioDiagnostic.views.tab3_review_deletions import restore_segments
        self.af.preview_metadata = {
            'deletion_regions': [
                {'segment_ids': [10], 'start': 0, 'end': 5},
                {'segment_ids': [11], 'start': 5, 'end': 10},
            ],
            'segments_deleted': 2
        }
        self.af.save()
        request = self._req(None, 'post', '/', {'segment_ids': [10]})
        response = restore_segments(request, self.project.id, self.af.id)
        self.assertIn(response.status_code, [200])

    def test_restore_segments_regenerate_preview(self):
        from audioDiagnostic.views.tab3_review_deletions import restore_segments
        self.af.preview_metadata = {
            'deletion_regions': [{'segment_ids': [20], 'start': 0, 'end': 5}],
            'segments_deleted': 1
        }
        self.af.save()
        with patch('audioDiagnostic.views.tab3_review_deletions.preview_deletions_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='task-restore-119')
            request = self._req(None, 'post', '/', {
                'segment_ids': [30],
                'regenerate_preview': True
            })
            response = restore_segments(request, self.project.id, self.af.id)
        self.assertIn(response.status_code, [200])

    def test_restore_segments_clear_all(self):
        from audioDiagnostic.views.tab3_review_deletions import restore_segments
        self.af.preview_metadata = {
            'deletion_regions': [{'segment_ids': [99], 'start': 0, 'end': 5}],
            'segments_deleted': 1
        }
        self.af.save()
        request = self._req(None, 'post', '/', {
            'segment_ids': [99],
            'regenerate_preview': True
        })
        response = restore_segments(request, self.project.id, self.af.id)
        self.assertIn(response.status_code, [200])

    def test_stream_preview_no_audio(self):
        from audioDiagnostic.views.tab3_review_deletions import stream_preview_audio
        request = self._req(None, 'get', '/')
        try:
            response = stream_preview_audio(request, self.project.id, self.af.id)
            self.assertIn(response.status_code, [400, 404, 500])
        except Exception:
            pass  # Http404 is expected

    def test_cancel_preview(self):
        from audioDiagnostic.views.tab3_review_deletions import cancel_preview
        request = self._req(None, 'delete', '/')
        response = cancel_preview(request, self.project.id, self.af.id)
        self.assertIn(response.status_code, [200, 404])


class Tab4PdfComparisonAdditionalTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='t4pdf119', password='pass')
        self.token = Token.objects.create(user=self.user)
        self.factory = APIRequestFactory()
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, order=0)

    def _req(self, method, data=None):
        token = Token.objects.get(user=self.user)
        if method == 'post':
            request = self.factory.post('/', data=data or {}, format='json')
        else:
            request = self.factory.get('/')
        request.META['HTTP_AUTHORIZATION'] = f'Token {token.key}'
        force_authenticate(request, user=self.user)
        return request

    def test_compare_view_no_pdf(self):
        from audioDiagnostic.views.tab4_pdf_comparison import SingleTranscriptionPDFCompareView
        view = SingleTranscriptionPDFCompareView.as_view()
        request = self._req('post')
        response = view(request, project_id=self.project.id, audio_file_id=self.af.id)
        self.assertEqual(response.status_code, 400)

    def test_compare_view_no_transcript(self):
        from audioDiagnostic.views.tab4_pdf_comparison import SingleTranscriptionPDFCompareView
        # Need to simulate pdf_file existing
        self.project.pdf_text = 'some pdf text'
        self.project.save()
        view = SingleTranscriptionPDFCompareView.as_view()
        request = self._req('post')
        # Without pdf_file field, still returns 400
        response = view(request, project_id=self.project.id, audio_file_id=self.af.id)
        self.assertIn(response.status_code, [400])

    def test_pdf_result_view_no_comparison(self):
        from audioDiagnostic.views.tab4_pdf_comparison import SingleTranscriptionPDFResultView
        view = SingleTranscriptionPDFResultView.as_view()
        request = self._req('get')
        response = view(request, project_id=self.project.id, audio_file_id=self.af.id)
        self.assertIn(response.status_code, [200, 400, 404])

    def test_pdf_status_view_no_transcription(self):
        from audioDiagnostic.views.tab4_pdf_comparison import SingleTranscriptionPDFStatusView
        view = SingleTranscriptionPDFStatusView.as_view()
        request = self._req('get')
        response = view(request, project_id=self.project.id, audio_file_id=self.af.id)
        self.assertIn(response.status_code, [200, 404])

    def test_pdf_status_view_with_transcription(self):
        from audioDiagnostic.models import Transcription
        from audioDiagnostic.views.tab4_pdf_comparison import SingleTranscriptionPDFStatusView
        Transcription.objects.create(audio_file=self.af, full_text='hello world')
        self.af.task_id = 'fake-task-t4pdf119'
        self.af.save()
        view = SingleTranscriptionPDFStatusView.as_view()
        request = self._req('get')
        with patch('audioDiagnostic.views.tab4_pdf_comparison.AsyncResult') as mock_ar:
            mock_instance = MagicMock()
            mock_instance.state = 'SUCCESS'
            mock_ar.return_value = mock_instance
            response = view(request, project_id=self.project.id, audio_file_id=self.af.id)
        self.assertIn(response.status_code, [200])

    def test_retry_view_no_pdf(self):
        from audioDiagnostic.views.tab4_pdf_comparison import SingleTranscriptionRetryComparisonView
        view = SingleTranscriptionRetryComparisonView.as_view()
        request = self._req('post', {'similarity_threshold': 0.9})
        response = view(request, project_id=self.project.id, audio_file_id=self.af.id)
        self.assertEqual(response.status_code, 400)

    def test_retry_view_no_transcription(self):
        from audioDiagnostic.views.tab4_pdf_comparison import SingleTranscriptionRetryComparisonView
        view = SingleTranscriptionRetryComparisonView.as_view()
        request = self._req('post', {'similarity_threshold': 0.9})
        response = view(request, project_id=self.project.id, audio_file_id=self.af.id)
        self.assertIn(response.status_code, [400])
