from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
import stripe
import os
from datetime import timedelta

from .models import SubscriptionPlan, UserSubscription, UsageTracking, BillingHistory, UserProfile
from .serializers import (
    UserRegistrationSerializer, UserProfileSerializer, 
    SubscriptionPlanSerializer, UserSubscriptionSerializer,
    UsageTrackingSerializer, BillingHistorySerializer
)

# Configure Stripe
stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', os.getenv('STRIPE_SECRET_KEY'))


class UserRegistrationView(generics.CreateAPIView):
    """
    Register new user with automatic free trial
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create user
        user = serializer.save()
        
        # Create Stripe customer
        try:
            stripe_customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip() or user.username,
                metadata={'user_id': user.id}
            )
            
            # Update subscription with Stripe customer ID
            subscription = user.subscription
            subscription.stripe_customer_id = stripe_customer.id
            subscription.save()
            
        except Exception as e:
            # Log error but don't fail registration
            print(f"Stripe customer creation failed: {e}")
        
        # Generate auth token
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'token': token.key,
            'subscription': UserSubscriptionSerializer(user.subscription).data,
            'message': 'Registration successful! Your 7-day free trial has started.'
        }, status=status.HTTP_201_CREATED)


class CustomAuthToken(ObtainAuthToken):
    """
    Custom login view that returns user info and subscription
    """
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'subscription': UserSubscriptionSerializer(user.subscription).data
        })


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Get and update user profile
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class SubscriptionPlansView(generics.ListAPIView):
    """
    List available subscription plans
    """
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.AllowAny]


class UserSubscriptionView(generics.RetrieveAPIView):
    """
    Get current user subscription details
    """
    serializer_class = UserSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        subscription, created = UserSubscription.objects.get_or_create(
            user=self.request.user,
            defaults={
                'plan': SubscriptionPlan.objects.get(name='free'),
                'status': 'trialing',
                'trial_end': timezone.now() + timedelta(days=7)
            }
        )
        return subscription


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_checkout_session(request):
    """
    Create Stripe Checkout session for subscription
    """
    try:
        plan_id = request.data.get('plan_id')
        billing_cycle = request.data.get('billing_cycle', 'monthly')  # monthly or yearly
        
        plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
        
        # Get the appropriate Stripe price ID
        if billing_cycle == 'yearly' and plan.stripe_price_id_yearly:
            price_id = plan.stripe_price_id_yearly
        else:
            price_id = plan.stripe_price_id_monthly
        
        if not price_id:
            return Response({
                'error': 'Stripe price not configured for this plan'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create Stripe customer
        user_subscription = request.user.subscription
        if not user_subscription.stripe_customer_id:
            stripe_customer = stripe.Customer.create(
                email=request.user.email,
                name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                metadata={'user_id': request.user.id}
            )
            user_subscription.stripe_customer_id = stripe_customer.id
            user_subscription.save()
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=user_subscription.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f"{request.build_absolute_uri('/dashboard')}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=request.build_absolute_uri('/pricing'),
            metadata={
                'user_id': request.user.id,
                'plan_id': plan.id,
                'billing_cycle': billing_cycle,
            }
        )
        
        return Response({
            'checkout_url': checkout_session.url,
            'session_id': checkout_session.id
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def cancel_subscription(request):
    """
    Cancel user's current subscription
    """
    try:
        user_subscription = request.user.subscription
        
        if user_subscription.stripe_subscription_id:
            # Cancel in Stripe
            stripe.Subscription.modify(
                user_subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            # Update local record
            user_subscription.status = 'canceled'
            user_subscription.save()
            
            return Response({
                'message': 'Subscription cancelled successfully. You can continue using the service until your current period ends.',
                'subscription': UserSubscriptionSerializer(user_subscription).data
            })
        else:
            return Response({
                'error': 'No active subscription to cancel'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


class UsageTrackingView(generics.ListAPIView):
    """
    Get user's usage history
    """
    serializer_class = UsageTrackingSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return UsageTracking.objects.filter(user=self.request.user)


class BillingHistoryView(generics.ListAPIView):
    """
    Get user's billing history
    """
    serializer_class = BillingHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return BillingHistory.objects.filter(user=self.request.user)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def usage_limits_check(request):
    """
    Check if user has exceeded usage limits
    """
    user = request.user
    subscription = user.subscription
    plan = subscription.plan
    
    # Get current period usage
    now = timezone.now()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    usage, created = UsageTracking.objects.get_or_create(
        user=user,
        period_start=current_month_start,
        defaults={
            'period_end': (current_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        }
    )
    
    # Check limits
    limits_exceeded = {}
    
    if plan.max_projects_per_month > 0 and usage.projects_created >= plan.max_projects_per_month:
        limits_exceeded['projects'] = {
            'limit': plan.max_projects_per_month,
            'used': usage.projects_created,
            'message': 'Monthly project limit reached'
        }
    
    if plan.max_audio_duration_minutes > 0 and usage.audio_minutes_processed >= plan.max_audio_duration_minutes:
        limits_exceeded['audio_duration'] = {
            'limit': plan.max_audio_duration_minutes,
            'used': float(usage.audio_minutes_processed),
            'message': 'Monthly audio processing limit reached'
        }
    
    return Response({
        'subscription_active': subscription.is_active,
        'plan': SubscriptionPlanSerializer(plan).data,
        'current_usage': UsageTrackingSerializer(usage).data,
        'limits_exceeded': limits_exceeded,
        'trial_days_remaining': subscription.days_until_renewal if subscription.is_trial else None
    })