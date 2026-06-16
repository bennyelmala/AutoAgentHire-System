import { FileText } from "lucide-react";

interface JobDescriptionPanelProps {
  value: string;
  onChange: (value: string) => void;
}

export default function JobDescriptionPanel({ value, onChange }: JobDescriptionPanelProps) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-lg">
      <div className="flex items-center gap-2 mb-4">
        <FileText className="w-5 h-5 text-primary" />
        <h3 className="font-semibold text-lg">Job Description</h3>
      </div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full h-64 bg-background border border-border rounded-lg p-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary resize-none"
        placeholder="Paste the complete job description here...

Example:
Role: Senior Software Engineer
Requirements:
- 5+ years of experience
- Python, React, AWS
- Strong problem-solving skills"
      />
      <div className="mt-2 text-xs text-muted-foreground">
        {value.length} characters
      </div>
    </div>
  );
}
