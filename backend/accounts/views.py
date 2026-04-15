from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import stripe
import os
import logging
from datetime import timedelta

from accounts.authentication import ExpiringTokenAuthentication

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')

from .models import SubscriptionPlan, UserSubscription, UsageTracking, BillingHistory, UserProfile
from .serializers import (
    UserRegistrationSerializer, UserProfileSerializer, 
    SubscriptionPlanSerializer, UserSubscriptionSerializer,
    UsageTrackingSerializer, BillingHistorySerializer
)

# Configure Stripe
stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', os.getenv('STRIPE_SECRET_KEY'))


class LoginBurstThrottle(AnonRateThrottle):
    """Burst limit: max 5 login attempts per minute per IP."""
    scope = 'login_burst'


class LoginSustainedThrottle(AnonRateThrottle):
    """Sustained limit: max 20 login attempts per hour per IP."""
    scope = 'login_sustained'


class RegistrationRateThrottle(AnonRateThrottle):
    """Limit account creation to prevent registration spam."""
    scope = 'register'


def _set_auth_cookie(response, token):
    """Set the auth token as a secure httpOnly cookie on the response."""
    expiry_days = getattr(settings, 'TOKEN_EXPIRY_DAYS', 30)
    response.set_cookie(
        key='auth_token',
        value=token.key,
        max_age=expiry_days * 24 * 60 * 60,
        httponly=True,
        secure=not settings.DEBUG,
        samesite='Lax',
    )


def _get_or_create_fresh_token(user):
    """Return a valid (non-expired) token, deleting and recreating if stale."""
    expiry_days = getattr(settings, 'TOKEN_EXPIRY_DAYS', 30)
    token, created = Token.objects.get_or_create(user=user)
    if not created and (timezone.now() - token.created) > timedelta(days=expiry_days):
        token.delete()
        token = Token.objects.create(user=user)
    return token


@method_decorator(csrf_exempt, name='dispatch')
class UserRegistrationView(generics.CreateAPIView):
    """
    Register new user with automatic free trial
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegistrationRateThrottle]
    
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
            logger.warning(f"Stripe customer creation failed for user_id={user.id}: {type(e).__name__}")
        
        # Generate auth token
        token = _get_or_create_fresh_token(user)

        response = Response({
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
        _set_auth_cookie(response, token)
        return response


@method_decorator(csrf_exempt, name='dispatch')
class CustomAuthToken(ObtainAuthToken):
    """
    Custom login view that returns user info and subscription
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginBurstThrottle, LoginSustainedThrottle]
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token = _get_or_create_fresh_token(user)
        
        security_logger.info(
            f"login_success user_id={user.id} ip={request.META.get('REMOTE_ADDR', 'unknown')}"
        )
        
        # Get or create subscription for user
        subscription, created = UserSubscription.objects.get_or_create(user=user)
        
        response = Response({
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'subscription': UserSubscriptionSerializer(subscription).data
        })
        _set_auth_cookie(response, token)
        return response


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


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """
    Logout: delete the auth token server-side and clear the httpOnly cookie.
    """
    try:
        request.user.auth_token.delete()
    except Exception:
        pass
    security_logger.info(
        f"logout user_id={request.user.id} ip={request.META.get('REMOTE_ADDR', 'unknown')}"
    )
    response = Response({'message': 'Logged out successfully'})
    response.delete_cookie('auth_token')
    return response


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def data_export(request):
    """
    GDPR Article 20 - Right to data portability.
    Returns a JSON export of all personal data held for the authenticated user.
    """
    user = request.user

    # Account data (never include password hash)
    account_data = {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'date_joined': user.date_joined.isoformat(),
        'last_login': user.last_login.isoformat() if user.last_login else None,
    }

    # Subscription
    try:
        sub = user.subscription
        subscription_data = {
            'plan': sub.plan.name if sub.plan else None,
            'status': sub.status,
            'trial_end': sub.trial_end.isoformat() if sub.trial_end else None,
            'current_period_end': sub.current_period_end.isoformat() if sub.current_period_end else None,
        }
    except Exception:
        subscription_data = None

    # Projects + audio files + transcriptions
    from audioDiagnostic.models import AudioProject, AudioFile, ClientTranscription, DuplicateAnalysis
    projects = []
    for project in AudioProject.objects.filter(user=user).prefetch_related('audio_files'):
        files = []
        for af in project.audio_files.all():
            files.append({
                'id': af.id,
                'filename': af.filename,
                'file_size': af.file_size,
                'duration': af.duration,
                'status': af.status,
                'created_at': af.created_at.isoformat() if af.created_at else None,
            })
        projects.append({
            'id': project.id,
            'title': project.title,
            'created_at': project.created_at.isoformat() if project.created_at else None,
            'audio_files': files,
        })

    # Synced transcription metadata
    transcriptions = list(
        ClientTranscription.objects.filter(project__user=user).values(
            'id', 'filename', 'processing_method', 'model_used', 'duration', 'language', 'timestamp'
        )
    )
    for t in transcriptions:
        if t.get('timestamp'):
            t['timestamp'] = t['timestamp'].isoformat()

    # Synced duplicate analyses
    analyses = list(
        DuplicateAnalysis.objects.filter(project__user=user).values(
            'id', 'filename', 'algorithm', 'total_segments', 'duplicate_count', 'timestamp'
        )
    )
    for a in analyses:
        if a.get('timestamp'):
            a['timestamp'] = a['timestamp'].isoformat()

    export = {
        'export_generated_at': timezone.now().isoformat(),
        'account': account_data,
        'subscription': subscription_data,
        'projects': projects,
        'transcription_metadata': transcriptions,
        'duplicate_analyses': analyses,
    }

    security_logger.info(f"data_export user_id={user.id} ip={request.META.get('REMOTE_ADDR', 'unknown')}")

    return Response(export)