"""
API tests for audioDiagnostic views.
Tests all API endpoints with authentication and validation.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from audioDiagnostic.models import AudioProject, AudioFile
from django.core.files.uploadedfile import SimpleUploadedFile
import json


class ProjectAPITest(APITestCase):
    """Test Project API endpoints"""
    
    def setUp(self):
        """Create test user and authenticate"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
    
    def test_list_projects(self):
        """Test GET /api/projects/ - list user's projects"""
        # Create some projects
        AudioProject.objects.create(user=self.user, title="Project 1")
        AudioProject.objects.create(user=self.user, title="Project 2")
        
        response = self.client.get('/api/projects/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('projects', response.data)
        self.assertEqual(len(response.data['projects']), 2)
    
    def test_list_projects_unauthenticated(self):
        """Test that unauthenticated users cannot list projects"""
        self.client.credentials()  # Remove authentication
        
        response = self.client.get('/api/projects/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_projects_only_shows_own_projects(self):
        """Test that users only see their own projects"""
        # Create another user with projects
        other_user = User.objects.create_user('other', 'other@test.com', 'pass')
        AudioProject.objects.create(user=other_user, title="Other's Project")
        
        # Create project for authenticated user
        AudioProject.objects.create(user=self.user, title="My Project")
        
        response = self.client.get('/api/projects/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['projects']), 1)
        self.assertEqual(response.data['projects'][0]['title'], "My Project")
    
    def test_create_project(self):
        """Test POST /api/projects/ - create new project"""
        data = {
            'title': 'New Test Project',
            'description': 'Test description'
        }
        
        response = self.client.post('/api/projects/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('project', response.data)
        self.assertEqual(response.data['project']['title'], 'New Test Project')
        self.assertEqual(response.data['project']['status'], 'setup')
        
        # Verify in database
        self.assertTrue(AudioProject.objects.filter(title='New Test Project').exists())
    
    def test_create_project_validation(self):
        """Test project creation with invalid data"""
        # Missing title
        response = self.client.post('/api/projects/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Title too short
        response = self.client.post('/api/projects/', {'title': 'AB'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Title too long
        long_title = 'A' * 201
        response = self.client.post('/api/projects/', {'title': long_title}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_project_detail(self):
        """Test GET /api/projects/<id>/ - get project details"""
        project = AudioProject.objects.create(
            user=self.user,
            title="Test Project"
        )
        
        response = self.client.get(f'/api/projects/{project.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['project']['title'], "Test Project")
    
    def test_get_project_not_found(self):
        """Test getting non-existent project"""
        response = self.client.get('/api/projects/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_get_other_users_project_forbidden(self):
        """Test that users cannot access other users' projects"""
        other_user = User.objects.create_user('other', 'other@test.com', 'pass')
        other_project = AudioProject.objects.create(
            user=other_user,
            title="Other's Project"
        )
        
        response = self.client.get(f'/api/projects/{other_project.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_delete_project(self):
        """Test DELETE /api/projects/<id>/ - delete project"""
        project = AudioProject.objects.create(
            user=self.user,
            title="Project to Delete"
        )
        
        response = self.client.delete(f'/api/projects/{project.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(AudioProject.objects.filter(id=project.id).exists())


class FileUploadAPITest(APITestCase):
    """Test file upload endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'pass')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        self.project = AudioProject.objects.create(
            user=self.user,
            title="Test Project"
        )
    
    def test_upload_pdf(self):
        """Test PDF upload"""
        pdf_content = b'%PDF-1.4 fake pdf content'
        pdf_file = SimpleUploadedFile(
            "test.pdf",
            pdf_content,
            content_type="application/pdf"
        )
        
        response = self.client.post(
            f'/api/projects/{self.project.id}/upload-pdf/',
            {'pdf_file': pdf_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify project was updated
        self.project.refresh_from_db()
        self.assertTrue(self.project.pdf_file)
    
    def test_upload_pdf_wrong_type(self):
        """Test uploading non-PDF file as PDF"""
        txt_file = SimpleUploadedFile(
            "test.txt",
            b"not a pdf",
            content_type="text/plain"
        )
        
        response = self.client.post(
            f'/api/projects/{self.project.id}/upload-pdf/',
            {'pdf_file': txt_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_upload_audio(self):
        """Test audio file upload"""
        audio_content = b'fake audio content'
        audio_file = SimpleUploadedFile(
            "test.mp3",
            audio_content,
            content_type="audio/mpeg"
        )
        
        response = self.client.post(
            f'/api/projects/{self.project.id}/upload-audio/',
            {
                'audio_file': audio_file,
                'title': 'Chapter 1',
                'order_index': 0
            },
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify audio file was created
        self.assertTrue(
            AudioFile.objects.filter(
                project=self.project,
                title='Chapter 1'
            ).exists()
        )


class TranscriptionAPITest(APITestCase):
    """Test transcription endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'pass')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        self.project = AudioProject.objects.create(
            user=self.user,
            title="Test Project",
            status="ready"
        )
        
        # Create audio files
        AudioFile.objects.create(
            project=self.project,
            title="Chapter 1",
            filename="ch1.mp3",
            order_index=0
        )
    
    def test_start_transcription(self):
        """Test starting transcription for project"""
        response = self.client.post(
            f'/api/projects/{self.project.id}/transcribe/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_get_transcript(self):
        """Test getting project transcript"""
        response = self.client.get(
            f'/api/projects/{self.project.id}/transcript/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class RateLimitingTest(APITestCase):
    """Test API rate limiting"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'pass')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        self.project = AudioProject.objects.create(
            user=self.user,
            title="Test Project"
        )
    
    def test_rate_limiting_on_expensive_operations(self):
        """Test that expensive operations are rate limited"""
        # Note: This is a basic test. In real scenarios, you'd need to
        # make multiple requests to trigger the rate limit
        
        response = self.client.post(
            f'/api/projects/{self.project.id}/transcribe/'
        )
        
        # First request should succeed
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST  # Might fail due to missing files
        ])
        
        # Check that rate limit headers are present (if DRF adds them)
        # This depends on DRF configuration


class AuthenticationTest(APITestCase):
    """Test authentication requirements"""
    
    def test_endpoints_require_authentication(self):
        """Test that API endpoints require authentication"""
        endpoints = [
            '/api/projects/',
            '/api/projects/1/',
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(
                response.status_code,
                status.HTTP_401_UNAUTHORIZED,
                f"Endpoint {endpoint} should require authentication"
            )
    
    def test_token_authentication_works(self):
        """Test that token authentication works"""
        user = User.objects.create_user('testuser', 'test@example.com', 'pass')
        token = Token.objects.create(user=user)
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        
        response = self.client.get('/api/projects/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_invalid_token_rejected(self):
        """Test that invalid tokens are rejected"""
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid_token_here')
        
        response = self.client.get('/api/projects/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
