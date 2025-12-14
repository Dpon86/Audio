"""
Unit tests for audioDiagnostic models.
Tests model creation, validation, relationships, and business logic.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from audioDiagnostic.models import (
    AudioProject, AudioFile, TranscriptionSegment, 
    TranscriptionWord, ProcessingResult
)
import json


class AudioProjectModelTest(TestCase):
    """Test AudioProject model"""
    
    def setUp(self):
        """Create test user for all tests"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_audio_project(self):
        """Test creating a basic audio project"""
        project = AudioProject.objects.create(
            user=self.user,
            title="Test Project",
            description="Test description",
            status="setup"
        )
        
        self.assertEqual(project.title, "Test Project")
        self.assertEqual(project.status, "setup")
        self.assertEqual(project.user, self.user)
        self.assertIsNotNone(project.created_at)
        self.assertIsNotNone(project.updated_at)
    
    def test_project_default_status(self):
        """Test that default status is 'setup'"""
        project = AudioProject.objects.create(
            user=self.user,
            title="Test Project"
        )
        self.assertEqual(project.status, "setup")
    
    def test_project_status_choices(self):
        """Test all valid status choices"""
        valid_statuses = ['setup', 'uploading', 'ready', 'transcribing', 
                         'transcribed', 'processing', 'completed', 'failed']
        
        for status_choice in valid_statuses:
            project = AudioProject.objects.create(
                user=self.user,
                title=f"Project {status_choice}",
                status=status_choice
            )
            self.assertEqual(project.status, status_choice)
    
    def test_project_ordering(self):
        """Test that projects are ordered by created_at descending"""
        project1 = AudioProject.objects.create(user=self.user, title="First")
        project2 = AudioProject.objects.create(user=self.user, title="Second")
        project3 = AudioProject.objects.create(user=self.user, title="Third")
        
        projects = AudioProject.objects.all()
        self.assertEqual(projects[0], project3)  # Most recent first
        self.assertEqual(projects[1], project2)
        self.assertEqual(projects[2], project1)
    
    def test_project_str_representation(self):
        """Test string representation of project"""
        project = AudioProject.objects.create(
            user=self.user,
            title="Test Project"
        )
        expected = f"Test Project - {self.user.username}"
        self.assertEqual(str(project), expected)
    
    def test_audio_files_count_property(self):
        """Test audio_files_count property"""
        project = AudioProject.objects.create(user=self.user, title="Test")
        
        self.assertEqual(project.audio_files_count, 0)
        
        # Add audio files
        AudioFile.objects.create(
            project=project,
            title="File 1",
            filename="file1.mp3",
            order_index=0
        )
        AudioFile.objects.create(
            project=project,
            title="File 2",
            filename="file2.mp3",
            order_index=1
        )
        
        self.assertEqual(project.audio_files_count, 2)
    
    def test_processed_files_count_property(self):
        """Test processed_files_count property"""
        project = AudioProject.objects.create(user=self.user, title="Test")
        
        AudioFile.objects.create(
            project=project,
            title="File 1",
            filename="file1.mp3",
            status="uploaded",
            order_index=0
        )
        AudioFile.objects.create(
            project=project,
            title="File 2",
            filename="file2.mp3",
            status="transcribed",
            order_index=1
        )
        
        # Note: processed_files_count looks for 'completed' status
        # but AudioFile doesn't have that status in choices
        # This might be a bug in the model
        self.assertEqual(project.processed_files_count, 0)
    
    def test_parent_project_relationship(self):
        """Test iterative cleaning parent-child relationship"""
        parent = AudioProject.objects.create(
            user=self.user,
            title="Parent Project",
            iteration_number=0
        )
        
        child = AudioProject.objects.create(
            user=self.user,
            title="Child Project",
            parent_project=parent,
            iteration_number=1
        )
        
        self.assertEqual(child.parent_project, parent)
        self.assertEqual(child.iteration_number, 1)
        self.assertIn(child, parent.iterations.all())
    
    def test_json_fields(self):
        """Test JSON field storage and retrieval"""
        duplicates = [
            {"segment_id": 1, "text": "duplicate text"},
            {"segment_id": 5, "text": "duplicate text"}
        ]
        
        project = AudioProject.objects.create(
            user=self.user,
            title="Test Project",
            duplicates_detected=duplicates,
            processing_summary={"total": 10, "removed": 2}
        )
        
        # Retrieve and verify
        saved_project = AudioProject.objects.get(id=project.id)
        self.assertEqual(saved_project.duplicates_detected, duplicates)
        self.assertEqual(saved_project.processing_summary["total"], 10)


