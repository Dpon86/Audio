# Payment System & AI Access Control Guide

**Created:** April 12, 2026  
**Purpose:** Complete guide to user authentication, payments, and AI feature gating

---

## 🎯 Overview

This guide explains how to:
1. **User Sign-Up & Authentication** - How users register and log in
2. **Subscription Plans** - Free trial vs paid tiers
3. **Stripe Payment Integration** - Taking payments
4. **AI Feature Access Control** - Gating AI features by subscription
5. **Usage Tracking** - Monitoring limits and billing

---

## 📋 Current System Status

### ✅ Already Implemented

Your system **already has**:
- ✅ User registration with automatic 7-day free trial
- ✅ Token-based authentication (REST API)
- ✅ Stripe integration (customer creation on signup)
- ✅ Subscription models (4 tiers: Free, Basic, Pro, Enterprise)
- ✅ Webhook handlers (payment events)
- ✅ Usage tracking (projects, audio minutes, storage)
- ✅ Billing history
- ✅ Monthly AI cost limits ($50 per user)

### ⚠️ Needs to be Added

Missing pieces:
- ⚠️ **AI feature gating by subscription plan** (currently not checked)
- ⚠️ Stripe product/price IDs need to be created
- ⚠️ Frontend payment UI (subscription page)
- ⚠️ Feature flag system for plan-based access

---

## 🔐 How User Authentication Works

### 1. User Registration Flow

```
User visits app → Clicks "Sign Up" → Fills form
            ↓
POST /api/auth/register/
{
  "username": "john",
  "email": "john@example.com",
  "password": "SecurePass123!",
  "password_confirm": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe"
}
            ↓
Backend creates:
1. User account
2. UserProfile
3. Stripe customer
4. UserSubscription (free trial, 7 days)
            ↓
Response:
{
  "user": {...},
  "token": "abc123...",
  "subscription": {
    "plan": "Free Trial",
    "status": "trialing",
    "trial_end": "2026-04-19T10:00:00Z"
  },
  "message": "Registration successful! Your 7-day free trial has started."
}
```

**What happens automatically:**
- ✅ 7-day free trial activated
- ✅ Stripe customer created
- ✅ Auth token generated
- ✅ User profile created

### 2. Login Flow

```
User visits app → Clicks "Log In" → Enters credentials
            ↓
POST /api/auth/login/
{
  "username": "john",
  "password": "SecurePass123!"
}
            ↓
Backend validates credentials
            ↓
Response:
{
  "token": "abc123...",
  "user": {...},
  "subscription": {
    "plan": "Professional",
    "status": "active",
    "current_period_end": "2026-05-12T10:00:00Z"
  }
}
```

### 3. Making Authenticated Requests

All API requests need the token:

```http
GET /api/ai-detection/detect/
Authorization: Token abc123...
```

Frontend stores token in localStorage:
```javascript
localStorage.setItem('authToken', 'abc123...');

// Use in requests
const response = await fetch('/api/some-endpoint/', {
  headers: {
    'Authorization': `Token ${localStorage.getItem('authToken')}`,
    'Content-Type': 'application/json'
  }
});
```

---

## 💳 Subscription Plans

> 📋 **For detailed plan comparisons with card-style layouts, see:** [PRICING_PLANS.md](PRICING_PLANS.md)

### Current Plan Structure

| Plan | Price/Month | Features | Audio Minutes | Projects | Storage |
|------|-------------|----------|---------------|----------|---------|
| **Free Trial** | £0 (7 days) | ✅ Basic features + 1 AI test | 60 min | 3 | 0.5 GB |
| **Starter** | £4.99/mo | ✅ Manual transcript + Algorithm detection | 300 min | 10 | 2 GB |
| **Basic** | £9.99/mo | ✅ AI Duplicate Detection | 500 min | 20 | 5 GB |
| **Pro** | £24.99/mo | ✅ All AI Features | 2000 min | Unlimited | 20 GB |
| **Enterprise** | £49.99/mo | ✅ Premium AI + Priority | Unlimited | Unlimited | 100 GB |

### Plan Definition (Database)

Located in: `backend/accounts/models.py`

