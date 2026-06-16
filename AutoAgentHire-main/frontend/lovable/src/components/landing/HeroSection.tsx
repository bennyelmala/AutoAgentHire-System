import { motion } from "framer-motion";
import { Bot, ArrowRight, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";

export const HeroSection = () => {
  return (
    <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden pt-20">
      {/* Background effects */}
      <div className="absolute inset-0 hero-gradient" />
      <div className="absolute inset-0 floating-particles opacity-40" />
      
      {/* Animated gradient orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/20 rounded-full blur-[100px] animate-float" />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-blue-500/20 rounded-full blur-[100px] animate-float" style={{ animationDelay: "2s" }} />

      <div className="relative z-10 max-w-7xl mx-auto px-4 text-center">
        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm font-medium mb-8"
        >
          <Bot className="w-4 h-4" />
          AI-Powered Job Automation
        </motion.div>

        {/* Main heading */}
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-5xl md:text-7xl lg:text-8xl font-bold mb-6 leading-tight"
        >
          Automate Your{" "}
          <span className="gradient-text">Job Hunt</span>
          <br />
          with AI
        </motion.h1>

        {/* Subheading */}
        <motion.p
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-xl md:text-2xl text-muted-foreground max-w-3xl mx-auto mb-10"
        >
          Apply to hundreds of jobs automatically while you sleep.
          Let AI handle the tedious work so you can focus on what matters.
        </motion.p>

        {/* CTA Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-16"
        >
          <Button variant="hero" size="xl" asChild>
            <Link to="/signup" className="group">
              Get Started Free
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Link>
          </Button>
          <Button variant="heroOutline" size="xl">
            <Play className="w-5 h-5" />
            Watch Demo
          </Button>
        </motion.div>

        {/* Stats preview */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.5 }}
          className="flex flex-wrap justify-center gap-8 md:gap-16"
        >
          {[
            { value: "10,000+", label: "Applications Sent" },
            { value: "500+", label: "Happy Users" },
            { value: "85%", label: "Success Rate" },
          ].map((stat) => (
            <div key={stat.label} className="text-center">
              <div className="text-3xl md:text-4xl font-bold font-display gradient-text">{stat.value}</div>
              <div className="text-muted-foreground text-sm">{stat.label}</div>
            </div>
          ))}
        </motion.div>

        {/* Hero visual */}
        <motion.div
          initial={{ opacity: 0, y: 60 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.6 }}
          className="mt-20 relative"
        >
          <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-transparent z-10 pointer-events-none" />
          <div className="relative rounded-2xl overflow-hidden border border-white/10 shadow-2xl shadow-primary/20 bg-card/80 backdrop-blur-xl p-4">
            {/* Dashboard preview mockup */}
            <div className="aspect-video rounded-lg bg-gradient-to-br from-navy-800 to-navy-900 p-6 relative overflow-hidden">
              {/* Mock dashboard elements */}
              <div className="grid grid-cols-4 gap-4 mb-6">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-20 rounded-lg bg-white/5 border border-white/10 animate-pulse" />
                ))}
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2 h-48 rounded-lg bg-white/5 border border-white/10" />
                <div className="h-48 rounded-lg bg-white/5 border border-white/10" />
              </div>
              
              {/* Floating elements for effect */}
              <div className="absolute top-4 right-4 px-3 py-1 rounded-full bg-success/20 text-success text-xs font-medium flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
                Live
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
};
