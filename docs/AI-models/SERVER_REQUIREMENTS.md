# Server Specifications & Requirements for AI Integration

**Created:** March 21, 2026  
**Current Server:** 4GB RAM  
**Target Feature:** AI-Powered Duplicate Detection

---

## 🖥️ Current Server Configuration

### Existing Setup
```
Server: VPS (Virtual Private Server)
RAM: 4GB
CPU: Shared (likely 2-4 vCPUs)
Storage: Unknown (likely 50-100GB SSD)
OS: Linux (likely Ubuntu 20.04/22.04)
Location: 82.165.221.205
```

### Current Services Running
```
- Django (Web Application)
- PostgreSQL (Database)
- Redis (Cache & Celery Broker)
- Celery Workers (Background Tasks)
- Nginx (Web Server)
- Docker (Container Runtime)
```

### Memory Usage (Estimated)
```
PostgreSQL:  ~500MB
Redis:       ~200MB
Django:      ~300MB
Celery:      ~400MB
Nginx:       ~50MB
System:      ~500MB
---
Total:       ~1.95GB / 4GB
Available:   ~2GB for new features
```

**Conclusion:** ⚠️ **Limited headroom for AI models** (only ~2GB available)

---

## 🚫 What CANNOT Run on 4GB RAM

### Local Language Models (LLMs)

❌ **GPT-family models:**
- GPT-2 Small (124M params): Needs ~2GB RAM
- GPT-2 Medium (355M params): Needs ~4GB RAM
- GPT-2 Large (774M params): Needs ~8GB RAM
- GPT-3 (175B params): Impossible (needs 350GB+ RAM)

❌ **LLaMA models:**
- LLaMA 7B: Needs ~14GB RAM (minimum)
- LLaMA 13B: Needs ~26GB RAM
- LLaMA 70B: Needs ~140GB RAM

❌ **Mistral models:**
- Mistral 7B: Needs ~14GB RAM
- Mixtral 8x7B: Needs ~90GB RAM

### Embedding Models

❌ **Large embedding models:**
- BERT-base: Needs ~2GB RAM
- BERT-large: Needs ~4GB RAM
- Sentence Transformers: Needs ~2-4GB RAM

### Audio Transcription Models

