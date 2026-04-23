"""
Wave 156: Target 19 specific missed statements across 4 files
- docker_status.py (3 miss): management command handle
- start_docker.py (1 miss): else branch when setup fails
- services/ai/duplicate_detector.py (6 miss): except branches in all 3 methods
- accounts/models_feedback.py (9 miss): FeatureFeedbackSummary.update_summary
"""
from io import StringIO
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.management import call_command


# ---------------------------------------------------------------------------
# docker_status.py  (3 miss)
# ---------------------------------------------------------------------------

class DockerStatusCommandTests(TestCase):
    """Test the docker_status management command handle method"""

    def test_handle_infrastructure_running(self):
        """Cover handle() with is_setup=True"""
        with patch('audioDiagnostic.management.commands.docker_status.docker_celery_manager') as mock_mgr:
            mock_mgr.get_status.return_value = {
                'is_setup': True,
                'workers': 2,
                'redis': True,
            }
            out = StringIO()
            call_command('docker_status', stdout=out)
            output = out.getvalue()
            self.assertIn('True', output)

    def test_handle_infrastructure_not_running(self):
        """Cover handle() with is_setup=False"""
        with patch('audioDiagnostic.management.commands.docker_status.docker_celery_manager') as mock_mgr:
            mock_mgr.get_status.return_value = {
                'is_setup': False,
                'workers': 0,
                'redis': False,
            }
            out = StringIO()
            call_command('docker_status', stdout=out)
            output = out.getvalue()
            self.assertIn('False', output)

    def test_handle_get_status_called(self):
        """Verify get_status is actually called"""
        with patch('audioDiagnostic.management.commands.docker_status.docker_celery_manager') as mock_mgr:
            mock_mgr.get_status.return_value = {'is_setup': True}
            out = StringIO()
            call_command('docker_status', stdout=out)
            mock_mgr.get_status.assert_called_once()


# ---------------------------------------------------------------------------
# start_docker.py  (1 miss: else branch)
# ---------------------------------------------------------------------------

class StartDockerCommandTests(TestCase):
    """Test the start_docker management command"""

    def test_handle_setup_success(self):
        """Cover the success branch"""
        with patch('audioDiagnostic.management.commands.start_docker.docker_celery_manager') as mock_mgr:
            mock_mgr.setup_infrastructure.return_value = True
            out = StringIO()
            call_command('start_docker', stdout=out)
            output = out.getvalue()
            self.assertIn('Starting Docker', output)

    def test_handle_setup_failure(self):
        """Cover the else branch when setup fails (1 miss stmt)"""
        with patch('audioDiagnostic.management.commands.start_docker.docker_celery_manager') as mock_mgr:
            mock_mgr.setup_infrastructure.return_value = False
            out = StringIO()
            call_command('start_docker', stdout=out)
            output = out.getvalue()
            self.assertIn('Starting Docker', output)


# ---------------------------------------------------------------------------
# services/ai/duplicate_detector.py  (6 miss: 2 lines per except branch x 3 methods)
# ---------------------------------------------------------------------------

class DuplicateDetectorExceptTests(TestCase):
    """Test except branches in all three DuplicateDetector methods"""

    def setUp(self):
        patcher_client = patch('audioDiagnostic.services.ai.duplicate_detector.AnthropicClient')
        patcher_prompts = patch('audioDiagnostic.services.ai.duplicate_detector.PromptTemplates')
        self.MockClient = patcher_client.start()
        self.MockPrompts = patcher_prompts.start()
        self.addCleanup(patcher_client.stop)
        self.addCleanup(patcher_prompts.stop)

        from audioDiagnostic.services.ai.duplicate_detector import DuplicateDetector
        self.detector = DuplicateDetector()
        # Set call_api to raise an exception so we hit the except blocks
        self.detector.client.call_api.side_effect = Exception("Simulated API failure")

    def test_detect_sentence_level_duplicates_exception(self):
        """Cover except block in detect_sentence_level_duplicates (logger.error + raise)"""
        with self.assertRaises(Exception) as ctx:
            self.detector.detect_sentence_level_duplicates({'segments': []})
        self.assertIn('Simulated API failure', str(ctx.exception))

    def test_expand_to_paragraph_level_exception(self):
        """Cover except block in expand_to_paragraph_level (logger.error + raise)"""
        with self.assertRaises(Exception) as ctx:
            self.detector.expand_to_paragraph_level([], [])
        self.assertIn('Simulated API failure', str(ctx.exception))

    def test_compare_with_pdf_exception(self):
        """Cover except block in compare_with_pdf (logger.error + raise)"""
        with self.assertRaises(Exception) as ctx:
            self.detector.compare_with_pdf('transcript text', 'pdf text', {'pages': 1})
        self.assertIn('Simulated API failure', str(ctx.exception))


