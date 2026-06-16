import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import {
  ExternalLink, Briefcase, Building2, Calendar, TrendingUp, Filter, Download
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Application {
  id: number;
  title: string;
  company: string;
  url: string;
  status: string;
  applied_date: string;
  match_score: number;
}

const Applications = () => {
  const { toast } = useToast();
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<string>("all");

  // Fetch applications
  useEffect(() => {
    const fetchApplications = async () => {
      try {
        setLoading(true);
        const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        const response = await fetch(`${API_BASE_URL}/api/applications`);
        const data = await response.json();
        setApplications(data.applications || []);
      } catch (error) {
        console.error('Failed to fetch applications:', error);
        toast({
          title: "Failed to load applications",
          description: "Could not retrieve your application history",
          variant: "destructive"
        });
      } finally {
        setLoading(false);
      }
    };

    fetchApplications();
  }, []);

  const filteredApplications = filterStatus === "all" 
    ? applications 
    : applications.filter(app => app.status === filterStatus);

  const formatDate = (dateString: string) => {
    if (!dateString) return "N/A";
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric' 
      });
    } catch {
      return "N/A";
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "applied":
        return <Badge className="bg-success text-success-foreground">Applied</Badge>;
      case "pending":
        return <Badge className="bg-warning text-warning-foreground">Pending</Badge>;
      case "rejected":
        return <Badge className="bg-destructive text-destructive-foreground">Rejected</Badge>;
      case "interviewing":
        return <Badge className="bg-primary text-primary-foreground">Interviewing</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const stats = [
    { 
      label: "Total Applications", 
      value: applications.length,
      icon: Briefcase,
      color: "text-primary"
    },
    { 
      label: "Applied This Week", 
      value: applications.filter(app => {
        const appDate = new Date(app.applied_date);
        const weekAgo = new Date();
        weekAgo.setDate(weekAgo.getDate() - 7);
        return appDate > weekAgo;
      }).length,
      icon: TrendingUp,
      color: "text-success"
    },
    { 
      label: "Companies", 
      value: new Set(applications.map(app => app.company)).size,
      icon: Building2,
      color: "text-electric"
    }
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-3xl font-bold">My Applications</h1>
          <Button variant="outline" size="sm">
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
        </div>
        <p className="text-muted-foreground">
          Track all your LinkedIn job applications in one place
        </p>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {stats.map((stat, index) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: index * 0.1 }}
          >
            <Card variant="glass">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-2">
                  <stat.icon className={`w-5 h-5 ${stat.color}`} />
                  <div className="text-2xl font-bold">{stat.value}</div>
                </div>
                <div className="text-sm text-muted-foreground">{stat.label}</div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Filters */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.3 }}
      >
        <Card variant="glass">
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium mr-4">Filter by status:</span>
              <div className="flex gap-2">
                <Button
                  variant={filterStatus === "all" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilterStatus("all")}
                >
                  All
                </Button>
                <Button
                  variant={filterStatus === "applied" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilterStatus("applied")}
                >
                  Applied
                </Button>
                <Button
                  variant={filterStatus === "interviewing" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilterStatus("interviewing")}
                >
                  Interviewing
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Applications Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.4 }}
      >
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="text-lg">Application History</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-center py-8 text-muted-foreground">
                Loading applications...
              </div>
            ) : filteredApplications.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No applications found. Start your job search to see applications here.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Position / Company</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Match Score</TableHead>
                      <TableHead>Applied Date</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredApplications.map((app, index) => (
                      <motion.tr
                        key={app.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: index * 0.05 }}
                        className="group hover:bg-muted/50"
                      >
                        <TableCell>
                          <div className="flex flex-col gap-1">
                            <div className="font-medium flex items-center gap-2">
                              {app.url ? (
                                <a 
                                  href={app.url} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  className="text-primary hover:underline flex items-center gap-1"
                                >
                                  {app.title}
                                  <ExternalLink className="w-3 h-3" />
                                </a>
                              ) : (
                                <span>{app.title}</span>
                              )}
                            </div>
                            <div className="text-sm text-muted-foreground flex items-center gap-1">
                              <Building2 className="w-3 h-3" />
                              {app.company}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          {getStatusBadge(app.status)}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-primary rounded-full"
                                style={{ width: `${app.match_score}%` }}
                              />
                            </div>
                            <span className="text-sm font-medium">{app.match_score}%</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1 text-sm text-muted-foreground">
                            <Calendar className="w-3 h-3" />
                            {formatDate(app.applied_date)}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          {app.url && (
                            <Button
                              variant="ghost"
                              size="sm"
                              asChild
                            >
                              <a 
                                href={app.url} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className="opacity-0 group-hover:opacity-100 transition-opacity"
                              >
                                <ExternalLink className="w-4 h-4" />
                              </a>
                            </Button>
                          )}
                        </TableCell>
                      </motion.tr>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
};

export default Applications;
