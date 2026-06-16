import { motion } from "framer-motion";
import { Upload, Search, Rocket, ArrowRight } from "lucide-react";

const steps = [
  {
    icon: <Upload className="w-8 h-8" />,
    step: "01",
    title: "Upload Resume & Set Preferences",
    description: "Upload your resume and tell us what you're looking for. Our AI will extract your skills and experience.",
  },
  {
    icon: <Search className="w-8 h-8" />,
    step: "02",
    title: "AI Finds & Matches Jobs",
    description: "Our intelligent algorithms scan thousands of job listings to find perfect matches for your profile.",
  },
  {
    icon: <Rocket className="w-8 h-8" />,
    step: "03",
    title: "Auto-Apply & Track Progress",
    description: "Sit back while we apply to jobs automatically. Track everything from your personalized dashboard.",
  },
];

export const HowItWorksSection = () => {
  return (
    <section className="py-24 px-4 relative">
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-6">
            Get Started in <span className="gradient-text">3 Simple Steps</span>
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            From signup to your first automated application in minutes.
          </p>
        </motion.div>

        <div className="relative">
          {/* Connection line */}
          <div className="hidden lg:block absolute top-1/2 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-primary/30 to-transparent -translate-y-1/2" />

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 lg:gap-4">
            {steps.map((step, index) => (
              <motion.div
                key={step.step}
                initial={{ opacity: 0, y: 40 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: index * 0.2 }}
                viewport={{ once: true }}
                className="relative"
              >
                <div className="relative z-10 p-8 rounded-2xl bg-card/60 backdrop-blur-xl border border-white/10 hover:border-primary/30 transition-all duration-300 group hover:-translate-y-2 hover:shadow-xl">
                  {/* Step number */}
                  <div className="absolute -top-4 left-8 px-4 py-1 bg-primary text-primary-foreground text-sm font-bold rounded-full">
                    Step {step.step}
                  </div>

                  {/* Icon */}
                  <div className="w-16 h-16 rounded-2xl bg-primary/20 flex items-center justify-center mb-6 group-hover:bg-primary/30 transition-colors group-hover:scale-110 duration-300">
                    <div className="text-primary">{step.icon}</div>
                  </div>

                  <h3 className="text-xl font-semibold mb-3 text-foreground">{step.title}</h3>
                  <p className="text-muted-foreground leading-relaxed">{step.description}</p>

                  {/* Arrow for desktop */}
                  {index < steps.length - 1 && (
                    <div className="hidden lg:flex absolute -right-6 top-1/2 -translate-y-1/2 z-20 w-12 h-12 rounded-full bg-card border border-primary/30 items-center justify-center text-primary">
                      <ArrowRight className="w-5 h-5" />
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};
