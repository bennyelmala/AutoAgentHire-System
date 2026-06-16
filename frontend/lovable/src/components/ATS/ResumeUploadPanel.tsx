import { Upload, CheckCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ResumeUploadPanelProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
  onAnalyze: () => void;
  isAnalyzing: boolean;
}

export default function ResumeUploadPanel({ 
  file, 
  onFileChange, 
  onAnalyze, 
  isAnalyzing 
}: ResumeUploadPanelProps) {
  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
      if (!validTypes.includes(selectedFile.type)) {
        alert('Please upload a PDF or DOCX file');
        return;
      }
      if (selectedFile.size > 10 * 1024 * 1024) {
        alert('File must be less than 10MB');
        return;
      }
      onFileChange(selectedFile);
    }
  };

  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-lg">
      <div className="flex items-center gap-2 mb-4">
        <Upload className="w-5 h-5 text-primary" />
        <h3 className="font-semibold text-lg">Upload Resume</h3>
      </div>

      {!file ? (
        <label className="flex flex-col items-center justify-center h-64 border-2 border-dashed border-border rounded-lg cursor-pointer hover:border-primary transition-colors bg-accent/50">
          <Upload className="w-12 h-12 text-muted-foreground mb-3" />
          <p className="text-foreground font-medium mb-1">Click to upload resume</p>
          <p className="text-muted-foreground text-sm">PDF or DOCX (max 10MB)</p>
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileInput}
            className="hidden"
          />
        </label>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-success/10 border border-success/30 rounded-lg">
            <div className="flex items-center gap-3">
              <CheckCircle className="w-6 h-6 text-success flex-shrink-0" />
              <div className="min-w-0">
                <p className="font-medium truncate">{file.name}</p>
                <p className="text-muted-foreground text-sm">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
            </div>
            <button
              onClick={() => onFileChange(null)}
              className="text-destructive hover:text-destructive/80 ml-2"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <Button
            onClick={onAnalyze}
            disabled={isAnalyzing}
            className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold py-6 text-lg"
          >
            {isAnalyzing ? (
              <>
                <span className="animate-spin mr-2">⏳</span>
                Analyzing...
              </>
            ) : (
              "Analyze Resume"
            )}
          </Button>
        </div>
      )}
    </div>
  );
}
