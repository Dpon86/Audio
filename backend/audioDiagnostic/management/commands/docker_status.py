"""
Django management command to check Docker infrastructure status
"""
from django.core.management.base import BaseCommand
from audioDiagnostic.services.docker_manager import docker_celery_manager

class Command(BaseCommand):
    help = 'Check status of Docker containers and Celery workers'

    def handle(self, *args, **options):
        status = docker_celery_manager.get_status()
        
        self.stdout.write(f"Infrastructure Running: {status['is_setup']}")
        self.stdout.write(f"Active Tasks: {status['active_tasks']}")
        
        if status['task_ids']:
            self.stdout.write("Task IDs:")
            for task_id in status['task_ids']:
                self.stdout.write(f"  - {task_id}")
        else:
            self.stdout.write("No active tasks")