# Quick Start: Adding Subscription-Based AI Access

**Goal:** Gate AI features behind paid subscriptions  
**Time Required:** 2-3 hours  
**Current Status:** Payment system exists, access control needs to be added

> 📋 **For detailed plan comparisons and pricing cards, see:** [PRICING_PLANS.md](PRICING_PLANS.md)

---

## 🎯 What You Need to Do

### Phase 1: Add AI Feature Flags (30 min)

**1. Update SubscriptionPlan model:**

```bash
ssh nickd@82.165.221.205
cd /opt/audioapp/backend
source venv/bin/activate  # or env/bin/activate

# Edit models.py
nano audioDiagnostic/utils/access_control.py
# Copy content from: docs/AI-models/PAYMENT_AND_ACCESS_CONTROL.md
# Save and exit

# Create migration
python manage.py makemigrations accounts
python manage.py migrate
```

**2. Update existing plans with AI permissions:**

```python
python manage.py shell

from accounts.models import SubscriptionPlan

# Free Trial - 7 days, 1 free AI use for testing
free = SubscriptionPlan.objects.get_or_create(
    name='free',
    defaults={
        'display_name': 'Free Trial',
        'description': '7-day free trial with 1 free AI test',
        'price_monthly': 0.00,
        'max_projects_per_month': 3,
        'max_audio_duration_minutes': 60,
        'max_file_size_mb': 50,
        'max_storage_gb': 0.5,
        'ai_duplicate_detection': True,
        'ai_transcription': True,
        'ai_pdf_comparison': True,
        'ai_monthly_cost_limit': 1.00  # £1 = ~1 AI use
    }
)[0]
free.ai_duplicate_detection = True
free.ai_transcription = True
free.ai_pdf_comparison = True
free.ai_monthly_cost_limit = 1.00  # Allow 1 free AI test
free.save()
print("✓ Free plan updated (1 free AI use)")

# Starter - Manual features (no AI)
starter, created = SubscriptionPlan.objects.get_or_create(
    name='starter',
    defaults={
        'display_name': 'Starter Plan',
        'description': 'Manual transcription + algorithm detection (no AI)',
        'price_monthly': 4.99,
        'max_projects_per_month': 10,
        'max_audio_duration_minutes': 300,
        'max_file_size_mb': 100,
        'max_storage_gb': 2.0,
        'ai_duplicate_detection': False,
        'ai_transcription': False,
        'ai_pdf_comparison': False,
        'ai_monthly_cost_limit': 0.00
    }
)
starter.ai_duplicate_detection = False
starter.ai_monthly_cost_limit = 0.00
starter.save()
print("✓ Starter plan updated")

# Basic - AI Duplicates Only
basic, created = SubscriptionPlan.objects.get_or_create(
    name='basic',
    defaults={
        'display_name': 'Basic Plan',
        'description': 'AI duplicate detection + 500 minutes audio',
        'price_monthly': 9.99,
        'max_projects_per_month': 20,
        'max_audio_duration_minutes': 500,
        'max_file_size_mb': 150,
        'max_storage_gb': 5.0,
        'ai_duplicate_detection': True,
        'ai_transcription': False,
        'ai_pdf_comparison': False,
        'ai_monthly_cost_limit': 20.00
    }
)
basic.ai_duplicate_detection = True
basic.ai_monthly_cost_limit = 20.00
basic.save()
print("✓ Basic plan updated")

# Pro - All AI Features
pro, created = SubscriptionPlan.objects.get_or_create(
    name='pro',
    defaults={
        'display_name': 'Professional',
        'description': 'All AI features + 2000 minutes audio',
        'price_monthly': 24.99,
        'max_projects_per_month': 0,  # unlimited
        'max_audio_duration_minutes': 2000,
        'max_file_size_mb': 300,
        'max_storage_gb': 20.0,
        'ai_duplicate_detection': True,
        'ai_transcription': True,
        'ai_pdf_comparison': True,
        'ai_monthly_cost_limit': 60.00
    }
)
pro.ai_duplicate_detection = True
pro.ai_transcription = True
pro.ai_pdf_comparison = True
pro.ai_monthly_cost_limit = 60.00
pro.save()
print("✓ Pro plan updated")

# Enterprise - Premium AI
enterprise, created = SubscriptionPlan.objects.get_or_create(
    name='enterprise',
    defaults={
        'display_name': 'Enterprise',
        'description': 'Premium AI + unlimited processing',
        'price_monthly': 49.99,
        'max_projects_per_month': 0,  # unlimited
        'max_audio_duration_minutes': 0,  # unlimited
        'max_file_size_mb': 500,
        'max_storage_gb': 100.0,
        'ai_duplicate_detection': True,
        'ai_transcription': True,
        'ai_pdf_comparison': True,
        'ai_monthly_cost_limit': 200.00
    }
)
enterprise.ai_duplicate_detection = True
enterprise.ai_transcription = True
enterprise.ai_pdf_comparison = True
enterprise.ai_monthly_cost_limit = 200.00
enterprise.save()
print("✓ Enterprise plan updated")

print("\n✅ All plans configured for AI access control")
exit()
```

