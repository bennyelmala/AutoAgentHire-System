/**
 * Resume Service - Handles resume upload and processing
 */
import { apiClient, API_ENDPOINTS } from '@/lib/api';

export interface UploadResumeResponse {
  status: string;
  filename: string;
  file_path: string;
  text_length: number;
  summary?: string;
}

export interface GenerateCoverLetterRequest {
  job_title: string;
  company: string;
  job_description: string;
  user_name: string;
  resume_text: string;
  ai_provider?: 'gemini' | 'groq' | 'openai';
  api_key?: string;
}

export interface GenerateCoverLetterResponse {
  status: string;
  cover_letter: string;
  file_path: string;
}

export interface AnswerQuestionRequest {
  question: string;
  job_title: string;
  company: string;
  resume_text: string;
  max_words?: number;
  ai_provider?: 'gemini' | 'groq' | 'openai';
  api_key?: string;
}

export interface AnswerQuestionResponse {
  status: string;
  question: string;
  answer: string;
}

export const resumeService = {
  /**
   * Upload and process a resume file
   */
  async uploadResume(file: File, userEmail: string): Promise<UploadResumeResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_email', userEmail);

    return apiClient.postFormData(API_ENDPOINTS.uploadResume, formData);
  },

  /**
   * Generate an AI-powered cover letter
   */
  async generateCoverLetter(request: GenerateCoverLetterRequest): Promise<GenerateCoverLetterResponse> {
    const formData = new FormData();
    formData.append('job_title', request.job_title);
    formData.append('company', request.company);
    formData.append('job_description', request.job_description);
    formData.append('user_name', request.user_name);
    formData.append('resume_text', request.resume_text);
    
    // Add AI provider and API key if specified
    if (request.ai_provider) {
      formData.append('ai_provider', request.ai_provider);
    }
    if (request.api_key) {
      formData.append('api_key', request.api_key);
    }

    return apiClient.postFormData(API_ENDPOINTS.generateCoverLetter, formData);
  },

  /**
   * Generate an intelligent answer to an application question
   */
  async answerQuestion(request: AnswerQuestionRequest): Promise<AnswerQuestionResponse> {
    const formData = new FormData();
    formData.append('question', request.question);
    formData.append('job_title', request.job_title);
    formData.append('company', request.company);
    formData.append('resume_text', request.resume_text);
    if (request.max_words) {
      formData.append('max_words', String(request.max_words));
    }
    
    // Add AI provider and API key if specified
    if (request.ai_provider) {
      formData.append('ai_provider', request.ai_provider);
    }
    if (request.api_key) {
      formData.append('api_key', request.api_key);
    }

    return apiClient.postFormData(API_ENDPOINTS.answerQuestion, formData);
  },
};
