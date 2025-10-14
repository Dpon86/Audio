from django.core.management.base import BaseCommand
from audioDiagnostic.models import AudioFile, AudioProject
from celery.result import AsyncResult


class Command(BaseCommand):
    help = 'Reset stuck audio processing tasks to pending status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reset without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
        
        # Reset stuck audio files
        stuck_audio_files = 0
        for af in AudioFile.objects.all():
            if af.status in ['transcribing', 'processing'] and af.task_id:
                # Check if Celery task is actually running
                result = AsyncResult(af.task_id)
                if result.state == 'PENDING':  # Task never started or stuck
                    stuck_audio_files += 1
                    self.stdout.write(
                        f'AudioFile {af.id} ({af.filename}): {af.status} -> pending'
                    )
                    if not dry_run:
                        af.status = 'pending'
                        af.task_id = None
                        af.save()
        
        # Reset stuck projects
        stuck_projects = 0
        for p in AudioProject.objects.all():
            if p.status == 'processing':
                stuck_projects += 1
                self.stdout.write(
                    f'Project {p.id} ({p.title}): processing -> pending'
                )
                if not dry_run:
                    p.status = 'pending'
                    p.save()
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Would reset {stuck_audio_files} audio files and {stuck_projects} projects'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully reset {stuck_audio_files} audio files and {stuck_projects} projects'
                )
            )