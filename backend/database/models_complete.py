"""
AutoAgentHire Complete Database Models
Production-ready SQLAlchemy ORM models for all tables
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime, Date,
    ForeignKey, Index, CheckConstraint, UniqueConstraint, 
    func, event, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid as uuid_module

Base = declarative_base()

# Use JSON type for cross-database compatibility (SQLite, PostgreSQL)
# For PostgreSQL, you can optionally use JSONB for better indexing
JSONB = JSON

# Custom UUID column helper - stores as String(36) for cross-database compatibility
def UUIDColumn(unique=True, nullable=False, default=None, **kwargs):
    """Create a UUID column that works with SQLite and PostgreSQL"""
    if default is None:
        default = lambda: str(uuid_module.uuid4())
    return Column(String(36), unique=unique, nullable=nullable, default=default, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE 1: Users - Complete user management with preferences
# ═══════════════════════════════════════════════════════════════════════════════

class User(Base):
    """User accounts, authentication, and preferences"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid_module.uuid4()))
    
    # Authentication
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    phone = Column(String(50))
    location = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime(timezone=True))
    
    # LinkedIn Integration (Encrypted)
    linkedin_email = Column(String(255))
    linkedin_password_encrypted = Column(Text)
    linkedin_session_token = Column(Text)
    linkedin_session_expires_at = Column(DateTime(timezone=True))
    
    # User Preferences
    default_job_role = Column(String(255))
    default_location = Column(String(255))
    default_experience_level = Column(String(50))
    default_job_types = Column(JSONB, default=[])
    default_skills = Column(JSONB, default=[])
    notification_preferences = Column(JSONB, default={
        "email_on_completion": True,
        "email_on_error": True,
        "daily_summary": False
    })
    
    # Rate Limiting
    applications_this_month = Column(Integer, default=0)
    last_application_reset = Column(Date)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    deleted_at = Column(DateTime(timezone=True))
    
    # Relationships
    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="user", cascade="all, delete-orphan")


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE 2: Resumes - Complete resume storage with embeddings
# ═══════════════════════════════════════════════════════════════════════════════

class Resume(Base):
    """Store uploaded resumes with parsed data and embeddings"""
    __tablename__ = 'resumes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid_module.uuid4()))
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # File Metadata
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    file_type = Column(String(50), nullable=False)
    file_hash = Column(String(64), unique=True)
    storage_provider = Column(String(50), default='local')
    storage_url = Column(Text)
    
    # Raw Content
    raw_text = Column(Text)
    page_count = Column(Integer)
    extraction_method = Column(String(50))
    
    # Parsed Structured Data
    parsed_data = Column(JSONB, default={})
    parsing_confidence_score = Column(Float)
    
    # Extracted Fields
    full_name = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    location = Column(String(255))
    linkedin_url = Column(String(512))
    portfolio_url = Column(String(512))
    
    # Professional Summary
    summary = Column(Text)
    years_of_experience = Column(Integer)
    current_job_title = Column(String(255))
    
    # Skills
    skills = Column(JSONB, default=[])
    skill_categories = Column(JSONB, default={})
    
    # Experience & Education
    experience = Column(JSONB, default=[])
    education = Column(JSONB, default=[])
    certifications = Column(JSONB, default=[])
    
    # Vector Embeddings
    embedding_vector = Column(JSONB)
    embedding_model = Column(String(100))
    embedding_dimensions = Column(Integer)
    embedding_created_at = Column(DateTime(timezone=True))
    
    # Metadata
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=False)
    version = Column(Integer, default=1)
    language = Column(String(10), default='en')
    
    # Quality
    completeness_score = Column(Float)
    quality_issues = Column(JSONB, default=[])
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_used_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="resumes")
    agent_runs = relationship("AgentRun", back_populates="resume")


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE 3: Agent Runs - Track automation execution
# ═══════════════════════════════════════════════════════════════════════════════

