/**
 * Agent Control Panel - Main automation interfa  const handleStart = () => {
    if (!credentials.linkedin_email || !credentials.linkedin_password) {
      toast({
        title: "Credentials Required",
        description: "Please enter your LinkedIn email and password",
        variant: "destructive",
      });
      return;
    }

    if (!resumeFile) {
      toast({
        title: "Resume Required",
        description: "Please upload your resume (PDF)",
        variant: "destructive",
      });
      return;
    }

    runAgent.mutate({
      ...searchConfig,
      ...credentials,
      keyword: searchConfig.keywords,
      skills: "", // Will be extracted from resume
      file: resumeFile,
    });
  }; LinkedIn job automation and shows real-time status
 */
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Bot, Play, Pause, Square, Loader2, CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { useRunAgent, useAgentStatus, useAgentControl } from "@/hooks/useJobAutomation";
import { useToast } from "@/hooks/use-toast";

export const AgentControlPanel = () => {
  const { data: agentStatus, isLoading: statusLoading } = useAgentStatus();
  const runAgent = useRunAgent();
  const { pause, resume, stop } = useAgentControl();
  const { toast } = useToast();

  const [searchConfig, setSearchConfig] = useState({
    keywords: "Software Engineer",
    location: "Remote",
    submit: false, // Safety: false = preview only, true = auto-submit
  });

  const [credentials, setCredentials] = useState({
    linkedin_email: "",
    linkedin_password: "",
  });

  // Load saved credentials from localStorage
  useEffect(() => {
    const savedProfile = localStorage.getItem('userProfile');
    if (savedProfile) {
      try {
        const profile = JSON.parse(savedProfile);
        setCredentials({
          linkedin_email: profile.linkedinEmail || "",
          linkedin_password: profile.linkedinPassword || "",
        });
        setSearchConfig({
          ...searchConfig,
          keywords: profile.jobKeywords?.[0] || "Software Engineer",
          location: profile.preferredLocations?.[0] || "Remote",
        });
      } catch (error) {
        console.error("Failed to load profile", error);
      }
    }
  }, []);

  const handleStart = () => {
    if (!credentials.linkedin_email || !credentials.linkedin_password) {
      toast({
        title: "Credentials Required",
        description: "Please enter your LinkedIn credentials",
        variant: "destructive",
      });
      return;
    }

    runAgent.mutate({
      ...searchConfig,
      ...credentials,
      keyword: searchConfig.keywords,
      skills: "",
      file: new File([], "temp.pdf"),
    });
  };

  const status = agentStatus?.status || "idle";
  const detail = agentStatus?.detail;

  const getStatusIcon = () => {
    switch (status) {
      case "running":
        return <Loader2 className="w-6 h-6 text-primary animate-spin" />;
      case "paused":
        return <Pause className="w-6 h-6 text-warning" />;
      case "completed":
        return <CheckCircle className="w-6 h-6 text-success" />;
      case "failed":
        return <XCircle className="w-6 h-6 text-destructive" />;
      default:
        return <Bot className="w-6 h-6 text-muted-foreground" />;
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case "running":
        return "text-primary";
      case "paused":
        return "text-warning";
      case "completed":
        return "text-success";
      case "failed":
        return "text-destructive";
      default:
        return "text-muted-foreground";
    }
  };

  const isRunning = status === "running";
  const isPaused = status === "paused";
  const canStart = status === "idle" || status === "completed" || status === "failed" || status === "stopped";

  return (
    <div className="space-y-6">
      {/* Status Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            {getStatusIcon()}
            <span>Agent Status</span>
            <span className={`ml-auto text-lg font-semibold ${getStatusColor()}`}>
              {status.toUpperCase()}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {detail && (
            <div className="space-y-4">
              {/* Current Phase */}
              {detail.phase && (
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Current Phase</p>
                  <p className="font-medium">{detail.phase}</p>
                </div>
              )}

              {/* Stats Grid */}
              <div className="grid grid-cols-3 gap-4">
                <div className="p-3 rounded-lg bg-primary/10">
                  <p className="text-sm text-muted-foreground mb-1">Jobs Found</p>
                  <p className="text-2xl font-bold text-primary">{detail.jobs_found}</p>
                </div>
                <div className="p-3 rounded-lg bg-success/10">
                  <p className="text-sm text-muted-foreground mb-1">Applied</p>
                  <p className="text-2xl font-bold text-success">{detail.applications_submitted}</p>
                </div>
                <div className="p-3 rounded-lg bg-warning/10">
                  <p className="text-sm text-muted-foreground mb-1">Previewed</p>
                  <p className="text-2xl font-bold text-warning">{detail.applications_previewed}</p>
                </div>
              </div>

              {/* Errors */}
              {detail.errors && detail.errors.length > 0 && (
                <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-destructive mt-0.5" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-destructive mb-1">Errors</p>
                      {detail.errors.map((error, index) => (
                        <p key={index} className="text-xs text-muted-foreground">{error}</p>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Recent Logs */}
              {detail.logs && detail.logs.length > 0 && (
                <div>
                  <p className="text-sm font-medium mb-2">Recent Activity</p>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {detail.logs.map((log, index) => (
                      <div key={index} className="text-xs flex items-start gap-2">
                        <span className="text-muted-foreground whitespace-nowrap">
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </span>
                        <span className={
                          log.level === "ERROR" ? "text-destructive" :
                          log.level === "WARNING" ? "text-warning" :
                          "text-muted-foreground"
                        }>
                          {log.message}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {status === "idle" && (
            <p className="text-muted-foreground">Agent is ready. Configure and start below.</p>
          )}
        </CardContent>
      </Card>

      {/* Configuration Card */}
      <Card>
        <CardHeader>
          <CardTitle>Job Search Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Keywords</label>
              <Input
                placeholder="Software Engineer, AI Engineer"
                value={searchConfig.keywords}
                onChange={(e) => setSearchConfig({...searchConfig, keywords: e.target.value})}
                disabled={isRunning}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Location</label>
              <Input
                placeholder="Remote, San Francisco"
                value={searchConfig.location}
                onChange={(e) => setSearchConfig({...searchConfig, location: e.target.value})}
                disabled={isRunning}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">LinkedIn Email</label>
              <Input
                type="email"
                placeholder="your.email@example.com"
                value={credentials.linkedin_email}
                onChange={(e) => setCredentials({...credentials, linkedin_email: e.target.value})}
                disabled={isRunning}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">LinkedIn Password</label>
              <Input
                type="password"
                placeholder="••••••••"
                value={credentials.linkedin_password}
                onChange={(e) => setCredentials({...credentials, linkedin_password: e.target.value})}
                disabled={isRunning}
              />
            </div>
          </div>

          <div className="flex items-center gap-2 p-3 rounded-lg border">
            <input
              type="checkbox"
              id="auto-submit"
              checked={searchConfig.submit}
              onChange={(e) => setSearchConfig({...searchConfig, submit: e.target.checked})}
              disabled={isRunning}
              className="w-4 h-4"
            />
            <label htmlFor="auto-submit" className="text-sm">
              <span className="font-medium">Auto-Submit Applications</span>
              <span className="text-muted-foreground block text-xs">
                If unchecked, will only preview jobs without applying
              </span>
            </label>
          </div>
        </CardContent>
      </Card>

      {/* Control Buttons */}
      <div className="flex items-center gap-3">
        {canStart && (
          <Button
            size="lg"
            onClick={handleStart}
            disabled={runAgent.isPending || !credentials.linkedin_email || !credentials.linkedin_password}
            className="flex-1"
          >
            {runAgent.isPending ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <Play className="w-5 h-5 mr-2" />
                Start Agent
              </>
            )}
          </Button>
        )}

        {isRunning && (
          <>
            <Button
              size="lg"
              variant="outline"
              onClick={() => pause.mutate()}
              disabled={pause.isPending}
              className="flex-1"
            >
              <Pause className="w-5 h-5 mr-2" />
              Pause
            </Button>
            <Button
              size="lg"
              variant="destructive"
              onClick={() => stop.mutate()}
              disabled={stop.isPending}
            >
              <Square className="w-5 h-5 mr-2" />
              Stop
            </Button>
          </>
        )}

        {isPaused && (
          <>
            <Button
              size="lg"
              onClick={() => resume.mutate()}
              disabled={resume.isPending}
              className="flex-1"
            >
              <Play className="w-5 h-5 mr-2" />
              Resume
            </Button>
            <Button
              size="lg"
              variant="destructive"
              onClick={() => stop.mutate()}
              disabled={stop.isPending}
            >
              <Square className="w-5 h-5 mr-2" />
              Stop
            </Button>
          </>
        )}
      </div>
    </div>
  );
};
