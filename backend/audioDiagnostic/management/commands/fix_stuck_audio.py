"""
Management command to fix audio files stuck in 'processing' status
Usage: python manage.py fix_stuck_audio
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from audioDiagnostic.models import AudioFile, AudioProject

class Command(BaseCommand):
    help = 'Fix audio files and projects stuck in processing status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=1,
            help='Consider stuck if processing for more than X hours (default: 1)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        hours_threshold = options['hours']
        
        self.stdout.write(self.style.WARNING(f'\n{"DRY RUN - " if dry_run else ""}Checking for stuck audio files and projects...'))
        self.stdout.write(f'Threshold: {hours_threshold} hour(s)\n')
        
        cutoff_time = timezone.now() - timedelta(hours=hours_threshold)
        
        # Fix stuck audio files
        stuck_audio_files = AudioFile.objects.filter(
            status__in=['processing', 'transcribing']
        ).filter(
            updated_at__lt=cutoff_time
        )
        
        audio_count = stuck_audio_files.count()
        
        if audio_count > 0:
            self.stdout.write(self.style.WARNING(f'\nFound {audio_count} stuck audio files:'))
            for audio_file in stuck_audio_files:
                time_stuck = timezone.now() - audio_file.updated_at
                hours_stuck = time_stuck.total_seconds() / 3600
                
                self.stdout.write(
                    f'  - Audio ID {audio_file.id}: "{audio_file.title}" '
                    f'(status: {audio_file.status}, stuck for {hours_stuck:.1f}h)'
                )
                
                if not dry_run:
                    # Reset to uploaded status so it can be retried
                    audio_file.status = 'uploaded'
                    audio_file.task_id = None
                    audio_file.error_message = None
                    audio_file.save()
                    self.stdout.write(self.style.SUCCESS(f'    → Reset to "uploaded" status'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ No stuck audio files found'))
        
        # Fix stuck projects
        stuck_projects = AudioProject.objects.filter(
            status__in=['processing', 'transcribing', 'matching_pdf', 'detecting_duplicates']
        ).filter(
            updated_at__lt=cutoff_time
        )
        
        project_count = stuck_projects.count()
        
        if project_count > 0:
            self.stdout.write(self.style.WARNING(f'\nFound {project_count} stuck projects:'))
            for project in stuck_projects:
                time_stuck = timezone.now() - project.updated_at
                hours_stuck = time_stuck.total_seconds() / 3600
                
                self.stdout.write(
                    f'  - Project ID {project.id}: "{project.title}" '
                    f'(status: {project.status}, stuck for {hours_stuck:.1f}h)'
                )
                
                if not dry_run:
                    # Determine appropriate reset status based on project state
                    if project.audio_files.filter(status='transcribed').exists():
                        new_status = 'transcribed'
                    elif project.pdf_file:
                        new_status = 'pending'
                    else:
                        new_status = 'created'
                    
                    project.status = new_status
                    project.error_message = None
                    project.save()
                    self.stdout.write(self.style.SUCCESS(f'    → Reset to "{new_status}" status'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ No stuck projects found'))
        
        # Summary
        total_fixed = audio_count + project_count
        
        if total_fixed > 0:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f'\n📋 Would fix {total_fixed} items. '
                                      f'Run without --dry-run to apply changes.')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'\n✅ Fixed {total_fixed} stuck items!')
                )
                self.stdout.write('\n💡 You can now retry transcription/processing for these items.')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ All audio files and projects are in good state!'))
