"""
CRUD Operations for AutoAgentHire Database
Repository pattern implementation for all models

Note: Pylance type warnings about SQLAlchemy Column assignments are false positives.
SQLAlchemy handles Column -> Python type conversion at runtime.
"""

from typing import List, Optional, Dict, Any, cast
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, and_, or_

from backend.database.models_complete import (
    User, Resume, AgentRun, Application, 
    AgentLog, JobCache, FileStorage, AnalyticsEvent
)


# ═══════════════════════════════════════════════════════════════════════════════
# User CRUD Operations
# ═══════════════════════════════════════════════════════════════════════════════

class UserRepository:
    """Repository for User operations"""
    
    @staticmethod
    def create(db: Session, email: str, hashed_password: str, **kwargs) -> User:
        """Create a new user"""
        user = User(
            email=email,
            hashed_password=hashed_password,
            **kwargs
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def get_by_uuid(db: Session, uuid: str) -> Optional[User]:
        """Get user by UUID"""
        return db.query(User).filter(User.uuid == uuid).first()
    
    @staticmethod
    def update(db: Session, user_id: int, **kwargs) -> Optional[User]:
        """Update user"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            db.commit()
            db.refresh(user)
        return user
    
    @staticmethod
    def delete(db: Session, user_id: int) -> bool:
        """Soft delete user"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.deleted_at = datetime.utcnow()
            user.is_active = False
            db.commit()
            return True
        return False
    
    @staticmethod
    def list_all(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """List all active users"""
        return db.query(User)\
            .filter(User.is_active == True)\
            .offset(skip)\
            .limit(limit)\
            .all()


# ═══════════════════════════════════════════════════════════════════════════════
# Resume CRUD Operations
# ═══════════════════════════════════════════════════════════════════════════════

class ResumeRepository:
    """Repository for Resume operations"""
    
    @staticmethod
    def create(db: Session, user_id: int, filename: str, file_path: str, 
               file_size_bytes: int, file_type: str, **kwargs) -> Resume:
        """Create a new resume"""
        # Deactivate existing resumes for user
        db.query(Resume)\
            .filter(Resume.user_id == user_id, Resume.is_active == True)\
            .update({"is_active": False})
        
        resume = Resume(
            user_id=user_id,
            filename=filename,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            file_type=file_type,
            **kwargs
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        return resume
    
    @staticmethod
    def get_by_id(db: Session, resume_id: int) -> Optional[Resume]:
        """Get resume by ID"""
        return db.query(Resume).filter(Resume.id == resume_id).first()
    
    @staticmethod
    def get_active_for_user(db: Session, user_id: int) -> Optional[Resume]:
        """Get active resume for user"""
        return db.query(Resume)\
            .filter(Resume.user_id == user_id, Resume.is_active == True)\
            .first()
    
    @staticmethod
    def get_all_for_user(db: Session, user_id: int) -> List[Resume]:
        """Get all resumes for user"""
        return db.query(Resume)\
            .filter(Resume.user_id == user_id)\
            .order_by(desc(Resume.created_at))\
            .all()
    
    @staticmethod
    def update(db: Session, resume_id: int, **kwargs) -> Optional[Resume]:
        """Update resume"""
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if resume:
            for key, value in kwargs.items():
                if hasattr(resume, key):
                    setattr(resume, key, value)
            db.commit()
            db.refresh(resume)
        return resume
    
    @staticmethod
    def update_embedding(db: Session, resume_id: int, embedding: List[float], 
                        model: str = "all-MiniLM-L6-v2") -> Optional[Resume]:
        """Update resume embedding"""
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if resume:
            resume.embedding_vector = embedding
            resume.embedding_model = model
            resume.embedding_dimensions = len(embedding)
            resume.embedding_created_at = datetime.utcnow()
            db.commit()
            db.refresh(resume)
        return resume
    
    @staticmethod
    def delete(db: Session, resume_id: int) -> bool:
        """Delete resume"""
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if resume:
            db.delete(resume)
            db.commit()
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# AgentRun CRUD Operations
# ═══════════════════════════════════════════════════════════════════════════════

class AgentRunRepository:
    """Repository for AgentRun operations"""
    
    @staticmethod
    def create(db: Session, user_id: int, resume_id: int, 
               job_role: str, **kwargs) -> AgentRun:
        """Create a new agent run"""
        agent_run = AgentRun(
            user_id=user_id,
            resume_id=resume_id,
            job_role=job_role,
            status='pending',
            **kwargs
        )
        db.add(agent_run)
        db.commit()
        db.refresh(agent_run)
        return agent_run
    
    @staticmethod
    def get_by_id(db: Session, run_id: int) -> Optional[AgentRun]:
        """Get agent run by ID"""
        return db.query(AgentRun).filter(AgentRun.id == run_id).first()
    
    @staticmethod
    def get_by_uuid(db: Session, uuid: str) -> Optional[AgentRun]:
        """Get agent run by UUID"""
        return db.query(AgentRun).filter(AgentRun.uuid == uuid).first()
    
    @staticmethod
    def get_for_user(db: Session, user_id: int, limit: int = 20) -> List[AgentRun]:
        """Get recent agent runs for user"""
        return db.query(AgentRun)\
            .filter(AgentRun.user_id == user_id)\
            .order_by(desc(AgentRun.created_at))\
            .limit(limit)\
            .all()
    
    @staticmethod
    def get_active_runs(db: Session) -> List[AgentRun]:
        """Get all currently running agents"""
        active_statuses = ['pending', 'initializing', 'parsing_resume', 
                          'searching_jobs', 'matching_jobs', 'applying']
        return db.query(AgentRun)\
            .filter(AgentRun.status.in_(active_statuses))\
            .all()
    
    @staticmethod
    def update_status(db: Session, run_id: int, status: str, 
                     phase: Optional[str] = None, progress: Optional[float] = None,
                     **kwargs: Any) -> Optional[AgentRun]:
        """Update agent run status"""
        agent_run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if agent_run:
            setattr(agent_run, 'status', status)
            if phase:
                setattr(agent_run, 'current_phase', phase)
            if progress is not None:
                setattr(agent_run, 'progress_percentage', progress)
            
            # Set timestamps
            if status in ['completed', 'failed', 'cancelled']:
                setattr(agent_run, 'completed_at', datetime.utcnow())
            elif status == 'initializing' and getattr(agent_run, 'started_at', None) is None:
                setattr(agent_run, 'started_at', datetime.utcnow())
            
            for key, value in kwargs.items():
                if hasattr(agent_run, key):
                    setattr(agent_run, key, value)
            
            db.commit()
            db.refresh(agent_run)
        return agent_run
    
    @staticmethod
    def update_metrics(db: Session, run_id: int, **kwargs) -> Optional[AgentRun]:
        """Update agent run metrics"""
        agent_run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if agent_run:
            for key, value in kwargs.items():
                if hasattr(agent_run, key):
                    setattr(agent_run, key, value)
            db.commit()
            db.refresh(agent_run)
        return agent_run


# ═══════════════════════════════════════════════════════════════════════════════
# Application CRUD Operations
# ═══════════════════════════════════════════════════════════════════════════════

class ApplicationRepository:
    """Repository for Application operations"""
    
    @staticmethod
    def create(db: Session, agent_run_id: int, job_url: str, 
               job_title: str, company_name: str, 
               match_score: float, **kwargs) -> Application:
        """Create a new application record"""
        application = Application(
            agent_run_id=agent_run_id,
            job_url=job_url,
            job_title=job_title,
            company_name=company_name,
            match_score=match_score,
            status='pending',
            **kwargs
        )
        db.add(application)
        db.commit()
        db.refresh(application)
        return application
    
    @staticmethod
    def get_by_id(db: Session, app_id: int) -> Optional[Application]:
        """Get application by ID"""
        return db.query(Application).filter(Application.id == app_id).first()
    
    @staticmethod
    def get_for_run(db: Session, run_id: int) -> List[Application]:
        """Get all applications for an agent run"""
        return db.query(Application)\
            .filter(Application.agent_run_id == run_id)\
            .order_by(desc(Application.match_score))\
            .all()
    
    @staticmethod
    def get_for_user(db: Session, user_id: int, limit: int = 100) -> List[Application]:
        """Get all applications for a user (via agent runs)"""
        return db.query(Application)\
            .join(AgentRun)\
            .filter(AgentRun.user_id == user_id)\
            .order_by(desc(Application.created_at))\
            .limit(limit)\
            .all()
    
    @staticmethod
    def update_status(db: Session, app_id: int, status: str, 
                     **kwargs: Any) -> Optional[Application]:
        """Update application status"""
        application = db.query(Application).filter(Application.id == app_id).first()
        if application:
            setattr(application, 'status', status)
            if status == 'applied' and getattr(application, 'applied_at', None) is None:
                setattr(application, 'applied_at', datetime.utcnow())
            
            for key, value in kwargs.items():
                if hasattr(application, key):
                    setattr(application, key, value)
            
            db.commit()
            db.refresh(application)
        return application
    
    @staticmethod
    def get_stats_for_user(db: Session, user_id: int) -> Dict[str, Any]:
        """Get application statistics for user"""
        apps = db.query(Application)\
            .join(AgentRun)\
            .filter(AgentRun.user_id == user_id)\
            .all()
        
        # Use getattr to avoid Pylance Column type issues
        def get_status(app: Application) -> str:
            return str(getattr(app, 'status', ''))
        
        def get_match_score(app: Application) -> float:
            return float(getattr(app, 'match_score', 0) or 0)
        
        return {
            "total": len(apps),
            "applied": len([a for a in apps if get_status(a) == 'applied']),
            "pending": len([a for a in apps if get_status(a) == 'pending']),
            "failed": len([a for a in apps if get_status(a) == 'failed']),
            "skipped": len([a for a in apps if get_status(a) == 'skipped']),
            "avg_match_score": sum(get_match_score(a) for a in apps) / len(apps) if apps else 0,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# AgentLog CRUD Operations
# ═══════════════════════════════════════════════════════════════════════════════

class AgentLogRepository:
    """Repository for AgentLog operations"""
    
    @staticmethod
    def create(db: Session, agent_run_id: int, agent_name: str,
               action: str, message: str, log_level: str = 'INFO',
               **kwargs) -> AgentLog:
        """Create a new log entry"""
        log = AgentLog(
            agent_run_id=agent_run_id,
            agent_name=agent_name,
            action=action,
            message=message,
            log_level=log_level,
            **kwargs
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
    
    @staticmethod
    def get_for_run(db: Session, run_id: int, 
                   level: Optional[str] = None, limit: int = 1000) -> List[AgentLog]:
        """Get logs for an agent run"""
        query = db.query(AgentLog).filter(AgentLog.agent_run_id == run_id)
        if level:
            query = query.filter(AgentLog.log_level == level)
        return query.order_by(desc(AgentLog.timestamp)).limit(limit).all()
    
    @staticmethod
    def get_errors(db: Session, run_id: int) -> List[AgentLog]:
        """Get error logs for an agent run"""
        return db.query(AgentLog)\
            .filter(
                AgentLog.agent_run_id == run_id,
                AgentLog.log_level.in_(['ERROR', 'CRITICAL'])
            )\
            .order_by(desc(AgentLog.timestamp))\
            .all()
    
    @staticmethod
    def bulk_create(db: Session, logs: List[Dict]) -> int:
        """Bulk create log entries"""
        log_objects = [AgentLog(**log) for log in logs]
        db.bulk_save_objects(log_objects)
        db.commit()
        return len(log_objects)


# ═══════════════════════════════════════════════════════════════════════════════
# JobCache CRUD Operations
# ═══════════════════════════════════════════════════════════════════════════════

class JobCacheRepository:
    """Repository for JobCache operations"""
    
    @staticmethod
    def create_or_update(db: Session, job_id: str, job_url: str,
                        job_title: str, company_name: str,
                        **kwargs) -> JobCache:
        """Create or update job cache entry"""
        job = db.query(JobCache).filter(JobCache.job_id == job_id).first()
        
        if job:
            # Update existing
            job.job_title = job_title
            job.company_name = company_name
            job.last_verified_at = datetime.utcnow()
            job.cache_hits += 1
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)
        else:
            # Create new
            job = JobCache(
                job_id=job_id,
                job_url=job_url,
                job_title=job_title,
                company_name=company_name,
                **kwargs
            )
            db.add(job)
        
        db.commit()
        db.refresh(job)
        return job
    
    @staticmethod
    def get_by_job_id(db: Session, job_id: str) -> Optional[JobCache]:
        """Get cached job by LinkedIn job ID"""
        return db.query(JobCache).filter(JobCache.job_id == job_id).first()
    
    @staticmethod
    def search(db: Session, keyword: Optional[str] = None, 
              location: Optional[str] = None, limit: int = 100) -> List[JobCache]:
        """Search cached jobs"""
        query = db.query(JobCache).filter(JobCache.is_active == True)
        
        if keyword:
            query = query.filter(
                or_(
                    JobCache.job_title.ilike(f'%{keyword}%'),
                    JobCache.company_name.ilike(f'%{keyword}%')
                )
            )
        if location:
            query = query.filter(JobCache.location.ilike(f'%{location}%'))
        
        return query.limit(limit).all()
    
    @staticmethod
    def cleanup_expired(db: Session) -> int:
        """Remove expired cache entries"""
        count = db.query(JobCache)\
            .filter(JobCache.expires_at < datetime.utcnow())\
            .delete()
        db.commit()
        return count


# ═══════════════════════════════════════════════════════════════════════════════
# FileStorage CRUD Operations
# ═══════════════════════════════════════════════════════════════════════════════

class FileStorageRepository:
    """Repository for FileStorage operations"""
    
    @staticmethod
    def create(db: Session, filename: str, file_path: str,
              file_size_bytes: int, file_type: str,
              category: str, **kwargs) -> FileStorage:
        """Create a new file storage record"""
        file_record = FileStorage(
            filename=filename,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            file_type=file_type,
            category=category,
            **kwargs
        )
        db.add(file_record)
        db.commit()
        db.refresh(file_record)
        return file_record
    
    @staticmethod
    def get_by_uuid(db: Session, uuid: str) -> Optional[FileStorage]:
        """Get file by UUID"""
        return db.query(FileStorage).filter(FileStorage.uuid == uuid).first()
    
    @staticmethod
    def get_for_entity(db: Session, entity_type: str, 
                      entity_id: int) -> List[FileStorage]:
        """Get files for an entity"""
        return db.query(FileStorage)\
            .filter(
                FileStorage.entity_type == entity_type,
                FileStorage.entity_id == entity_id,
                FileStorage.deleted_at.is_(None)
            )\
            .all()
    
    @staticmethod
    def soft_delete(db: Session, file_id: int) -> bool:
        """Soft delete a file record"""
        file_record = db.query(FileStorage).filter(FileStorage.id == file_id).first()
        if file_record:
            file_record.deleted_at = datetime.utcnow()
            db.commit()
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Analytics CRUD Operations
# ═══════════════════════════════════════════════════════════════════════════════

class AnalyticsRepository:
    """Repository for Analytics operations"""
    
    @staticmethod
    def track_event(db: Session, event_type: str, event_name: str,
                   user_id: Optional[int] = None, **kwargs: Any) -> AnalyticsEvent:
        """Track an analytics event"""
        event = AnalyticsEvent(
            event_type=event_type,
            event_name=event_name,
            user_id=user_id,
            **kwargs
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    
    @staticmethod
    def get_events_for_user(db: Session, user_id: int,
                           days: int = 30, limit: int = 1000) -> List[AnalyticsEvent]:
        """Get events for a user"""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        return db.query(AnalyticsEvent)\
            .filter(
                AnalyticsEvent.user_id == user_id,
                AnalyticsEvent.timestamp > cutoff
            )\
            .order_by(desc(AnalyticsEvent.timestamp))\
            .limit(limit)\
            .all()
