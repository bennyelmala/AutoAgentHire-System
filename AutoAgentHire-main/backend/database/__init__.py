"""
AutoAgentHire Database Module
Complete database architecture for the job automation platform
"""

# Connection and Session Management
from backend.database.connection import (
    engine,
    SessionLocal,
    get_db,
    get_db_session,
    init_db,
    drop_db,
    db_manager,
    DatabaseManager
)

# Complete Models
from backend.database.models_complete import (
    Base,
    User,
    Resume,
    AgentRun,
    Application,
    AgentLog,
    JobCache,
    FileStorage,
    AnalyticsEvent
)

# CRUD Repositories
from backend.database.crud import (
    UserRepository,
    ResumeRepository,
    AgentRunRepository,
    ApplicationRepository,
    AgentLogRepository,
    JobCacheRepository,
    FileStorageRepository,
    AnalyticsRepository
)

# Vector Store (optional - torch may not be compatible with current Python version)
try:
    from backend.database.vector_store import (
        VectorStoreManager,
        vector_store,
        get_embedding,
        calculate_job_match_score,
        find_matching_jobs
    )
except Exception as _vs_err:
    print("[DB] WARNING - Vector store unavailable: " + str(_vs_err).splitlines()[0])
    VectorStoreManager = None
    vector_store = None
    get_embedding = None
    calculate_job_match_score = None
    find_matching_jobs = None

# File Storage
from backend.database.file_storage import (
    FileStorageManager,
    file_storage,
    save_resume,
    save_screenshot,
    get_file
)

# Qdrant Cloud Vector Store
try:
    from backend.database.qdrant_store import QdrantVectorStore, qdrant_store
except Exception as _qd_err:
    print("[QD] WARNING - Qdrant store unavailable: " + str(_qd_err).splitlines()[0])
    QdrantVectorStore = None
    qdrant_store = None

__all__ = [
    # Connection
    'engine',
    'SessionLocal', 
    'get_db',
    'get_db_session',
    'init_db',
    'drop_db',
    'db_manager',
    'DatabaseManager',
    
    # Models
    'Base',
    'User',
    'Resume',
    'AgentRun',
    'Application',
    'AgentLog',
    'JobCache',
    'FileStorage',
    'AnalyticsEvent',
    
    # Repositories
    'UserRepository',
    'ResumeRepository',
    'AgentRunRepository',
    'ApplicationRepository',
    'AgentLogRepository',
    'JobCacheRepository',
    'FileStorageRepository',
    'AnalyticsRepository',
    
    # Vector Store
    'VectorStoreManager',
    'vector_store',
    'get_embedding',
    'calculate_job_match_score',
    'find_matching_jobs',
    
    # File Storage
    'FileStorageManager',
    'file_storage',
    'save_resume',
    'save_screenshot',
    'get_file',

    # Qdrant Cloud Vector Store
    'QdrantVectorStore',
    'qdrant_store',
]
