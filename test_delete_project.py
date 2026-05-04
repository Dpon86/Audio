#!/usr/bin/env python
"""Test script to diagnose project deletion issue."""
import os
import sys
import django

# Add the project directory to Python path
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

django.setup()

from audioDiagnostic.models import AudioProject
from rest_framework.test import APIRequestFactory
from audioDiagnostic.views.project_views import ProjectDetailView
from django.contrib.auth import get_user_model

print("=" * 60)
print("TESTING PROJECT 21 DELETION")
print("=" * 60)

# 1. Check if project exists
project = AudioProject.objects.filter(id=21).first()
if not project:
    print("ERROR: Project 21 does not exist")
    sys.exit(1)

print(f"\n1. Project Details:")
print(f"   ID: {project.id}")
print(f"   Title: {project.title}")
print(f"   Owner ID: {project.user_id}")
print(f"   Created: {project.created_at}")
print(f"   PDF File: {project.pdf_file}")
print(f"   Final Audio: {project.final_processed_audio}")

# 2. Check owner exists
User = get_user_model()
try:
    owner = User.objects.get(id=project.user_id)
    print(f"\n2. Owner Details:")
    print(f"   Username: {owner.username}")
    print(f"   ID: {owner.id}")
except User.DoesNotExist:
    print(f"\n2. ERROR: Owner with ID {project.user_id} does not exist!")

# 3. Check related audio files
audio_files = project.audio_files.all()
print(f"\n3. Related Audio Files: {audio_files.count()}")
for af in audio_files[:5]:
    print(f"   - ID {af.id}: {af.filename} ({af.status})")

# 4. Test the DELETE method directly with exception capture
print(f"\n4. Testing DELETE Method with Exception Capture:")
try:
    User = get_user_model()
    user = User.objects.get(id=1)
    print(f"   Using User: {user.username} (ID: {user.id})")
    
    # Import after Django setup
    from audioDiagnostic.views.project_views import ProjectDetailView
    import logging
    
    # Enable DEBUG logging temporarily  
    logging.basicConfig(level=logging.DEBUG, force=True)
    
    # Try to delete directly without going through middleware
    try:
        # Simulate the delete operation step by step
        print("   Step 1: Getting project...")
        project_to_delete = AudioProject.objects.get(id=21)
        print(f"      Project found: {project_to_delete.title}")
        
        print("   Step 2: Collecting file paths...")
        files_to_delete = []
        
        # PDF file
        if project_to_delete.pdf_file:
            try:
                files_to_delete.append(project_to_delete.pdf_file.path)
                print(f"      PDF file path: {project_to_delete.pdf_file.path}")
            except Exception as e:
                print(f"      PDF path error: {e}")
        
        # Audio files
        for audio_file in project_to_delete.audio_files.all():
            if audio_file.file:
                try:
                    files_to_delete.append(audio_file.file.path)
                    print(f"      Audio file path: {audio_file.file.path}")
                except Exception as e:
                    print(f"      Audio path error: {e}")
        
        print(f"   Step 3: Deleting project from database...")
        project_to_delete.delete()
        print("      Project deleted from database!")
        
        print(f"   Step 4: Cleaning up {len(files_to_delete)} physical files...")
        import os
        for file_path in files_to_delete:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"      Deleted: {file_path}")
                else:
                    print(f"      File not found: {file_path}")
            except Exception as e:
                print(f"      Error deleting {file_path}: {e}")
        
        print("   SUCCESS: Project deleted successfully!")
        
    except Exception as e:
        print(f"   EXCEPTION during delete: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"   OUTER EXCEPTION: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)

print("\n" + "=" * 60)
