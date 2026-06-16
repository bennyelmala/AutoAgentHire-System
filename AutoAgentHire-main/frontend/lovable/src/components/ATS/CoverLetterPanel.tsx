import { FileText, Copy, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface CoverLetterPanelProps {
  coverLetter: string;
  onChange: (value: string) => void;
  onCopy: () => void;
  onDownload: () => void;
  isLoading: boolean;
}

export default function CoverLetterPanel({
  coverLetter,
  onChange,
  onCopy,
  onDownload,
  isLoading
}: CoverLetterPanelProps) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-lg col-span-3">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-primary" />
          <h3 className="font-semibold text-lg">
            AI-Generated Cover Letter
          </h3>
        </div>
        {!isLoading && coverLetter && (
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={onCopy}
            >
              <Copy className="w-4 h-4 mr-2" />
              Copy
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onDownload}
            >
              <Download className="w-4 h-4 mr-2" />
              Download
            </Button>
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center h-64 text-center">
          <div className="animate-spin text-5xl mb-4">⏳</div>
          <p className="text-muted-foreground text-lg">Generating your personalized cover letter...</p>
          <p className="text-muted-foreground text-sm mt-2">Powered by Google Gemini AI</p>
        </div>
      ) : (
        <Textarea
          value={coverLetter}
          onChange={(e) => onChange(e.target.value)}
          className="w-full h-64 bg-background border-border resize-none focus:ring-2 focus:ring-primary font-mono text-sm leading-relaxed"
          placeholder="Your AI-generated cover letter will appear here after analysis..."
        />
      )}

      {!isLoading && coverLetter && (
        <p className="mt-2 text-xs text-muted-foreground">
          ✨ Editable • {coverLetter.length} characters
        </p>
      )}
    </div>
  );
}
