"""
LangGraph State Schema for AutoAgentHire Multi-Agent Workflow
Defines the state model used throughout the agent execution pipeline.
"""
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class WorkflowStatus(str, Enum):
    """Overall workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class AgentState(TypedDict):
    """
    Core state model for the LangGraph multi-agent workflow.
    Each node reads from and writes to this shared state.
    
    State Flow:
    1. Input Phase: user_id, resume_text, preferences
    2. Resume Parsing: parsed_resume, skills, experience
    3. Job Search: job_listings
    4. Matching: ranked_jobs
    5. Application: submitted_applications
    
    Note: All fields are required to avoid TypedDict access errors.
    Optional fields use Optional[T] type hints.
    """
    
    # === Input Parameters (Required) ===
    user_id: str  # Unique user identifier
    session_id: str  # Workflow session ID
    resume_text: Optional[str]  # Raw resume text (if provided)
    resume_file_path: Optional[str]  # Path to uploaded resume file
    
    # === User Preferences (Required) ===
    target_roles: List[str]  # e.g., ["machine_learning_engineer", "data_scientist"]
    desired_locations: List[str]  # e.g., ["San Francisco, CA", "Remote"]
    min_salary: Optional[int]  # Minimum acceptable salary
    max_applications: int  # Max jobs to apply to (default: 10)
    
    # === Resume Intelligence Output (Required) ===
    parsed_resume: Optional[Dict[str, Any]]  # Structured resume data
    extracted_skills: List[str]  # Skills extracted from resume
    experience_years: Optional[float]  # Total years of experience
    education: List[Dict[str, Any]]  # Education history
    
    # === Job Search Output (Required) ===
    job_listings: List[Dict[str, Any]]  # Raw job search results
    search_queries: List[str]  # Queries used for search
    total_jobs_found: int  # Total jobs discovered
    
    # === Matching & Ranking Output (Required) ===
    ranked_jobs: List[Dict[str, Any]]  # Jobs with match scores
    top_matches: List[Dict[str, Any]]  # Best N matches (filtered)
    filtered_count: int  # Jobs remaining after filtering
    
    # === Application Output (Required) ===
    submitted_applications: List[Dict[str, Any]]  # Successfully submitted apps
    application_errors: List[Dict[str, Any]]  # Failed applications
    cover_letters: Dict[str, str]  # Generated cover letters (job_id -> text)
    
    # === Workflow Control (Required) ===
    workflow_status: WorkflowStatus  # Overall status
    current_step: str  # Current node/agent executing
    errors: List[str]  # Error messages encountered
    warnings: List[str]  # Warning messages
    
    # === Metadata (Required) ===
    started_at: datetime  # Workflow start time
    completed_at: Optional[datetime]  # Workflow end time
    execution_time_seconds: Optional[float]  # Total execution time
    
    # === Configuration (Required) ===
    config: Dict[str, Any]  # Additional runtime configuration
    dry_run: bool  # If True, don't actually apply to jobs


class AgentInput(TypedDict):
    """
    Simplified input model for starting a workflow.
    Gets converted to full AgentState internally.
    """
    user_id: str
    resume_text: Optional[str]
    resume_file_path: Optional[str]
    target_roles: List[str]
    desired_locations: Optional[List[str]]
    min_salary: Optional[int]
    max_applications: Optional[int]
    dry_run: Optional[bool]


class AgentOutput(TypedDict):
    """
    Simplified output model returned to API consumers.
    Extracted from final AgentState.
    """
    session_id: str
    workflow_status: str
    total_jobs_found: int
    applications_submitted: int
    application_errors: int
    execution_time_seconds: float
    top_matches: List[Dict[str, Any]]
    submitted_applications: List[Dict[str, Any]]
    errors: List[str]
    warnings: List[str]


def create_initial_state(input_data: AgentInput) -> AgentState:
    """
    Create initial AgentState from user input.
    Sets defaults and initializes collections.
    """
    from uuid import uuid4
    
    # Build state as a dictionary that conforms to AgentState
    state: AgentState = {
        # Input
        "user_id": input_data["user_id"],
        "session_id": str(uuid4()),
        "resume_text": input_data.get("resume_text"),
        "resume_file_path": input_data.get("resume_file_path"),
        
        # Preferences
        "target_roles": input_data["target_roles"],
        "desired_locations": input_data.get("desired_locations") or [],
        "min_salary": input_data.get("min_salary"),
        "max_applications": input_data.get("max_applications") or 10,
        
        # Initialize resume intelligence output
        "parsed_resume": None,
        "extracted_skills": [],
        "experience_years": None,
        "education": [],
        
        # Initialize empty collections
        "extracted_skills": [],
        "job_listings": [],
        "search_queries": [],
        "total_jobs_found": 0,
        "ranked_jobs": [],
        "top_matches": [],
        "filtered_count": 0,
        "submitted_applications": [],
        "application_errors": [],
        "cover_letters": {},
        
        # Workflow control
        "workflow_status": WorkflowStatus.PENDING,
        "current_step": "initialized",
        "errors": [],
        "warnings": [],
        
        # Metadata
        "started_at": datetime.now(),
        "completed_at": None,
        "execution_time_seconds": None,
        
        # Config
        "config": {},
        "dry_run": input_data.get("dry_run") or False,
    }
    
    return state


def extract_output(state: AgentState) -> AgentOutput:
    """
    Extract simplified output model from final state.
    """
    execution_time = None
    started_at = state.get("started_at")
    completed_at = state.get("completed_at")
    
    if started_at and completed_at:
        delta = completed_at - started_at
        execution_time = delta.total_seconds()
    
    # Safely extract workflow status
    workflow_status = state.get("workflow_status", WorkflowStatus.PENDING)
    if isinstance(workflow_status, WorkflowStatus):
        workflow_status_str = workflow_status.value
    else:
        workflow_status_str = str(workflow_status)
    
    return AgentOutput(
        session_id=state.get("session_id", "unknown"),
        workflow_status=workflow_status_str,
        total_jobs_found=state.get("total_jobs_found", 0),
        applications_submitted=len(state.get("submitted_applications", [])),
        application_errors=len(state.get("application_errors", [])),
        execution_time_seconds=execution_time or 0,
        top_matches=state.get("top_matches", []),
        submitted_applications=state.get("submitted_applications", []),
        errors=state.get("errors", []),
        warnings=state.get("warnings", []),
    )
