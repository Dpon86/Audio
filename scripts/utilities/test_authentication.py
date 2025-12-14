#!/usr/bin/env python3
"""
Test script to verify authentication is working properly for the audio detection system
"""

import requests
import json

def test_authentication():
    """Test that authentication is required for project endpoints"""
    base_url = "http://localhost:8000/api"
    
    print("🔐 Testing Authentication Requirements...")
    print("=" * 50)
    
    # Test 1: Try to access projects without authentication
    print("📋 Test 1: Access projects without authentication")
    try:
        response = requests.get(f"{base_url}/projects/")
        if response.status_code == 401:
            print("✅ PASS: Projects endpoint requires authentication (401 Unauthorized)")
        else:
            print(f"❌ FAIL: Expected 401, got {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("⚠️  WARNING: Server not running. Start with ./start-dev.bat")
        return
    
    # Test 2: Login with unlimited user
    print("\n👤 Test 2: Login with unlimited user")
    login_data = {
        'username': 'unlimited_user',
        'password': 'AudioUnlimited2025!'
    }
    
    try:
        login_response = requests.post(f"{base_url}/auth/login/", json=login_data)
        if login_response.status_code == 200:
            token_data = login_response.json()
            token = token_data.get('token')
            print(f"✅ PASS: Login successful, token received: {token[:20]}...")
            
            # Test 3: Access projects with authentication
            print("\n📁 Test 3: Access projects with authentication")
            headers = {'Authorization': f'Token {token}'}
            auth_response = requests.get(f"{base_url}/projects/", headers=headers)
            
            if auth_response.status_code == 200:
                projects_data = auth_response.json()
                project_count = len(projects_data.get('projects', []))
                print(f"✅ PASS: Authenticated access successful, found {project_count} projects")
                
                # Show project details
                for project in projects_data.get('projects', []):
                    print(f"   - {project['title']} (Status: {project['status']})")
            else:
                print(f"❌ FAIL: Authenticated request failed with status {auth_response.status_code}")
                
        else:
            print(f"❌ FAIL: Login failed with status {login_response.status_code}")
            print(f"Response: {login_response.text}")
            
    except requests.exceptions.ConnectionError:
        print("⚠️  WARNING: Server not running. Start with ./start-dev.bat")
    
    print("\n" + "=" * 50)
    print("🎉 Authentication test completed!")
    print("\n🔐 LOGIN CREDENTIALS:")
    print("Username: unlimited_user")
    print("Password: AudioUnlimited2025!")
    print("Frontend: http://localhost:3000")

if __name__ == "__main__":
    test_authentication()