```python
class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=50)  # 'free', 'basic', 'pro', 'enterprise'
    display_name = models.CharField(max_length=100)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Limits
    max_projects_per_month = models.IntegerField(default=0)  # 0 = unlimited
    max_audio_duration_minutes = models.IntegerField(default=0)
    max_file_size_mb = models.IntegerField(default=100)
    max_storage_gb = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Features
    priority_processing = models.BooleanField(default=False)
    api_access = models.BooleanField(default=False)
```

### Add AI Feature Flags

**STEP 1:** Update the SubscriptionPlan model to include AI features:

```python
# Add to backend/accounts/models.py in SubscriptionPlan class

class SubscriptionPlan(models.Model):
    # ... existing fields ...
    
    # AI Features (NEW)
    ai_duplicate_detection = models.BooleanField(default=False)
    ai_transcription = models.BooleanField(default=False)
    ai_pdf_comparison = models.BooleanField(default=False)
    ai_monthly_cost_limit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Monthly AI API cost limit in USD (0 = no access)"
    )
```

**STEP 2:** Create migration:

```bash
python manage.py makemigrations
python manage.py migrate
```

**STEP 3:** Update plans in Django admin or shell:

```python
python manage.py shell

from accounts.models import SubscriptionPlan

# Free Trial - 1 AI test allowed
free = SubscriptionPlan.objects.get(name='free')
free.ai_duplicate_detection = True
free.ai_transcription = True
free.ai_pdf_comparison = True
free.ai_monthly_cost_limit = 1.00  # £1 = ~1 AI use for testing
free.save()

# Basic - AI Duplicates only
basic = SubscriptionPlan.objects.get(name='basic')
basic.ai_duplicate_detection = True
basic.ai_transcription = False
basic.ai_pdf_comparison = False
basic.ai_monthly_cost_limit = 10.00  # $10/month AI budget
basic.save()

# Pro - All AI features
pro = SubscriptionPlan.objects.get(name='pro')
pro.ai_duplicate_detection = True
pro.ai_transcription = True
pro.ai_pdf_comparison = True
pro.ai_monthly_cost_limit = 50.00  # $50/month AI budget
pro.save()

# Enterprise - All AI features + higher limit
enterprise = SubscriptionPlan.objects.get(name='enterprise')
enterprise.ai_duplicate_detection = True
enterprise.ai_transcription = True
enterprise.ai_pdf_comparison = True
enterprise.ai_monthly_cost_limit = 200.00  # $200/month AI budget
enterprise.save()
```

---

## 🔒 Implementing AI Feature Access Control

### Create Access Control Decorator

**Create:** `backend/audioDiagnostic/utils/access_control.py`

```python
from functools import wraps
from rest_framework.response import Response
from rest_framework import status


def require_ai_feature(feature_name):
    """
    Decorator to check if user's subscription allows AI feature
    
    Usage:
        @require_ai_feature('ai_duplicate_detection')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get user's subscription
            if not hasattr(request.user, 'subscription'):
                return Response({
                    'success': False,
                    'error': 'No active subscription',
                    'upgrade_required': True,
                    'recommended_plan': 'basic'
                }, status=status.HTTP_402_PAYMENT_REQUIRED)
            
            subscription = request.user.subscription
            plan = subscription.plan
            
            # Check if subscription is active
            if not subscription.is_active:
                return Response({
                    'success': False,
                    'error': 'Subscription not active',
                    'subscription_status': subscription.status,
                    'upgrade_required': True
                }, status=status.HTTP_402_PAYMENT_REQUIRED)
            
            # Check if plan has the feature
            has_feature = getattr(plan, feature_name, False)
            if not has_feature:
                return Response({
                    'success': False,
                    'error': f'Your plan does not include {feature_name}',
                    'current_plan': plan.display_name,
                    'upgrade_required': True,
                    'recommended_plan': 'pro' if feature_name == 'ai_transcription' else 'basic'
                }, status=status.HTTP_402_PAYMENT_REQUIRED)
            
            # Feature is allowed - proceed
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def check_ai_cost_limit(user, estimated_cost):
    """
    Check if user has enough AI budget remaining
    
    Returns:
        tuple: (bool, float, str) - (allowed, remaining, message)
    """
    from django.core.cache import cache
    from datetime import datetime
    
    subscription = user.subscription
    plan = subscription.plan
    
    # Get monthly limit from plan
    monthly_limit = float(plan.ai_monthly_cost_limit)
    
    if monthly_limit == 0:
        return False, 0.0, "Your plan does not include AI features"
    
    # Get current month usage
    month_key = f"ai_cost_{user.id}_{datetime.now().strftime('%Y_%m')}"
    current_usage = float(cache.get(month_key, 0.0))
    
    # Calculate remaining budget
    remaining = monthly_limit - current_usage
    
    # Check if this request would exceed limit
    if estimated_cost > remaining:
        return False, remaining, f"This would exceed your monthly AI budget (${remaining:.2f} remaining)"
    
    return True, remaining, "OK"
```

