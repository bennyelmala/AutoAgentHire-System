"""
LangGraph Orchestrator for AutoAgentHire Multi-Agent Workflow

This orchestrator uses LangGraph to manage a stateful multi-agent pipeline:
1. Resume Parsing → Extract skills and experience
2. Job Search → Find relevant job openings
3. Job Matching → Rank jobs by fit
4. Application → Submit applications

Benefits of LangGraph:
- State persistence across nodes
- Easy to visualize and debug
- Checkpointing support for long-running workflows
- Clean separation of concerns
"""
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from datetime import datetime
import logging

from backend.agents.graph_state import (
    AgentState,
    AgentInput,
    AgentOutput,
    WorkflowStatus,
    create_initial_state,
    extract_output,
)
from backend.agents.nodes.resume_parser import parse_resume_node
from backend.agents.nodes.job_search import job_search_node
from backend.agents.nodes.job_matching import job_matching_node
from backend.agents.nodes.application import application_node

logger = logging.getLogger(__name__)


class LangGraphOrchestrator:
    """
    LangGraph-based orchestrator for the job application workflow.
    
    Usage:
        orchestrator = LangGraphOrchestrator()
        result = await orchestrator.run(input_data)
    """
    
    def __init__(self):
        """Initialize the LangGraph workflow."""
        self.graph = self._build_graph()
        self.app = self.graph.compile()
        logger.info("[LangGraphOrchestrator] Initialized and compiled workflow graph")
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph StateGraph with all nodes and edges.
        
        Workflow:
        START → parse_resume → job_search → job_matching → application → END
        """
        # Create graph with AgentState schema
        workflow = StateGraph(AgentState)
        
        # Add nodes (each node is a processing step)
        workflow.add_node("parse_resume", parse_resume_node)
        workflow.add_node("job_search", job_search_node)
        workflow.add_node("job_matching", job_matching_node)
        workflow.add_node("application", application_node)
        
        # Define edges (workflow flow)
        workflow.set_entry_point("parse_resume")
        workflow.add_edge("parse_resume", "job_search")
        workflow.add_edge("job_search", "job_matching")
        workflow.add_edge("job_matching", "application")
        workflow.add_edge("application", END)
        
        logger.info("[LangGraphOrchestrator] Graph built with 4 nodes")
        return workflow
    
    async def run(self, input_data: AgentInput) -> AgentOutput:
        """
        Execute the complete workflow asynchronously.
        
        Args:
            input_data: User input with resume, preferences, and configuration
            
        Returns:
            AgentOutput: Workflow results including matched jobs and applications
        """
        logger.info(f"[LangGraphOrchestrator] Starting workflow for user: {input_data['user_id']}")
        
        # Create initial state
        initial_state = create_initial_state(input_data)
        initial_state["workflow_status"] = WorkflowStatus.RUNNING
        
        try:
            # Run the graph (synchronous for now, async support coming)
            final_state_raw = self.app.invoke(initial_state)
            
            # Convert to AgentState (it might come back as plain dict)
            final_state: AgentState = final_state_raw  # type: ignore
            
            # Mark as completed
            final_state["workflow_status"] = WorkflowStatus.COMPLETED
            final_state["completed_at"] = datetime.now()
            
            # Calculate execution time
            if final_state.get("started_at") and final_state.get("completed_at"):
                delta = final_state["completed_at"] - final_state["started_at"]  # type: ignore
                final_state["execution_time_seconds"] = delta.total_seconds()
            
            logger.info(
                f"[LangGraphOrchestrator] Workflow completed successfully. "
                f"Applied to {len(final_state.get('submitted_applications', []))} jobs"
            )
            
            # Extract output
            return extract_output(final_state)
            
        except Exception as e:
            logger.error(f"[LangGraphOrchestrator] Workflow failed: {e}", exc_info=True)
            
            # Mark as failed and return error state
            error_state: AgentState = initial_state.copy()  # type: ignore
            error_state["workflow_status"] = WorkflowStatus.FAILED
            error_state["errors"] = [str(e)]
            error_state["completed_at"] = datetime.now()
            
            return extract_output(error_state)
    
    def run_sync(self, input_data: AgentInput) -> AgentOutput:
        """
        Synchronous version of run() for non-async contexts.
        """
        logger.info(f"[LangGraphOrchestrator] Starting synchronous workflow for user: {input_data['user_id']}")
        
        # Create initial state
        initial_state = create_initial_state(input_data)
        initial_state["workflow_status"] = WorkflowStatus.RUNNING
        
        try:
            # Run the graph synchronously
            final_state_raw = self.app.invoke(initial_state)
            
            # Convert to AgentState
            final_state: AgentState = final_state_raw  # type: ignore
            
            # Mark as completed
            final_state["workflow_status"] = WorkflowStatus.COMPLETED
            final_state["completed_at"] = datetime.now()
            
            # Calculate execution time
            if final_state.get("started_at") and final_state.get("completed_at"):
                delta = final_state["completed_at"] - final_state["started_at"]  # type: ignore
                final_state["execution_time_seconds"] = delta.total_seconds()
            
            logger.info(
                f"[LangGraphOrchestrator] Workflow completed. "
                f"Applied to {len(final_state.get('submitted_applications', []))} jobs"
            )
            
            # Extract output
            return extract_output(final_state)
            
        except Exception as e:
            logger.error(f"[LangGraphOrchestrator] Workflow failed: {e}", exc_info=True)
            
            # Mark as failed
            error_state: AgentState = initial_state.copy()  # type: ignore
            error_state["workflow_status"] = WorkflowStatus.FAILED
            error_state["errors"] = [str(e)]
            error_state["completed_at"] = datetime.now()
            
            return extract_output(error_state)
    
    def visualize(self, output_path: str = "workflow_graph.png"):
        """
        Generate a visual representation of the workflow graph.
        Requires graphviz to be installed.
        """
        try:
            from IPython.display import Image, display
            display(Image(self.app.get_graph().draw_mermaid_png()))
        except Exception as e:
            logger.warning(f"Could not visualize graph: {e}")
            logger.info("Install graphviz and ipython to enable visualization")


# Singleton instance for easy import
_orchestrator_instance: Optional[LangGraphOrchestrator] = None


def get_orchestrator() -> LangGraphOrchestrator:
    """Get or create singleton orchestrator instance."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = LangGraphOrchestrator()
    return _orchestrator_instance
