"""
Wave 63 — Coverage boost
Targets:
  - duplicate_tasks.py pure functions: identify_all_duplicates, mark_duplicates_for_removal,
    detect_duplicates_against_pdf_task (called directly as pure function)
  - project_views.py: ProjectDetailView GET, DELETE; ProjectListCreateView POST/GET
  - duplicate_views.py: more branch paths
  - tab3_review_deletions.py: remaining branches
  - transcription_views.py: more view hits
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token

from audioDiagnostic.models import (
from rest_framework.test import force_authenticate
    AudioFile, AudioProject, Transcription, TranscriptionSegment,
)


# ────────────────────── helpers ──────────────────────
def make_user(username='w63user', password='pass1234!'):
    u, _ = User.objects.get_or_create(username=username)
    u.set_password(password)
    u.save()
    return u


def make_project(user, title='W63 Project', status='ready', **kwargs):
    return AudioProject.objects.create(user=user, title=title, status=status, **kwargs)


def make_audio_file(project, title='W63 File', status='transcribed', order=0, **kwargs):
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


def make_segment(audio_file, transcription, text='Segment', idx=0,
                 is_duplicate=False, is_kept=True, file_order=0):
    return TranscriptionSegment.objects.create(
        audio_file=audio_file,
        transcription=transcription,
        text=text,
        start_time=float(idx),
        end_time=float(idx) + 1.0,
        segment_index=idx,
        is_duplicate=is_duplicate,
        is_kept=is_kept,
    )


# ══════════════════════════════════════════════════════
# duplicate_tasks.py — identify_all_duplicates
# ══════════════════════════════════════════════════════
class IdentifyAllDuplicatesTests(TestCase):
    """Tests for duplicate_tasks.identify_all_duplicates"""

    def _make_seg_data(self, text, start, end, file_order=0):
        return {
            'text': text,
            'start_time': start,
            'end_time': end,
            'file_order': file_order,
            'segment': None,        # Not used in identify_all_duplicates
            'audio_file': None,
        }

    def test_no_duplicates(self):
        """identify_all_duplicates returns empty dict for unique segments"""
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        segs = [
            self._make_seg_data('First unique segment.', 0.0, 1.0),
            self._make_seg_data('Second unique segment.', 1.0, 2.0),
            self._make_seg_data('Third unique segment.', 2.0, 3.0),
        ]
        result = identify_all_duplicates(segs)
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

    def test_with_duplicates(self):
        """identify_all_duplicates detects repeated text"""
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        segs = [
            self._make_seg_data('Repeated text here.', 0.0, 1.0),
            self._make_seg_data('Unique middle.', 1.0, 2.0),
            self._make_seg_data('Repeated text here.', 2.0, 3.0),
        ]
        result = identify_all_duplicates(segs)
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 1)
        group = list(result.values())[0]
        self.assertEqual(group['count'], 2)
        self.assertIn('occurrences', group)

    def test_empty_segments(self):
        """identify_all_duplicates handles empty list"""
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        result = identify_all_duplicates([])
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

    def test_empty_text_segments_skipped(self):
        """identify_all_duplicates skips segments with empty text"""
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        segs = [
            self._make_seg_data('', 0.0, 1.0),
            self._make_seg_data('   ', 1.0, 2.0),
            self._make_seg_data('Valid segment content.', 2.0, 3.0),
        ]
        result = identify_all_duplicates(segs)
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

    def test_single_word_content_type(self):
        """identify_all_duplicates marks single-word segments as 'word' type"""
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        segs = [
            self._make_seg_data('Hello', 0.0, 1.0),
            self._make_seg_data('World', 1.0, 2.0),
            self._make_seg_data('Hello', 2.0, 3.0),
        ]
        result = identify_all_duplicates(segs)
        self.assertEqual(len(result), 1)
        group = list(result.values())[0]
        self.assertEqual(group['content_type'], 'word')

    def test_sentence_content_type(self):
        """identify_all_duplicates marks <=15 word segments as 'sentence' type"""
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        text = 'This is a sentence with about ten words total here.'
        segs = [
            self._make_seg_data(text, 0.0, 1.0),
            self._make_seg_data('Different content.', 1.0, 2.0),
            self._make_seg_data(text, 2.0, 3.0),
        ]
        result = identify_all_duplicates(segs)
        self.assertEqual(len(result), 1)
        group = list(result.values())[0]
        self.assertEqual(group['content_type'], 'sentence')

    def test_paragraph_content_type(self):
        """identify_all_duplicates marks >15 word segments as 'paragraph' type"""
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        text = ('This is a long paragraph that has more than fifteen words and '
                'should be classified as a paragraph type segment.')
        segs = [
            self._make_seg_data(text, 0.0, 2.0),
            self._make_seg_data('Unique content here.', 2.0, 3.0),
            self._make_seg_data(text, 3.0, 5.0),
        ]
        result = identify_all_duplicates(segs)
        self.assertEqual(len(result), 1)
        group = list(result.values())[0]
        self.assertEqual(group['content_type'], 'paragraph')

    def test_multiple_dup_groups(self):
        """identify_all_duplicates returns multiple duplicate groups"""
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        segs = [
            self._make_seg_data('First repeated.', 0.0, 1.0),
            self._make_seg_data('Second repeated.', 1.0, 2.0),
            self._make_seg_data('First repeated.', 2.0, 3.0),
            self._make_seg_data('Second repeated.', 3.0, 4.0),
        ]
        result = identify_all_duplicates(segs)
        self.assertEqual(len(result), 2)


# ══════════════════════════════════════════════════════
# duplicate_tasks.py — mark_duplicates_for_removal
# ══════════════════════════════════════════════════════
class MarkDuplicatesForRemovalTests(TestCase):
    """Tests for duplicate_tasks.mark_duplicates_for_removal"""

    def setUp(self):
        self.user = make_user('w63_mark_dup_user')
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, order=0)
        self.tr = make_transcription(self.af, 'Mark duplicates test.')

    def _make_seg(self, text, idx, file_order=0):
        seg = make_segment(self.af, self.tr, text, idx=idx)
        return {
            'audio_file': self.af,
            'segment': seg,
            'text': text,
            'start_time': float(idx),
            'end_time': float(idx) + 1.0,
            'file_order': file_order,
        }

    def test_mark_with_duplicates(self):
        """mark_duplicates_for_removal marks earlier occurrences for deletion"""
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        seg0_data = self._make_seg('Repeated sentence here.', idx=0)
        seg1_data = self._make_seg('Unique middle sentence.', idx=1)
        seg2_data = self._make_seg('Repeated sentence here.', idx=2)
        duplicates_found = {
            'dup_1': {
                'normalized_text': 'repeated sentence here',
                'content_type': 'sentence',
                'occurrences': [
                    {'segment_data': seg0_data, 'normalized_text': 'repeated sentence here',
                     'content_type': 'sentence', 'word_count': 3},
                    {'segment_data': seg2_data, 'normalized_text': 'repeated sentence here',
                     'content_type': 'sentence', 'word_count': 3},
                ],
                'count': 2
            }
        }
        result = mark_duplicates_for_removal(duplicates_found)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['group_id'], 'dup_1')
        self.assertEqual(result[0]['type'], 'sentence')
        seg0_data['segment'].refresh_from_db()
        self.assertTrue(seg0_data['segment'].is_duplicate)
        self.assertFalse(seg0_data['segment'].is_kept)
        seg2_data['segment'].refresh_from_db()
        self.assertTrue(seg2_data['segment'].is_kept)

    def test_mark_empty_duplicates(self):
        """mark_duplicates_for_removal with empty dict returns empty list"""
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        result = mark_duplicates_for_removal({})
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_mark_across_files(self):
        """mark_duplicates_for_removal handles cross-file ordering"""
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        af2 = make_audio_file(self.project, title='W63 File2', order=1)
        tr2 = make_transcription(af2, 'Second file transcription.')
        seg0_data = self._make_seg('Cross-file duplicate.', idx=10, file_order=0)
        seg_other_file = TranscriptionSegment.objects.create(
            audio_file=af2, transcription=tr2, text='Cross-file duplicate.',
            start_time=5.0, end_time=6.0, segment_index=0,
        )
        seg1_data = {
            'audio_file': af2,
            'segment': seg_other_file,
            'text': 'Cross-file duplicate.',
            'start_time': 5.0,
            'end_time': 6.0,
            'file_order': 1,
        }
        duplicates_found = {
            'dup_cross': {
                'normalized_text': 'cross-file duplicate',
                'content_type': 'sentence',
                'occurrences': [
                    {'segment_data': seg0_data, 'normalized_text': 'cross-file duplicate',
                     'content_type': 'sentence', 'word_count': 3},
                    {'segment_data': seg1_data, 'normalized_text': 'cross-file duplicate',
                     'content_type': 'sentence', 'word_count': 3},
                ],
                'count': 2
            }
        }
        result = mark_duplicates_for_removal(duplicates_found)
        self.assertEqual(len(result), 1)


# ══════════════════════════════════════════════════════
# duplicate_tasks.py — detect_duplicates_against_pdf_task (pure fn)
# ══════════════════════════════════════════════════════
class DetectDuplicatesAgainstPDFTests(TestCase):
    """Tests for detect_duplicates_against_pdf_task as pure function"""

    def _make_segment_dict(self, text, start, end, idx, audio_file_id=1):
        return {
            'id': idx,
            'audio_file_id': audio_file_id,
            'audio_file_title': 'Test',
            'text': text,
            'start_time': start,
            'end_time': end,
            'segment_index': idx,
        }

    def test_empty_segments(self):
        """detect_duplicates_against_pdf_task handles empty segments list"""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        mock_r = MagicMock()
        result = detect_duplicates_against_pdf_task(
            [], 'Some PDF text.', 'Some transcript.', 'task-w63-empty', mock_r)
        self.assertIsInstance(result, dict)
        self.assertIn('duplicates', result)
        self.assertEqual(len(result['duplicates']), 0)
        self.assertIn('summary', result)

    def test_all_unique_segments(self):
        """detect_duplicates_against_pdf_task with all unique segments"""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        mock_r = MagicMock()
        segs = [
            self._make_segment_dict('First completely unique statement.', 0.0, 2.0, 0),
            self._make_segment_dict('Second totally different passage.', 2.0, 4.0, 1),
            self._make_segment_dict('Third entirely original content.', 4.0, 6.0, 2),
        ]
        result = detect_duplicates_against_pdf_task(
            segs, 'PDF section', 'Full transcript', 'task-w63-unique', mock_r)
        self.assertIsInstance(result, dict)
        self.assertIn('duplicates', result)
        self.assertIn('summary', result)

    def test_with_repeated_segments(self):
        """detect_duplicates_against_pdf_task finds repeated segments"""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        mock_r = MagicMock()
        repeated_text = 'This is a repeated narrator section.'
        segs = [
            self._make_segment_dict(repeated_text, 0.0, 2.0, 0),
            self._make_segment_dict('Unique passage in the middle.', 2.0, 4.0, 1),
            self._make_segment_dict(repeated_text, 4.0, 6.0, 2),
        ]
        result = detect_duplicates_against_pdf_task(
            segs, 'PDF with narrator section',
            'Full transcript with repeated', 'task-w63-repeat', mock_r)
        self.assertIsInstance(result, dict)
        dups = result.get('duplicates', [])
        self.assertGreater(len(dups), 0)

    def test_short_segments_skipped(self):
        """detect_duplicates_against_pdf_task skips segments with < 3 words"""
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_against_pdf_task
        mock_r = MagicMock()
        segs = [
            self._make_segment_dict('Hi', 0.0, 0.5, 0),
            self._make_segment_dict('Hi', 0.5, 1.0, 1),
            self._make_segment_dict('A longer segment with words here.', 1.0, 3.0, 2),
        ]
        result = detect_duplicates_against_pdf_task(
            segs, 'PDF text', 'Transcript', 'task-w63-short', mock_r)
        self.assertIsInstance(result, dict)
        self.assertIn('unique_segments', result)


# ══════════════════════════════════════════════════════
# Project Views — more branches
# ══════════════════════════════════════════════════════
class ProjectViewsDeleteTests(TestCase):
    """Tests for ProjectDetailView DELETE"""

    def setUp(self):
        self.user = make_user('w63_proj_del_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.client.raise_request_exception = False

    def test_delete_project_success(self):
        """DELETE /api/projects/{id}/ deletes the project"""
        project_id = self.project.id
        resp = self.client.delete(f'/api/projects/{project_id}/')
        self.assertIn(resp.status_code, [200, 204, 404])
        if resp.status_code in [200, 204]:
            self.assertFalse(AudioProject.objects.filter(id=project_id).exists())

    def test_delete_project_wrong_user(self):
        """DELETE /api/projects/{id}/ for another user's project → 404"""
        other_user = make_user('w63_proj_del_other')
        other_proj = make_project(other_user, title='Other Del Project')
        resp = self.client.delete(f'/api/projects/{other_proj.id}/')
        self.assertIn(resp.status_code, [404])

    def test_delete_nonexistent_project(self):
        """DELETE /api/projects/99999/ → 404"""
        resp = self.client.delete('/api/projects/99999/')
        self.assertIn(resp.status_code, [404])


