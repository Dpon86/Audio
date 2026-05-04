#!/usr/bin/env python3
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from audioDiagnostic.models import AudioProject
from django.contrib.auth import get_user_model

User = get_user_model()

# Check if project 21 exists
print("Checking project 21...")
try:
    project = AudioProject.objects.get(id=21)
    print(f"✓ Project exists: {project.title}")
    print(f"  Owner: {project.user.username} (ID: {project.user.id})")
    print(f"  Created: {project.created_at}")
    print(f"  Audio files: {project.audio_files.count()}")
    print(f"  PDF: {project.pdf_file}")
except AudioProject.DoesNotExist:
    print("✗ Project 21 does not exist")
except Exception as e:
    print(f"✗ Error checking project: {e}")
    import traceback
    traceback.print_exc()
