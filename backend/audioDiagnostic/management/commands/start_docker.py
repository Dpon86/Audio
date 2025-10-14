"""
Django management command to start Docker infrastructure
"""
from django.core.management.base import BaseCommand
from audioDiagnostic.services.docker_manager import docker_celery_manager

class Command(BaseCommand):
    help = 'Start Docker containers and Celery workers for audio processing'

    def handle(self, *args, **options):
        self.stdout.write('Starting Docker infrastructure...')
        
        if docker_celery_manager.setup_infrastructure():
            self.stdout.write(
                self.style.SUCCESS('Successfully started Docker infrastructure')
            )
        else:
            self.stdout.write(
                self.style.ERROR('Failed to start Docker infrastructure')
            )