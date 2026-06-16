/**
 * Job Service - Handles job search and automation
 */
import { apiClient, API_ENDPOINTS, type Job, type AgentStatus } from '@/lib/api';

export interface SearchJobsRequest {
  keywords: string;
  location: string;
  maxResults?: number;
}

export interface RunAgentRequest {
  file: File;  // Resume PDF file
  keyword: string;
  location: string;
  skills: string;
  linkedin_email: string;
  linkedin_password: string;
  experience_level?: string;
  job_type?: string;
  salary_range?: string;
  max_jobs?: number;
  max_applications?: number;
  similarity_threshold?: number;
  auto_apply?: boolean;
}

export const jobService = {
  /**
   * Search for jobs (preview only, no automation)
   */
  async searchJobs(params: SearchJobsRequest): Promise<{ jobs: Job[]; count: number }> {
    const queryParams = new URLSearchParams({
      keywords: params.keywords,
      location: params.location,
      max_results: String(params.maxResults || 20),
    });
    
    return apiClient.get(`${API_ENDPOINTS.searchJobs}?${queryParams}`);
  },

  /**
   * Start the automated job application agent with resume upload
   */
  async runAgent(request: RunAgentRequest): Promise<{ status: string; message: string; data: any }> {
    const formData = new FormData();
    formData.append('file', request.file);
    formData.append('keyword', request.keyword);
    formData.append('location', request.location);
    // These three fields are REQUIRED by the backend schema.
    // If they are empty strings, FastAPI can treat them as missing and return 422.
    formData.append('skills', (request.skills || 'N/A').trim() || 'N/A');
    formData.append('linkedin_email', (request.linkedin_email || '').trim());
    formData.append('linkedin_password', request.linkedin_password || '');
    formData.append('experience_level', request.experience_level || 'Any');
    formData.append('job_type', request.job_type || 'Any');
    formData.append('salary_range', request.salary_range || 'Any');
    formData.append('max_jobs', String(request.max_jobs || 15));
    formData.append('max_applications', String(request.max_applications || 5));
    formData.append('similarity_threshold', String(request.similarity_threshold || 0.6));
  // Backend OpenAPI shows auto_apply is a string field ("true"/"false").
  formData.append('auto_apply', (request.auto_apply !== false) ? 'true' : 'false');
    
    // IMPORTANT: use API_BASE_URL directly so this hits backend/api/autoagenthire.py
    // which is mounted under /api and expects multipart form data for /api/run-agent.
    // Some other routers in the codebase also define /api/run-agent with a different
    // contract; calling the wrong one results in 422.
    return apiClient.postFormData('/api/run-agent', formData);
  },

  /**
   * Get current agent status
   */
  async getAgentStatus(): Promise<AgentStatus> {
    return apiClient.get(API_ENDPOINTS.agentStatus);
  },

  /**
   * Pause the running agent
   */
  async pauseAgent(): Promise<{ status: string }> {
    return apiClient.post(API_ENDPOINTS.pauseAgent);
  },

  /**
   * Resume a paused agent
   */
  async resumeAgent(): Promise<{ status: string }> {
    return apiClient.post(API_ENDPOINTS.resumeAgent);
  },

  /**
   * Stop the running agent
   */
  async stopAgent(): Promise<{ status: string }> {
    return apiClient.post(API_ENDPOINTS.stopAgent);
  },
};
