"""
Client Storage APIs
Handles saving and loading client-side transcriptions and duplicate analyses
for cross-device persistence.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from accounts.authentication import ExpiringTokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q

from ..models import AudioProject, AudioFile, ClientTranscription, DuplicateAnalysis
from ..serializers import ClientTranscriptionSerializer, DuplicateAnalysisSerializer


class ClientTranscriptionListCreateView(APIView):
    """
    GET: List all client transcriptions for a project
    POST: Save a new client transcription or update existing
    """
    authentication_classes = [SessionAuthentication, ExpiringTokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id):
        """Get all client transcriptions for a project"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Optional filter by audio_file
        audio_file_id = request.query_params.get('audio_file')
        filename = request.query_params.get('filename')
        
        transcriptions = ClientTranscription.objects.filter(project=project)
        
        if audio_file_id:
            transcriptions = transcriptions.filter(audio_file_id=audio_file_id)
        
        if filename:
            transcriptions = transcriptions.filter(filename=filename)
        
        transcriptions = transcriptions.order_by('-created_at')
        
        serializer = ClientTranscriptionSerializer(transcriptions, many=True)
        
        return Response({
            'success': True,
            'transcriptions': serializer.data,
            'total_count': transcriptions.count()
        })
    
    def post(self, request, project_id):
        """Save or update client transcription"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Check if transcription already exists for this file
        filename = request.data.get('filename')
        audio_file_id = request.data.get('audio_file')
        
        existing = None
        if audio_file_id:
            # Try to find by audio_file FK
            existing = ClientTranscription.objects.filter(
                project=project,
                audio_file_id=audio_file_id
            ).first()
        elif filename:
            # Try to find by filename
            existing = ClientTranscription.objects.filter(
                project=project,
                filename=filename
            ).first()
        
        # Prepare data
        data = {
            'project': project.id,
            **request.data
        }
        
        if existing:
            # Update existing transcription
            serializer = ClientTranscriptionSerializer(existing, data=data, partial=True)
        else:
            # Create new transcription
            serializer = ClientTranscriptionSerializer(data=data)
        
        if serializer.is_valid():
            transcription = serializer.save()
            
            return Response({
                'success': True,
                'message': 'Transcription saved successfully' if not existing else 'Transcription updated successfully',
                'transcription': ClientTranscriptionSerializer(transcription).data,
                'updated': existing is not None
            }, status=status.HTTP_201_CREATED if not existing else status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class ClientTranscriptionDetailView(APIView):
    """
    GET: Retrieve a specific client transcription
    PUT/PATCH: Update a client transcription
    DELETE: Delete a client transcription
    """
    authentication_classes = [SessionAuthentication, ExpiringTokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, transcription_id):
        """Get specific transcription"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        transcription = get_object_or_404(ClientTranscription, id=transcription_id, project=project)
        
        serializer = ClientTranscriptionSerializer(transcription)
        
        return Response({
            'success': True,
            'transcription': serializer.data
        })
    
    def put(self, request, project_id, transcription_id):
        """Update transcription (full update)"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        transcription = get_object_or_404(ClientTranscription, id=transcription_id, project=project)
        
        data = {
            'project': project.id,
            **request.data
        }
        
        serializer = ClientTranscriptionSerializer(transcription, data=data)
        
        if serializer.is_valid():
            serializer.save()
            
            return Response({
                'success': True,
                'message': 'Transcription updated successfully',
                'transcription': serializer.data
            })
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, project_id, transcription_id):
        """Update transcription (partial update)"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        transcription = get_object_or_404(ClientTranscription, id=transcription_id, project=project)
        
        serializer = ClientTranscriptionSerializer(transcription, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            
            return Response({
                'success': True,
                'message': 'Transcription updated successfully',
                'transcription': serializer.data
            })
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, project_id, transcription_id):
        """Delete transcription"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        transcription = get_object_or_404(ClientTranscription, id=transcription_id, project=project)
        
        filename = transcription.filename
        transcription.delete()
        
        return Response({
            'success': True,
            'message': f'Transcription for {filename} deleted successfully'
        })


class DuplicateAnalysisListCreateView(APIView):
    """
    GET: List all duplicate analyses for a project
    POST: Save a new duplicate analysis or update existing
    """
    authentication_classes = [SessionAuthentication, ExpiringTokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id):
        """Get all duplicate analyses for a project"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Optional filter by audio_file
        audio_file_id = request.query_params.get('audio_file')
        filename = request.query_params.get('filename')
        
        analyses = DuplicateAnalysis.objects.filter(project=project)
        
        if audio_file_id:
            analyses = analyses.filter(audio_file_id=audio_file_id)
        
        if filename:
            analyses = analyses.filter(filename=filename)
        
        analyses = analyses.order_by('-created_at')
        
        serializer = DuplicateAnalysisSerializer(analyses, many=True)
        
        return Response({
            'success': True,
            'analyses': serializer.data,
            'total_count': analyses.count()
        })
    
    def post(self, request, project_id):
        """Save or update duplicate analysis"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        
        # Check if analysis already exists for this file
        filename = request.data.get('filename')
        audio_file_id = request.data.get('audio_file')
        
        existing = None
        if audio_file_id:
            # Try to find by audio_file FK
            existing = DuplicateAnalysis.objects.filter(
                project=project,
                audio_file_id=audio_file_id
            ).first()
        elif filename:
            # Try to find by filename
            existing = DuplicateAnalysis.objects.filter(
                project=project,
                filename=filename
            ).first()
        
        # Prepare data
        data = {
            'project': project.id,
            **request.data
        }
        
        if existing:
            # Update existing analysis
            serializer = DuplicateAnalysisSerializer(existing, data=data, partial=True)
        else:
            # Create new analysis
            serializer = DuplicateAnalysisSerializer(data=data)
        
        if serializer.is_valid():
            analysis = serializer.save()
            
            return Response({
                'success': True,
                'message': 'Duplicate analysis saved successfully' if not existing else 'Duplicate analysis updated successfully',
                'analysis': DuplicateAnalysisSerializer(analysis).data,
                'updated': existing is not None
            }, status=status.HTTP_201_CREATED if not existing else status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class DuplicateAnalysisDetailView(APIView):
    """
    GET: Retrieve a specific duplicate analysis
    PUT/PATCH: Update a duplicate analysis
    DELETE: Delete a duplicate analysis
    """
    authentication_classes = [SessionAuthentication, ExpiringTokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id, analysis_id):
        """Get specific duplicate analysis"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        analysis = get_object_or_404(DuplicateAnalysis, id=analysis_id, project=project)
        
        serializer = DuplicateAnalysisSerializer(analysis)
        
        return Response({
            'success': True,
            'analysis': serializer.data
        })
    
    def put(self, request, project_id, analysis_id):
        """Update analysis (full update)"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        analysis = get_object_or_404(DuplicateAnalysis, id=analysis_id, project=project)
        
        data = {
            'project': project.id,
            **request.data
        }
        
        serializer = DuplicateAnalysisSerializer(analysis, data=data)
        
        if serializer.is_valid():
            serializer.save()
            
            return Response({
                'success': True,
                'message': 'Duplicate analysis updated successfully',
                'analysis': serializer.data
            })
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, project_id, analysis_id):
        """Update analysis (partial update)"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        analysis = get_object_or_404(DuplicateAnalysis, id=analysis_id, project=project)
        
        serializer = DuplicateAnalysisSerializer(analysis, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            
            return Response({
                'success': True,
                'message': 'Duplicate analysis updated successfully',
                'analysis': serializer.data
            })
        
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, project_id, analysis_id):
        """Delete duplicate analysis"""
        project = get_object_or_404(AudioProject, id=project_id, user=request.user)
        analysis = get_object_or_404(DuplicateAnalysis, id=analysis_id, project=project)
        
        filename = analysis.filename
        analysis.delete()
        
        return Response({
            'success': True,
            'message': f'Duplicate analysis for {filename} deleted successfully'
        })
