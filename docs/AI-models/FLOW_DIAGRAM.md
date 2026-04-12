# User Authentication & Payment Flow Diagram

This document visualizes the complete user journey from signup to AI feature access.

---

## 🔄 Complete User Journey

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: USER REGISTRATION                                      │
│                                                                  │
│  User visits app → Clicks "Sign Up" → Fills form               │
│                                                                  │
│  POST /api/auth/register/                                       │
│  {                                                              │
│    "username": "john",                                          │
│    "email": "john@example.com",                                 │
│    "password": "SecurePass123!",                                │
│    "first_name": "John",                                        │
│    "last_name": "Doe"                                           │
│  }                                                              │
│                                                                  │
│  Backend creates:                                               │
│  ✅ User account (Django User)                                  │
│  ✅ UserProfile (additional info)                               │
│  ✅ Stripe Customer (payment system)                            │
│  ✅ UserSubscription (Free Trial, 7 days)                       │
│                                                                  │
│  Response:                                                       │
│  {                                                              │
│    "token": "abc123...",              ← Auth token              │
│    "user": {...},                                               │
│    "subscription": {                                            │
│      "plan": "Free Trial",                                      │
│      "status": "trialing",                                      │
│      "trial_end": "2026-04-19",                                 │
│      "ai_features": {                                           │
│        "ai_duplicate_detection": false,  ← No AI access         │
│        "ai_transcription": false,                               │
│        "ai_monthly_budget": 0.00                                │
│      }                                                          │
│    }                                                            │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: FREE TRIAL PERIOD (7 DAYS)                            │
│                                                                  │
│  User can:                                                       │
│  ✅ Upload audio files                                          │
│  ✅ Transcribe audio (client-side, free)                        │
│  ✅ Use algorithm-based duplicate detection                     │
│  ✅ Create PDFs                                                 │
│  ✅ Manage projects (up to 3)                                   │
│  ✅ Process 60 minutes of audio                                 │
│                                                                  │
│  User CANNOT:                                                    │
│  ❌ Use AI duplicate detection (paywalled)                      │
│  ❌ Use AI transcription (paywalled)                            │
│  ❌ Use AI PDF comparison (paywalled)                           │
│                                                                  │
│  If user clicks "Use AI Detection":                             │
│  → Frontend sends: POST /api/ai-detection/detect/              │
│  → Backend checks: @require_ai_feature('ai_duplicate_detection')│
│  → Returns: 402 Payment Required                                │
│       {                                                         │
│         "error": "Your Free Trial does not include AI features",│
│         "upgrade_required": true,                               │
│         "recommended_plan": "basic"                             │
│       }                                                         │
│  → Frontend shows: "Upgrade to Basic Plan ($19.99/mo)"         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: USER DECIDES TO UPGRADE                                │
│                                                                  │
│  User clicks "Upgrade" → Views pricing page                     │
│                                                                  │
│  ┌──────────────────┬──────────────────┬──────────────────┐    │
│  │   Free Trial     │   Basic Plan     │   Pro Plan       │    │
│  │   $0 (7 days)    │   $19.99/mo      │   $49.99/mo      │    │
│  ├──────────────────┼──────────────────┼──────────────────┤    │
│  │ ❌ No AI         │ ✅ AI Duplicates │ ✅ All AI        │    │
│  │ 60 min audio     │ 300 min audio    │ 1000 min audio   │    │
│  │ 3 projects       │ 10 projects      │ Unlimited        │    │
│  │ 0.5 GB storage   │ 2 GB storage     │ 10 GB storage    │    │
│  └──────────────────┴──────────────────┴──────────────────┘    │
│                                                                  │
│  User selects "Basic Plan" → Clicks "Subscribe"                │
│                                                                  │
│  Frontend:                                                       │
│  POST /api/auth/checkout/                                       │
│  {                                                              │
│    "plan_id": 2,               ← Basic Plan ID                 │
│    "billing_cycle": "monthly"                                   │
│  }                                                              │
│                                                                  │
│  Backend:                                                        │
│  1. Gets/creates Stripe customer for user                       │
│  2. Creates Stripe Checkout session                             │
│  3. Returns checkout URL                                         │
│                                                                  │
│  Response:                                                       │
│  {                                                              │
│    "checkout_url": "https://checkout.stripe.com/c/pay/cs_..."  │
│  }                                                              │
│                                                                  │
│  Frontend redirects user to Stripe Checkout page                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: STRIPE CHECKOUT                                        │
│                                                                  │
│  User on Stripe Checkout:                                       │
│  1. Sees plan details: "Basic Plan - $19.99/month"             │
│  2. Enters payment info:                                        │
│     - Card: 4242 4242 4242 4242 (test card)                    │
│     - Expiry: 12/28                                             │
│     - CVC: 123                                                  │
│  3. Clicks "Subscribe"                                          │
│                                                                  │
│  Stripe processes payment:                                      │
│  ✅ Charges $19.99                                              │
│  ✅ Creates subscription                                        │
│  ✅ Sends webhook to your server                                │
│                                                                  │
│  Webhook Event: checkout.session.completed                      │
│  → Sent to: https://audio.precisepouchtrack.com/api/auth/      │
│              stripe-webhook/                                     │
│                                                                  │
│  User redirected back to your app:                              │
│  → Success URL: https://audio.precisepouchtrack.com/dashboard  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: WEBHOOK PROCESSING                                     │
│                                                                  │
│  Stripe webhook arrives at backend:                             │
│                                                                  │
│  POST /api/auth/stripe-webhook/                                 │
│  {                                                              │
│    "type": "checkout.session.completed",                        │
│    "data": {                                                    │
│      "object": {                                                │
│        "customer": "cus_ABC123",                                │
│        "subscription": "sub_DEF456",                            │
│        "metadata": {                                            │
│          "user_id": 42,                                         │
│          "plan_id": 2                                           │
│        }                                                        │
│      }                                                          │
│    }                                                            │
│  }                                                              │
│                                                                  │
│  Backend webhook handler:                                       │
│  1. Verifies signature (security)                               │
│  2. Finds user by ID                                            │
│  3. Updates UserSubscription:                                   │
│     - plan = Basic Plan                                         │
│     - status = 'active'                                         │
│     - stripe_subscription_id = 'sub_DEF456'                     │
│     - current_period_start = now                                │
│     - current_period_end = now + 30 days                        │
│  4. Creates BillingHistory record:                              │
│     - transaction_type = 'payment'                              │
│     - amount = 19.99                                            │
│     - stripe_invoice_id = 'in_GHI789'                           │
│                                                                  │
│  ✅ Subscription activated!                                     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 6: USER NOW HAS AI ACCESS                                │
│                                                                  │
│  User returns to app dashboard:                                 │
│                                                                  │
│  ┌────────────────────────────────────────────────────┐        │
│  │  Welcome back, John!                                │        │
│  │                                                      │        │
│  │  Subscription: Basic Plan 💳                        │        │
│  │  Status: Active ✅                                  │        │
│  │  Renews: May 12, 2026                               │        │
│  │                                                      │        │
│  │  AI Budget: $20.00 / month                          │        │
│  │  Used: $0.00 | Remaining: $20.00 💰                │        │
│  └────────────────────────────────────────────────────┘        │
│                                                                  │
│  User uploads audio → Goes to Tab 3 (Duplicates)               │
│  → Toggles "AI Mode" ON                                        │
│  → Clicks "Start AI Detection"                                 │
│                                                                  │
│  Frontend sends:                                                 │
│  POST /api/ai-detection/detect/                                 │
│  Authorization: Token abc123...                                 │
│                                                                  │
│  Backend checks:                                                 │
│  1. @require_ai_feature('ai_duplicate_detection')               │
│     → Checks: user.subscription.plan.ai_duplicate_detection     │
│     → Result: True ✅                                           │
│                                                                  │
│  2. check_ai_cost_limit(user, $0.06)                            │
│     → Current usage: $0.00                                      │
│     → Monthly limit: $20.00                                     │
│     → Remaining: $20.00                                         │
│     → Result: Allowed ✅                                        │
│                                                                  │
│  3. Start Celery task:                                          │
│     → ai_detect_duplicates_task.delay(...)                      │
│     → Returns: task_id = "abc-123-def-456"                      │
│                                                                  │
│  Response:                                                       │
│  {                                                              │
│    "success": true,                                             │
│    "task_id": "abc-123-def-456",                                │
│    "estimated_cost": 0.06,                                      │
│    "remaining_budget": 19.94                                    │
│  }                                                              │
│                                                                  │
│  Frontend polls task status:                                    │
│  GET /api/ai-detection/status/abc-123-def-456/                 │
│  → Progress: 0% → 25% → 50% → 75% → 100%                      │
│                                                                  │
│  AI detection complete! 🎉                                      │
│  → Found 12 duplicate groups                                    │
│  → Cost: $0.06                                                  │
│  → Budget tracking updated: $19.94 remaining                    │
│  → Results displayed on waveform with confidence scores         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  ONGOING: MONTHLY BILLING & USAGE TRACKING                      │
│                                                                  │
│  Every month (automatic):                                       │
│  1. Stripe charges $19.99 on billing date                       │
│  2. Sends webhook: invoice.payment_succeeded                    │
│  3. Backend creates BillingHistory record                       │
│  4. Resets monthly usage counters                               │
│  5. Resets AI budget (new $20.00 allowance)                     │
│                                                                  │
│  If payment fails:                                              │
│  1. Stripe retries (3 attempts over 2 weeks)                    │
│  2. Sends webhook: invoice.payment_failed                       │
│  3. Backend updates:                                            │
│     - subscription.status = 'past_due'                          │
│     - AI features blocked                                       │
│  4. User receives email: "Payment failed"                       │
│  5. After 3 failed attempts:                                    │
│     - subscription.status = 'canceled'                          │
│     - All premium features blocked                              │
│     - User downgraded to Free Trial                             │
│                                                                  │
│  User can cancel anytime:                                       │
│  POST /api/auth/cancel-subscription/                            │
│  → Stripe: cancel_at_period_end = true                          │
│  → User keeps access until end of billing period                │
│  → Then auto-downgrades to Free Trial                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔒 Access Control Logic

```python
# Every AI API call goes through this flow:

@api_view(['POST'])
@permission_classes([IsAuthenticated])          # ← Check 1: Must be logged in
@require_ai_feature('ai_duplicate_detection')   # ← Check 2: Must have feature in plan
def ai_detect_duplicates_view(request):
    
    # Check 3: Must have AI budget remaining
    allowed, remaining, message = check_ai_cost_limit(
        request.user,
        estimated_cost=0.06
    )
    
    if not allowed:
        return Response({
            'error': 'Monthly AI budget exceeded',
            'upgrade_required': True
        }, status=402)
    
    # All checks passed → Start AI processing
    task = ai_detect_duplicates_task.delay(...)
    
    return Response({'task_id': task.id})
```

**Access Control Checks:**

1. **Authentication** (`@permission_classes([IsAuthenticated])`)
   - Has valid token?
   - User exists?

2. **Feature Access** (`@require_ai_feature('ai_duplicate_detection')`)
   - Has active subscription?
   - Subscription status is 'active' or 'trialing'?
   - Plan includes `ai_duplicate_detection = True`?

3. **Budget Check** (`check_ai_cost_limit()`)
   - Current month usage < monthly limit?
   - This request won't exceed limit?
   - Returns remaining budget

4. **Process AI Request**
   - Start Celery task
   - Track actual cost
   - Update usage cache

---

## 📊 Data Flow

```
User Action → Frontend → Backend → Stripe → Database → AI Service
                 ↓          ↓        ↓         ↓          ↓
              Token     Permission  Payment  Subscription Cost
              Check     Check       Process  Update      Tracking
```

**Key Database Tables:**

```sql
-- User account
auth_user (Django built-in)
  - id, username, email, password

-- Extended profile
accounts_userprofile
  - user_id, company_name, phone, preferences

-- Subscription info
accounts_usersubscription
  - user_id, plan_id, status, stripe_customer_id,
    stripe_subscription_id, current_period_end

-- Plan definitions
accounts_subscriptionplan
  - name, price_monthly, price_yearly,
    ai_duplicate_detection, ai_transcription,
    ai_monthly_cost_limit, max_projects, etc.

-- Payment history
accounts_billinghistory
  - user_id, transaction_type, amount,
    stripe_invoice_id, created_at

-- Usage tracking
accounts_usagetracking
  - user_id, projects_created, audio_minutes_processed,
    storage_used_mb, period_start, period_end

-- AI processing logs
audioDiagnostic_aiprocessinglog
  - user_id, audio_file_id, ai_provider, ai_model,
    input_tokens, output_tokens, cost_usd, status
```

**Cache (Redis):**

```
ai_cost_{user_id}_{year}_{month} → Total AI spending this month
progress:{task_id} → Celery task progress (0-100)
status:{task_id} → Celery task status message
```

---

## 🎯 Summary

**The Complete Flow:**

1. User signs up → Free trial created (7 days)
2. User tries AI feature → Blocked (402 Payment Required)
3. User upgrades → Stripe checkout
4. Payment succeeds → Webhook updates subscription
5. User tries AI again → Allowed! ✅
6. AI processes → Cost tracked
7. Monthly billing → Automatic renewal
8. Usage tracked → Stays within limits

**Security:**
- ✅ Webhook signature verification
- ✅ Three-level access control (auth + feature + budget)
- ✅ Token-based authentication
- ✅ HTTPS only for payments
- ✅ No credit card data stored (Stripe handles it)

**Monitoring:**
- ✅ Billing history (all transactions)
- ✅ Usage tracking (projects, audio, storage)
- ✅ AI cost tracking (per user, per month)
- ✅ Processing logs (every AI call logged)

**User Experience:**
- ✅ Clear upgrade prompts
- ✅ Trial period to test
- ✅ Budget visibility
- ✅ Smooth payment flow
- ✅ Immediate feature access after payment

---

**Implementation Time:** 2-3 hours  
**Monthly Maintenance:** ~1 hour (monitor webhooks, support)  
**Revenue Potential:** $500-2000/month (25-100 paid users)