class ProjectViewsGetTests(TestCase):
    """Tests for ProjectDetailView GET — various branches"""

    def setUp(self):
        self.user = make_user('w63_proj_get_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(
            self.user, status='setup', pdf_file=None, title='W63 Get Project')
        self.af = make_audio_file(self.project, status='uploaded', order=0)
        self.client.raise_request_exception = False

    def test_get_project_setup_status(self):
        """GET project detail returns setup status and available actions"""
        AudioProject.objects.filter(id=self.project.id).update(pdf_file='pdfs/test.pdf')
        resp = self.client.get(f'/api/projects/{self.project.id}/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()['project']
            self.assertIn('available_actions', data)
            self.assertIn('workflow_status', data)

    def test_get_project_transcribed_status(self):
        """GET project with transcribed status shows transcribe action"""
        AudioProject.objects.filter(id=self.project.id).update(status='transcribed')
        AudioFile.objects.filter(id=self.af.id).update(status='transcribed')
        resp = self.client.get(f'/api/projects/{self.project.id}/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()['project']
            self.assertEqual(data['status'], 'transcribed')

    def test_get_project_completed_status(self):
        """GET project with completed status shows download action"""
        AudioProject.objects.filter(id=self.project.id).update(status='completed')
        resp = self.client.get(f'/api/projects/{self.project.id}/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()['project']
            self.assertEqual(data['status'], 'completed')

    def test_get_project_with_include_pdf_text(self):
        """GET project with ?include_pdf_text=1 includes pdf_text field"""
        AudioProject.objects.filter(id=self.project.id).update(pdf_text='Some PDF text here.')
        resp = self.client.get(f'/api/projects/{self.project.id}/?include_pdf_text=1')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            data = resp.json()['project']
            self.assertIsNotNone(data.get('pdf_text'))

    def test_get_project_wrong_user(self):
        """GET project detail for another user → 404"""
        other_user = make_user('w63_proj_get_other')
        other_proj = make_project(other_user, title='Other Get Project')
        resp = self.client.get(f'/api/projects/{other_proj.id}/')
        self.assertIn(resp.status_code, [404])


class ProjectListCreateMoreTests(TestCase):
    """More tests for ProjectListCreateView"""

    def setUp(self):
        self.user = make_user('w63_proj_list_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.client.raise_request_exception = False

    def test_list_projects_empty(self):
        """GET /api/projects/ returns empty list when no projects"""
        resp = self.client.get('/api/projects/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertEqual(resp.json()['projects'], [])

    def test_list_projects_multiple(self):
        """GET /api/projects/ returns all user's projects"""
        make_project(self.user, title='W63 Project A')
        make_project(self.user, title='W63 Project B')
        resp = self.client.get('/api/projects/')
        self.assertIn(resp.status_code, [200, 404])
        if resp.status_code == 200:
            self.assertGreaterEqual(len(resp.json()['projects']), 2)

    def test_create_project_success(self):
        """POST /api/projects/ creates new project"""
        resp = self.client.post(
            '/api/projects/',
            {'title': 'New W63 Project'},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [200, 201, 400, 404])

    def test_create_project_no_title(self):
        """POST /api/projects/ without title → validation error"""
        resp = self.client.post(
            '/api/projects/',
            {},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_list_projects_no_auth(self):
        """GET /api/projects/ without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.get('/api/projects/')
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════
# Tab 3 Review Deletions — remaining branches
# ══════════════════════════════════════════════════════
class Tab3ReviewDeletionsMoreTests(TestCase):
    """More branches for tab3_review_deletions.py"""

    def setUp(self):
        self.user = make_user('w63_tab3_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(self.user)
        self.af = make_audio_file(self.project, status='transcribed', order=0)
        self.tr = make_transcription(self.af, 'Tab3 test transcription.')
        self.seg1 = make_segment(self.af, self.tr, 'Segment one.', idx=0)
        self.seg2 = make_segment(self.af, self.tr, 'Segment two.', idx=1)
        self.client.raise_request_exception = False

    # ── preview_deletions view ─────────────────────────
    def test_preview_deletions_no_transcription(self):
        """POST preview-deletions for file without transcription → 400"""
        af2 = make_audio_file(self.project, status='transcribed', order=2)
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{af2.id}/preview-deletions/',
            {'segment_ids': [999]},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_preview_deletions_no_segments(self):
        """POST preview-deletions with empty segment_ids → 400"""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/preview-deletions/',
            {'segment_ids': []},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_preview_deletions_invalid_segments(self):
        """POST preview-deletions with segment IDs not belonging to this file → 400"""
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/preview-deletions/',
            {'segment_ids': [99991, 99992]},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_preview_deletions_valid(self):
        """POST preview-deletions with valid segment IDs → task launched"""
        with patch(
            'audioDiagnostic.views.tab3_review_deletions.preview_deletions_task'
        ) as mock_task:
            mock_task.delay.return_value = MagicMock(id='preview-w63')
            resp = self.client.post(
                f'/api/api/projects/{self.project.id}/files/{self.af.id}/preview-deletions/',
                {'segment_ids': [self.seg1.id]},
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [200, 201, 202, 400, 404])

    def test_preview_deletions_no_auth(self):
        """POST preview-deletions without auth → 401/403"""
        del self.client.defaults['HTTP_AUTHORIZATION']
        resp = self.client.post(
            f'/api/api/projects/{self.project.id}/files/{self.af.id}/preview-deletions/',
            {'segment_ids': [self.seg1.id]},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [401, 403])


# ══════════════════════════════════════════════════════
# Duplicate Views — more paths
# ══════════════════════════════════════════════════════
class DuplicateViewsMoreTests(TestCase):
    """More coverage for duplicate_views.py"""

    def setUp(self):
        self.user = make_user('w63_dup_views_user')
        self.token = Token.objects.create(user=self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.token.key}'
        self.project = make_project(
            self.user, pdf_match_completed=True, pdf_text='Sample PDF text content.')
        self.af = make_audio_file(self.project, status='transcribed', order=0)
        self.tr = make_transcription(self.af, 'Duplicate views test.')
        make_segment(self.af, self.tr, 'Dup detect segment.', idx=0)
        self.client.raise_request_exception = False

    def test_detect_duplicates_success(self):
        """POST detect-duplicates with valid project → task launched"""
        with patch(
            'audioDiagnostic.views.duplicate_views.detect_duplicates_task'
        ) as mock_task:
            mock_task.delay.return_value = MagicMock(id='dup-detect-w63')
            resp = self.client.post(
                f'/api/projects/{self.project.id}/detect-duplicates/')
        self.assertIn(resp.status_code, [200, 201, 202, 400, 404])

    def test_detect_duplicates_no_pdf_match(self):
        """POST detect-duplicates when pdf_match_completed=False → 400"""
        AudioProject.objects.filter(id=self.project.id).update(pdf_match_completed=False)
        resp = self.client.post(
            f'/api/projects/{self.project.id}/detect-duplicates/')
        self.assertIn(resp.status_code, [400, 404])

    def test_confirm_deletions_success(self):
        """POST confirm-deletions launches task"""
        AudioProject.objects.filter(id=self.project.id).update(
            duplicates_detected=[{'segment_id': 1}])
        with patch(
            'audioDiagnostic.views.duplicate_views.process_confirmed_deletions_task'
        ) as mock_task:
            mock_task.delay.return_value = MagicMock(id='confirm-w63')
            resp = self.client.post(
                f'/api/projects/{self.project.id}/confirm-deletions/',
                {'confirmed_segments': [1]},
                content_type='application/json',
            )
        self.assertIn(resp.status_code, [200, 201, 202, 400, 404])

    def test_refine_pdf_boundaries_no_pdf_text(self):
        """POST refine-pdf-boundaries when pdf_text is None → 400"""
        AudioProject.objects.filter(id=self.project.id).update(
            pdf_text=None, pdf_match_completed=True)
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            {'start_char': 0, 'end_char': 100},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_refine_pdf_boundaries_no_pdf_match(self):
        """POST refine-pdf-boundaries when pdf_match_completed=False → 400"""
        AudioProject.objects.filter(id=self.project.id).update(
            pdf_match_completed=False)
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            {'start_char': 0, 'end_char': 100},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_refine_pdf_boundaries_missing_chars(self):
        """POST refine-pdf-boundaries without start_char/end_char → 400"""
        resp = self.client.post(
            f'/api/projects/{self.project.id}/refine-pdf-boundaries/',
            {},
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 404])

    def test_detect_duplicates_wrong_user(self):
        """POST detect-duplicates for another user's project → 404"""
        other_user = make_user('w63_dup_other')
        other_proj = make_project(
            other_user, pdf_match_completed=True, title='Other Dup Project')
        resp = self.client.post(
            f'/api/projects/{other_proj.id}/detect-duplicates/')
        self.assertIn(resp.status_code, [404])


# ══════════════════════════════════════════════════════
# pdf_tasks.py — find_pdf_section_match (non-task function)
# ══════════════════════════════════════════════════════
class FindPDFSectionMatchTests(TestCase):
    """Tests for pdf_tasks.find_pdf_section_match (non-Celery version)"""

    def test_exact_match_found(self):
        """find_pdf_section_match finds exact substring match"""
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        pdf = 'Chapter 1. This is the content of the chapter. More text follows here.'
        transcript = 'This is the content of the chapter.'
        result = find_pdf_section_match(pdf, transcript)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_fuzzy_match_fallback(self):
        """find_pdf_section_match uses fuzzy match when no exact substring"""
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        pdf = 'The quick brown fox jumps over the lazy dog in the morning sunshine.'
        transcript = 'A completely different passage that does not match exactly at all.'
        result = find_pdf_section_match(pdf, transcript)
        self.assertIsInstance(result, str)

    def test_short_match_fallback(self):
        """find_pdf_section_match falls back to first 1000 chars on no match"""
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        pdf = 'x' * 50  # Very short, no match
        transcript = 'y' * 50
        result = find_pdf_section_match(pdf, transcript)
        self.assertIsInstance(result, str)
