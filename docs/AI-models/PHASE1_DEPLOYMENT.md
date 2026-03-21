# AI Feature Setup - Phase 1 Complete ✅

**Date:** March 21, 2026  
**Commit:** 583d0ab  
**Status:** Backend Infrastructure Ready, Needs Server Deployment

---

## ✅ What Was Completed

### 1. AI Service Layer Created
**Location:** `backend/audioDiagnostic/services/ai/`

- **`anthropic_client.py`** (270 lines)
  - Anthropic Claude API wrapper
  - Automatic retry with exponential backoff
  - Rate limiting handling
  - Token counting and cost tracking
  - User monthly cost limit enforcement ($50 default)
  - Cache-based cost tracking per user per month

- **`duplicate_detector.py`** (180 lines)
  - Main service for AI duplicate detection
  - Methods for sentence-level detection
  - Paragraph expansion support
  - PDF comparison support
  - Cost estimation

- **`prompt_templates.py`** (320 lines)
  - System prompts for 3 AI tasks
  - User prompts with variable substitution
  - JSON schema specifications
  - Examples and formatting

- **`cost_calculator.py`** (120 lines)
  - Cost calculation for multiple providers
  - Cost estimates by audio duration
  - Pricing table for Anthropic and OpenAI models

---

### 2. Database Models Added
**Location:** `backend/audioDiagnostic/models.py` (+235 lines)

- **`AIDuplicateDetectionResult`**
  - Stores AI detection results
  - Tracks costs and token usage
  - Links to audio_file and user
  - Stores duplicate_groups JSON
  - Tracks confidence scores
  - User confirmation/modification flags

- **`AIPDFComparisonResult`**
  - Stores PDF comparison results
  - Tracks alignment and discrepancies
  - Coverage percentage calculation
  - Severity breakdown (high/medium/low)
  - Quality assessment

- **`AIProcessingLog`**
  - Audit log for all AI API calls
  - Cost tracking per task type
  - Status monitoring (success/failure/timeout)
  - Privacy flags (user_consented, data_sanitized)
  - Monthly cost calculation helper method

---

### 3. Configuration Updates

**Django Settings** (`myproject/settings.py`)
```python
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
AI_PROVIDER = os.getenv('AI_PROVIDER', 'anthropic')
AI_MODEL = os.getenv('AI_MODEL', 'claude-3-5-sonnet-20241022')
AI_MAX_TOKENS = int(os.getenv('AI_MAX_TOKENS', '4096'))
AI_COST_LIMIT_PER_USER_PER_MONTH = float(os.getenv('AI_COST_LIMIT_PER_USER_PER_MONTH', '50.00'))
```

**Environment Template** (`.env.example`)
```bash
ANTHROPIC_API_KEY=your-anthropic-api-key-here
AI_PROVIDER=anthropic
AI_MODEL=claude-3-5-sonnet-20241022
AI_MAX_TOKENS=4096
AI_COST_LIMIT_PER_USER_PER_MONTH=50.00
```

**Dependencies** (`requirements.txt`)
```
anthropic==0.39.0  # NEW - Added for AI duplicate detection
```

---

### 4. Deployment Script Created
**Location:** `backend/scripts/deploy_ai_feature.sh`

Automated deployment script that:
1. Pulls latest code from GitHub
2. Updates .env with your API key
3. Installs anthropic package
4. Generates database migrations
5. Applies migrations
6. Restarts Celery and Django

---

## 📋 Next Steps - Server Deployment

### Option A: Automated Deployment (Recommended)

SSH into your server and run:

```bash
ssh nickd@82.165.221.205
cd /opt/audioapp
sudo bash scripts/deploy_ai_feature.sh
```

This will:
- ✅ Add your Anthropic API key to .env
- ✅ Install dependencies
- ✅ Run database migrations
- ✅ Restart services

---

### Option B: Manual Deployment

If you prefer manual steps:

#### Step 1: SSH into server
```bash
ssh nickd@82.165.221.205
cd /opt/audioapp
```

#### Step 2: Pull latest code
```bash
sudo git pull origin master
```

#### Step 3: Update .env file
```bash
sudo nano .env
```

Add these lines:
```bash
# Anthropic API Configuration
ANTHROPIC_API_KEY=<your-api-key-here>
AI_PROVIDER=anthropic
AI_MODEL=claude-3-5-sonnet-20241022
AI_MAX_TOKENS=4096
AI_COST_LIMIT_PER_USER_PER_MONTH=50.00
```

**Note:** Replace `<your-api-key-here>` with the actual API key (starts with `sk-ant-api03-...`)

Save and exit (Ctrl+X, Y, Enter)

#### Step 4: Install dependencies
```bash
sudo docker-compose exec audioapp pip install anthropic==0.39.0
```

#### Step 5: Generate migrations
```bash
sudo docker-compose exec audioapp python manage.py makemigrations
```

Expected output: `Migrations for 'audioDiagnostic': ... (3 new models)`

#### Step 6: Apply migrations
```bash
sudo docker-compose exec audioapp python manage.py migrate
```

Expected output: `Applying audioDiagnostic.XXXX... OK`

#### Step 7: Restart services
```bash
sudo docker-compose restart audioapp_celery_worker
sudo docker-compose restart audioapp
```

