import { motion } from "framer-motion";
import { Bot, Sparkles, Zap, FileText, Mail, BarChart3, Shield } from "lucide-react";

interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  delay?: number;
}

const FeatureCard = ({ icon, title, description, delay = 0 }: FeatureCardProps) => (
  <motion.div
    initial={{ opacity: 0, y: 30 }}
    whileInView={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.5, delay }}
    viewport={{ once: true }}
    className="group relative p-6 rounded-2xl bg-card/60 backdrop-blur-xl border border-white/10 hover:border-primary/40 transition-all duration-300 hover:-translate-y-2 hover:shadow-xl hover:shadow-primary/10"
  >
    <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
    <div className="relative z-10">
      <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center mb-4 group-hover:bg-primary/30 transition-colors">
        <div className="text-primary">{icon}</div>
      </div>
      <h3 className="text-lg font-semibold mb-2 text-foreground">{title}</h3>
      <p className="text-muted-foreground text-sm leading-relaxed">{description}</p>
    </div>
  </motion.div>
);

const features = [
  {
    icon: <Bot className="w-6 h-6" />,
    title: "AI-Powered Matching",
    description: "Smart algorithms analyze your skills and match you with perfect job opportunities automatically.",
  },
  {
    icon: <Zap className="w-6 h-6" />,
    title: "Auto-Fill Forms",
    description: "Automatically complete job applications with your data. No more repetitive typing.",
  },
  {
    icon: <FileText className="w-6 h-6" />,
    title: "Resume Optimization",
    description: "AI optimizes your resume with relevant keywords for each specific job posting.",
  },
  {
    icon: <Mail className="w-6 h-6" />,
    title: "Custom Cover Letters",
    description: "Generate personalized, compelling cover letters tailored to each position instantly.",
  },
  {
    icon: <BarChart3 className="w-6 h-6" />,
    title: "Track Applications",
    description: "Comprehensive dashboard to monitor all your applications and their status in real-time.",
  },
  {
    icon: <Shield className="w-6 h-6" />,
    title: "Secure & Private",
    description: "Your credentials and data are encrypted with enterprise-grade security protocols.",
  },
];

export const FeaturesSection = () => {
  return (
    <section className="py-24 px-4 relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-primary/5 to-transparent" />
      
      <div className="max-w-7xl mx-auto relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm font-medium mb-6">
            <Sparkles className="w-4 h-4" />
            Powerful Features
          </div>
          <h2 className="text-4xl md:text-5xl font-bold mb-6">
            Why Choose <span className="gradient-text">AutoAgentHire</span>?
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Everything you need to automate your job search and land your dream position faster than ever.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <FeatureCard
              key={feature.title}
              {...feature}
              delay={index * 0.1}
            />
          ))}
        </div>
      </div>
    </section>
  );
};
