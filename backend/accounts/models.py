from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import stripe
from django.conf import settings


class SubscriptionPlan(models.Model):
    """Define available subscription plans"""
    PLAN_CHOICES = [
        ('free', 'Free Trial'),
        ('basic', 'Basic Plan'),
        ('pro', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]
    
    name = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField()
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Usage limits
    max_projects_per_month = models.IntegerField(default=0)  # 0 = unlimited
    max_audio_duration_minutes = models.IntegerField(default=0)  # 0 = unlimited
    max_file_size_mb = models.IntegerField(default=100)
    max_storage_gb = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    
    # Features
    priority_processing = models.BooleanField(default=False)
    api_access = models.BooleanField(default=False)
    custom_branding = models.BooleanField(default=False)
    
    stripe_price_id_monthly = models.CharField(max_length=100, blank=True, null=True)
    stripe_price_id_yearly = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.display_name
    
    class Meta:
        ordering = ['price_monthly']


class UserSubscription(models.Model):
    """User's current subscription status"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('trialing', 'Free Trial'),
        ('incomplete', 'Incomplete'),
    ]
    
    BILLING_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trialing')
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CHOICES, default='monthly')
    
    # Stripe integration
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Subscription dates
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.plan.display_name} ({self.status})"
    
    @property
    def is_active(self):
        """Check if subscription is currently active"""
        return self.status in ['active', 'trialing']
    
    @property
    def days_until_renewal(self):
        """Days until next billing cycle"""
        if self.current_period_end:
            delta = self.current_period_end - timezone.now()
            return delta.days
        return None
    
    @property
    def is_trial(self):
        """Check if user is in trial period"""
        return self.status == 'trialing'


class UsageTracking(models.Model):
    """Track user usage for billing and limits"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='usage_records')
    
    # Usage metrics
    projects_created = models.IntegerField(default=0)
    audio_minutes_processed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    storage_used_mb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    api_calls_made = models.IntegerField(default=0)
    
    # Period tracking
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} usage for {self.period_start.strftime('%Y-%m')}"
    
    class Meta:
        unique_together = ['user', 'period_start']
        ordering = ['-period_start']


class BillingHistory(models.Model):
    """Track billing events and payments"""
    TRANSACTION_TYPES = [
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('failed', 'Failed Payment'),
        ('credit', 'Credit'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='billing_history')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='GBP')
    
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_invoice_id = models.CharField(max_length=100, blank=True, null=True)
    
    description = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} ${self.amount}"
    
    class Meta:
        ordering = ['-created_at']


class UserProfile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Company information
    company_name = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Preferences
    email_notifications = models.BooleanField(default=True)
    marketing_emails = models.BooleanField(default=False)
    
    # Analytics
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    signup_source = models.CharField(max_length=100, blank=True)  # Track where users came from
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} profile"


# Signal to create profile and free trial when user registers
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_subscription_and_profile(sender, instance, created, **kwargs):
    """Create subscription and profile when new user registers"""
    if created:
        # Create user profile
        UserProfile.objects.create(user=instance)
        
        # Create free trial subscription
        free_plan, created = SubscriptionPlan.objects.get_or_create(
            name='free',
            defaults={
                'display_name': 'Free Trial',
                'description': 'Try our service free for 7 days',
                'price_monthly': 0.00,
                'max_projects_per_month': 3,
                'max_audio_duration_minutes': 60,
                'max_file_size_mb': 50,
                'max_storage_gb': 0.5,
            }
        )
        
        # Set trial period (7 days)
        trial_end = timezone.now() + timezone.timedelta(days=7)
        
        UserSubscription.objects.create(
            user=instance,
            plan=free_plan,
            status='trialing',
            trial_end=trial_end
        )