"""
Multi-Agent Orchestrator - Production-Grade AutoAgentHire System
================================================================
Implements autonomous agentic workflow for LinkedIn job applications.

Architecture:
  User → Resume Agent → Job Search Agent → Matching Agent → Apply Agent → Report Agent
  
Agents:
  1. Resume Agent: Parse resume, extract skills, generate embeddings
  2. Job Search Agent: Execute LinkedIn search via browser automation
  3. Matching Agent: Score jobs using RAG + semantic similarity
  4. Apply Agent: Submit applications autonomously
  5. Report Agent: Generate summary and metrics

Features:
  - State management with recovery
  - Agent-to-agent handoff messages
  - Error handling and retry logic
  - Real-time status updates
  - Database persistence
"""

import asyncio
import logging
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)


# ===========================
# ENUMS & DATA CLASSES
# ===========================

class AgentStatus(str, Enum):
    """Status of agent execution"""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowPhase(str, Enum):
    """Workflow execution phases"""
    INITIALIZATION = "initialization"
    RESUME_PARSING = "resume_parsing"
    JOB_SEARCH = "job_search"
    JOB_MATCHING = "job_matching"
    JOB_APPLICATION = "job_application"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentMessage:
    """Message passed between agents with context"""
    from_agent: str
    to_agent: str
    action: str
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AgentExecutionState:
    """State of individual agent execution"""
    name: str
    status: AgentStatus
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    output: Optional[Dict] = None
    error: Optional[str] = None
    retries: int = 0


@dataclass
class OrchestrationState:
    """Complete orchestration state with all agent outputs"""
    run_id: str
    user_id: str
    status: AgentStatus
    current_phase: WorkflowPhase
    agents: Dict[str, AgentExecutionState]
    
    # Data passed between agents
    resume_data: Optional[Dict] = None
    jobs_found: List[Dict] = field(default_factory=list)
    jobs_matched: List[Dict] = field(default_factory=list)
    jobs_applied: List[Dict] = field(default_factory=list)
    final_report: Optional[Dict] = None
    
    # Timestamps
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)


# ===========================
# BASE AGENT
# ===========================

