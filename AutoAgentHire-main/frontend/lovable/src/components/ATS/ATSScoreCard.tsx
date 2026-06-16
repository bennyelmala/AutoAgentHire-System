import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Progress } from "@/components/ui/progress";

interface ATSScoreCardProps {
  score: number;
}

export default function ATSScoreCard({ score }: ATSScoreCardProps) {
  const getScoreColor = () => {
    if (score >= 80) return "text-success";
    if (score >= 60) return "text-warning";
    return "text-destructive";
  };

  const getScoreLabel = () => {
    if (score >= 80) return "Excellent";
    if (score >= 60) return "Good";
    return "Needs Improvement";
  };

  const getScoreIcon = () => {
    if (score >= 80) return <TrendingUp className="w-6 h-6 text-success" />;
    if (score >= 60) return <Minus className="w-6 h-6 text-warning" />;
    return <TrendingDown className="w-6 h-6 text-destructive" />;
  };

  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-sm text-muted-foreground font-medium">ATS Match Score</h4>
        {getScoreIcon()}
      </div>
      
      <div className="flex items-baseline gap-2 mb-2">
        <p className={`text-5xl font-bold ${getScoreColor()}`}>{score}</p>
        <span className="text-2xl text-muted-foreground">%</span>
      </div>
      
      <p className={`text-sm font-medium mb-4 ${getScoreColor()}`}>
        {getScoreLabel()}
      </p>
      
      <Progress value={score} className="h-2" />
    </div>
  );
}
