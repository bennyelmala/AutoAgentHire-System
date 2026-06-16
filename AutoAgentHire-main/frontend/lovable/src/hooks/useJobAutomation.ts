/**
 * Custom React hooks for job automation features
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jobService, type SearchJobsRequest, type RunAgentRequest } from '@/services/jobService';
import { resumeService, type GenerateCoverLetterRequest, type AnswerQuestionRequest } from '@/services/resumeService';
import { applicationService, type GetApplicationsParams } from '@/services/applicationService';
import { useToast } from '@/hooks/use-toast';

/**
 * Hook to search for jobs
 */
export const useSearchJobs = () => {
  const { toast } = useToast();
  
  return useMutation({
    mutationFn: (params: SearchJobsRequest) => jobService.searchJobs(params),
    onSuccess: (data) => {
      toast({
        title: 'Success',
        description: `Found ${data.count} matching jobs`,
      });
    },
    onError: (error: Error) => {
      toast({
        title: 'Search Failed',
        description: error.message,
        variant: 'destructive',
      });
    },
  });
};

/**
 * Hook to run the automation agent
 */
export const useRunAgent = () => {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (request: RunAgentRequest) => jobService.runAgent(request),
    onSuccess: (data) => {
      toast({
        title: 'Agent Started',
        description: 'Job automation agent is now running. Check the dashboard for progress.',
      });
      // Invalidate agent status to trigger refresh
      queryClient.invalidateQueries({ queryKey: ['agentStatus'] });
    },
    onError: (error: Error) => {
      toast({
        title: 'Failed to Start Agent',
        description: error.message,
        variant: 'destructive',
      });
    },
  });
};

/**
 * Hook to get agent status (auto-refreshes every 2 seconds when running)
 */
export const useAgentStatus = () => {
  return useQuery({
    queryKey: ['agentStatus'],
    queryFn: () => jobService.getAgentStatus(),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      // Refresh every 2 seconds if running, every 10 seconds otherwise
      return status === 'running' ? 2000 : 10000;
    },
  });
};

/**
 * Hook to pause/resume/stop agent
 */
export const useAgentControl = () => {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const pause = useMutation({
    mutationFn: () => jobService.pauseAgent(),
    onSuccess: () => {
      toast({ title: 'Agent Paused' });
      queryClient.invalidateQueries({ queryKey: ['agentStatus'] });
    },
  });

  const resume = useMutation({
    mutationFn: () => jobService.resumeAgent(),
    onSuccess: () => {
      toast({ title: 'Agent Resumed' });
      queryClient.invalidateQueries({ queryKey: ['agentStatus'] });
    },
  });

  const stop = useMutation({
    mutationFn: () => jobService.stopAgent(),
    onSuccess: () => {
      toast({ title: 'Agent Stopped' });
      queryClient.invalidateQueries({ queryKey: ['agentStatus'] });
    },
  });

  return { pause, resume, stop };
};

/**
 * Hook to upload resume
 */
export const useUploadResume = () => {
  const { toast } = useToast();
  
  return useMutation({
    mutationFn: ({ file, email }: { file: File; email: string }) =>
      resumeService.uploadResume(file, email),
    onSuccess: (data) => {
      toast({
        title: 'Resume Uploaded',
        description: `${data.filename} processed successfully`,
      });
    },
    onError: (error: Error) => {
      toast({
        title: 'Upload Failed',
        description: error.message,
        variant: 'destructive',
      });
    },
  });
};

/**
 * Hook to generate cover letter
 */
export const useGenerateCoverLetter = () => {
  const { toast } = useToast();
  
  return useMutation({
    mutationFn: (request: GenerateCoverLetterRequest) =>
      resumeService.generateCoverLetter(request),
    onSuccess: () => {
      toast({
        title: 'Cover Letter Generated',
        description: 'AI-powered cover letter created successfully',
      });
    },
    onError: (error: Error) => {
      toast({
        title: 'Generation Failed',
        description: error.message,
        variant: 'destructive',
      });
    },
  });
};

/**
 * Hook to answer application questions
 */
export const useAnswerQuestion = () => {
  const { toast } = useToast();
  
  return useMutation({
    mutationFn: (request: AnswerQuestionRequest) =>
      resumeService.answerQuestion(request),
    onError: (error: Error) => {
      toast({
        title: 'Failed to Generate Answer',
        description: error.message,
        variant: 'destructive',
      });
    },
  });
};

/**
 * Hook to get application history
 */
export const useApplications = (params?: GetApplicationsParams) => {
  return useQuery({
    queryKey: ['applications', params],
    queryFn: () => applicationService.getApplications(params),
    refetchInterval: 30000, // Refresh every 30 seconds
  });
};