❌ **Whisper models (local):**
- Whisper Tiny: Needs ~1GB RAM (might work)
- Whisper Small: Needs ~2GB RAM (tight fit)
- Whisper Medium: Needs ~5GB RAM (won't work)
- Whisper Large: Needs ~10GB RAM (definitely won't work)

---

## ✅ Recommended Solution: External AI APIs

### Why External APIs?

**Pros:**
- ✅ **Zero additional RAM required**
- ✅ **No GPU required**
- ✅ **State-of-the-art models** (GPT-4, Claude 3)
- ✅ **Fast processing** (10-30s per hour of audio)
- ✅ **Automatic updates** (models improve over time)
- ✅ **Scalable** (handles traffic spikes)
- ✅ **Reliable** (99.9% uptime SLA)
- ✅ **Cost-effective for low-medium usage**

**Cons:**
- ❌ Ongoing API costs
- ❌ Requires internet connection
- ❌ Data sent to third party
- ❌ Rate limits (can be mitigated)

### Recommended API Providers

#### Option 1: OpenAI (GPT-4 Turbo) ⭐ **RECOMMENDED**

**Model:** `gpt-4-turbo-preview` (latest)

**Pricing:**
- Input: $10 / 1M tokens
- Output: $30 / 1M tokens

**Performance:**
- Speed: 10-20 seconds per request
- Context: 128,000 tokens (very large)
- Accuracy: Excellent (95-99%)

**Estimated Costs:**
```
1 hour of audio transcription ≈ 10,000 tokens input + 2,000 tokens output
Cost per hour: (10,000 * $10 / 1M) + (2,000 * $30 / 1M) = $0.10 + $0.06 = $0.16

Monthly estimates:
- 10 hours: ~$1.60
- 100 hours: ~$16
- 1000 hours: ~$160
```

**Pros:**
- ✅ Best performance
- ✅ Largest context window
- ✅ Most feature-rich
- ✅ Excellent documentation

**Cons:**
- ❌ More expensive than alternatives
- ❌ Stricter rate limits
- ❌ Privacy concerns (OpenAI retains data for 30 days)

---

#### Option 2: Anthropic Claude 3 Sonnet 💰 **BEST VALUE**

**Model:** `claude-3-sonnet-20240229`

**Pricing:**
- Input: $3 / 1M tokens
- Output: $15 / 1M tokens

**Performance:**
- Speed: 5-15 seconds per request
- Context: 200,000 tokens (largest available)
- Accuracy: Very Good (90-95%)

**Estimated Costs:**
```
1 hour of audio ≈ 10,000 tokens input + 2,000 tokens output
Cost per hour: (10,000 * $3 / 1M) + (2,000 * $15 / 1M) = $0.03 + $0.03 = $0.06

Monthly estimates:
- 10 hours: ~$0.60
- 100 hours: ~$6
- 1000 hours: ~$60
```

**Pros:**
- ✅ **62% cheaper than GPT-4**
- ✅ Largest context window (200K tokens)
- ✅ Very fast
- ✅ Better privacy (no training on user data)
- ✅ Excellent at reasoning

**Cons:**
- ❌ Slightly lower accuracy than GPT-4
- ❌ Less feature-rich API

---

#### Option 3: Anthropic Claude 3 Haiku 🏃 **FASTEST/CHEAPEST**

**Model:** `claude-3-haiku-20240307`

**Pricing:**
- Input: $0.25 / 1M tokens
- Output: $1.25 / 1M tokens

**Performance:**
- Speed: 2-5 seconds per request (very fast)
- Context: 200,000 tokens
- Accuracy: Good (85-90%)

**Estimated Costs:**
```
1 hour of audio ≈ 10,000 tokens input + 2,000 tokens output
Cost per hour: (10,000 * $0.25 / 1M) + (2,000 * $1.25 / 1M) = $0.0025 + $0.0025 = $0.005

Monthly estimates:
- 10 hours: ~$0.05
- 100 hours: ~$0.50
- 1000 hours: ~$5
```

**Pros:**
- ✅ **Extremely cheap** (97% cheaper than GPT-4)
- ✅ Very fast
- ✅ Good for simple tasks

**Cons:**
- ❌ Lower accuracy for complex semantic analysis
- ❌ Not recommended for nuanced duplicate detection

---

### Recommendation: Tiered Approach

**Use multiplemodels based on task complexity:**

```python
def choose_ai_model(task_complexity, user_budget):
    if task_complexity == 'simple' or user_budget == 'low':
        return 'claude-3-haiku'  # Cheap & fast
    
    elif task_complexity == 'medium':
        return 'claude-3-sonnet'  # Balanced
    
    elif task_complexity == 'complex' or user_budget == 'premium':
        return 'gpt-4-turbo'  # Best accuracy
```

**Example usage:**
- **Sentence-level duplicates:** Claude 3 Haiku (simple pattern matching)
- **Semantic paragraph analysis:** Claude 3 Sonnet (context-aware)
- **PDF comparison with nuance:** GPT-4 Turbo (high accuracy required)

---

## 🔧 Server Configuration Changes Needed

### 1. Environment Variables

Add to `/opt/audioapp/.env`:

```bash
# AI API Keys
OPENAI_API_KEY=sk-proj-...your-key-here...
ANTHROPIC_API_KEY=sk-ant-...your-key-here...

# AI Service Configuration
AI_PROVIDER=anthropic  # or 'openai'
AI_MODEL=claude-3-sonnet-20240229
AI_MAX_TOKENS=4096
AI_TEMPERATURE=0.2  # Lower = more deterministic
AI_TIMEOUT_SECONDS=60

# Cost Limits
AI_MAX_COST_PER_USER_MONTHLY=50.00  # USD
AI_COST_WARNING_THRESHOLD=40.00  # USD
AI_COST_ALERT_EMAIL=admin@example.com

# Rate Limiting
AI_RATE_LIMIT_PER_MINUTE=10
AI_RATE_LIMIT_PER_HOUR=100
AI_RATE_LIMIT_PER_DAY=500
```

### 2. Python Dependencies

Add to `requirements.txt`:

```txt
# AI/ML Libraries
openai==1.13.3
anthropic==0.18.1
tiktoken==0.6.0  # Token counting for OpenAI
```

### 3. Django Settings

Add to `backend/myproject/settings.py`:

```python
# AI Configuration
AI_SETTINGS = {
    'PROVIDER': os.getenv('AI_PROVIDER', 'anthropic'),
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
    'MODEL': os.getenv('AI_MODEL', 'claude-3-sonnet-20240229'),
    'MAX_TOKENS': int(os.getenv('AI_MAX_TOKENS', 4096)),
    'TEMPERATURE': float(os.getenv('AI_TEMPERATURE', 0.2)),
    'TIMEOUT': int(os.getenv('AI_TIMEOUT_SECONDS', 60)),
    'MAX_COST_PER_USER_MONTHLY': Decimal(os.getenv('AI_MAX_COST_PER_USER_MONTHLY', '50.00')),
}
```

### 4. Memory Optimization

Current services can stay as-is, but consider:

```bash
# Reduce PostgreSQL cache (if needed for more headroom)
# Edit /etc/postgresql/*/main/postgresql.conf
shared_buffers = 256MB  # Reduce from 512MB if needed

# Optimize Redis memory
# Edit /etc/redis/redis.conf
maxmemory 128mb
maxmemory-policy allkeys-lru
```

### 5. Celery Queue Configuration

Add dedicated queue for AI tasks:

```python
# backend/myproject/celery.py

CELERY_TASK_ROUTES = {
    'audioDiagnostic.tasks.ai_tasks.*': {'queue': 'ai'},
    'audioDiagnostic.tasks.duplicate_tasks.*': {'queue': 'duplicates'},
    # ... existing routes
}

# Start additional worker for AI tasks
# docker-compose.yml or systemd service:
# celery -A myproject worker -Q ai -c 2 -n ai_worker@%h
```

---

## 📊 Cost Projections & Budget Planning

### Scenario Analysis

#### Scenario 1: Small Audiobook Producer
**Usage:** 20 hours of audio per month

**Using Claude 3 Sonnet:**
- Cost per hour: $0.06
- Monthly cost: 20 × $0.06 = **$1.20**
- Annual cost: $1.20 × 12 = **$14.40**

**Verdict:** ✅ Very affordable

---

#### Scenario 2: Medium Audiobook Publisher
**Usage:** 200 hours of audio per month

**Using Claude 3 Sonnet:**
- Cost per hour: $0.06
- Monthly cost: 200 × $0.06 = **$12**
- Annual cost: $12 × 12 = **$144**

**With 20% using GPT-4 for complex analysis:**
- Claude cost: 160 hrs × $0.06 = $9.60
- GPT-4 cost: 40 hrs × $0.16 = $6.40
- **Total monthly: $16**
- **Annual: $192**

**Verdict:** ✅ Reasonable for business use

---

#### Scenario 3: Large Production House
**Usage:** 1000 hours of audio per month

**Using Claude 3 Sonnet:**
- Cost per hour: $0.06
- Monthly cost: 1000 × $0.06 = **$60**
- Annual cost: $60 × 12 = **$720**

**With 30% using GPT-4:**
- Claude cost: 700 hrs × $0.06 = $42
- GPT-4 cost: 300 hrs × $0.16 = $48
- **Total monthly: $90**
- **Annual: $1,080**

**Verdict:** ⚠️ Consider local model if processing >1500 hrs/month

---

### Break-Even Analysis

**When does local model make sense?**

**Local server with GPU:**
- Server upgrade: $50/month (16GB RAM + T4 GPU)
- One-time setup: ~$500 (development time)
- Ongoing maintenance: ~$100/month (DevOps time)

**Total:** $150/month

**Break-even point:** 
- Claude 3 Sonnet: $150 / $0.06 = **2,500 hours/month**
- GPT-4 Turbo: $150 / $0.16 = **937 hours/month**

**Recommendation:** 
- **< 1000 hrs/month:** Use external API (Claude 3 Sonnet)
- **> 2500 hrs/month:** Consider local model (requires server upgrade)

---

## 🎯 Recommended Server Configuration

### Keep Current 4GB Server + External API

**Configuration:**
```
Server: VPS with 4GB RAM (no changes needed)
AI: External API (Anthropic Claude 3 Sonnet)
Cost: $0.06 per hour of audio analyzed
Monthly budget: $10-50 for typical usage
```

**This approach:**
- ✅ Works with existing hardware
- ✅ Zero infrastructure changes
- ✅ Fast implementation (days, not weeks)
- ✅ Predictable costs
- ✅ Professional results
- ✅ Scales automatically

---

### Alternative: Upgrade Server (Only if >1500 hrs/month)

**If processing very high volumes:**

```
Server Upgrade Options:

Option A: CPU-Only (Minimal)
- RAM: 8GB
- CPU: 4 vCPUs
- Storage: 100GB SSD
- Cost: +$10-20/month
- Can run: Small models (DistilBERT, small embeddings)
- Performance: Slow (60-120s per hour of audio)

Option B: Entry GPU (Recommended if upgrading)
- RAM: 16GB
- GPU: NVIDIA T4 (16GB VRAM)
- CPU: 4-8 vCPUs
- Storage: 200GB SSD
- Cost: +$50-80/month
- Can run: Mistral 7B, LLaMA 7B, Whisper Medium
- Performance: Fast (5-15s per hour of audio)

Option C: Production GPU (High Volume)
- RAM: 32GB
- GPU: NVIDIA A10 (24GB VRAM)
- CPU: 8-16 vCPUs
- Storage: 500GB SSD
- Cost: +$150-250/month
- Can run: LLaMA 13B, GPT-J, Whisper Large
- Performance: Very Fast (2-5s per hour of audio)
```

**Recommendation:** **DON'T upgrade yet**
- Start with external API
- Monitor usage and costs for 3-6 months
- Only upgrade if costs consistently exceed $150/month

---

## 🔒 Security & Compliance

### Data Privacy with External APIs

**What gets sent to AI:**
- ✅ Transcription text (necessary)
- ✅ Timestamps (necessary)
- ✅ PDF text (necessary for comparison)
- ❌ Audio files (NEVER sent)
- ❌ User personal info (NOT sent)
- ❌ Filenames (sanitized before sending)

### Provider Privacy Policies

**OpenAI:**
- Retains data for 30 days
- May use for training (unless opted out)
- Subject to US data laws

**Anthropic:**
- Does NOT train on user data
- Better for privacy-conscious users
- Subject to US data laws

**Recommendation:** Use **Anthropic Claude** for better privacy

### Compliance Measures

```python
# Anonymize before sending to AI
def sanitize_for_ai(transcript_data):
    """Remove PII before sending to external API"""
    
    # Remove filenames
    transcript_data['metadata']['filename'] = 'audio_file_' + str(transcript_data['audio_file_id'])
    
    # Remove user info
    if 'user_id' in transcript_data['metadata']:
        del transcript_data['metadata']['user_id']
    
    # Strip potentially sensitive metadata
    safe_fields = ['duration', 'language', 'segments']
    transcript_data = {k: v for k, v in transcript_data.items() if k in safe_fields}
    
    return transcript_data
```

---

## ✅ Final Recommendations

### For Current 4GB Server

**DO:**
- ✅ Use external AI API (Anthropic Claude 3 Sonnet)
- ✅ Implement cost tracking and limits
- ✅ Start with tiered model approach
- ✅ Monitor usage monthly
- ✅ Cache results to avoid re-processing
- ✅ Add user consent for AI processing

**DON'T:**
- ❌ Try to run local LLMs (not enough RAM)
- ❌ Upgrade server until proven necessary
- ❌ Send raw user data to APIs (sanitize first)
- ❌ Process everything with most expensive model

### Implementation Checklist

- [ ] Sign up for Anthropic API
- [ ] Get API key
- [ ] Add environment variables
- [ ] Install Python packages (openai, anthropic)
- [ ] Implement AI client wrapper
- [ ] Add cost tracking
- [ ] Set per-user limits
- [ ] Test with small audio file
- [ ] Monitor costs for 1 month
- [ ] Adjust model selection based on results

**Estimated Setup Time:** 4-6 hours  
**Estimated Monthly Cost (100 hrs):** $6-12  
**Break-even vs Server Upgrade:** 2,500 hours/month

---

**Next Steps:** Proceed with [AI_DUPLICATE_DETECTION_TODO.md](AI_DUPLICATE_DETECTION_TODO.md) to begin implementation!
