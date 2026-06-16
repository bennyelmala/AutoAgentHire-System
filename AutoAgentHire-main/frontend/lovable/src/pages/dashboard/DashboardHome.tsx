import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import {
  Send, Eye, TrendingUp, TrendingDown,
  Pause, FileText, Search, Activity
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Link, useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import { apiClient, API_ENDPOINTS } from "@/lib/api";

const DashboardHome = () => {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [agentStatus, setAgentStatus] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [userName, setUserName] = useState<string>("");

  // Fetch logged-in user's name
  useEffect(() => {
    const fetchUser = async () => {
      try {
        const response = await apiClient.get(API_ENDPOINTS.auth.me);
        const user = response.data;
        if (user.full_name && user.full_name.trim()) {
          setUserName(user.full_name.split(" ")[0]);
        } else if (user.email) {
          setUserName(user.email.split("@")[0]);
        }
      } catch (error) {
        console.error("Failed to fetch user profile:", error);
      }
    };
    fetchUser();
  }, []);

  // Fetch agent status
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const response = await fetch(`${API_BASE_URL}/api/agent/status`);
        const data = await response.json();
        setAgentStatus(data.detail);
      } catch (error) {
        console.error('Failed to fetch status:', error);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleStartSearch = () => {
    // Navigate to search configuration page
    navigate('/dashboard/search');
  };

  const stats = [
    { 
      title: "Total Applications", 
      value: agentStatus?.applications_submitted || "0", 
      change: agentStatus?.applications_submitted > 0 ? "+12%" : null, 
      trend: "up",
      icon: Send,
      color: "text-primary",
      bgColor: "bg-primary/20"
    },
    { 
      title: "Jobs Found Today", 
      value: agentStatus?.jobs_found || "0", 
      subtitle: "Matching your criteria",
      icon: Search,
      color: "text-success",
      bgColor: "bg-success/20"
    },
    { 
      title: "Status", 
      value: agentStatus?.status === "running" ? "Active" : agentStatus?.status === "completed" ? "Complete" : "Idle", 
      subtitle: agentStatus?.phase || "Ready to start",
      icon: Activity,
      color: agentStatus?.status === "running" ? "text-success" : "text-warning",
      bgColor: agentStatus?.status === "running" ? "bg-success/20" : "bg-warning/20"
    },
    { 
      title: "Previewed", 
      value: agentStatus?.applications_previewed || "0", 
      subtitle: "Ready to apply",
      icon: Eye,
      color: "text-electric",
      bgColor: "bg-electric/20"
    },
  ];

  return (
    <div className="space-y-8">
      {/* Welcome section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="text-3xl font-bold mb-2">
          Welcome back{userName ? `, ${userName}` : ""}! 👋
        </h1>
        <p className="text-muted-foreground">
          {agentStatus?.status === "running" 
            ? "Your AI agent is actively searching for jobs and applying on LinkedIn..." 
            : "Ready to start your automated job search? Configure your preferences and let AI do the work."}
        </p>
      </motion.div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, index) => (
          <motion.div
            key={stat.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: index * 0.1 }}
          >
            <Card variant="glass" hover="glow" className="h-full">
              <CardContent className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className={`w-12 h-12 rounded-xl ${stat.bgColor} flex items-center justify-center`}>
                    <stat.icon className={`w-6 h-6 ${stat.color}`} />
                  </div>
                  {stat.change && (
                    <div className={`flex items-center gap-1 text-sm ${
                      stat.trend === "up" ? "text-success" : "text-destructive"
                    }`}>
                      {stat.trend === "up" ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                      {stat.change}
                    </div>
                  )}
                </div>
                <div className="text-3xl font-bold font-display mb-1">{stat.value}</div>
                <div className="text-sm text-muted-foreground">
                  {stat.subtitle || stat.title}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Quick actions & Automation status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quick actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="lg:col-span-2"
        >
          <Card variant="glass">
            <CardHeader>
              <CardTitle className="text-lg">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Button 
                variant="hero" 
                className="h-auto py-6 flex-col gap-2"
                onClick={handleStartSearch}
                disabled={agentStatus?.status === "running"}
              >
                {agentStatus?.status === "running" ? <Activity className="w-6 h-6 animate-pulse" /> : <Search className="w-6 h-6" />}
                <span>{agentStatus?.status === "running" ? "Agent Running..." : "Start Job Search"}</span>
              </Button>
              <Button variant="outline" className="h-auto py-6 flex-col gap-2" asChild>
                <Link to="/dashboard/resume">
                  <FileText className="w-6 h-6" />
                  <span>Upload Resume</span>
                </Link>
              </Button>
              <Button variant="outline" className="h-auto py-6 flex-col gap-2" asChild>
                <Link to="/dashboard/applications">
                  <Eye className="w-6 h-6" />
                  <span>View Applications</span>
                </Link>
              </Button>
            </CardContent>
          </Card>
        </motion.div>

        {/* Automation status */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          <Card variant="glow">
            <CardHeader>
              <CardTitle className="text-lg flex items-center justify-between">
                Automation Status
                <span className={`flex items-center gap-2 text-sm font-normal ${
                  agentStatus?.status === "running" ? "text-success" : 
                  agentStatus?.status === "completed" ? "text-primary" : "text-muted-foreground"
                }`}>
                  <span className={`w-2 h-2 rounded-full ${
                    agentStatus?.status === "running" ? "bg-success animate-pulse" : 
                    agentStatus?.status === "completed" ? "bg-primary" : "bg-muted-foreground"
                  }`} />
                  {agentStatus?.status === "running" ? "Active" : 
                   agentStatus?.status === "completed" ? "Complete" : "Idle"}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {agentStatus?.status === "running" || agentStatus?.status === "completed" ? (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground text-sm">Jobs Found</span>
                    <span className="text-sm font-medium">{agentStatus?.jobs_found || 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground text-sm">Applications</span>
                    <span className="text-sm font-medium">{agentStatus?.applications_submitted || 0}</span>
                  </div>
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div 
                      className="h-full bg-primary rounded-full transition-all" 
                      style={{ width: `${Math.min((agentStatus?.applications_submitted || 0) / 25 * 100, 100)}%` }} 
                    />
                  </div>
                  {agentStatus?.phase && (
                    <div className="text-sm text-muted-foreground">
                      Current: <span className="text-foreground font-medium">{agentStatus.phase}</span>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-4 text-muted-foreground text-sm">
                  Click "Start Job Search" to begin automation
                </div>
              )}
              <Button 
                variant="outline" 
                className="w-full" 
                size="sm"
                disabled={agentStatus?.status !== "running"}
                onClick={async () => {
                  try {
                    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
                    await fetch(`${API_BASE_URL}/api/agent/pause`, { method: 'POST' });
                    toast({ title: "Agent paused" });
                  } catch (error) {
                    toast({ title: "Failed to pause agent", variant: "destructive" });
                  }
                }}
              >
                <Pause className="w-4 h-4" />
                Pause Automation
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Agent Activity Log */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.6 }}
      >
        <Card variant="glass">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="text-lg">Live Activity Log</CardTitle>
            {agentStatus?.logs && agentStatus.logs.length > 0 && (
              <Button variant="ghost" size="sm" onClick={() => setAgentStatus(prev => ({...prev, logs: []}))}>
                Clear
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {agentStatus?.logs && agentStatus.logs.length > 0 ? (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {agentStatus.logs.slice(-10).reverse().map((log: any, index: number) => (
                  <div key={index} className="flex gap-3 p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
                    <div className={`w-2 h-2 mt-2 rounded-full flex-shrink-0 ${
                      log.level === 'ERROR' ? 'bg-destructive' : 
                      log.level === 'INFO' ? 'bg-primary' : 'bg-muted-foreground'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm">{log.message}</div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p className="text-sm">No activity yet</p>
                <p className="text-xs mt-2">Start the job search agent to see live updates</p>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
};

export default DashboardHome;
