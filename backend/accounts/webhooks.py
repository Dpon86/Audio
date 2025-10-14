import stripe
import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserSubscription, BillingHistory, SubscriptionPlan
import logging

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handle Stripe webhook events for subscription management
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid payload in Stripe webhook")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in Stripe webhook")
        return HttpResponse(status=400)
    
    # Handle the event
    try:
        if event['type'] == 'checkout.session.completed':
            handle_checkout_completed(event['data']['object'])
        
        elif event['type'] == 'customer.subscription.created':
            handle_subscription_created(event['data']['object'])
        
        elif event['type'] == 'customer.subscription.updated':
            handle_subscription_updated(event['data']['object'])
        
        elif event['type'] == 'customer.subscription.deleted':
            handle_subscription_cancelled(event['data']['object'])
        
        elif event['type'] == 'invoice.payment_succeeded':
            handle_payment_succeeded(event['data']['object'])
        
        elif event['type'] == 'invoice.payment_failed':
            handle_payment_failed(event['data']['object'])
        
        else:
            logger.info(f"Unhandled Stripe webhook event: {event['type']}")
    
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        return HttpResponse(status=500)
    
    return HttpResponse(status=200)


def handle_checkout_completed(session):
    """Handle successful checkout session completion"""
    try:
        user_id = session['metadata'].get('user_id')
        plan_id = session['metadata'].get('plan_id')
        billing_cycle = session['metadata'].get('billing_cycle', 'monthly')
        
        user = User.objects.get(id=user_id)
        plan = SubscriptionPlan.objects.get(id=plan_id)
        
        # Get the subscription ID from Stripe
        subscription_id = session.get('subscription')
        
        # Update user subscription
        user_subscription, created = UserSubscription.objects.get_or_create(
            user=user,
            defaults={
                'plan': plan,
                'status': 'active',
                'billing_cycle': billing_cycle,
                'stripe_customer_id': session['customer'],
                'stripe_subscription_id': subscription_id,
            }
        )
        
        if not created:
            user_subscription.plan = plan
            user_subscription.status = 'active'
            user_subscription.billing_cycle = billing_cycle
            user_subscription.stripe_subscription_id = subscription_id
            user_subscription.save()
        
        logger.info(f"Checkout completed for user {user.username} - Plan: {plan.display_name}")
        
    except Exception as e:
        logger.error(f"Error handling checkout completion: {str(e)}")


def handle_subscription_created(subscription):
    """Handle new subscription creation"""
    try:
        customer_id = subscription['customer']
        subscription_id = subscription['id']
        
        # Find user by Stripe customer ID
        user_subscription = UserSubscription.objects.filter(
            stripe_customer_id=customer_id
        ).first()
        
        if user_subscription:
            user_subscription.stripe_subscription_id = subscription_id
            user_subscription.status = 'active'
            user_subscription.current_period_start = timezone.datetime.fromtimestamp(
                subscription['current_period_start'], tz=timezone.utc
            )
            user_subscription.current_period_end = timezone.datetime.fromtimestamp(
                subscription['current_period_end'], tz=timezone.utc
            )
            user_subscription.save()
            
            logger.info(f"Subscription created for user {user_subscription.user.username}")
        
    except Exception as e:
        logger.error(f"Error handling subscription creation: {str(e)}")


def handle_subscription_updated(subscription):
    """Handle subscription updates"""
    try:
        subscription_id = subscription['id']
        
        user_subscription = UserSubscription.objects.filter(
            stripe_subscription_id=subscription_id
        ).first()
        
        if user_subscription:
            # Map Stripe status to our status
            status_mapping = {
                'active': 'active',
                'past_due': 'past_due',
                'canceled': 'canceled',
                'unpaid': 'past_due',
                'trialing': 'trialing',
            }
            
            user_subscription.status = status_mapping.get(
                subscription['status'], 'active'
            )
            user_subscription.current_period_start = timezone.datetime.fromtimestamp(
                subscription['current_period_start'], tz=timezone.utc
            )
            user_subscription.current_period_end = timezone.datetime.fromtimestamp(
                subscription['current_period_end'], tz=timezone.utc
            )
            user_subscription.save()
            
            logger.info(f"Subscription updated for user {user_subscription.user.username}")
        
    except Exception as e:
        logger.error(f"Error handling subscription update: {str(e)}")


def handle_subscription_cancelled(subscription):
    """Handle subscription cancellation"""
    try:
        subscription_id = subscription['id']
        
        user_subscription = UserSubscription.objects.filter(
            stripe_subscription_id=subscription_id
        ).first()
        
        if user_subscription:
            user_subscription.status = 'canceled'
            user_subscription.save()
            
            logger.info(f"Subscription cancelled for user {user_subscription.user.username}")
        
    except Exception as e:
        logger.error(f"Error handling subscription cancellation: {str(e)}")


def handle_payment_succeeded(invoice):
    """Handle successful payment"""
    try:
        customer_id = invoice['customer']
        amount = invoice['amount_paid'] / 100  # Convert cents to dollars
        
        user_subscription = UserSubscription.objects.filter(
            stripe_customer_id=customer_id
        ).first()
        
        if user_subscription:
            # Create billing history record
            BillingHistory.objects.create(
                user=user_subscription.user,
                transaction_type='payment',
                amount=amount,
                currency=invoice['currency'].upper(),
                stripe_invoice_id=invoice['id'],
                description=f"Payment for {user_subscription.plan.display_name} subscription"
            )
            
            logger.info(f"Payment succeeded for user {user_subscription.user.username}: ${amount}")
        
    except Exception as e:
        logger.error(f"Error handling payment success: {str(e)}")


def handle_payment_failed(invoice):
    """Handle failed payment"""
    try:
        customer_id = invoice['customer']
        amount = invoice['amount_due'] / 100  # Convert cents to dollars
        
        user_subscription = UserSubscription.objects.filter(
            stripe_customer_id=customer_id
        ).first()
        
        if user_subscription:
            # Update subscription status
            user_subscription.status = 'past_due'
            user_subscription.save()
            
            # Create billing history record
            BillingHistory.objects.create(
                user=user_subscription.user,
                transaction_type='failed',
                amount=amount,
                currency=invoice['currency'].upper(),
                stripe_invoice_id=invoice['id'],
                description=f"Failed payment for {user_subscription.plan.display_name} subscription"
            )
            
            logger.info(f"Payment failed for user {user_subscription.user.username}: ${amount}")
        
    except Exception as e:
        logger.error(f"Error handling payment failure: {str(e)}")