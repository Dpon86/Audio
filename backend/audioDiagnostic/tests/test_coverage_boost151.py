"""
Wave 151: ai_pdf_comparison_task.py utility functions - ai_find_start_position, ai_detailed_comparison, find_matching_segments
"""
from django.test import TestCase
from unittest.mock import MagicMock, patch, PropertyMock
from django.contrib.auth import get_user_model
from rest_framework.test import force_authenticate

User = get_user_model()


class AIFindStartPositionTests(TestCase):
    """Test ai_find_start_position utility function."""

    def test_success_path(self):
        """Test successful response from AI."""
        from audioDiagnostic.tasks.ai_pdf_comparison_task import ai_find_start_position

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"start_position": 500, "confidence": 0.9, "matched_text": "some text", "reasoning": "found it"}'
        mock_client.chat.completions.create.return_value = mock_response

        pdf_text = "A" * 10000
        transcript = "B" * 2000

        result = ai_find_start_position(mock_client, pdf_text, transcript, [])

        self.assertIn('start_position', result)
        self.assertEqual(result['start_position'], 500)
        self.assertEqual(result['confidence'], 0.9)

    def test_success_with_markdown_blocks(self):
        """Test JSON wrapped in markdown code blocks."""
        from audioDiagnostic.tasks.ai_pdf_comparison_task import ai_find_start_position

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '```json\n{"start_position": 0, "confidence": 0.7, "matched_text": "text", "reasoning": "reason"}\n```'
        mock_client.chat.completions.create.return_value = mock_response

        result = ai_find_start_position(mock_client, "PDF content", "transcript", [])

        self.assertIn('start_position', result)

    def test_fallback_on_error(self):
        """Test fallback when AI call fails."""
        from audioDiagnostic.tasks.ai_pdf_comparison_task import ai_find_start_position

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")

        pdf_text = "C" * 5000
        transcript = "D" * 1000

        result = ai_find_start_position(mock_client, pdf_text, transcript, [])

        # Falls back to position 0
        self.assertEqual(result['start_position'], 0)
        self.assertIn('confidence', result)

    def test_fallback_on_invalid_json(self):
        """Test fallback when AI returns invalid JSON."""
        from audioDiagnostic.tasks.ai_pdf_comparison_task import ai_find_start_position

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = 'not valid json at all'
        mock_client.chat.completions.create.return_value = mock_response

        result = ai_find_start_position(mock_client, "PDF text", "transcript", [])

        self.assertEqual(result['start_position'], 0)

    def test_with_ignored_sections(self):
        """Test with ignored sections passed."""
        from audioDiagnostic.tasks.ai_pdf_comparison_task import ai_find_start_position

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"start_position": 100, "confidence": 0.8, "matched_text": "x", "reasoning": "y"}'
        mock_client.chat.completions.create.return_value = mock_response

        ignored = [{'text': 'ignore this'}]
        result = ai_find_start_position(mock_client, "PDF content here", "transcript here", ignored)

        self.assertEqual(result['start_position'], 100)


class AIDetailedComparisonTests(TestCase):
    """Test ai_detailed_comparison utility function."""

    def _mock_client(self, json_str):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json_str
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    def test_success_path(self):
        """Test successful comparison response."""
        from audioDiagnostic.tasks.ai_pdf_comparison_task import ai_detailed_comparison

        json_content = '''{
            "missing_content": [{"text": "missing text", "word_count": 5, "position_in_pdf": "ch1"}],
            "extra_content": [{"text": "extra text", "word_count": 2, "possible_type": "narrator_info", "position_in_transcript": "start"}],
            "statistics": {
                "transcript_word_count": 100,
                "pdf_word_count": 120,
                "matching_word_count": 90,
                "missing_word_count": 30,
                "extra_word_count": 10,
                "accuracy_percentage": 90.0,
                "coverage_percentage": 75.0,
                "match_quality": "good"
            },
            "ai_analysis": "Good match overall"
        }'''

        mock_client = self._mock_client(json_content)

        result = ai_detailed_comparison(mock_client, "PDF text here", "Transcript text", 0, "PDF section", [])

        self.assertIn('missing_content', result)
        self.assertIn('extra_content', result)
        self.assertIn('statistics', result)
        self.assertEqual(result['statistics']['accuracy_percentage'], 90.0)

    def test_fallback_on_error(self):
        """Test fallback when AI call fails."""
        from audioDiagnostic.tasks.ai_pdf_comparison_task import ai_detailed_comparison

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API timeout")

        result = ai_detailed_comparison(mock_client, "PDF", "Transcript", 0, "section", [])

        # Returns empty result
        self.assertIn('missing_content', result)
        self.assertIn('extra_content', result)
        self.assertEqual(result['missing_content'], [])

    def test_with_ignored_sections(self):
        """Test with ignored_sections provided."""
        from audioDiagnostic.tasks.ai_pdf_comparison_task import ai_detailed_comparison

        json_content = '{"missing_content": [], "extra_content": [], "statistics": {"transcript_word_count": 50, "pdf_word_count": 50, "matching_word_count": 50, "missing_word_count": 0, "extra_word_count": 0, "accuracy_percentage": 100.0, "coverage_percentage": 100.0, "match_quality": "excellent"}, "ai_analysis": "Perfect match"}'
        mock_client = self._mock_client(json_content)

        ignored = [{'text': 'some ignored text'}, {'text': 'another ignored'}]
        result = ai_detailed_comparison(mock_client, "PDF text", "Transcript text", 100, "matched section", ignored)

        self.assertIn('statistics', result)
        self.assertEqual(result['statistics']['accuracy_percentage'], 100.0)

    def test_with_markdown_json(self):
        """Test JSON in markdown blocks."""
        from audioDiagnostic.tasks.ai_pdf_comparison_task import ai_detailed_comparison

        json_content = '```json\n{"missing_content": [], "extra_content": [], "statistics": {"transcript_word_count": 10, "pdf_word_count": 10, "matching_word_count": 10, "missing_word_count": 0, "extra_word_count": 0, "accuracy_percentage": 95.0, "coverage_percentage": 100.0, "match_quality": "excellent"}, "ai_analysis": "ok"}\n```'
        mock_client = self._mock_client(json_content)

        result = ai_detailed_comparison(mock_client, "PDF", "Transcript", 0, "section", [])
        self.assertIn('statistics', result)


class FindMatchingSegmentsTests(TestCase):
    """Test find_matching_segments utility."""

    def test_matching_segments(self):
        """Test finding matching segments."""
        from audioDiagnostic.tasks.ai_pdf_comparison_task import find_matching_segments

        segments = [
            MagicMock(text='Hello world this is a test', start_time=0.0, end_time=3.0),
            MagicMock(text='Another sentence here', start_time=3.0, end_time=6.0),
            MagicMock(text='Third segment text', start_time=6.0, end_time=9.0),
        ]

        result = find_matching_segments('Hello world', segments)

        self.assertIsInstance(result, list)

    def test_no_matching_segments(self):
        """Test with no matching segments."""
        from audioDiagnostic.tasks.ai_pdf_comparison_task import find_matching_segments

        segments = [
            MagicMock(text='Nothing relevant', start_time=0.0, end_time=1.0),
        ]

        result = find_matching_segments('xyz abc def ghi jkl mno', segments)
        self.assertIsInstance(result, list)

    def test_empty_segments(self):
        """Test with empty segments list."""
        from audioDiagnostic.tasks.ai_pdf_comparison_task import find_matching_segments

        result = find_matching_segments('some text to find', [])
        self.assertEqual(result, [])
