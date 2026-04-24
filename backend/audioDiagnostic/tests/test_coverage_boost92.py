"""
Wave 92 — Coverage boost
Targets:
  - audioDiagnostic/services/ai/anthropic_client.py (parse_json_response, _calculate_cost)
  - audioDiagnostic/services/ai/duplicate_detector.py (DuplicateDetector mocked)
  - audioDiagnostic/utils/production_report.py (generate_production_report)
  - audioDiagnostic/utils/access_control.py remaining branches
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock, PropertyMock
from django.contrib.auth import get_user_model
from rest_framework.test import force_authenticate

User = get_user_model()


# ─── AnthropicClient tests ───────────────────────────────────────────────────

class AnthropicClientParseJsonTests(TestCase):

    def _make_client(self):
        from audioDiagnostic.services.ai.anthropic_client import AnthropicClient
        client = AnthropicClient.__new__(AnthropicClient)
        client.model = 'claude-3-5-sonnet-20241022'
        client.max_tokens = 4096
        client.max_retries = 3
        client.base_delay = 1
        # Mock inner Anthropic client
        client.client = MagicMock()
        return client

    def test_parse_direct_json(self):
        client = self._make_client()
        result = client.parse_json_response('{"key": "value"}')
        self.assertEqual(result['key'], 'value')

    def test_parse_markdown_json_block(self):
        client = self._make_client()
        content = '```json\n{"answer": 42}\n```'
        result = client.parse_json_response(content)
        self.assertEqual(result['answer'], 42)

    def test_parse_generic_code_block(self):
        client = self._make_client()
        content = '```\n{"value": true}\n```'
        result = client.parse_json_response(content)
        self.assertTrue(result['value'])

    def test_parse_invalid_raises(self):
        client = self._make_client()
        with self.assertRaises(ValueError):
            client.parse_json_response('not json at all')

    def test_calculate_cost(self):
        client = self._make_client()
        cost = client._calculate_cost(1_000_000, 1_000_000)
        self.assertAlmostEqual(cost, 18.0, places=2)  # $3 + $15

    def test_calculate_cost_zero(self):
        client = self._make_client()
        cost = client._calculate_cost(0, 0)
        self.assertEqual(cost, 0.0)

    def test_calculate_cost_small(self):
        client = self._make_client()
        cost = client._calculate_cost(1000, 500)
        expected = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
        self.assertAlmostEqual(cost, expected, places=6)


# ─── DuplicateDetector (mocked) tests ────────────────────────────────────────

class DuplicateDetectorTests(TestCase):

    def _make_detector(self):
        from audioDiagnostic.services.ai.duplicate_detector import DuplicateDetector
        detector = DuplicateDetector.__new__(DuplicateDetector)
        mock_client = MagicMock()
        mock_client.call_api.return_value = {
            'content': '{"duplicate_groups": [], "summary": {"total_duplicate_groups": 0}}',
            'usage': {'input_tokens': 100, 'output_tokens': 50, 'total_tokens': 150},
            'cost': 0.001,
            'model': 'claude-3-5-sonnet-20241022',
        }
        mock_client.parse_json_response.return_value = {
            'duplicate_groups': [],
            'summary': {'total_duplicate_groups': 0},
        }
        mock_prompts = MagicMock()
        mock_prompts.duplicate_detection_system_prompt.return_value = 'system'
        mock_prompts.duplicate_detection_prompt.return_value = 'user'
        detector.client = mock_client
        detector.prompts = mock_prompts
        return detector

    def test_detect_sentence_level_duplicates_success(self):
        detector = self._make_detector()
        result = detector.detect_sentence_level_duplicates(
            transcript_data={'segments': []},
        )
        self.assertIn('duplicate_groups', result)
        self.assertIn('ai_metadata', result)

    def test_detect_raises_on_client_error(self):
        from audioDiagnostic.services.ai.duplicate_detector import DuplicateDetector
        detector = DuplicateDetector.__new__(DuplicateDetector)
        mock_client = MagicMock()
        mock_client.call_api.side_effect = Exception("API error")
        mock_prompts = MagicMock()
        mock_prompts.duplicate_detection_system_prompt.return_value = 'system'
        mock_prompts.duplicate_detection_prompt.return_value = 'user'
        detector.client = mock_client
        detector.prompts = mock_prompts
        with self.assertRaises(Exception):
            detector.detect_sentence_level_duplicates({'segments': []})


# ─── production_report.py generate_production_report ─────────────────────────

class GenerateProductionReportTests(TestCase):

    def test_generate_basic_report(self):
        from audioDiagnostic.utils.production_report import generate_production_report
        from audioDiagnostic.utils.quality_scorer import QualitySegment, ErrorDetail
        from audioDiagnostic.utils.gap_detector import MissingSection

        # Minimal mocks
        mock_alignment = [MagicMock()]
        mock_alignment[0].match_type = 'exact'
        mock_alignment[0].timestamp = 0.0
        mock_alignment[0].pdf_word = 'hello'
        mock_alignment[0].transcript_word = 'hello'

        with patch('audioDiagnostic.utils.production_report.analyze_segments', return_value=[]):
            with patch('audioDiagnostic.utils.production_report.calculate_overall_quality', return_value=0.95):
                with patch('audioDiagnostic.utils.production_report.determine_overall_status', return_value='excellent'):
                    with patch('audioDiagnostic.utils.production_report.find_missing_sections', return_value=[]):
                        with patch('audioDiagnostic.utils.production_report.calculate_completeness_percentage', return_value=100.0):
                            result = generate_production_report(mock_alignment, 'Test title')
        self.assertIsNotNone(result)


# ─── access_control.py remaining coverage ────────────────────────────────────

class AccessControlTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='ac_user', password='pass123')

    def test_check_project_access_missing_project(self):
        from audioDiagnostic.utils.access_control import check_project_access
        result = check_project_access(user=self.user, project_id=999999)
        self.assertIsNone(result)

    def test_check_project_access_wrong_user(self):
        from audioDiagnostic.utils.access_control import check_project_access
        from audioDiagnostic.models import AudioProject
        other_user = User.objects.create_user(username='other_ac_user', password='pass123')
        project = AudioProject.objects.create(user=other_user, title='AC Project')
        result = check_project_access(user=self.user, project_id=project.id)
        self.assertIsNone(result)

    def test_check_project_access_correct_user(self):
        from audioDiagnostic.utils.access_control import check_project_access
        from audioDiagnostic.models import AudioProject
        project = AudioProject.objects.create(user=self.user, title='My Project')
        result = check_project_access(user=self.user, project_id=project.id)
        self.assertEqual(result.id, project.id)