#### Step 8: Verify deployment
```bash
# Test API key is loaded
sudo docker-compose exec audioapp python -c "from django.conf import settings; print('API Key loaded:', settings.ANTHROPIC_API_KEY[:20] + '...')"

# Test AI client initialization
sudo docker-compose exec audioapp python manage.py shell
>>> from audioDiagnostic.services.ai import AnthropicClient
>>> client = AnthropicClient()
>>> print('✓ Client initialized successfully!')
>>> exit()
```

---

## 🧪 Testing the AI Client

Once deployed, you can test the AI client directly:

```bash
sudo docker-compose exec audioapp python manage.py shell
```

```python
from audioDiagnostic.services.ai import DuplicateDetector, CostCalculator

# Test cost estimation
calc = CostCalculator()
estimate = calc.estimate_cost_for_audio(
    provider='anthropic',
    model='claude-3-5-sonnet-20241022',
    audio_duration_seconds=3600,  # 1 hour
    task='duplicate_detection'
)
print(f"Estimated cost for 1 hour: ${estimate['estimated_cost_usd']}")
print(f"Estimated tokens: {estimate['estimated_total_tokens']}")

# OPTIONAL: Test actual AI call (costs ~$0.001)
# detector = DuplicateDetector()
# response = detector.client.call_api(
#     prompt="Test prompt: Say 'Hello from the AI!'",
#     system_prompt="You are a helpful assistant."
# )
# print(response)
```

---

## 💰 Cost Summary

**Setup:** FREE (no API calls yet)

**Phase 1 Completed:**
- Backend infrastructure: ✅ Ready
- Database models: ✅ Created
- API client: ✅ Configured
- Deployment script: ✅ Ready

**Cost Tracking Features:**
- Per-user monthly limit: $50.00 (configurable)
- Automatic cost calculation on every API call
- Cost stored in cache with monthly reset
- Detailed logging in `AIProcessingLog` model

**Estimated Costs:**
- Sentence-level detection: ~$0.06 per hour of audio
- Paragraph expansion: ~$0.03 per hour
- PDF comparison: ~$0.05 per hour
- **Total workflow: ~$0.14 per hour of audio**

For 100 hours/month: ~$14/month per user

---

## 📂 Files Changed in This Commit

```
backend/.env.example                              (Updated)
backend/requirements.txt                          (Updated)
backend/myproject/settings.py                     (Updated)
backend/audioDiagnostic/models.py                (Updated - 3 new models)
backend/audioDiagnostic/services/ai/__init__.py  (Created)
backend/audioDiagnostic/services/ai/anthropic_client.py (Created - 270 lines)
backend/audioDiagnostic/services/ai/duplicate_detector.py (Created - 180 lines)
backend/audioDiagnostic/services/ai/prompt_templates.py (Created - 320 lines)
backend/audioDiagnostic/services/ai/cost_calculator.py (Created - 120 lines)
backend/scripts/deploy_ai_feature.sh             (Created)
```

**Total:** 10 files changed, 1,230 insertions

---

## 🎯 What's Next

After deployment:

### Immediate (Phase 2 - Week 1):
1. ✅ Deploy to server (you're doing this now)
2. ⏳ Test AI client connection
3. ⏳ Create Celery task for AI detection
4. ⏳ Create API endpoint for frontend

### Near-term (Phase 2-3 - Week 2-4):
- Implement Task 1: Sentence-level duplicate detection
- Build frontend toggle button
- Create waveform markers display
- Add confidence score visualization

### Long-term (Phase 4-6 - Week 5-8):
- Implement paragraph expansion
- Implement PDF comparison
- Complete testing suite
- Production deployment with monitoring

---

## 🔗 Related Documentation

- **Planning:** [docs/AI-models/AI_DUPLICATE_DETECTION_PLAN.md](../../docs/AI-models/AI_DUPLICATE_DETECTION_PLAN.md)
- **Implementation TODO:** [docs/AI-models/AI_DUPLICATE_DETECTION_TODO.md](../../docs/AI-models/AI_DUPLICATE_DETECTION_TODO.md)
- **Data Formats:** [docs/AI-models/TEXT_FORMAT_RECOMMENDATIONS.md](../../docs/AI-models/TEXT_FORMAT_RECOMMENDATIONS.md)
- **Cost Analysis:** [docs/AI-models/SERVER_REQUIREMENTS.md](../../docs/AI-models/SERVER_REQUIREMENTS.md)

---

## ❓ Troubleshooting

**Issue:** `ModuleNotFoundError: No module named 'anthropic'`
**Solution:** Run `sudo docker-compose exec audioapp pip install anthropic==0.39.0`

**Issue:** `ANTHROPIC_API_KEY not found in settings`
**Solution:** Verify .env file has the key, then restart: `sudo docker-compose restart audioapp`

**Issue:** Migration errors
**Solution:** Check Django can import models: `sudo docker-compose exec audioapp python manage.py check`

**Issue:** Cost limit reached
**Solution:** Clear cache: `sudo docker-compose exec audioapp python manage.py shell`
```python
from django.core.cache import cache
cache.clear()
```

---

**Ready to deploy? Run:** `sudo bash scripts/deploy_ai_feature.sh` on the server! 🚀
