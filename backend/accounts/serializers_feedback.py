"""
Serializers for Feature Feedback
"""

from rest_framework import serializers
from .models_feedback import FeatureFeedback, FeatureFeedbackSummary


class FeatureFeedbackSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and viewing feature feedback
    """
    user_username = serializers.CharField(source='user.username', read_only=True)
    feature_display = serializers.CharField(source='get_feature_display', read_only=True)
    is_positive = serializers.BooleanField(read_only=True)
    needs_attention = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = FeatureFeedback
        fields = (
            'id', 'user', 'user_username', 'feature', 'feature_display',
            'worked_as_expected', 'what_you_like', 'what_to_improve', 'rating',
            'audio_file_id', 'user_plan', 'created_at', 'updated_at',
            'is_positive', 'needs_attention', 'status'
        )
        read_only_fields = ('id', 'user', 'created_at', 'updated_at', 'status')
    
    def validate_rating(self, value):
        """Ensure rating is between 1 and 5"""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5 stars")
        return value
    
    def create(self, validated_data):
        """Create feedback and auto-populate user_plan"""
        user = self.context['request'].user
        
        # Auto-populate user's current plan
        if hasattr(user, 'subscription'):
            validated_data['user_plan'] = user.subscription.plan.name
        
        validated_data['user'] = user
        
        feedback = super().create(validated_data)
        
        # Update summary statistics
        FeatureFeedbackSummary.update_summary(feedback.feature)
        
        return feedback


class FeatureFeedbackSummarySerializer(serializers.ModelSerializer):
    """
    Serializer for feature feedback summaries
    """
    class Meta:
        model = FeatureFeedbackSummary
        fields = (
            'feature', 'total_responses', 'average_rating',
            'rating_5_count', 'rating_4_count', 'rating_3_count',
            'rating_2_count', 'rating_1_count',
            'worked_as_expected_count', 'worked_as_expected_percentage',
            'last_updated'
        )
        read_only_fields = '__all__'


class QuickFeedbackSerializer(serializers.Serializer):
    """
    Quick feedback submission (simplified)
    """
    feature = serializers.ChoiceField(choices=FeatureFeedback.FEATURE_CHOICES)
    worked_as_expected = serializers.BooleanField()
    what_you_like = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    what_to_improve = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    audio_file_id = serializers.IntegerField(required=False, allow_null=True)
