import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Loader2, ExternalLink, Building2, MapPin, Briefcase, Filter, AlertCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Alert, AlertDescription } from "@/components/ui/alert";

type Job = {
  title: string;
  company: string;
  location: string;
  url: string;
  role?: string;
  index: number;
};

type ApiResponse = {
  status: string;
  total: number;
  filtered_from?: number;
  jobs: Job[];
  message: string;
  filter_applied?: boolean;
  warning?: string | null;
};

type RoleOption = {
  key: string;
  display_name: string;
};

export default function RecommendedJobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [linkedinEmail, setLinkedinEmail] = useState("");
  const [linkedinPassword, setLinkedinPassword] = useState("");
  // Default to backend roles (matches the screenshot flow) and keep filtering enabled
  // so user-selected role actually influences the result list.
  const [jobRole, setJobRole] = useState("backend_engineer");
  const [enableFiltering, setEnableFiltering] = useState(true);
  const [availableRoles, setAvailableRoles] = useState<RoleOption[]>([]);
  const [filteredFrom, setFilteredFrom] = useState<number>(0);
  const { toast } = useToast();

  const cleanCompany = (company: string) => {
    const c = (company || "").replace(/\s+/g, " ").trim();
    // Remove common trailing noise like separators or bullets.
    return c.replace(/[•|].*$/, "").trim();
  };

  // Fetch available roles on component mount
  useEffect(() => {
    const fetchRoles = async () => {
      try {
        const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        const response = await fetch(`${API_BASE_URL}/api/linkedin/available-roles`);
        const data = await response.json();
        if (data.status === "success") {
          setAvailableRoles(data.roles);
        }
      } catch (err) {
        console.error("Failed to fetch available roles:", err);
        toast({
          title: "Connection Error",
          description: "Could not connect to backend server. Make sure it's running on port 8000.",
          variant: "destructive"
        });
        // Set default roles if API fails
        setAvailableRoles([
          { key: "cloud_engineer", display_name: "Cloud Engineer" },
          { key: "machine_learning_engineer", display_name: "Machine Learning Engineer" },
          { key: "data_scientist", display_name: "Data Scientist" },
          { key: "software_engineer", display_name: "Software Engineer" },
        ]);
      }
    };
    fetchRoles();
  }, []);

  const fetchJobs = async () => {
    setLoading(true);
    setError(null);
    setWarning(null);
    
    try {
      if (!linkedinEmail || !linkedinPassword) {
        throw new Error("Please enter your LinkedIn email and password.");
      }

      console.log("Fetching jobs with role:", jobRole, "filtering:", enableFiltering);

      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${API_BASE_URL}/api/linkedin/recommended-jobs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          linkedin_email: linkedinEmail,
          linkedin_password: linkedinPassword,
          max_jobs: 25,
          job_role: jobRole,
          enable_filtering: enableFiltering,
        }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data: ApiResponse = await response.json();
      
      console.log("API Response:", data);
      
      if (data.status === "success") {
        const jobsList = (data.jobs || []).map((j) => ({
          ...j,
          company: cleanCompany(j.company),
        }));
        
        setJobs(jobsList);
        setFilteredFrom(data.filtered_from || data.total);
        
        // Show warning if present
        if (data.warning) {
          setWarning(data.warning);
        }
        
        toast({
          title: "Success!",
          description: data.filter_applied 
            ? `Found ${data.total} relevant jobs (filtered from ${data.filtered_from || data.total} total)`
            : `Fetched ${data.total} jobs from LinkedIn`,
        });
      } else {
        throw new Error(data.message || "Failed to fetch jobs");
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch jobs";
      setError(errorMessage);
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Briefcase className="h-6 w-6" />
            LinkedIn Recommended Jobs
          </CardTitle>
          <CardDescription>
            Fetch and display your personalized LinkedIn job recommendations with intelligent role-based filtering
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 mb-4">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="job-role" className="flex items-center gap-2">
                <Filter className="h-4 w-4" />
                Job Role (for display)
              </Label>
              <Select value={jobRole} onValueChange={setJobRole}>
                <SelectTrigger id="job-role">
                  <SelectValue placeholder="Select a job role" />
                </SelectTrigger>
                <SelectContent>
                  {availableRoles.map((role) => (
                    <SelectItem key={role.key} value={role.key}>
                      {role.display_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div className="space-y-3 sm:col-span-2">
              <div className="flex items-center space-x-2">
                <Checkbox 
                  id="enable-filtering" 
                  checked={enableFiltering}
                  onCheckedChange={(checked) => setEnableFiltering(checked as boolean)}
                />
                <Label 
                  htmlFor="enable-filtering" 
                  className="text-sm font-normal cursor-pointer"
                >
                  Enable strict role filtering (may return fewer jobs)
                </Label>
              </div>
              <p className="text-xs text-muted-foreground pl-6">
                {enableFiltering 
                  ? "⚡ Will filter jobs to match selected role keywords exactly (recommended for specific searches)"
                  : "📋 Will show all LinkedIn recommendations (LinkedIn has already pre-filtered based on your profile)"}
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="linkedin-email">LinkedIn Email</Label>
              <Input
                id="linkedin-email"
                type="email"
                placeholder="you@example.com"
                value={linkedinEmail}
                onChange={(e) => setLinkedinEmail(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="linkedin-password">LinkedIn Password</Label>
              <Input
                id="linkedin-password"
                type="password"
                placeholder="••••••••"
                value={linkedinPassword}
                onChange={(e) => setLinkedinPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
          </div>

          <Button 
            onClick={fetchJobs} 
            disabled={loading}
            className="w-full sm:w-auto"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Fetching Jobs...
              </>
            ) : (
              "Fetch Recommended Jobs"
            )}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">Error</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{error}</p>
          </CardContent>
        </Card>
      )}

      {warning && !error && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{warning}</AlertDescription>
        </Alert>
      )}

      {jobs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Found {jobs.length} Jobs</CardTitle>
            <CardDescription>
              {filteredFrom > jobs.length 
                ? `Showing ${jobs.length} relevant jobs (filtered from ${filteredFrom} total using AI matching)`
                : `Jobs shown below. Use the link column to open LinkedIn.`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="w-full overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="text-left py-2 pr-4">#</th>
                    <th className="text-left py-2 pr-4">Role</th>
                    <th className="text-left py-2 pr-4">Title</th>
                    <th className="text-left py-2 pr-4">Company</th>
                    <th className="text-left py-2 pr-4">Location</th>
                    <th className="text-left py-2">Link</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.url} className="border-b last:border-b-0">
                      <td className="py-3 pr-4 align-top">{job.index}</td>
                      <td className="py-3 pr-4 align-top">
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary">
                          {availableRoles.find(r => r.key === jobRole)?.display_name || jobRole}
                        </span>
                      </td>
                      <td className="py-3 pr-4 align-top">
                        <div className="flex items-start gap-2">
                          <Briefcase className="h-4 w-4 mt-0.5 text-muted-foreground flex-shrink-0" />
                          <span className="font-medium">{job.title}</span>
                        </div>
                      </td>
                      <td className="py-3 pr-4 align-top">
                        <div className="flex items-start gap-2">
                          <Building2 className="h-4 w-4 mt-0.5 text-muted-foreground flex-shrink-0" />
                          <span>{cleanCompany(job.company)}</span>
                        </div>
                      </td>
                      <td className="py-3 pr-4 align-top">
                        <div className="flex items-start gap-2">
                          <MapPin className="h-4 w-4 mt-0.5 text-muted-foreground flex-shrink-0" />
                          <span>{job.location}</span>
                        </div>
                      </td>
                      <td className="py-3 align-top">
                        <a
                          href={job.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-primary hover:underline whitespace-nowrap"
                        >
                          Open
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {!loading && jobs.length === 0 && !error && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <Briefcase className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No jobs loaded yet. Click "Fetch Recommended Jobs" to get started.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
