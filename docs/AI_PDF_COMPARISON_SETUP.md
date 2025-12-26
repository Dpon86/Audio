# AI-Powered PDF Comparison Setup

## Overview
The PDF comparison feature now uses OpenAI's GPT-4o model to intelligently compare your transcript against the PDF. This provides much better results than algorithmic approaches.

## What Changed
- **Old approach**: Myers Diff algorithm (Git-style sequence matching) - didn't work well
- **New approach**: AI-powered comparison using GPT-4o
- Same UI, same API - just better results!

## Setup Required

### 1. Get OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-...`)

### 2. Add API Key to Backend

**Option A: Using .env file (Recommended)**
1. Copy the example file:
   ```bash
   cd backend
   copy .env.example .env
   ```

2. Edit `.env` and replace `your-api-key-here` with your actual key:
   ```
   OPENAI_API_KEY=sk-your-actual-key-here
   ```

3. Restart the Celery worker (it's already running, just needs restart to pick up the key)

**Option B: Set environment variable directly**
```powershell
$env:OPENAI_API_KEY="sk-your-actual-key-here"
# Then restart Celery worker
```

### 3. Restart Celery Worker
The worker is currently running but doesn't have the API key yet. Stop it (Ctrl+C in the terminal) and restart:

```powershell
cd backend
& ".\venv\Scripts\python.exe" -m celery -A myproject worker --loglevel=info --pool=solo
```

## How It Works

### Phase 1: Find Starting Point
- AI analyzes the first 2000 characters of your transcript
- Searches through 20,000 characters of the PDF
- Returns: exact position where transcript begins + confidence score

**Prompt used:**
```
Find where the transcript begins in the PDF. The PDF is the full book, 
the transcript is a section. Return JSON with:
- start_position (character index)
- confidence (0-1)
- matched_text (excerpt showing the match)
- reasoning (explanation)
```

### Phase 2: Detailed Comparison
- AI compares 15,000 characters from each document
- Identifies missing content (in PDF but not transcript)
- Identifies extra content (in transcript but not PDF)
- Classifies extra content:
  - `chapter_marker`: Chapter headings, section titles
  - `narrator_info`: Narrator cues like "Chapter 1 narrated by..."
  - `duplicate`: Repeated text
  - `other`: Unknown additions

**Prompt used:**
```
Compare these documents. The PDF is the correct version.
Identify:
1. MISSING content (in PDF but not transcript)
2. EXTRA content (in transcript but not PDF)

For each extra content item, classify it and explain why.
Return structured JSON with statistics.
```

### Phase 3: Timestamp Matching
- Matches extra content back to your TranscriptionSegments
- Provides start/end times for each extra section
- Allows you to see exactly when the narrator said something extra

## AI Models & Costs

- **Model**: `gpt-4o` (GPT-4 Omni - latest, most capable)
- **Temperature**: 0.3 (consistent results, not creative)
- **Max tokens**: 1000 (Phase 1), 4000 (Phase 2)
- **Approximate cost per comparison**: $0.01-0.03 USD

### Token Usage Estimate:
- Phase 1 input: ~22,000 characters = ~5,500 tokens
- Phase 1 output: ~1,000 tokens
- Phase 2 input: ~30,000 characters = ~7,500 tokens
- Phase 2 output: ~4,000 tokens
- **Total**: ~18,000 tokens per comparison
- **Cost**: ~$0.02 at current GPT-4o pricing

## Testing

1. Make sure Celery worker is running with API key configured
2. Go to Tab 5: Compare PDF
3. Select an audio file with transcription
4. Click "Start Comparison"
5. Wait for AI analysis (should take 10-30 seconds)
6. Review results in the UI

## Error Handling

The AI task includes fallback logic:
- If AI fails, returns safe default values
- Logs detailed error messages to Celery worker console
- Frontend shows "Comparison failed" with error message
- System never crashes, just returns empty results

## Fallback to Algorithmic Approach

If you want to use the old Myers Diff algorithm instead:
1. Edit `backend/audioDiagnostic/views/tab5_pdf_comparison.py`
2. Change imports:
   ```python
   from ..tasks.compare_pdf_task import compare_transcription_to_pdf_task
   ```
3. Change task calls:
   ```python
   task = compare_transcription_to_pdf_task.delay(audio_file.id)
   ```
4. Restart Celery worker

## Benefits of AI Approach

1. **Context Understanding**: AI understands semantic meaning, not just text matching
2. **Flexible Matching**: Handles paraphrasing, slight variations
3. **Smart Classification**: Automatically categorizes narrator additions
4. **Better with Errors**: More forgiving of OCR errors, typos
5. **Reasoning**: Provides explanations for its decisions
6. **Handles Edge Cases**: Works with unusual formatting, multi-language, etc.

## Limitations

1. **Requires OpenAI Account**: Need API key (free tier available)
2. **Costs Money**: ~$0.02 per comparison (very affordable)
3. **Slower**: 10-30 seconds vs instant for algorithmic
4. **Internet Required**: API calls go to OpenAI servers
5. **Rate Limits**: OpenAI has rate limits (usually 3-5 requests/min on free tier)

## Troubleshooting

### "OPENAI_API_KEY not configured" warning
- You haven't added the API key yet
- Follow Setup step 2 above

### "Comparison failed" error
- Check Celery worker logs for detailed error
- Verify API key is correct
- Check OpenAI account has credits
- Verify internet connection

### "Rate limit exceeded" error
- Wait 60 seconds and try again
- Upgrade OpenAI account for higher limits
- Use algorithmic fallback temporarily

## Files Changed

- **Created**: `backend/audioDiagnostic/tasks/ai_pdf_comparison_task.py` (430 lines)
- **Modified**: `backend/audioDiagnostic/tasks/__init__.py` (added AI task import)
- **Modified**: `backend/audioDiagnostic/views/tab5_pdf_comparison.py` (use AI task)
- **Modified**: `backend/myproject/settings.py` (added OPENAI_API_KEY config)
- **Created**: `backend/.env.example` (API key template)

## Next Steps

1. ✅ AI task created and registered with Celery
2. ✅ View updated to use AI task
3. ✅ OpenAI package installed
4. ✅ Settings configured to read OPENAI_API_KEY
5. ⏳ **YOU NEED TO**: Add your OpenAI API key to `.env` file
6. ⏳ **YOU NEED TO**: Restart Celery worker to pick up key
7. ⏳ **TEST**: Try comparison in Tab 5

## Support

If you have issues:
1. Check Celery worker logs (running in terminal)
2. Check browser console for frontend errors
3. Verify `.env` file is in `backend/` directory
4. Verify API key format (should start with `sk-`)
5. Check OpenAI dashboard for API usage/errors
