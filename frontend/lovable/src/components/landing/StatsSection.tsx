import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Send, Users, TrendingUp, Clock } from "lucide-react";

interface StatItemProps {
  icon: React.ReactNode;
  value: number;
  suffix: string;
  label: string;
  delay: number;
}

const StatItem = ({ icon, value, suffix, label, delay }: StatItemProps) => {
  const [count, setCount] = useState(0);
  const [hasAnimated, setHasAnimated] = useState(false);

  useEffect(() => {
    if (hasAnimated) return;
    
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !hasAnimated) {
          setHasAnimated(true);
          let start = 0;
          const end = value;
          const duration = 2000;
          const increment = end / (duration / 16);

          const timer = setInterval(() => {
            start += increment;
            if (start >= end) {
              setCount(end);
              clearInterval(timer);
            } else {
              setCount(Math.floor(start));
            }
          }, 16);

          return () => clearInterval(timer);
        }
      },
      { threshold: 0.5 }
    );

    const element = document.getElementById(`stat-${label.replace(/\s/g, '-')}`);
    if (element) observer.observe(element);

    return () => observer.disconnect();
  }, [value, label, hasAnimated]);

  return (
    <motion.div
      id={`stat-${label.replace(/\s/g, '-')}`}
      initial={{ opacity: 0, scale: 0.8 }}
      whileInView={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, delay }}
      viewport={{ once: true }}
      className="text-center p-6"
    >
      <div className="w-14 h-14 rounded-2xl bg-primary/20 flex items-center justify-center mx-auto mb-4">
        <div className="text-primary">{icon}</div>
      </div>
      <div className="text-4xl md:text-5xl font-bold font-display gradient-text mb-2">
        {count.toLocaleString()}{suffix}
      </div>
      <div className="text-muted-foreground">{label}</div>
    </motion.div>
  );
};

const stats = [
  { icon: <Send className="w-6 h-6" />, value: 10000, suffix: "+", label: "Applications Sent" },
  { icon: <Users className="w-6 h-6" />, value: 500, suffix: "+", label: "Happy Users" },
  { icon: <TrendingUp className="w-6 h-6" />, value: 92, suffix: "%", label: "Success Rate" },
  { icon: <Clock className="w-6 h-6" />, value: 24, suffix: "/7", label: "Automation" },
];

export const StatsSection = () => {
  return (
    <section className="py-20 px-4 relative">
      <div className="absolute inset-0 bg-gradient-to-r from-primary/5 via-primary/10 to-primary/5" />
      <div className="absolute inset-0 floating-particles opacity-30" />
      
      <div className="max-w-6xl mx-auto relative z-10">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 md:gap-8">
          {stats.map((stat, index) => (
            <StatItem
              key={stat.label}
              {...stat}
              delay={index * 0.1}
            />
          ))}
        </div>
      </div>
    </section>
  );
};