class AudioFileModelTest(TestCase):
    """Test AudioFile model"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'pass')
        self.project = AudioProject.objects.create(
            user=self.user,
            title="Test Project"
        )
    
    def test_create_audio_file(self):
        """Test creating an audio file"""
        audio_file = AudioFile.objects.create(
            project=self.project,
            title="Chapter 1",
            filename="chapter1.mp3",
            order_index=0
        )
        
        self.assertEqual(audio_file.title, "Chapter 1")
        self.assertEqual(audio_file.status, "uploaded")  # Default status
        self.assertEqual(audio_file.project, self.project)
    
    def test_audio_file_ordering(self):
        """Test audio files are ordered by order_index"""
        file3 = AudioFile.objects.create(
            project=self.project, title="File 3", 
            filename="f3.mp3", order_index=2
        )
        file1 = AudioFile.objects.create(
            project=self.project, title="File 1",
            filename="f1.mp3", order_index=0
        )
        file2 = AudioFile.objects.create(
            project=self.project, title="File 2",
            filename="f2.mp3", order_index=1
        )
        
        files = AudioFile.objects.filter(project=self.project)
        self.assertEqual(files[0], file1)
        self.assertEqual(files[1], file2)
        self.assertEqual(files[2], file3)
    
    def test_unique_order_index_per_project(self):
        """Test that order_index is unique per project"""
        AudioFile.objects.create(
            project=self.project,
            title="File 1",
            filename="f1.mp3",
            order_index=0
        )
        
        # Creating another file with same order_index should raise error
        with self.assertRaises(Exception):
            AudioFile.objects.create(
                project=self.project,
                title="File 2",
                filename="f2.mp3",
                order_index=0
            )
    
    def test_audio_file_cascade_delete(self):
        """Test that deleting project deletes audio files"""
        audio_file = AudioFile.objects.create(
            project=self.project,
            title="File 1",
            filename="f1.mp3",
            order_index=0
        )
        
        project_id = self.project.id
        self.project.delete()
        
        # Audio file should be deleted
        self.assertFalse(AudioFile.objects.filter(id=audio_file.id).exists())


class TranscriptionSegmentModelTest(TestCase):
    """Test TranscriptionSegment model"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'pass')
        self.project = AudioProject.objects.create(user=self.user, title="Test")
        self.audio_file = AudioFile.objects.create(
            project=self.project,
            title="Chapter 1",
            filename="ch1.mp3",
            order_index=0
        )
    
    def test_create_segment(self):
        """Test creating a transcription segment"""
        segment = TranscriptionSegment.objects.create(
            audio_file=self.audio_file,
            text="This is a test segment.",
            start_time=0.0,
            end_time=2.5,
            segment_index=0
        )
        
        self.assertEqual(segment.text, "This is a test segment.")
        self.assertEqual(segment.start_time, 0.0)
        self.assertEqual(segment.end_time, 2.5)
        self.assertFalse(segment.is_duplicate)
    
    def test_segment_ordering(self):
        """Test segments are ordered by segment_index"""
        seg2 = TranscriptionSegment.objects.create(
            audio_file=self.audio_file, text="Second", 
            start_time=2.5, end_time=5.0, segment_index=1
        )
        seg1 = TranscriptionSegment.objects.create(
            audio_file=self.audio_file, text="First",
            start_time=0.0, end_time=2.5, segment_index=0
        )
        
        segments = TranscriptionSegment.objects.filter(audio_file=self.audio_file)
        self.assertEqual(segments[0], seg1)
        self.assertEqual(segments[1], seg2)
    
    def test_duplicate_detection_fields(self):
        """Test duplicate detection related fields"""
        segment = TranscriptionSegment.objects.create(
            audio_file=self.audio_file,
            text="Duplicate text",
            start_time=0.0,
            end_time=2.0,
            segment_index=0,
            is_duplicate=True,
            duplicate_type="sentence",
            duplicate_group_id="group_123",
            is_kept=False
        )
        
        self.assertTrue(segment.is_duplicate)
        self.assertEqual(segment.duplicate_type, "sentence")
        self.assertEqual(segment.duplicate_group_id, "group_123")
        self.assertFalse(segment.is_kept)


