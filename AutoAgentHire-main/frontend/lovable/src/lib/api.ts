import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ─── TypeScript Interfaces ────────────────────────────────────────────────────

export interface Job {
  id?: string;
  title: string;
  company: string;
  location: string;
  url?: string;
  description?: string;
  match_score?: number;
  status?: string;
  applied_at?: string;
}

export interface Application {
  id?: string;
  job_title?: string;
  company?: string;
  status?: string;
  applied_at?: string;
  match_score?: number;
  job_url?: string;
}

export interface AgentStatus {
  status: string;
  phase?: string;
  jobs_found?: number;
  applications_submitted?: number;
  applications_previewed?: number;
  errors?: string[];
  start_time?: string | null;
  end_time?: string | null;
  logs?: any[];
}

// ─── Axios Instance ───────────────────────────────────────────────────────────

// Create axios instance with default configuration
export const apiClient = {
  _axios: axios.create({
    baseURL: API_BASE_URL,
    headers: { 'Content-Type': 'application/json' },
    timeout: 30000,
  }),

  // Attach interceptors below then expose get/post/put/patch/delete/postFormData
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this._axios.get(url, config);
  },
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this._axios.post(url, data, config);
  },
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this._axios.put(url, data, config);
  },
  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this._axios.patch(url, data, config);
  },
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this._axios.delete(url, config);
  },
  /** Send multipart/form-data (for file uploads). */
  postFormData<T = any>(url: string, formData: FormData, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this._axios.post(url, formData, {
      ...config,
      headers: { ...(config?.headers || {}), 'Content-Type': 'multipart/form-data' },
    });
  },
};

// Request interceptor – attach auth token
apiClient._axios.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error),
);

// Response interceptor – global 401 handler
apiClient._axios.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('authToken');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

// ─── API Endpoints ────────────────────────────────────────────────────────────

export const API_ENDPOINTS = {
  // Authentication
  auth: {
    login: '/auth/login',
    signup: '/auth/signup',
    register: '/auth/signup',
    logout: '/auth/logout',
    refresh: '/auth/refresh',
    me: '/auth/me',
    google: '/auth/google',
  },

  // Jobs
  jobs: {
    search: '/api/jobs/search',
    recommended: '/api/linkedin/recommended-jobs',
    details: (id: string) => `/api/jobs/${id}`,
    apply: '/api/v2/start-automation',
    automation: '/api/v2/start-automation',
    automationStatus: (sessionId: string) => `/api/v2/automation-status/${sessionId}`,
    automationResults: (sessionId: string) => `/api/v2/automation-results/${sessionId}`,
  },

  // Applications
  applications: {
    list: '/api/applications',
    create: '/api/applications',
    details: (id: string) => `/api/applications/${id}`,
    update: (id: string) => `/api/applications/${id}`,
    delete: (id: string) => `/api/applications/${id}`,
    stats: '/api/agent/status',
  },

  // Resume
  resume: {
    upload: '/api/upload-resume',
    parse: '/api/upload-resume',
    download: '/api/upload-resume',
    analyze: '/api/upload-resume',
  },

  // Cover Letter
  coverLetter: {
    generate: '/api/cover-letter/generate',
    templates: '/api/cover-letter/generate',
  },

  // ATS
  ats: {
    check: '/api/ats/match',
    score: '/api/ats/match',
    optimize: '/api/ats/match',
    parseResume: '/api/ats/parse-resume',
  },

  // LinkedIn
  linkedin: {
    connect: '/api/v2/start-automation',
    profile: '/auth/me',
    jobs: '/api/linkedin/recommended-jobs',
    availableRoles: '/api/linkedin/available-roles',
  },

  // Settings
  settings: {
    profile: '/auth/me',
    preferences: '/auth/me',
    apiKeys: '/auth/me',
  },

  // Agent control
  agent: {
    run: '/api/run-agent',
    status: '/api/agent/status',
    pause: '/api/agent/pause',
    resume: '/api/agent/resume',
    stop: '/api/agent/stop',
    statusById: (runId: string) => `/api/agent/status/${runId}`,
    results: (runId: string) => `/api/agent/results/${runId}`,
    uploadResume: '/api/agent/resume/upload',
    agentRuns: '/api/v2/agent-runs',
    v2Applications: '/api/v2/applications',
  },

  // Autoagenthire
  autoagenthire: {
    start: '/api/autoagenthire/start',
    searchJobs: '/api/autoagenthire/search-jobs',
    applySingle: '/api/autoagenthire/apply-single',
    run: (runId: string) => `/api/autoagenthire/run/${runId}`,
  },

  // Health check
  health: '/health',

  // ── Flat aliases (for services that import them at top-level) ───────────────
  searchJobs: '/api/jobs/search',
  getApplications: '/api/applications',
  uploadResume: '/api/upload-resume',
  generateCoverLetter: '/api/cover-letter/generate',
  answerQuestion: '/api/answer-question',
  matchProfile: '/api/match-profile',
  agentStatus: '/api/agent/status',
  pauseAgent: '/api/agent/pause',
  resumeAgent: '/api/agent/resume',
  stopAgent: '/api/agent/stop',
  agentResults: (runId: string) => `/api/agent/results/${runId}`,
  runAgent: '/api/run-agent',
} as const;

// ─── Convenience re-export ────────────────────────────────────────────────────

export const api = {
  get: <T = any>(url: string, config?: AxiosRequestConfig) => apiClient.get<T>(url, config),
  post: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => apiClient.post<T>(url, data, config),
  put: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => apiClient.put<T>(url, data, config),
  patch: <T = any>(url: string, data?: any, config?: AxiosRequestConfig) => apiClient.patch<T>(url, data, config),
  delete: <T = any>(url: string, config?: AxiosRequestConfig) => apiClient.delete<T>(url, config),
};

export default api;