### Update AI Detection View

**Modify:** `backend/audioDiagnostic/views/ai_detection_views.py`

```python
from ..utils.access_control import require_ai_feature, check_ai_cost_limit

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_ai_feature('ai_duplicate_detection')  # NEW - Check subscription
def ai_detect_duplicates_view(request):
    """
    Start AI-powered duplicate detection
    
    Requires: Basic plan or higher
    """
    serializer = AIDetectionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    validated_data = serializer.validated_data
    audio_file_id = validated_data['audio_file_id']
    
    try:
        audio_file = get_object_or_404(AudioFile, id=audio_file_id)
        
        # Check permission
        if audio_file.project.user != request.user:
            return Response(
                {'success': False, 'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Estimate cost
        duration = audio_file.duration_seconds or 0
        calculator = CostCalculator()
        cost_estimate = calculator.estimate_cost_for_audio(
            provider='anthropic',
            model='claude-3-5-sonnet-20241022',
            audio_duration_seconds=duration,
            task='duplicate_detection'
        )
        
        # Check AI budget (NEW)
        allowed, remaining, message = check_ai_cost_limit(
            request.user, 
            cost_estimate['estimated_cost_usd']
        )
        
        if not allowed:
            return Response({
                'success': False,
                'error': message,
                'current_usage': float(remaining),
                'plan_limit': float(request.user.subscription.plan.ai_monthly_cost_limit),
                'estimated_cost': cost_estimate['estimated_cost_usd'],
                'upgrade_required': True
            }, status=status.HTTP_402_PAYMENT_REQUIRED)
        
        # Start task
        task = ai_detect_duplicates_task.delay(
            audio_file_id=audio_file_id,
            user_id=request.user.id,
            min_words=validated_data['min_words'],
            similarity_threshold=validated_data['similarity_threshold'],
            keep_occurrence=validated_data['keep_occurrence'],
            enable_paragraph_expansion=validated_data['enable_paragraph_expansion']
        )
        
        return Response({
            'success': True,
            'task_id': task.id,
            'estimated_cost': cost_estimate,
            'remaining_budget': remaining,
            'status_url': f'/api/ai-detection/status/{task.id}/'
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logger.error(f"AI detection failed: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

---

## 💰 Setting Up Stripe Payments

### Step 1: Create Stripe Account

1. Go to https://stripe.com
2. Sign up for account (free to start)
3. Verify email and business details
4. Get API keys from Dashboard → Developers → API Keys

### Step 2: Create Products in Stripe

Navigate to **Products** in Stripe Dashboard:

**Product 1: Starter Plan**
- Name: "Starter Plan"
- Description: "Manual transcription + algorithm detection"
- Pricing:
  - Monthly: £4.99/month (create price, note the `price_XXX` ID)
  - Yearly: £49/year (optional, save 17%)

**Product 2: Basic Plan**
- Name: "Basic Plan"
- Description: "AI duplicate detection + 500 minutes audio"
- Pricing:
  - Monthly: £9.99/month
  - Yearly: £99/year (optional, save 17%)

**Product 3: Professional Plan**
- Name: "Professional Plan"
- Description: "All AI features + 2000 minutes audio"
- Pricing:
  - Monthly: £24.99/month
  - Yearly: £249/year

**Product 4: Enterprise Plan**
- Name: "Enterprise Plan"
- Description: "Premium AI + unlimited audio"
- Pricing:
  - Monthly: £49.99/month
  - Yearly: £499/year

**Save the price IDs** (they look like `price_1ABC2DEF3GHI4JKL`)

### Step 3: Configure Backend

**Update .env file:**

```bash
# Stripe Configuration
STRIPE_PUBLISHABLE_KEY=pk_test_51ABC...  # From Stripe Dashboard
STRIPE_SECRET_KEY=sk_test_51ABC...       # From Stripe Dashboard (KEEP SECRET!)
STRIPE_WEBHOOK_SECRET=whsec_ABC...       # Created in Step 4
```

**Update database with Stripe IDs:**

```python
python manage.py shell

