"""
Advanced Job Filtering System
Provides strict role-based filtering, filled job detection, and freshness validation
to ensure only relevant, open, and recent jobs reach the frontend.

This module implements a production-grade filtering pipeline that:
1. Uses strict role taxonomy for accurate matching
2. Detects filled/closed jobs reliably
3. Validates job freshness
4. Normalizes data efficiently
5. Prevents irrelevant jobs from reaching users
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ==========================================
# ROLE TAXONOMY (LinkedIn-Aligned)
# ==========================================

ROLE_TAXONOMY = {
    "machine_learning_engineer": {
        "required": ["machine learning", "ml engineer", "machine learning engineer"],
        "optional": ["deep learning", "tensorflow", "pytorch", "keras", "scikit-learn", 
                    "neural networks", "mlops", "model deployment"],
        "exclude": ["intern", "junior intern", "entry level intern"]
    },
    "data_scientist": {
        "required": ["data scientist", "data science"],
        "optional": ["statistics", "pandas", "numpy", "sql", "python", "r", 
                    "data analysis", "predictive modeling", "a/b testing"],
        "exclude": ["intern", "junior intern"]
    },
    "ai_engineer": {
        "required": ["ai engineer", "artificial intelligence engineer", "ai/ml engineer"],
        "optional": ["llm", "nlp", "computer vision", "gpt", "bert", "transformers",
                    "generative ai", "rag", "embeddings"],
        "exclude": ["intern", "junior intern"]
    },
    "software_engineer": {
        "required": ["software engineer", "software developer"],
        "optional": ["python", "java", "javascript", "react", "nodejs", "backend",
                    "frontend", "fullstack", "microservices", "api"],
        "exclude": ["intern", "junior intern"]
    },
    "data_engineer": {
        "required": ["data engineer", "data engineering"],
        "optional": ["spark", "hadoop", "kafka", "airflow", "etl", "data pipeline",
                    "sql", "nosql", "aws", "azure", "gcp"],
        "exclude": ["intern", "junior intern"]
    },
    "mlops_engineer": {
        "required": ["mlops", "ml ops", "machine learning operations"],
        "optional": ["kubernetes", "docker", "ci/cd", "model deployment", "monitoring",
                    "mlflow", "kubeflow", "sagemaker"],
        "exclude": ["intern", "junior intern"]
    },
    "research_scientist": {
        "required": ["research scientist", "research engineer"],
        "optional": ["phd", "publications", "deep learning", "computer vision", "nlp",
                    "reinforcement learning", "optimization"],
        "exclude": ["intern", "junior intern"]
    },
    "backend_engineer": {
        "required": ["backend engineer", "backend developer", "server engineer"],
        "optional": ["api", "rest", "graphql", "microservices", "database", "sql",
                    "python", "java", "golang", "nodejs"],
        "exclude": ["intern", "junior intern"]
    },
    "frontend_engineer": {
        "required": ["frontend engineer", "frontend developer", "ui engineer"],
        "optional": ["react", "vue", "angular", "javascript", "typescript", "css",
                    "html", "redux", "webpack"],
        "exclude": ["intern", "junior intern"]
    },
    "fullstack_engineer": {
        "required": ["fullstack", "full stack", "full-stack"],
        "optional": ["react", "nodejs", "python", "javascript", "api", "database",
                    "frontend", "backend"],
        "exclude": ["intern", "junior intern"]
    },
    "cloud_engineer": {
        "required": ["cloud engineer", "cloud architect", "cloud developer"],
        "optional": ["aws", "azure", "gcp", "google cloud", "kubernetes", "docker",
                    "terraform", "cloudformation", "devops", "infrastructure"],
        "exclude": ["intern", "junior intern"]
    },
    "devops_engineer": {
        "required": ["devops", "devops engineer", "site reliability", "sre"],
        "optional": ["kubernetes", "docker", "jenkins", "ci/cd", "terraform",
                    "ansible", "aws", "azure", "monitoring", "automation"],
        "exclude": ["intern", "junior intern"]
    }
}

# Default role for general searches
DEFAULT_ROLE = {
    "required": [],
    "optional": ["software", "engineer", "developer", "data", "ai", "ml"],
    "exclude": ["intern"]
}

# ==========================================
# FILLED / CLOSED JOB DETECTION
# ==========================================

FILLED_KEYWORDS = [
    "no longer accepting applications",
    "position filled",
    "job has expired",
    "hiring completed",
    "this job is closed",
    "applications closed",
    "position has been filled",
    "we are no longer",
    "job posting closed",
    "opening closed",
    "role filled",
    "we've filled this position",
    "application deadline passed"
]

# ==========================================
# CONFIGURATION
# ==========================================

MAX_JOB_AGE_DAYS = 30  # Only show jobs posted within last 30 days
MIN_MATCH_SCORE = 50    # Minimum matching score to include job


# ==========================================
# CORE FILTERING FUNCTIONS
# ==========================================

def normalize(text: str) -> str:
    """
    Normalize text for consistent matching.
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized lowercase text
    """
    return text.lower().strip() if text else ""


def matches_role(job: Dict[str, Any], target_role: str) -> bool:
    """
    Check if a job matches the target role using strict taxonomy.
    
    Args:
        job: Job dictionary with title, description, etc.
        target_role: Target role key from ROLE_TAXONOMY
        
    Returns:
        True if job matches role requirements, False otherwise
    """
    # Get role rules (default to generic if not found)
    role_rules = ROLE_TAXONOMY.get(target_role, DEFAULT_ROLE)
    
    # Combine title and description for comprehensive matching
    title = normalize(job.get("title", ""))
    description = normalize(job.get("description", ""))
    text_blob = f"{title} {description}"
    
    # Check exclusions first (most efficient)
    if role_rules.get("exclude"):
        for exclude_keyword in role_rules["exclude"]:
            if exclude_keyword in text_blob:
                logger.debug(f"Job excluded due to keyword: {exclude_keyword}")
                return False
    
    # Required keywords: At least ONE must match (they are alternatives)
    if role_rules.get("required"):
        required_match = any(keyword in text_blob for keyword in role_rules["required"])
        if not required_match:
            logger.debug(f"Job missing all required keywords")
            return False
    
    # Optional keywords improve confidence (at least one should match)
    if role_rules.get("optional"):
        optional_match = any(opt in text_blob for opt in role_rules["optional"])
        if not optional_match:
            logger.debug("Job has no optional keyword matches")
            return False
    
    return True


def is_filled_job(job: Dict[str, Any]) -> bool:
    """
    Detect if a job posting is filled or closed.
    
    Args:
        job: Job dictionary with title, description, etc.
        
    Returns:
        True if job appears to be filled/closed, False otherwise
    """
    # Check explicit flag from API/scraper
    if job.get("is_open") is False:
        logger.debug("Job marked as not open")
        return True
    
    if job.get("status") == "closed":
        logger.debug("Job status is closed")
        return True
    
    # Text-based detection
    title = normalize(job.get("title", ""))
    description = normalize(job.get("description", ""))
    text_blob = f"{title} {description}"
    
    for keyword in FILLED_KEYWORDS:
        if keyword in text_blob:
            logger.debug(f"Job filled - detected keyword: {keyword}")
            return True
    
    return False


def is_recent(job: Dict[str, Any], max_age_days: int = MAX_JOB_AGE_DAYS) -> bool:
    """
    Check if a job posting is recent enough.
    
    Args:
        job: Job dictionary with posted_date
        max_age_days: Maximum age in days (default: 30)
        
    Returns:
        True if job is recent, False otherwise
    """
    posted_date = job.get("posted_date")
    
    # If no date, consider it stale
    if not posted_date:
        logger.debug("Job has no posted_date")
        return False
    
    # Handle string dates
    if isinstance(posted_date, str):
        try:
            # Try parsing ISO format
            posted_date = datetime.fromisoformat(posted_date.replace('Z', '+00:00'))
        except ValueError:
            logger.warning(f"Could not parse posted_date: {posted_date}")
            return False
    
    # Calculate age
    age = datetime.now(posted_date.tzinfo) - posted_date
    is_fresh = age <= timedelta(days=max_age_days)
    
    if not is_fresh:
        logger.debug(f"Job too old: {age.days} days")
    
    return is_fresh


def has_valid_link(job: Dict[str, Any]) -> bool:
    """
    Validate that job has a proper application link.
    
    Args:
        job: Job dictionary with apply_link or url
        
    Returns:
        True if valid link exists, False otherwise
    """
    link = job.get("apply_link") or job.get("url") or job.get("link")
    
    if not link:
        logger.debug("Job has no application link")
        return False
    
    # Basic URL validation
    link = str(link).strip()
    if not link.startswith(("http://", "https://")):
        logger.debug(f"Invalid link format: {link}")
        return False
    
    # Check for common invalid patterns
    invalid_patterns = ["example.com", "localhost", "127.0.0.1"]
    if any(pattern in link.lower() for pattern in invalid_patterns):
        logger.debug(f"Invalid link pattern: {link}")
        return False
    
    return True


def meets_match_threshold(job: Dict[str, Any], min_score: int = MIN_MATCH_SCORE) -> bool:
    """
    Check if job meets minimum match score threshold.
    
    Args:
        job: Job dictionary with match_score
        min_score: Minimum acceptable score (default: 50)
        
    Returns:
        True if meets threshold, False otherwise
    """
    match_score = job.get("match_score", 0)
    
    if match_score < min_score:
        logger.debug(f"Job match score too low: {match_score} < {min_score}")
        return False
    
    return True


# ==========================================
# MAIN FILTERING PIPELINE
# ==========================================

def filter_jobs(
    jobs: List[Dict[str, Any]], 
    target_role: Optional[str] = None,
    min_match_score: int = MIN_MATCH_SCORE,
    max_age_days: int = MAX_JOB_AGE_DAYS,
    enable_deduplication: bool = True
) -> List[Dict[str, Any]]:
    """
    Apply comprehensive filtering pipeline to job list.
    
    This is the SINGLE FUNCTION frontend should rely on.
    Never pass unfiltered jobs to frontend!
    
    Args:
        jobs: List of job dictionaries
        target_role: Target role key from ROLE_TAXONOMY (None for general search)
        min_match_score: Minimum match score (0-100)
        max_age_days: Maximum job age in days
        enable_deduplication: Remove duplicate jobs by ID
        
    Returns:
        Filtered list of jobs that pass all criteria
    """
    if not jobs:
        return []
    
    filtered = []
    seen_job_ids = set()
    
    stats = {
        "total": len(jobs),
        "role_mismatch": 0,
        "filled": 0,
        "stale": 0,
        "invalid_link": 0,
        "low_score": 0,
        "duplicate": 0,
        "passed": 0
    }
    
    for job in jobs:
        # Normalize data once
        if "title" in job:
            job["title_normalized"] = normalize(job["title"])
        if "description" in job:
            job["description_normalized"] = normalize(job["description"])
        
        # 1. Deduplication (cheapest check first)
        if enable_deduplication:
            job_id = job.get("job_id") or job.get("id") or job.get("url")
            if job_id in seen_job_ids:
                stats["duplicate"] += 1
                continue
            if job_id:
                seen_job_ids.add(job_id)
        
        # 2. Role matching (if specified)
        if target_role and not matches_role(job, target_role):
            stats["role_mismatch"] += 1
            continue
        
        # 3. Filled / closed check
        if is_filled_job(job):
            stats["filled"] += 1
            continue
        
        # 4. Freshness check
        if not is_recent(job, max_age_days):
            stats["stale"] += 1
            continue
        
        # 5. Valid link check
        if not has_valid_link(job):
            stats["invalid_link"] += 1
            continue
        
        # 6. Match score threshold (if available)
        if "match_score" in job and not meets_match_threshold(job, min_match_score):
            stats["low_score"] += 1
            continue
        
        # Job passed all filters!
        stats["passed"] += 1
        
        # Return clean job object
        filtered.append({
            "job_id": job.get("job_id") or job.get("id"),
            "title": job.get("title"),
            "company": job.get("company"),
            "location": job.get("location"),
            "description": job.get("description"),
            "apply_link": job.get("apply_link") or job.get("url"),
            "posted_date": job.get("posted_date"),
            "match_score": job.get("match_score"),
            "salary": job.get("salary"),
            "job_type": job.get("job_type"),
            "experience_level": job.get("experience_level")
        })
    
    # Log filtering statistics
    logger.info(f"Job filtering stats: {stats}")
    logger.info(f"Filter efficiency: {stats['passed']}/{stats['total']} " 
               f"({100 * stats['passed'] / stats['total']:.1f}%) passed")
    
    return filtered


def get_available_roles() -> List[str]:
    """
    Get list of available role taxonomy keys.
    
    Returns:
        List of role keys that can be used for filtering
    """
    return list(ROLE_TAXONOMY.keys())


def get_role_info(role: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific role.
    
    Args:
        role: Role key from ROLE_TAXONOMY
        
    Returns:
        Role configuration dict or None if not found
    """
    return ROLE_TAXONOMY.get(role)