# ---------------------------------------------------------------------------
# accounts/models_feedback.py  (9 miss: FeatureFeedbackSummary.update_summary)
# ---------------------------------------------------------------------------

class FeatureFeedbackSummaryTests(TestCase):
    """Test FeatureFeedbackSummary model methods"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='feedbackuser156',
            password='testpass123'
        )

    def test_update_summary_no_feedback_returns_early(self):
        """Cover the total==0 early return branch"""
        from accounts.models_feedback import FeatureFeedbackSummary
        # No FeatureFeedback objects exist for this feature
        FeatureFeedbackSummary.update_summary('nonexistent_feature_xyz')
        # Should not create a summary (returns early)
        self.assertFalse(
            FeatureFeedbackSummary.objects.filter(feature='nonexistent_feature_xyz').exists()
        )

    def test_update_summary_with_feedback_data(self):
        """Cover the main body of update_summary with real data"""
        from accounts.models_feedback import FeatureFeedback, FeatureFeedbackSummary

        # Create some feedback entries
        FeatureFeedback.objects.create(
            user=self.user,
            feature='ai_transcription',
            worked_as_expected=True,
            rating=5,
            what_you_like='Great feature',
            what_to_improve=''
        )
        FeatureFeedback.objects.create(
            user=self.user,
            feature='ai_transcription',
            worked_as_expected=False,
            rating=2,
            what_you_like='',
            what_to_improve='Needs improvement'
        )
        FeatureFeedback.objects.create(
            user=self.user,
            feature='ai_transcription',
            worked_as_expected=True,
            rating=4,
            what_you_like='Good',
            what_to_improve=''
        )

        FeatureFeedbackSummary.update_summary('ai_transcription')

        summary = FeatureFeedbackSummary.objects.get(feature='ai_transcription')
        self.assertEqual(summary.total_responses, 3)
        self.assertEqual(summary.rating_5_count, 1)
        self.assertEqual(summary.rating_4_count, 1)
        self.assertEqual(summary.rating_2_count, 1)
        self.assertEqual(summary.worked_as_expected_count, 2)

    def test_update_summary_str(self):
        """Cover FeatureFeedbackSummary.__str__"""
        from accounts.models_feedback import FeatureFeedback, FeatureFeedbackSummary

        FeatureFeedback.objects.create(
            user=self.user,
            feature='pdf_upload',
            worked_as_expected=True,
            rating=4,
        )
        FeatureFeedbackSummary.update_summary('pdf_upload')
        summary = FeatureFeedbackSummary.objects.get(feature='pdf_upload')
        result = str(summary)
        self.assertIn('pdf_upload', result)
        self.assertIn('Avg:', result)

    def test_feature_feedback_is_positive_true(self):
        """Cover is_positive property — positive case"""
        from accounts.models_feedback import FeatureFeedback
        fb = FeatureFeedback(
            user=self.user,
            feature='ai_transcription',
            worked_as_expected=True,
            rating=5,
        )
        self.assertTrue(fb.is_positive)

    def test_feature_feedback_is_positive_false(self):
        """Cover is_positive property — negative case"""
        from accounts.models_feedback import FeatureFeedback
        fb = FeatureFeedback(
            user=self.user,
            feature='ai_transcription',
            worked_as_expected=False,
            rating=2,
        )
        self.assertFalse(fb.is_positive)

    def test_feature_feedback_needs_attention_true(self):
        """Cover needs_attention property — needs attention"""
        from accounts.models_feedback import FeatureFeedback
        fb = FeatureFeedback(
            user=self.user,
            feature='ai_transcription',
            worked_as_expected=False,
            rating=1,
        )
        self.assertTrue(fb.needs_attention)

    def test_feature_feedback_needs_attention_false(self):
        """Cover needs_attention property — all good"""
        from accounts.models_feedback import FeatureFeedback
        fb = FeatureFeedback(
            user=self.user,
            feature='ai_transcription',
            worked_as_expected=True,
            rating=5,
        )
        self.assertFalse(fb.needs_attention)

    def test_update_summary_called_twice_updates(self):
        """Cover update_or_create update path (summary already exists)"""
        from accounts.models_feedback import FeatureFeedback, FeatureFeedbackSummary

        FeatureFeedback.objects.create(
            user=self.user,
            feature='audio_assembly',
            worked_as_expected=True,
            rating=3,
        )
        # First call creates
        FeatureFeedbackSummary.update_summary('audio_assembly')
        # Second call updates
        FeatureFeedback.objects.create(
            user=self.user,
            feature='audio_assembly',
            worked_as_expected=True,
            rating=5,
        )
        FeatureFeedbackSummary.update_summary('audio_assembly')
        summary = FeatureFeedbackSummary.objects.get(feature='audio_assembly')
        self.assertEqual(summary.total_responses, 2)