from accounts.models import SubscriptionPlan

# Basic Plan
basic = SubscriptionPlan.objects.get(name='basic')
basic.stripe_price_id_monthly = 'price_1ABC...'  # From Stripe
basic.stripe_price_id_yearly = 'price_1DEF...'   # Optional
basic.save()

# Pro Plan
pro = SubscriptionPlan.objects.get(name='pro')
pro.stripe_price_id_monthly = 'price_1GHI...'
pro.stripe_price_id_yearly = 'price_1JKL...'
pro.save()

# Enterprise Plan
enterprise = SubscriptionPlan.objects.get(name='enterprise')
enterprise.stripe_price_id_monthly = 'price_1MNO...'
enterprise.stripe_price_id_yearly = 'price_1PQR...'
enterprise.save()
```

### Step 4: Set Up Webhooks

Stripe needs to notify your server about payment events.

**In Stripe Dashboard:**

1. Go to **Developers → Webhooks**
2. Click **Add endpoint**
3. Endpoint URL: `https://audio.precisepouchtrack.com/api/auth/stripe-webhook/`
4. Select events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
5. Click **Add endpoint**
6. Copy the **Signing secret** (starts with `whsec_...`)
7. Add to `.env` as `STRIPE_WEBHOOK_SECRET`

**Test webhook locally (development):**

```bash
# Install Stripe CLI
# Download from: https://stripe.com/docs/stripe-cli

# Login
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/api/auth/stripe-webhook/

# Test with sample event
stripe trigger checkout.session.completed
```

---

## 🎨 Frontend Implementation

### 1. Subscription Plans Page

Create a pricing page showing plan comparison:

```jsx
// frontend/src/pages/Pricing.jsx

import React, { useState, useEffect } from 'react';

function Pricing() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
    // Fetch plans from API
    fetch('/api/auth/plans/')
      .then(res => res.json())
      .then(data => setPlans(data));
  }, []);
  
  const handleSubscribe = async (planId) => {
    setLoading(true);
    
    try {
      const token = localStorage.getItem('authToken');
      const response = await fetch('/api/auth/checkout/', {
        method: 'POST',
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          plan_id: planId,
          billing_cycle: 'monthly'
        })
      });
      
      const data = await response.json();
      
      // Redirect to Stripe Checkout
      window.location.href = data.checkout_url;
      
    } catch (error) {
      alert('Failed to start checkout');
      setLoading(false);
    }
  };
  
  return (
    <div className="pricing-page">
      <h1>Choose Your Plan</h1>
      
      <div className="pricing-grid">
        {plans.map(plan => (
          <div key={plan.id} className="pricing-card">
            <h2>{plan.display_name}</h2>
            <p className="price">${plan.price_monthly}/month</p>
            <p className="description">{plan.description}</p>
            
            <ul className="features">
              {plan.features.map((feature, i) => (
                <li key={i}>{feature}</li>
              ))}
            </ul>
            
            <button 
              onClick={() => handleSubscribe(plan.id)}
              disabled={loading}
            >
              Subscribe Now
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Pricing;
```

### 2. Check Subscription Before AI Actions

```jsx
// frontend/src/components/Tab3Duplicates.js

const handleAIDetectDuplicates = async () => {
  // ... existing code ...
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/ai-detection/detect/`, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        audio_file_id: numericAudioFileId,
        min_words: windowMinWordLength || 3,
        similarity_threshold: tfidfSimilarityThreshold || 0.85,
        keep_occurrence: 'last'
      })
    });
    
    const data = await response.json();
    
    // Handle payment required
    if (response.status === 402) {
      const upgradeMessage = data.upgrade_required
        ? `\n\nPlease upgrade to ${data.recommended_plan || 'a paid plan'} to use AI features.`
        : '';
      
      alert(`${data.error}${upgradeMessage}`);
      
      // Optionally redirect to pricing page
      if (confirm('Go to subscription plans?')) {
        window.location.href = '/pricing';
      }
      
      return;
    }
    
    if (!response.ok) {
      throw new Error(data.error || 'AI detection failed');
    }
    
    // Continue with normal flow...
    await pollAIDetectionStatus(data.task_id);
    
  } catch (error) {
    alert(`AI detection failed: ${error.message}`);
  }
};
```

### 3. Show Subscription Status in UI

```jsx
// frontend/src/components/UserMenu.jsx

