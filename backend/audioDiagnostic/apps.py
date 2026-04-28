from django.apps import AppConfig
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)


class AudiodiagnosticConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audioDiagnostic'
    
    def ready(self):
        """
        Called when Django app is ready.
        Set up Docker/Celery infrastructure on startup if not in migration mode.
        """
        # Skip infrastructure setup during migrations, tests, or collectstatic
        import sys
        skip_conditions = [
            'migrate' in sys.argv,
            'makemigrations' in sys.argv,
            'collectstatic' in sys.argv,
            'test' in sys.argv,
            'check' in sys.argv,
            '--help' in sys.argv,
            'shell' in sys.argv,
            'dbshell' in sys.argv,
        ]
        
        if any(skip_conditions):
            logger.info("Skipping infrastructure setup during Django management command")
            return

        # Pre-warm Whisper model on Celery worker startup
        if 'celery' in sys.argv:
            self._warmup_whisper_model()

        # Only set up infrastructure when running the actual server
        if 'runserver' in sys.argv or 'rundev' in sys.argv:
            logger.info("Django app ready - initializing Docker/Celery infrastructure...")
            
            # Run infrastructure setup in background thread to avoid blocking startup
            def setup_infrastructure():
                try:
                    # Small delay to let Django fully initialize
                    time.sleep(2)
                    
                    from .services.docker_manager import docker_celery_manager
                    
                    logger.info("Setting up Docker/Celery infrastructure on startup...")
                    if docker_celery_manager.setup_infrastructure():
                        logger.info("✅ Docker/Celery infrastructure ready")
                    else:
                        logger.warning("⚠️ Docker/Celery infrastructure setup failed - will retry on first task")
                        
                except Exception as e:
                    logger.error(f"Error during infrastructure setup: {e}")
                    logger.info("Infrastructure will be set up on first task instead")
            
            # Start setup in background thread
            setup_thread = threading.Thread(target=setup_infrastructure, daemon=True)
            setup_thread.start()

    def _warmup_whisper_model(self):
        """Pre-load Whisper model on Celery worker startup"""
        try:
            logger.info("Pre-warming Whisper model on worker startup...")

            from .tasks.transcription_tasks import _get_whisper_model
            _get_whisper_model()

            logger.info("✓ Whisper model pre-warmed and ready")
        except Exception as e:
            logger.error(f"Failed to pre-warm Whisper model: {str(e)}")
            # Don't fail worker startup, just log the error
            # Model will attempt to load when first transcription task runs