class AgentRun(Base):
    """Track agent execution lifecycle, status, and results"""
    __tablename__ = 'agent_runs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid_module.uuid4()))
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    resume_id = Column(Integer, ForeignKey('resumes.id', ondelete='CASCADE'), nullable=False)
    
    # Run Configuration
    job_role = Column(String(255), nullable=False)
    location = Column(String(255))
    experience_level = Column(String(50))
    job_types = Column(JSONB, default=[])
    skills_filter = Column(JSONB, default=[])
    remote_only = Column(Boolean, default=False)
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    company_blacklist = Column(JSONB, default=[])
    
    # Search Configuration
    max_applications = Column(Integer, default=20)
    similarity_threshold = Column(Float, default=0.7)
    search_radius_miles = Column(Integer)
    date_posted_filter = Column(String(20))
    
    # Execution Status
    status = Column(String(50), nullable=False, default='pending')
    current_phase = Column(String(100))
    current_agent = Column(String(100))
    progress_percentage = Column(Float, default=0.0)
    
    # Results Metrics
    jobs_found = Column(Integer, default=0)
    jobs_matched = Column(Integer, default=0)
    jobs_applied = Column(Integer, default=0)
    jobs_skipped = Column(Integer, default=0)
    jobs_failed = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    average_match_score = Column(Float)
    
    # Performance Metrics
    total_duration_seconds = Column(Integer)
    resume_parsing_time_ms = Column(Integer)
    job_search_time_ms = Column(Integer)
    matching_time_ms = Column(Integer)
    application_time_ms = Column(Integer)
    
    # Error Handling
    error_message = Column(Text)
    error_type = Column(String(100))
    error_trace = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # LinkedIn Session
    linkedin_session_id = Column(String(255))
    linkedin_session_active = Column(Boolean, default=False)
    
    # Execution Metadata
    execution_mode = Column(String(50), default='automatic')
    priority = Column(Integer, default=5)
    scheduled_at = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    deleted_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="agent_runs")
    resume = relationship("Resume", back_populates="agent_runs")
    applications = relationship("Application", back_populates="agent_run", cascade="all, delete-orphan")
    logs = relationship("AgentLog", back_populates="agent_run", cascade="all, delete-orphan")


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE 4: Applications - Job application records
# ═══════════════════════════════════════════════════════════════════════════════

class Application(Base):
    """Store individual job application records with match data"""
    __tablename__ = 'applications'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid_module.uuid4()))
    agent_run_id = Column(Integer, ForeignKey('agent_runs.id', ondelete='CASCADE'), nullable=False)
    
    # Job Identification
    job_id = Column(String(255))
    job_url = Column(String(512), nullable=False)
    job_title = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    company_id = Column(String(255))
    company_url = Column(String(512))
    company_size = Column(String(50))
    company_industry = Column(String(255))
    
    # Job Details
    location = Column(String(255))
    is_remote = Column(Boolean, default=False)
    job_type = Column(String(50))
    experience_level = Column(String(50))
    employment_type = Column(String(50))
    seniority_level = Column(String(50))
    
    # Salary
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    salary_currency = Column(String(10), default='USD')
    salary_period = Column(String(20))
    
    # Job Content
    description = Column(Text)
    description_html = Column(Text)
    requirements = Column(Text)
    responsibilities = Column(Text)
    benefits = Column(Text)
    
    # Skills
    required_skills = Column(JSONB, default=[])
    preferred_skills = Column(JSONB, default=[])
    required_education = Column(String(255))
    required_experience_years = Column(Integer)
    
    # Matching Data (RAG Scores)
    match_score = Column(Float, nullable=False)
    embedding_similarity = Column(Float)
    keyword_match_score = Column(Float)
    skill_match_percentage = Column(Float)
    experience_match_score = Column(Float)
    location_match_score = Column(Float)
    
    # Match Details
    matched_skills = Column(JSONB, default=[])
    missing_skills = Column(JSONB, default=[])
    matched_keywords = Column(JSONB, default=[])
    match_explanation = Column(Text)
    
    # Application Status
    status = Column(String(50), nullable=False, default='pending')
    application_method = Column(String(50))
    
    # Application Content
    cover_letter = Column(Text)
    cover_letter_prompt = Column(Text)
    additional_questions = Column(JSONB, default=[])
    resume_version_used = Column(String(100))
    
    # Easy Apply Data
    easy_apply_form_fields = Column(JSONB, default={})
    easy_apply_steps_completed = Column(Integer, default=0)
    easy_apply_total_steps = Column(Integer)
    
    # Error Handling
    error_message = Column(Text)
    error_type = Column(String(100))
    screenshot_path = Column(String(512))
    retry_count = Column(Integer, default=0)
    skip_reason = Column(String(255))
    
    # Engagement Tracking
    viewed_by_company = Column(Boolean, default=False)
    company_response = Column(String(50))
    company_response_date = Column(DateTime(timezone=True))
    interview_requested = Column(Boolean, default=False)
    
    # Job Metadata
    posted_date = Column(Date)
    applicant_count = Column(Integer)
    is_promoted = Column(Boolean, default=False)
    is_urgent = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    applied_at = Column(DateTime(timezone=True))
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    agent_run = relationship("AgentRun", back_populates="applications")


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE 5: Agent Logs - Comprehensive logging
# ═══════════════════════════════════════════════════════════════════════════════