function UserMenu() {
  const [subscription, setSubscription] = useState(null);
  
  useEffect(() => {
    const token = localStorage.getItem('authToken');
    
    fetch('/api/auth/subscription/', {
      headers: {
        'Authorization': `Token ${token}`
      }
    })
      .then(res => res.json())
      .then(data => setSubscription(data));
  }, []);
  
  return (
    <div className="user-menu">
      <div className="subscription-badge">
        {subscription?.plan?.display_name || 'Free Trial'}
      </div>
      
      {subscription?.status === 'trialing' && (
        <div className="trial-warning">
          Trial ends in {subscription.days_until_renewal} days
          <button onClick={() => window.location.href = '/pricing'}>
            Upgrade Now
          </button>
        </div>
      )}
      
      <div className="ai-budget">
        AI Budget: ${subscription?.remaining_budget || 0} / 
        ${subscription?.plan?.ai_monthly_cost_limit || 0}
      </div>
    </div>
  );
}
```

---

## 🧪 Testing the Payment Flow

### Test Mode (Development)

Stripe provides test card numbers:

**Successful payment:**
- Card: `4242 4242 4242 4242`
- Exp: Any future date
- CVC: Any 3 digits
- ZIP: Any 5 digits

**Payment requires authentication:**
- Card: `4000 0025 0000 3155`

**Card declined:**
- Card: `4000 0000 0000 9995`

### Test Flow

1. **Create test user:**
   ```bash
   POST /api/auth/register/
   {
     "username": "testuser",
     "email": "test@example.com",
     "password": "TestPass123!",
     "password_confirm": "TestPass123!"
   }
   ```

2. **Verify free trial:**
   ```bash
   GET /api/auth/subscription/
   # Should show status="trialing", 7 days remaining
   ```

3. **Try AI feature (should fail):**
   ```bash
   POST /api/ai-detection/detect/
   # Should return 402 Payment Required
   ```

4. **Upgrade to Basic:**
   ```bash
   POST /api/auth/checkout/
   {
     "plan_id": 2,  # Basic plan ID
     "billing_cycle": "monthly"
   }
   # Returns checkout_url → Open in browser
   ```

5. **Complete Stripe checkout:**
   - Use test card `4242 4242 4242 4242`
   - Complete payment
   - Redirected back to app

6. **Verify webhook received:**
   ```bash
   # Check logs for webhook event
   tail -f /var/log/audioapp/django.log
   # Should see: "Checkout completed for user testuser"
   ```

7. **Check subscription updated:**
   ```bash
   GET /api/auth/subscription/
   # Should show status="active", plan="Basic"
   ```

8. **Try AI feature again (should work):**
   ```bash
   POST /api/ai-detection/detect/
   # Should return task_id and start processing
   ```

---

## 📊 Monitoring & Analytics

### Track Conversion Rate

```python
# backend/analytics/models.py

class UserEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=50)  # 'signup', 'trial_started', 'upgraded', 'churned'
    event_data = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)

# Track key events:
# - User signs up → trial_started
# - Trial ends without upgrade → trial_expired
# - User upgrades → upgraded (note which plan)
# - User cancels → churned
# - AI feature blocked → upgrade_prompted
```

### Revenue Dashboard

```python
from accounts.models import BillingHistory, UserSubscription
from django.db.models import Sum, Count
from datetime import datetime, timedelta

# Monthly recurring revenue
active_subs = UserSubscription.objects.filter(status='active')
mrr = sum(sub.plan.price_monthly for sub in active_subs)

# Monthly revenue
month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0)
monthly_revenue = BillingHistory.objects.filter(
    transaction_type='payment',
    created_at__gte=month_start
).aggregate(Sum('amount'))['amount__sum'] or 0

# Churn rate
churned_this_month = UserSubscription.objects.filter(
    status='canceled',
    updated_at__gte=month_start
).count()

