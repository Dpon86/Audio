"""
Wave 89 — Coverage boost
Targets:
  - audioDiagnostic/tasks/duplicate_tasks.py helpers:
      identify_all_duplicates, mark_duplicates_for_removal
  - audioDiagnostic/models.py remaining uncovered methods
  - accounts/models.py uncovered methods
"""
from django.test import TestCase
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model

User = get_user_model()


# ─── identify_all_duplicates tests ──────────────────────────────────────────

class IdentifyAllDuplicatesTests(TestCase):

    def _make_segment(self, text, file_order=0, start_time=0.0, end_time=1.0):
        return {
            'text': text,
            'start_time': start_time,
            'end_time': end_time,
            'file_order': file_order,
            'segment': MagicMock(),
            'audio_file': MagicMock(),
        }

    def test_no_duplicates(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        segments = [
            self._make_segment("hello world", file_order=0, start_time=0.0, end_time=1.0),
            self._make_segment("different content here", file_order=0, start_time=1.0, end_time=2.0),
        ]
        result = identify_all_duplicates(segments)
        self.assertEqual(len(result), 0)

    def test_detects_sentence_duplicate(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        segments = [
            self._make_segment("hello world again", file_order=0, start_time=0.0, end_time=1.0),
            self._make_segment("hello world again", file_order=0, start_time=2.0, end_time=3.0),
        ]
        result = identify_all_duplicates(segments)
        self.assertEqual(len(result), 1)

    def test_detects_word_duplicate(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        segments = [
            self._make_segment("hello", file_order=0, start_time=0.0, end_time=0.5),
            self._make_segment("hello", file_order=0, start_time=1.0, end_time=1.5),
        ]
        result = identify_all_duplicates(segments)
        self.assertEqual(len(result), 1)
        key = list(result.keys())[0]
        self.assertEqual(result[key]['content_type'], 'word')

    def test_detects_paragraph_duplicate(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        long_text = "this is a very long paragraph with many many words that spans across multiple sentences"
        segments = [
            self._make_segment(long_text, file_order=0, start_time=0.0, end_time=5.0),
            self._make_segment(long_text, file_order=1, start_time=0.0, end_time=5.0),
        ]
        result = identify_all_duplicates(segments)
        self.assertEqual(len(result), 1)
        key = list(result.keys())[0]
        self.assertEqual(result[key]['content_type'], 'paragraph')

    def test_empty_segments(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        result = identify_all_duplicates([])
        self.assertEqual(len(result), 0)

    def test_empty_text_skipped(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        segments = [
            self._make_segment("", file_order=0),
            self._make_segment("   ", file_order=0),
            self._make_segment("hello world", file_order=0),
        ]
        result = identify_all_duplicates(segments)
        self.assertEqual(len(result), 0)

    def test_case_insensitive_comparison(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        segments = [
            self._make_segment("Hello World Again", file_order=0, start_time=0.0, end_time=1.0),
            self._make_segment("hello world again", file_order=0, start_time=2.0, end_time=3.0),
        ]
        result = identify_all_duplicates(segments)
        self.assertEqual(len(result), 1)


# ─── mark_duplicates_for_removal tests ──────────────────────────────────────

class MarkDuplicatesForRemovalTests(TestCase):

    def _make_group(self, occurrences_list):
        """
        occurrences_list: list of (file_order, start_time, text) tuples
        """
        occurrences = []
        for file_order, start_time, text in occurrences_list:
            mock_segment = MagicMock()
            mock_segment.text = text
            mock_segment.start_time = start_time
            mock_segment.end_time = start_time + 1.0
            mock_segment.save = MagicMock()
            occurrences.append({
                'segment_data': {
                    'file_order': file_order,
                    'start_time': start_time,
                    'segment': mock_segment,
                    'audio_file': MagicMock(title='file1'),
                },
                'content_type': 'sentence',
            })
        return occurrences

    def test_removes_earlier_occurrences(self):
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        mock_seg1 = MagicMock()
        mock_seg1.text = "hello world"
        mock_seg1.start_time = 0.0
        mock_seg1.end_time = 1.0
        mock_seg1.save = MagicMock()
        mock_seg2 = MagicMock()
        mock_seg2.text = "hello world"
        mock_seg2.start_time = 2.0
        mock_seg2.end_time = 3.0
        mock_seg2.save = MagicMock()

        duplicates_found = {
            'dup_1': {
                'normalized_text': 'hello world',
                'content_type': 'sentence',
                'count': 2,
                'occurrences': [
                    {
                        'segment_data': {
                            'file_order': 0, 'start_time': 0.0,
                            'segment': mock_seg1,
                            'audio_file': MagicMock(title='file1'),
                        },
                        'content_type': 'sentence',
                    },
                    {
                        'segment_data': {
                            'file_order': 0, 'start_time': 2.0,
                            'segment': mock_seg2,
                            'audio_file': MagicMock(title='file1'),
                        },
                        'content_type': 'sentence',
                    },
                ],
            }
        }
        result = mark_duplicates_for_removal(duplicates_found)
        self.assertEqual(len(result), 1)
        # First occurrence removed
        self.assertTrue(mock_seg1.is_duplicate)
        self.assertFalse(mock_seg1.is_kept)
        # Last occurrence kept
        self.assertTrue(mock_seg2.is_duplicate)
        self.assertTrue(mock_seg2.is_kept)

    def test_empty_duplicates(self):
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        result = mark_duplicates_for_removal({})
        self.assertEqual(result, [])


# ─── AudioProject model tests ────────────────────────────────────────────────

class AudioProjectModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='proj_user', password='pass123')

    def test_str_representation(self):
        from audioDiagnostic.models import AudioProject
        project = AudioProject.objects.create(user=self.user, title='Test Project')
        s = str(project)
        self.assertIn('Test Project', s)

    def test_default_status(self):
        from audioDiagnostic.models import AudioProject
        project = AudioProject.objects.create(user=self.user, title='Status Test')
        self.assertIsNotNone(project.status)

    def test_boolean_defaults(self):
        from audioDiagnostic.models import AudioProject
        project = AudioProject.objects.create(user=self.user, title='Bool Test')
        self.assertFalse(project.pdf_match_completed)
        self.assertFalse(project.duplicates_detected)
        self.assertFalse(project.duplicates_detection_completed)


# ─── AudioFile model tests ───────────────────────────────────────────────────

class AudioFileModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='af_user', password='pass123')
        from audioDiagnostic.models import AudioProject
        self.project = AudioProject.objects.create(user=self.user, title='AF Project')

    def test_str_representation(self):
        from audioDiagnostic.models import AudioFile
        af = AudioFile.objects.create(
            project=self.project, filename='test.mp3', order_index=0
        )
        s = str(af)
        self.assertIsInstance(s, str)

    def test_default_status(self):
        from audioDiagnostic.models import AudioFile
        af = AudioFile.objects.create(
            project=self.project, filename='test2.mp3', order_index=1
        )
        self.assertIsNotNone(af.status)


# ─── TranscriptionSegment model tests ───────────────────────────────────────

class TranscriptionSegmentModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='seg_user', password='pass123')
        from audioDiagnostic.models import AudioProject, AudioFile
        self.project = AudioProject.objects.create(user=self.user, title='Seg Project')
        self.audio_file = AudioFile.objects.create(
            project=self.project, filename='seg.mp3', order_index=0
        )

    def test_create_segment(self):
        from audioDiagnostic.models import TranscriptionSegment
        seg = TranscriptionSegment.objects.create(
            audio_file=self.audio_file,
            text='Hello world',
            start_time=0.0,
            end_time=1.0,
            segment_index=0,
        )
        self.assertEqual(seg.text, 'Hello world')
        self.assertFalse(seg.is_duplicate)

    def test_str_representation(self):
        from audioDiagnostic.models import TranscriptionSegment
        seg = TranscriptionSegment.objects.create(
            audio_file=self.audio_file,
            text='Test segment text',
            start_time=0.0,
            end_time=1.0,
            segment_index=0,
        )
        s = str(seg)
        self.assertIsInstance(s, str)


# ─── DuplicateGroup model tests ──────────────────────────────────────────────

class DuplicateGroupModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='dg_user', password='pass123')
        from audioDiagnostic.models import AudioProject, AudioFile
        self.project = AudioProject.objects.create(user=self.user, title='DG Project')
        self.audio_file = AudioFile.objects.create(
            project=self.project, filename='dg.mp3', order_index=0
        )

    def test_create_and_str(self):
        from audioDiagnostic.models import DuplicateGroup
        dg = DuplicateGroup.objects.create(
            audio_file=self.audio_file,
            group_id='grp_1',
            duplicate_text='repeated text here',
            occurrence_count=2,
            total_duration_seconds=5.0,
        )
        s = str(dg)
        self.assertIsInstance(s, str)
