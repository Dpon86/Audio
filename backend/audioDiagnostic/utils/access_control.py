"""
Access Control Utilities for Subscription-Based Features

Provides decorators and helper functions to gate features based on
user subscription plans and limits.
"""

from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def require_ai_feature(feature_name):
    """
    Decorator to check if user's subscription allows a specific AI feature
    
    Args:
        feature_name: Name of the feature flag on SubscriptionPlan model
                     e.g., 'ai_duplicate_detection', 'ai_transcription', 'ai_pdf_comparison'
    
    Usage:
        @api_view(['POST'])
        @permission_classes([IsAuthenticated])
        @require_ai_feature('ai_duplicate_detection')
        def my_ai_view(request):
            # This only executes if user has access
            ...
    
    Returns:
        402 Payment Required if:
        - User has no subscription
        - Subscription is not active
        - Plan doesn't include the feature
        
        Otherwise proceeds with the view function
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            
            # Check if user has a subscription
            if not hasattr(user, 'subscription'):
                logger.warning(f"User {user.username} has no subscription")
                return Response({
                    'success': False,
                    'error': 'No active subscription found',
                    'upgrade_required': True,
                    'recommended_plan': 'basic',
                    'message': 'Please subscribe to a plan to access AI features'
                }, status=status.HTTP_402_PAYMENT_REQUIRED)
            
            subscription = user.subscription
            plan = subscription.plan
            
            # Check if subscription is active (not expired, not canceled)
            if not subscription.is_active:
                logger.warning(
                    f"User {user.username} subscription is {subscription.status}, "
                    f"not active"
                )
                
                # Provide helpful error message based on status
                if subscription.status == 'trialing':
                    message = 'Your free trial has expired. Please upgrade to continue.'
                elif subscription.status == 'canceled':
                    message = 'Your subscription has been canceled. Please reactivate to continue.'
                elif subscription.status == 'past_due':
                    message = 'Your payment is past due. Please update your payment method.'
                else:
                    message = f'Subscription is {subscription.status}. Please contact support.'
                
                return Response({
                    'success': False,
                    'error': message,
                    'subscription_status': subscription.status,
                    'current_plan': plan.display_name,
                    'upgrade_required': True
                }, status=status.HTTP_402_PAYMENT_REQUIRED)
            
            # Check if plan includes this feature
            has_feature = getattr(plan, feature_name, False)
            
            if not has_feature:
                logger.info(
                    f"User {user.username} plan '{plan.name}' doesn't include {feature_name}"
                )
                
                # Recommend appropriate plan based on feature
                if feature_name == 'ai_duplicate_detection':
                    recommended_plan = 'basic'
                    recommended_display = 'Basic Plan ($19.99/month)'
                elif feature_name == 'ai_transcription':
                    recommended_plan = 'pro'
                    recommended_display = 'Professional Plan ($49.99/month)'
                elif feature_name == 'ai_pdf_comparison':
                    recommended_plan = 'pro'
                    recommended_display = 'Professional Plan ($49.99/month)'
                else:
                    recommended_plan = 'pro'
                    recommended_display = 'Professional Plan'
                
                return Response({
                    'success': False,
                    'error': f'Your {plan.display_name} does not include {feature_name.replace("_", " ")}',
                    'current_plan': plan.display_name,
                    'upgrade_required': True,
                    'recommended_plan': recommended_plan,
                    'recommended_plan_display': recommended_display,
                    'feature': feature_name
                }, status=status.HTTP_402_PAYMENT_REQUIRED)
            
            # All checks passed - user has access to this feature
            logger.debug(f"User {user.username} has access to {feature_name}")
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def check_ai_cost_limit(user, estimated_cost):
    """
    Check if user has enough AI budget remaining for this month
    
    Args:
        user: Django User object
        estimated_cost: Estimated cost in USD for the AI operation
    
    Returns:
        tuple: (allowed, remaining_budget, message)
            - allowed (bool): Whether the operation is allowed
            - remaining_budget (float): Remaining budget in USD
            - message (str): Human-readable message
    
    Example:
        allowed, remaining, msg = check_ai_cost_limit(request.user, 0.15)
        if not allowed:
            return Response({'error': msg}, status=402)
    """
    try:
        subscription = user.subscription
        plan = subscription.plan
        
        # Get monthly AI budget limit from plan
        monthly_limit = float(plan.ai_monthly_cost_limit)
        
        if monthly_limit == 0:
            return False, 0.0, "Your plan does not include AI API access"
        
        # Get current month's usage from cache
        current_month = datetime.now().strftime('%Y_%m')
        cache_key = f"ai_cost_{user.id}_{current_month}"
        current_usage = float(cache.get(cache_key, 0.0))
        
        # Calculate remaining budget
        remaining_budget = monthly_limit - current_usage
        
        # Check if this request would exceed the limit
        if estimated_cost > remaining_budget:
            overage = estimated_cost - remaining_budget
            return (
                False,
                remaining_budget,
                f"This operation would cost ${estimated_cost:.2f} but you only have "
                f"${remaining_budget:.2f} remaining in your AI budget this month. "
                f"(${overage:.2f} over limit)"
            )
        
        # Operation is within budget
        return (
            True,
            remaining_budget,
            f"OK - ${remaining_budget:.2f} remaining after this operation"
        )
        
    except AttributeError as e:
        logger.error(f"Error checking AI cost limit for user {user.username}: {e}")
        return False, 0.0, "Unable to verify AI budget - subscription not found"
    except Exception as e:
        logger.error(f"Unexpected error in check_ai_cost_limit: {e}", exc_info=True)
        return False, 0.0, f"Error checking AI budget: {str(e)}"


def track_ai_cost(user, actual_cost):
    """
    Track actual AI API cost for a user
    
    Args:
        user: Django User object
        actual_cost: Actual cost in USD that was charged
    
    Updates the user's monthly AI spending in cache
    """
    try:
        current_month = datetime.now().strftime('%Y_%m')
        cache_key = f"ai_cost_{user.id}_{current_month}"
        
        # Get current total
        current_total = float(cache.get(cache_key, 0.0))
        
        # Add new cost
        new_total = current_total + actual_cost
        
        # Store with 32-day expiry (covers longest month + 1 day)
        cache.set(cache_key, new_total, timeout=60*60*24*32)
        
        logger.info(
            f"Tracked AI cost for {user.username}: "
            f"${actual_cost:.4f} (total this month: ${new_total:.4f})"
        )
        
        return new_total
        
    except Exception as e:
        logger.error(f"Failed to track AI cost for user_id={user.id}: {e}", exc_info=True)
        return 0.0


def get_user_ai_usage(user):
    """
    Get user's AI usage statistics for current month
    
    Args:
        user: Django User object
    
    Returns:
        dict: {
            'current_usage': float,
            'monthly_limit': float,
            'remaining': float,
            'usage_percentage': float,
            'month': str
        }
    """
    try:
        subscription = user.subscription
        plan = subscription.plan
        
        monthly_limit = float(plan.ai_monthly_cost_limit)
        current_month = datetime.now().strftime('%Y_%m')
        cache_key = f"ai_cost_{user.id}_{current_month}"
        
        current_usage = float(cache.get(cache_key, 0.0))
        remaining = max(0, monthly_limit - current_usage)
        usage_percentage = (current_usage / monthly_limit * 100) if monthly_limit > 0 else 0
        
        return {
            'current_usage': round(current_usage, 2),
            'monthly_limit': round(monthly_limit, 2),
            'remaining': round(remaining, 2),
            'usage_percentage': round(usage_percentage, 1),
            'month': datetime.now().strftime('%B %Y'),
            'plan_name': plan.display_name
        }
        
    except Exception as e:
        logger.error(f"Error getting AI usage for user_id={user.id}: {e}")
        return {
            'current_usage': 0.0,
            'monthly_limit': 0.0,
            'remaining': 0.0,
            'usage_percentage': 0.0,
            'month': datetime.now().strftime('%B %Y'),
            'plan_name': 'Unknown'
        }


def require_subscription_tier(min_tier='basic'):
    """
    Decorator to require a minimum subscription tier
    
    Args:
        min_tier: Minimum required tier ('free', 'basic', 'pro', 'enterprise')
    
    Usage:
        @require_subscription_tier('pro')
        def premium_only_view(request):
            ...
    
    Tier hierarchy: free < basic < pro < enterprise
    """
    tier_levels = {
        'free': 0,
        'basic': 1,
        'pro': 2,
        'enterprise': 3
    }
    
    required_level = tier_levels.get(min_tier, 0)
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user
            
            if not hasattr(user, 'subscription'):
                return Response({
                    'success': False,
                    'error': 'No subscription found',
                    'required_tier': min_tier,
                    'upgrade_required': True
                }, status=status.HTTP_402_PAYMENT_REQUIRED)
            
            subscription = user.subscription
            plan = subscription.plan
            
            # Check tier level
            user_level = tier_levels.get(plan.name, 0)
            
            if user_level < required_level:
                return Response({
                    'success': False,
                    'error': f'This feature requires {min_tier} plan or higher',
                    'current_plan': plan.display_name,
                    'required_tier': min_tier,
                    'upgrade_required': True
                }, status=status.HTTP_402_PAYMENT_REQUIRED)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def check_usage_limit(user, metric, increment=1):
    """
    Check if user can perform an action based on usage limits
    
    Args:
        user: Django User object
        metric: Type of limit ('projects', 'audio_minutes', 'storage_mb')
        increment: How much to add (default: 1)
    
    Returns:
        tuple: (allowed, current, limit, message)
    """
    try:
        subscription = user.subscription
        plan = subscription.plan
        
        # Get current month usage
        from accounts.models import UsageTracking
        from django.utils import timezone
        
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        usage, created = UsageTracking.objects.get_or_create(
            user=user,
            period_start=month_start,
            defaults={
                'period_end': month_start.replace(month=month_start.month + 1) if month_start.month < 12 
                             else month_start.replace(year=month_start.year + 1, month=1)
            }
        )
        
        # Check limit based on metric
        if metric == 'projects':
            current = usage.projects_created
            limit = plan.max_projects_per_month
            field_name = 'projects_created'
            
        elif metric == 'audio_minutes':
            current = float(usage.audio_minutes_processed)
            limit = plan.max_audio_duration_minutes
            field_name = 'audio_minutes_processed'
            
        elif metric == 'storage_mb':
            current = float(usage.storage_used_mb)
            limit = float(plan.max_storage_gb * 1024)  # Convert GB to MB
            field_name = 'storage_used_mb'
            
        else:
            return False, 0, 0, f"Unknown metric: {metric}"
        
        # 0 = unlimited
        if limit == 0:
            return True, current, "unlimited", "OK"
        
        # Check if increment would exceed limit
        if current + increment > limit:
            overage = (current + increment) - limit
            return (
                False,
                current,
                limit,
                f"Adding {increment} would exceed your {metric} limit ({current}/{limit} used)"
            )
        
        return True, current, limit, "OK"
        
    except Exception as e:
        logger.error(f"Error checking usage limit: {e}", exc_info=True)
        return False, 0, 0, str(e)
