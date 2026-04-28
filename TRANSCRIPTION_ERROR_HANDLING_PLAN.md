# Transcription Model Error Handling Improvement Plan

**Date**: April 28, 2026  
**Issue**: "Unable to connect to model" error on ISO laptop (April 25, 2026)  
**Goal**: Implement better error logging and model pre-warming

---

## Changes to Implement

### 1. Better Error Logging in Whisper Model Loading

**File**: `backend/audioDiagnostic/tasks/transcription_tasks.py`

**Current Code** (lines 18-22):
```python
def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model("base")
    return _whisper_model
```

**Replace With**:
```python
def _get_whisper_model():
    """
    Load Whisper model with comprehensive error handling and logging.
    
    The model is cached globally per Celery worker process.
    On first load, Whisper downloads ~140MB model files to ~/.cache/whisper/
    
    Raises:
        Exception: If model fails to load with diagnostic information
    """
    global _whisper_model
    if _whisper_model is None:
        try:
            logger.info("Loading Whisper 'base' model...")
            logger.info("Note: First-time load downloads ~140MB to ~/.cache/whisper/")
            
            import time
            start_time = time.time()
            
            _whisper_model = whisper.load_model("base")
            
            load_time = time.time() - start_time
            logger.info(f"✓ Whisper model loaded successfully in {load_time:.2f} seconds")
            
        except Exception as e:
            error_msg = f"Failed to load Whisper model: {str(e)}"
            logger.error("=" * 80)
            logger.error("WHISPER MODEL LOADING FAILED")
            logger.error("=" * 80)
            logger.error(error_msg)
            logger.error("\nTroubleshooting steps:")
            logger.error("1. Check internet connectivity (model downloads on first use)")
            logger.error("2. Verify disk space: df -h")
            logger.error("3. Check cache directory permissions: ls -la ~/.cache/whisper/")
            logger.error("4. Try manual load: docker exec audioapp_celery_worker python -c 'import whisper; whisper.load_model(\"base\")'")
            logger.error("5. For ISO/restricted environments, pre-download model files")
            logger.error("=" * 80)
            
            # Re-raise with clearer message for frontend
            raise Exception(f"Unable to connect to Whisper transcription model: {str(e)}. Check server logs for details.")
    
    return _whisper_model
```

---

### 2. Model Pre-warming Health Check Script

**Create New File**: `backend/management/commands/warmup_whisper.py`

