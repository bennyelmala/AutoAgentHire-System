"""
Resume parsing node for LangGraph workflow.
Extracts structured data from resume text/file.
"""
from typing import Dict, Any
from backend.agents.graph_state import AgentState
import logging

logger = logging.getLogger(__name__)


def parse_resume_node(state: AgentState) -> Dict[str, Any]:
    """
    Parse resume and extract skills, experience, education.
    
    For now, uses a simple keyword-based parser.
    TODO: Integrate with existing resume intelligence system.
    """
    logger.info(f"[ResumeParserNode] Processing for user {state.get('user_id')}")
    
    resume_text = state.get("resume_text", "")
    
    # Simple skills extraction (demo logic)
    skills = []
    skill_keywords = [
        "python", "java", "javascript", "react", "django", "fastapi",
        "machine learning", "deep learning", "nlp", "computer vision",
        "sql", "postgresql", "mongodb", "redis", "docker", "kubernetes",
        "aws", "gcp", "azure", "tensorflow", "pytorch", "scikit-learn"
    ]
    
    if resume_text:
        lower_text = resume_text.lower()
        skills = [skill for skill in skill_keywords if skill in lower_text]
    
    # Calculate experience years (placeholder)
    experience_years = 3.0  # Default assumption
    
    # Build parsed resume structure
    parsed_resume = {
        "raw_text": resume_text,
        "skills": skills,
        "experience_years": experience_years,
        "education": [],  # TODO: Parse education section
        "certifications": [],
        "parsed_at": "2025-01-06"
    }
    
    logger.info(f"[ResumeParserNode] Extracted {len(skills)} skills")
    
    return {
        "parsed_resume": parsed_resume,
        "extracted_skills": skills,
        "experience_years": experience_years,
        "current_step": "resume_parsed",
    }