---

### Phase 2: Add Access Control to AI Views (30 min)

**1. Create access control utilities:**

File already created at: `backend/audioDiagnostic/utils/access_control.py`

**2. Update AI detection view:**

```bash
nano audioDiagnostic/views/ai_detection_views.py
```

Add at top:
```python
from ..utils.access_control import require_ai_feature, check_ai_cost_limit
```

Update `ai_detect_duplicates_view`:
```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_ai_feature('ai_duplicate_detection')  # NEW
def ai_detect_duplicates_view(request):
    # ... rest of function
    
    # Before starting task, add:
    allowed, remaining, message = check_ai_cost_limit(
        request.user,
        cost_estimate['estimated_cost_usd']
    )
    
    if not allowed:
        return Response({
            'success': False,
            'error': message,
            'remaining_budget': remaining,
            'upgrade_required': True
        }, status=status.HTTP_402_PAYMENT_REQUIRED)
```

---

### Phase 3: Set Up Stripe (45 min)

**1. Create Stripe account:**
- Go to https://stripe.com
- Sign up (free)
- Verify email

**2. Create products:**

In Stripe Dashboard → Products:

- **Basic Plan:** $19.99/month
  - Copy price ID (e.g., `price_1ABC...`)
  
- **Professional Plan:** $49.99/month
  - Copy price ID

**3. Add to database:**

```python
python manage.py shell

from accounts.models import SubscriptionPlan

basic = SubscriptionPlan.objects.get(name='basic')
basic.stripe_price_id_monthly = 'price_1ABC...'  # From Stripe
basic.save()

pro = SubscriptionPlan.objects.get(name='pro')
pro.stripe_price_id_monthly = 'price_1DEF...'  # From Stripe
pro.save()

exit()
```

**4. Add API keys to .env:**

```bash
nano .env
```

Add:
```bash
STRIPE_PUBLISHABLE_KEY=pk_live_...  # From Stripe Dashboard
STRIPE_SECRET_KEY=sk_live_...       # KEEP SECRET!
STRIPE_WEBHOOK_SECRET=whsec_...     # Created in step 5
```

**5. Configure webhook:**

In Stripe Dashboard → Developers → Webhooks:
- Add endpoint: `https://audio.precisepouchtrack.com/api/auth/stripe-webhook/`
- Select events:
  - `checkout.session.completed`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_succeeded`
  - `invoice.payment_failed`
- Copy webhook secret → Add to .env

**6. Restart server:**

```bash
sudo systemctl restart audioapp
sudo systemctl restart audioapp-celery
```

---

### Phase 4: Frontend Updates (45 min)

**1. Create pricing page:**

Create `frontend/src/pages/Pricing.jsx` - see full code in PAYMENT_AND_ACCESS_CONTROL.md

**2. Handle payment errors in AI detection:**

Update `Tab3Duplicates.js`:

```javascript
const handleAIDetectDuplicates = async () => {
  // ... existing code ...
  
  const response = await fetch('/api/ai-detection/detect/', {
    method: 'POST',
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({...})
  });
  
  const data = await response.json();
  
  // Handle payment required (NEW)
  if (response.status === 402) {
    if (confirm(`${data.error}\n\nWould you like to upgrade now?`)) {
      window.location.href = '/pricing';
    }
    return;
  }
  
  // ... rest of code ...
};
```

**3. Show subscription status:**

Add to user menu:
```jsx
<div className="subscription-badge">
  {userSubscription?.plan?.display_name || 'Free Trial'}
</div>

{userSubscription?.ai_budget && (
  <div className="ai-budget">
    AI Budget: ${userSubscription.ai_remaining} / ${userSubscription.ai_limit}
  </div>
)}
```

---

## 🧪 Testing

### 1. Test Free User (No AI Access)

```bash
# Create test user
curl -X POST http://audio.precisepouchtrack.com/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testfree",
    "email": "test@example.com",
    "password": "Test123!",
    "password_confirm": "Test123!"
  }'

# Try AI detection (should fail with 402)
curl -X POST http://audio.precisepouchtrack.com/api/ai-detection/detect/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"audio_file_id": 1}'

# Expected response:
{
  "success": false,
  "error": "Your Free Trial does not include ai_duplicate_detection",
  "upgrade_required": true,
  "recommended_plan": "basic"
}
```

### 2. Test Upgrade Flow

```bash
# Get checkout URL
curl -X POST http://audio.precisepouchtrack.com/api/auth/checkout/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan_id": 2, "billing_cycle": "monthly"}'

