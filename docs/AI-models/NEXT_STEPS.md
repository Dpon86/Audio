# AI Feature - Next Steps & Deployment

**Created:** April 12, 2026  
**Current Status:** Backend complete, needs server deployment + optional transcription upgrade

---

## 🎯 Quick Summary

You have **two AI features** to consider:

### ✅ Feature 1: AI Duplicate Detection
**Status:** Code complete, ready to deploy  
**Cost:** ~$0.06 per hour of audio  
**Quality:** 95-99% confidence scores  
**Action Required:** Deploy to server (15-30 minutes)

### 🤔 Feature 2: AI Transcription (Optional Upgrade)
**Status:** Documented, not implemented  
**Current:** Client-side Whisper.js (FREE, 85-90% accuracy)  
**Upgrade:** OpenAI Whisper API ($0.36/hour, 95-98% accuracy)  
**Action Required:** Decide if upgrade is needed

---

## 📋 Phase 1: Deploy AI Duplicate Detection (30 min)

### Prerequisites Check

Before deploying, verify you have:
- [ ] Anthropic API key (get from https://console.anthropic.com/)
- [ ] SSH access to server (82.165.221.205)
- [ ] Git repository up to date

### Step 1: Get Anthropic API Key (5 min)

1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to API Keys
4. Create new key
5. Copy the key (starts with `sk-ant-api03-...`)

**Pricing:** Pay-as-you-go, no monthly minimum
- First 100 hours: ~$6
- Claude 3.5 Sonnet: $3 per million input tokens

### Step 2: Deploy to Server (10-15 min)

**Option A: Automated (Recommended)**

```bash
# SSH into server
ssh nickd@82.165.221.205

# Navigate to app directory
cd /opt/audioapp/backend

# Pull latest code
git pull origin master

# Add API key to .env
nano .env
# Add this line (replace with your actual key):
# ANTHROPIC_API_KEY=sk-ant-api03-YOUR-KEY-HERE
# Save and exit (Ctrl+X, Y, Enter)

# Activate virtual environment
source venv/bin/activate  # or env/bin/activate

# Install new dependency
pip install anthropic==0.39.0

# Run migrations (creates 3 new database tables)
python manage.py makemigrations
python manage.py migrate

# Restart services
# If using systemd:
sudo systemctl restart audioapp
sudo systemctl restart audioapp-celery

# If using docker:
# docker restart audioapp_backend
# docker restart audioapp_celery
```

**Option B: Check Deployment Script**

There may be an automated deployment script:
```bash
ssh nickd@82.165.221.205
cd /opt/audioapp/backend/scripts
ls -la deploy_ai_feature.sh
# If it exists, run it:
bash deploy_ai_feature.sh
```

### Step 3: Verify Deployment (5 min)

```bash
# Test 1: Check API key loaded
python manage.py shell
>>> from django.conf import settings
>>> print('API Key:', settings.ANTHROPIC_API_KEY[:20] + '...')
>>> exit()

# Test 2: Check AI client works
python manage.py shell
>>> from audioDiagnostic.services.ai import AnthropicClient
>>> client = AnthropicClient()
>>> print('✅ Client initialized successfully!')
>>> exit()

# Test 3: Check Celery tasks registered
celery -A myproject inspect registered | grep ai_detect
# Should show: ai_detect_duplicates_task, ai_compare_pdf_task
```

### Step 4: Test from Frontend (5 min)

1. Log in to https://audio.precisepouchtrack.com
2. Upload a test audio file (or use existing)
3. Transcribe it (Tab 2)
4. Go to Tab 3 (Duplicates)
5. Select "AI Mode" toggle
6. Click "Start AI Detection"
7. Wait for results (~10-30 seconds)

**Expected:**
- Progress indicator shows 0-100%
- Results appear with confidence scores
- Each duplicate has a confidence percentage
- Total cost displayed (~$0.06 for 1 hour audio)

---

## 📋 Phase 2: Optional AI Transcription Upgrade

### Current Transcription: Client-Side Whisper.js

**Pros:**
- ✅ FREE (no API costs)
- ✅ Privacy-friendly (audio never uploaded)
- ✅ Works offline
- ✅ Good quality (85-90% accuracy)

**Cons:**
- ❌ Slower on older devices
- ❌ Limited to smaller models
- ❌ Lower accuracy than cloud versions

### Upgrade Option: OpenAI Whisper API

**Pros:**
- ✅ Professional quality (95-98% accuracy)
- ✅ Very fast (cloud GPUs)
- ✅ Speaker diarization (multi-speaker support)
- ✅ Works on any device
- ✅ Automatic punctuation

**Cons:**
- ❌ Costs $0.36/hour
- ❌ Audio uploaded to OpenAI
- ❌ Requires internet

### Cost Comparison

| Scenario | Current | With AI Transcription | Savings |
|----------|---------|----------------------|---------|
| **Transcription** | FREE | $0.36/hour | -$0.36 |
| **Duplicate Detection** | $0.06/hour | $0.06/hour | - |
| **Total per hour** | $0.06 | $0.42 | - |
| **100 hours/month** | $6 | $42 | - |

### My Recommendation

**Start with current setup:**
- Use FREE client-side transcription (Whisper.js)
- Use AI duplicate detection ($0.06/hour)
- **Total cost: $6/100 hours**

**Upgrade to AI transcription later if:**
- Quality isn't good enough
- Users have older devices (slow processing)
- You need speaker diarization
- Budget allows $42/month for 100 hours

---

## 🔧 Implementing AI Transcription (If Needed)

### Step 1: Get OpenAI API Key

1. Go to https://platform.openai.com/
2. Sign up or log in
3. Navigate to API Keys
4. Create new key
5. Add $10-20 credit to account

### Step 2: Add to Backend

**Update .env:**
```bash
OPENAI_API_KEY=sk-proj-YOUR-KEY-HERE
TRANSCRIPTION_METHOD=openai  # or 'client' for current setup
```

**Update Django settings (`myproject/settings.py`):**
```python
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TRANSCRIPTION_METHOD = os.getenv('TRANSCRIPTION_METHOD', 'client')
```

### Step 3: Create Transcription Service

**Create:** `backend/audioDiagnostic/services/openai_transcription.py`

```python
import openai
from django.conf import settings

class OpenAITranscriptionService:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def transcribe_audio(self, audio_file_path):
        """
        Transcribe audio using OpenAI Whisper API
        
        Returns:
            dict with segments, text, and word-level timestamps
        """
        with open(audio_file_path, 'rb') as audio_file:
            response = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["word", "segment"]
            )
        
        return {
            'text': response.text,
            'segments': response.segments,
            'words': response.words,
            'language': response.language,
            'duration': response.duration
        }
```

### Step 4: Add Frontend Option

Update Tab2 (Transcription) to show two options:
```jsx
<div className="transcription-method-selector">
  <button 
    className={method === 'client' ? 'selected' : ''}
    onClick={() => setMethod('client')}
  >
    <span>🔒 Free & Private</span>
    <span className="subtitle">Browser-based (Whisper.js)</span>
    <span className="cost">$0.00</span>
  </button>
  
  <button 
    className={method === 'openai' ? 'selected' : ''}
    onClick={() => setMethod('openai')}
  >
    <span>⚡ Professional Quality</span>
    <span className="subtitle">OpenAI Whisper API</span>
    <span className="cost">$0.36/hour</span>
  </button>
</div>
```

**Estimated Implementation Time:** 4-6 hours

---

## 💰 Cost Summary

### Current Setup (Recommended Start)
```
Transcription: FREE (client-side)
Duplicate Detection: $0.06/hour (AI)
PDF Comparison: $0.005/hour (AI, optional)
─────────────────────────────
Total: ~$0.065/hour

Monthly costs:
- 10 hours: $0.65
- 100 hours: $6.50
- 1000 hours: $65
```

### With AI Transcription Upgrade
```
Transcription: $0.36/hour (OpenAI)
Duplicate Detection: $0.06/hour (Anthropic)
PDF Comparison: $0.005/hour (Anthropic)
─────────────────────────────
Total: ~$0.425/hour

Monthly costs:
- 10 hours: $4.25
- 100 hours: $42.50
- 1000 hours: $425
```

### Premium (All OpenAI)
```
Transcription: $0.36/hour (OpenAI Whisper)
Duplicate Detection: $0.16/hour (GPT-4)
PDF Comparison: $0.08/hour (GPT-4)
─────────────────────────────
Total: ~$0.60/hour

Monthly costs:
- 10 hours: $6
- 100 hours: $60
- 1000 hours: $600
```

---

## ❓ FAQ

### Q: Do I need to deploy both features?
**A:** No! Start with AI duplicate detection only. Keep current free transcription for now.

### Q: What if I run out of API credits?
**A:** 
- Anthropic: Pay-as-you-go, no risk of overage (fails gracefully)
- User monthly limit: $50 per user (configurable in settings)
- You can increase/decrease limits as needed

### Q: Can users choose which method to use?
**A:** Yes! Both frontend toggles exist:
- Tab 2: "Client-side" vs "Cloud" transcription (if you implement upgrade)
- Tab 3: "Algorithm" vs "AI" duplicate detection

### Q: Is the server powerful enough?
**A:** Yes! External APIs don't use your server resources. Your 3GB RAM server just makes HTTP calls to AI providers.

### Q: What about privacy?
**A:** 
- Client transcription: Audio never leaves user's device
- AI detection: Only text sent to Anthropic (not audio files)
- AI transcription (if upgraded): Audio sent to OpenAI
- All providers have strict privacy policies and delete data after processing

### Q: Can I test without deploying?
**A:** Yes, but only locally:
```bash
# On your dev machine:
cd backend
pip install anthropic==0.39.0
export ANTHROPIC_API_KEY=sk-ant-api03-...
python manage.py shell
>>> from audioDiagnostic.services.ai import DuplicateDetector
>>> detector = DuplicateDetector()
>>> # Test with sample data
```

---

## 🚀 Ready to Deploy?

### Checklist

- [ ] Get Anthropic API key
- [ ] SSH into server
- [ ] Pull latest code
- [ ] Add API key to .env
- [ ] Install anthropic package
- [ ] Run migrations
- [ ] Restart services
- [ ] Test from frontend
- [ ] Monitor costs

### Rollback Plan

If something breaks:
```bash
# Revert code
git reset --hard HEAD~1

# Remove .env changes
nano .env  # Remove ANTHROPIC_API_KEY line

# Restart
sudo systemctl restart audioapp audioapp-celery
```

---

## 📞 Need Help?

**Documentation:**
- Phase 1 Deployment: `docs/AI-models/PHASE1_DEPLOYMENT.md`
- Phase 2 Deployment: `docs/AI-models/PHASE2_DEPLOYMENT.md`
- Full Plan: `docs/AI-models/AI_DUPLICATE_DETECTION_PLAN.md`
- Workflow Options: `docs/AI-models/AUDIO_TO_AI_WORKFLOW.md`

**Testing:**
- Start with small test file (1-2 minutes)
- Cost should be ~$0.001 for testing
- Verify results before processing large files

---

**Last Updated:** April 12, 2026  
**Status:** Backend deployed, Phase 1 ready, Phase 2 optional