class AgentLog(Base):
    """Comprehensive logging of all agent actions"""
    __tablename__ = 'agent_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_run_id = Column(Integer, ForeignKey('agent_runs.id', ondelete='CASCADE'), nullable=False)
    
    # Log Metadata
    agent_name = Column(String(100), nullable=False)
    log_level = Column(String(20), nullable=False, default='INFO')
    phase = Column(String(100))
    
    # Log Content
    action = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    log_metadata = Column(JSONB, default={})
    
    # Context
    user_id = Column(Integer)
    resume_id = Column(Integer)
    application_id = Column(Integer)
    job_url = Column(String(512))
    
    # Error Details
    error_type = Column(String(255))
    error_code = Column(String(50))
    error_trace = Column(Text)
    error_context = Column(JSONB)
    
    # Performance
    duration_ms = Column(Integer)
    memory_usage_mb = Column(Float)
    cpu_usage_percent = Column(Float)
    
    # Browser Automation
    page_url = Column(Text)
    page_title = Column(Text)
    screenshot_path = Column(String(512))
    html_snapshot_path = Column(String(512))
    
    # API Tracking
    api_endpoint = Column(String(255))
    api_method = Column(String(10))
    api_status_code = Column(Integer)
    api_response_time_ms = Column(Integer)
    
    # LLM Tracking
    llm_model = Column(String(100))
    llm_prompt_tokens = Column(Integer)
    llm_completion_tokens = Column(Integer)
    llm_total_tokens = Column(Integer)
    llm_cost_usd = Column(Float)
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    agent_run = relationship("AgentRun", back_populates="logs")


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE 6: Job Cache - Reduce scraping
# ═══════════════════════════════════════════════════════════════════════════════

class JobCache(Base):
    """Cache job listings to reduce LinkedIn scraping"""
    __tablename__ = 'job_cache'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(255), unique=True, nullable=False)
    job_url = Column(String(512), nullable=False)
    
    # Job Info
    job_title = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    company_id = Column(String(255))
    location = Column(String(255))
    is_remote = Column(Boolean, default=False)
    
    # Classification
    job_type = Column(String(50))
    experience_level = Column(String(50))
    employment_type = Column(String(50))
    
    # Content
    description = Column(Text)
    description_hash = Column(String(64))
    
    # Embedding
    embedding_vector = Column(JSONB)
    embedding_model = Column(String(100))
    embedding_created_at = Column(DateTime(timezone=True))
    
    # Cache Metadata
    is_easy_apply = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    applicant_count = Column(Integer)
    views_count = Column(Integer)
    
    # Cache Management
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    last_verified_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    cache_hits = Column(Integer, default=0)
    
    # Change Tracking
    version = Column(Integer, default=1)
    last_updated_at = Column(DateTime(timezone=True))


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE 7: File Storage - Track all files
# ═══════════════════════════════════════════════════════════════════════════════

class FileStorage(Base):
    """Track all generated and uploaded files"""
    __tablename__ = 'file_storage'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid_module.uuid4()))
    
    # File Metadata
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255))
    file_path = Column(String(512), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    file_type = Column(String(50), nullable=False)
    mime_type = Column(String(100))
    file_hash = Column(String(64), unique=True)
    
    # Storage
    storage_provider = Column(String(50), default='local')
    storage_bucket = Column(String(255))
    storage_key = Column(String(512))
    storage_url = Column(Text)
    cdn_url = Column(Text)
    
    # Category
    category = Column(String(50), nullable=False)
    
    # Polymorphic Relationship
    entity_type = Column(String(50))
    entity_id = Column(Integer)
    
    # Access Control
    is_public = Column(Boolean, default=False)
    access_token = Column(String(255))
    access_expires_at = Column(DateTime(timezone=True))
    
    # Metadata
    file_metadata = Column(JSONB, default={})
    tags = Column(JSONB, default=[])
    
    # Virus Scan
    virus_scan_status = Column(String(50))
    virus_scan_at = Column(DateTime(timezone=True))
    
    # Usage
    download_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE 8: Analytics Events
# ═══════════════════════════════════════════════════════════════════════════════

class AnalyticsEvent(Base):
    """Track user actions and system events"""
    __tablename__ = 'analytics_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    session_id = Column(String(36))
    
    # Event Details
    event_type = Column(String(100), nullable=False)
    event_name = Column(String(255), nullable=False)
    event_category = Column(String(100))
    
    # Event Data
    properties = Column(JSONB, default={})
    
    # Context
    page_url = Column(Text)
    referrer_url = Column(Text)
    user_agent = Column(Text)
    ip_address = Column(String(45))
    
    # Device
    device_type = Column(String(50))
    browser = Column(String(100))
    os = Column(String(100))
    
    # Geolocation
    country = Column(String(100))
    city = Column(String(255))
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