```python
"""
Django management command to pre-warm the Whisper model.
Run this after deployment to ensure the model is loaded and cached.

Usage:
    python manage.py warmup_whisper
    
Or via Docker:
    docker exec audioapp_celery_worker python manage.py warmup_whisper
"""
from django.core.management.base import BaseCommand
import logging
import sys

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Pre-warm the Whisper model to verify it loads successfully'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-reload',
            action='store_true',
            help='Force reload the model even if already cached',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('Whisper Model Pre-warming Health Check'))
        self.stdout.write(self.style.WARNING('=' * 80))
        
        try:
            import whisper
            import time
            import os
            from pathlib import Path
            
            # Check cache directory
            cache_dir = Path.home() / '.cache' / 'whisper'
            self.stdout.write(f"\n1. Checking cache directory: {cache_dir}")
            
            if cache_dir.exists():
                cache_files = list(cache_dir.glob('*.pt'))
                if cache_files:
                    self.stdout.write(self.style.SUCCESS(f"   ✓ Cache exists with {len(cache_files)} model file(s)"))
                    for f in cache_files:
                        size_mb = f.stat().st_size / (1024 * 1024)
                        self.stdout.write(f"     - {f.name} ({size_mb:.1f} MB)")
                else:
                    self.stdout.write(self.style.WARNING("   ⚠ Cache directory exists but empty - model will be downloaded"))
            else:
                self.stdout.write(self.style.WARNING("   ⚠ Cache directory doesn't exist - model will be downloaded (~140MB)"))
            
            # Check disk space
            self.stdout.write(f"\n2. Checking disk space...")
            stat = os.statvfs(str(Path.home()))
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            self.stdout.write(f"   Available space: {free_gb:.2f} GB")
            
            if free_gb < 0.5:
                self.stdout.write(self.style.ERROR("   ✗ Low disk space! Need at least 500MB"))
                return
            else:
                self.stdout.write(self.style.SUCCESS("   ✓ Sufficient disk space"))
            
            # Load the model
            self.stdout.write(f"\n3. Loading Whisper 'base' model...")
            self.stdout.write("   (This may take 1-2 minutes on first run)")
            
            start_time = time.time()
            model = whisper.load_model("base")
            load_time = time.time() - start_time
            
            self.stdout.write(self.style.SUCCESS(f"   ✓ Model loaded in {load_time:.2f} seconds"))
            
            # Test transcription on silence (quick sanity check)
            self.stdout.write(f"\n4. Testing model with sample audio...")
            import numpy as np
            
            # Create 1 second of silence
            sample_rate = 16000
            silence = np.zeros(sample_rate, dtype=np.float32)
            
            test_start = time.time()
            result = model.transcribe(silence)
            test_time = time.time() - test_start
            
            self.stdout.write(self.style.SUCCESS(f"   ✓ Test transcription completed in {test_time:.2f} seconds"))
            self.stdout.write(f"   Result: '{result['text'].strip()}' (expected: empty or noise)")
            
            # Summary
            self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
            self.stdout.write(self.style.SUCCESS('✓ WHISPER MODEL IS READY'))
            self.stdout.write(self.style.SUCCESS('=' * 80))
            self.stdout.write(self.style.SUCCESS(f'Total check time: {time.time() - start_time:.2f} seconds'))
            self.stdout.write(self.style.SUCCESS('The model is now cached and ready for transcription tasks.'))
            self.stdout.write('')
            
        except ImportError as e:
            self.stdout.write(self.style.ERROR('\n✗ Whisper library not installed'))
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            self.stdout.write('Install with: pip install openai-whisper')
            sys.exit(1)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR('\n' + '=' * 80))
            self.stdout.write(self.style.ERROR('✗ WHISPER MODEL HEALTH CHECK FAILED'))
            self.stdout.write(self.style.ERROR('=' * 80))
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            self.stdout.write(self.style.ERROR('\nTroubleshooting:'))
            self.stdout.write('1. Check internet connection (model downloads on first use)')
            self.stdout.write('2. Verify disk space: df -h')
            self.stdout.write('3. Check permissions: ls -la ~/.cache/whisper/')
            self.stdout.write('4. Check logs: docker logs audioapp_celery_worker')
            self.stdout.write('')
            sys.exit(1)
```

---

### 3. Add Model Pre-warming to Celery Worker Startup

**File**: `backend/audioDiagnostic/apps.py`

**Find this section** (around line 10-20):
```python
class AudioDiagnosticConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audioDiagnostic'
    
    def ready(self):
        # Import signals
        from . import signals
```

**Add this after the ready() method**:
```python
    def ready(self):
        # Import signals
        from . import signals
        
        # Pre-warm Whisper model on Celery worker startup
        # Only do this in Celery worker process, not Django web server
        import sys
        if 'celery' in sys.argv:
            self._warmup_whisper_model()
    
    def _warmup_whisper_model(self):
        """Pre-load Whisper model on Celery worker startup"""
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Pre-warming Whisper model on worker startup...")
            
            from .tasks.transcription_tasks import _get_whisper_model
            _get_whisper_model()
            
            logger.info("✓ Whisper model pre-warmed and ready")
        except Exception as e:
            logger.error(f"Failed to pre-warm Whisper model: {str(e)}")
            # Don't fail worker startup, just log the error
            # Model will attempt to load when first transcription task runs
```

---

## Deployment Steps

### On Local Windows Machine

1. **Navigate to local audio app repository**:
   ```powershell
   cd C:\Users\NickD\Documents\Github\Audio
   ```

2. **Create a new branch for this fix**:
   ```powershell
   git checkout -b fix/whisper-error-handling
   ```

3. **Make the code changes**:
   - Edit `backend/audioDiagnostic/tasks/transcription_tasks.py` - update `_get_whisper_model()` function
   - Create `backend/audioDiagnostic/management/commands/warmup_whisper.py` - new file
   - Edit `backend/audioDiagnostic/apps.py` - add pre-warming to `ready()` method

4. **Test locally if possible** (optional, if you have Python/Whisper installed):
   ```powershell
   cd backend
   python manage.py warmup_whisper
   ```

5. **Commit the changes**:
   ```powershell
   git add backend/audioDiagnostic/tasks/transcription_tasks.py
   git add backend/audioDiagnostic/management/commands/warmup_whisper.py
   git add backend/audioDiagnostic/apps.py
   git commit -m "Add better error logging and pre-warming for Whisper model

- Enhanced _get_whisper_model() with detailed error logging
- Added troubleshooting steps for model loading failures
- Created warmup_whisper management command for health checks
- Added automatic model pre-warming on Celery worker startup
- Addresses 'unable to connect to model' error from April 25, 2026"
   ```

