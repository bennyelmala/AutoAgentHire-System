import { useState } from "react";
import { useToast } from "@/hooks/use-toast";
import ResumeUploadPanel from "@/components/ATS/ResumeUploadPanel";
import JobDescriptionPanel from "@/components/ATS/JobDescriptionPanel";
import ATSScoreCard from "@/components/ATS/ATSScoreCard";
import KeywordMatchTable from "@/components/ATS/KeywordMatchTable";
import CoverLetterPanel from "@/components/ATS/CoverLetterPanel";
import { ArrowLeft, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

interface ATSResult {
  score: number;  // Main ATS score from backend
  match_score?: number;  // Backwards compatibility field
  matched_keywords: string[];
  missing_keywords: string[];
  matched_skills: string[];
  suggestions: string[];
  resume_text?: string;
}

const ATSChecker = () => {
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jobDescription, setJobDescription] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<ATSResult | null>(null);
  const [coverLetter, setCoverLetter] = useState("");
  const [isGeneratingCoverLetter, setIsGeneratingCoverLetter] = useState(false);
  const { toast } = useToast();
  const navigate = useNavigate();

  const handleAnalyze = async () => {
    if (!resumeFile) {
      toast({
        title: "Missing Resume",
        description: "Please upload your resume first",
        variant: "destructive",
      });
      return;
    }

    if (!jobDescription.trim()) {
      toast({
        title: "Missing Job Description",
        description: "Please paste the job description",
        variant: "destructive",
      });
      return;
    }

    setIsAnalyzing(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("resume", resumeFile);  // Backend expects "resume" not "resume_file"
      formData.append("job_description", jobDescription);

      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
      const response = await fetch(`${API_BASE_URL}/api/ats/match`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setResult(data);

      const displayScore = data.score || data.match_score || 0;
      toast({
        title: "✅ Analysis Complete!",
        description: `Your ATS score is ${displayScore}%`,
      });
    } catch (error: any) {
      console.error("ATS analysis error:", error);
      toast({
        title: "Analysis Failed",
        description: error.message || "Failed to analyze resume. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleReset = () => {
    setResumeFile(null);
    setJobDescription("");
    setResult(null);
    setCoverLetter("");
  };

  const handleGenerateCoverLetter = async () => {
    if (!result?.resume_text || !jobDescription) {
      toast({
        title: "Missing Information",
        description: "Resume and job description are required",
        variant: "destructive",
      });
      return;
    }

    setIsGeneratingCoverLetter(true);

    try {
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
      const response = await fetch(`${API_BASE_URL}/api/cover-letter/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          resume_text: result.resume_text,
          job_description: jobDescription,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || "Failed to generate cover letter");
      }

      const data = await response.json();
      setCoverLetter(data.cover_letter);

      toast({
        title: "✨ Cover Letter Generated!",
        description: "Your personalized cover letter is ready",
      });
    } catch (error: any) {
      console.error("Cover letter generation error:", error);
      toast({
        title: "Generation Failed",
        description: error.message || "Failed to generate cover letter. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsGeneratingCoverLetter(false);
    }
  };

  const handleCopyCoverLetter = () => {
    navigator.clipboard.writeText(coverLetter);
    toast({
      title: "Copied!",
      description: "Cover letter copied to clipboard",
    });
  };

  const handleDownloadCoverLetter = () => {
    const blob = new Blob([coverLetter], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "cover-letter.txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    toast({
      title: "Downloaded!",
      description: "Cover letter saved successfully",
    });
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("/dashboard")}
                className="text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Dashboard
              </Button>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gradient-to-br from-primary to-primary/60 rounded-lg">
                  <Sparkles className="w-6 h-6 text-primary-foreground" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold">ATS Checker</h1>
                  <p className="text-sm text-muted-foreground">Optimize your resume for Applicant Tracking Systems</p>
                </div>
              </div>
            </div>
            {result && (
              <Button
                onClick={handleReset}
                variant="outline"
                className="border-border hover:bg-accent"
              >
                New Analysis
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="container mx-auto px-6 py-8">
        {!result ? (
          /* Input Phase */
          <div className="grid md:grid-cols-2 gap-6 max-w-6xl mx-auto">
            <ResumeUploadPanel
              file={resumeFile}
              onFileChange={setResumeFile}
              onAnalyze={handleAnalyze}
              isAnalyzing={isAnalyzing}
            />
            <JobDescriptionPanel
              value={jobDescription}
              onChange={setJobDescription}
            />
          </div>
        ) : (
          /* Results Phase */
          <div className="max-w-7xl mx-auto space-y-6">
            {/* Score Overview */}
            <div className="grid md:grid-cols-3 gap-6">
              <ATSScoreCard score={Math.round(result.score || result.match_score || 0)} />
              
              <div className="bg-card border border-border rounded-xl p-6 shadow-lg">
                <h4 className="text-sm text-muted-foreground font-medium mb-2">Keyword Match</h4>
                <p className="text-3xl font-bold text-primary">
                  {result.matched_keywords.length > 0 
                    ? Math.round((result.matched_keywords.length / (result.matched_keywords.length + result.missing_keywords.length)) * 100)
                    : 0}%
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  {result.matched_keywords.length} / {result.matched_keywords.length + result.missing_keywords.length} keywords
                </p>
              </div>

              <div className="bg-card border border-border rounded-xl p-6 shadow-lg">
                <h4 className="text-sm text-muted-foreground font-medium mb-2">Skills Match</h4>
                <p className="text-3xl font-bold text-primary">
                  {result.matched_skills.length}
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  Technical skills found
                </p>
              </div>
            </div>

            {/* Keyword Analysis */}
            <KeywordMatchTable
              matchedKeywords={result.matched_keywords}
              missingKeywords={result.missing_keywords}
              matchedSkills={result.matched_skills}
              suggestions={result.suggestions}
            />

            {/* Cover Letter Section */}
            {!coverLetter && !isGeneratingCoverLetter && (
              <div className="flex justify-center pt-4">
                <Button
                  onClick={handleGenerateCoverLetter}
                  size="lg"
                  className="bg-gradient-to-r from-primary to-primary/60 hover:from-primary/90 hover:to-primary/70"
                >
                  <Sparkles className="w-5 h-5 mr-2" />
                  Generate AI Cover Letter
                </Button>
              </div>
            )}

            {(coverLetter || isGeneratingCoverLetter) && (
              <CoverLetterPanel
                coverLetter={coverLetter}
                onChange={setCoverLetter}
                onCopy={handleCopyCoverLetter}
                onDownload={handleDownloadCoverLetter}
                isLoading={isGeneratingCoverLetter}
              />
            )}

            {/* Action Buttons */}
            <div className="flex gap-4 justify-center pt-4">
              <Button
                onClick={handleReset}
                variant="outline"
                className="border-slate-600 text-white hover:bg-slate-800"
              >
                Analyze Another Resume
              </Button>
              <Button
                onClick={() => navigate("/dashboard/search")}
                className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
              >
                Find Matching Jobs
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ATSChecker;

