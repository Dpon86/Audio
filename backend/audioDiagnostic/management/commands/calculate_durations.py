from django.core.management.base import BaseCommand
from audioDiagnostic.models import AudioProject, TranscriptionSegment
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Calculate duration statistics for existing projects'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project-id',
            type=int,
            help='Calculate durations for specific project ID',
        )

    def handle(self, *args, **options):
        project_id = options.get('project_id')
        
        if project_id:
            projects = AudioProject.objects.filter(id=project_id)
        else:
            # Get all completed projects without duration data
            projects = AudioProject.objects.filter(
                status='completed',
                original_audio_duration__isnull=True
            )
        
        for project in projects:
            self.stdout.write(f"Processing project {project.id}: {project.title}")
            
            # Get confirmed deletions
            if not project.duplicates_confirmed_for_deletion:
                self.stdout.write(self.style.WARNING(f"  No confirmed deletions found, skipping"))
                continue
            
            # Create set of segment IDs to delete
            segments_to_delete = set(
                deletion['segment_id'] 
                for deletion in project.duplicates_confirmed_for_deletion
            )
            
            # Get all segments from original audio
            all_segments = TranscriptionSegment.objects.filter(
                audio_file__project=project,
                is_verification=False
            )
            
            # Calculate original total duration (sum of all segments)
            original_duration = sum(
                (segment.end_time - segment.start_time) 
                for segment in all_segments
            )
            
            # Calculate deleted duration (only confirmed deletions)
            deleted_duration = sum(
                (segment.end_time - segment.start_time)
                for segment in all_segments
                if segment.id in segments_to_delete
            )
            
            # Final duration is original minus deleted
            final_duration = original_duration - deleted_duration
            
            # Save to project
            project.original_audio_duration = original_duration
            project.duration_deleted = deleted_duration
            project.final_audio_duration = final_duration
            project.save()
            
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ Original: {original_duration:.2f}s, "
                f"Deleted: {deleted_duration:.2f}s, "
                f"Final: {final_duration:.2f}s"
            ))
        
        self.stdout.write(self.style.SUCCESS(f"\nProcessed {len(projects)} project(s)"))
