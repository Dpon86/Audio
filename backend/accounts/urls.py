from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from .views import (
    UserRegistrationView, CustomAuthToken, UserProfileView,
    SubscriptionPlansView, UserSubscriptionView, UsageTrackingView,
    BillingHistoryView, create_checkout_session, cancel_subscription,
    usage_limits_check
)
from .webhooks import stripe_webhook

urlpatterns = [
    # Authentication
    path('register/', csrf_exempt(UserRegistrationView.as_view()), name='user_register'),
    path('login/', csrf_exempt(CustomAuthToken.as_view()), name='user_login'),
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    
    # Subscription management
    path('plans/', SubscriptionPlansView.as_view(), name='subscription_plans'),
    path('subscription/', UserSubscriptionView.as_view(), name='user_subscription'),
    path('checkout/', create_checkout_session, name='create_checkout'),
    path('cancel-subscription/', cancel_subscription, name='cancel_subscription'),
    
    # Usage and billing
    path('usage/', UsageTrackingView.as_view(), name='usage_tracking'),
    path('billing/', BillingHistoryView.as_view(), name='billing_history'),
    path('usage-limits/', usage_limits_check, name='usage_limits'),
    
    # Webhooks
    path('stripe-webhook/', stripe_webhook, name='stripe_webhook'),
]