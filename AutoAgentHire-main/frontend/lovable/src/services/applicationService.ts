/**
 * Application Service - Handles application tracking
 */
import { apiClient, API_ENDPOINTS, type Application } from '@/lib/api';

export interface GetApplicationsParams {
  user_email?: string;
  status?: string;
  limit?: number;
}

export interface GetApplicationsResponse {
  applications: Application[];
  total: number;
  page: number;
  limit: number;
}

export const applicationService = {
  /**
   * Get application history
   */
  async getApplications(params?: GetApplicationsParams): Promise<GetApplicationsResponse> {
    const queryParams = new URLSearchParams();
    
    if (params?.user_email) {
      queryParams.append('user_email', params.user_email);
    }
    if (params?.status) {
      queryParams.append('status', params.status);
    }
    if (params?.limit) {
      queryParams.append('limit', String(params.limit));
    }

    const query = queryParams.toString();
    const endpoint = query ? `${API_ENDPOINTS.getApplications}?${query}` : API_ENDPOINTS.getApplications;
    
    return apiClient.get(endpoint);
  },
};