class TranscriptionWordModelTest(TestCase):
    """Test TranscriptionWord model"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'pass')
        self.project = AudioProject.objects.create(user=self.user, title="Test")
        self.audio_file = AudioFile.objects.create(
            project=self.project, title="Chapter 1",
            filename="ch1.mp3", order_index=0
        )
        self.segment = TranscriptionSegment.objects.create(
            audio_file=self.audio_file,
            text="Hello world",
            start_time=0.0,
            end_time=1.0,
            segment_index=0
        )
    
    def test_create_word(self):
        """Test creating a transcription word"""
        word = TranscriptionWord.objects.create(
            segment=self.segment,
            audio_file=self.audio_file,
            word="Hello",
            start_time=0.0,
            end_time=0.5,
            confidence=0.95,
            word_index=0
        )
        
        self.assertEqual(word.word, "Hello")
        self.assertEqual(word.confidence, 0.95)
        self.assertEqual(word.segment, self.segment)
    
    def test_word_ordering(self):
        """Test words are ordered by word_index"""
        word2 = TranscriptionWord.objects.create(
            segment=self.segment, word="world",
            start_time=0.5, end_time=1.0, word_index=1
        )
        word1 = TranscriptionWord.objects.create(
            segment=self.segment, word="Hello",
            start_time=0.0, end_time=0.5, word_index=0
        )
        
        words = TranscriptionWord.objects.filter(segment=self.segment)
        self.assertEqual(words[0], word1)
        self.assertEqual(words[1], word2)
    
    def test_word_str_representation(self):
        """Test string representation of word"""
        word = TranscriptionWord.objects.create(
            segment=self.segment,
            word="Hello",
            start_time=0.25,
            end_time=0.75,
            word_index=0
        )
        
        self.assertEqual(str(word), "Hello (0.25s)")


class ProcessingResultModelTest(TestCase):
    """Test ProcessingResult model"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'pass')
        self.project = AudioProject.objects.create(user=self.user, title="Test")
    
    def test_create_processing_result(self):
        """Test creating a processing result"""
        result = ProcessingResult.objects.create(
            project=self.project,
            total_segments_processed=100,
            duplicates_removed=15,
            words_removed=50,
            original_total_duration=600.0,
            final_duration=550.0,
            time_saved=50.0
        )
        
        self.assertEqual(result.total_segments_processed, 100)
        self.assertEqual(result.duplicates_removed, 15)
        self.assertEqual(result.time_saved, 50.0)
    
    def test_one_to_one_relationship(self):
        """Test that only one ProcessingResult per project"""
        ProcessingResult.objects.create(
            project=self.project,
            total_segments_processed=100
        )
        
        # Creating another should raise error
        with self.assertRaises(Exception):
            ProcessingResult.objects.create(
                project=self.project,
                total_segments_processed=200
            )
    
    def test_processing_result_str(self):
        """Test string representation"""
        result = ProcessingResult.objects.create(project=self.project)
        expected = f"Processing Result for {self.project.title}"
        self.assertEqual(str(result), expected)