# Returns: {"checkout_url": "https://checkout.stripe.com/..."}
# Open URL in browser, use test card: 4242 4242 4242 4242
```

### 3. Test AI Access After Payment

```bash
# Verify subscription updated
curl http://audio.precisepouchtrack.com/api/auth/subscription/ \
  -H "Authorization: Token YOUR_TOKEN"

# Should show: "plan": "Basic Plan", "status": "active"

# Try AI detection again (should work now)
curl -X POST http://audio.precisepouchtrack.com/api/ai-detection/detect/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"audio_file_id": 1}'

# Should return: task_id and start processing
```

---

## 📋 Deployment Checklist

Before deploying to production:

- [ ] Run migrations on production server
- [ ] Update all SubscriptionPlan records with AI flags
- [ ] Create Stripe products and copy price IDs
- [ ] Add Stripe API keys to production .env
- [ ] Configure Stripe webhook endpoint
- [ ] Test webhook with Stripe CLI: `stripe trigger checkout.session.completed`
- [ ] Deploy access_control.py to production
- [ ] Update AI views with @require_ai_feature decorator
- [ ] Deploy pricing page to frontend
- [ ] Test complete payment flow end-to-end
- [ ] Monitor webhook delivery in Stripe dashboard
- [ ] Set up alerts for failed payments

---

## 🚨 Common Issues

### Issue: Webhook not working

**Symptoms:**
- User pays but subscription stays "trialing"
- Stripe shows webhook sent but not received

**Fix:**
1. Check webhook URL is correct
2. Verify STRIPE_WEBHOOK_SECRET matches
3. Check Django logs: `tail -f /var/log/audioapp/django.log`
4. Test locally: `stripe listen --forward-to localhost:8000/api/auth/stripe-webhook/`

### Issue: AI still blocked after upgrade

**Symptoms:**
- User upgraded but gets 402 error on AI features

**Fix:**
1. Check plan has feature flag: `python manage.py shell` → `user.subscription.plan.ai_duplicate_detection`
2. Verify subscription status: `user.subscription.status` should be 'active'
3. Check webhook was processed (Django logs)
4. Manually update if needed: `subscription.status = 'active'; subscription.save()`

### Issue: Cost limit reached but budget shows remaining

**Symptoms:**
- User gets "Monthly AI cost limit exceeded" but dashboard shows budget left

**Fix:**
1. Check Redis cache: `redis-cli` → `GET ai_cost_USER_ID_2026_04`
2. Clear cache if corrupted: `redis-cli FLUSHDB` (WARNING: clears all cache)
3. Or specific key: `redis-cli DEL ai_cost_USER_ID_2026_04`

---

## 💡 Recommended Rollout

### Week 1: Soft Launch
- Enable for existing users (grandfather them in)
- New signups get 7-day trial
- Don't enforce yet, just track data
- Monitor usage patterns

### Week 2: Email Campaign
- Send email to trial users: "Your trial ends in X days"
- Offer 20% discount for early adopters
- Link to pricing page

### Week 3: Enforcement
- Enable access control on AI features
- Show upgrade prompts
- Monitor conversion rate

### Week 4: Optimization
- A/B test pricing
- Analyze churn
- Adjust limits based on usage

---

## 📊 Success Metrics

Track these in first month:

- **Trial-to-Paid Conversion:** Target 10-20%
- **Monthly Recurring Revenue (MRR):** Target $500+ (25 paid users)
- **Churn Rate:** Target <5%
- **Average Revenue Per User (ARPU):** Target $20-30
- **AI Feature Usage:** % of paid users actually using AI

---

## 🆘 Need Help?

**Full Documentation:**
- Complete guide: `docs/AI-models/PAYMENT_AND_ACCESS_CONTROL.md`
- Access control code: `backend/audioDiagnostic/utils/access_control.py`

**External Resources:**
- Stripe Testing: https://stripe.com/docs/testing
- Stripe Webhooks: https://stripe.com/docs/webhooks

**Key Commands:**
```bash
# Check subscription
python manage.py shell
>>> from django.contrib.auth.models import User
>>> user = User.objects.get(username='USERNAME')
>>> print(user.subscription.plan.display_name)
>>> print(user.subscription.status)

# Check AI usage
>>> from audioDiagnostic.utils.access_control import get_user_ai_usage
>>> print(get_user_ai_usage(user))

# Manually upgrade user
>>> from accounts.models import SubscriptionPlan
>>> basic = SubscriptionPlan.objects.get(name='basic')
>>> user.subscription.plan = basic
>>> user.subscription.status = 'active'
>>> user.subscription.save()
```

---

**Total Time:** 2-3 hours  
**Cost:** $0 to test (use Stripe test mode)  
**Revenue Potential:** $500-2000/month with 25-100 paid users

Ready to implement? Start with Phase 1! 🚀
