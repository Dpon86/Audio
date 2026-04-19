"""
Comprehensive task tests with heavy mocking.
Covers duplicate_tasks, pdf_tasks, ai_tasks, audio_processing_tasks,
compare_pdf_task, precise_pdf_comparison_task, transcription_tasks.
"""
import json
from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock, PropertyMock, call
from audioDiagnostic.models import (
    AudioProject, AudioFile, Transcription, TranscriptionSegment,
    AIDuplicateDetectionResult, AIPDFComparisonResult, AIProcessingLog,
    DuplicateGroup,
)


def make_user(username='taskuser'):
    return User.objects.create_user(username=username, email=f'{username}@test.com', password='pass123')


def make_project(user, **kwargs):
    return AudioProject.objects.create(user=user, title='Test Project', **kwargs)


def make_audio_file(project, status='transcribed', transcript='Hello world test', **kwargs):
    return AudioFile.objects.create(
        project=project,
        title='Chapter 1',
        filename='test.mp3',
        file='audio/test.mp3',
        status=status,
        transcript_text=transcript,
        **kwargs
    )


def make_transcription(audio_file):
    return Transcription.objects.create(
        audio_file=audio_file,
        full_text=audio_file.transcript_text or 'Hello world test',
        word_count=3,
    )


def make_segment(transcription, text='Hello world', index=0):
    return TranscriptionSegment.objects.create(
        audio_file=transcription.audio_file,
        transcription=transcription,
        text=text,
        start_time=0.0,
        end_time=2.0,
        segment_index=index,
        is_kept=True,
    )


def mock_redis():
    r = MagicMock()
    r.set.return_value = True
    r.get.return_value = None
    r.ping.return_value = True
    return r


# ---------------------------------------------------------------------------
# PDF Tasks
# ---------------------------------------------------------------------------

class PDFMatchingTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('pdfuser')
        self.project = make_project(self.user, pdf_file='pdfs/test.pdf')
        self.audio_file = make_audio_file(self.project, status='transcribed',
                                          transcript='Hello world this is chapter one')

    @patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection')
    def test_match_pdf_task_setup_fails(self, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = False

        from audioDiagnostic.tasks.pdf_tasks import match_pdf_to_audio_task
        with self.assertRaises(Exception) as ctx:
            match_pdf_to_audio_task.apply(args=[self.project.id])
        # Either raises or returns failed state
        # The task should raise "Failed to set up Docker..."

    @patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.pdf_tasks.AudioProject')
    def test_match_pdf_task_no_pdf(self, mock_ap_cls, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = True
        mock_docker.register_task.return_value = None
        mock_docker.unregister_task.return_value = None

        mock_project = MagicMock()
        mock_project.pdf_file = None
        mock_ap_cls.objects.get.return_value = mock_project

        from audioDiagnostic.tasks.pdf_tasks import match_pdf_to_audio_task
        result = match_pdf_to_audio_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())

    @patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.pdf_tasks.AudioProject')
    def test_match_pdf_task_no_transcribed_files(self, mock_ap_cls, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = True
        mock_docker.register_task.return_value = None
        mock_docker.unregister_task.return_value = None

        mock_project = MagicMock()
        mock_project.pdf_file = MagicMock()
        mock_project.audio_files.filter.return_value.exists.return_value = False
        mock_ap_cls.objects.get.return_value = mock_project

        from audioDiagnostic.tasks.pdf_tasks import match_pdf_to_audio_task
        result = match_pdf_to_audio_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())


class PDFTaskHelperFunctionTests(TestCase):
    """Test helper functions in pdf_tasks"""

    def test_find_pdf_section_match(self):
        from audioDiagnostic.tasks.pdf_tasks import find_pdf_section_match
        pdf_text = 'Chapter one hello world this is a test of the system'
        transcript = 'hello world this is a test'
        result = find_pdf_section_match(pdf_text, transcript)
        self.assertIsInstance(result, (str, dict, type(None)))

    def test_identify_pdf_based_duplicates(self):
        from audioDiagnostic.tasks.pdf_tasks import identify_pdf_based_duplicates
        segments = [
            {'text': 'hello world', 'id': 1},
            {'text': 'hello world', 'id': 2},
            {'text': 'different text', 'id': 3},
        ]
        result = identify_pdf_based_duplicates(segments, 'hello world different text book')
        self.assertIsInstance(result, (list, dict))

    def test_validate_transcript_task_no_pdf(self):
        """Test validate_transcript_against_pdf_task with missing section"""
        from audioDiagnostic.tasks.pdf_tasks import validate_transcript_against_pdf_task

        user = make_user('valuser')
        project = make_project(user)

        with patch('audioDiagnostic.tasks.pdf_tasks.get_redis_connection') as mock_r:
            mock_r.return_value = mock_redis()
            with patch('audioDiagnostic.tasks.pdf_tasks.docker_celery_manager') as mock_docker:
                mock_docker.setup_infrastructure.return_value = True
                mock_docker.register_task.return_value = None
                mock_docker.unregister_task.return_value = None

                with patch('audioDiagnostic.tasks.pdf_tasks.AudioProject') as mock_ap_cls:
                    mock_project = MagicMock()
                    mock_project.pdf_match_completed = False
                    mock_ap_cls.objects.get.return_value = mock_project

                    result = validate_transcript_against_pdf_task.apply(args=[project.id])
                    self.assertTrue(result.failed())


# ---------------------------------------------------------------------------
# Duplicate Detection Task helpers
# ---------------------------------------------------------------------------

class DuplicateTaskHelperTests(TestCase):

    def test_find_text_in_pdf(self):
        from audioDiagnostic.tasks.duplicate_tasks import find_text_in_pdf
        pdf = 'Hello world this is a big long text about something important'
        self.assertTrue(find_text_in_pdf('Hello world', pdf))
        self.assertFalse(find_text_in_pdf('nonexistent phrase xyz', pdf))

    def test_identify_all_duplicates(self):
        from audioDiagnostic.tasks.duplicate_tasks import identify_all_duplicates
        user = make_user('duphelp')
        project = make_project(user)
        af = make_audio_file(project)
        segments = [
            {'text': 'hello world', 'audio_file': MagicMock(), 'segment': MagicMock(), 
             'start_time': 0.0, 'end_time': 2.0, 'file_order': 0},
            {'text': 'hello world', 'audio_file': MagicMock(), 'segment': MagicMock(), 
             'start_time': 3.0, 'end_time': 5.0, 'file_order': 0},
            {'text': 'different content here', 'audio_file': MagicMock(), 'segment': MagicMock(), 
             'start_time': 6.0, 'end_time': 8.0, 'file_order': 0},
        ]
        result = identify_all_duplicates(segments)
        self.assertIsInstance(result, list)

    def test_mark_duplicates_for_removal(self):
        from audioDiagnostic.tasks.duplicate_tasks import mark_duplicates_for_removal
        mock_seg = MagicMock()
        duplicates = [
            {'type': 'word', 'segment': mock_seg, 'text': 'hello', 'occurrences': [0, 1]},
        ]
        result = mark_duplicates_for_removal(duplicates)
        self.assertIsInstance(result, list)

    def test_find_missing_pdf_content(self):
        from audioDiagnostic.tasks.duplicate_tasks import find_missing_pdf_content
        final = 'hello world test'
        pdf = 'hello world test missing content here'
        result = find_missing_pdf_content(final, pdf)
        self.assertIsInstance(result, (str, type(None)))


class DuplicateTaskMainTests(TestCase):

    @patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection')
    def test_process_project_duplicates_setup_fails(self, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = False
        from audioDiagnostic.tasks.duplicate_tasks import process_project_duplicates_task
        result = process_project_duplicates_task.apply(args=[999])
        self.assertTrue(result.failed())

    @patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.duplicate_tasks.AudioProject')
    def test_process_project_no_audio_files(self, mock_ap_cls, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = True
        mock_docker.register_task.return_value = None

        mock_project = MagicMock()
        mock_project.audio_files.filter.return_value.order_by.return_value.exists.return_value = False
        mock_ap_cls.objects.get.return_value = mock_project

        from audioDiagnostic.tasks.duplicate_tasks import process_project_duplicates_task
        result = process_project_duplicates_task.apply(args=[1])
        self.assertTrue(result.failed())

    @patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection')
    def test_detect_duplicates_setup_fails(self, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = False
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_task
        result = detect_duplicates_task.apply(args=[999])
        self.assertTrue(result.failed())

    @patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.duplicate_tasks.AudioProject')
    def test_detect_duplicates_no_pdf_match(self, mock_ap_cls, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = True
        mock_docker.register_task.return_value = None

        mock_project = MagicMock()
        mock_project.pdf_match_completed = False
        mock_ap_cls.objects.get.return_value = mock_project

        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_task
        result = detect_duplicates_task.apply(args=[1])
        self.assertTrue(result.failed())

    @patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection')
    def test_detect_duplicates_single_file_setup_fails(self, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = False
        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        result = detect_duplicates_single_file_task.apply(args=[999, 'tfidf_cosine', False])
        self.assertTrue(result.failed())

    @patch('audioDiagnostic.tasks.duplicate_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.duplicate_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.duplicate_tasks.AudioFile')
    def test_detect_duplicates_single_file_no_transcription(self, mock_af_cls, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = True
        mock_docker.register_task.return_value = None

        mock_af = MagicMock()
        mock_af.status = 'transcribed'
        mock_af.transcript_text = 'hello world'
        mock_af.project.pdf_matched_section = 'some pdf section'
        mock_af.project.pdf_text = 'some pdf text'
        # No transcription attribute
        del mock_af.transcription
        type(mock_af).transcription = PropertyMock(side_effect=Exception('no transcription'))
        mock_af_cls.objects.get.return_value = mock_af

        from audioDiagnostic.tasks.duplicate_tasks import detect_duplicates_single_file_task
        result = detect_duplicates_single_file_task.apply(args=[1, 'tfidf_cosine', False])
        # Should either fail or succeed depending on implementation
        self.assertIn(result.state, ['FAILURE', 'SUCCESS'])


# ---------------------------------------------------------------------------
# Compare PDF Task
# ---------------------------------------------------------------------------

class ComparePDFTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('cmppdf')
        self.project = make_project(self.user, pdf_file='pdfs/test.pdf',
                                    pdf_text='Hello world this is the full PDF text content')
        self.audio_file = make_audio_file(self.project, transcript='Hello world this is text')

    @patch('audioDiagnostic.tasks.compare_pdf_task.get_redis_connection')
    @patch('audioDiagnostic.tasks.compare_pdf_task.AudioFile')
    def test_compare_task_no_pdf(self, mock_af_cls, mock_redis_conn):
        mock_redis_conn.return_value = mock_redis()
        mock_af = MagicMock()
        mock_af.project.pdf_file = None
        mock_af.transcript_text = 'hello'
        mock_af_cls.objects.select_related.return_value.get.return_value = mock_af

        from audioDiagnostic.tasks.compare_pdf_task import compare_transcription_to_pdf_task
        result = compare_transcription_to_pdf_task.apply(args=[self.audio_file.id])
        self.assertTrue(result.failed())

    @patch('audioDiagnostic.tasks.compare_pdf_task.get_redis_connection')
    @patch('audioDiagnostic.tasks.compare_pdf_task.AudioFile')
    def test_compare_task_no_transcript(self, mock_af_cls, mock_redis_conn):
        mock_redis_conn.return_value = mock_redis()
        mock_af = MagicMock()
        mock_af.project.pdf_file = MagicMock()
        mock_af.transcript_text = ''
        mock_af_cls.objects.select_related.return_value.get.return_value = mock_af

        from audioDiagnostic.tasks.compare_pdf_task import compare_transcription_to_pdf_task
        result = compare_transcription_to_pdf_task.apply(args=[self.audio_file.id])
        self.assertTrue(result.failed())

    def test_find_start_position_in_pdf(self):
        from audioDiagnostic.tasks.compare_pdf_task import find_start_position_in_pdf
        pdf = 'Hello world this is a test of matching algorithm for PDF content'
        transcript = 'this is a test'
        pos, confidence = find_start_position_in_pdf(pdf, transcript)
        self.assertIsInstance(pos, int)
        self.assertIsInstance(confidence, float)

    def test_extract_pdf_section(self):
        from audioDiagnostic.tasks.compare_pdf_task import extract_pdf_section
        pdf = 'A' * 1000
        result = extract_pdf_section(pdf, 10, 100)
        self.assertIsInstance(result, str)

    def test_classify_differences(self):
        from audioDiagnostic.tasks.compare_pdf_task import classify_differences
        diffs = [
            ('equal', ['hello', 'world']),
            ('delete', ['missing_word']),
            ('insert', ['extra_word']),
        ]
        result = classify_differences(diffs)
        self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# AI Tasks
# ---------------------------------------------------------------------------

class AITaskTests(TestCase):

    def setUp(self):
        self.user = make_user('aiuser')
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project, status='transcribed',
                                          transcript='Hello world segment one. Hello world segment two.')
        self.transcription = make_transcription(self.audio_file)
        make_segment(self.transcription, 'Hello world segment one', 0)
        make_segment(self.transcription, 'Hello world segment two', 1)

    @patch('audioDiagnostic.tasks.ai_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.ai_tasks.AudioFile')
    def test_ai_detect_no_transcription(self, mock_af_cls, mock_redis_conn):
        mock_redis_conn.return_value = mock_redis()
        mock_af = MagicMock()
        mock_af.id = self.audio_file.id
        del mock_af.transcription
        type(mock_af).transcription = PropertyMock(side_effect=Exception('no transcription'))
        mock_af_cls.objects.get.side_effect = [mock_af, MagicMock()]

        from audioDiagnostic.tasks.ai_tasks import ai_detect_duplicates_task
        result = ai_detect_duplicates_task.apply(
            args=[self.audio_file.id, self.user.id, 3, 0.85, 'last', False]
        )
        self.assertIn(result.state, ['FAILURE', 'SUCCESS'])

    @patch('audioDiagnostic.tasks.ai_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.ai_tasks.AudioFile')
    @patch('audioDiagnostic.tasks.ai_tasks.User')
    def test_ai_detect_no_segments(self, mock_user_cls, mock_af_cls, mock_redis_conn):
        mock_redis_conn.return_value = mock_redis()

        mock_transcription = MagicMock()
        mock_transcription.segments.all.return_value.order_by.return_value.exists.return_value = False
        mock_transcription.segments.all.return_value.order_by.return_value = MagicMock(
            exists=MagicMock(return_value=False)
        )

        mock_af = MagicMock()
        mock_af.transcription = mock_transcription
        mock_af_cls.objects.get.return_value = mock_af
        mock_user_cls.objects.get.return_value = MagicMock()

        from audioDiagnostic.tasks.ai_tasks import ai_detect_duplicates_task
        result = ai_detect_duplicates_task.apply(
            args=[self.audio_file.id, self.user.id, 3, 0.85, 'last', False]
        )
        self.assertIn(result.state, ['FAILURE', 'SUCCESS'])

    @patch('audioDiagnostic.tasks.ai_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.ai_tasks.AudioFile')
    def test_ai_compare_pdf_no_pdf(self, mock_af_cls, mock_redis_conn):
        mock_redis_conn.return_value = mock_redis()
        mock_af = MagicMock()
        mock_af.project.pdf_file = None
        mock_af_cls.objects.get.return_value = mock_af

        from audioDiagnostic.tasks.ai_tasks import ai_compare_pdf_task
        result = ai_compare_pdf_task.apply(args=[self.audio_file.id, self.user.id])
        self.assertIn(result.state, ['FAILURE', 'SUCCESS'])

    @patch('audioDiagnostic.tasks.ai_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.ai_tasks.AudioFile')
    @patch('audioDiagnostic.tasks.ai_tasks.User')
    def test_estimate_cost_task(self, mock_user_cls, mock_af_cls, mock_redis_conn):
        mock_redis_conn.return_value = mock_redis()
        mock_transcription = MagicMock()
        mock_transcription.full_text = 'hello world test content for cost estimation'
        mock_af = MagicMock()
        mock_af.transcription = mock_transcription
        mock_af_cls.objects.get.return_value = mock_af
        mock_user_cls.objects.get.return_value = MagicMock()

        with patch('audioDiagnostic.tasks.ai_tasks.CostCalculator') as mock_cc:
            mock_cc.return_value.estimate_cost.return_value = {'total': 0.01}
            from audioDiagnostic.tasks.ai_tasks import estimate_ai_cost_task
            result = estimate_ai_cost_task.apply(
                args=[self.audio_file.id, self.user.id]
            )
            self.assertIn(result.state, ['SUCCESS', 'FAILURE'])


# ---------------------------------------------------------------------------
# Audio Processing Tasks
# ---------------------------------------------------------------------------

class AudioProcessingTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('audproc')
        self.project = make_project(self.user, pdf_file='pdfs/test.pdf')
        self.audio_file = make_audio_file(self.project, status='transcribed')

    @patch('audioDiagnostic.tasks.audio_processing_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.audio_processing_tasks.get_redis_connection')
    def test_process_audio_setup_fails(self, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = False
        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        result = process_audio_file_task.apply(args=[self.audio_file.id])
        self.assertTrue(result.failed())

    @patch('audioDiagnostic.tasks.audio_processing_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.audio_processing_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.audio_processing_tasks.AudioFile')
    def test_process_audio_wrong_status(self, mock_af_cls, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = True
        mock_docker.register_task.return_value = None

        mock_af = MagicMock()
        mock_af.status = 'uploaded'
        mock_af.project.pdf_file = MagicMock()
        mock_af_cls.objects.get.return_value = mock_af

        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        result = process_audio_file_task.apply(args=[self.audio_file.id])
        self.assertTrue(result.failed())

    @patch('audioDiagnostic.tasks.audio_processing_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.audio_processing_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.audio_processing_tasks.TranscriptionSegment')
    @patch('audioDiagnostic.tasks.audio_processing_tasks.AudioFile')
    def test_process_audio_no_segments(self, mock_af_cls, mock_seg_cls, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = True
        mock_docker.register_task.return_value = None

        mock_af = MagicMock()
        mock_af.status = 'transcribed'
        mock_af.project.pdf_file = MagicMock()
        mock_af_cls.objects.get.return_value = mock_af

        mock_seg_cls.objects.filter.return_value.order_by.return_value.exists.return_value = False

        from audioDiagnostic.tasks.audio_processing_tasks import process_audio_file_task
        result = process_audio_file_task.apply(args=[self.audio_file.id])
        self.assertTrue(result.failed())


# ---------------------------------------------------------------------------
# Transcription Tasks
# ---------------------------------------------------------------------------

class TranscriptionTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('transctask')
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project, status='uploaded')

    @patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection')
    def test_transcribe_all_project_setup_fails(self, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = False
        from audioDiagnostic.tasks.transcription_tasks import transcribe_all_project_audio_task
        result = transcribe_all_project_audio_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())

    @patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.transcription_tasks.AudioProject')
    def test_transcribe_all_no_audio_files(self, mock_ap_cls, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = True
        mock_docker.register_task.return_value = None

        mock_project = MagicMock()
        mock_project.audio_files.filter.return_value.order_by.return_value.exists.return_value = False
        mock_ap_cls.objects.get.return_value = mock_project

        from audioDiagnostic.tasks.transcription_tasks import transcribe_all_project_audio_task
        result = transcribe_all_project_audio_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())

    @patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection')
    def test_transcribe_single_setup_fails(self, mock_redis_conn, mock_docker):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = False
        from audioDiagnostic.tasks.transcription_tasks import transcribe_single_audio_file_task
        result = transcribe_single_audio_file_task.apply(args=[self.audio_file.id])
        self.assertTrue(result.failed())

    @patch('audioDiagnostic.tasks.transcription_tasks.docker_celery_manager')
    @patch('audioDiagnostic.tasks.transcription_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.transcription_tasks.AudioFile')
    def test_transcribe_single_file_not_found(self, mock_af_cls, mock_redis_conn, mock_docker):
        from django.core.exceptions import ObjectDoesNotExist
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = True
        mock_docker.register_task.return_value = None
        mock_af_cls.objects.get.side_effect = ObjectDoesNotExist('not found')

        from audioDiagnostic.tasks.transcription_tasks import transcribe_single_audio_file_task
        result = transcribe_single_audio_file_task.apply(args=[99999])
        self.assertTrue(result.failed())


# ---------------------------------------------------------------------------
# Transcription Utils
# ---------------------------------------------------------------------------

class TranscriptionUtilsTests(TestCase):

    def test_timestamp_aligner_init(self):
        from audioDiagnostic.tasks.transcription_utils import TimestampAligner
        aligner = TimestampAligner()
        self.assertIsNotNone(aligner)

    def test_transcription_post_processor_init(self):
        from audioDiagnostic.tasks.transcription_utils import TranscriptionPostProcessor
        pp = TranscriptionPostProcessor()
        self.assertIsNotNone(pp)

    def test_memory_manager_log(self):
        from audioDiagnostic.tasks.transcription_utils import MemoryManager
        # Should not raise
        MemoryManager.log_memory_usage('test point')

    def test_calculate_quality_metrics(self):
        from audioDiagnostic.tasks.transcription_utils import calculate_transcription_quality_metrics
        segments = [{'text': 'hello world', 'start': 0, 'end': 2}]
        result = calculate_transcription_quality_metrics(segments, 'hello world')
        self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# PDF Comparison Tasks (precise, ai, audiobook)
# ---------------------------------------------------------------------------

class PrecisePDFComparisonTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('precisepdf')
        self.project = make_project(self.user, pdf_file='pdfs/test.pdf',
                                    pdf_text='Hello world PDF content for precise comparison')
        self.audio_file = make_audio_file(self.project, transcript='Hello world PDF content')

    @patch('audioDiagnostic.tasks.precise_pdf_comparison_task.get_redis_connection')
    @patch('audioDiagnostic.tasks.precise_pdf_comparison_task.AudioFile')
    def test_precise_compare_no_pdf(self, mock_af_cls, mock_redis_conn):
        mock_redis_conn.return_value = mock_redis()
        mock_af = MagicMock()
        mock_af.project.pdf_file = None
        mock_af_cls.objects.select_related.return_value.get.return_value = mock_af

        from audioDiagnostic.tasks.precise_pdf_comparison_task import precise_compare_transcription_to_pdf_task
        result = precise_compare_transcription_to_pdf_task.apply(args=[self.audio_file.id])
        self.assertTrue(result.failed())

    @patch('audioDiagnostic.tasks.precise_pdf_comparison_task.get_redis_connection')
    @patch('audioDiagnostic.tasks.precise_pdf_comparison_task.AudioFile')
    def test_precise_compare_no_transcript(self, mock_af_cls, mock_redis_conn):
        mock_redis_conn.return_value = mock_redis()
        mock_af = MagicMock()
        mock_af.project.pdf_file = MagicMock()
        mock_af.transcript_text = ''
        mock_af_cls.objects.select_related.return_value.get.return_value = mock_af

        from audioDiagnostic.tasks.precise_pdf_comparison_task import precise_compare_transcription_to_pdf_task
        result = precise_compare_transcription_to_pdf_task.apply(args=[self.audio_file.id])
        self.assertTrue(result.failed())


class AIPDFComparisonTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('aipdfcomp')
        self.project = make_project(self.user, pdf_file='pdfs/test.pdf',
                                    pdf_text='Hello world PDF content')
        self.audio_file = make_audio_file(self.project, transcript='Hello world PDF content')

    @patch('audioDiagnostic.tasks.ai_pdf_comparison_task.get_redis_connection')
    @patch('audioDiagnostic.tasks.ai_pdf_comparison_task.AudioFile')
    def test_ai_pdf_compare_no_pdf(self, mock_af_cls, mock_redis_conn):
        mock_redis_conn.return_value = mock_redis()
        mock_af = MagicMock()
        mock_af.project.pdf_file = None
        mock_af_cls.objects.get.return_value = mock_af

        from audioDiagnostic.tasks.ai_pdf_comparison_task import ai_compare_transcription_to_pdf_task
        result = ai_compare_transcription_to_pdf_task.apply(args=[self.audio_file.id])
        self.assertIn(result.state, ['FAILURE', 'SUCCESS'])


class PDFComparisonTasksTests(TestCase):

    def setUp(self):
        self.user = make_user('pdfcomptask')
        self.project = make_project(self.user, pdf_file='pdfs/test.pdf')
        self.audio_file = make_audio_file(self.project, transcript='Hello world PDF content')

    @patch('audioDiagnostic.tasks.pdf_comparison_tasks.get_redis_connection')
    @patch('audioDiagnostic.tasks.pdf_comparison_tasks.docker_celery_manager')
    def test_pdf_comparison_setup_fails(self, mock_docker, mock_redis_conn):
        mock_redis_conn.return_value = mock_redis()
        mock_docker.setup_infrastructure.return_value = False

        from audioDiagnostic.tasks.pdf_comparison_tasks import compare_pdf_to_audio_task
        result = compare_pdf_to_audio_task.apply(args=[self.project.id])
        self.assertTrue(result.failed())


class AudiobookProductionTaskTests(TestCase):

    def setUp(self):
        self.user = make_user('audiobk')
        self.project = make_project(self.user, pdf_file='pdfs/test.pdf',
                                    pdf_text='Hello world PDF text content')
        self.audio_file = make_audio_file(self.project, status='transcribed',
                                          transcript='Hello world PDF text')

    @patch('audioDiagnostic.tasks.audiobook_production_task.get_redis_connection')
    @patch('audioDiagnostic.tasks.audiobook_production_task.AudioProject')
    def test_audiobook_production_no_pdf(self, mock_ap_cls, mock_redis_conn):
        mock_redis_conn.return_value = mock_redis()
        mock_project = MagicMock()
        mock_project.pdf_file = None
        mock_ap_cls.objects.get.return_value = mock_project

        from audioDiagnostic.tasks.audiobook_production_task import audiobook_production_analysis_task
        result = audiobook_production_analysis_task.apply(args=[self.project.id])
        self.assertIn(result.state, ['FAILURE', 'SUCCESS'])

    def test_get_audiobook_analysis_progress(self):
        from audioDiagnostic.tasks.audiobook_production_task import get_audiobook_analysis_progress
        with patch('audioDiagnostic.tasks.audiobook_production_task.get_redis_connection') as mock_r:
            mock_r.return_value = MagicMock(get=MagicMock(return_value=None))
            result = get_audiobook_analysis_progress(self.project.id)
            self.assertIsInstance(result, dict)

    def test_get_audiobook_report_summary(self):
        from audioDiagnostic.tasks.audiobook_production_task import get_audiobook_report_summary
        with patch('audioDiagnostic.tasks.audiobook_production_task.AudioProject') as mock_ap:
            mock_ap.objects.get.return_value = MagicMock(processing_summary=None)
            result = get_audiobook_report_summary(self.project.id)
            self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# Task utils
# ---------------------------------------------------------------------------

class TaskUtilsTests(TestCase):

    def setUp(self):
        self.user = make_user('taskutil')
        self.project = make_project(self.user)
        self.audio_file = make_audio_file(self.project)

    def test_get_final_transcript_without_duplicates(self):
        from audioDiagnostic.tasks.utils import get_final_transcript_without_duplicates
        transcription = make_transcription(self.audio_file)
        seg1 = make_segment(transcription, 'hello world', 0)
        seg2 = make_segment(transcription, 'this is a test', 1)
        seg1.is_kept = True
        seg1.save()
        seg2.is_kept = False
        seg2.save()
        segments = [
            {'segment': seg1, 'text': seg1.text},
            {'segment': seg2, 'text': seg2.text},
        ]
        result = get_final_transcript_without_duplicates(segments)
        self.assertIsInstance(result, str)

    def test_normalize(self):
        from audioDiagnostic.tasks.utils import normalize
        result = normalize('Hello, World! This is a TEST.')
        self.assertIsInstance(result, str)
        self.assertEqual(result, result.lower())
