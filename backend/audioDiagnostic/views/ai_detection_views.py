"""
AI-Powered Duplicate Detection Views

API endpoints for AI-powered duplicate detection, paragraph expansion,
and PDF comparison.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from celery.result import AsyncResult
import logging
import json

from ..models import (
    AudioFile,
    AIDuplicateDetectionResult,
    AIPDFComparisonResult,
    AIProcessingLog
)
from ..serializers import (
    AIDetectionRequestSerializer,
    AIPDFComparisonRequestSerializer,
    AICostEstimateRequestSerializer,
    AIDuplicateDetectionResultSerializer,
    AIPDFComparisonResultSerializer,
    AIProcessingLogSerializer
)
from ..tasks.ai_tasks import (
    ai_detect_duplicates_task,
    ai_compare_pdf_task,
    estimate_ai_cost_task
)
from ..services.ai import CostCalculator

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_detect_duplicates_view(request):
    """
    Start AI-powered duplicate detection for an audio file
    
    POST /api/ai-detection/detect/
    {
        "audio_file_id": 123,
        "min_words": 3,
        "similarity_threshold": 0.85,
        "keep_occurrence": "last",
        "enable_paragraph_expansion": false
    }
    
    Returns:
    {
        "success": true,
        "task_id": "celery-task-id",
        "message": "AI duplicate detection started",
        "estimated_cost": {...}
    }
    """
    # Validate request data
    serializer = AIDetectionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    validated_data = serializer.validated_data
    audio_file_id = validated_data['audio_file_id']
    
    try:
        # Get audio file
        audio_file = get_object_or_404(AudioFile, id=audio_file_id)
        
        # Check permission (user owns the project)
        if audio_file.project.user != request.user:
            return Response(
                {'success': False, 'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if transcription exists
        if not hasattr(audio_file, 'transcription'):
            return Response(
                {'success': False, 'error': 'Audio file must be transcribed first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Estimate cost before starting
        duration = audio_file.duration_seconds or 0
        calculator = CostCalculator()
        cost_estimate = calculator.estimate_cost_for_audio(
            provider='anthropic',
            model='claude-3-5-sonnet-20241022',
            audio_duration_seconds=duration,
            task='duplicate_detection'
        )
        
        # Check user monthly cost limit
        from ..services.ai import DuplicateDetector
        detector = DuplicateDetector()
        if not detector.client.check_user_cost_limit(request.user.id):
            # Get current usage
            from datetime import datetime
            month_key = f"ai_cost_{request.user.id}_{datetime.now().strftime('%Y_%m')}"
            current_usage = cache.get(month_key, 0.0)
            
            return Response({
                'success': False,
                'error': 'Monthly AI cost limit exceeded',
                'current_usage_usd': float(current_usage),
                'limit_usd': 50.0
            }, status=status.HTTP_402_PAYMENT_REQUIRED)
        
        # Start Celery task
        task = ai_detect_duplicates_task.delay(
            audio_file_id=audio_file_id,
            user_id=request.user.id,
            min_words=validated_data['min_words'],
            similarity_threshold=validated_data['similarity_threshold'],
            keep_occurrence=validated_data['keep_occurrence'],
            enable_paragraph_expansion=validated_data['enable_paragraph_expansion']
        )
        
        logger.info(
            f"AI duplicate detection started for audio_file_id={audio_file_id}, "
            f"user={request.user.username}, task_id={task.id}"
        )
        
        return Response({
            'success': True,
            'task_id': task.id,
            'message': 'AI duplicate detection started',
            'audio_file_id': audio_file_id,
            'estimated_cost': cost_estimate,
            'status_url': f'/api/ai-detection/status/{task.id}/'
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logger.error(f"Failed to start AI detection: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_task_status_view(request, task_id):
    """
    Get status of AI detection task
    
    GET /api/ai-detection/status/{task_id}/
    
    Returns:
    {
        "success": true,
        "task_id": "...",
        "state": "PENDING|STARTED|SUCCESS|FAILURE",
        "progress": 0-100,
        "result": {...}  // If completed
    }
    """
    try:
        # Get Celery task result
        task = AsyncResult(task_id)
        
        # Get progress from Redis if available
        r = cache._cache.get_client()  # Get Redis client
        progress_key = f"progress:{task_id}"
        status_key = f"status:{task_id}"
        
        progress = r.get(progress_key)
        progress = int(progress) if progress else 0
        
        status_data = r.get(status_key)
        if status_data:
            try:
                status_info = json.loads(status_data)
            except:
                status_info = {'status': 'processing', 'message': 'Processing...'}
        else:
            status_info = {'status': 'pending', 'message': 'Starting...'}
        
        response_data = {
            'success': True,
            'task_id': task_id,
            'state': task.state,
            'progress': progress,
            'status': status_info.get('status', 'pending'),
            'message': status_info.get('message', ''),
        }
        
        # If task is complete, include result
        if task.state == 'SUCCESS':
            response_data['result'] = task.result
            response_data['progress'] = 100
            
            # Get the detection result from database if available
            result_id = task.result.get('result_id') if isinstance(task.result, dict) else None
            if result_id:
                try:
                    detection_result = AIDuplicateDetectionResult.objects.get(id=result_id)
                    serializer = AIDuplicateDetectionResultSerializer(detection_result)
                    response_data['detection_result'] = serializer.data
                except AIDuplicateDetectionResult.DoesNotExist:
                    pass
        
        elif task.state == 'FAILURE':
            response_data['error'] = str(task.info)
            response_data['progress'] = 0
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to get task status: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_compare_pdf_view(request):
    """
    Start AI-powered PDF comparison for an audio file
    
    POST /api/ai-detection/compare-pdf/
    {
        "audio_file_id": 123
    }
    
    Returns:
    {
        "success": true,
        "task_id": "celery-task-id",
        "message": "AI PDF comparison started"
    }
    """
    # Validate request data
    serializer = AIPDFComparisonRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    validated_data = serializer.validated_data
    audio_file_id = validated_data['audio_file_id']
    
    try:
        # Get audio file
        audio_file = get_object_or_404(AudioFile, id=audio_file_id)
        
        # Check permission
        if audio_file.project.user != request.user:
            return Response(
                {'success': False, 'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check user cost limit
        from ..services.ai import DuplicateDetector
        detector = DuplicateDetector()
        if not detector.client.check_user_cost_limit(request.user.id):
            return Response({
                'success': False,
                'error': 'Monthly AI cost limit exceeded'
            }, status=status.HTTP_402_PAYMENT_REQUIRED)
        
        # Start Celery task
        task = ai_compare_pdf_task.delay(
            audio_file_id=audio_file_id,
            user_id=request.user.id
        )
        
        logger.info(
            f"AI PDF comparison started for audio_file_id={audio_file_id}, "
            f"user={request.user.username}, task_id={task.id}"
        )
        
        return Response({
            'success': True,
            'task_id': task.id,
            'message': 'AI PDF comparison started',
            'audio_file_id': audio_file_id,
            'status_url': f'/api/ai-detection/status/{task.id}/'
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logger.error(f"Failed to start AI PDF comparison: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_estimate_cost_view(request):
    """
    Estimate cost for AI processing
    
    POST /api/ai-detection/estimate-cost/
    {
        "audio_duration_seconds": 3600,
        "task_type": "duplicate_detection"
    }
    
    Returns cost estimate
    """
    serializer = AICostEstimateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    validated_data = serializer.validated_data
    
    try:
        # Calculate estimate
        task = estimate_ai_cost_task.delay(
            audio_duration_seconds=validated_data['audio_duration_seconds'],
            task_type=validated_data['task_type']
        )
        
        # Wait for quick result (cost estimation is fast)
        estimate = task.get(timeout=5)
        
        return Response({
            'success': True,
            'estimate': estimate
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to estimate cost: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_detection_results_view(request, audio_file_id):
    """
    Get AI detection results for an audio file
    
    GET /api/ai-detection/results/{audio_file_id}/
    
    Returns list of detection results (newest first)
    """
    try:
        # Get audio file
        audio_file = get_object_or_404(AudioFile, id=audio_file_id)
        
        # Check permission
        if audio_file.project.user != request.user:
            return Response(
                {'success': False, 'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get all detection results for this audio file
        results = AIDuplicateDetectionResult.objects.filter(
            audio_file=audio_file
        ).order_by('-processing_date')
        
        serializer = AIDuplicateDetectionResultSerializer(results, many=True)
        
        return Response({
            'success': True,
            'count': results.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to get detection results: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_user_cost_view(request):
    """
    Get user's AI cost usage for current month
    
    GET /api/ai-detection/user-cost/
    
    Returns:
    {
        "success": true,
        "current_month_cost": 12.50,
        "limit": 50.00,
        "usage_percentage": 25.0,
        "remaining": 37.50
    }
    """
    try:
        from datetime import datetime
        
        # Get current month cost from cache
        month_key = f"ai_cost_{request.user.id}_{datetime.now().strftime('%Y_%m')}"
        current_cost = cache.get(month_key, 0.0)
        
        # Get limit from settings
        from django.conf import settings
        limit = getattr(settings, 'AI_COST_LIMIT_PER_USER_PER_MONTH', 50.0)
        
        # Calculate usage percentage
        usage_percentage = (current_cost / limit * 100) if limit > 0 else 0
        remaining = max(0, limit - current_cost)
        
        # Get detailed logs for this month
        logs = AIProcessingLog.objects.filter(
            user=request.user,
            timestamp__year=datetime.now().year,
            timestamp__month=datetime.now().month,
            status='success'
        ).order_by('-timestamp')
        
        log_serializer = AIProcessingLogSerializer(logs[:10], many=True)  # Last 10 transactions
        
        return Response({
            'success': True,
            'current_month_cost': float(current_cost),
            'limit': float(limit),
            'usage_percentage': float(usage_percentage),
            'remaining': float(remaining),
            'month': datetime.now().strftime('%B %Y'),
            'recent_transactions': log_serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to get user cost: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
