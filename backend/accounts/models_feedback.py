"""
Feature Feedback & Survey Models

Collects user feedback on features to improve the product.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class FeatureFeedback(models.Model):
    """
    User feedback on specific features
    
    3-question survey:
    1. Did this work as expected?
    2. What do you like?
    3. What could be improved?
    4. Star rating (1-5)
    """
    
    FEATURE_CHOICES = [
        ('ai_duplicate_detection', 'AI Duplicate Detection'),
        ('ai_transcription', 'AI Transcription'),
        ('ai_pdf_comparison', 'AI PDF Comparison'),
        ('manual_transcription', 'Manual Transcription'),
        ('algorithm_detection', 'Algorithm Duplicate Detection'),
        ('pdf_upload', 'PDF Upload'),
        ('audio_assembly', 'Audio Assembly'),
        ('project_management', 'Project Management'),
        ('other', 'Other Feature'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feature_feedback')
    feature = models.CharField(max_length=50, choices=FEATURE_CHOICES)
    
    # Question 1: Did this work as expected?
    worked_as_expected = models.BooleanField(
        help_text="Did the feature work as you expected it to?"
    )
    
    # Question 2: What do you like?
    what_you_like = models.TextField(
        blank=True,
        help_text="What do you like about this feature?"
    )
    
    # Question 3: What could be improved?
    what_to_improve = models.TextField(
        blank=True,
        help_text="What could be improved or added?"
    )
    
    # Question 4: Star rating
    rating = models.IntegerField(
        choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')],
        help_text="How many stars would you rate this feature? (1-5)"
    )
    
    # Metadata
    audio_file_id = models.IntegerField(null=True, blank=True, help_text="Related audio file if applicable")
    user_plan = models.CharField(max_length=50, blank=True, help_text="User's subscription plan at time of feedback")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Admin response
    admin_notes = models.TextField(blank=True, help_text="Internal notes from admin")
    status = models.CharField(
        max_length=20,
        choices=[
            ('new', 'New'),
            ('reviewed', 'Reviewed'),
            ('addressed', 'Addressed'),
            ('implemented', 'Implemented'),
        ],
        default='new'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Feature Feedback'
        verbose_name_plural = 'Feature Feedback'
    
    def __str__(self):
        return f"{self.user.username} - {self.get_feature_display()} - {self.rating} stars"
    
    @property
    def is_positive(self):
        """Feedback is positive if rating >= 4 and worked as expected"""
        return self.rating >= 4 and self.worked_as_expected
    
    @property
    def needs_attention(self):
        """Feedback needs attention if rating <= 2 or didn't work as expected"""
        return self.rating <= 2 or not self.worked_as_expected


class FeatureFeedbackSummary(models.Model):
    """
    Aggregated feedback statistics per feature (updated nightly)
    """
    feature = models.CharField(max_length=50, unique=True)
    
    total_responses = models.IntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    
    rating_5_count = models.IntegerField(default=0)
    rating_4_count = models.IntegerField(default=0)
    rating_3_count = models.IntegerField(default=0)
    rating_2_count = models.IntegerField(default=0)
    rating_1_count = models.IntegerField(default=0)
    
    worked_as_expected_count = models.IntegerField(default=0)
    worked_as_expected_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Feature Feedback Summary'
        verbose_name_plural = 'Feature Feedback Summaries'
    
    def __str__(self):
        return f"{self.feature} - Avg: {self.average_rating} ({self.total_responses} responses)"
    
    @classmethod
    def update_summary(cls, feature_name):
        """Update summary statistics for a specific feature"""
        from django.db.models import Avg, Count, Q
        
        feedback_qs = FeatureFeedback.objects.filter(feature=feature_name)
        
        total = feedback_qs.count()
        if total == 0:
            return
        
        avg_rating = feedback_qs.aggregate(Avg('rating'))['rating__avg'] or 0.0
        
        rating_counts = {
            'rating_5_count': feedback_qs.filter(rating=5).count(),
            'rating_4_count': feedback_qs.filter(rating=4).count(),
            'rating_3_count': feedback_qs.filter(rating=3).count(),
            'rating_2_count': feedback_qs.filter(rating=2).count(),
            'rating_1_count': feedback_qs.filter(rating=1).count(),
        }
        
        worked_count = feedback_qs.filter(worked_as_expected=True).count()
        worked_percentage = (worked_count / total) * 100 if total > 0 else 0
        
        summary, created = cls.objects.update_or_create(
            feature=feature_name,
            defaults={
                'total_responses': total,
                'average_rating': round(avg_rating, 2),
                'worked_as_expected_count': worked_count,
                'worked_as_expected_percentage': round(worked_percentage, 2),
                **rating_counts
            }
        )
        
        return summary
