import { useState, useRef } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { 
  Search, MapPin, Briefcase, Upload, FileText,
  Zap, ArrowLeft, Play, Save, X 
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { jobService } from "@/services/jobService";

function normalizeErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  if (error && typeof error === 'object') {
    const e: any = error;
    // Prefer the shapes we use across backend
    if (typeof e.message === 'string' && e.message) return e.message;
    if (typeof e.detail === 'string' && e.detail) return e.detail;
    if (typeof e.error === 'string' && e.error) return e.error;
    // FastAPI / our custom validation handler
    if (Array.isArray(e.errors) && e.errors.length) return e.errors.join('\n');
    if (Array.isArray(e.detail)) {
      return e.detail
        .map((d: any) => {
          const loc = Array.isArray(d?.loc) ? d.loc.join('.') : '';
          const msg = d?.msg || 'Invalid value';
          return loc ? `${loc}: ${msg}` : msg;
        })
        .join('\n');
    }
    try {
      return JSON.stringify(error);
    } catch {
      return 'Unknown error occurred';
    }
  }
  return 'Unknown error occurred';
}

const JobSearchConfig = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  
  const [searchConfig, setSearchConfig] = useState({
    keywords: "",
    location: "Remote",
    skills: "",
    jobType: "Full-time",
    experienceLevel: "Mid-level",
    salaryRange: "Any",
    maxJobs: 15,
    maxApplications: 5,
    linkedinEmail: "",
    linkedinPassword: "",
    autoApply: true,
    similarityThreshold: 0.6
  });

  const handleChange = (field: string, value: any) => {
    setSearchConfig(prev => ({ ...prev, [field]: value }));
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (file.type !== 'application/pdf') {
        toast({
          title: "Invalid file type",
          description: "Please upload a PDF file",
          variant: "destructive"
        });
        return;
      }
      if (file.size > 10 * 1024 * 1024) { // 10MB
        toast({
          title: "File too large",
          description: "Resume must be less than 10MB",
          variant: "destructive"
        });
        return;
      }
      setResumeFile(file);
      toast({
        title: "Resume uploaded",
        description: `${file.name} (${(file.size / 1024).toFixed(1)} KB)`,
      });
    }
  };

  const handleStartAutomation = async () => {
    // Validation
    if (!resumeFile) {
      toast({
        title: "Resume required",
        description: "Please upload your resume (PDF)",
        variant: "destructive"
      });
      return;
    }

    if (!searchConfig.keywords.trim()) {
      toast({
        title: "Keywords required",
        description: "Please enter job keywords to search for",
        variant: "destructive"
      });
      return;
    }

    if (!searchConfig.linkedinEmail || !searchConfig.linkedinPassword) {
      toast({
        title: "LinkedIn credentials required",
        description: "Please enter your LinkedIn email and password",
        variant: "destructive"
      });
      return;
    }

    setLoading(true);

    try {
      const result = await jobService.runAgent({
        file: resumeFile,
        keyword: searchConfig.keywords,
        location: searchConfig.location,
        skills: searchConfig.skills,
        linkedin_email: searchConfig.linkedinEmail,
        linkedin_password: searchConfig.linkedinPassword,
        experience_level: searchConfig.experienceLevel,
        job_type: searchConfig.jobType,
        salary_range: searchConfig.salaryRange,
        max_jobs: searchConfig.maxJobs,
        max_applications: searchConfig.maxApplications,
        similarity_threshold: searchConfig.similarityThreshold,
        auto_apply: searchConfig.autoApply
      });

      toast({
        title: "Automation Started! 🚀",
        description: "Your LinkedIn automation agent is now running. Check the dashboard for progress.",
      });

      // Navigate back to dashboard
      setTimeout(() => {
        navigate('/dashboard');
      }, 2000);

    } catch (error) {
      console.error('Error starting automation:', error);
      const errorMessage = normalizeErrorMessage(error);
      toast({
        title: "Failed to start automation",
        description: errorMessage,
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveConfig = () => {
    const configToSave = { ...searchConfig };
    // Don't save credentials
    delete (configToSave as any).linkedinEmail;
    delete (configToSave as any).linkedinPassword;
    
    localStorage.setItem('jobSearchConfig', JSON.stringify(configToSave));
    toast({
      title: "Configuration saved",
      description: "Your search preferences have been saved"
    });
  };

  return (
    <div className="container max-w-7xl mx-auto p-6 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/dashboard')}
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold">Configure Job Search</h1>
            <p className="text-muted-foreground mt-1">
              Set up your automated LinkedIn job application preferences
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Resume Upload */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card variant="glass">
              <CardHeader>
                <CardTitle>Resume Upload</CardTitle>
                <CardDescription>
                  Upload your resume (PDF only, max 10MB)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  
                  {resumeFile ? (
                    <div className="flex items-center justify-between p-4 rounded-lg bg-primary/10 border border-primary/20">
                      <div className="flex items-center gap-3">
                        <FileText className="w-8 h-8 text-primary" />
                        <div>
                          <p className="font-medium">{resumeFile.name}</p>
                          <p className="text-sm text-muted-foreground">
                            {(resumeFile.size / 1024).toFixed(1)} KB
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setResumeFile(null)}
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  ) : (
                    <Button
                      variant="outline"
                      className="w-full h-32 border-dashed"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <div className="flex flex-col items-center gap-2">
                        <Upload className="w-8 h-8" />
                        <p>Click to upload resume</p>
                        <p className="text-xs text-muted-foreground">PDF only, max 10MB</p>
                      </div>
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Search Criteria */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
          >
            <Card variant="glass">
              <CardHeader>
                <CardTitle>Search Criteria</CardTitle>
                <CardDescription>
                  Define what jobs you're looking for
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="keywords">Job Title / Keywords *</Label>
                  <div className="relative mt-1.5">
                    <Search className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                    <Input
                      id="keywords"
                      placeholder="e.g., Python Developer, Data Scientist"
                      value={searchConfig.keywords}
                      onChange={(e) => handleChange('keywords', e.target.value)}
                      className="pl-9"
                    />
                  </div>
                </div>

                <div>
                  <Label htmlFor="location">Location</Label>
                  <div className="relative mt-1.5">
                    <MapPin className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                    <Input
                      id="location"
                      placeholder="e.g., Remote, San Francisco, New York"
                      value={searchConfig.location}
                      onChange={(e) => handleChange('location', e.target.value)}
                      className="pl-9"
                    />
                  </div>
                </div>

                <div>
                  <Label htmlFor="skills">Skills (optional)</Label>
                  <Textarea
                    id="skills"
                    placeholder="e.g., Python, React, Machine Learning, AWS"
                    value={searchConfig.skills}
                    onChange={(e) => handleChange('skills', e.target.value)}
                    className="mt-1.5"
                    rows={3}
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="jobType">Job Type</Label>
                    <Select
                      value={searchConfig.jobType}
                      onValueChange={(value) => handleChange('jobType', value)}
                    >
                      <SelectTrigger className="mt-1.5">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Full-time">Full-time</SelectItem>
                        <SelectItem value="Part-time">Part-time</SelectItem>
                        <SelectItem value="Contract">Contract</SelectItem>
                        <SelectItem value="Internship">Internship</SelectItem>
                        <SelectItem value="Any">Any</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label htmlFor="experienceLevel">Experience Level</Label>
                    <Select
                      value={searchConfig.experienceLevel}
                      onValueChange={(value) => handleChange('experienceLevel', value)}
                    >
                      <SelectTrigger className="mt-1.5">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Entry-level">Entry-level</SelectItem>
                        <SelectItem value="Mid-level">Mid-level</SelectItem>
                        <SelectItem value="Senior">Senior</SelectItem>
                        <SelectItem value="Lead">Lead</SelectItem>
                        <SelectItem value="Any">Any</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="maxJobs">Max Jobs to Analyze</Label>
                    <Input
                      id="maxJobs"
                      type="number"
                      min="1"
                      max="50"
                      value={searchConfig.maxJobs}
                      onChange={(e) => handleChange('maxJobs', parseInt(e.target.value))}
                      className="mt-1.5"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      How many jobs to collect and analyze
                    </p>
                  </div>

                  <div>
                    <Label htmlFor="maxApplications">Max Applications</Label>
                    <Input
                      id="maxApplications"
                      type="number"
                      min="1"
                      max="20"
                      value={searchConfig.maxApplications}
                      onChange={(e) => handleChange('maxApplications', parseInt(e.target.value))}
                      className="mt-1.5"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      How many jobs to actually apply to
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* LinkedIn Credentials */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Card variant="glass">
              <CardHeader>
                <CardTitle>LinkedIn Credentials</CardTitle>
                <CardDescription>
                  Required to automate job applications (stored securely, not saved on server)
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="linkedinEmail">LinkedIn Email *</Label>
                  <Input
                    id="linkedinEmail"
                    type="email"
                    placeholder="your@email.com"
                    value={searchConfig.linkedinEmail}
                    onChange={(e) => handleChange('linkedinEmail', e.target.value)}
                    className="mt-1.5"
                  />
                </div>

                <div>
                  <Label htmlFor="linkedinPassword">LinkedIn Password *</Label>
                  <Input
                    id="linkedinPassword"
                    type="password"
                    placeholder="••••••••"
                    value={searchConfig.linkedinPassword}
                    onChange={(e) => handleChange('linkedinPassword', e.target.value)}
                    className="mt-1.5"
                  />
                </div>

                <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                  <p className="text-sm text-yellow-500">
                    🔒 Your credentials are never stored on our servers. They are only used temporarily for automation.
                  </p>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Automation Settings */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
          >
            <Card variant="glass">
              <CardHeader>
                <CardTitle>Automation Settings</CardTitle>
                <CardDescription>
                  Control how the agent applies to jobs
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-lg bg-white/5">
                  <div>
                    <Label htmlFor="autoApply" className="cursor-pointer">Auto-Apply to Matched Jobs</Label>
                    <p className="text-xs text-muted-foreground mt-1">
                      Automatically submit applications to Easy Apply jobs
                    </p>
                  </div>
                  <Switch
                    id="autoApply"
                    checked={searchConfig.autoApply}
                    onCheckedChange={(checked) => handleChange('autoApply', checked)}
                  />
                </div>

                <div>
                  <Label htmlFor="similarityThreshold">
                    Minimum Match Score: {Math.round(searchConfig.similarityThreshold * 100)}%
                  </Label>
                  <Input
                    id="similarityThreshold"
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={searchConfig.similarityThreshold}
                    onChange={(e) => handleChange('similarityThreshold', parseFloat(e.target.value))}
                    className="mt-2"
                  />
                  <p className="text-xs text-muted-foreground mt-1.5">
                    Only apply to jobs that match at least {Math.round(searchConfig.similarityThreshold * 100)}% of your profile
                  </p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Sidebar - Summary & Actions */}
        <div className="space-y-6">
          {/* Summary */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
          >
            <Card variant="glow">
              <CardHeader>
                <CardTitle className="text-lg">Ready to Start?</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Resume:</span>
                    <span className="font-medium">{resumeFile ? "✅ Uploaded" : "❌ Required"}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Searching for:</span>
                    <span className="font-medium truncate max-w-[150px]">{searchConfig.keywords || "Not set"}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Location:</span>
                    <span className="font-medium">{searchConfig.location}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Auto-Apply:</span>
                    <span className="font-medium">{searchConfig.autoApply ? "Yes" : "No"}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Max Applications:</span>
                    <span className="font-medium">{searchConfig.maxApplications}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Match Threshold:</span>
                    <span className="font-medium">{Math.round(searchConfig.similarityThreshold * 100)}%</span>
                  </div>
                </div>

                <div className="pt-4 border-t border-white/10 space-y-3">
                  <Button
                    variant="hero"
                    className="w-full"
                    size="lg"
                    onClick={handleStartAutomation}
                    disabled={loading}
                  >
                    <Play className="w-5 h-5" />
                    {loading ? "Starting..." : "Start Automation"}
                  </Button>

                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={handleSaveConfig}
                  >
                    <Save className="w-4 h-4" />
                    Save Configuration
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Info */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">How it works</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <div className="flex gap-3">
                  <div className="w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center flex-shrink-0 text-xs font-bold">
                    1
                  </div>
                  <p>Upload your resume and configure search criteria</p>
                </div>
                <div className="flex gap-3">
                  <div className="w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center flex-shrink-0 text-xs font-bold">
                    2
                  </div>
                  <p>Agent logs into LinkedIn with your credentials</p>
                </div>
                <div className="flex gap-3">
                  <div className="w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center flex-shrink-0 text-xs font-bold">
                    3
                  </div>
                  <p>Searches for jobs with Easy Apply filter enabled</p>
                </div>
                <div className="flex gap-3">
                  <div className="w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center flex-shrink-0 text-xs font-bold">
                    4
                  </div>
                  <p>AI analyzes each job and matches with your resume</p>
                </div>
                <div className="flex gap-3">
                  <div className="w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center flex-shrink-0 text-xs font-bold">
                    5
                  </div>
                  <p>Automatically applies to matched Easy Apply jobs</p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </div>
  );
};

export default JobSearchConfig;