churn_rate = (churned_this_month / active_subs.count()) * 100 if active_subs.count() > 0 else 0
```

---

## ✅ Deployment Checklist

### Before Going Live

- [ ] Set up Stripe account (production mode)
- [ ] Create products and prices in Stripe
- [ ] Add production API keys to server `.env`
- [ ] Configure webhook endpoint (production URL)
- [ ] Test webhook with Stripe CLI
- [ ] Add AI feature flags to SubscriptionPlan model
- [ ] Update existing plans with AI permissions
- [ ] Deploy access control decorator
- [ ] Update AI views with `@require_ai_feature`
- [ ] Create pricing page frontend
- [ ] Add subscription status to user menu
- [ ] Test payment flow end-to-end
- [ ] Set up monitoring/alerts for failed payments
- [ ] Create admin dashboard for subscription management

### Security Checklist

- [ ] Never commit Stripe secret keys to Git
- [ ] Use environment variables for all secrets
- [ ] Verify webhook signatures (already implemented)
- [ ] Use HTTPS for all payment pages
- [ ] Don't store credit card details (Stripe handles this)
- [ ] Implement rate limiting on checkout endpoints
- [ ] Add CAPTCHA to registration if needed
- [ ] Monitor for fraudulent signups

---

## 💡 Recommended Setup

### For Initial Launch

**Option 1: Simple (No Payments Yet)**
1. Everyone gets free trial (7 days)
2. After trial, manually approve users
3. No payment processing yet
4. Good for beta testing

**Option 2: Payment Optional**
1. Free tier: Basic features only
2. Paid tier: AI features unlocked
3. Allow both free and paid users
4. Recommended for gradual rollout

**Option 3: Payment Required (Recommended)**
1. 7-day free trial (auto-created)
2. After trial, must upgrade to continue
3. AI features only for paid users
4. Best for sustainable business

### Pricing Recommendations

Based on your AI costs (~$0.06/hour detection):

**Free Trial**
- 7 days
- 60 minutes audio
- **1 FREE AI use** (test any AI feature)
- Good for testing before subscribing

**Basic - $9.99/month**
- AI duplicate detection
- 300 minutes audio (~$18 AI cost max)
- You make: ~$10/user profit
- Good margin

**Pro - $29.99/month**
- All AI features
- 1000 minutes audio
- $50 AI budget
- Premium features

**Cost Breakdown:**
- 300 min audio × $0.06 = $18 max AI cost
- Charge $9.99/month
- Net revenue: -$8/user (loss leader)

**Better Pricing:**
- Basic - $19.99/month (300 min, AI detection)
- Pro - $49.99/month (1000 min, all AI)
- Makes you profitable at scale

---

## 🆘 Troubleshooting

### Webhook Not Receiving Events

**Problem:** Stripe sends webhook but backend doesn't process it

**Solutions:**
1. Check webhook URL is correct in Stripe dashboard
2. Verify STRIPE_WEBHOOK_SECRET is set correctly
3. Check firewall allows Stripe IPs
4. Test locally with `stripe listen --forward-to`
5. Check Django logs for errors

### User Stuck in Trial After Payment

**Problem:** User paid but still shows as 'trialing'

**Solutions:**
1. Check webhook was received (logs)
2. Verify subscription ID matches Stripe
3. Manually update: `user.subscription.status = 'active'; user.subscription.save()`
4. Check Stripe dashboard for subscription status

### AI Feature Still Blocked After Upgrade

**Problem:** User upgraded but can't access AI

**Solutions:**
1. Verify plan has `ai_duplicate_detection = True`
2. Check subscription status is 'active'
3. Clear Redis cache: `redis-cli FLUSHDB`
4. Refresh user session (logout/login)

---

## 📞 Support

**Documentation:**
- Backend models: `backend/accounts/models.py`
- Views: `backend/accounts/views.py`
- Webhooks: `backend/accounts/webhooks.py`
- Serializers: `backend/accounts/serializers.py`

**External Resources:**
- Stripe Docs: https://stripe.com/docs
- Stripe Testing: https://stripe.com/docs/testing
- Django Rest Auth: https://www.django-rest-framework.org/api-guide/authentication/

**Key Files:**
- `backend/accounts/` - All auth/payment code
- `backend/audioDiagnostic/utils/access_control.py` - Feature gating (create this)
- `frontend/src/pages/Pricing.jsx` - Subscription page (create this)

---

**Last Updated:** April 12, 2026  
**Status:** Ready for implementation - 2-3 days development time
