"""
Wave 87 — Coverage boost
Targets serializer validation logic in:
  - audioDiagnostic/serializers.py
    (AudioProjectSerializer, AudioFileSerializer,
     TranscriptionSegmentSerializer, TranscriptionWordSerializer,
     ProcessingResultSerializer, ProjectCreateSerializer)
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class AudioProjectSerializerTests(TestCase):

    def test_validate_title_too_short(self):
        from audioDiagnostic.serializers import AudioProjectSerializer
        s = AudioProjectSerializer(data={'title': 'ab'})
        self.assertFalse(s.is_valid())
        self.assertIn('title', s.errors)

    def test_validate_title_too_long(self):
        from audioDiagnostic.serializers import AudioProjectSerializer
        s = AudioProjectSerializer(data={'title': 'x' * 201})
        self.assertFalse(s.is_valid())
        self.assertIn('title', s.errors)

    def test_validate_title_valid(self):
        from audioDiagnostic.serializers import AudioProjectSerializer
        # Just validate the field independently
        s = AudioProjectSerializer(data={'title': 'Valid Title'})
        # Not fully valid (missing required fields) but title shouldn't be the error
        s.is_valid()
        self.assertNotIn('title', s.errors)

    def test_validate_description_too_long(self):
        from audioDiagnostic.serializers import AudioProjectSerializer
        s = AudioProjectSerializer(data={'title': 'Valid Title', 'description': 'x' * 1001})
        self.assertFalse(s.is_valid())
        self.assertIn('description', s.errors)

    def test_validate_description_none_ok(self):
        from audioDiagnostic.serializers import AudioProjectSerializer
        # description is optional
        s = AudioProjectSerializer(data={'title': 'Valid Title'})
        s.is_valid()
        self.assertNotIn('description', s.errors)


class AudioFileSerializerTests(TestCase):

    def test_validate_title_empty(self):
        from audioDiagnostic.serializers import AudioFileSerializer
        s = AudioFileSerializer(data={'title': ''})
        self.assertFalse(s.is_valid())
        self.assertIn('title', s.errors)

    def test_validate_title_too_long(self):
        from audioDiagnostic.serializers import AudioFileSerializer
        s = AudioFileSerializer(data={'title': 'x' * 201})
        self.assertFalse(s.is_valid())
        self.assertIn('title', s.errors)

    def test_validate_order_index_negative(self):
        from audioDiagnostic.serializers import AudioFileSerializer
        s = AudioFileSerializer(data={'title': 'Test', 'order_index': -1})
        self.assertFalse(s.is_valid())
        self.assertIn('order_index', s.errors)

    def test_validate_order_index_zero_ok(self):
        from audioDiagnostic.serializers import AudioFileSerializer
        s = AudioFileSerializer(data={'title': 'Test', 'order_index': 0})
        s.is_valid()
        self.assertNotIn('order_index', s.errors)


class TranscriptionSegmentSerializerTests(TestCase):

    def test_validate_negative_start(self):
        from audioDiagnostic.serializers import TranscriptionSegmentSerializer
        s = TranscriptionSegmentSerializer(data={
            'start_time': -1.0,
            'end_time': 1.0,
            'text': 'hello',
        })
        self.assertFalse(s.is_valid())

    def test_validate_negative_end(self):
        from audioDiagnostic.serializers import TranscriptionSegmentSerializer
        s = TranscriptionSegmentSerializer(data={
            'start_time': 0.0,
            'end_time': -1.0,
            'text': 'hello',
        })
        self.assertFalse(s.is_valid())

    def test_validate_end_before_start(self):
        from audioDiagnostic.serializers import TranscriptionSegmentSerializer
        s = TranscriptionSegmentSerializer(data={
            'start_time': 5.0,
            'end_time': 3.0,
            'text': 'hello',
        })
        self.assertFalse(s.is_valid())

    def test_valid_times(self):
        from audioDiagnostic.serializers import TranscriptionSegmentSerializer
        s = TranscriptionSegmentSerializer(data={
            'start_time': 1.0,
            'end_time': 3.0,
            'text': 'hello',
        })
        s.is_valid()
        self.assertNotIn('non_field_errors', s.errors)


class TranscriptionWordSerializerTests(TestCase):

    def test_confidence_out_of_range_high(self):
        from audioDiagnostic.serializers import TranscriptionWordSerializer
        s = TranscriptionWordSerializer(data={
            'word': 'test',
            'confidence': 1.5,
        })
        self.assertFalse(s.is_valid())
        self.assertIn('confidence', s.errors)

    def test_confidence_out_of_range_low(self):
        from audioDiagnostic.serializers import TranscriptionWordSerializer
        s = TranscriptionWordSerializer(data={
            'word': 'test',
            'confidence': -0.1,
        })
        self.assertFalse(s.is_valid())
        self.assertIn('confidence', s.errors)

    def test_confidence_none_ok(self):
        from audioDiagnostic.serializers import TranscriptionWordSerializer
        s = TranscriptionWordSerializer(data={'word': 'test', 'confidence': None})
        s.is_valid()
        self.assertNotIn('confidence', s.errors)

    def test_confidence_valid(self):
        from audioDiagnostic.serializers import TranscriptionWordSerializer
        s = TranscriptionWordSerializer(data={'word': 'test', 'confidence': 0.9})
        s.is_valid()
        self.assertNotIn('confidence', s.errors)


class ProcessingResultSerializerTests(TestCase):

    def test_negative_int_field(self):
        from audioDiagnostic.serializers import ProcessingResultSerializer
        s = ProcessingResultSerializer(data={
            'project': 1,
            'total_segments_processed': -1,
            'duplicates_removed': 0,
        })
        self.assertFalse(s.is_valid())

    def test_negative_float_field(self):
        from audioDiagnostic.serializers import ProcessingResultSerializer
        s = ProcessingResultSerializer(data={
            'project': 1,
            'total_segments_processed': 0,
            'original_total_duration': -5.0,
        })
        self.assertFalse(s.is_valid())

    def test_zero_values_ok(self):
        from audioDiagnostic.serializers import ProcessingResultSerializer
        s = ProcessingResultSerializer(data={
            'project': 1,
            'total_segments_processed': 0,
            'duplicates_removed': 0,
            'words_removed': 0,
            'sentences_removed': 0,
            'paragraphs_removed': 0,
            'missing_content_count': 0,
            'original_total_duration': 0.0,
            'final_duration': 0.0,
            'time_saved': 0.0,
            'pdf_coverage_percentage': 0.0,
        })
        s.is_valid()
        # project field may fail (FK), but our fields should not
        self.assertNotIn('total_segments_processed', s.errors)
        self.assertNotIn('original_total_duration', s.errors)


class ProjectCreateSerializerTests(TestCase):

    def test_title_too_short(self):
        from audioDiagnostic.serializers import ProjectCreateSerializer
        s = ProjectCreateSerializer(data={'title': 'ab'})
        self.assertFalse(s.is_valid())
        self.assertIn('title', s.errors)

    def test_title_valid(self):
        from audioDiagnostic.serializers import ProjectCreateSerializer
        s = ProjectCreateSerializer(data={'title': 'My Great Project'})
        self.assertTrue(s.is_valid())

    def test_description_optional(self):
        from audioDiagnostic.serializers import ProjectCreateSerializer
        s = ProjectCreateSerializer(data={'title': 'Valid Title'})
        self.assertTrue(s.is_valid())

    def test_description_provided(self):
        from audioDiagnostic.serializers import ProjectCreateSerializer
        s = ProjectCreateSerializer(data={'title': 'Valid Title', 'description': 'A description'})
        self.assertTrue(s.is_valid())
