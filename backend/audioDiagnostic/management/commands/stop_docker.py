"""
Django management command to stop Docker infrastructure
"""
from django.core.management.base import BaseCommand
from audioDiagnostic.services.docker_manager import docker_celery_manager

class Command(BaseCommand):
    help = 'Stop Docker containers and Celery workers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force shutdown even if tasks are running',
        )

    def handle(self, *args, **options):
        self.stdout.write('Stopping Docker infrastructure...')
        
        if options['force']:
            docker_celery_manager.force_shutdown()
        else:
            docker_celery_manager.shutdown_infrastructure()
            
        self.stdout.write(
            self.style.SUCCESS('Docker infrastructure stopped')
        )