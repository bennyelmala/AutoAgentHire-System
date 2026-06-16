import { CheckCircle, AlertCircle, Lightbulb } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface KeywordMatchTableProps {
  matchedKeywords: string[];
  missingKeywords: string[];
  matchedSkills: string[];
  suggestions: string[];
}

export default function KeywordMatchTable({
  matchedKeywords,
  missingKeywords,
  matchedSkills,
  suggestions
}: KeywordMatchTableProps) {
  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-lg col-span-2">
      <h3 className="font-semibold text-lg mb-6">Keyword Analysis</h3>

      <div className="space-y-6">
        {/* Matched Keywords */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle className="w-5 h-5 text-success" />
            <h4 className="text-sm font-semibold">
              Matched Keywords ({matchedKeywords.length})
            </h4>
          </div>
          <div className="flex flex-wrap gap-2">
            {matchedKeywords.slice(0, 20).map((keyword, idx) => (
              <Badge 
                key={idx} 
                className="bg-success/20 text-success border-success/30 hover:bg-success/30"
              >
                {keyword}
              </Badge>
            ))}
          </div>
        </div>

        {/* Missing Keywords */}
        {missingKeywords.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <AlertCircle className="w-5 h-5 text-destructive" />
              <h4 className="text-sm font-semibold">
                Missing Keywords ({missingKeywords.length})
              </h4>
            </div>
            <div className="flex flex-wrap gap-2">
              {missingKeywords.slice(0, 15).map((keyword, idx) => (
                <Badge 
                  key={idx} 
                  className="bg-destructive/20 text-destructive border-destructive/30 hover:bg-destructive/30"
                >
                  {keyword}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Matched Skills */}
        {matchedSkills.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold mb-3">
              Your Matching Skills
            </h4>
            <div className="flex flex-wrap gap-2">
              {matchedSkills.map((skill, idx) => (
                <Badge 
                  key={idx} 
                  className="bg-primary/20 text-primary border-primary/30 hover:bg-primary/30"
                >
                  {skill}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Suggestions */}
        {suggestions.length > 0 && (
          <div className="bg-warning/10 border border-warning/20 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <Lightbulb className="w-5 h-5 text-warning" />
              <h4 className="text-sm font-semibold text-warning">
                Improvement Suggestions
              </h4>
            </div>
            <ul className="space-y-2 text-sm text-foreground">
              {suggestions.map((suggestion, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-warning mt-1">•</span>
                  <span>{suggestion}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
