"""
API Views for Feature Feedback
"""

from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models_feedback import FeatureFeedback, FeatureFeedbackSummary
from .serializers_feedback import (
    FeatureFeedbackSerializer,
    FeatureFeedbackSummarySerializer,
    QuickFeedbackSerializer
)
import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def submit_feedback(request):
    """
    Submit feature feedback
    
    POST /api/feedback/submit/
    {
        "feature": "ai_duplicate_detection",
        "worked_as_expected": true,
        "what_you_like": "Very accurate and fast!",
        "what_to_improve": "Could show more details about confidence scores",
        "rating": 5,
        "audio_file_id": 123  // optional
    }
    
    Returns:
    {
        "success": true,
        "message": "Thank you for your feedback!",
        "feedback_id": 456
    }
    """
    serializer = FeatureFeedbackSerializer(data=request.data, context={'request': request})
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    feedback = serializer.save()
    
    logger.info(
        f"Feedback submitted by {request.user.username} for {feedback.feature} "
        f"- Rating: {feedback.rating}/5, Worked as expected: {feedback.worked_as_expected}"
    )
    
    return Response({
        'success': True,
        'message': 'Thank you for your feedback! We appreciate you helping us improve.',
        'feedback_id': feedback.id,
        'feature': feedback.feature,
        'rating': feedback.rating
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_feedback_history(request):
    """
    Get user's feedback history
    
    GET /api/feedback/my-feedback/
    
    Returns list of all feedback submitted by the user
    """
    feedback_qs = FeatureFeedback.objects.filter(user=request.user)
    serializer = FeatureFeedbackSerializer(feedback_qs, many=True)
    
    return Response({
        'success': True,
        'count': feedback_qs.count(),
        'feedback': serializer.data
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def feature_summary(request, feature_name):
    """
    Get aggregated feedback summary for a feature
    
    GET /api/feedback/summary/ai_duplicate_detection/
    
    Returns statistics about user feedback for this feature
    """
    try:
        summary = FeatureFeedbackSummary.objects.get(feature=feature_name)
        serializer = FeatureFeedbackSummarySerializer(summary)
        
        return Response({
            'success': True,
            'summary': serializer.data
        })
    except FeatureFeedbackSummary.DoesNotExist:
        return Response({
            'success': True,
            'summary': {
                'feature': feature_name,
                'total_responses': 0,
                'average_rating': 0.0,
                'message': 'No feedback yet for this feature'
            }
        })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def all_feature_summaries(request):
    """
    Get feedback summaries for all features
    
    GET /api/feedback/summaries/
    
    Returns statistics for all features
    """
    summaries = FeatureFeedbackSummary.objects.all()
    serializer = FeatureFeedbackSummarySerializer(summaries, many=True)
    
    return Response({
        'success': True,
        'count': summaries.count(),
        'summaries': serializer.data
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def quick_feedback(request):
    """
    Quick feedback submission (simplified API)
    
    POST /api/feedback/quick/
    {
        "feature": "ai_duplicate_detection",
        "worked_as_expected": true,
        "what_you_like": "Fast and accurate",
        "rating": 5
    }
    """
    serializer = QuickFeedbackSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create feedback using validated data
    feedback_data = serializer.validated_data
    feedback_serializer = FeatureFeedbackSerializer(
        data=feedback_data,
        context={'request': request}
    )
    
    if feedback_serializer.is_valid():
        feedback = feedback_serializer.save()
        
        return Response({
            'success': True,
            'message': 'Thanks for the quick feedback!',
            'feedback_id': feedback.id
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'success': False,
        'errors': feedback_serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


class FeatureFeedbackListView(generics.ListAPIView):
    """
    List all feedback (admin only)
    
    GET /api/feedback/all/
    
    Query params:
    - feature: Filter by feature name
    - rating: Filter by rating
    - needs_attention: true/false
    """
    serializer_class = FeatureFeedbackSerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_queryset(self):
        queryset = FeatureFeedback.objects.all()
        
        # Filter by feature
        feature = self.request.query_params.get('feature', None)
        if feature:
            queryset = queryset.filter(feature=feature)
        
        # Filter by rating
        rating = self.request.query_params.get('rating', None)
        if rating:
            queryset = queryset.filter(rating=int(rating))
        
        # Filter by needs attention
        needs_attention = self.request.query_params.get('needs_attention', None)
        if needs_attention == 'true':
            queryset = queryset.filter(rating__lte=2) | queryset.filter(worked_as_expected=False)
        
        return queryset.select_related('user')
