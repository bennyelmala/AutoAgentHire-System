#!/usr/bin/env python3
"""
Test script to add sample application data for testing the Applications page.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta

# Sample applications with proper structure
sample_applications = [
    {
        "user_id": "test_user",
        "result": {
            "url": "https://www.linkedin.com/jobs/view/12345678/",
            "title": "Senior Software Engineer",
            "company": "Google",
            "status": "applied",
            "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
            "match_score": 95
        }
    },
    {
        "user_id": "test_user",
        "result": {
            "url": "https://www.linkedin.com/jobs/view/87654321/",
            "title": "AI/ML Engineer",
            "company": "OpenAI",
            "status": "applied",
            "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
            "match_score": 92
        }
    },
    {
        "user_id": "test_user",
        "result": {
            "url": "https://www.linkedin.com/jobs/view/11223344/",
            "title": "Full Stack Developer",
            "company": "Meta",
            "status": "applied",
            "timestamp": datetime.now().isoformat(),
            "match_score": 88
        }
    },
    {
        "user_id": "test_user",
        "result": {
            "url": "https://www.linkedin.com/jobs/view/99887766/",
            "title": "Backend Engineer",
            "company": "Amazon",
            "status": "applied",
            "timestamp": (datetime.now() - timedelta(hours=5)).isoformat(),
            "match_score": 85
        }
    },
    {
        "user_id": "test_user",
        "result": {
            "url": "https://www.linkedin.com/jobs/view/55443322/",
            "title": "DevOps Engineer",
            "company": "Microsoft",
            "status": "applied",
            "timestamp": (datetime.now() - timedelta(days=3)).isoformat(),
            "match_score": 82
        }
    }
]

def add_sample_applications():
    """Add sample applications to the applications.json file."""
    applications_file = Path("data") / "applications.json"
    applications_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing applications
    existing_apps = []
    if applications_file.exists():
        try:
            with open(applications_file, 'r') as f:
                existing_apps = json.load(f)
        except:
            existing_apps = []
    
    # Add sample applications to the beginning
    all_apps = sample_applications + existing_apps
    
    # Save back to file
    with open(applications_file, 'w') as f:
        json.dump(all_apps, f, indent=2)
    
    print(f"✅ Added {len(sample_applications)} sample applications")
    print(f"📊 Total applications in database: {len(all_apps)}")
    print(f"\nSample applications:")
    for app in sample_applications:
        result = app['result']
        print(f"  • {result['title']} at {result['company']} - {result['match_score']}%")

if __name__ == "__main__":
    add_sample_applications()
