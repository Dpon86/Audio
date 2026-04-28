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
