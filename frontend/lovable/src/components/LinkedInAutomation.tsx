import React, { useState } from 'react';
import { Upload, Play, CheckCircle, XCircle, Loader2, FileText, Briefcase } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/hooks/use-toast';

interface AutomationFormData {
  linkedinEmail: string;
  linkedinPassword: string;
  jobKeywords: string;
  jobLocation: string;
  maxApplications: number;
  firstName: string;
  lastName: string;
  phone: string;
  email: string;
  city: string;
  state: string;
  zipCode: string;
  country: string;
  address: string;
  linkedinUrl: string;
  githubUrl: string;
  portfolioUrl: string;
  currentCompany: string;
  currentTitle: string;
  yearsExperience: string;
  workAuthorizationUs: string;
  requireSponsorship: string;
  willingToRelocate: string;
  skillSet: string;
  dryRun: boolean;
  headless: boolean;
  resume: File | null;
}

interface AutomationStatus {
  sessionId: string;
  status: string;
  phase: string;
  jobsFound: number;
  currentJob: number;
  totalJobs: number;
  currentJobTitle: string;
  applicationsSubmitted: number;
  applicationsFailed: number;
}

interface ApplicationResult {
  title: string;
  company: string;
  location: string;
  url: string;
  status: string;
  reason: string;
  appliedAt: string;
  matchScore: number;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function LinkedInAutomation() {
  const { toast } = useToast();
  const [formData, setFormData] = useState<AutomationFormData>({
    linkedinEmail: '',
    linkedinPassword: '',
    jobKeywords: 'Software Engineer',
    jobLocation: 'Remote',
    maxApplications: 5,
    firstName: '',
    lastName: '',
    phone: '',
    email: '',
    city: '',
    state: '',
    zipCode: '',
    country: 'United States',
    address: '',
    linkedinUrl: '',
    githubUrl: '',
    portfolioUrl: '',
    currentCompany: '',
    currentTitle: '',
    yearsExperience: '3',
    workAuthorizationUs: 'Yes',
    requireSponsorship: 'No',
    willingToRelocate: 'Yes',
    skillSet: '',
    dryRun: false,  // CHANGED: Default to false to actually submit applications
    headless: false,
    resume: null
  });

  const [isRunning, setIsRunning] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<AutomationStatus | null>(null);
  const [results, setResults] = useState<ApplicationResult[]>([]);
  const [showResults, setShowResults] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFormData(prev => ({
        ...prev,
        resume: e.target.files![0]
      }));
      toast({
        title: 'Resume Selected',
        description: e.target.files[0].name,
      });
    }
  };

  const startAutomation = async () => {
    try {
      if (!formData.linkedinEmail || !formData.linkedinPassword) {
        toast({
          title: 'Validation Error',
          description: 'LinkedIn credentials are required',
          variant: 'destructive'
        });
        return;
      }

      if (!formData.firstName || !formData.lastName || !formData.email || !formData.phone) {
        toast({
          title: 'Validation Error',
          description: 'Personal information is required',
          variant: 'destructive'
        });
        return;
      }

      if (!formData.resume) {
        toast({
          title: 'Validation Error',
          description: 'Please upload your resume',
          variant: 'destructive'
        });
        return;
      }

      setIsRunning(true);
      setShowResults(false);
      setResults([]);

      const apiFormData = new FormData();
      apiFormData.append('linkedin_email', formData.linkedinEmail);
      apiFormData.append('linkedin_password', formData.linkedinPassword);
      apiFormData.append('job_keywords', formData.jobKeywords);
      apiFormData.append('job_location', formData.jobLocation);
      apiFormData.append('max_applications', formData.maxApplications.toString());
      apiFormData.append('first_name', formData.firstName);
      apiFormData.append('last_name', formData.lastName);
      apiFormData.append('phone', formData.phone);
      apiFormData.append('phone_number', formData.phone);
      apiFormData.append('email', formData.email);
      apiFormData.append('city', formData.city);
      apiFormData.append('state', formData.state);
      apiFormData.append('zip_code', formData.zipCode);
      apiFormData.append('country', formData.country);
      apiFormData.append('address', formData.address || '');
      apiFormData.append('linkedin_url', formData.linkedinUrl || '');
      apiFormData.append('github_url', formData.githubUrl || '');
      apiFormData.append('portfolio_url', formData.portfolioUrl || '');
      apiFormData.append('current_company', formData.currentCompany || '');
      apiFormData.append('current_title', formData.currentTitle || '');
      apiFormData.append('years_experience', formData.yearsExperience);
      apiFormData.append('skill_set', formData.skillSet || '');
      apiFormData.append('work_authorization_us', formData.workAuthorizationUs);
      apiFormData.append('require_sponsorship', formData.requireSponsorship);
      apiFormData.append('willing_to_relocate', formData.willingToRelocate);

      // Optional AI mode: pass user-provided API keys (if saved in ApiKeySettings)
      const geminiKey = (localStorage.getItem('GEMINI_API_KEY') || '').trim();
      const groqKey = (localStorage.getItem('GROQ_API_KEY') || '').trim();
      const openaiKey = (localStorage.getItem('OPENAI_API_KEY') || '').trim();
      if (geminiKey) {
        apiFormData.append('gemini_api_key', geminiKey);
      }
      if (groqKey) {
        apiFormData.append('groq_api_key', groqKey);
      }
      if (openaiKey) {
        apiFormData.append('openai_api_key', openaiKey);
      }
      const aiProvider = geminiKey ? 'gemini' : (groqKey ? 'groq' : (openaiKey ? 'openai' : 'none'));
      apiFormData.append('ai_provider', aiProvider);
      apiFormData.append('use_ai', aiProvider === 'none' ? 'false' : 'true');

      // Debug: log all form data being sent
      console.log('[AUTOMATION] Form data being sent:');
      for (const [key, value] of apiFormData.entries()) {
        if (key !== 'linkedin_password' && key !== 'resume') {
          console.log(`  ${key}: ${value}`);
        }
      }
      apiFormData.append('dry_run', formData.dryRun.toString());
      apiFormData.append('headless', formData.headless.toString());
      
      if (formData.resume) {
        apiFormData.append('resume', formData.resume);
      }

      const response = await fetch(`${API_BASE_URL}/api/v2/start-automation`, {
        method: 'POST',
        body: apiFormData
      });

      if (!response.ok) {
        throw new Error('Failed to start automation');
      }

      const data = await response.json();
      setSessionId(data.session_id);

      toast({
        title: 'Automation Started',
        description: `Session ID: ${data.session_id}`,
      });

      pollStatus(data.session_id);

    } catch (error: any) {
      console.error('Automation error:', error);
      toast({
        title: 'Error',
        description: error.message || 'Failed to start automation',
        variant: 'destructive'
      });
      setIsRunning(false);
    }
  };

  const pollStatus = async (sid: string) => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v2/automation-status/${sid}`);
        const data = await response.json();
        
        setStatus(data);

        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(interval);
          setIsRunning(false);

          if (data.status === 'completed') {
            const resultsResponse = await fetch(`${API_BASE_URL}/api/v2/automation-results/${sid}`);
            const resultsData = await resultsResponse.json();
            setResults(resultsData.results);
            setShowResults(true);

            if (data.phase === 'no_jobs_found' || data.jobs_found === 0) {
              toast({
                title: 'No Jobs Found',
                description: 'No Easy Apply jobs matched your search filters. Try broader keywords/location.',
              });
            } else if ((data.applications_submitted ?? 0) > 0) {
              toast({
                title: 'Automation Complete',
                description: `Applied to ${data.applications_submitted} jobs successfully`,
              });
            } else {
              toast({
                title: 'Automation Completed',
                description: `Found ${data.jobs_found ?? 0} jobs, but no applications were submitted. Check validation/filters and retry.`,
              });
            }
          } else {
            toast({
              title: 'Automation Failed',
              description: data.error || 'Unknown error',
              variant: 'destructive'
            });
          }
        }
      } catch (error) {
        console.error('Status poll error:', error);
      }
    }, 3000);
  };

  const getPhaseText = (phase: string) => {
    const phases: Record<string, string> = {
      'setup': 'Setting up...',
      'initializing': 'Initializing...',
      'subprocess_started': 'Starting automation engine...',
      'browser_initialized': 'Browser initialized',
      'browser_init': 'Initializing browser...',
      'logged_in': 'Logged into LinkedIn',
      'login': 'Logging into LinkedIn...',
      'logging_in': 'Logging into LinkedIn...',
      'searching': 'Searching for jobs...',
      'searching_jobs': 'Searching for jobs...',
      'jobs_collected': 'Jobs collected!',
      'collecting_jobs': 'Collecting job listings...',
      'applying': 'Applying to jobs...',
      'completed': 'Completed!',
      'finished': 'Completed!',
      'done': 'Completed!',
      'no_jobs_found': 'No jobs found matching criteria',
    };
    return phases[phase] || phase;
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Briefcase className="w-6 h-6" />
            LinkedIn Job Automation
          </CardTitle>
          <CardDescription>
            Automate your LinkedIn job applications with AI-powered form filling
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">LinkedIn Credentials</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="linkedinEmail">LinkedIn Email*</Label>
                <Input
                  id="linkedinEmail"
                  name="linkedinEmail"
                  type="email"
                  value={formData.linkedinEmail}
                  onChange={handleInputChange}
                  placeholder="your.email@example.com"
                  required
                />
              </div>
              <div>
                <Label htmlFor="linkedinPassword">LinkedIn Password*</Label>
                <Input
                  id="linkedinPassword"
                  name="linkedinPassword"
                  type="password"
                  value={formData.linkedinPassword}
                  onChange={handleInputChange}
                  required
                />
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Job Search</h3>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label htmlFor="jobKeywords">Job Keywords*</Label>
                <Input
                  id="jobKeywords"
                  name="jobKeywords"
                  value={formData.jobKeywords}
                  onChange={handleInputChange}
                  placeholder="Software Engineer"
                  required
                />
              </div>
              <div>
                <Label htmlFor="jobLocation">Location*</Label>
                <Input
                  id="jobLocation"
                  name="jobLocation"
                  value={formData.jobLocation}
                  onChange={handleInputChange}
                  placeholder="Remote"
                  required
                />
              </div>
              <div>
                <Label htmlFor="maxApplications">Max Applications*</Label>
                <Input
                  id="maxApplications"
                  name="maxApplications"
                  type="number"
                  value={formData.maxApplications}
                  onChange={handleInputChange}
                  min="1"
                  max="20"
                  required
                />
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Personal Information</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="firstName">First Name*</Label>
                <Input
                  id="firstName"
                  name="firstName"
                  value={formData.firstName}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div>
                <Label htmlFor="lastName">Last Name*</Label>
                <Input
                  id="lastName"
                  name="lastName"
                  value={formData.lastName}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div>
                <Label htmlFor="email">Email*</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div>
                <Label htmlFor="phone">Phone*</Label>
                <Input
                  id="phone"
                  name="phone"
                  type="tel"
                  value={formData.phone}
                  onChange={handleInputChange}
                  placeholder="+1-234-567-8900"
                  required
                />
              </div>
              <div>
                <Label htmlFor="city">City*</Label>
                <Input
                  id="city"
                  name="city"
                  value={formData.city}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div>
                <Label htmlFor="state">State*</Label>
                <Input
                  id="state"
                  name="state"
                  value={formData.state}
                  onChange={handleInputChange}
                  placeholder="CA"
                  required
                />
              </div>
              <div>
                <Label htmlFor="zipCode">ZIP Code*</Label>
                <Input
                  id="zipCode"
                  name="zipCode"
                  value={formData.zipCode}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div>
                <Label htmlFor="yearsExperience">Years of Experience*</Label>
                <Input
                  id="yearsExperience"
                  name="yearsExperience"
                  value={formData.yearsExperience}
                  onChange={handleInputChange}
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mt-4">
              <div>
                <Label htmlFor="country">Country</Label>
                <Input
                  id="country"
                  name="country"
                  value={formData.country}
                  onChange={handleInputChange}
                  placeholder="United States"
                />
              </div>
              <div>
                <Label htmlFor="address">Street Address</Label>
                <Input
                  id="address"
                  name="address"
                  value={formData.address}
                  onChange={handleInputChange}
                  placeholder="123 Main St"
                />
              </div>
              <div>
                <Label htmlFor="linkedinUrl">LinkedIn URL</Label>
                <Input
                  id="linkedinUrl"
                  name="linkedinUrl"
                  value={formData.linkedinUrl}
                  onChange={handleInputChange}
                  placeholder="https://linkedin.com/in/yourprofile"
                />
              </div>
              <div>
                <Label htmlFor="currentTitle">Current Job Title</Label>
                <Input
                  id="currentTitle"
                  name="currentTitle"
                  value={formData.currentTitle}
                  onChange={handleInputChange}
                  placeholder="Software Engineer"
                />
              </div>
              <div>
                <Label htmlFor="currentCompany">Current Company</Label>
                <Input
                  id="currentCompany"
                  name="currentCompany"
                  value={formData.currentCompany}
                  onChange={handleInputChange}
                  placeholder="Company name"
                />
              </div>
              <div>
                <Label htmlFor="skillSet">Skill Set</Label>
                <Input
                  id="skillSet"
                  name="skillSet"
                  value={formData.skillSet}
                  onChange={handleInputChange}
                  placeholder="Python, React, AWS..."
                />
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Resume Upload</h3>
            <div className="flex items-center gap-4">
              <Label htmlFor="resume" className="cursor-pointer">
                <div className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90">
                  <Upload className="w-4 h-4" />
                  Select Resume
                </div>
                <Input
                  id="resume"
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={handleFileChange}
                  className="hidden"
                  required
                />
              </Label>
              {formData.resume && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <FileText className="w-4 h-4" />
                  {formData.resume.name}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Settings</h3>
            <div className="flex items-center gap-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  name="dryRun"
                  checked={formData.dryRun}
                  onChange={handleInputChange}
                  className="w-4 h-4"
                />
                <span className="text-sm">Test Mode (No Real Submissions)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  name="headless"
                  checked={formData.headless}
                  onChange={handleInputChange}
                  className="w-4 h-4"
                />
                <span className="text-sm">Run in Background</span>
              </label>
            </div>
          </div>

          <Button
            onClick={startAutomation}
            disabled={isRunning}
            className="w-full"
            size="lg"
          >
            {isRunning ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Running Automation...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Start Automation
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {isRunning && status && (
        <Card>
          <CardHeader>
            <CardTitle>Automation Progress</CardTitle>
            <CardDescription>{getPhaseText(status.phase)}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Progress</span>
                <span>{status.currentJob}/{status.totalJobs} jobs</span>
              </div>
              <Progress 
                value={status.totalJobs > 0 ? (status.currentJob / status.totalJobs) * 100 : 0} 
              />
            </div>
            
            {status.currentJobTitle && (
              <div className="p-3 bg-muted rounded-md">
                <p className="text-sm font-medium">Currently applying to:</p>
                <p className="text-sm text-muted-foreground">{status.currentJobTitle}</p>
              </div>
            )}

            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="p-3 bg-muted rounded-md">
                <p className="text-2xl font-bold">{status.jobsFound}</p>
                <p className="text-xs text-muted-foreground">Jobs Found</p>
              </div>
              <div className="p-3 bg-green-50 rounded-md">
                <p className="text-2xl font-bold text-green-600">{status.applicationsSubmitted}</p>
                <p className="text-xs text-muted-foreground">Applied</p>
              </div>
              <div className="p-3 bg-red-50 rounded-md">
                <p className="text-2xl font-bold text-red-600">{status.applicationsFailed}</p>
                <p className="text-xs text-muted-foreground">Failed</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {showResults && (
        <Card>
          <CardHeader>
            <CardTitle>Application Results</CardTitle>
            <CardDescription>
              {results.length} applications processed
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {results.map((result, index) => (
                <div
                  key={index}
                  className="flex items-start gap-3 p-4 border rounded-lg hover:bg-muted/50 transition-colors"
                >
                  <div className="mt-1">
                    {result.status === 'APPLIED' || result.status === 'DRY_RUN' ? (
                      <CheckCircle className="w-5 h-5 text-green-600" />
                    ) : (
                      <XCircle className="w-5 h-5 text-red-600" />
                    )}
                  </div>
                  <div className="flex-1 space-y-1">
                    <h4 className="font-semibold">{result.title}</h4>
                    <p className="text-sm text-muted-foreground">
                      {result.company} • {result.location}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {result.reason}
                    </p>
                    <a
                      href={result.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-primary hover:underline"
                    >
                      View Job →
                    </a>
                  </div>
                  <div className="text-right">
                    <span className={`inline-block px-2 py-1 text-xs rounded-full ${
                      result.status === 'APPLIED' || result.status === 'DRY_RUN'
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {result.status === 'DRY_RUN' ? 'READY TO APPLY' : result.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
