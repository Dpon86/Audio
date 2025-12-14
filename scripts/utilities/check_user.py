#!/usr/bin/env python
import os
import sys
import django

# Add the backend directory to the path
sys.path.append(r'c:\Users\user\Documents\GitHub\Audio repetative detection\backend')

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# Setup Django
django.setup()

# Now import Django models
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from audioDiagnostic.models import AudioProject

print("=== User and Token Check ===")

# Check if unlimited_user exists
try:
    user = User.objects.get(username='unlimited_user')
    print(f"✅ Found user: {user.username} (ID: {user.id})")
    print(f"   Email: {user.email}")
    print(f"   First name: {user.first_name}")
    print(f"   Last name: {user.last_name}")
    
    # Get or create token for this user
    token, created = Token.objects.get_or_create(user=user)
    print(f"   Token: {token.key} {'(newly created)' if created else '(existing)'}")
    
    # Check projects for this user
    projects = AudioProject.objects.filter(user=user)
    print(f"\n=== Projects for {user.username} ===")
    if projects.exists():
        for project in projects:
            print(f"   - {project.title} (ID: {project.id}, Status: {project.status})")
    else:
        print(f"   No projects found for {user.username}")
    
    # Check all projects in the system
    all_projects = AudioProject.objects.all()
    print(f"\n=== All Projects in System ===")
    for project in all_projects:
        print(f"   - {project.title} (ID: {project.id}, User: {project.user.username if project.user else 'None'}, Status: {project.status})")
        
except User.DoesNotExist:
    print("❌ User 'unlimited_user' does not exist")
    
    # Show all users
    all_users = User.objects.all()
    print(f"\n=== All Users in System ===")
    for user in all_users:
        print(f"   - {user.username} (ID: {user.id})")