6. **Push to GitHub**:
   ```powershell
   git push origin fix/whisper-error-handling
   ```

### On Server (82.165.221.205)

1. **SSH to server**:
   ```bash
   ssh nickd@82.165.221.205
   cd /opt/audioapp
   ```

2. **Pull the changes**:
   ```bash
   # If you merged to master:
   git pull origin master
   
   # OR if still on branch:
   git fetch origin
   git checkout fix/whisper-error-handling
   ```

3. **⚠️ CRITICAL: Rebuild Docker images** (code is baked into images!):
   ```bash
   docker-compose -f docker-compose.production.yml up -d --build backend celery_worker
   ```

4. **Wait for containers to start**:
   ```bash
   # Monitor startup (Ctrl+C to exit)
   docker logs -f audioapp_celery_worker
   
   # You should see:
   # "Pre-warming Whisper model on worker startup..."
   # "✓ Whisper model pre-warmed and ready"
   ```

5. **Verify the model loaded successfully**:
   ```bash
   # Check Celery logs for pre-warming messages
   docker logs audioapp_celery_worker 2>&1 | grep -i "whisper\|model"
   
   # Should show:
   # - "Pre-warming Whisper model on worker startup..."
   # - "Loading Whisper 'base' model..."
   # - "✓ Whisper model loaded successfully in X.XX seconds"
   # - "✓ Whisper model pre-warmed and ready"
   ```

6. **Run manual health check**:
   ```bash
   docker exec audioapp_celery_worker python manage.py warmup_whisper
   ```

7. **Verify transcription works**:
   - Go to https://audio.precisepouchtrack.com
   - Upload a test audio file
   - Try transcribing it
   - Check for better error messages if it fails

---

## Expected Improvements

### Before:
- Generic error: "AudioFile matching query does not exist"
- No indication of why model failed to load
- Silent failures in model initialization

### After:
- ✓ Clear error messages: "Unable to connect to Whisper transcription model: [reason]"
- ✓ Detailed troubleshooting steps in logs
- ✓ Model pre-warmed on worker startup (faster first transcription)
- ✓ Health check command to verify model is working
- ✓ Better logging of model load times and cache status

---

## Troubleshooting

### If Model Still Fails to Load:

1. **Check disk space**:
   ```bash
   docker exec audioapp_celery_worker df -h
   ```

2. **Check cache directory**:
   ```bash
   docker exec audioapp_celery_worker ls -la ~/.cache/whisper/
   ```

3. **Check internet connectivity from container**:
   ```bash
   docker exec audioapp_celery_worker ping -c 3 8.8.8.8
   ```

4. **Manually download model**:
   ```bash
   docker exec audioapp_celery_worker python -c "import whisper; whisper.load_model('base')"
   ```

5. **Check Celery worker logs**:
   ```bash
   docker logs audioapp_celery_worker --tail 100
   ```

### For ISO Laptops:

If using from restricted/ISO environments that can't download models:

1. **Pre-download model on server** and bundle it in Docker image
2. Or copy model files manually to container:
   ```bash
   # On server with internet:
   docker exec audioapp_celery_worker python -c "import whisper; whisper.load_model('base')"
   
   # Copy model files out
   docker cp audioapp_celery_worker:/root/.cache/whisper/ ./whisper_models/
   
   # Copy to ISO laptop container (if running locally)
   docker cp ./whisper_models/. audioapp_celery_worker:/root/.cache/whisper/
   ```

---

## Files Modified

1. ✏️ `backend/audioDiagnostic/tasks/transcription_tasks.py` - Enhanced error logging
2. ➕ `backend/audioDiagnostic/management/commands/warmup_whisper.py` - New health check
3. ✏️ `backend/audioDiagnostic/apps.py` - Auto pre-warming on startup

## Testing Checklist

- [ ] Code changes made locally
- [ ] Changes committed to git
- [ ] Changes pushed to GitHub
- [ ] Pulled changes on server
- [ ] Docker images rebuilt
- [ ] Celery worker restarted successfully
- [ ] Pre-warming messages appear in logs
- [ ] Manual health check runs successfully
- [ ] Test transcription completes
- [ ] Error messages are clearer if failure occurs

---

**Created**: April 28, 2026  
**Ready for implementation**: Yes  
**Estimated time**: 30 minutes (10 min local, 20 min deployment)
