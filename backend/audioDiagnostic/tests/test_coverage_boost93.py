"""
Wave 93 — Coverage boost
Targets:
  - audioDiagnostic/serializers.py:
      FileUploadSerializer, PDFUploadSerializer, AudioUploadSerializer,
      DuplicateConfirmationSerializer
  - audioDiagnostic/serializers.py:
      TranscriptionSerializer, DuplicateGroupSerializer, ClientTranscriptionSerializer
      AIDetectionRequestSerializer, AIPDFComparisonRequestSerializer
"""
from django.test import TestCase
from unittest.mock import MagicMock
from django.contrib.auth import get_user_model

User = get_user_model()


def _make_file(name, size=100, content_type='audio/mpeg'):
    mock = MagicMock()
    mock.name = name
    mock.size = size
    mock.content_type = content_type
    return mock


# ─── FileUploadSerializer ────────────────────────────────────────────────────

class FileUploadSerializerTests(TestCase):

    def test_file_too_large(self):
        from audioDiagnostic.serializers import FileUploadSerializer
        from rest_framework import serializers as drf_serializers
        s = FileUploadSerializer()
        big_file = _make_file('big.mp3', size=600 * 1024 * 1024)
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_file(big_file)

    def test_file_ok(self):
        from audioDiagnostic.serializers import FileUploadSerializer
        s = FileUploadSerializer()
        ok_file = _make_file('ok.mp3', size=1024)
        result = s.validate_file(ok_file)
        self.assertEqual(result, ok_file)


# ─── PDFUploadSerializer ─────────────────────────────────────────────────────

class PDFUploadSerializerTests(TestCase):

    def test_valid_pdf(self):
        from audioDiagnostic.serializers import PDFUploadSerializer
        s = PDFUploadSerializer()
        f = _make_file('book.pdf', size=1024, content_type='application/pdf')
        result = s.validate_file(f)
        self.assertEqual(result, f)

    def test_wrong_extension(self):
        from audioDiagnostic.serializers import PDFUploadSerializer
        from rest_framework import serializers as drf_serializers
        s = PDFUploadSerializer()
        f = _make_file('doc.docx', size=1024, content_type='application/pdf')
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_file(f)

    def test_wrong_mime_type(self):
        from audioDiagnostic.serializers import PDFUploadSerializer
        from rest_framework import serializers as drf_serializers
        s = PDFUploadSerializer()
        f = _make_file('book.pdf', size=1024, content_type='text/html')
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_file(f)

    def test_no_content_type(self):
        from audioDiagnostic.serializers import PDFUploadSerializer
        s = PDFUploadSerializer()
        f = _make_file('book.pdf', size=1024)
        f.content_type = None
        result = s.validate_file(f)
        self.assertEqual(result, f)


# ─── AudioUploadSerializer ───────────────────────────────────────────────────

class AudioUploadSerializerTests(TestCase):

    def test_valid_mp3(self):
        from audioDiagnostic.serializers import AudioUploadSerializer
        s = AudioUploadSerializer()
        f = _make_file('track.mp3', size=1024, content_type='audio/mpeg')
        result = s.validate_file(f)
        self.assertEqual(result, f)

    def test_invalid_extension(self):
        from audioDiagnostic.serializers import AudioUploadSerializer
        from rest_framework import serializers as drf_serializers
        s = AudioUploadSerializer()
        f = _make_file('track.txt', size=1024, content_type='audio/mpeg')
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_file(f)

    def test_invalid_mime(self):
        from audioDiagnostic.serializers import AudioUploadSerializer
        from rest_framework import serializers as drf_serializers
        s = AudioUploadSerializer()
        f = _make_file('track.mp3', size=1024, content_type='text/plain')
        with self.assertRaises(drf_serializers.ValidationError):
            s.validate_file(f)

    def test_no_content_type(self):
        from audioDiagnostic.serializers import AudioUploadSerializer
        s = AudioUploadSerializer()
        f = _make_file('track.wav', size=1024)
        f.content_type = None
        result = s.validate_file(f)
        self.assertEqual(result, f)

    def test_valid_wav(self):
        from audioDiagnostic.serializers import AudioUploadSerializer
        s = AudioUploadSerializer()
        f = _make_file('track.wav', size=1024, content_type='audio/wav')
        result = s.validate_file(f)
        self.assertEqual(result, f)


# ─── DuplicateConfirmationSerializer ─────────────────────────────────────────

class DuplicateConfirmationSerializerTests(TestCase):

    def test_valid_data(self):
        from audioDiagnostic.serializers import DuplicateConfirmationSerializer
        s = DuplicateConfirmationSerializer(data={
            'confirmed_deletions': [
                {'segment_id': 1, 'duplicate_group_id': 'grp_1'},
            ],
            'use_clean_audio': False,
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_not_a_list(self):
        from audioDiagnostic.serializers import DuplicateConfirmationSerializer
        s = DuplicateConfirmationSerializer(data={
            'confirmed_deletions': {'segment_id': 1},
            'use_clean_audio': False,
        })
        self.assertFalse(s.is_valid())

    def test_item_not_dict(self):
        from audioDiagnostic.serializers import DuplicateConfirmationSerializer
        s = DuplicateConfirmationSerializer(data={
            'confirmed_deletions': [1, 2, 3],
            'use_clean_audio': False,
        })
        self.assertFalse(s.is_valid())

    def test_missing_required_field(self):
        from audioDiagnostic.serializers import DuplicateConfirmationSerializer
        s = DuplicateConfirmationSerializer(data={
            'confirmed_deletions': [{'segment_id': 1}],  # missing duplicate_group_id
            'use_clean_audio': False,
        })
        self.assertFalse(s.is_valid())


# ─── AIDetectionRequestSerializer ────────────────────────────────────────────

class AIDetectionRequestSerializerTests(TestCase):

    def test_valid(self):
        from audioDiagnostic.serializers import AIDetectionRequestSerializer
        s = AIDetectionRequestSerializer(data={
            'audio_file_id': 1,
            'min_words': 3,
            'similarity_threshold': 0.85,
            'keep_occurrence': 'last',
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_invalid_similarity(self):
        from audioDiagnostic.serializers import AIDetectionRequestSerializer
        s = AIDetectionRequestSerializer(data={
            'audio_file_id': 1,
            'similarity_threshold': 1.5,  # out of range
        })
        self.assertFalse(s.is_valid())


# ─── AIPDFComparisonRequestSerializer ────────────────────────────────────────

class AIPDFComparisonRequestSerializerTests(TestCase):

    def test_valid(self):
        from audioDiagnostic.serializers import AIPDFComparisonRequestSerializer
        s = AIPDFComparisonRequestSerializer(data={
            'audio_file_id': 1,
        })
        self.assertTrue(s.is_valid(), s.errors)