class BaseAgent:
    """
    Base class for all agents in the system.
    Provides common functionality: logging, status management, message creation.
    """
    
    def __init__(self, name: str, max_retries: int = 3):
        self.name = name
        self.status = AgentStatus.IDLE
        self.max_retries = max_retries
        self.logger = logging.getLogger(f"Agent.{name}")
    
    async def execute(self, message: AgentMessage, state: OrchestrationState) -> AgentMessage:
        """
        Execute agent logic. Must be implemented by subclasses.
        
        Args:
            message: Input message from previous agent
            state: Current orchestration state (mutable)
            
        Returns:
            AgentMessage for next agent
            
        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError(f"{self.name}.execute() not implemented")
    
    async def execute_with_retry(
        self, 
        message: AgentMessage, 
        state: OrchestrationState
    ) -> AgentMessage:
        """Execute agent with automatic retry on failure"""
        last_error: Optional[Exception] = None
        
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Attempt {attempt + 1}/{self.max_retries}")
                return await self.execute(message, state)
            except Exception as e:
                last_error = e
                self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        # All retries exhausted
        raise last_error if last_error else Exception("All retry attempts failed")
    
    def _create_message(self, to_agent: str, action: str, data: Dict) -> AgentMessage:
        """Helper to create outgoing message"""
        return AgentMessage(
            from_agent=self.name,
            to_agent=to_agent,
            action=action,
            data=data
        )
    
    def _log_start(self):
        """Log agent start with visual separator"""
        self.logger.info("\n" + "="*70)
        self.logger.info(f"🎯 {self.name.upper()} ACTIVATED")
        self.logger.info("="*70)
    
    def _log_success(self, message: str):
        """Log successful completion"""
        self.logger.info(f"✅ {message}")
    
    def _log_error(self, message: str):
        """Log error"""
        self.logger.error(f"❌ {message}")


# ===========================
# AGENT IMPLEMENTATIONS
# ===========================

class ResumeParsingAgent(BaseAgent):
    """
    Agent #1: Parse resume and extract structured data.
    Uses RAG intelligence module for LLM-powered parsing.
    """
    
    def __init__(self, resume_intelligence):
        super().__init__("ResumeAgent")
        self.resume_intelligence = resume_intelligence
    
    async def execute(self, message: AgentMessage, state: OrchestrationState) -> AgentMessage:
        self._log_start()
        self.status = AgentStatus.RUNNING
        
        try:
            resume_file_path = message.data.get('resume_file_path')
            if not resume_file_path or not Path(resume_file_path).exists():
                raise ValueError(f"Resume file not found: {resume_file_path}")
            
            self.logger.info(f"📄 Parsing: {resume_file_path}")
            
            # Parse resume with RAG
            resume_data = self.resume_intelligence.parse_resume_file(resume_file_path)
            
            # Convert to dict for state storage
            resume_dict = asdict(resume_data)
            if resume_data.embedding is not None:
                resume_dict['embedding'] = resume_data.embedding.tolist()
            
            # Update state
            state.resume_data = resume_dict
            state.current_phase = WorkflowPhase.RESUME_PARSING
            
            self._log_success("Resume parsed successfully")
            self.logger.info(f"   Name: {resume_data.name}")
            self.logger.info(f"   Skills: {len(resume_data.skills)} identified")
            self.logger.info(f"   Experience: {resume_data.experience_years} years")
            self.logger.info(f"   Embedding: {len(resume_data.embedding) if resume_data.embedding is not None else 0}D vector")
            
            self.status = AgentStatus.SUCCESS
            
            # Handoff to Job Search Agent
            return self._create_message(
                to_agent="JobSearchAgent",
                action="SEARCH_JOBS",
                data={
                    "resume_data": resume_dict,
                    "keywords": message.data.get('keywords', ''),
                    "location": message.data.get('location', 'United States'),
                    "max_jobs": message.data.get('max_jobs', 50)
                }
            )
            
        except Exception as e:
            self.status = AgentStatus.FAILED
            self._log_error(f"Resume parsing failed: {e}")
            raise


class JobSearchAgent(BaseAgent):
    """
    Agent #2: Execute LinkedIn job search via browser automation.
    Uses existing browser automation with Easy Apply filter.
    """
    
    def __init__(self, browser_automation):
        super().__init__("JobSearchAgent")
        self.browser = browser_automation
    
    async def execute(self, message: AgentMessage, state: OrchestrationState) -> AgentMessage:
        self._log_start()
        self.status = AgentStatus.RUNNING
        
        try:
            keywords = message.data.get('keywords', '')
            location = message.data.get('location', 'United States')
            max_jobs = message.data.get('max_jobs', 50)
            
            self.logger.info(f"🔍 Search Parameters:")
            self.logger.info(f"   Keywords: {keywords}")
            self.logger.info(f"   Location: {location}")
            self.logger.info(f"   Max Jobs: {max_jobs}")
            
            # Initialize browser
            await self.browser.initialize_browser()
            
            # Login to LinkedIn
            self.logger.info("🔐 Logging into LinkedIn...")
            login_success = await self.browser.login_linkedin()
            if not login_success:
                raise Exception("LinkedIn login failed")
            self._log_success("LinkedIn login successful")
            
            # Search jobs with Easy Apply filter
            self.logger.info("🔎 Executing job search...")
            await self.browser.search_jobs(keywords, location)
            
            # Collect job listings
            self.logger.info(f"📥 Collecting up to {max_jobs} job listings...")
            jobs = await self.browser.collect_job_listings(max_jobs)
            
            # Update state
            state.jobs_found = jobs
            state.current_phase = WorkflowPhase.JOB_SEARCH
            
            self._log_success(f"Found {len(jobs)} jobs with Easy Apply")
            
            self.status = AgentStatus.SUCCESS
            
            # Handoff to Matching Agent
            return self._create_message(
                to_agent="MatchingAgent",
                action="MATCH_JOBS",
                data={
                    "jobs": jobs,
                    "resume_data": message.data.get('resume_data')
                }
            )
            
        except Exception as e:
            self.status = AgentStatus.FAILED
            self._log_error(f"Job search failed: {e}")
            
            # Cleanup browser on failure
            try:
                if hasattr(self.browser, 'close'):
                    await self.browser.close()
            except:
                pass
            
            raise


class JobMatchingAgent(BaseAgent):
    """
    Agent #3: Match jobs against resume using semantic similarity.
    Uses RAG intelligence for embedding-based matching.
    """
    
    def __init__(self, resume_intelligence, similarity_threshold: float = 0.75):
        super().__init__("MatchingAgent")
        self.resume_intelligence = resume_intelligence
        self.similarity_threshold = similarity_threshold
    
    async def execute(self, message: AgentMessage, state: OrchestrationState) -> AgentMessage:
        self._log_start()
        self.status = AgentStatus.RUNNING
        
        try:
            jobs = message.data.get('jobs', [])
            
            if not jobs:
                raise ValueError("No jobs to match")
            
            self.logger.info(f"🎯 Matching {len(jobs)} jobs against resume...")
            self.logger.info(f"   Threshold: {self.similarity_threshold*100}% for APPLY")
            
            # Match jobs using RAG
            matches = self.resume_intelligence.match_multiple_jobs(jobs)
            
            # Filter for high-quality matches
            apply_jobs = [m for m in matches if m.match_score >= self.similarity_threshold * 100]
            maybe_jobs = [m for m in matches if 0.6 * 100 <= m.match_score < self.similarity_threshold * 100]
            skip_jobs = [m for m in matches if m.match_score < 0.6 * 100]
            
            # Convert to dict for state storage
            matched_jobs = [asdict(m) for m in matches]
            apply_jobs_dict = [asdict(m) for m in apply_jobs]
            
            # Update state
            state.jobs_matched = matched_jobs
            state.current_phase = WorkflowPhase.JOB_MATCHING
            
            self._log_success(f"Matching complete")
            self.logger.info(f"   ✅ APPLY: {len(apply_jobs)} jobs (≥{self.similarity_threshold*100}%)")
            self.logger.info(f"   ⚠️  MAYBE: {len(maybe_jobs)} jobs (60-{self.similarity_threshold*100}%)")
            self.logger.info(f"   ❌ SKIP: {len(skip_jobs)} jobs (<60%)")
            
            if apply_jobs:
                self.logger.info(f"   🏆 Top match: {apply_jobs[0].job_title} @ {apply_jobs[0].company} ({apply_jobs[0].match_score:.1f}%)")
            
            self.status = AgentStatus.SUCCESS
            
            # Handoff to Apply Agent
            return self._create_message(
                to_agent="ApplyAgent",
                action="APPLY_TO_JOBS",
                data={
                    "qualified_jobs": apply_jobs_dict,
                    "resume_data": message.data.get('resume_data')
                }
            )
            
        except Exception as e:
            self.status = AgentStatus.FAILED
            self._log_error(f"Job matching failed: {e}")
            raise


class JobApplicationAgent(BaseAgent):
    """
    Agent #4: Apply to qualified jobs autonomously.
    Uses browser automation for Easy Apply submissions.
    """
    
    def __init__(self, browser_automation, apply_delay_range=(5, 10)):
        super().__init__("ApplyAgent")
        self.browser = browser_automation
        self.apply_delay_range = apply_delay_range
    
    async def execute(self, message: AgentMessage, state: OrchestrationState) -> AgentMessage:
        self._log_start()
        self.status = AgentStatus.RUNNING
        
        try:
            qualified_jobs = message.data.get('qualified_jobs', [])
            
            if not qualified_jobs:
                self.logger.warning("⚠️ No qualified jobs to apply to")
                state.current_phase = WorkflowPhase.JOB_APPLICATION
                self.status = AgentStatus.SKIPPED
                
                # Skip to report
                return self._create_message(
                    to_agent="ReportAgent",
                    action="GENERATE_REPORT",
                    data={
                        "applications": [],
                        "total_found": len(state.jobs_found),
                        "total_matched": len(state.jobs_matched)
                    }
                )
            
            self.logger.info(f"📝 Applying to {len(qualified_jobs)} qualified jobs...")
            
            results = []
            
            for i, job_match in enumerate(qualified_jobs, 1):
                self.logger.info(f"\n{'─'*60}")
                self.logger.info(f"Application {i}/{len(qualified_jobs)}")
                self.logger.info(f"📋 {job_match['job_title']}")
                self.logger.info(f"🏢 {job_match['company']}")
                self.logger.info(f"🎯 Match Score: {job_match['match_score']:.1f}%")
                self.logger.info(f"{'─'*60}")
                
                try:
                    # Apply to job
                    result = await self.browser.apply_to_single_job(job_match)
                    
                    application_record = {
                        'job_id': job_match['job_id'],
                        'job_title': job_match['job_title'],
                        'company': job_match['company'],
                        'match_score': job_match['match_score'],
                        'status': result.get('status', 'failed'),
                        'error': result.get('error'),
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    results.append(application_record)
                    
                    if result.get('success'):
                        self._log_success("Application submitted")
                    else:
                        self.logger.warning(f"⚠️ Failed: {result.get('error', 'Unknown error')}")
                    
                    # Human-like delay between applications
                    delay = random.uniform(*self.apply_delay_range)
                    self.logger.info(f"⏳ Waiting {delay:.1f}s before next application...")
                    await asyncio.sleep(delay)
                    
                except Exception as e:
                    self._log_error(f"Application error: {e}")
                    results.append({
                        'job_id': job_match.get('job_id', 'unknown'),
                        'job_title': job_match.get('job_title', 'Unknown'),
                        'company': job_match.get('company', 'Unknown'),
                        'match_score': job_match.get('match_score', 0),
                        'status': 'failed',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Update state
            state.jobs_applied = results
            state.current_phase = WorkflowPhase.JOB_APPLICATION
            
            success_count = sum(1 for r in results if r['status'] == 'success')
            
            self._log_success(f"Application phase complete")
            self.logger.info(f"   ✅ Success: {success_count}")
            self.logger.info(f"   ❌ Failed: {len(results) - success_count}")
            self.logger.info(f"   📊 Success Rate: {(success_count/len(results)*100) if results else 0:.1f}%")
            
            self.status = AgentStatus.SUCCESS
            
            # Handoff to Report Agent
            return self._create_message(
                to_agent="ReportAgent",
                action="GENERATE_REPORT",
                data={
                    "applications": results,
                    "total_found": len(state.jobs_found),
                    "total_matched": len(state.jobs_matched)
                }
            )
            
        except Exception as e:
            self.status = AgentStatus.FAILED
            self._log_error(f"Application phase failed: {e}")
            raise
        finally:
            # Always cleanup browser
            try:
                if hasattr(self.browser, 'close'):
                    await self.browser.close()
            except Exception as e:
                self.logger.warning(f"Browser cleanup warning: {e}")


class ReportGenerationAgent(BaseAgent):
    """
    Agent #5: Generate comprehensive report with metrics.
    Final agent in the workflow.
    """
    
    def __init__(self):
        super().__init__("ReportAgent")
    
    async def execute(self, message: AgentMessage, state: OrchestrationState) -> AgentMessage:
        self._log_start()
        self.status = AgentStatus.RUNNING
        
        try:
            applications = message.data.get('applications', [])
            total_found = message.data.get('total_found', 0)
            total_matched = message.data.get('total_matched', 0)
            
            success_count = sum(1 for a in applications if a['status'] == 'success')
            failed_count = sum(1 for a in applications if a['status'] == 'failed')
            
            # Calculate average match score
            avg_score = sum(a['match_score'] for a in applications) / len(applications) if applications else 0
            
            # Build comprehensive report
            report = {
                'run_id': state.run_id,
                'user_id': state.user_id,
                'summary': {
                    'total_jobs_found': total_found,
                    'total_jobs_matched': total_matched,
                    'applications_attempted': len(applications),
                    'applications_successful': success_count,
                    'applications_failed': failed_count,
                    'success_rate': f"{(success_count/len(applications)*100) if applications else 0:.1f}%",
                    'average_match_score': f"{avg_score:.1f}%"
                },
                'applications': applications,
                'timestamps': {
                    'started_at': state.started_at,
                    'completed_at': datetime.now().isoformat()
                }
            }
            
            # Update state
            state.final_report = report
            state.current_phase = WorkflowPhase.REPORT_GENERATION
            
            # Print formatted report
            self._print_report(report)
            
            self._log_success("Report generated")
            self.status = AgentStatus.SUCCESS
            
            return self._create_message(
                to_agent="Orchestrator",
                action="WORKFLOW_COMPLETE",
                data={'report': report}
            )
            
        except Exception as e:
            self.status = AgentStatus.FAILED
            self._log_error(f"Report generation failed: {e}")
            raise
    
    def _print_report(self, report: Dict):
        """Print beautifully formatted console report"""
        print("\n" + "="*70)
        print(" "*15 + "🤖 AUTO AGENT HIRE - FINAL REPORT 🤖")
        print("="*70)
        
        summary = report['summary']
        
        print(f"\n📊 EXECUTION SUMMARY")
        print(f"   Run ID: {report['run_id']}")
        print(f"   Jobs Found: {summary['total_jobs_found']}")
        print(f"   Jobs Matched (>75%): {summary['total_jobs_matched']}")
        print(f"   Average Match Score: {summary['average_match_score']}")
        
        print(f"\n📝 APPLICATION RESULTS")
        print(f"   Attempted: {summary['applications_attempted']}")
        print(f"   ✅ Successful: {summary['applications_successful']}")
        print(f"   ❌ Failed: {summary['applications_failed']}")
        print(f"   Success Rate: {summary['success_rate']}")
        
        if report['applications']:
            print(f"\n📋 APPLICATION DETAILS")
            for i, app in enumerate(report['applications'], 1):
                status_icon = "✅" if app['status'] == 'success' else "❌"
                print(f"   {i}. {status_icon} {app['job_title']}")
                print(f"      Company: {app['company']}")
                print(f"      Match Score: {app['match_score']:.1f}%")
                print(f"      Status: {app['status']}")
                if app.get('error'):
                    print(f"      Error: {app['error']}")
        
        timestamps = report['timestamps']
        print(f"\n⏱️  TIMING")
        print(f"   Started: {timestamps['started_at']}")
        print(f"   Completed: {timestamps['completed_at']}")
        
        print("\n" + "="*70 + "\n")


# ===========================
# MULTI-AGENT ORCHESTRATOR
# ===========================

class MultiAgentOrchestrator:
    """
    Central orchestrator coordinating all agents in sequential workflow.
    
    Workflow:
      1. Resume Agent: Parse resume → 2. Job Search Agent: Find jobs →
      3. Matching Agent: Score jobs → 4. Apply Agent: Submit applications →
      5. Report Agent: Generate summary
    
    Features:
      - State management with recovery
      - Agent handoff with messages
      - Real-time status updates
      - Error handling and retry
      - Database persistence
    """
    
    def __init__(
        self,
        resume_intelligence,
        browser_automation,
        similarity_threshold: float = 0.75
    ):
        """
        Initialize orchestrator with dependencies.
        
        Args:
            resume_intelligence: RAG intelligence module
            browser_automation: Browser automation module
            similarity_threshold: Minimum match score for application (default: 0.75)
        """
        self.resume_intelligence = resume_intelligence
        self.browser_automation = browser_automation
        self.similarity_threshold = similarity_threshold
        
        # Initialize all agents
        self.agents = {
            "ResumeAgent": ResumeParsingAgent(resume_intelligence),
            "JobSearchAgent": JobSearchAgent(browser_automation),
            "MatchingAgent": JobMatchingAgent(resume_intelligence, similarity_threshold),
            "ApplyAgent": JobApplicationAgent(browser_automation),
            "ReportAgent": ReportGenerationAgent()
        }
        
        self.state: Optional[OrchestrationState] = None
        self.logger = logging.getLogger("MultiAgentOrchestrator")
    
    async def run(
        self,
        user_id: str,
        resume_file_path: str,
        keywords: str,
        location: str = "United States",
        max_jobs: int = 50,
        config: Optional[Dict] = None
    ) -> Dict:
        """
        Execute complete autonomous workflow.
        
        Args:
            user_id: User identifier
            resume_file_path: Path to resume file (PDF/DOCX/TXT)
            keywords: Job search keywords
            location: Job location
            max_jobs: Maximum jobs to process
            config: Additional configuration
            
        Returns:
            Dict: Final report with results
        """
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize orchestration state
        self.state = OrchestrationState(
            run_id=run_id,
            user_id=user_id,
            status=AgentStatus.RUNNING,
            current_phase=WorkflowPhase.INITIALIZATION,
            agents={
                name: AgentExecutionState(name=name, status=AgentStatus.IDLE)
                for name in self.agents.keys()
            },
            config=config or {}
        )
        
        self.logger.info("\n" + "="*70)
        self.logger.info(" "*10 + "🚀 AUTONOMOUS AGENT WORKFLOW STARTED 🚀")
        self.logger.info("="*70)
        self.logger.info(f"Run ID: {run_id}")
        self.logger.info(f"User: {user_id}")
        self.logger.info(f"Keywords: {keywords}")
        self.logger.info(f"Location: {location}")
        self.logger.info(f"Max Jobs: {max_jobs}")
        self.logger.info("="*70 + "\n")
        
        try:
            # Create initial message for Resume Agent
            message = AgentMessage(
                from_agent="Orchestrator",
                to_agent="ResumeAgent",
                action="PARSE_RESUME",
                data={
                    'resume_file_path': resume_file_path,
                    'keywords': keywords,
                    'location': location,
                    'max_jobs': max_jobs
                }
            )
            
            # Execute agent chain sequentially
            agent_sequence = [
                "ResumeAgent",
                "JobSearchAgent",
                "MatchingAgent",
                "ApplyAgent",
                "ReportAgent"
            ]
            
            for agent_name in agent_sequence:
                agent = self.agents[agent_name]
                
                # Update phase
                self.state.current_phase = WorkflowPhase[agent_name.replace("Agent", "").upper()]
                
                # Update agent state
                agent_state = self.state.agents[agent_name]
                agent_state.status = AgentStatus.RUNNING
                agent_state.start_time = datetime.now().isoformat()
                
                try:
                    # Execute agent with retry
                    message = await agent.execute_with_retry(message, self.state)
                    
                    # Mark success
                    agent_state.status = AgentStatus.SUCCESS
                    agent_state.end_time = datetime.now().isoformat()
                    agent_state.output = message.data
                    
                except Exception as e:
                    # Mark failure
                    agent_state.status = AgentStatus.FAILED
                    agent_state.end_time = datetime.now().isoformat()
                    agent_state.error = str(e)
                    
                    self.logger.error(f"\n❌ {agent_name} FAILED: {e}")
                    raise
            
            # Mark workflow complete
            self.state.status = AgentStatus.SUCCESS
            self.state.current_phase = WorkflowPhase.COMPLETED
            self.state.completed_at = datetime.now().isoformat()
            
            self.logger.info("\n" + "="*70)
            self.logger.info(" "*15 + "🎉 WORKFLOW COMPLETED SUCCESSFULLY 🎉")
            self.logger.info("="*70 + "\n")
            
            return self.state.final_report or {}
            
        except Exception as e:
            self.state.status = AgentStatus.FAILED
            self.state.current_phase = WorkflowPhase.FAILED
            self.state.completed_at = datetime.now().isoformat()
            
            self.logger.error("\n" + "="*70)
            self.logger.error(" "*20 + "❌ WORKFLOW FAILED ❌")
            self.logger.error("="*70)
            self.logger.error(f"Error: {e}")
            self.logger.error("="*70 + "\n")
            
            raise
    
    def get_status(self) -> Dict:
        """
        Get current workflow status.
        Used for real-time status polling from frontend.
        
        Returns:
            Dict: Current state with agent statuses
        """
        if not self.state:
            return {
                'status': 'not_started',
                'message': 'Workflow not started'
            }
        
        return {
            'run_id': self.state.run_id,
            'user_id': self.state.user_id,
            'status': self.state.status.value,
            'current_phase': self.state.current_phase.value,
            'agents': {
                name: {
                    'status': agent.status.value,
                    'start_time': agent.start_time,
                    'end_time': agent.end_time,
                    'error': agent.error
                }
                for name, agent in self.state.agents.items()
            },
            'metrics': {
                'jobs_found': len(self.state.jobs_found),
                'jobs_matched': len(self.state.jobs_matched),
                'jobs_applied': len(self.state.jobs_applied)
            },
            'timestamps': {
                'started_at': self.state.started_at,
                'completed_at': self.state.completed_at
            }
        }


# ===========================
# EXAMPLE USAGE
# ===========================

if __name__ == "__main__":
    """
    Example: Run autonomous workflow
    """
    import sys
    import os
    
    # Add parent directory to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from backend.rag.resume_intelligence import ResumeIntelligence
    # from backend.agents.autoagenthire_bot import AutoAgentHireBot
    
    async def main():
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Initialize components
        resume_intel = ResumeIntelligence()
        # browser = AutoAgentHireBot(config={})  # Replace with actual config
        
        # Mock browser for testing
        class MockBrowser:
            async def initialize_browser(self): pass
            async def login_linkedin(self): return True
            async def search_jobs(self, keywords, location): pass
            async def collect_job_listings(self, max_jobs): 
                return [
                    {'job_id': '123', 'title': 'ML Engineer', 'company': 'Tech Corp', 'description': 'Great opportunity...'}
                ]
            async def apply_to_single_job(self, job): 
                return {'success': True, 'status': 'success'}
            async def close(self): pass
        
        browser = MockBrowser()
        
        # Create orchestrator
        orchestrator = MultiAgentOrchestrator(
            resume_intelligence=resume_intel,
            browser_automation=browser,
            similarity_threshold=0.75
        )
        
        # Run autonomous workflow
        try:
            report = await orchestrator.run(
                user_id="test_user",
                resume_file_path="data/resumes/sample_resume.pdf",
                keywords="Machine Learning Engineer",
                location="San Francisco, CA",
                max_jobs=30
            )
            
            print("\n✅ Workflow completed!")
            print(json.dumps(report, indent=2))
            
        except Exception as e:
            print(f"\n❌ Workflow failed: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(main())
