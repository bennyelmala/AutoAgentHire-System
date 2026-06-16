"""
Database Initialization Script for AutoAgentHire
Creates all tables and sets up initial data
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from backend.database.connection import engine, init_db, db_manager
from backend.database.models_complete import (
    Base, User, Resume, AgentRun, Application, 
    AgentLog, JobCache, FileStorage, AnalyticsEvent
)


def create_tables():
    """Create all database tables"""
    print("📊 Creating database tables...")
    init_db()
    print("✅ All tables created successfully!")


def create_indexes():
    """Create additional indexes for performance"""
    print("📊 Creating additional indexes...")
    
    indexes = [
        # Users indexes
        "CREATE INDEX IF NOT EXISTS idx_users_uuid ON users(uuid)",
        "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC)",
        
        # Resumes indexes
        "CREATE INDEX IF NOT EXISTS idx_resumes_user_id ON resumes(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_resumes_uuid ON resumes(uuid)",
        "CREATE INDEX IF NOT EXISTS idx_resumes_file_hash ON resumes(file_hash)",
        
        # Agent runs indexes
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_user_id ON agent_runs(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status)",
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_created_at ON agent_runs(created_at DESC)",
        
        # Applications indexes
        "CREATE INDEX IF NOT EXISTS idx_applications_agent_run_id ON applications(agent_run_id)",
        "CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status)",
        "CREATE INDEX IF NOT EXISTS idx_applications_match_score ON applications(match_score DESC)",
        "CREATE INDEX IF NOT EXISTS idx_applications_company ON applications(company_name)",
        
        # Agent logs indexes
        "CREATE INDEX IF NOT EXISTS idx_agent_logs_run_id ON agent_logs(agent_run_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_logs_timestamp ON agent_logs(timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_agent_logs_level ON agent_logs(log_level)",
        
        # Job cache indexes
        "CREATE INDEX IF NOT EXISTS idx_job_cache_job_id ON job_cache(job_id)",
        "CREATE INDEX IF NOT EXISTS idx_job_cache_company ON job_cache(company_name)",
        
        # File storage indexes
        "CREATE INDEX IF NOT EXISTS idx_file_storage_uuid ON file_storage(uuid)",
        "CREATE INDEX IF NOT EXISTS idx_file_storage_category ON file_storage(category)",
        
        # Analytics indexes
        "CREATE INDEX IF NOT EXISTS idx_analytics_user_id ON analytics_events(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON analytics_events(timestamp DESC)",
    ]
    
    with engine.connect() as conn:
        for idx_sql in indexes:
            try:
                conn.execute(text(idx_sql))
                conn.commit()
            except Exception as e:
                print(f"⚠️ Index creation warning: {e}")
    
    print("✅ Indexes created!")


def create_views():
    """Create useful database views"""
    print("📊 Creating database views...")
    
    views = [
        # User dashboard statistics
        """
        CREATE VIEW IF NOT EXISTS user_dashboard AS
        SELECT 
            u.id as user_id,
            u.email,
            u.full_name,
            COUNT(DISTINCT ar.id) as total_runs,
            COUNT(DISTINCT a.id) as total_applications
        FROM users u
        LEFT JOIN agent_runs ar ON u.id = ar.user_id
        LEFT JOIN applications a ON ar.id = a.agent_run_id
        GROUP BY u.id, u.email, u.full_name
        """,
        
        # Application summary by company
        """
        CREATE VIEW IF NOT EXISTS company_applications AS
        SELECT 
            company_name,
            COUNT(*) as total_applications,
            AVG(match_score) as avg_match_score
        FROM applications
        GROUP BY company_name
        HAVING COUNT(*) >= 1
        ORDER BY total_applications DESC
        """,
    ]
    
    with engine.connect() as conn:
        for view_sql in views:
            try:
                conn.execute(text(view_sql))
                conn.commit()
            except Exception as e:
                # Views might already exist
                print(f"⚠️ View creation note: {e}")
    
    print("✅ Views created!")


def create_test_user():
    """Create a test user for development"""
    from backend.database.connection import get_db_session
    import hashlib
    
    print("👤 Creating test user...")
    
    with get_db_session() as session:
        # Check if test user exists
        existing = session.query(User).filter(User.email == "test@example.com").first()
        if existing:
            print("✅ Test user already exists")
            return
        
        # Create test user
        test_user = User(
            email="test@example.com",
            hashed_password=hashlib.sha256("test123".encode()).hexdigest(),
            full_name="Test User",
            is_active=True,
            is_verified=True,
            default_job_role="Software Engineer",
            default_location="Remote",
        )
        session.add(test_user)
        session.commit()
        print(f"✅ Test user created (ID: {test_user.id})")


def setup_directories():
    """Create necessary data directories"""
    print("📁 Setting up directories...")
    
    directories = [
        "data/resumes",
        "data/cover_letters",
        "data/screenshots",
        "data/reports",
        "data/vectors",
        "data/logs",
        "data/temp",
    ]
    
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    print("✅ Directories created!")


def initialize_database():
    """Full database initialization"""
    print("\n" + "="*60)
    print("🚀 AUTOAGENTHIRE DATABASE INITIALIZATION")
    print("="*60 + "\n")
    
    # Setup directories
    setup_directories()
    
    # Create tables
    create_tables()
    
    # Create indexes
    create_indexes()
    
    # Create views (SQLite doesn't support all PostgreSQL view features)
    try:
        create_views()
    except Exception as e:
        print(f"⚠️ Views not created (SQLite limitation): {e}")
    
    # Create test user (development only)
    if os.getenv('APP_ENV', 'development') == 'development':
        try:
            create_test_user()
        except Exception as e:
            print(f"⚠️ Test user creation failed: {e}")
    
    print("\n" + "="*60)
    print("✅ DATABASE INITIALIZATION COMPLETE!")
    print("="*60 + "\n")
    
    # Print stats
    print("📊 Database Stats:")
    print(f"   • Database URL: {os.getenv('DATABASE_URL', 'sqlite:///./data/autoagenthire.db')}")
    print(f"   • Tables: 8")
    print(f"   • Indexes: Created")
    print(f"   • Storage: Local")


if __name__ == "__main__":
    initialize_database()
